"""Executable golden tests for F04 soil/site derivation."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from rangematch.engine import evaluate_land_profile
from rangematch.f04_derivation import (
    derive_available_water_storage,
    derive_f04_from_fixture_dir,
    derive_f04_parcel_facts,
    ecological_site_access_status,
    horizon_overlap_cm,
    parse_sda_table,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "test-data/live-results/cper"
PROFILE = json.loads((ROOT / "test-data/land-profiles/land_profile_cper_001.json").read_text())


def _table(header, rows):
    metadata = ["ColumnOrdinal=0"] + [""] * (len(header) - 1)
    return {"Table": [header, metadata, *rows]}


class F04DerivationGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.derived = derive_f04_from_fixture_dir(FIXTURE_DIR)
        cls.spatial = json.loads(
            (FIXTURE_DIR / "cper_sda_spatial_coverage_2026-08-07.json").read_text()
        )
        cls.components = json.loads(
            (FIXTURE_DIR / "cper_sda_mapunit_component_ecosite_2026-08-07.json").read_text()
        )
        cls.horizons = json.loads(
            (FIXTURE_DIR / "cper_sda_horizons_2026-08-07.json").read_text()
        )
        cls.restrictions = json.loads(
            (FIXTURE_DIR / "cper_sda_restrictions_2026-08-07.json").read_text()
        )
        cls.monthly = json.loads(
            (FIXTURE_DIR / "cper_sda_monthly_wetness_2026-08-07.json").read_text()
        )
        cls.ecological = json.loads(
            (FIXTURE_DIR / "cper_ecological_site_access_2026-08-07.json").read_text()
        )

    def test_f04_derive_001_coverage_from_polygon_intersection(self):
        self.assertTrue(
            self.derived["parcel_coverage"]["coverage_calculated_from_polygon_intersection"]
        )
        self.assertFalse(
            self.derived["parcel_coverage"]["successful_query_implies_complete_coverage"]
        )
        self.assertAlmostEqual(
            self.derived["parcel_coverage"]["coverage_fraction"],
            self.spatial["coverage_fraction"],
            places=12,
        )

    def test_f04_derive_002_all_components_preserved(self):
        parsed = parse_sda_table(self.components)
        self.assertEqual(len(parsed), 16)
        self.assertEqual(len(self.derived["component_support_weights"]), 16)
        self.assertFalse(
            any(
                item.get("dominant_component_only_output")
                for item in self.derived["component_support_weights"]
            )
        )
        # Synthetic map unit with four components must preserve all four.
        synthetic = derive_f04_parcel_facts(
            spatial_coverage={
                "requested_area_m2": 100.0,
                "covered_area_m2": 100.0,
                "coverage_fraction": 1.0,
                "intersecting_mapunit_count": 1,
                "mapunit_intersection_areas": [{"mukey": "1", "intersection_area_m2": 100.0}],
            },
            components_table=_table(
                [
                    "mukey",
                    "musym",
                    "muname",
                    "cokey",
                    "compname",
                    "comppct_r",
                    "majcompflag",
                    "drainagecl",
                    "hydgrp",
                    "ecoclassid",
                    "ecoclassname",
                    "ecoclasstypename",
                ],
                [
                    ["1", "A", "Unit", "c1", "A", 50, "Yes", "Well drained", "B", None, None, None],
                    ["1", "A", "Unit", "c2", "B", 35, "Yes", "Well drained", "B", None, None, None],
                    ["1", "A", "Unit", "c3", "C", 8, "No", "Poorly drained", "D", None, None, None],
                    ["1", "A", "Unit", "c4", "D", 7, "No", "Poorly drained", "D", None, None, None],
                ],
            ),
            horizons_table=_table(
                ["mukey", "cokey", "compname", "comppct_r", "chkey", "hzname", "hzdept_r", "hzdepb_r", "awc_r", "ec_r", "ph1to1h2o_r"],
                [],
            ),
            restrictions_table=_table(
                ["mukey", "cokey", "compname", "comppct_r", "corestrictkey", "reskind", "resdept_r"],
                [],
            ),
            monthly_wetness_table=_table(
                ["mukey", "cokey", "compname", "comppct_r", "comonthkey", "monthseq", "flodfreqcl", "pondfreqcl"],
                [],
            ),
            ecological_site_access=[],
        )
        self.assertEqual(len(synthetic["component_support_weights"]), 4)

    def test_f04_derive_003_missing_component_share_not_renormalized(self):
        synthetic = derive_f04_parcel_facts(
            spatial_coverage={
                "requested_area_m2": 100.0,
                "covered_area_m2": 100.0,
                "coverage_fraction": 1.0,
                "intersecting_mapunit_count": 1,
                "mapunit_intersection_areas": [{"mukey": "1", "intersection_area_m2": 100.0}],
            },
            components_table=_table(
                [
                    "mukey",
                    "musym",
                    "muname",
                    "cokey",
                    "compname",
                    "comppct_r",
                    "majcompflag",
                    "drainagecl",
                    "hydgrp",
                    "ecoclassid",
                    "ecoclassname",
                    "ecoclasstypename",
                ],
                [
                    ["1", "A", "Unit", "c1", "A", 60, "Yes", "Well drained", "B", None, None, None],
                    ["1", "A", "Unit", "c2", "B", 20, "No", "Well drained", "B", None, None, None],
                ],
            ),
            horizons_table=_table(
                ["mukey", "cokey", "compname", "comppct_r", "chkey", "hzname", "hzdept_r", "hzdepb_r", "awc_r", "ec_r", "ph1to1h2o_r"],
                [],
            ),
            restrictions_table=_table(
                ["mukey", "cokey", "compname", "comppct_r", "corestrictkey", "reskind", "resdept_r"],
                [],
            ),
            monthly_wetness_table=_table(
                ["mukey", "cokey", "compname", "comppct_r", "comonthkey", "monthseq", "flodfreqcl", "pondfreqcl"],
                [],
            ),
            ecological_site_access=[],
        )
        self.assertAlmostEqual(synthetic["known_component_share"], 0.8)
        self.assertAlmostEqual(synthetic["unaccounted_component_share"], 0.2)
        self.assertFalse(synthetic["component_percentages_renormalized"])

    def test_duplicate_ecological_join_rows_do_not_double_count_component_share(self):
        columns = [
            "mukey", "musym", "muname", "cokey", "compname", "comppct_r",
            "majcompflag", "drainagecl", "hydgrp", "ecoclassid",
            "ecoclassname", "ecoclasstypename",
        ]
        synthetic = derive_f04_parcel_facts(
            spatial_coverage={
                "requested_area_m2": 100.0,
                "covered_area_m2": 100.0,
                "coverage_fraction": 1.0,
                "intersecting_mapunit_count": 1,
                "mapunit_intersection_areas": [{"mukey": "1", "intersection_area_m2": 100.0}],
            },
            components_table=_table(
                columns,
                [
                    ["1", "A", "Unit", "c1", "A", 60, "Yes", "Well drained", "B", "R001", "Site 1", "ESD"],
                    ["1", "A", "Unit", "c1", "A", 60, "Yes", "Well drained", "B", "R002", "Site 2", "ESD"],
                    ["1", "A", "Unit", "c2", "B", 40, "Yes", "Well drained", "B", None, None, None],
                ],
            ),
            horizons_table=_table(
                ["mukey", "cokey", "compname", "comppct_r", "chkey", "hzname", "hzdept_r", "hzdepb_r", "awc_r", "ec_r", "ph1to1h2o_r"],
                [],
            ),
            restrictions_table=_table(
                ["mukey", "cokey", "compname", "comppct_r", "corestrictkey", "reskind", "resdept_r"],
                [],
            ),
            monthly_wetness_table=_table(
                ["mukey", "cokey", "compname", "comppct_r", "comonthkey", "monthseq", "flodfreqcl", "pondfreqcl"],
                [],
            ),
            ecological_site_access=[],
        )
        self.assertEqual(len(synthetic["component_support_weights"]), 2)
        self.assertAlmostEqual(synthetic["known_component_share"], 1.0)
        self.assertEqual(synthetic["duplicate_component_rows_deduplicated"], 1)

    def test_f04_derive_004_controlled_categories_remain_distributions(self):
        distribution = self.derived["drainage_class_distribution"]
        self.assertIn("Well drained", distribution)
        self.assertNotIn("numeric_average", distribution)
        self.assertFalse(self.derived["quality"]["numeric_average_of_controlled_categories"])
        # Synthetic two-class case from the golden YAML.
        synthetic = derive_f04_parcel_facts(
            spatial_coverage={
                "requested_area_m2": 100.0,
                "covered_area_m2": 100.0,
                "coverage_fraction": 1.0,
                "intersecting_mapunit_count": 1,
                "mapunit_intersection_areas": [{"mukey": "1", "intersection_area_m2": 100.0}],
            },
            components_table=_table(
                [
                    "mukey",
                    "musym",
                    "muname",
                    "cokey",
                    "compname",
                    "comppct_r",
                    "majcompflag",
                    "drainagecl",
                    "hydgrp",
                    "ecoclassid",
                    "ecoclassname",
                    "ecoclasstypename",
                ],
                [
                    ["1", "A", "Unit", "c1", "A", 70, "Yes", "Well drained", "B", None, None, None],
                    ["1", "A", "Unit", "c2", "B", 30, "No", "Poorly drained", "D", None, None, None],
                ],
            ),
            horizons_table=_table(
                ["mukey", "cokey", "compname", "comppct_r", "chkey", "hzname", "hzdept_r", "hzdepb_r", "awc_r", "ec_r", "ph1to1h2o_r"],
                [],
            ),
            restrictions_table=_table(
                ["mukey", "cokey", "compname", "comppct_r", "corestrictkey", "reskind", "resdept_r"],
                [],
            ),
            monthly_wetness_table=_table(
                ["mukey", "cokey", "compname", "comppct_r", "comonthkey", "monthseq", "flodfreqcl", "pondfreqcl"],
                [],
            ),
            ecological_site_access=[],
        )
        self.assertAlmostEqual(synthetic["drainage_class_distribution"]["Well drained"], 0.7)
        self.assertAlmostEqual(synthetic["drainage_class_distribution"]["Poorly drained"], 0.3)

    def test_f04_derive_005_null_monthly_wetness_remains_unknown(self):
        null_rows = [
            row
            for row in self.derived["monthly_wetness_records"]
            if row["pondfreqcl"] == "UNKNOWN"
        ]
        self.assertGreater(len(null_rows), 0)
        self.assertTrue(all(row["interpreted_null_as_none"] is False for row in null_rows))
        self.assertIn("UNKNOWN", self.derived["ponding_frequency_distribution"])
        # Explicit string "None" remains a known class, not UNKNOWN.
        self.assertIn("None", self.derived["ponding_frequency_distribution"])

    def test_f04_derive_006_null_restriction_remains_unknown(self):
        unknown = [
            row
            for row in self.derived["restrictive_layer_records"]
            if row["restrictive_layer_status"] == "UNKNOWN"
        ]
        self.assertEqual(len(unknown), 13)
        self.assertTrue(all(row["interpreted_as_unrestricted"] is False for row in unknown))
        self.assertIn("UNKNOWN", self.derived["restrictive_layer_distribution"])

    def test_f04_derive_007_awc_requires_declared_interval(self):
        result = derive_available_water_storage(
            [{"cokey": "1", "hzdept_r": 0, "hzdepb_r": 10, "awc_r": 0.14}],
            declared_depth_interval_cm=None,
        )
        self.assertIsNone(result["derived_storage_mm"])
        self.assertEqual(result["status"], "METHOD_INPUT_REQUIRED")
        self.assertEqual(
            self.derived["available_water_storage"]["status"], "METHOD_INPUT_REQUIRED"
        )

    def test_awc_overlap_calculation_and_missing_awc_coverage(self):
        self.assertEqual(horizon_overlap_cm(0, 10, 0, 20), 10)
        self.assertEqual(horizon_overlap_cm(10, 30, 0, 20), 10)
        self.assertEqual(horizon_overlap_cm(25, 40, 0, 20), 0)
        horizons = [
            {"cokey": "1", "hzdept_r": 0, "hzdepb_r": 10, "awc_r": 0.10},
            {"cokey": "1", "hzdept_r": 10, "hzdepb_r": 20, "awc_r": None},
        ]
        result = derive_available_water_storage(
            horizons,
            declared_depth_interval_cm=(0.0, 20.0),
            component_support_weights={"1": 1.0},
        )
        self.assertEqual(result["status"], "DERIVED")
        self.assertAlmostEqual(result["derived_storage_mm"], 0.10 * 10 * 10)
        self.assertAlmostEqual(result["represented_depth_cm"], 10.0)
        self.assertAlmostEqual(result["depth_coverage_fraction"], 0.5)

    def test_f04_derive_008_ecological_site_no_current_state_or_ranking(self):
        self.assertEqual(len(self.derived["ecological_site_references"]), 6)
        access_statuses = set()
        for site in self.derived["ecological_site_references"]:
            self.assertEqual(site["current_vegetation_state"], "UNKNOWN")
            self.assertEqual(site["operation_ranking_effect"], "NONE")
            self.assertIn(
                site["public_description_access_status"],
                {"ACCESSIBLE", "NOT_ACCESSIBLE", "UNKNOWN"},
            )
            access_statuses.add(site["public_description_access_status"])
        self.assertIn("ACCESSIBLE", access_statuses)
        self.assertIn("UNKNOWN", access_statuses)
        self.assertNotIn("NOT_ACCESSIBLE", access_statuses)
        self.assertEqual(self.derived["ranking_effect"], "NONE")
        self.assertFalse(self.derived["directional_signal_allowed"])

    def test_timeout_access_is_unknown_not_inaccessible(self):
        self.assertEqual(
            ecological_site_access_status(
                {
                    "public_description_accessible": False,
                    "error_type": "TimeoutError",
                }
            ),
            "UNKNOWN",
        )
        self.assertEqual(
            ecological_site_access_status(
                {"public_description_accessible": False, "http_status": 404}
            ),
            "NOT_ACCESSIBLE",
        )
        timeout_sites = [
            site
            for site in self.derived["ecological_site_references"]
            if site.get("access_error_type") == "TimeoutError"
        ]
        self.assertEqual(len(timeout_sites), 3)
        self.assertTrue(
            all(site["public_description_access_status"] == "UNKNOWN" for site in timeout_sites)
        )

    def test_provenance_hash_includes_horizons(self):
        import hashlib
        import json

        from rangematch.f04_derivation import parse_sda_table

        components = parse_sda_table(self.components)
        horizons = parse_sda_table(self.horizons)
        restrictions = parse_sda_table(self.restrictions)
        monthly = parse_sda_table(self.monthly)
        with_horizons = hashlib.sha256(
            json.dumps(
                {
                    "spatial_coverage": self.spatial,
                    "components": components,
                    "horizons": horizons,
                    "restrictions": restrictions,
                    "monthly": monthly,
                    "ecological_site_access": self.ecological,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        without_horizons = hashlib.sha256(
            json.dumps(
                {
                    "spatial_coverage": self.spatial,
                    "components": components,
                    "restrictions": restrictions,
                    "monthly": monthly,
                    "ecological_site_access": self.ecological,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        self.assertEqual(
            self.derived["provenance"]["response_or_artifact_hash"], with_horizons
        )
        self.assertNotEqual(
            self.derived["provenance"]["response_or_artifact_hash"], without_horizons
        )

    def test_awc_component_support_coverage_excludes_missing_awc(self):
        horizons = [
            {"cokey": "1", "hzdept_r": 0, "hzdepb_r": 20, "awc_r": 0.10},
            {"cokey": "2", "hzdept_r": 0, "hzdepb_r": 20, "awc_r": None},
        ]
        result = derive_available_water_storage(
            horizons,
            declared_depth_interval_cm=(0.0, 20.0),
            component_support_weights={"1": 0.7, "2": 0.3},
        )
        self.assertAlmostEqual(result["component_support_coverage_fraction"], 0.7)
        by_cokey = {row["cokey"]: row for row in result["component_results"]}
        self.assertTrue(by_cokey["1"]["contributes_awc"])
        self.assertFalse(by_cokey["2"]["contributes_awc"])

    def test_mireye_point_cannot_replace_parcel_facts(self):
        self.assertIsNotNone(self.derived["mireye_point_qa"])
        self.assertFalse(self.derived["mireye_point_qa"]["may_represent_whole_parcel"])
        self.assertEqual(
            self.derived["provenance"]["mireye_role"], "POINT_DISPLAY_AND_QA_ONLY"
        )
        self.assertGreater(len(self.derived["component_support_weights"]), 1)

    def test_identical_derivation_inputs_are_deterministic(self):
        again = derive_f04_from_fixture_dir(FIXTURE_DIR)
        self.assertEqual(self.derived, again)


class F04EngineIntegrationTests(unittest.TestCase):
    def test_cper_f04_is_context_dependent_with_no_ranking(self):
        result = evaluate_land_profile(PROFILE)
        for operation in result["operation_results"].values():
            factor = operation["factor_evaluations"]["F04_SOIL_WETNESS_ECOLOGICAL_SITE"]
            self.assertEqual(factor["signal"], "CONTEXT_DEPENDENT")
            self.assertEqual(factor["ranking_effect"], "NONE")
            self.assertEqual(operation["decision_label"], "HOLD")
            self.assertIsNone(operation["ranking_position"])
        self.assertFalse(result["cross_profile_comparison"]["ranking_permitted"])

    def test_missing_f04_remains_unknown(self):
        profile = deepcopy(PROFILE)
        profile["factors"].pop("F04_SOIL_WETNESS_ECOLOGICAL_SITE")
        result = evaluate_land_profile(profile)
        signal = result["operation_results"]["COW_CALF_OPERATION"]["factor_evaluations"][
            "F04_SOIL_WETNESS_ECOLOGICAL_SITE"
        ]["signal"]
        self.assertEqual(signal, "UNKNOWN")

    def test_point_only_mireye_soil_needs_verification(self):
        profile = deepcopy(PROFILE)
        profile["factors"]["F04_SOIL_WETNESS_ECOLOGICAL_SITE"] = {
            "input_quality_state": "POINT_ONLY",
            "mireye_point_qa": PROFILE["factors"]["F04_SOIL_WETNESS_ECOLOGICAL_SITE"][
                "mireye_point_qa"
            ],
        }
        result = evaluate_land_profile(profile)
        factor = result["operation_results"]["SHEEP_GRAZING"]["factor_evaluations"][
            "F04_SOIL_WETNESS_ECOLOGICAL_SITE"
        ]
        self.assertEqual(factor["signal"], "NEEDS_VERIFICATION")
        self.assertEqual(factor["ranking_effect"], "NONE")

    def test_incomplete_provenance_needs_verification(self):
        profile = deepcopy(PROFILE)
        profile["factors"]["F04_SOIL_WETNESS_ECOLOGICAL_SITE"]["provenance"][
            "response_or_artifact_hash"
        ] = None
        result = evaluate_land_profile(profile)
        factor = result["operation_results"]["COW_CALF_OPERATION"]["factor_evaluations"][
            "F04_SOIL_WETNESS_ECOLOGICAL_SITE"
        ]
        self.assertEqual(factor["signal"], "NEEDS_VERIFICATION")

    def test_conflicting_sources_need_verification(self):
        profile = deepcopy(PROFILE)
        profile["factors"]["F04_SOIL_WETNESS_ECOLOGICAL_SITE"]["input_quality_state"] = (
            "CONFLICTING_SOURCES"
        )
        result = evaluate_land_profile(profile)
        factor = result["operation_results"]["COW_CALF_OPERATION"]["factor_evaluations"][
            "F04_SOIL_WETNESS_ECOLOGICAL_SITE"
        ]
        self.assertEqual(factor["signal"], "NEEDS_VERIFICATION")

    def test_f04_does_not_create_species_ranking(self):
        result = evaluate_land_profile(PROFILE)
        cow = result["operation_results"]["COW_CALF_OPERATION"]
        sheep = result["operation_results"]["SHEEP_GRAZING"]
        self.assertEqual(cow["decision_label"], sheep["decision_label"])
        self.assertIsNone(cow["ranking_position"])
        self.assertIsNone(sheep["ranking_position"])
        self.assertFalse(result["llm_override_permitted"])


if __name__ == "__main__":
    unittest.main()
