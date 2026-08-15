"""CPER trial LLM loop: fixture pass, six validator cases, live miss is not fixture."""

from __future__ import annotations

import copy
import io
import json
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from rangematch.advisor_insight import (
    project_advisor_llm_workbench,
    validate_insight_record,
)
from rangematch.advisor_llm import generate_advisor_buyer_explanation
from rangematch.llm_provider import OpenAILLMProvider
from rangematch.advisor_report import validate_buyer_copy_quality
from rangematch.advisor_packet import (
    F03_INVENTORY_REF,
    F03_REMOTE_PILOT_REF,
    project_cper_buyer_evidence_packet,
)

ROOT = Path(__file__).resolve().parents[1]
MIREYE = {
    "lookup": {"ok": False, "error_class": "INVALID_INPUT", "endpoint": "/v1/lookup"},
    "contexts": {
        "POINT_LAND_CONTEXT": {"status": "SUCCEEDED", "error_class": None},
    },
}


class AdvisorLlmTrialTests(unittest.TestCase):
    def setUp(self) -> None:
        uo = json.loads((ROOT / "test-data/land-profiles/unified_output_cper_001.json").read_text())
        claims = json.loads(
            (ROOT / "test-data/advisor/cper_listing_claims_fixture.json").read_text()
        )["listing_claims"]
        self.uo = uo
        self.packet = project_cper_buyer_evidence_packet(
            uo,
            listing_claims=claims,
            candidate_inventory=json.loads((ROOT / F03_INVENTORY_REF).read_text()),
            remote_pilot=json.loads((ROOT / F03_REMOTE_PILOT_REF).read_text()),
        )
        self.workbench = project_advisor_llm_workbench(
            self.packet, mireye_live=MIREYE, unified_output=uo
        )
        self.good = json.loads(
            (ROOT / "test-data/llm/advisor_cper_insights.json").read_text()
        )["insights"][0]

    def test_fixture_loop_passes_and_renders_six_sections(self) -> None:
        report = generate_advisor_buyer_explanation(
            self.packet, mireye_live=MIREYE, unified_output=self.uo, provider_name="FIXTURE"
        )
        self.assertEqual(report["source"], "STRUCTURED_FIXTURE")
        self.assertEqual(report["validation_status"], "PASSED")
        self.assertEqual(report["validation_violations"], [])
        self.assertIn("Request access documents", report["sections"]["recommendation"])
        self.assertTrue(report["sections"]["why"])
        self.assertTrue(report["sections"]["listing_jumps"])
        self.assertTrue(report["sections"]["do_now"])
        self.assertTrue(report["sections"]["if_changes"])
        self.assertTrue(report["sections"]["professional_reminders"])
        self.assertEqual(report["provenance"]["provider_status"], "FIXTURE")
        self.assertFalse(report["provenance"]["llm_used"])

    def test_only_valid_insight_is_accepted(self) -> None:
        cases = {
            "invent_well": {
                **copy.deepcopy(self.good),
                "recommendation": "This parcel has a well; go sample it first.",
            },
            "field_first": {
                **copy.deepcopy(self.good),
                "llm_recommended_order": [
                    "ACTION_WATER_FIELD_CATEGORY",
                    "ACTION_ACCESS_DOCUMENTS",
                ],
            },
            "stocking": {
                **copy.deepcopy(self.good),
                "recommendation": "This ranch's stocking rate is 40 cow-calf pairs.",
            },
            "internal_action_id": {
                **copy.deepcopy(self.good),
                "recommendation": "Prioritize ACTION_WATER_FIELD_CATEGORY next.",
            },
            "knowledge_as_fact": {
                "insight_id": "INSIGHT_BAD_KNOWLEDGE_001",
                "recommendation": "RAP already measured available forage on this tract.",
                "reasoning_type": "SUPPORTED_INTERPRETATION",
                "packet_refs": [],
                "context_refs": [],
                "knowledge_refs": ["RAP_INTERPRETATION_001"],
            },
            "unknown_ref": {
                **copy.deepcopy(self.good),
                "packet_refs": ["OBS_DOES_NOT_EXIST"],
            },
        }
        accepted = []
        for name, insight in [("valid", self.good), *cases.items()]:
            codes = {row["code"] for row in validate_insight_record(insight, self.workbench)}
            if not codes:
                accepted.append(name)
        self.assertEqual(accepted, ["valid"])

    def test_deepseek_miss_falls_back_and_ignores_openai_key(self) -> None:
        with (
            patch("rangematch.llm_provider._deepseek_api_key", return_value=None),
            patch("rangematch.llm_provider._api_key", return_value="sk-openai-dead"),
        ):
            report = generate_advisor_buyer_explanation(
                self.packet,
                mireye_live=MIREYE,
                unified_output=self.uo,
                provider_name="DEEPSEEK",
            )
        self.assertEqual(report["source"], "DETERMINISTIC_FALLBACK")
        self.assertEqual(report["provenance"]["provider"], "DEEPSEEK")
        self.assertEqual(report["provenance"]["provider_status"], "NOT_CONFIGURED")

    def test_deepseek_posts_to_deepseek_host_not_openai(self) -> None:
        captured: dict[str, str] = {}

        def fake_urlopen(req, timeout=None, context=None):  # noqa: ARG001
            captured["url"] = req.full_url
            raise RuntimeError("stop")

        with (
            patch("rangematch.llm_provider._deepseek_api_key", return_value="ds-test"),
            patch.dict("os.environ", {"RANGEMATCH_LLM_BASE_URL": "https://api.openai.com/v1"}, clear=False),
            patch("rangematch.llm_provider.urllib.request.urlopen", side_effect=fake_urlopen),
        ):
            completion = OpenAILLMProvider("DEEPSEEK").complete_json(
                system="system", user="user", prompt_version="test"
            )
        self.assertIn("api.deepseek.com", captured["url"])
        self.assertNotIn("api.openai.com", captured["url"])
        self.assertEqual(completion.provider, "DEEPSEEK")
        self.assertEqual(completion.provider_status, "FAILED_EXTERNAL")

    def test_live_request_does_not_swap_fixture_when_unconfigured(self) -> None:
        with patch("rangematch.llm_provider._api_key", return_value=None):
            report = generate_advisor_buyer_explanation(
                self.packet,
                mireye_live=MIREYE,
                unified_output=self.uo,
                provider_name="OPENAI",
            )
        self.assertEqual(report["source"], "DETERMINISTIC_FALLBACK")
        self.assertEqual(report["provenance"]["provider_status"], "NOT_CONFIGURED")
        self.assertEqual(report["provenance"]["provider"], "OPENAI")
        self.assertTrue(report["sections"]["recommendation"])

    def test_transient_429_retries_then_succeeds(self) -> None:
        limited = urllib.error.HTTPError(
            "https://api.openai.com/v1/chat/completions",
            429,
            "rate limited",
            {"x-request-id": "req_rate_limited"},
            io.BytesIO(b'{"error":{"type":"rate_limit_exceeded","code":"rate_limit_exceeded"}}'),
        )
        response = unittest.mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"choices":[{"message":{"content":"{\\"insights\\":[]}"}}]}'
        response.headers = {"x-request-id": "req_success"}
        with (
            patch("rangematch.llm_provider._api_key", return_value="test-key"),
            patch("rangematch.llm_provider._retry_delays", return_value=(0.0,)),
            patch("rangematch.llm_provider.urllib.request.urlopen", side_effect=[limited, response]),
        ):
            completion = OpenAILLMProvider().complete_json(
                system="system", user="user", prompt_version="test"
            )
        self.assertEqual(completion.provider_status, "OK")
        self.assertEqual(completion.retry_count, 1)
        self.assertEqual(completion.request_id, "req_success")

    def test_insufficient_quota_429_does_not_retry(self) -> None:
        quota = urllib.error.HTTPError(
            "https://api.openai.com/v1/chat/completions",
            429,
            "quota",
            {"x-request-id": "req_quota"},
            io.BytesIO(b'{"error":{"type":"insufficient_quota","code":"insufficient_quota"}}'),
        )
        with (
            patch("rangematch.llm_provider._api_key", return_value="test-key"),
            patch("rangematch.llm_provider.urllib.request.urlopen", side_effect=quota) as call,
        ):
            completion = OpenAILLMProvider().complete_json(
                system="system", user="user", prompt_version="test"
            )
        self.assertEqual(completion.error_code, "LLM_RATE_LIMITED")
        self.assertEqual(completion.retry_count, 0)
        self.assertEqual(completion.request_id, "req_quota")
        self.assertEqual(call.call_count, 1)

    def test_buyer_copy_gate_rejects_repetition_internal_label_and_id(self) -> None:
        report = {
            "sections": {
                "recommendation": "Request access documents first.",
                "why": (
                    "Request access documents first. Not first: repeat forage work. "
                    "Then run ACTION_WATER_FIELD_CATEGORY."
                ),
            }
        }
        codes = {row["code"] for row in validate_buyer_copy_quality(report)}
        self.assertEqual(
            codes,
            {
                "BUYER_COPY_REPEATS_RECOMMENDATION",
                "BUYER_COPY_INTERNAL_REASONING_LABEL",
                "BUYER_COPY_INTERNAL_ID",
            },
        )


if __name__ == "__main__":
    unittest.main()
