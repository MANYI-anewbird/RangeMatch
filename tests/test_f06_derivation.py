"""Executable golden tests for F06 parcel-configuration derivation."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from rangematch.engine import evaluate_land_profile
from rangematch.f06_derivation import (
    ALGORITHM_VERSION,
    INTERNATIONAL_ACRE_M2,
    compactness_isoperimetric,
    derive_f06_from_geometry,
    derive_f06_from_geometry_path,
    evaluate_f06_signal,
)
from rangematch.geometry_replace import replace_geometry


ROOT = Path(__file__).resolve().parents[1]
GEOMETRY_001 = ROOT / "test-data/engineering_test_geometry_cper_001.geojson"
GEOMETRY_002 = ROOT / "test-data/engineering_test_geometry_cper_002.geojson"
PROFILE = json.loads((ROOT / "test-data/land-profiles/land_profile_cper_001.json").read_text())
F06_RESULT = json.loads(
    (ROOT / "test-data/live-results/cper/f06_derivation_result_2026-08-08.json").read_text()
)


def _polygon_feature(coords, *, holes=None, geometry_id="TEST_POLY"):
    rings = [coords]
    if holes:
        rings.extend(holes)
    return {
        "type": "Feature",
        "id": geometry_id,
        "properties": {"geometry_id": geometry_id},
        "geometry": {"type": "Polygon", "coordinates": rings},
    }


class F06DerivationGoldenTests(unittest.TestCase):
    def test_f06_001_valid_geometry_context_dependent(self):
        derived = derive_f06_from_geometry_path(
            GEOMETRY_001,
            geometry_reference="test-data/engineering_test_geometry_cper_001.geojson",
        )
        self.assertEqual(derived["input_quality_state"], "PARCEL_GEOMETRY_COMPLETE")
        self.assertEqual(derived["algorithm_version"], ALGORITHM_VERSION)
        self.assertEqual(derived["working_crs"], "EPSG:32613")
        self.assertFalse(derived["automatic_repair_applied"])
        signal = evaluate_f06_signal(derived)
        self.assertEqual(signal["signal"], "CONTEXT_DEPENDENT")
        self.assertEqual(signal["ranking_effect"], "NONE")
        self.assertEqual(signal["explanation_code"], "F06_EXPL_CONTEXT_ONLY")

    def test_f06_002_missing_geometry_unknown(self):
        derived = derive_f06_from_geometry(None)
        signal = evaluate_f06_signal(derived)
        self.assertEqual(derived["input_quality_state"], "MISSING")
        self.assertEqual(signal["signal"], "UNKNOWN")
        self.assertEqual(signal["explanation_code"], "F06_EXPL_MISSING")

    def test_f06_003_invalid_geometry_needs_verification_not_unsuitable(self):
        # Self-touching / bowtie-like invalid ring.
        bad = _polygon_feature(
            [[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]],
            geometry_id="INVALID_BOWTIE",
        )
        derived = derive_f06_from_geometry(bad, geometry_hash="deadbeef")
        signal = evaluate_f06_signal(derived)
        self.assertEqual(derived["input_quality_state"], "GEOMETRY_INVALID_OR_EMPTY")
        self.assertFalse(derived.get("automatic_repair_applied", True))
        self.assertIsNone(derived["area_m2"])
        self.assertEqual(signal["signal"], "NEEDS_VERIFICATION")
        self.assertEqual(signal["explanation_code"], "F06_EXPL_GEOMETRY_UNUSABLE")
        profile = deepcopy(PROFILE)
        profile["factors"]["F06_PARCEL_CONFIGURATION"] = derived
        result = evaluate_land_profile(profile)
        for operation in result["operation_results"].values():
            self.assertEqual(operation["decision_label"], "HOLD")
            self.assertNotEqual(operation["decision_label"], "REJECT")

    def test_f06_004_utm_zone_crossing_needs_verification(self):
        # Lon span crosses UTM zone 12/13 boundary near -108°.
        wide = _polygon_feature(
            [
                [-108.5, 40.0],
                [-107.5, 40.0],
                [-107.5, 40.1],
                [-108.5, 40.1],
                [-108.5, 40.0],
            ],
            geometry_id="ZONE_CROSS",
        )
        derived = derive_f06_from_geometry(wide, geometry_hash="zonehash")
        signal = evaluate_f06_signal(derived)
        self.assertEqual(derived["input_quality_state"], "CRS_UNSUPPORTED")
        self.assertEqual(
            derived["crs_selection"]["reason"], "PARCEL_CROSSES_UTM_ZONE_BOUNDARY"
        )
        self.assertIsNone(derived["area_m2"])
        self.assertEqual(signal["signal"], "NEEDS_VERIFICATION")
        self.assertEqual(signal["explanation_code"], "F06_EXPL_CRS_UNSUPPORTED")

    def test_f06_005_incomplete_provenance_needs_verification(self):
        derived = derive_f06_from_geometry_path(
            GEOMETRY_001,
            geometry_reference="test-data/engineering_test_geometry_cper_001.geojson",
        )
        derived.pop("geometry_hash")
        completeness_state = evaluate_f06_signal(
            {
                **derived,
                "input_quality_state": "PARCEL_INCOMPLETE",
            }
        )
        self.assertEqual(completeness_state["signal"], "NEEDS_VERIFICATION")
        self.assertEqual(
            completeness_state["explanation_code"], "F06_EXPL_INCOMPLETE_PROVENANCE"
        )

    def test_f06_006_conflicting_sources_needs_verification(self):
        derived = derive_f06_from_geometry(
            None,
            conflicting_geometry_hashes=["aaa", "bbb"],
        )
        signal = evaluate_f06_signal(derived)
        self.assertEqual(derived["input_quality_state"], "CONFLICTING_SOURCES")
        self.assertEqual(signal["signal"], "NEEDS_VERIFICATION")
        self.assertEqual(signal["explanation_code"], "F06_EXPL_CONFLICT")

    def test_f06_007_planar_lon_lat_degrees_prohibited(self):
        # Derivation always projects; degree planar area is never used as Land Fact.
        derived = derive_f06_from_geometry_path(GEOMETRY_001)
        self.assertTrue(str(derived["working_crs"]).startswith("EPSG:326"))
        self.assertNotEqual(derived["working_crs"], "EPSG:4326")
        self.assertIsInstance(derived["area_m2"], float)
        self.assertGreater(derived["area_m2"], 1000.0)

    def test_f06_008_compactness_formula_no_threshold(self):
        value = compactness_isoperimetric(10000.0, 400.0)
        self.assertAlmostEqual(value, 0.7853981633974483, places=12)
        self.assertIsNone(evaluate_f06_signal({"input_quality_state": "PARCEL_GEOMETRY_COMPLETE", "compactness": value}).get("suitability_class"))
        self.assertEqual(
            evaluate_f06_signal(
                {
                    "input_quality_state": "PARCEL_GEOMETRY_COMPLETE",
                    "compactness": value,
                }
            )["ranking_effect"],
            "NONE",
        )

    def test_f06_009_multipart_remains_context(self):
        multi = {
            "type": "Feature",
            "id": "MULTI",
            "properties": {"geometry_id": "MULTI"},
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [
                    [[[-104.7, 40.8], [-104.69, 40.8], [-104.69, 40.81], [-104.7, 40.81], [-104.7, 40.8]]],
                    [[[-104.68, 40.8], [-104.67, 40.8], [-104.67, 40.81], [-104.68, 40.81], [-104.68, 40.8]]],
                ],
            },
        }
        derived = derive_f06_from_geometry(multi, geometry_hash="multi")
        signal = evaluate_f06_signal(derived)
        self.assertEqual(derived["polygon_part_count"], 2)
        self.assertEqual(derived["input_quality_state"], "PARCEL_GEOMETRY_COMPLETE")
        self.assertEqual(signal["signal"], "CONTEXT_DEPENDENT")
        self.assertTrue(
            any("Multi-part" in item for item in derived["limitations"])
        )

    def test_f06_010_geometry_hash_change_requires_recompute(self):
        original = deepcopy(PROFILE)
        replaced = replace_geometry(
            original,
            GEOMETRY_002,
            geometry_reference="test-data/engineering_test_geometry_cper_002.geojson",
        )
        f06 = replaced["factors"]["F06_PARCEL_CONFIGURATION"]
        self.assertEqual(f06["input_quality_state"], "MISSING")
        self.assertEqual(f06["geometry_replacement_status"], "EVIDENCE_INVALIDATED")
        self.assertNotIn("area_m2", f06)
        recomputed = derive_f06_from_geometry_path(
            GEOMETRY_002,
            geometry_reference="test-data/engineering_test_geometry_cper_002.geojson",
        )
        self.assertNotEqual(
            recomputed["geometry_hash"],
            original["factors"]["F06_PARCEL_CONFIGURATION"]["geometry_hash"],
        )
        self.assertNotAlmostEqual(
            recomputed["area_m2"],
            original["factors"]["F06_PARCEL_CONFIGURATION"]["area_m2"],
            places=3,
        )

    def test_f06_holes_subtracted_perimeter_exterior_only(self):
        outer = [
            [-104.70, 40.80],
            [-104.69, 40.80],
            [-104.69, 40.81],
            [-104.70, 40.81],
            [-104.70, 40.80],
        ]
        hole = [
            [-104.697, 40.803],
            [-104.693, 40.803],
            [-104.693, 40.807],
            [-104.697, 40.807],
            [-104.697, 40.803],
        ]
        solid = derive_f06_from_geometry(
            _polygon_feature(outer, geometry_id="SOLID"), geometry_hash="solid"
        )
        with_hole = derive_f06_from_geometry(
            _polygon_feature(outer, holes=[hole], geometry_id="HOLED"),
            geometry_hash="holed",
        )
        self.assertTrue(with_hole["has_holes"])
        self.assertLess(with_hole["area_m2"], solid["area_m2"])
        # Exterior perimeter should match for identical outer rings.
        self.assertAlmostEqual(with_hole["perimeter_m"], solid["perimeter_m"], places=6)

    def test_f06_international_acre_display_only(self):
        derived = derive_f06_from_geometry_path(GEOMETRY_001)
        expected_acre = derived["area_m2"] / INTERNATIONAL_ACRE_M2
        self.assertAlmostEqual(
            derived["display_only"]["area_acre_international"], expected_acre, places=12
        )
        self.assertFalse(derived["display_conversions"]["are_land_facts"])
        self.assertEqual(
            derived["display_conversions"]["acre_convention"], "international_acre"
        )

    def test_f06_cper_fixture_matches_locked_result(self):
        derived = derive_f06_from_geometry_path(
            GEOMETRY_001,
            geometry_reference="test-data/engineering_test_geometry_cper_001.geojson",
            geometry_id="ENGINEERING_TEST_GEOMETRY_CPER_001",
        )
        self.assertAlmostEqual(derived["area_m2"], F06_RESULT["area_m2"], places=6)
        self.assertAlmostEqual(derived["perimeter_m"], F06_RESULT["perimeter_m"], places=6)
        self.assertAlmostEqual(derived["compactness"], F06_RESULT["compactness"], places=12)
        self.assertEqual(derived["geometry_hash"], F06_RESULT["geometry_hash"])

    def test_f06_engine_cow_sheep_identical_no_ranking(self):
        result = evaluate_land_profile(PROFILE)
        cow = result["operation_results"]["COW_CALF_OPERATION"]["factor_evaluations"][
            "F06_PARCEL_CONFIGURATION"
        ]
        sheep = result["operation_results"]["SHEEP_GRAZING"]["factor_evaluations"][
            "F06_PARCEL_CONFIGURATION"
        ]
        self.assertEqual(cow, sheep)
        self.assertEqual(cow["signal"], "CONTEXT_DEPENDENT")
        self.assertEqual(cow["ranking_effect"], "NONE")
        self.assertFalse(result["cross_profile_comparison"]["ranking_permitted"])
        for operation in result["operation_results"].values():
            self.assertEqual(operation["decision_label"], "HOLD")
            self.assertIsNone(operation["ranking_position"])

    def test_f06_neg_no_fencing_cost_or_carrying_capacity_fields(self):
        derived = derive_f06_from_geometry_path(GEOMETRY_001)
        blob = json.dumps(derived).lower()
        self.assertNotIn("fencing_cost", blob)
        self.assertNotIn("carrying_capacity", blob)
        self.assertNotIn("suitability_class", blob)
        self.assertNotIn("road_access", blob)

    def test_f06_feature_collection_zero_features_needs_verification(self):
        empty_fc = {"type": "FeatureCollection", "features": []}
        derived = derive_f06_from_geometry(empty_fc, geometry_hash="empty_fc")
        signal = evaluate_f06_signal(derived)
        self.assertEqual(derived["input_quality_state"], "GEOMETRY_INVALID_OR_EMPTY")
        self.assertEqual(
            derived["extraction_error"]["reason"], "FEATURE_COLLECTION_EMPTY"
        )
        self.assertIsNone(derived["area_m2"])
        self.assertEqual(signal["signal"], "NEEDS_VERIFICATION")

    def test_f06_feature_collection_one_feature_allowed(self):
        feature = _polygon_feature(
            [
                [-104.70, 40.80],
                [-104.69, 40.80],
                [-104.69, 40.81],
                [-104.70, 40.81],
                [-104.70, 40.80],
            ],
            geometry_id="SINGLE_FC",
        )
        fc = {"type": "FeatureCollection", "features": [feature]}
        derived = derive_f06_from_geometry(fc, geometry_hash="single_fc")
        signal = evaluate_f06_signal(derived)
        self.assertEqual(derived["feature_count"], 1)
        self.assertEqual(derived["input_quality_state"], "PARCEL_GEOMETRY_COMPLETE")
        self.assertIsInstance(derived["area_m2"], float)
        self.assertEqual(signal["signal"], "CONTEXT_DEPENDENT")

    def test_f06_feature_collection_multiple_features_not_silent_first(self):
        small = _polygon_feature(
            [
                [-104.70, 40.80],
                [-104.699, 40.80],
                [-104.699, 40.801],
                [-104.70, 40.801],
                [-104.70, 40.80],
            ],
            geometry_id="SMALL",
        )
        large = _polygon_feature(
            [
                [-104.70, 40.80],
                [-104.68, 40.80],
                [-104.68, 40.82],
                [-104.70, 40.82],
                [-104.70, 40.80],
            ],
            geometry_id="LARGE",
        )
        # If implementation silently measured features[0], area would match SMALL only.
        silent_first = derive_f06_from_geometry(
            {"type": "FeatureCollection", "features": [small]},
            geometry_hash="small_only",
        )
        multi = derive_f06_from_geometry(
            {"type": "FeatureCollection", "features": [small, large]},
            geometry_hash="multi_fc",
        )
        signal = evaluate_f06_signal(multi)
        self.assertEqual(multi["input_quality_state"], "GEOMETRY_INVALID_OR_EMPTY")
        self.assertEqual(
            multi["extraction_error"]["reason"], "FEATURE_COLLECTION_MULTIPLE_FEATURES"
        )
        self.assertEqual(multi["feature_count"], 2)
        self.assertIsNone(multi["area_m2"])
        self.assertNotEqual(multi.get("area_m2"), silent_first.get("area_m2"))
        self.assertEqual(signal["signal"], "NEEDS_VERIFICATION")
        self.assertTrue(
            any("does not silently" in item for item in multi["limitations"])
        )

    def test_f06_non_epsg_4326_source_crs_unsupported(self):
        feature = _polygon_feature(
            [
                [-104.70, 40.80],
                [-104.69, 40.80],
                [-104.69, 40.81],
                [-104.70, 40.81],
                [-104.70, 40.80],
            ]
        )
        derived = derive_f06_from_geometry(
            feature,
            geometry_hash="utm13n_as_source",
            source_crs="EPSG:32613",
        )
        signal = evaluate_f06_signal(derived)
        self.assertEqual(derived["input_quality_state"], "CRS_UNSUPPORTED")
        self.assertEqual(
            derived["crs_selection"]["reason"], "SOURCE_CRS_NOT_EPSG_4326"
        )
        self.assertIsNone(derived["area_m2"])
        self.assertEqual(signal["signal"], "NEEDS_VERIFICATION")
        self.assertEqual(signal["explanation_code"], "F06_EXPL_CRS_UNSUPPORTED")

    def test_f06_lon_lat_bounds_outside_valid_range(self):
        out_of_range = _polygon_feature(
            [
                [200.0, 40.0],
                [201.0, 40.0],
                [201.0, 41.0],
                [200.0, 41.0],
                [200.0, 40.0],
            ],
            geometry_id="BAD_LON",
        )
        derived = derive_f06_from_geometry(out_of_range, geometry_hash="bad_lon")
        signal = evaluate_f06_signal(derived)
        self.assertEqual(derived["input_quality_state"], "CRS_UNSUPPORTED")
        self.assertEqual(
            derived["crs_selection"]["reason"], "PARCEL_OUTSIDE_VALID_LON_LAT_BOUNDS"
        )
        self.assertIsNone(derived["area_m2"])
        self.assertEqual(signal["signal"], "NEEDS_VERIFICATION")

        polar = _polygon_feature(
            [
                [-104.70, 85.0],
                [-104.69, 85.0],
                [-104.69, 86.0],
                [-104.70, 86.0],
                [-104.70, 85.0],
            ],
            geometry_id="POLAR",
        )
        polar_derived = derive_f06_from_geometry(polar, geometry_hash="polar")
        self.assertEqual(polar_derived["input_quality_state"], "CRS_UNSUPPORTED")
        self.assertEqual(
            polar_derived["crs_selection"]["reason"],
            "PARCEL_OUTSIDE_SUPPORTED_UTM_LATITUDE",
        )


if __name__ == "__main__":
    unittest.main()
