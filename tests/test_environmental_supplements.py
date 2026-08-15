"""Phase 4 Gate: plan-driven supplements + combined evidence merge."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from rangematch.advisor_agent import COLLECTION_MODE_LEGACY
from rangematch.advisor_generic_collect import LIVE_FACTOR_IDS
from rangematch.environmental_evidence_packet import (
    buyer_visible_observations,
    build_combined_environmental_evidence_packet,
)
from rangematch.environmental_gap_detector import (
    STATUS_SUFFICIENT,
    TOOL_F01,
    TOOL_F02,
    TOOL_F03,
    detect_environmental_gaps,
)
from rangematch.environmental_supplement_runner import (
    EnvironmentalSupplementError,
    PROVIDER_CORE,
    PROVIDER_MIREYE,
    PROVIDER_SUPPLEMENT,
    execute_supplement_plan,
    planned_factor_jobs,
)
from rangematch.mireye_environmental_profile import validate_mireye_environmental_profile
from rangematch.mireye_first_collection import derive_confirmed_f06

REPO = Path(__file__).resolve().parents[1]
NAMBE_PROFILE = (
    REPO
    / "test-data"
    / "mireye-environmental-profile"
    / "nambe_mireye_environmental_profile.json"
)

SIMPLE_POLYGON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-104.9, 40.5],
                        [-104.89, 40.5],
                        [-104.89, 40.49],
                        [-104.9, 40.49],
                        [-104.9, 40.5],
                    ]
                ],
            },
        }
    ],
}


def _f01_ok() -> dict:
    return {
        "factor_id": "F01_TOPOGRAPHY",
        "canonical_source_id": "USGS_3DEP_1_3_ARC_SECOND_SEAMLESS_DEM",
        "summary": {"elevation_median_m": 1650.0, "slope_median_degrees": 3.2},
        "geometry_hash": "x",
        "land_facts": [
            {
                "variable_id": "VAR_F01_ELEVATION_MEDIAN_M",
                "value": 1650.0,
                "unit": "m",
                "spatial_semantics": "parcel_aggregate",
                "source_id": "USGS_3DEP_1_3_ARC_SECOND_SEAMLESS_DEM",
            },
            {
                "variable_id": "VAR_F01_SLOPE_MEDIAN_DEGREES",
                "value": 3.2,
                "unit": "degree",
                "spatial_semantics": "parcel_aggregate",
                "source_id": "USGS_3DEP_1_3_ARC_SECOND_SEAMLESS_DEM",
            },
        ],
    }


def _f02_ok() -> dict:
    return {
        "factors": {
            "F02_HERBACEOUS_RESOURCE": {
                "factor_id": "F02_HERBACEOUS_RESOURCE",
                "canonical_source_id": "USDA_ARS_RAP_V3",
                "land_facts": [
                    {
                        "variable_id": "VAR_F02_ANNUAL_HERB_PRODUCTION",
                        "value": 800.0,
                        "unit": "pound_per_acre",
                        "spatial_semantics": "parcel_aggregate",
                        "source_id": "USDA_ARS_RAP_V3",
                    }
                ],
            },
            "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE": {
                "factor_id": "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE",
                "canonical_source_id": "USDA_ARS_RAP_V3",
                "land_facts": [
                    {
                        "variable_id": "VAR_F08_SHRUB_COVER_FRACTION",
                        "value": 0.12,
                        "unit": "fraction",
                        "spatial_semantics": "parcel_aggregate",
                        "source_id": "USDA_ARS_RAP_V3",
                    }
                ],
            },
        }
    }


def _f03_ok() -> dict:
    return {
        "factor_id": "F03_LIVESTOCK_WATER",
        "mapped_candidate_count": 2,
        "canonical_source_id": "USGS_NHDPLUS_HR",
        "land_facts": [
            {
                "variable_id": "VAR_F03_MAPPED_WATER_CANDIDATE_COUNT",
                "value": 2,
                "unit": "count",
                "spatial_semantics": "parcel_aggregate",
                "source_id": "USGS_NHDPLUS_HR",
            }
        ],
    }


class Phase4SupplementRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = json.loads(NAMBE_PROFILE.read_text(encoding="utf-8"))
        validate_mireye_environmental_profile(self.profile)
        self.plan = detect_environmental_gaps(
            self.profile,
            f06_geometry_hash=self.profile["parcel_ref"]["geometry_hash"],
        )
        self.geometry_hash = self.profile["parcel_ref"]["geometry_hash"]

    def test_planned_jobs_exclude_f07_and_dedupe_f08_with_f02(self) -> None:
        jobs = planned_factor_jobs(self.plan)
        self.assertIn("F01_TOPOGRAPHY", jobs)
        self.assertIn("F02_HERBACEOUS_RESOURCE", jobs)
        self.assertNotIn("F07_ROAD_AND_PHYSICAL_ACCESS", jobs)
        self.assertNotIn("F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE", jobs)

    def test_execute_only_planned_adapters(self) -> None:
        calls: list[str] = []

        def track(label: str, payload):
            def _run():
                calls.append(label)
                return payload

            return _run

        runners = {
            "F01_TOPOGRAPHY": track("F01", _f01_ok()),
            "F02_HERBACEOUS_RESOURCE": track("F02", _f02_ok()),
            "F03_LIVESTOCK_WATER": track("F03", _f03_ok()),
            "F04_SOIL_WETNESS_ECOLOGICAL_SITE": track(
                "F04",
                {
                    "factor_id": "F04_SOIL_WETNESS_ECOLOGICAL_SITE",
                    "canonical_source_id": "USDA_SSURGO",
                    "land_facts": [
                        {
                            "variable_id": "VAR_F04_SDA_VALID_COVERAGE_FRACTION",
                            "value": 0.9,
                            "unit": "fraction",
                            "spatial_semantics": "parcel_aggregate",
                            "source_id": "USDA_SSURGO",
                        }
                    ],
                },
            ),
            "F05_CLIMATE_DROUGHT_EXPOSURE": track(
                "F05",
                {
                    "factor_id": "F05_CLIMATE_DROUGHT_EXPOSURE",
                    "canonical_source_id": "NOAA_NCEI",
                    "land_facts": [
                        {
                            "variable_id": "VAR_F05_MEAN_ANNUAL_PRECIPITATION",
                            "value": 320.0,
                            "unit": "mm/year",
                            "spatial_semantics": "parcel_aggregate",
                            "source_id": "NOAA_NCEI",
                        }
                    ],
                },
            ),
            "F07_ROAD_AND_PHYSICAL_ACCESS": track(
                "F07", {"nearest_mapped_road_distance_m": 0}
            ),
        }
        plan = copy.deepcopy(self.plan)
        plan["ordered_supplemental_tool_ids"] = [TOOL_F01, TOOL_F02]
        for domain in plan["domains"]:
            if domain["domain"] == "TERRAIN":
                domain["supplemental_tool_ids"] = [TOOL_F01]
            elif domain["domain"] == "FEED_VEGETATION":
                domain["supplemental_tool_ids"] = [TOOL_F02]
            else:
                domain["supplemental_tool_ids"] = []

        result = execute_supplement_plan(
            plan,
            geometry=SIMPLE_POLYGON,
            geometry_id="gate4",
            geometry_hash=self.geometry_hash,
            runners=runners,
        )
        self.assertEqual(set(calls), {"F01", "F02"})
        self.assertNotIn("F07", calls)
        self.assertIn(TOOL_F01, result["succeeded_tool_ids"])
        self.assertIn(TOOL_F02, result["succeeded_tool_ids"])
        self.assertIn("F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE", result["computed_factors"])

    def test_adapter_failure_is_source_unavailable_not_fixture(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["ordered_supplemental_tool_ids"] = [TOOL_F01]

        def boom():
            raise RuntimeError("LIVE_ADAPTER_DOWN")

        result = execute_supplement_plan(
            plan,
            geometry=SIMPLE_POLYGON,
            geometry_id="gate4",
            geometry_hash=self.geometry_hash,
            runners={"F01_TOPOGRAPHY": boom},
        )
        self.assertEqual(result["failed_tool_ids"], [TOOL_F01])
        self.assertEqual(result["computed_factors"], {})
        packet = build_combined_environmental_evidence_packet(
            mireye_profile=self.profile,
            gap_plan=plan,
            supplement_execution=result,
            f06=derive_confirmed_f06(
                SIMPLE_POLYGON, geometry_hash=self.geometry_hash
            ),
        )
        failures = [
            obs
            for obs in packet["supplement_observations"]
            if obs.get("status") == "SOURCE_UNAVAILABLE"
        ]
        self.assertTrue(failures)
        self.assertTrue(
            all(
                "fixture" not in str(obs.get("notes") or "").lower()
                or "no fixture" in str(obs.get("notes") or "").lower()
                for obs in failures
            )
        )
        self.assertGreater(len(packet["mireye_observations"]), 0)
        self.assertTrue(
            any(obs.get("provider") == PROVIDER_MIREYE for obs in packet["mireye_observations"])
        )

    def test_merge_keeps_mireye_and_marks_supplements(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["ordered_supplemental_tool_ids"] = [TOOL_F01]
        result = execute_supplement_plan(
            plan,
            geometry=SIMPLE_POLYGON,
            geometry_id="gate4",
            geometry_hash=self.geometry_hash,
            runners={"F01_TOPOGRAPHY": _f01_ok},
        )
        packet = build_combined_environmental_evidence_packet(
            mireye_profile=self.profile,
            gap_plan=plan,
            supplement_execution=result,
            f06=derive_confirmed_f06(
                SIMPLE_POLYGON, geometry_hash=self.geometry_hash
            ),
        )
        self.assertEqual(packet["execution"]["f06_counted_as_supplement"], False)
        self.assertTrue(any(obs["provider"] == PROVIDER_CORE for obs in packet["core_observations"]))
        supp = [
            obs
            for obs in packet["supplement_observations"]
            if obs.get("status") == "RETRIEVED"
        ]
        self.assertTrue(supp)
        self.assertTrue(all(obs["provider"] == PROVIDER_SUPPLEMENT for obs in supp))
        self.assertTrue(any(row.get("domain") == "TERRAIN" for row in packet["conflicts"]))
        visible = buyer_visible_observations(packet)
        self.assertTrue(all(row.get("value") is not None for row in visible))
        self.assertFalse(
            any(row.get("status") == "SOURCE_UNAVAILABLE" for row in visible)
        )

    def test_mireye_only_domain_skips_its_adapter_while_other_gap_runs(self) -> None:
        profile = copy.deepcopy(self.profile)
        for obs in profile["observations"]:
            if obs.get("domain") == "TERRAIN":
                obs["spatial_semantics"] = "PARCEL"
                obs["canonical_for_parcel_facts"] = True
                obs["status"] = "RETRIEVED"
                obs["geometry_hash_ref"] = profile["parcel_ref"]["geometry_hash"]
        profile["profile_hash"] = "a" * 64
        plan = detect_environmental_gaps(profile)
        terrain = next(d for d in plan["domains"] if d["domain"] == "TERRAIN")
        self.assertEqual(terrain["coverage_status"], STATUS_SUFFICIENT)
        self.assertNotIn(TOOL_F01, plan["ordered_supplemental_tool_ids"])
        self.assertIn(TOOL_F03, plan["ordered_supplemental_tool_ids"])

        calls: list[str] = []

        def f03():
            calls.append("F03")
            return _f03_ok()

        narrow = copy.deepcopy(plan)
        narrow["ordered_supplemental_tool_ids"] = [TOOL_F03]
        result = execute_supplement_plan(
            narrow,
            geometry=SIMPLE_POLYGON,
            geometry_id="gate4",
            geometry_hash=self.geometry_hash,
            runners={
                "F03_LIVESTOCK_WATER": f03,
                "F01_TOPOGRAPHY": lambda: (_ for _ in ()).throw(
                    AssertionError("F01 must not run")
                ),
            },
        )
        self.assertEqual(calls, ["F03"])
        self.assertNotIn(TOOL_F01, result["attempted_tool_ids"])
        self.assertIn(TOOL_F03, result["succeeded_tool_ids"])

    def test_f07_in_plan_is_rejected(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["ordered_supplemental_tool_ids"] = [TOOL_F01, "F07_ROAD"]
        with self.assertRaises(EnvironmentalSupplementError):
            planned_factor_jobs(plan)

    def test_f07_runner_present_is_never_invoked(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["ordered_supplemental_tool_ids"] = [TOOL_F01]
        calls: list[str] = []

        def f01():
            calls.append("F01")
            return _f01_ok()

        def f07():
            calls.append("F07")
            return {"nearest_mapped_road_distance_m": 0}

        result = execute_supplement_plan(
            plan,
            geometry=SIMPLE_POLYGON,
            geometry_id="gate4",
            geometry_hash=self.geometry_hash,
            runners={
                "F01_TOPOGRAPHY": f01,
                "F07_ROAD_AND_PHYSICAL_ACCESS": f07,
            },
        )
        self.assertEqual(calls, ["F01"])
        self.assertNotIn("F07", calls)
        self.assertIn(TOOL_F01, result["succeeded_tool_ids"])

    def test_rerun_does_not_mix_prior_results(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["ordered_supplemental_tool_ids"] = [TOOL_F01]
        first = execute_supplement_plan(
            plan,
            geometry=SIMPLE_POLYGON,
            geometry_id="gate4",
            geometry_hash=self.geometry_hash,
            runners={"F01_TOPOGRAPHY": _f01_ok},
        )
        second = execute_supplement_plan(
            plan,
            geometry=SIMPLE_POLYGON,
            geometry_id="gate4",
            geometry_hash=self.geometry_hash,
            runners={
                "F01_TOPOGRAPHY": lambda: (_ for _ in ()).throw(RuntimeError("down"))
            },
        )
        self.assertIn(TOOL_F01, first["succeeded_tool_ids"])
        self.assertEqual(second["computed_factors"], {})
        self.assertIn(TOOL_F01, second["failed_tool_ids"])
        self.assertNotEqual(first["succeeded_tool_ids"], second["succeeded_tool_ids"])

    def test_legacy_nambe_path_untouched_by_phase4_modules(self) -> None:
        self.assertIn("F07_ROAD_AND_PHYSICAL_ACCESS", LIVE_FACTOR_IDS)
        self.assertEqual(COLLECTION_MODE_LEGACY, "LEGACY")


if __name__ == "__main__":
    unittest.main()
