"""F03 candidate-object projection and navigation-safety tests."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from rangematch.advisor_contract import (
    has_drawable_geometry,
    land_fact_index,
    packet_hash,
    validate_packet,
    validate_three_page,
)
from rangematch.advisor_packet import (
    F03_INVENTORY_REF,
    F03_REMOTE_PILOT_REF,
    constrain_actions_to_objects,
    project_cper_buyer_evidence_packet,
    project_candidate_objects,
    rank_bottlenecks,
)

ROOT = Path(__file__).resolve().parents[1]


class F03ObjectProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.uo = json.loads(
            (ROOT / "test-data/land-profiles/unified_output_cper_001.json").read_text()
        )
        self.facts = land_fact_index(self.uo)
        self.inventory = json.loads((ROOT / F03_INVENTORY_REF).read_text())
        self.pilot = json.loads((ROOT / F03_REMOTE_PILOT_REF).read_text())
        self.claims = json.loads(
            (ROOT / "test-data/advisor/cper_listing_claims_fixture.json").read_text()
        )["listing_claims"]
        self.packet = project_cper_buyer_evidence_packet(
            self.uo,
            listing_claims=self.claims,
            candidate_inventory=self.inventory,
            remote_pilot=self.pilot,
        )
        self.brief = json.loads(
            (ROOT / "test-data/advisor/cper_three_page_brief.json").read_text()
        )

    def test_nine_identities_three_sampled_two_remote_zero_field_verified(self) -> None:
        objects = self.packet["candidate_objects"]
        self.assertEqual(len(objects), 9)
        self.assertEqual(self.packet["technical_references"]["candidate_object_count_in_packet"], 9)
        ids = [row["candidate_id"] for row in objects]
        self.assertEqual(len(set(ids)), 9)
        for row in objects:
            self.assertTrue(row["candidate_id"].startswith("USGS_NHDPLUS_HR:"))
            self.assertEqual(
                row["candidate_id"],
                f"USGS_NHDPLUS_HR:{row['source_feature_type']}:{row['source_feature_id']}",
            )
            self.assertNotEqual(row["evidence_state"], "FIELD_VERIFIED")
            self.assertIsNone(row["geometry"]["centroid"])
            self.assertNotEqual(row["geometry"]["field_navigation_precision"], "EXACT")
        self.assertEqual(sum(row["review_status"] == "SAMPLED" for row in objects), 3)
        self.assertEqual(sum(row["review_status"] == "UNREVIEWED" for row in objects), 6)
        self.assertEqual(sum(row["evidence_state"] == "REMOTELY_SUPPORTED" for row in objects), 2)
        self.assertEqual(
            [row["bottleneck_rank"] for row in self.packet["bottlenecks"]], [1, 2, 3]
        )

    def test_flowline_and_waterbody_geometry_rules(self) -> None:
        drawable = 0
        not_nav = 0
        for row in self.packet["candidate_objects"]:
            geometry = row["geometry"]
            if row["candidate_type"] == "FLOWLINE":
                self.assertEqual(geometry["kind"], "LINE")
            if row["candidate_type"] == "WATERBODY":
                self.assertEqual(geometry["kind"], "BBOX")
            if has_drawable_geometry(geometry):
                self.assertEqual(geometry["field_navigation_precision"], "AREA_ONLY")
                drawable += 1
            else:
                self.assertEqual(geometry["field_navigation_precision"], "NOT_NAVIGABLE")
                self.assertEqual(geometry.get("bbox") or [], [])
                not_nav += 1
        self.assertEqual(drawable, 3)
        self.assertEqual(not_nav, 6)
        self.assertEqual(validate_packet(self.packet, land_facts=self.facts), [])

    def test_missing_source_feature_id_cannot_be_object_level(self) -> None:
        packet = copy.deepcopy(self.packet)
        packet["candidate_objects"][0]["source_feature_id"] = None
        packet["actions"][1]["specificity"] = "OBJECT_LEVEL"
        packet["actions"][1]["candidate_id"] = packet["candidate_objects"][0]["candidate_id"]
        codes = {v["code"] for v in validate_packet(packet, land_facts=self.facts)}
        self.assertIn("OBJECT_ACTION_MISSING_SOURCE_FEATURE_ID", codes)
        demoted = constrain_actions_to_objects(packet["actions"], packet["candidate_objects"])
        self.assertEqual(demoted[1]["specificity"], "CATEGORY_LEVEL")
        self.assertIsNone(demoted[1]["candidate_id"])

    def test_centroid_cannot_become_exact_pin(self) -> None:
        packet = copy.deepcopy(self.packet)
        packet["candidate_objects"][0]["geometry"]["centroid"] = [-104.76, 40.82]
        packet["candidate_objects"][0]["geometry"]["field_navigation_precision"] = "EXACT"
        codes = {v["code"] for v in validate_packet(packet, land_facts=self.facts)}
        self.assertIn("CENTROID_PROMOTED_TO_PIN", codes)

    def test_message_may_name_only_bound_candidate(self) -> None:
        packet = copy.deepcopy(self.packet)
        bound = "USGS_NHDPLUS_HR:NetworkNHDFlowline:120638830"
        other = "USGS_NHDPLUS_HR:NHDWaterbody:120639594"
        packet["actions"][1]["specificity"] = "OBJECT_LEVEL"
        packet["actions"][1]["candidate_id"] = bound
        brief = copy.deepcopy(self.brief)
        brief["packet_hash"] = packet_hash(packet)
        field = next(
            row
            for row in brief["page_two_actions"]["messages"]
            if row["message_id"] == "MSG_FIELD_WATER"
        )
        field["body"] = f"Review {other} as well as the bound reach."
        codes = {v["code"] for v in validate_three_page(brief, packet, land_facts=self.facts)}
        self.assertIn("MESSAGE_NAMES_UNBOUND_CANDIDATE", codes)

    def test_deleting_object_demotes_or_fails_object_action(self) -> None:
        packet = copy.deepcopy(self.packet)
        target = packet["candidate_objects"][0]["candidate_id"]
        packet["actions"][1]["specificity"] = "OBJECT_LEVEL"
        packet["actions"][1]["candidate_id"] = target
        packet["candidate_objects"] = [
            row for row in packet["candidate_objects"] if row["candidate_id"] != target
        ]
        codes = {v["code"] for v in validate_packet(packet, land_facts=self.facts)}
        self.assertIn("OBJECT_ACTION_WITHOUT_OBJECT", codes)
        self.assertIn("CANDIDATE_COUNT_MISMATCH", codes)
        packet["actions"] = constrain_actions_to_objects(
            packet["actions"], packet["candidate_objects"]
        )
        packet["technical_references"]["candidate_object_count_in_packet"] = len(
            packet["candidate_objects"]
        )
        packet["bottlenecks"][0]["affected_candidate_ids"] = [
            row["candidate_id"] for row in packet["candidate_objects"]
        ]
        self.assertEqual(packet["actions"][1]["specificity"], "CATEGORY_LEVEL")
        codes = {v["code"] for v in validate_packet(packet, land_facts=self.facts)}
        self.assertNotIn("OBJECT_ACTION_WITHOUT_OBJECT", codes)
        self.assertIn("CANDIDATE_COUNT_MISMATCH", codes)

    def test_count_mismatch_and_stale_brief_hash_fail(self) -> None:
        packet = copy.deepcopy(self.packet)
        packet["technical_references"]["candidate_object_count_in_packet"] = 8
        codes = {v["code"] for v in validate_packet(packet, land_facts=self.facts)}
        self.assertIn("CANDIDATE_COUNT_MISMATCH", codes)
        new_hash = packet_hash(self.packet)
        self.assertEqual(self.brief["packet_hash"], new_hash)
        stale = copy.deepcopy(self.brief)
        stale["packet_hash"] = "0" * 64
        codes = {v["code"] for v in validate_three_page(stale, self.packet, land_facts=self.facts)}
        self.assertIn("PACKET_HASH_MISMATCH", codes)

    def test_inventory_without_feature_id_is_dropped(self) -> None:
        inventory = copy.deepcopy(self.inventory)
        inventory["candidate_inventory"][0]["source_feature_id"] = None
        objects = project_candidate_objects(inventory, self.pilot)
        self.assertEqual(len(objects), 8)

    def test_generic_ranker_is_not_production_policy(self) -> None:
        with self.assertRaises(NotImplementedError):
            rank_bottlenecks(self.packet)


if __name__ == "__main__":
    unittest.main()
