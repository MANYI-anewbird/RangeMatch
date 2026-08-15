"""Phase 3 Gate: deterministic Environmental Gap Detector."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from rangematch.environmental_gap_detector import (
    DETECTOR_ID,
    DOMAINS,
    STATUS_SUFFICIENT,
    STATUS_SUPPLEMENT,
    STATUS_UNAVAILABLE,
    TOOL_F01,
    TOOL_F02,
    TOOL_F03,
    TOOL_F04,
    TOOL_F05,
    TOOL_F08,
    detect_environmental_gaps,
    validate_environmental_gap_plan,
)
from rangematch.mireye_environmental_profile import (
    project_mireye_environmental_profile,
    validate_mireye_environmental_profile,
)

REPO = Path(__file__).resolve().parents[1]
NAMBE_PROFILE = (
    REPO
    / "test-data"
    / "mireye-environmental-profile"
    / "nambe_mireye_environmental_profile.json"
)
NAMBE_FIELDS = (
    REPO
    / "test-data"
    / "mireye-environmental-profile"
    / "nambe_mireye_field_values.json"
)


def _domain(plan: dict, name: str) -> dict:
    return next(row for row in plan["domains"] if row["domain"] == name)


class EnvironmentalGapDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = json.loads(NAMBE_PROFILE.read_text(encoding="utf-8"))
        validate_mireye_environmental_profile(self.profile)

    def test_nambe_profile_yields_schema_valid_deterministic_plan(self) -> None:
        plan_a = detect_environmental_gaps(
            self.profile,
            f06_geometry_hash=self.profile["parcel_ref"]["geometry_hash"],
            built_at="2026-08-15T20:00:00+00:00",
        )
        plan_b = detect_environmental_gaps(
            self.profile,
            f06_geometry_hash=self.profile["parcel_ref"]["geometry_hash"],
            built_at="2026-08-15T21:00:00+00:00",
        )
        validate_environmental_gap_plan(plan_a)
        self.assertEqual(plan_a["detector_id"], DETECTOR_ID)
        self.assertEqual(plan_a["plan_hash"], plan_b["plan_hash"])
        self.assertEqual(
            plan_a["ordered_supplemental_tool_ids"],
            plan_b["ordered_supplemental_tool_ids"],
        )
        self.assertFalse(plan_a["provenance"]["llm_tool_routing"])
        self.assertEqual([row["domain"] for row in plan_a["domains"]], list(DOMAINS))

    def test_every_planned_supplement_has_reason_and_capability(self) -> None:
        plan = detect_environmental_gaps(self.profile)
        self.assertTrue(plan["ordered_supplemental_tool_ids"])
        for domain in plan["domains"]:
            if domain["coverage_status"] != STATUS_SUPPLEMENT:
                continue
            self.assertTrue(domain["reason_codes"], domain)
            self.assertTrue(domain["missing_capabilities"], domain)
            self.assertTrue(domain["supplemental_tool_ids"], domain)
            for tool in domain["supplemental_tool_ids"]:
                self.assertIn(tool, plan["ordered_supplemental_tool_ids"])

    def test_f07_never_planned(self) -> None:
        plan = detect_environmental_gaps(self.profile)
        self.assertNotIn("F07_ROADS", plan["ordered_supplemental_tool_ids"])
        self.assertIn("F07_ROADS", plan["excluded_tool_ids"])
        for domain in plan["domains"]:
            self.assertNotIn("F07_ROADS", domain["supplemental_tool_ids"])
            self.assertTrue(
                all(not str(tool).startswith("F07") for tool in domain["supplemental_tool_ids"])
            )

    def test_point_only_domains_request_expected_supplements(self) -> None:
        plan = detect_environmental_gaps(self.profile)
        terrain = _domain(plan, "TERRAIN")
        feed = _domain(plan, "FEED_VEGETATION")
        water = _domain(plan, "WATER")
        soil = _domain(plan, "SOIL_ECOLOGY")
        climate = _domain(plan, "CLIMATE_HAZARD")

        self.assertEqual(terrain["coverage_status"], STATUS_SUPPLEMENT)
        self.assertEqual(terrain["supplemental_tool_ids"], [TOOL_F01])

        self.assertEqual(feed["coverage_status"], STATUS_SUPPLEMENT)
        self.assertEqual(feed["supplemental_tool_ids"], [TOOL_F02, TOOL_F08])

        self.assertEqual(water["coverage_status"], STATUS_SUPPLEMENT)
        self.assertEqual(water["supplemental_tool_ids"], [TOOL_F03])
        # Wetland parcel rows are context for wetlands, not hydro inventory sufficiency.
        self.assertIn("MISSING_PARCEL_HYDROGRAPHY_INVENTORY", water["reason_codes"])

        self.assertEqual(soil["coverage_status"], STATUS_SUPPLEMENT)
        self.assertEqual(soil["supplemental_tool_ids"], [TOOL_F04])

        self.assertEqual(climate["coverage_status"], STATUS_SUPPLEMENT)
        self.assertEqual(climate["supplemental_tool_ids"], [TOOL_F05])

        self.assertEqual(
            plan["ordered_supplemental_tool_ids"],
            [TOOL_F01, TOOL_F02, TOOL_F03, TOOL_F04, TOOL_F05, TOOL_F08],
        )

    def test_empty_domain_still_plans_supplement_not_silent_skip(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["observations"] = [
            obs
            for obs in profile["observations"]
            if obs.get("domain") != "TERRAIN"
        ]
        # Recompute hash via projector path would be ideal; detector only needs profile_hash string.
        profile["profile_hash"] = "d" * 64
        plan = detect_environmental_gaps(profile)
        terrain = _domain(plan, "TERRAIN")
        self.assertEqual(terrain["coverage_status"], STATUS_SUPPLEMENT)
        self.assertIn("MIREYE_DOMAIN_EMPTY", terrain["reason_codes"])
        self.assertEqual(terrain["supplemental_tool_ids"], [TOOL_F01])

    def test_source_unavailable_records_reason(self) -> None:
        profile = copy.deepcopy(self.profile)
        for obs in profile["observations"]:
            if obs.get("domain") == "SOIL_ECOLOGY":
                obs["status"] = "SOURCE_UNAVAILABLE"
                obs["value"] = None
                obs["canonical_for_parcel_facts"] = False
        profile["profile_hash"] = "e" * 64
        plan = detect_environmental_gaps(profile)
        soil = _domain(plan, "SOIL_ECOLOGY")
        self.assertEqual(soil["coverage_status"], STATUS_SUPPLEMENT)
        self.assertIn("MIREYE_SOURCE_UNAVAILABLE", soil["reason_codes"])
        self.assertEqual(soil["supplemental_tool_ids"], [TOOL_F04])

    def test_catalog_drift_fails_closed_to_unavailable(self) -> None:
        plan = detect_environmental_gaps(
            self.profile, catalog_drift_fail_closed=True
        )
        self.assertEqual(plan["ordered_supplemental_tool_ids"], [])
        for domain in plan["domains"]:
            self.assertEqual(domain["coverage_status"], STATUS_UNAVAILABLE)
            self.assertEqual(domain["supplemental_tool_ids"], [])
            self.assertIn("CATALOG_DRIFT_FAIL_CLOSED", domain["reason_codes"])

    def test_parcel_semantics_can_mark_domain_sufficient(self) -> None:
        profile = copy.deepcopy(self.profile)
        for obs in profile["observations"]:
            if obs.get("domain") != "TERRAIN":
                continue
            obs["spatial_semantics"] = "PARCEL"
            obs["canonical_for_parcel_facts"] = True
            obs["status"] = "RETRIEVED"
            obs["geometry_hash_ref"] = profile["parcel_ref"]["geometry_hash"]
        profile["profile_hash"] = "f" * 64
        plan = detect_environmental_gaps(profile)
        terrain = _domain(plan, "TERRAIN")
        self.assertEqual(terrain["coverage_status"], STATUS_SUFFICIENT)
        self.assertEqual(terrain["supplemental_tool_ids"], [])
        self.assertIn("MIREYE_HAS_PARCEL_SEMANTICS", terrain["reason_codes"])
        self.assertNotIn(TOOL_F01, plan["ordered_supplemental_tool_ids"])

    def test_llm_cannot_alter_plan_hash_contract(self) -> None:
        plan = detect_environmental_gaps(self.profile)
        tampered = copy.deepcopy(plan)
        tampered["ordered_supplemental_tool_ids"] = ["F02_RAP"]
        tampered["provenance"]["llm_tool_routing"] = True
        with self.assertRaises(Exception):
            validate_environmental_gap_plan(tampered)

    def test_reprojected_fields_match_fixture_plan_stability(self) -> None:
        bundle = json.loads(NAMBE_FIELDS.read_text(encoding="utf-8"))
        profile = project_mireye_environmental_profile(
            run_id="gap_detector_reproject",
            parcel_ref=bundle["parcel_ref"],
            field_values=bundle["fields"],
            fetched_at=bundle["fetched_at"],
            built_at=bundle["fetched_at"],
        )
        plan = detect_environmental_gaps(
            profile, f06_geometry_hash=bundle["parcel_ref"]["geometry_hash"]
        )
        self.assertEqual(
            plan["ordered_supplemental_tool_ids"],
            [TOOL_F01, TOOL_F02, TOOL_F03, TOOL_F04, TOOL_F05, TOOL_F08],
        )


if __name__ == "__main__":
    unittest.main()
