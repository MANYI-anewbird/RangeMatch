"""JSON Schema Draft 2020-12 gates sit in front of the semantic validator."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from rangematch.advisor_insight import project_advisor_llm_workbench
from rangematch.advisor_llm import generate_advisor_buyer_explanation
from rangematch.advisor_packet import (
    F03_INVENTORY_REF,
    F03_REMOTE_PILOT_REF,
    project_cper_buyer_evidence_packet,
)
from rangematch.advisor_schema import validate_insight_bundle_schema
from rangematch.llm_provider import LLMCompletion

ROOT = Path(__file__).resolve().parents[1]
MIREYE = {
    "lookup": {"ok": False, "error_class": "INVALID_INPUT", "endpoint": "/v1/lookup"},
    "contexts": {"POINT_LAND_CONTEXT": {"status": "SUCCEEDED", "error_class": None}},
}


class AdvisorSchemaGateTests(unittest.TestCase):
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
        self.bundle = json.loads((ROOT / "test-data/llm/advisor_cper_insights.json").read_text())

    def test_unknown_insight_field_fails_schema_gate(self) -> None:
        bad = copy.deepcopy(self.bundle)
        bad["insights"][0]["invented_field"] = "should fail additionalProperties"
        violations = validate_insight_bundle_schema(bad)
        self.assertTrue(violations)
        self.assertTrue(all(row["code"] == "INSIGHT_SCHEMA_INVALID" for row in violations))

    def test_unknown_field_forces_deterministic_fallback_not_fixture_swap(self) -> None:
        bad = copy.deepcopy(self.bundle)
        bad["insights"][0]["invented_field"] = "nope"

        class FakeProvider:
            provider = "OPENAI"

            def complete_json(self, **kwargs):  # noqa: ANN003
                return LLMCompletion(
                    content=bad,
                    provider="OPENAI",
                    provider_status="OK",
                    model_id="fake",
                    prompt_version="RANGEMATCH_ADVISOR_INSIGHT@0.1.0",
                    generated_at="2026-08-12T00:00:00Z",
                    error_code=None,
                    error_message=None,
                )

        with patch("rangematch.advisor_llm.get_provider", return_value=FakeProvider()):
            report = generate_advisor_buyer_explanation(
                self.packet,
                mireye_live=MIREYE,
                unified_output=self.uo,
                provider_name="OPENAI",
            )
        self.assertEqual(report["source"], "DETERMINISTIC_FALLBACK")
        self.assertEqual(report["validation_status"], "FAILED")
        self.assertTrue(
            any(row["code"] == "INSIGHT_SCHEMA_INVALID" for row in report["validation_violations"])
        )


if __name__ == "__main__":
    unittest.main()
