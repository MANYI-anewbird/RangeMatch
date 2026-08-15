"""Slice 1: malformed DeepSeek / live LLM output must fall back, never raise."""

from __future__ import annotations

import copy
import io
import json
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from rangematch.advisor_llm import generate_advisor_buyer_explanation
from rangematch.advisor_ranch_narrative import (
    render_deterministic_ranch_narrative,
    validate_ranch_narrative,
)
from rangematch.livestock_operating_profile import project_livestock_operating_profile
from rangematch.llm_provider import LLMCompletion

ROOT = Path(__file__).resolve().parents[1]


def _nambe():
    bundle = json.loads(
        (ROOT / "test-data/advisor/nambe/nambe_advisor_report_bundle.json").read_text()
    )
    packet = bundle["generic_evidence_packet"]
    uo = bundle["unified_output"]
    profile = project_livestock_operating_profile(packet, uo)
    return packet, uo, profile


def _ok_completion(content: dict) -> LLMCompletion:
    return LLMCompletion(
        content=content,
        provider="DEEPSEEK",
        model_id="deepseek-chat",
        prompt_version="test",
        generated_at="2026-08-14T00:00:00Z",
        provider_status="OK",
    )


def _provider_returning(content):
    provider = MagicMock()
    if isinstance(content, LLMCompletion):
        provider.complete_json.return_value = content
    else:
        provider.complete_json.return_value = _ok_completion(content)
    return provider


def test_conditional_path_string_falls_back_without_raising():
    """Known DeepSeek failure: conditional_path / attention_pivot as string."""
    packet, uo, profile = _nambe()
    good = render_deterministic_ranch_narrative(profile, packet)
    bad = copy.deepcopy(good)
    bad["conditional_path"] = "if access holds then visit; if not, pause."
    bad["attention_pivot"] = "water is the theme"

    provider = _provider_returning({"ranch_narrative": bad})
    with patch("rangematch.advisor_llm.get_provider", return_value=provider):
        report = generate_advisor_buyer_explanation(
            packet,
            unified_output=uo,
            operating_profile=profile,
            provider_name="DEEPSEEK",
        )
    assert report["source"] == "DETERMINISTIC_FALLBACK"
    assert report["validation_status"] in {"PASSED", "FAILED"}
    codes = {row["code"] for row in report["validation_violations"]}
    assert "RANCH_NARRATIVE_TYPE_INVALID" in codes or "RANCH_NARRATIVE_SCHEMA_INVALID" in codes
    assert report["sections"]["recommendation"]
    assert report["provenance"]["provider"] == "DEEPSEEK"


def test_ranch_narrative_missing_field_falls_back():
    packet, uo, profile = _nambe()
    good = render_deterministic_ranch_narrative(profile, packet)
    bad = copy.deepcopy(good)
    del bad["client_summary"]

    provider = _provider_returning({"ranch_narrative": bad})
    # One repair attempt also returns the same bad payload.
    provider.complete_json.side_effect = [
        _ok_completion({"ranch_narrative": bad}),
        _ok_completion({"ranch_narrative": bad}),
    ]
    with patch("rangematch.advisor_llm.get_provider", return_value=provider):
        report = generate_advisor_buyer_explanation(
            packet,
            unified_output=uo,
            operating_profile=profile,
            provider_name="DEEPSEEK",
        )
    assert report["source"] == "DETERMINISTIC_FALLBACK"
    assert any(
        row["code"] in {"RANCH_NARRATIVE_SCHEMA_INVALID", "RANCH_NARRATIVE_TYPE_INVALID"}
        for row in report["validation_violations"]
    )


def test_ranch_narrative_wrong_top_level_type_falls_back():
    packet, uo, profile = _nambe()
    provider = _provider_returning({"ranch_narrative": ["not", "an", "object"]})
    with patch("rangematch.advisor_llm.get_provider", return_value=provider):
        report = generate_advisor_buyer_explanation(
            packet,
            unified_output=uo,
            operating_profile=profile,
            provider_name="DEEPSEEK",
        )
    assert report["source"] == "DETERMINISTIC_FALLBACK"
    assert any(row["code"] == "RANCH_NARRATIVE_MISSING" for row in report["validation_violations"])


def test_provider_http_5xx_falls_back():
    packet, uo, profile = _nambe()
    failed = LLMCompletion(
        content=None,
        provider="DEEPSEEK",
        model_id="deepseek-chat",
        prompt_version="test",
        generated_at="2026-08-14T00:00:00Z",
        provider_status="FAILED_EXTERNAL",
        error_code="LLM_HTTP_ERROR",
        error_message="http_500",
    )
    with patch("rangematch.advisor_llm.get_provider", return_value=_provider_returning(failed)):
        report = generate_advisor_buyer_explanation(
            packet,
            unified_output=uo,
            operating_profile=profile,
            provider_name="DEEPSEEK",
        )
    assert report["source"] == "DETERMINISTIC_FALLBACK"
    assert report["provenance"]["provider_status"] == "FAILED_EXTERNAL"
    assert report["provenance"]["error_code"] == "LLM_HTTP_ERROR"


def test_provider_timeout_falls_back_via_provider_layer():
    packet, uo, profile = _nambe()

    def boom(*_a, **_k):
        raise TimeoutError("timed out")

    with (
        patch("rangematch.llm_provider._deepseek_api_key", return_value="ds-test"),
        patch("rangematch.llm_provider.urllib.request.urlopen", side_effect=boom),
    ):
        report = generate_advisor_buyer_explanation(
            packet,
            unified_output=uo,
            operating_profile=profile,
            provider_name="DEEPSEEK",
        )
    assert report["source"] == "DETERMINISTIC_FALLBACK"
    assert report["provenance"]["provider_status"] == "FAILED_EXTERNAL"


def test_provider_429_falls_back_when_not_retryable():
    packet, uo, profile = _nambe()
    quota = urllib.error.HTTPError(
        "https://api.deepseek.com/chat/completions",
        429,
        "quota",
        {"x-request-id": "req_quota"},
        io.BytesIO(b'{"error":{"type":"insufficient_quota","code":"insufficient_quota"}}'),
    )
    with (
        patch("rangematch.llm_provider._deepseek_api_key", return_value="ds-test"),
        patch("rangematch.llm_provider.urllib.request.urlopen", side_effect=quota),
    ):
        report = generate_advisor_buyer_explanation(
            packet,
            unified_output=uo,
            operating_profile=profile,
            provider_name="DEEPSEEK",
        )
    assert report["source"] == "DETERMINISTIC_FALLBACK"
    assert report["provenance"]["error_code"] == "LLM_RATE_LIMITED"


def test_valid_deepseek_ranch_narrative_accepted():
    packet, uo, profile = _nambe()
    good = render_deterministic_ranch_narrative(profile, packet)
    provider = _provider_returning({"ranch_narrative": good})
    with patch("rangematch.advisor_llm.get_provider", return_value=provider):
        report = generate_advisor_buyer_explanation(
            packet,
            unified_output=uo,
            operating_profile=profile,
            provider_name="DEEPSEEK",
        )
    assert report["source"] == "LIVE_LLM"
    assert report["validation_status"] == "PASSED"
    assert report["ranch_narrative"]["operating_thesis"] == good["operating_thesis"]


def test_validate_ranch_never_raises_on_string_nested_objects():
    packet, uo, profile = _nambe()
    from rangematch.advisor_insight import project_advisor_llm_workbench

    workbench = project_advisor_llm_workbench(
        packet, unified_output=uo, operating_profile=profile
    )
    ranch = render_deterministic_ranch_narrative(profile, packet)
    ranch["conditional_path"] = "string-not-object"
    ranch["attention_pivot"] = "also-string"
    violations = validate_ranch_narrative(ranch, workbench)
    assert violations
    assert any(row["code"] == "RANCH_NARRATIVE_TYPE_INVALID" for row in violations)


def test_pipeline_exception_still_returns_report():
    packet, uo, profile = _nambe()
    with patch(
        "rangematch.advisor_llm._generate_advisor_buyer_explanation",
        side_effect=RuntimeError("boom"),
    ):
        report = generate_advisor_buyer_explanation(
            packet,
            unified_output=uo,
            operating_profile=profile,
            provider_name="DEEPSEEK",
        )
    assert report["source"] == "DETERMINISTIC_FALLBACK"
    assert any(row["code"] == "LLM_PIPELINE_EXCEPTION" for row in report["validation_violations"])
