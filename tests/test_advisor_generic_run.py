"""Confirmed non-CPER Advisor run: F01–F08 → Generic Packet → brief. No live HTTP."""

from __future__ import annotations

import unittest

from rangematch.advisor_agent import (
    OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED,
    TRACK_GENERIC,
    reset_advisor_runs_for_tests,
    run_cper_advisor_agent,
    set_advisor_factor_collect_for_tests,
)
from rangematch.advisor_generic_collect import unit_test_factor_collect
from rangematch.advisor_packet import F03_AVAILABLE
from rangematch.advisor_parcel_gate import (
    require_confirmed_parcel,
    stage_mireye_mapping_for_confirmation,
)
from rangematch.mireye_parcel_resolver import map_mireye_lookup_to_parcel
from rangematch.parcel_resolution import confirm_selected_parcel
from rangematch.parcel_resolution_store import get_parcel_resolution_store

from mireye_lookup_samples import UNIQUE_WITH_POLYGON


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


class AdvisorGenericRunTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_advisor_runs_for_tests()

    def test_confirmed_non_cper_completes_generic_packet_without_invented_facts(self) -> None:
        address, resolution_id, geometry_hash = _confirm_unique()
        result = run_cper_advisor_agent(
            address=address,
            parcel_resolution_id=resolution_id,
        )
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED
        )
        self.assertEqual(result["track"], TRACK_GENERIC)
        self.assertTrue(result["parcel_geometry_confirmed"])
        self.assertEqual(result["geometry_hash"], geometry_hash)
        self.assertIsNone(result["limited_investigation"])
        packet = result["packet"]
        brief = result["brief"]
        self.assertIsNotNone(packet)
        self.assertIsNotNone(brief)
        self.assertEqual(packet["technical_references"]["policy_scope"], "GENERIC_MINIMAL")
        self.assertEqual(
            packet["technical_references"]["policy"], "build_generic_minimal_policy"
        )
        self.assertFalse(packet["parcel"]["is_engineering_test_geometry"])
        self.assertEqual(packet["listing_claims"], [])
        blob = repr(packet).lower()
        self.assertNotIn("cper_f03", blob)
        self.assertNotIn("engineering_test_geometry_cper", blob)
        precip = next(
            row
            for row in packet["observations"]
            if row["observation_id"] == "OBS_PRECIP"
        )
        self.assertIsNone(precip["value"])
        self.assertEqual(precip["evidence_state"], "SOURCE_UNAVAILABLE")
        area = next(
            row for row in packet["observations"] if row["observation_id"] == "OBS_AREA"
        )
        self.assertIsNotNone(area["value"])
        self.assertEqual(brief["validation_status"], "PASSED")
        self.assertFalse(brief["report_provenance"]["llm_used"])
        portrait = brief["page_one_advisor"]["how_the_tract_reads"]
        self.assertNotIn("measured rainfall", portrait)
        self.assertIn("not yet available", portrait)
        action_ids = {row["action_id"] for row in packet["actions"]}
        self.assertIn("ACTION_ACCESS_DOCUMENTS", action_ids)
        self.assertIn("ACTION_INTERPRET_RAP_FORAGE", action_ids)
        self.assertGreaterEqual(len(result["agenda"]), 8)
        self.assertIsNotNone(result.get("operating_profile"))
        self.assertTrue(result.get("operating_profile_hash"))
        self.assertIsNotNone(result.get("buyer_explanation"))
        self.assertEqual(result["buyer_explanation"]["validation_status"], "PASSED")
        self.assertIn(
            result["buyer_explanation"]["source"],
            {"STRUCTURED_FIXTURE", "LIVE_LLM", "DETERMINISTIC_FALLBACK"},
        )

    def test_generic_run_can_project_f03_objects_from_collect_hook(self) -> None:
        address, resolution_id, _ = _confirm_unique()

        def collect_fn(**_kwargs):
            base = unit_test_factor_collect()
            base["computed_factors"] = {
                "F03_LIVESTOCK_WATER": {
                    "mapped_candidate_count": 1,
                    "field_verified_count": 0,
                    "candidate_inventory": [
                        {
                            "candidate_id": "USGS_NHDPLUS_HR:NHDWaterbody:99",
                            "source_layer": "NHDWaterbody",
                            "source_feature_id": "99",
                            "intersects_parcel": True,
                            "bbox": [-104.9, 40.49, -104.89, 40.5],
                            "gnis_name": None,
                        }
                    ],
                }
            }
            base["factor_errors"].pop("F03_LIVESTOCK_WATER", None)
            base["f03_status"] = F03_AVAILABLE
            base["f03_inventory"] = base["computed_factors"]["F03_LIVESTOCK_WATER"][
                "candidate_inventory"
            ]
            return base

        set_advisor_factor_collect_for_tests(collect_fn)
        result = run_cper_advisor_agent(
            address=address,
            parcel_resolution_id=resolution_id,
        )
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED
        )
        objects = result["packet"]["candidate_objects"]
        self.assertEqual(len(objects), 1)
        self.assertEqual(
            objects[0]["candidate_id"], "USGS_NHDPLUS_HR:NHDWaterbody:99"
        )
        self.assertEqual(result["packet"]["technical_references"]["f03_status"], "AVAILABLE")
        self.assertNotIn("WATER_CANDIDATE_", objects[0]["candidate_id"])

    def test_adapter_timeout_still_emits_generic_brief(self) -> None:
        address, resolution_id, _ = _confirm_unique()

        def collect_fn(**_kwargs):
            base = unit_test_factor_collect()
            base["factor_errors"]["F03_LIVESTOCK_WATER"] = "ADAPTER_TIMEOUT"
            base["progress_notes"] = [
                "F03 timed out — continuing with remaining evidence"
            ]
            return base

        set_advisor_factor_collect_for_tests(collect_fn)
        result = run_cper_advisor_agent(
            address=address,
            parcel_resolution_id=resolution_id,
        )
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED
        )
        self.assertIsNotNone(result["brief"])
        self.assertTrue(
            any("F03 timed out" in note for note in (result.get("limitations") or []))
        )
        water = next(
            row
            for row in result["packet"]["observations"]
            if row["observation_id"] == "OBS_WATER_COUNT"
        )
        self.assertEqual(water["evidence_state"], "SOURCE_UNAVAILABLE")

    def test_missing_netcdf4_from_collect_still_emits_limited_brief(self) -> None:
        address, resolution_id, _ = _confirm_unique()

        def collect_fn(**_kwargs):
            raise ModuleNotFoundError(name="netCDF4")

        set_advisor_factor_collect_for_tests(collect_fn)
        result = run_cper_advisor_agent(
            address=address,
            parcel_resolution_id=resolution_id,
        )
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED
        )
        self.assertEqual(
            result["packet"]["technical_references"]["policy_scope"], "GENERIC_MINIMAL"
        )
        self.assertEqual(result["brief"]["validation_status"], "PASSED")
        self.assertFalse(result["packet"]["parcel"]["is_engineering_test_geometry"])
        blob = repr(result["packet"]).lower()
        self.assertNotIn("engineering_test_geometry_cper", blob)
        area = next(
            row for row in result["packet"]["observations"] if row["observation_id"] == "OBS_AREA"
        )
        self.assertIsNotNone(area["value"])
        precip = next(
            row
            for row in result["packet"]["observations"]
            if row["observation_id"] == "OBS_PRECIP"
        )
        self.assertIsNone(precip["value"])
        self.assertEqual(precip["evidence_state"], "SOURCE_UNAVAILABLE")
        self.assertTrue(
            any("missing dependency netCDF4" in note for note in (result.get("limitations") or []))
        )

    def test_all_live_unavailable_still_has_f06_and_honest_brief(self) -> None:
        address, resolution_id, _ = _confirm_unique()
        result = run_cper_advisor_agent(
            address=address,
            parcel_resolution_id=resolution_id,
        )
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED
        )
        self.assertEqual(result["brief"]["validation_status"], "PASSED")
        self.assertEqual(
            result["packet"]["technical_references"]["policy_scope"], "GENERIC_MINIMAL"
        )
        area = next(
            row for row in result["packet"]["observations"] if row["observation_id"] == "OBS_AREA"
        )
        self.assertIsNotNone(area["value"])
        for obs_id in ("OBS_PRECIP", "OBS_SLOPE", "OBS_RAP_PROD", "OBS_ROAD"):
            row = next(
                item
                for item in result["packet"]["observations"]
                if item["observation_id"] == obs_id
            )
            self.assertEqual(row["evidence_state"], "SOURCE_UNAVAILABLE")
            self.assertIsNone(row["value"])


if __name__ == "__main__":
    unittest.main()
