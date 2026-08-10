"""Tests for Parcel Resolution contract (FIXTURE resolver, no network)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from rangematch.parcel_resolution import (
    ADAPTER_FIXTURE,
    ADAPTER_LIVE,
    REQUIRED_CRS,
    SCHEMA_VERSION,
    TERMINAL_FAILURE,
    FixtureParcelResolver,
    LiveParcelResolver,
    ParcelResolutionError,
    apply_geometry_change_after_confirmation,
    compute_geometry_hash,
    confirm_selected_parcel,
    find_fixture_scenario_id_for_coordinates,
    get_parcel_resolver,
    is_parcel_quality_accuracy,
    planner_parcel_input,
    reject_inferred_polygon_from_geocode_point,
    select_parcel_candidate,
    start_parcel_resolution,
)
from rangematch.unified_output import validate_one_parcel_geometry


ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "test-data" / "parcel-resolution"


def _scenario(name: str) -> dict:
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


class ParcelResolutionContractTests(unittest.TestCase):
    def test_01_one_valid_candidate_requires_confirmation_then_confirms(self):
        scenario = _scenario("one_valid_candidate")
        record = start_parcel_resolution(
            scenario["raw_address"],
            mode="FIXTURE",
            scenario_id="one_valid_candidate",
        )
        self.assertEqual(record["schema_version"], SCHEMA_VERSION)
        self.assertEqual(record["adapter_id"], ADAPTER_FIXTURE)
        self.assertEqual(record["status"], "NEEDS_BOUNDARY_CONFIRMATION")
        self.assertEqual(len(record["candidates"]), 1)
        self.assertIsNone((record.get("selection") or {}).get("confirmed_at"))

        confirmed = confirm_selected_parcel(
            record,
            candidate_id="cand_demo_001",
            confirm_boundary=True,
            resolver=FixtureParcelResolver("one_valid_candidate"),
        )
        self.assertEqual(confirmed["status"], "PARCEL_CONFIRMED")
        binding = planner_parcel_input(confirmed)
        self.assertEqual(binding["source_crs"], REQUIRED_CRS)
        self.assertRegex(binding["geometry_hash"], r"^[a-f0-9]{64}$")
        validate_one_parcel_geometry(binding["parcel_geometry"])
        self.assertEqual(
            binding["geometry_hash"],
            compute_geometry_hash(binding["parcel_geometry"]),
        )

    def test_02_multiple_candidates_need_user_selection(self):
        scenario = _scenario("multiple_candidates")
        record = start_parcel_resolution(
            scenario["raw_address"],
            mode="FIXTURE",
            scenario_id="multiple_candidates",
        )
        self.assertEqual(record["status"], "NEEDS_USER_SELECTION")
        self.assertGreaterEqual(len(record["candidates"]), 2)

        selected = select_parcel_candidate(record, candidate_id="cand_demo_B")
        self.assertEqual(selected["status"], "NEEDS_BOUNDARY_CONFIRMATION")
        confirmed = confirm_selected_parcel(
            selected,
            candidate_id="cand_demo_B",
            resolver=FixtureParcelResolver("multiple_candidates"),
        )
        self.assertEqual(confirmed["status"], "PARCEL_CONFIRMED")
        self.assertEqual(
            confirmed["selection"]["selected_candidate_id"], "cand_demo_B"
        )

    def test_03_no_match(self):
        scenario = _scenario("no_match")
        record = start_parcel_resolution(
            scenario["raw_address"], mode="FIXTURE", scenario_id="no_match"
        )
        self.assertEqual(record["status"], "NO_MATCH")
        self.assertEqual(record["candidates"], [])

    def test_04_geocode_ok_parcel_lookup_fail(self):
        scenario = _scenario("geocode_ok_parcel_lookup_fail")
        record = start_parcel_resolution(
            scenario["raw_address"],
            mode="FIXTURE",
            scenario_id="geocode_ok_parcel_lookup_fail",
        )
        self.assertEqual(record["geocode"]["status"], "OK")
        self.assertEqual(record["status"], "NO_MATCH")

    def test_05_blocked_external(self):
        scenario = _scenario("blocked_external")
        record = start_parcel_resolution(
            scenario["raw_address"],
            mode="FIXTURE",
            scenario_id="blocked_external",
        )
        self.assertEqual(record["status"], "BLOCKED_EXTERNAL")

    def test_06_invalid_polygon(self):
        scenario = _scenario("invalid_polygon")
        record = start_parcel_resolution(
            scenario["raw_address"],
            mode="FIXTURE",
            scenario_id="invalid_polygon",
        )
        self.assertEqual(record["status"], "INVALID_GEOMETRY")
        self.assertTrue(
            any(
                "INVALID_POLYGON" in (c.get("validation_errors") or [])
                for c in record["candidates"]
            )
        )

    def test_07_feature_collection_empty(self):
        scenario = _scenario("feature_collection_empty")
        record = start_parcel_resolution(
            scenario["raw_address"],
            mode="FIXTURE",
            scenario_id="feature_collection_empty",
        )
        self.assertEqual(record["status"], "INVALID_GEOMETRY")
        self.assertTrue(
            any(
                "FEATURE_COLLECTION_EMPTY" in (c.get("validation_errors") or [])
                for c in record["candidates"]
            )
        )

    def test_08_feature_collection_multi(self):
        scenario = _scenario("feature_collection_multi")
        record = start_parcel_resolution(
            scenario["raw_address"],
            mode="FIXTURE",
            scenario_id="feature_collection_multi",
        )
        self.assertEqual(record["status"], "INVALID_GEOMETRY")
        self.assertTrue(
            any(
                "FEATURE_COLLECTION_MULTI" in (c.get("validation_errors") or [])
                for c in record["candidates"]
            )
        )

    def test_09_unsupported_crs(self):
        scenario = _scenario("unsupported_crs")
        record = start_parcel_resolution(
            scenario["raw_address"],
            mode="FIXTURE",
            scenario_id="unsupported_crs",
        )
        self.assertEqual(record["status"], "INVALID_GEOMETRY")
        self.assertTrue(
            any(
                "UNSUPPORTED_CRS" in (c.get("validation_errors") or [])
                for c in record["candidates"]
            )
        )

    def test_10_geometry_changed_after_confirmation(self):
        scenario = _scenario("geometry_changed_after_confirmation")
        record = start_parcel_resolution(
            scenario["raw_address"],
            mode="FIXTURE",
            scenario_id="geometry_changed_after_confirmation",
        )
        confirmed = confirm_selected_parcel(
            record,
            candidate_id="cand_demo_001",
            resolver=FixtureParcelResolver("geometry_changed_after_confirmation"),
        )
        self.assertEqual(confirmed["status"], "PARCEL_CONFIRMED")
        old_hash = confirmed["confirmed_parcel"]["geometry_hash"]

        changed = apply_geometry_change_after_confirmation(
            confirmed,
            scenario["changed_geometry"],
        )
        self.assertTrue(changed["evidence_invalidation_required"])
        self.assertEqual(changed["previous_geometry_hash"], old_hash)
        self.assertNotEqual(
            changed["confirmed_parcel"]["geometry_hash"], old_hash
        )
        self.assertEqual(changed["status"], "NEEDS_BOUNDARY_CONFIRMATION")

    def test_11_address_point_as_boundary_rejected(self):
        scenario = _scenario("address_point_as_boundary")
        record = start_parcel_resolution(
            scenario["raw_address"],
            mode="FIXTURE",
            scenario_id="address_point_as_boundary",
        )
        self.assertEqual(record["status"], "INVALID_GEOMETRY")
        self.assertTrue(
            any(
                "ADDRESS_POINT_NOT_PARCEL_BOUNDARY"
                in (c.get("validation_errors") or [])
                for c in record["candidates"]
            )
        )

    def test_12_silent_cper_substitution_rejected(self):
        scenario = _scenario("silent_cper_substitution")
        record = start_parcel_resolution(
            scenario["raw_address"],
            mode="FIXTURE",
            scenario_id="silent_cper_substitution",
        )
        self.assertEqual(record["status"], "INVALID_GEOMETRY")
        self.assertTrue(
            any(
                "SILENT_CPER_SUBSTITUTION_REJECTED"
                in (c.get("validation_errors") or [])
                for c in record["candidates"]
            ),
            record["candidates"],
        )

    def test_13_fixture_requires_explicit_scenario(self):
        with self.assertRaises(ParcelResolutionError) as ctx:
            get_parcel_resolver("FIXTURE", scenario_id=None)
        self.assertEqual(ctx.exception.code, "SCENARIO_REQUIRED")

    def test_14_live_resolver_blocked_without_network_or_cper(self):
        live = LiveParcelResolver()
        self.assertEqual(live.adapter_id, ADAPTER_LIVE)
        record = start_parcel_resolution(
            "123 Main St, Denver, CO 80202",
            resolver=live,
        )
        self.assertEqual(record["status"], "BLOCKED_EXTERNAL")
        self.assertIsNone(record.get("confirmed_parcel"))
        blob = json.dumps(record)
        self.assertNotIn("engineering_test_geometry_cper", blob)

    def test_15_refuse_infer_polygon_from_geocode_point(self):
        with self.assertRaises(ParcelResolutionError) as ctx:
            reject_inferred_polygon_from_geocode_point(
                {"type": "Point", "coordinates": [-104.895, 40.495]},
                buffer_degrees=0.01,
            )
        self.assertEqual(ctx.exception.code, "INFERRED_POLYGON_FORBIDDEN")

    def test_16_single_candidate_not_auto_confirmed(self):
        scenario = _scenario("one_valid_candidate")
        record = start_parcel_resolution(
            scenario["raw_address"],
            mode="FIXTURE",
            scenario_id="one_valid_candidate",
        )
        self.assertEqual(record["status"], "NEEDS_BOUNDARY_CONFIRMATION")
        self.assertIsNone(record.get("confirmed_parcel"))
        with self.assertRaises(ParcelResolutionError) as ctx:
            confirm_selected_parcel(
                record,
                candidate_id="cand_demo_001",
                confirm_boundary=False,
            )
        self.assertEqual(ctx.exception.code, "CONFIRMATION_REQUIRED")

    def test_17_address_mismatch_refuses_fixture_geometry(self):
        with self.assertRaises(ParcelResolutionError) as ctx:
            start_parcel_resolution(
                "Totally Different Address, Nowhere, CO 80000",
                mode="FIXTURE",
                scenario_id="one_valid_candidate",
            )
        self.assertEqual(ctx.exception.code, "FIXTURE_ADDRESS_MISMATCH")

    def test_18_provenance_fields_present_on_confirmed(self):
        scenario = _scenario("one_valid_candidate")
        record = start_parcel_resolution(
            scenario["raw_address"],
            mode="FIXTURE",
            scenario_id="one_valid_candidate",
        )
        confirmed = confirm_selected_parcel(
            record,
            candidate_id="cand_demo_001",
            resolver=FixtureParcelResolver("one_valid_candidate"),
        )
        prov = confirmed["provenance"]
        for key in (
            "provider",
            "request_id",
            "retrieved_at",
            "source_crs",
            "normalized_crs",
        ):
            self.assertIn(key, prov)
        self.assertEqual(prov["normalized_crs"], REQUIRED_CRS)
        cand = confirmed["candidates"][0]
        self.assertIn("source", cand["provenance"])
        self.assertIn("reference_id", cand["provenance"])
        self.assertTrue(
            any("not verified" in x.lower() for x in confirmed["limitations"])
        )

    def test_19_planner_input_rejected_before_confirm(self):
        scenario = _scenario("one_valid_candidate")
        record = start_parcel_resolution(
            scenario["raw_address"],
            mode="FIXTURE",
            scenario_id="one_valid_candidate",
        )
        with self.assertRaises(ParcelResolutionError) as ctx:
            planner_parcel_input(record)
        self.assertEqual(ctx.exception.code, "NOT_CONFIRMED")

    def test_20_geocode_quality_and_parcel_unavailable_statuses(self):
        self.assertTrue(is_parcel_quality_accuracy("rooftop"))
        self.assertTrue(is_parcel_quality_accuracy("nearest_rooftop_match"))
        self.assertFalse(is_parcel_quality_accuracy("range_interpolation"))
        self.assertFalse(is_parcel_quality_accuracy(None))
        for status in (
            "PARCEL_DATA_UNAVAILABLE",
            "GEOCODE_QUALITY_INSUFFICIENT",
        ):
            self.assertIn(status, TERMINAL_FAILURE)

    def test_21_coordinate_fixture_resolution(self):
        scenario = _scenario("coord_one_valid_candidate")
        record = start_parcel_resolution(
            f"{scenario['latitude']},{scenario['longitude']}",
            mode="FIXTURE",
            scenario_id="coord_one_valid_candidate",
            input_kind="COORDINATE",
            latitude=float(scenario["latitude"]),
            longitude=float(scenario["longitude"]),
            lookup_kind="coord",
        )
        self.assertEqual(record["status"], "NEEDS_BOUNDARY_CONFIRMATION")
        self.assertEqual(record["input"]["input_kind"], "COORDINATE")
        self.assertEqual(record["input"]["latitude"], scenario["latitude"])
        self.assertEqual(len(record["candidates"]), 1)
        matched = find_fixture_scenario_id_for_coordinates(40.495, -104.895)
        self.assertEqual(matched, "coord_one_valid_candidate")


if __name__ == "__main__":
    unittest.main()
