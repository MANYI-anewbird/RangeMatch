"""Cattle ranch narrative: Profile in workbench, guardrails, no invented infrastructure."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from rangematch.advisor_insight import project_advisor_llm_workbench
from rangematch.advisor_llm import generate_advisor_buyer_explanation
from rangematch.advisor_ranch_narrative import (
    render_deterministic_ranch_narrative,
    validate_ranch_narrative,
)
from rangematch.livestock_operating_profile import (
    profile_for_llm,
    project_livestock_operating_profile,
)

ROOT = Path(__file__).resolve().parents[1]


def _nambe():
    bundle = json.loads((ROOT / "test-data/advisor/nambe/nambe_advisor_report_bundle.json").read_text())
    return bundle["generic_evidence_packet"], bundle["unified_output"]


def test_nambe_profile_enters_workbench_without_guardrail_thesis():
    packet, uo = _nambe()
    profile = project_livestock_operating_profile(packet, uo)
    workbench = project_advisor_llm_workbench(
        packet, unified_output=uo, operating_profile=profile
    )
    assert workbench["operating_profile_hash"] == profile["profile_hash"]
    slice_ = workbench["operating_profile"]
    assert "contain" not in slice_["operating_domains"]
    assert "DRINK_DRAWABLE_WATER_NONE" not in slice_["operating_thesis_inputs"]
    assert "DRINK_DRAWABLE_WATER_NONE" not in workbench["operating_thesis_inputs"]
    llm = profile_for_llm(profile)
    assert llm["operating_thesis_inputs"] == slice_["operating_thesis_inputs"]


def test_fixture_ranch_story_passes_and_keeps_profile_hash():
    packet, uo = _nambe()
    profile = project_livestock_operating_profile(packet, uo)
    report = generate_advisor_buyer_explanation(
        packet,
        unified_output=uo,
        operating_profile=profile,
        provider_name="FIXTURE",
    )
    assert report["validation_status"] == "PASSED"
    assert report["source"] == "STRUCTURED_FIXTURE"
    assert report["operating_profile_hash"] == profile["profile_hash"]
    ranch = report["ranch_narrative"]
    assert ranch["attention_pivot"]["first_action_id"] == "ACTION_ACCESS_DOCUMENTS"
    assert "DRINK_DRAWABLE_WATER_NONE" not in json.dumps(ranch)
    assert validate_ranch_narrative(ranch, project_advisor_llm_workbench(
        packet, unified_output=uo, operating_profile=profile
    )) == []


def test_ranch_validator_rejects_stocking_and_unknown_list():
    packet, uo = _nambe()
    profile = project_livestock_operating_profile(packet, uo)
    workbench = project_advisor_llm_workbench(
        packet, unified_output=uo, operating_profile=profile
    )
    ranch = render_deterministic_ranch_narrative(profile, packet)
    ranch["operating_thesis"] = "This ranch can carry a stocking rate of 40 cow-calf pairs."
    codes = {row["code"] for row in validate_ranch_narrative(ranch, workbench)}
    assert "RANCH_PROHIBITED_CONCLUSION" in codes


@patch("rangematch.llm_provider._api_key", return_value=None)
def test_openai_miss_falls_back_to_deterministic_ranch(_key):
    packet, uo = _nambe()
    profile = project_livestock_operating_profile(packet, uo)
    report = generate_advisor_buyer_explanation(
        packet,
        unified_output=uo,
        operating_profile=profile,
        provider_name="OPENAI",
    )
    assert report["source"] == "DETERMINISTIC_FALLBACK"
    assert report["ranch_narrative"]
    assert report["operating_profile_hash"] == profile["profile_hash"]
    assert report["validation_status"] == "PASSED"
