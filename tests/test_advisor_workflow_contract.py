"""Acceptance, mutation, withdrawal, and navigation tests for the Advisor contract."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from rangematch.advisor_brief import generate_deterministic_brief
from rangematch.advisor_contract import (
    DuplicateLandFactId,
    land_fact_index,
    packet_hash,
    validate_packet,
    validate_three_page,
)
from rangematch.advisor_packet import (
    CperDemoPolicyRejected,
    F03_INVENTORY_REF,
    F03_REMOTE_PILOT_REF,
    MissingPolicyError,
    build_cper_demo_policy,
    project_buyer_evidence_packet,
    project_cper_buyer_evidence_packet,
    project_observations,
)

ROOT = Path(__file__).resolve().parents[1]
UO_PATH = ROOT / "test-data" / "land-profiles" / "unified_output_cper_001.json"
PACKET_PATH = ROOT / "test-data" / "advisor" / "cper_buyer_evidence_packet.json"
BRIEF_PATH = ROOT / "test-data" / "advisor" / "cper_three_page_brief.json"
CLAIMS_PATH = ROOT / "test-data" / "advisor" / "cper_listing_claims_fixture.json"


class AdvisorWorkflowContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.uo = json.loads(UO_PATH.read_text(encoding="utf-8"))
        self.facts = land_fact_index(self.uo)
        self.claims = json.loads(CLAIMS_PATH.read_text(encoding="utf-8"))["listing_claims"]
        self.packet = json.loads(PACKET_PATH.read_text(encoding="utf-8"))
        self.brief = json.loads(BRIEF_PATH.read_text(encoding="utf-8"))
        inventory = json.loads((ROOT / F03_INVENTORY_REF).read_text(encoding="utf-8"))
        pilot = json.loads((ROOT / F03_REMOTE_PILOT_REF).read_text(encoding="utf-8"))
        self.projected = project_cper_buyer_evidence_packet(
            self.uo,
            listing_claims=self.claims,
            candidate_inventory=inventory,
            remote_pilot=pilot,
        )

    def test_projected_packet_matches_fixture_and_canonical_facts(self) -> None:
        self.assertEqual(self.projected, self.packet)
        self.assertEqual(validate_packet(self.packet, land_facts=self.facts), [])
        slope = self.facts["VAR_F01_SLOPE_MEDIAN_DEGREES"]
        obs = next(row for row in self.packet["observations"] if row["observation_id"] == "OBS_SLOPE")
        self.assertEqual(obs["land_fact_ref"], "VAR_F01_SLOPE_MEDIAN_DEGREES")
        self.assertEqual(obs["value"], slope["value"])
        self.assertNotEqual(obs["value"], 2.4)

    def test_cper_brief_passes_bound_hash(self) -> None:
        self.assertEqual(self.brief["packet_hash"], packet_hash(self.packet))
        self.assertEqual(validate_three_page(self.brief, self.packet, land_facts=self.facts), [])

    def test_water_is_top_bottleneck_access_is_first_action(self) -> None:
        water = next(b for b in self.packet["bottlenecks"] if b["bottleneck_id"] == "BOTTLENECK_WATER_EVIDENCE")
        access = next(a for a in self.packet["actions"] if a["action_id"] == "ACTION_ACCESS_DOCUMENTS")
        self.assertEqual(water["bottleneck_rank"], 1)
        self.assertEqual(access["execution_order"], 1)
        self.assertEqual(water["next_action_ids"], ["ACTION_WATER_FIELD_CATEGORY"])

    def test_forage_gap_is_warning_only(self) -> None:
        forage = next(g for g in self.packet["claim_evidence_gaps"] if g["claim_id"] == "CLAIM_FORAGE_001")
        self.assertIsNone(forage["recommended_action_id"])
        self.assertIsNone(forage["recommended_message_id"])

    def test_objects_do_not_promote_actions_or_reorder_bottlenecks(self) -> None:
        self.assertEqual(len(self.packet["candidate_objects"]), 9)
        self.assertEqual([row["bottleneck_rank"] for row in self.packet["bottlenecks"]], [1, 2, 3])
        self.assertEqual(self.packet["bottlenecks"][0]["bottleneck_id"], "BOTTLENECK_WATER_EVIDENCE")
        for action in self.packet["actions"]:
            self.assertEqual(action["specificity"], "CATEGORY_LEVEL")
            self.assertIsNone(action["candidate_id"])

    def test_unconfirmed_parcel_cannot_feed_full_brief(self) -> None:
        packet = copy.deepcopy(self.packet)
        packet["parcel"]["confirmation_status"] = "UNCONFIRMED"
        codes = {v["code"] for v in validate_packet(packet, land_facts=self.facts)}
        self.assertIn("PARCEL_UNCONFIRMED", codes)

    def test_wrong_land_fact_id_and_rounded_value_fail(self) -> None:
        packet = copy.deepcopy(self.packet)
        obs = next(row for row in packet["observations"] if row["observation_id"] == "OBS_SLOPE")
        obs["land_fact_ref"] = "VAR_F01_SLOPE_MEDIAN_DEG"
        codes = {v["code"] for v in validate_packet(packet, land_facts=self.facts)}
        self.assertIn("LAND_FACT_REF_UNKNOWN", codes)
        obs["land_fact_ref"] = "VAR_F01_SLOPE_MEDIAN_DEGREES"
        obs["value"] = 2.4
        codes = {v["code"] for v in validate_packet(packet, land_facts=self.facts)}
        self.assertIn("LAND_FACT_VALUE_MISMATCH", codes)

    def test_reference_graph_mutations_fail(self) -> None:
        cases = [
            ("bottlenecks", 0, "supporting_observation_ids", ["OBS_MISSING"], "DANGLING_OBSERVATION_REF"),
            ("bottlenecks", 0, "affected_candidate_ids", ["USGS_NHDPLUS_HR:fake:1"], "DANGLING_CANDIDATE_REF"),
            ("bottlenecks", 0, "next_action_ids", ["ACTION_MISSING"], "DANGLING_ACTION_REF"),
            ("claim_evidence_gaps", 0, "recommended_action_id", "ACTION_MISSING", "DANGLING_GAP_ACTION"),
            ("copy_ready_message_specs", 0, "bound_claim_id", "CLAIM_MISSING", "MESSAGE_UNBOUND_CLAIM"),
        ]
        for group, index, field, value, code in cases:
            packet = copy.deepcopy(self.packet)
            packet[group][index][field] = value
            codes = {v["code"] for v in validate_packet(packet, land_facts=self.facts)}
            self.assertIn(code, codes, msg=f"{group}.{field} should fail with {code}, got {codes}")

    def test_rank_and_order_must_be_one_through_n(self) -> None:
        packet = copy.deepcopy(self.packet)
        packet["bottlenecks"][1]["bottleneck_rank"] = 1
        packet["bottlenecks"].sort(key=lambda row: row["bottleneck_rank"])
        codes = {v["code"] for v in validate_packet(packet, land_facts=self.facts)}
        self.assertIn("BOTTLENECK_RANK_SEQUENCE", codes)
        packet = copy.deepcopy(self.packet)
        packet["actions"][0]["execution_order"] = 2
        packet["actions"][1]["execution_order"] = 3
        packet["actions"].sort(key=lambda row: row["execution_order"])
        codes = {v["code"] for v in validate_packet(packet, land_facts=self.facts)}
        self.assertIn("ACTION_ORDER_SEQUENCE", codes)

    def test_placeholder_or_stale_hash_fails(self) -> None:
        brief = copy.deepcopy(self.brief)
        brief["packet_hash"] = "cper_buyer_evidence_packet_placeholder_hash01"
        codes = {v["code"] for v in validate_three_page(brief, self.packet, land_facts=self.facts)}
        self.assertIn("PACKET_HASH_MISMATCH", codes)

    def test_failed_brief_cannot_be_displayable(self) -> None:
        brief = copy.deepcopy(self.brief)
        brief["validation_status"] = "FAILED"
        codes = {v["code"] for v in validate_three_page(brief, self.packet, land_facts=self.facts)}
        self.assertIn("DISPLAYABLE_WHILE_FAILED", codes)

    def test_page_one_rejects_hold_and_absence_inventory(self) -> None:
        brief = copy.deepcopy(self.brief)
        brief["page_one_advisor"]["how_the_tract_reads"] = (
            "HOLD. We did not find verified water. F03 remains unknown."
        )
        codes = {v["code"] for v in validate_three_page(brief, self.packet, land_facts=self.facts)}
        self.assertIn("KITCHEN_ON_BUYER_PAGES", codes)
        self.assertIn("ABSENCE_INVENTORY", codes)

    def test_withdrawing_water_observation_breaks_dependents(self) -> None:
        packet = copy.deepcopy(self.packet)
        packet["observations"] = [
            row for row in packet["observations"] if row["observation_id"] != "OBS_WATER_COUNT"
        ]
        codes = {v["code"] for v in validate_packet(packet, land_facts=self.facts)}
        self.assertIn("DANGLING_OBSERVATION_REF", codes)

    def test_object_precision_rejects_pin_language_for_line(self) -> None:
        packet = copy.deepcopy(self.packet)
        target = "USGS_NHDPLUS_HR:NetworkNHDFlowline:120638830"
        packet["actions"][1]["specificity"] = "OBJECT_LEVEL"
        packet["actions"][1]["candidate_id"] = target
        brief = copy.deepcopy(self.brief)
        brief["packet_hash"] = packet_hash(packet)
        field = next(
            row
            for row in brief["page_two_actions"]["messages"]
            if row["message_id"] == "MSG_FIELD_WATER"
        )
        field["body"] = "Go to this point at the exact pin for Little Owl Creek."
        codes = {v["code"] for v in validate_three_page(brief, packet, land_facts=self.facts)}
        self.assertIn("PIN_LANGUAGE_FOR_AREA_GEOMETRY", codes)
        field["body"] = (
            "Review the Little Owl Creek mapped flowline segment as an area. "
            "Do not treat this as a well or a legal drinking source."
        )
        codes = {v["code"] for v in validate_three_page(brief, packet, land_facts=self.facts)}
        self.assertNotIn("PIN_LANGUAGE_FOR_AREA_GEOMETRY", codes)
        self.assertNotIn("INVENTED_PIN_OR_NAME", codes)
        self.assertNotIn("CATEGORY_MESSAGE_NAMES_OBJECT", codes)

    def test_category_level_still_rejects_named_object_or_pin(self) -> None:
        brief = copy.deepcopy(self.brief)
        field = next(
            row
            for row in brief["page_two_actions"]["messages"]
            if row["message_id"] == "MSG_FIELD_WATER"
        )
        field["body"] = (
            "Walk these two points at Little Owl Creek and stand on the exact pin."
        )
        codes = {v["code"] for v in validate_three_page(brief, self.packet, land_facts=self.facts)}
        self.assertTrue(
            {"INVENTED_PIN_OR_NAME", "CATEGORY_MESSAGE_NAMES_OBJECT"} & codes
        )

    def test_missing_unified_output_is_fail_closed(self) -> None:
        packet = copy.deepcopy(self.packet)
        packet["technical_references"]["unified_output"] = "test-data/missing_unified_output.json"
        codes = {v["code"] for v in validate_packet(packet)}
        self.assertIn("PACKET_SOURCE_UNAVAILABLE", codes)

    def test_observations_cannot_be_hand_typed_off_canonical_index(self) -> None:
        projected = project_observations(self.uo)
        self.assertEqual(
            {row["land_fact_ref"] for row in projected},
            {spec["land_fact_ref"] for spec in projected},
        )
        for row in projected:
            self.assertEqual(row["value"], self.facts[row["land_fact_ref"]]["value"])

    def test_policy_is_required_and_not_a_cper_default(self) -> None:
        with self.assertRaises(MissingPolicyError):
            project_buyer_evidence_packet(self.uo, listing_claims=self.claims)
        other = copy.deepcopy(self.uo)
        other["parcel"]["geometry_id"] = "REAL_LISTING_PARCEL_001"
        with self.assertRaises(CperDemoPolicyRejected):
            project_buyer_evidence_packet(
                other, listing_claims=self.claims, policy=build_cper_demo_policy
            )
        self.assertEqual(
            self.projected["technical_references"]["policy_scope"], "CPER_FIXTURE_ONLY"
        )

    def test_duplicate_land_fact_id_is_rejected(self) -> None:
        uo = copy.deepcopy(self.uo)
        facts = uo["factors"]["F01_TOPOGRAPHY"]["land_facts"]
        facts.append(copy.deepcopy(facts[0]))
        with self.assertRaises(DuplicateLandFactId):
            land_fact_index(uo)

    def test_geometry_hash_mismatch_fails(self) -> None:
        facts = copy.deepcopy(self.facts)
        facts["VAR_F01_SLOPE_MEDIAN_DEGREES"]["geometry_hash"] = "0" * 64
        codes = {v["code"] for v in validate_packet(self.packet, land_facts=facts)}
        self.assertIn("GEOMETRY_HASH_MISMATCH", codes)

    def test_cper_policy_cannot_enter_real_listing_packet(self) -> None:
        packet = copy.deepcopy(self.packet)
        packet["parcel"]["parcel_id"] = "SOME_REAL_PARCEL"
        packet["parcel"]["is_engineering_test_geometry"] = False
        codes = {v["code"] for v in validate_packet(packet, land_facts=self.facts)}
        self.assertIn("CPER_POLICY_ON_REAL_PARCEL", codes)

    def test_generated_brief_is_complete_kitchen(self) -> None:
        generated = generate_deterministic_brief(
            self.projected, land_facts=self.facts, unified_output=self.uo
        )
        self.assertEqual(generated, self.brief)
        kitchen = generated["page_three_kitchen"]
        for key in (
            "parcel_summary",
            "map_layers",
            "observations",
            "candidate_objects",
            "source_notes",
            "coverage_and_limitations",
            "engine_appendix",
            "validation_record",
        ):
            self.assertIn(key, kitchen)
        self.assertEqual(len(kitchen["candidate_objects"]), 9)
        self.assertEqual(len(kitchen["map_layers"]), 3)
        self.assertTrue(all(layer.get("bbox") for layer in kitchen["map_layers"]))
        self.assertEqual(
            sum(
                row["geometry"]["field_navigation_precision"] == "NOT_NAVIGABLE"
                for row in kitchen["candidate_objects"]
            ),
            6,
        )
        self.assertEqual(
            generated["page_one_advisor"]["visit_purpose"],
            "VISIT_DEPENDS_ON_DOCUMENT",
        )
        self.assertNotIn("visit_has_defined_purpose", generated["page_one_advisor"])
        self.assertTrue(kitchen["engine_appendix"]["hold_confined_to_appendix"])
        self.assertEqual(
            kitchen["engine_appendix"]["policy_scope"], "CPER_FIXTURE_ONLY"
        )
        self.assertTrue(
            any(row.get("decision_label") == "HOLD" for row in kitchen["engine_appendix"]["operation_decisions"])
        )
        flags_only = copy.deepcopy(self.brief)
        flags_only["page_three_kitchen"] = {
            "engine_ledger_present": True,
            "unified_output_ref": kitchen["unified_output_ref"],
            "hold_confined_to_appendix": True,
        }
        codes = {
            v["code"]
            for v in validate_three_page(flags_only, self.packet, land_facts=self.facts)
        }
        self.assertIn("PAGE_THREE_INCOMPLETE", codes)


if __name__ == "__main__":
    unittest.main()
