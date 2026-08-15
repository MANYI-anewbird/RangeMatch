"""Phase 2 Gate: Mireye-first collection without fixed F01–F08 agenda."""

from __future__ import annotations

import unittest

from mireye_lookup_samples import UNIQUE_WITH_POLYGON

from rangematch.advisor_agent import (
    COLLECTION_MODE_LEGACY,
    COLLECTION_MODE_MIREYE_FIRST,
    OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED,
    reset_advisor_runs_for_tests,
    run_cper_advisor_agent,
    set_advisor_mireye_hooks_for_tests,
)
from rangematch.advisor_parcel_gate import (
    require_confirmed_parcel,
    stage_mireye_mapping_for_confirmation,
)
from rangematch.mireye_environmental_profile import (
    load_field_manifest,
    validate_mireye_environmental_profile,
)
from rangematch.mireye_first_collection import (
    OUTCOME_ENVIRONMENTAL_PROFILE_COMPLETED,
    OUTCOME_ENVIRONMENTAL_PROFILE_PARTIAL,
    build_mireye_fetch_body,
    manifest_field_ids,
)
from rangematch.mireye_parcel_resolver import map_mireye_lookup_to_parcel
from rangematch.parcel_resolution import confirm_selected_parcel
from rangematch.parcel_resolution_store import get_parcel_resolution_store


def _confirm_unique() -> tuple[str, str, str]:
    address = UNIQUE_WITH_POLYGON["normalized_address"]
    mapping = map_mireye_lookup_to_parcel(UNIQUE_WITH_POLYGON)
    staged = stage_mireye_mapping_for_confirmation(address=address, mapping=mapping)
    candidate_id = staged["selection"]["selected_candidate_id"]
    geometry_hash = staged["candidates"][0]["geometry_hash"]
    confirmed = confirm_selected_parcel(
        staged,
        candidate_id=candidate_id,
        confirm_boundary=True,
        expected_geometry_hash=geometry_hash,
    )
    get_parcel_resolution_store().put(confirmed)
    binding = require_confirmed_parcel(confirmed)
    return address, confirmed["resolution_id"], binding["geometry_hash"]


def _fetch_ok_response(body: dict) -> tuple[dict, dict]:
    field_ids = list(body.get("fields") or [])
    fields = {}
    for fid in field_ids:
        if fid == "nearest_waterbody_name":
            fields[fid] = {"value": None, "source": "USGS_NHDPLUS_HR"}
            continue
        if fid in {"wetland_fraction_of_parcel", "wetland_acres_on_parcel"}:
            fields[fid] = {
                "value": 0.01 if "fraction" in fid else 0.5,
                "source": "USFWS_NWI",
                "confidence": "medium",
            }
            continue
        if fid in {
            "nearest_usgs_gage_name",
            "nearest_usgs_gage_distance_m",
            "nearest_usgs_gage_daily_discharge_cfs",
            "soil_restrictive_layer_depth_cm",
            "soil_restrictive_layer_kind",
            "soil_ponding_frequency_class",
        }:
            # Leave absent → unavailable/missing path in collection.
            continue
        fields[fid] = {
            "value": 1 if fid.startswith("intersects") else f"fixture_{fid}",
            "source": "TEST_SOURCE",
            "confidence": "medium",
            "unit": None,
        }
        if fid == "elevation":
            fields[fid]["value"] = 1800.0
            fields[fid]["unit"] = "meters"
        if fid == "slope_degrees":
            fields[fid]["value"] = 5.0
            fields[fid]["unit"] = "degrees"
        if fid == "intersects_nhd_area":
            fields[fid]["value"] = True
        if fid == "within_floodplain_polygon":
            fields[fid]["value"] = False
    # Fix bool/number-ish fields more carefully for required set
    numericish = {
        "aspect_degrees": 200.0,
        "ndvi_current": 0.3,
        "ndvi_change_5y": -0.02,
        "tree_canopy_pct": 4.0,
        "surface_water_permanence_pct": 10.0,
        "nearest_groundwater_well_depth_to_water_m": 12.0,
        "nearest_wetland_distance_m": 80.0,
        "soil_available_water_capacity": 0.1,
        "mean_annual_dry_bulb_temperature_degc": 11.0,
        "days_above_32c_annual_count": 20,
        "wildfire_annual_frequency": 0.002,
    }
    for key, val in numericish.items():
        if key in fields:
            fields[key]["value"] = val
    for key in ("lcms_class", "land_use_class", "aspect_cardinal", "soil_drainage_class",
                "soil_hydrologic_group", "soil_map_unit_name", "drought_category",
                "nearest_flowline_name", "fema_flood_zone"):
        if key in fields and isinstance(fields[key].get("value"), str):
            fields[key]["value"] = {
                "lcms_class": "Grass/Shrub",
                "land_use_class": "Rangeland",
                "aspect_cardinal": "SW",
                "soil_drainage_class": "Well drained",
                "soil_hydrologic_group": "B",
                "soil_map_unit_name": "Test loam",
                "drought_category": "None",
                "nearest_flowline_name": "Test Creek",
                "fema_flood_zone": "X",
            }[key]
    return (
        {"fields": fields, "fetched_at": "2026-08-15T18:00:00+00:00"},
        {"ok": True, "http_status": 200},
    )


class Phase2MireyeFirstCollectionTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_advisor_runs_for_tests()

    def test_default_collection_mode_is_legacy(self) -> None:
        from rangematch.advisor_agent import enqueue_advisor_run

        queued = enqueue_advisor_run(address="x", fixture_id=None, parcel_resolution_id="tmp")
        # Will fail resolve; we only care about default mode on the queued record.
        self.assertEqual(queued["collection_mode"], COLLECTION_MODE_LEGACY)

    def test_fetch_body_uses_frozen_manifest_fields(self) -> None:
        body = build_mireye_fetch_body(lat=40.0, lng=-105.0)
        self.assertEqual(set(body["fields"]), set(manifest_field_ids()))
        self.assertEqual(len(body["fields"]), len(load_field_manifest()["fields"]))

    def test_mireye_first_profile_then_planned_supplements(self) -> None:
        address, resolution_id, geometry_hash = _confirm_unique()

        def request_fn(*, endpoint: str, body: dict):
            self.assertEqual(endpoint, "/v1/fetch")
            self.assertEqual(set(body.get("fields") or []), set(manifest_field_ids()))
            return _fetch_ok_response(body)

        set_advisor_mireye_hooks_for_tests(request_fn=request_fn)
        result = run_cper_advisor_agent(
            address=address,
            parcel_resolution_id=resolution_id,
            collection_mode=COLLECTION_MODE_MIREYE_FIRST,
        )
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(result["collection_mode"], COLLECTION_MODE_MIREYE_FIRST)
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED
        )
        self.assertIn(
            result["environmental_profile_outcome"],
            {
                OUTCOME_ENVIRONMENTAL_PROFILE_COMPLETED,
                OUTCOME_ENVIRONMENTAL_PROFILE_PARTIAL,
            },
        )
        self.assertEqual(result["geometry_hash"], geometry_hash)
        self.assertIsNone(result["packet"])
        self.assertIsNone(result["brief"])
        self.assertIsNone(result["operating_profile"])
        self.assertIsNone(result["operating_conclusion"])

        profile = result["mireye_environmental_profile"]
        self.assertIsNotNone(profile)
        validate_mireye_environmental_profile(profile)
        coverage = profile["coverage_summary"]
        self.assertEqual(
            coverage["requested_field_count"], len(load_field_manifest()["fields"])
        )
        self.assertGreater(coverage["retrieved_field_count"], 0)
        self.assertEqual(
            coverage["retrieved_field_count"],
            coverage["point_count"]
            + coverage["parcel_count"]
            + coverage["context_count"],
        )

        f06 = result["f06_derivation"]
        self.assertEqual(f06["role"], "ALWAYS_ON_CORE_DERIVATION")
        self.assertEqual(f06["geometry_hash"], geometry_hash)
        self.assertIsNotNone(f06["summary"].get("area_m2"))

        gap_plan = result["environmental_gap_plan"]
        self.assertIsNotNone(gap_plan)
        self.assertTrue(gap_plan.get("plan_hash"))
        self.assertNotIn(
            "F07_ROADS",
            gap_plan.get("ordered_supplemental_tool_ids") or [],
        )
        self.assertNotIn(
            "F07_ROAD_AND_PHYSICAL_ACCESS",
            gap_plan.get("ordered_supplemental_tool_ids") or [],
        )

        execution = result["supplement_execution"]
        self.assertIsNotNone(execution)
        self.assertEqual(
            set(execution["planned_tool_ids"]),
            set(gap_plan["ordered_supplemental_tool_ids"]),
        )
        packet = result["combined_environmental_evidence_packet"]
        self.assertIsNotNone(packet)
        self.assertEqual(packet["execution"]["f06_counted_as_supplement"], False)
        self.assertTrue(
            any(
                obs.get("provider") == "RANGEMATCH_SUPPLEMENT"
                for obs in packet.get("supplement_observations") or []
            )
        )

        natural = result["natural_cattle_profile"]
        self.assertIsNotNone(natural)
        self.assertEqual(len(natural["domains"]), 5)
        self.assertFalse(natural["provenance"]["llm_authored"])
        self.assertNotEqual(
            natural["overall_natural_foundation"]["status"],
            "ENVIRONMENTALLY_CONSTRAINED",
        )

        self.assertIsNotNone(result["deal_context"])
        interpretation = result["natural_foundation_interpretation"]
        self.assertIsNotNone(interpretation)
        self.assertEqual(interpretation["validation_status"], "PASSED")
        self.assertEqual(
            interpretation["status"],
            natural["overall_natural_foundation"]["status"],
        )
        self.assertNotEqual(
            interpretation["next_question"]["question_id"], "Q_ACCESS_DOCUMENTS"
        )

        agenda_blob = repr(result.get("agenda") or []).upper()
        self.assertNotIn("F07_ROAD", agenda_blob)
        step_ids = [row["step_id"] for row in result["steps"]]
        self.assertEqual(
            step_ids,
            [
                "ACCEPT_PLACE",
                "RESOLVE_PARCEL",
                "DERIVE_F06",
                "FETCH_MIREYE_ENVIRONMENT",
                "BUILD_MIREYE_ENVIRONMENTAL_PROFILE",
                "DETECT_ENVIRONMENTAL_GAPS",
                "RUN_ENVIRONMENTAL_SUPPLEMENTS",
                "COLLECT_ADDITIONAL_PROPERTY_CONTEXT",
                "MERGE_ENVIRONMENTAL_EVIDENCE",
                "PROJECT_NATURAL_CATTLE_PROFILE",
                "CREATE_DEAL_CONTEXT",
                "GENERATE_NATURAL_FOUNDATION_INTERPRETATION",
            ],
        )
        self.assertTrue(all(row["status"] == "SUCCEEDED" for row in result["steps"]))
        factor_ids = {
            row.get("factor_id") for row in (result.get("agenda") or []) if row.get("factor_id")
        }
        self.assertIn("F06_PARCEL_CONFIGURATION", factor_ids)
        self.assertNotIn("F07_ROAD_AND_PHYSICAL_ACCESS", factor_ids)

    def test_fetch_failure_yields_honest_partial_without_fixture(self) -> None:
        address, resolution_id, _geometry_hash = _confirm_unique()

        def request_fn(*, endpoint: str, body: dict):
            from rangematch.mireye_adapter import MireyeAdapterError

            raise MireyeAdapterError("BLOCKED_EXTERNAL:unit_test")

        set_advisor_mireye_hooks_for_tests(request_fn=request_fn)
        result = run_cper_advisor_agent(
            address=address,
            parcel_resolution_id=resolution_id,
            collection_mode=COLLECTION_MODE_MIREYE_FIRST,
        )
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(
            result["environmental_profile_outcome"],
            OUTCOME_ENVIRONMENTAL_PROFILE_PARTIAL,
        )
        profile = result["mireye_environmental_profile"]
        validate_mireye_environmental_profile(profile)
        self.assertEqual(profile["coverage_summary"]["retrieved_field_count"], 0)
        statuses = {obs["status"] for obs in profile["observations"]}
        self.assertIn("SOURCE_UNAVAILABLE", statuses)
        self.assertTrue(
            any("No fixture substitution" in note for note in (result.get("limitations") or []))
        )
        # Must not invent retrieved values after failure.
        self.assertTrue(
            all(
                obs.get("value") is None
                for obs in profile["observations"]
                if obs["status"] == "SOURCE_UNAVAILABLE"
            )
        )

    def test_legacy_path_still_available_for_confirmed_parcel(self) -> None:
        from rangematch.advisor_generic_collect import unit_test_factor_collect
        from rangematch.advisor_agent import set_advisor_factor_collect_for_tests

        address, resolution_id, _geometry_hash = _confirm_unique()
        set_advisor_factor_collect_for_tests(unit_test_factor_collect)
        result = run_cper_advisor_agent(
            address=address,
            parcel_resolution_id=resolution_id,
            collection_mode=COLLECTION_MODE_LEGACY,
        )
        self.assertEqual(result["collection_mode"], COLLECTION_MODE_LEGACY)
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertIsNotNone(result["packet"])
        self.assertIsNone(result.get("mireye_environmental_profile"))
        self.assertIsNone(result.get("environmental_profile_outcome"))


if __name__ == "__main__":
    unittest.main()
