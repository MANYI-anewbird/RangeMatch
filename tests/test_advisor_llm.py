"""CPER trial LLM loop: fixture pass, six validator cases, live miss is not fixture."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from rangematch.advisor_insight import (
    project_advisor_llm_workbench,
    validate_insight_record,
)
from rangematch.advisor_llm import generate_advisor_buyer_explanation
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


if __name__ == "__main__":
    unittest.main()
