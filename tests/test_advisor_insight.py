"""Insight contract: workbench allowlist, rails, withdrawal, Mireye refs."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from rangematch.advisor_brief import generate_deterministic_brief
from rangematch.advisor_contract import land_fact_index, packet_hash, validate_packet
from rangematch.advisor_insight import (
    compute_depends_on,
    compute_withdraw_when,
    knowledge_content_hash,
    load_approved_knowledge_cards,
    project_advisor_llm_workbench,
    validate_insight_bundle,
    validate_insight_record,
    validate_knowledge_card,
)
from rangematch.advisor_packet import (
    F03_INVENTORY_REF,
    F03_REMOTE_PILOT_REF,
    project_cper_buyer_evidence_packet,
)

ROOT = Path(__file__).resolve().parents[1]
PACKET_PATH = ROOT / "test-data/advisor/cper_buyer_evidence_packet.json"
INSIGHT_PATH = ROOT / "test-data/advisor/cper_insight_records.json"

MIREYE = {
    "mode": "LIVE",
    "lookup": {"ok": False, "error_class": "INVALID_INPUT", "endpoint": "/v1/lookup"},
    "contexts": {
        "PROPERTY_DILIGENCE_CONTEXT": {"status": "SUCCEEDED", "error_class": None},
        "POINT_LAND_CONTEXT": {"status": "SUCCEEDED", "error_class": None},
        "POINT_HAZARD_CONTEXT": {"status": "SUCCEEDED", "error_class": None},
    },
}


class AdvisorInsightContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.uo = json.loads(
            (ROOT / "test-data/land-profiles/unified_output_cper_001.json").read_text()
        )
        self.facts = land_fact_index(self.uo)
        self.packet = json.loads(PACKET_PATH.read_text(encoding="utf-8"))
        self.insights = json.loads(INSIGHT_PATH.read_text(encoding="utf-8"))["insights"]
        self.workbench = project_advisor_llm_workbench(
            self.packet, mireye_live=MIREYE, unified_output=self.uo
        )

    def test_cper_packet_carries_action_policy(self) -> None:
        projected = project_cper_buyer_evidence_packet(
            self.uo,
            listing_claims=json.loads(
                (ROOT / "test-data/advisor/cper_listing_claims_fixture.json").read_text()
            )["listing_claims"],
            candidate_inventory=json.loads((ROOT / F03_INVENTORY_REF).read_text()),
            remote_pilot=json.loads((ROOT / F03_REMOTE_PILOT_REF).read_text()),
        )
        self.assertEqual(projected, self.packet)
        self.assertEqual(validate_packet(self.packet, land_facts=self.facts), [])
        self.assertEqual(
            self.packet["action_policy"]["allowed_first_actions"],
            ["ACTION_ACCESS_DOCUMENTS"],
        )
        self.assertEqual(
            self.packet["action_policy"]["action_dependencies"]["ACTION_WATER_FIELD_CATEGORY"],
            ["ACTION_ACCESS_DOCUMENTS"],
        )
        brief = generate_deterministic_brief(
            self.packet, land_facts=self.facts, unified_output=self.uo
        )
        self.assertEqual(brief["packet_hash"], packet_hash(self.packet))
        self.assertEqual(brief["validation_status"], "PASSED")

    def test_knowledge_cards_have_provenance_and_hash(self) -> None:
        cards = load_approved_knowledge_cards()
        self.assertEqual(len(cards), 3)
        self.assertTrue(all(row["review_status"] == "PROVISIONAL_FOR_CPER_TEST" for row in cards))
        for card in cards:
            self.assertEqual(validate_knowledge_card(card), [])
            self.assertEqual(card["content_hash"], knowledge_content_hash(card))
            self.assertIn("legal_conclusion", card["prohibited_use"])
            self.assertTrue(card["source_url_or_citation"])
            self.assertTrue(card["reviewed_by"])

    def test_cper_insights_pass(self) -> None:
        self.assertEqual(validate_insight_bundle(self.insights, self.workbench), [])
        first = next(row for row in self.insights if row["insight_id"] == "INSIGHT_ACCESS_FIRST_001")
        depends = compute_depends_on(first)
        self.assertIn("OBS_ROAD", depends["packet_refs"])
        self.assertIn("ACTION_ACCESS_DOCUMENTS", depends["action_refs"])
        events = {row["ref"]: row["events"] for row in compute_withdraw_when(depends)}
        self.assertIn("REMOVED", events["OBS_ROAD"])

    def test_workbench_is_allowlist_not_kitchen(self) -> None:
        dumped = json.dumps(self.workbench)
        self.assertNotIn("engine_appendix", dumped)
        self.assertNotIn("HOLD", dumped)
        self.assertIn("packet_hash", self.workbench)
        self.assertEqual(self.workbench["visit_purpose"], "VISIT_DEPENDS_ON_DOCUMENT")
        self.assertTrue(
            any(row["action_id"] == "ACTION_REPEAT_PRECIP" for row in self.workbench["action_candidates"])
        )

    def test_field_first_is_illegal(self) -> None:
        insight = copy.deepcopy(self.insights[0])
        insight["llm_recommended_order"] = [
            "ACTION_WATER_FIELD_CATEGORY",
            "ACTION_ACCESS_DOCUMENTS",
        ]
        codes = {row["code"] for row in validate_insight_record(insight, self.workbench)}
        self.assertIn("ILLEGAL_FIRST_ACTION", codes)
        self.assertIn("ACTION_DEPENDENCY_VIOLATION", codes)

    def test_execution_order_is_not_overwritten_by_pass(self) -> None:
        self.assertEqual(
            self.workbench["execution_order"][0], "ACTION_ACCESS_DOCUMENTS"
        )
        first = self.insights[0]
        self.assertEqual(first["llm_recommended_order"][0], "ACTION_ACCESS_DOCUMENTS")

    def test_mireye_as_parcel_fact_rejected(self) -> None:
        insight = {
            "insight_id": "INSIGHT_BAD_MIREYE_001",
            "recommendation": "Mireye proved the whole parcel is wet.",
            "reasoning_type": "SUPPORTED_INTERPRETATION",
            "packet_refs": [],
            "context_refs": ["MIREYE_POINT_LAND_CONTEXT"],
            "knowledge_refs": [],
        }
        codes = {row["code"] for row in validate_insight_record(insight, self.workbench)}
        self.assertIn("MIREYE_AS_PARCEL_FACT", codes)
        self.assertIn("INTERPRETATION_NEEDS_PACKET_REF", codes)

    def test_authored_withdrawal_rule_rejected(self) -> None:
        insight = copy.deepcopy(self.insights[0])
        insight["withdrawal_rule"] = "withdraw if OBS_ROAD is gone"
        codes = {row["code"] for row in validate_insight_record(insight, self.workbench)}
        self.assertIn("INSIGHT_AUTHORED_WITHDRAWAL_RULE", codes)

    def test_removed_ref_requires_withdrawal(self) -> None:
        codes = {
            row["code"]
            for row in validate_insight_record(
                self.insights[0], self.workbench, withdrawn_refs={"OBS_ROAD"}
            )
        }
        self.assertIn("INSIGHT_NOT_WITHDRAWN", codes)

    def test_invented_action_and_well_rejected(self) -> None:
        insight = copy.deepcopy(self.insights[0])
        insight["rejected_actions"] = [{"action_id": "ACTION_INVENTED", "reason": "x"}]
        insight["recommendation"] = "This parcel has a well; go sample it first."
        codes = {row["code"] for row in validate_insight_record(insight, self.workbench)}
        self.assertIn("INSIGHT_ACTION_NOT_CANDIDATE", codes)
        self.assertIn("INSIGHT_PROHIBITED_INFERENCE", codes)

    def test_stocking_and_invented_value_rank_rejected(self) -> None:
        insight = copy.deepcopy(self.insights[0])
        insight["recommendation"] = "This is the lowest cost and highest value choice."
        codes = {row["code"] for row in validate_insight_record(insight, self.workbench)}
        self.assertTrue(
            {"INSIGHT_PROHIBITED_INFERENCE", "INVENTED_INFORMATION_VALUE_RANK"} & codes
        )


if __name__ == "__main__":
    unittest.main()
