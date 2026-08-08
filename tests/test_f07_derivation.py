"""Executable golden tests for F07 road / physical-access derivation."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from rangematch.engine import evaluate_land_profile
from rangematch.f07_derivation import (
    ALGORITHM_VERSION,
    CANONICAL_SOURCE_ID,
    derive_f07_from_inputs,
    evaluate_county_coverage,
    evaluate_f07_signal,
    stable_road_feature_id,
)
from rangematch.geometry_replace import replace_geometry


ROOT = Path(__file__).resolve().parents[1]
GEOMETRY_001 = ROOT / "test-data/engineering_test_geometry_cper_001.geojson"
GEOMETRY_002 = ROOT / "test-data/engineering_test_geometry_cper_002.geojson"
PROFILE = json.loads((ROOT / "test-data/land-profiles/land_profile_cper_001.json").read_text())
PARCEL = json.loads(GEOMETRY_001.read_text())


def _line_feature(coords, *, linearid: str, mtfcc: str = "S1400"):
    return {
        "type": "Feature",
        "properties": {"LINEARID": linearid, "MTFCC": mtfcc, "FULLNAME": linearid},
        "geometry": {"type": "LineString", "coordinates": coords},
    }


def _roads(*features):
    return {"type": "FeatureCollection", "features": list(features)}


class F07DerivationGoldenTests(unittest.TestCase):
    def test_f07_001_complete_context_dependent(self):
        # Road crossing the CPER engineering rectangle.
        roads = _roads(
            _line_feature(
                [[-104.78, 40.825], [-104.74, 40.825]],
                linearid="L0000001",
            )
        )
        derived = derive_f07_from_inputs(
            PARCEL,
            roads,
            requested_county_fips=["08123"],
            loaded_county_fips=["08123"],
            geometry_hash="testhash",
        )
        signal = evaluate_f07_signal(derived)
        self.assertEqual(derived["algorithm_version"], ALGORITHM_VERSION)
        self.assertEqual(derived["road_source_id"], CANONICAL_SOURCE_ID)
        self.assertEqual(derived["input_quality_state"], "ROAD_CONTEXT_COMPLETE")
        self.assertEqual(derived["road_parcel_contact_status"], "INTERSECTS")
        self.assertGreaterEqual(derived["mapped_road_feature_count_in_search_window"], 1)
        self.assertEqual(signal["signal"], "CONTEXT_DEPENDENT")
        self.assertEqual(signal["ranking_effect"], "NONE")
        self.assertFalse(signal["legal_access_inferred"])
        self.assertFalse(derived["osm_consulted"])

    def test_f07_002_empty_window_context_not_reject(self):
        far = _roads(
            _line_feature(
                [[-105.5, 41.5], [-105.4, 41.5]],
                linearid="FAR1",
            )
        )
        derived = derive_f07_from_inputs(
            PARCEL,
            far,
            requested_county_fips=["08123"],
            loaded_county_fips=["08123"],
            geometry_hash="testhash",
        )
        signal = evaluate_f07_signal(derived)
        self.assertEqual(
            derived["input_quality_state"], "NO_MAPPED_ROAD_IN_SEARCH_WINDOW"
        )
        self.assertEqual(derived["mapped_road_feature_count_in_search_window"], 0)
        self.assertEqual(signal["signal"], "CONTEXT_DEPENDENT")
        profile = deepcopy(PROFILE)
        profile["factors"]["F07_ROAD_AND_PHYSICAL_ACCESS"] = derived
        result = evaluate_land_profile(profile)
        for operation in result["operation_results"].values():
            self.assertEqual(operation["decision_label"], "HOLD")
            self.assertNotEqual(operation["decision_label"], "REJECT")

    def test_f07_003_missing_unknown(self):
        derived = derive_f07_from_inputs(
            None,
            None,
            requested_county_fips=["08123"],
            loaded_county_fips=["08123"],
        )
        signal = evaluate_f07_signal(derived)
        self.assertEqual(derived["input_quality_state"], "MISSING")
        self.assertEqual(signal["signal"], "UNKNOWN")

    def test_f07_012_cross_county_incomplete_needs_verification(self):
        roads = _roads(
            _line_feature(
                [[-104.78, 40.825], [-104.74, 40.825]],
                linearid="L0000001",
            )
        )
        derived = derive_f07_from_inputs(
            PARCEL,
            roads,
            requested_county_fips=["08123", "08069"],
            loaded_county_fips=["08123"],
            geometry_hash="testhash",
        )
        signal = evaluate_f07_signal(derived)
        self.assertEqual(derived["county_coverage"]["status"], "PARTIAL")
        self.assertEqual(derived["input_quality_state"], "ROAD_SOURCE_INCOMPLETE")
        self.assertIsNone(derived["nearest_mapped_road_distance_m"])
        self.assertIsNone(derived["mapped_road_feature_count_in_search_window"])
        self.assertEqual(signal["signal"], "NEEDS_VERIFICATION")
        self.assertEqual(signal["explanation_code"], "F07_EXPL_SOURCE_INCOMPLETE")

    def test_f07_013_cross_county_complete_allows_measure(self):
        roads = _roads(
            _line_feature(
                [[-104.78, 40.825], [-104.74, 40.825]],
                linearid="L0000001",
            )
        )
        derived = derive_f07_from_inputs(
            PARCEL,
            roads,
            requested_county_fips=["08123", "08069"],
            loaded_county_fips=["08123", "08069"],
            geometry_hash="testhash",
        )
        self.assertEqual(derived["county_coverage"]["status"], "COMPLETE")
        self.assertEqual(derived["input_quality_state"], "ROAD_CONTEXT_COMPLETE")
        self.assertIsInstance(derived["nearest_mapped_road_distance_m"], float)

    def test_f07_014_equal_distance_tie_break_by_stable_id(self):
        # Two parallel roads at identical distance south of the parcel.
        roads = _roads(
            _line_feature(
                [[-104.770, 40.815], [-104.755, 40.815]],
                linearid="LZZZZZZZ",
            ),
            _line_feature(
                [[-104.770, 40.815], [-104.755, 40.815]],
                linearid="LAAAAAAA",
            ),
        )
        derived = derive_f07_from_inputs(
            PARCEL,
            roads,
            requested_county_fips=["08123"],
            loaded_county_fips=["08123"],
            geometry_hash="testhash",
        )
        self.assertEqual(derived["mapped_road_feature_count_in_search_window"], 2)
        self.assertEqual(derived["nearest_road_feature_id"], "LAAAAAAA")
        self.assertLess(
            stable_road_feature_id({"LINEARID": "LAAAAAAA"}, 0),
            stable_road_feature_id({"LINEARID": "LZZZZZZZ"}, 1),
        )

    def test_f07_touches_preserved_distinct_from_intersects(self):
        # Road exactly along the southern boundary (touches).
        roads = _roads(
            _line_feature(
                [[-104.770, 40.820], [-104.755, 40.820]],
                linearid="TOUCH1",
            )
        )
        derived = derive_f07_from_inputs(
            PARCEL,
            roads,
            requested_county_fips=["08123"],
            loaded_county_fips=["08123"],
            geometry_hash="testhash",
        )
        self.assertEqual(derived["road_parcel_contact_status"], "TOUCHES")
        self.assertEqual(
            derived["road_parcel_contact_detail"]["touches_feature_count"], 1
        )
        self.assertEqual(
            derived["road_parcel_contact_detail"]["intersects_feature_count"], 0
        )

    def test_f07_osm_deferred_rejected(self):
        roads = _roads(
            _line_feature(
                [[-104.78, 40.825], [-104.74, 40.825]],
                linearid="OSM1",
            )
        )
        derived = derive_f07_from_inputs(
            PARCEL,
            roads,
            requested_county_fips=["08123"],
            loaded_county_fips=["08123"],
            road_source_id="OPENSTREETMAP_HIGHWAYS",
            geometry_hash="testhash",
        )
        signal = evaluate_f07_signal(derived)
        self.assertEqual(signal["signal"], "NEEDS_VERIFICATION")
        self.assertFalse(derived["osm_consulted"])

    def test_f07_edges_fallback_not_implemented_in_v0_1(self):
        from rangematch.f07_derivation import EDGES_FALLBACK_SOURCE_ID

        roads = _roads(
            _line_feature(
                [[-104.78, 40.825], [-104.74, 40.825]],
                linearid="EDGE1",
            )
        )
        derived = derive_f07_from_inputs(
            PARCEL,
            roads,
            requested_county_fips=["08123"],
            loaded_county_fips=["08123"],
            road_source_id=EDGES_FALLBACK_SOURCE_ID,
            geometry_hash="testhash",
        )
        signal = evaluate_f07_signal(derived)
        self.assertEqual(derived["input_quality_state"], "ROAD_SOURCE_INCOMPLETE")
        self.assertFalse(derived["edges_fallback_used"])
        self.assertEqual(signal["signal"], "NEEDS_VERIFICATION")
        self.assertTrue(
            any("not implemented" in item.lower() for item in derived["limitations"])
        )

    def test_f07_county_coverage_unknown_when_none_requested(self):
        coverage = evaluate_county_coverage([], ["08123"])
        self.assertEqual(coverage["status"], "UNKNOWN")

    def test_f07_geometry_replace_invalidates(self):
        if "F07_ROAD_AND_PHYSICAL_ACCESS" not in PROFILE["factors"]:
            self.skipTest("CPER profile F07 not yet written")
        replaced = replace_geometry(
            deepcopy(PROFILE),
            GEOMETRY_002,
            geometry_reference="test-data/engineering_test_geometry_cper_002.geojson",
        )
        f07 = replaced["factors"]["F07_ROAD_AND_PHYSICAL_ACCESS"]
        self.assertEqual(f07["input_quality_state"], "MISSING")
        self.assertNotIn("nearest_mapped_road_distance_m", f07)

    def test_f07_engine_cow_sheep_identical_no_ranking(self):
        if "F07_ROAD_AND_PHYSICAL_ACCESS" not in PROFILE["factors"]:
            self.skipTest("CPER profile F07 not yet written")
        result = evaluate_land_profile(PROFILE)
        cow = result["operation_results"]["COW_CALF_OPERATION"]["factor_evaluations"][
            "F07_ROAD_AND_PHYSICAL_ACCESS"
        ]
        sheep = result["operation_results"]["SHEEP_GRAZING"]["factor_evaluations"][
            "F07_ROAD_AND_PHYSICAL_ACCESS"
        ]
        self.assertEqual(cow, sheep)
        self.assertEqual(cow["ranking_effect"], "NONE")
        self.assertIn(cow["signal"], {"CONTEXT_DEPENDENT", "NEEDS_VERIFICATION", "UNKNOWN"})
        self.assertFalse(result["cross_profile_comparison"]["ranking_permitted"])

    def test_f07_neg_no_legal_or_threshold_fields(self):
        roads = _roads(
            _line_feature(
                [[-104.78, 40.825], [-104.74, 40.825]],
                linearid="L0000001",
            )
        )
        derived = derive_f07_from_inputs(
            PARCEL,
            roads,
            requested_county_fips=["08123"],
            loaded_county_fips=["08123"],
            geometry_hash="testhash",
        )
        blob = json.dumps(derived).lower()
        self.assertNotIn("legal_access_status", blob)
        self.assertNotIn("suitability_class", blob)
        self.assertNotIn("carrying_capacity", blob)
        self.assertNotIn("fencing_cost", blob)
        self.assertNotIn("travel_time", blob)


if __name__ == "__main__":
    unittest.main()
