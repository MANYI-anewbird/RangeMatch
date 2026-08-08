"""Executable golden tests for F08 woody / shrub vegetation-structure derivation."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from rangematch.engine import evaluate_land_profile
from rangematch.f08_derivation import (
    ALGORITHM_VERSION,
    FACTOR_ID,
    combined_modeled_woody_cover_fraction,
    derive_f08_from_coverV3_artifact,
    derive_f08_from_rap_bands,
    derive_f08_reusing_f02_artifact,
    evaluate_f08_signal,
    percent_to_fraction,
    sha256_file,
)
from rangematch.geometry_replace import replace_geometry


ROOT = Path(__file__).resolve().parents[1]
GEOMETRY_001 = ROOT / "test-data/engineering_test_geometry_cper_001.geojson"
GEOMETRY_002 = ROOT / "test-data/engineering_test_geometry_cper_002.geojson"
PROFILE_PATH = ROOT / "test-data/land-profiles/land_profile_cper_001.json"
COVER_V3 = ROOT / "test-data/live-results/cper/rap_coverV3_2025.json"
PROFILE = json.loads(PROFILE_PATH.read_text())


class F08DerivationGoldenTests(unittest.TestCase):
    def test_f08_001_coverage_unquantified_needs_verification(self):
        derived = derive_f08_from_rap_bands(
            raw_shr_percent=6.73,
            raw_tre_percent=0.11,
            source_year=2025,
            mask=True,
            geometry_hash="abc",
            response_or_artifact_hash="hash1",
            applicability_status="IN_DOCUMENTED_PRODUCT_SCOPE",
            coverage_status="COVERAGE_UNQUANTIFIED",
        )
        signal = evaluate_f08_signal(derived)
        self.assertEqual(
            derived["input_quality_state"],
            "WOODY_CONTEXT_AVAILABLE_COVERAGE_UNQUANTIFIED",
        )
        self.assertEqual(signal["signal"], "NEEDS_VERIFICATION")
        self.assertEqual(signal["explanation_code"], "F08_EXPL_COVERAGE_UNQUANTIFIED")
        self.assertEqual(signal["ranking_effect"], "NONE")
        self.assertFalse(signal["labeled_complete"])
        self.assertFalse(signal["browse_inferred"])
        self.assertFalse(signal["obstruction_inferred"])

    def test_f08_002_mireye_point_only_needs_verification(self):
        derived = derive_f08_from_coverV3_artifact(
            None,
            point_only_secondary=True,
        )
        signal = evaluate_f08_signal(derived)
        self.assertEqual(derived["input_quality_state"], "POINT_ONLY_SECONDARY")
        self.assertEqual(signal["signal"], "NEEDS_VERIFICATION")
        self.assertEqual(signal["explanation_code"], "F08_EXPL_POINT_ONLY")
        self.assertFalse(derived["mireye_used_as_parcel_land_fact"])

    def test_f08_003_missing_and_coverage_missing(self):
        missing = derive_f08_from_rap_bands(
            raw_shr_percent=None,
            raw_tre_percent=None,
            source_year=None,
            mask=None,
            geometry_hash=None,
            response_or_artifact_hash=None,
            applicability_status=None,
            coverage_status=None,
        )
        self.assertEqual(evaluate_f08_signal(missing)["signal"], "UNKNOWN")
        self.assertEqual(missing["input_quality_state"], "MISSING")

        cov_missing = derive_f08_from_rap_bands(
            raw_shr_percent=10.0,
            raw_tre_percent=1.0,
            source_year=2025,
            mask=True,
            geometry_hash="g",
            response_or_artifact_hash="h",
            applicability_status="IN_DOCUMENTED_PRODUCT_SCOPE",
            coverage_status="UNKNOWN",
        )
        self.assertEqual(cov_missing["input_quality_state"], "COVERAGE_MISSING")
        self.assertEqual(
            evaluate_f08_signal(cov_missing)["signal"], "NEEDS_VERIFICATION"
        )

    def test_f08_004_applicability_preserved(self):
        for status in ("OUTSIDE_DOCUMENTED_PRODUCT_SCOPE", "UNKNOWN"):
            derived = derive_f08_from_rap_bands(
                raw_shr_percent=5.0,
                raw_tre_percent=1.0,
                source_year=2025,
                mask=True,
                geometry_hash="g",
                response_or_artifact_hash="h",
                applicability_status=status,
                coverage_status="COVERAGE_UNQUANTIFIED",
            )
            signal = evaluate_f08_signal(derived)
            self.assertEqual(
                derived["input_quality_state"], "RAP_OUTSIDE_OR_UNKNOWN_APPLICABILITY"
            )
            self.assertEqual(signal["signal"], "NEEDS_VERIFICATION")
            self.assertEqual(signal["explanation_code"], "F08_EXPL_APPLICABILITY")
            self.assertEqual(derived["applicability_status"], status)

    def test_f08_005_conflict_not_averaged(self):
        derived = derive_f08_from_coverV3_artifact(
            {
                "type": "Feature",
                "properties": {
                    "year": 2025,
                    "mask": True,
                    "cover": [
                        ["year", "SHR", "TRE"],
                        [2025, 10.0, 1.0],
                    ],
                },
            },
            conflicting_sources=True,
            applicability_status="IN_DOCUMENTED_PRODUCT_SCOPE",
            coverage_status="COVERAGE_UNQUANTIFIED",
        )
        signal = evaluate_f08_signal(derived)
        self.assertEqual(derived["input_quality_state"], "CONFLICTING_SOURCES")
        self.assertEqual(signal["signal"], "NEEDS_VERIFICATION")
        self.assertEqual(signal["explanation_code"], "F08_EXPL_CONFLICT")

    def test_f08_006_shrub_not_browse(self):
        derived = derive_f08_from_rap_bands(
            raw_shr_percent=25.0,
            raw_tre_percent=0.0,
            source_year=2025,
            mask=True,
            geometry_hash="g",
            response_or_artifact_hash="h",
            applicability_status="IN_DOCUMENTED_PRODUCT_SCOPE",
            coverage_status="COVERAGE_UNQUANTIFIED",
        )
        self.assertAlmostEqual(derived["shrub_cover_fraction"], 0.25)
        self.assertIsNone(derived.get("browse_availability"))
        self.assertFalse(derived["browse_inferred"])

    def test_f08_007_tree_not_obstruction(self):
        derived = derive_f08_from_rap_bands(
            raw_shr_percent=0.0,
            raw_tre_percent=15.0,
            source_year=2025,
            mask=True,
            geometry_hash="g",
            response_or_artifact_hash="h",
            applicability_status="IN_DOCUMENTED_PRODUCT_SCOPE",
            coverage_status="COVERAGE_UNQUANTIFIED",
        )
        self.assertAlmostEqual(derived["tree_cover_fraction"], 0.15)
        self.assertFalse(derived["obstruction_inferred"])
        self.assertNotIn("obstruction_class", derived)

    def test_f08_008_no_cow_sheep_ranking(self):
        derived = derive_f08_from_rap_bands(
            raw_shr_percent=30.0,
            raw_tre_percent=5.0,
            source_year=2025,
            mask=True,
            geometry_hash="g",
            response_or_artifact_hash="h",
            applicability_status="IN_DOCUMENTED_PRODUCT_SCOPE",
            coverage_status="COVERAGE_UNQUANTIFIED",
        )
        profile = deepcopy(PROFILE)
        profile["factors"][FACTOR_ID] = derived
        result = evaluate_land_profile(profile)
        cow = result["operation_results"]["COW_CALF_OPERATION"]
        sheep = result["operation_results"]["SHEEP_GRAZING"]
        cow_sig = cow["factor_evaluations"][FACTOR_ID]["signal"]
        sheep_sig = sheep["factor_evaluations"][FACTOR_ID]["signal"]
        self.assertEqual(cow_sig, sheep_sig)
        self.assertIsNone(cow["ranking_position"])
        self.assertIsNone(sheep["ranking_position"])
        self.assertEqual(
            cow["factor_evaluations"][FACTOR_ID]["ranking_effect"], "NONE"
        )

    def test_f08_009_deterministic_identical(self):
        kwargs = dict(
            raw_shr_percent=6.73,
            raw_tre_percent=0.11,
            source_year=2025,
            mask=True,
            geometry_hash="abc",
            response_or_artifact_hash="hash1",
            applicability_status="IN_DOCUMENTED_PRODUCT_SCOPE",
            coverage_status="COVERAGE_UNQUANTIFIED",
            derived_at="2026-08-08T12:00:00Z",
        )
        a = derive_f08_from_rap_bands(**kwargs)
        b = derive_f08_from_rap_bands(**kwargs)
        self.assertEqual(a["algorithm_version"], ALGORITHM_VERSION)
        self.assertEqual(
            json.dumps(a, sort_keys=True),
            json.dumps(b, sort_keys=True),
        )

    def test_f08_010_geometry_replacement_invalidates(self):
        profile = deepcopy(PROFILE)
        if FACTOR_ID not in profile["factors"]:
            profile["factors"][FACTOR_ID] = derive_f08_from_rap_bands(
                raw_shr_percent=6.73,
                raw_tre_percent=0.11,
                source_year=2025,
                mask=True,
                geometry_hash=profile["geometry_hash"],
                response_or_artifact_hash="hash1",
                applicability_status="IN_DOCUMENTED_PRODUCT_SCOPE",
                coverage_status="COVERAGE_UNQUANTIFIED",
            )
        prior_shr = profile["factors"][FACTOR_ID].get("shrub_cover_fraction")
        replaced = replace_geometry(
            profile,
            GEOMETRY_002,
            geometry_reference="test-data/engineering_test_geometry_cper_002.geojson",
        )
        f08 = replaced["factors"][FACTOR_ID]
        self.assertEqual(f08.get("input_quality_state"), "MISSING")
        self.assertEqual(
            f08.get("geometry_replacement_status"), "EVIDENCE_INVALIDATED"
        )
        self.assertNotIn("shrub_cover_fraction", f08)
        self.assertNotEqual(replaced["geometry_hash"], profile["geometry_hash"])
        self.assertTrue(
            replaced["geometry_replacement"]["factor_evidence_invalidated"]
        )
        self.assertTrue(
            any("F01–F08" in item for item in replaced.get("unknowns") or [])
        )
        # Prior woody measurement must not remain on the invalidated factor.
        if prior_shr is not None:
            self.assertNotEqual(f08.get("shrub_cover_fraction"), prior_shr)

    def test_f08_011_shared_f02_provenance_aligned(self):
        f02 = PROFILE["factors"]["F02_HERBACEOUS_RESOURCE"]
        derived = derive_f08_reusing_f02_artifact(
            coverV3_artifact_path=COVER_V3,
            f02_factor=f02,
            geometry_hash=PROFILE["geometry_hash"],
            geometry_id=PROFILE["geometry_id"],
            geometry_reference=PROFILE["geometry_reference"],
        )
        shared = derived["shared_with_f02"]
        self.assertTrue(shared["same_artifact"])
        self.assertTrue(shared["same_geometry_hash"])
        self.assertTrue(shared["same_source_year"])
        self.assertTrue(shared["same_mask"])
        self.assertTrue(shared["same_applicability_status"])
        self.assertTrue(shared["same_coverage_status"])
        self.assertEqual(
            derived["response_or_artifact_hash"],
            shared["f02_response_or_artifact_hash"],
        )
        self.assertEqual(derived["coverage_status"], "COVERAGE_UNQUANTIFIED")
        self.assertFalse(derived["duplicate_coverV3_fetch"])
        self.assertTrue(derived["reused_existing_artifact"])
        self.assertEqual(
            sha256_file(COVER_V3), derived["response_or_artifact_hash"]
        )

    def test_f08_012_percent_to_fraction_and_combined(self):
        self.assertAlmostEqual(percent_to_fraction(6.73), 0.0673)
        self.assertAlmostEqual(percent_to_fraction(0.11), 0.0011)
        derived = derive_f08_from_rap_bands(
            raw_shr_percent=6.73,
            raw_tre_percent=0.11,
            source_year=2025,
            mask=True,
            geometry_hash="g",
            response_or_artifact_hash="h",
            applicability_status="IN_DOCUMENTED_PRODUCT_SCOPE",
            coverage_status="COVERAGE_UNQUANTIFIED",
        )
        self.assertAlmostEqual(derived["shrub_cover_fraction"], 0.0673)
        self.assertAlmostEqual(derived["tree_cover_fraction"], 0.0011)
        self.assertAlmostEqual(derived["combined_modeled_woody_cover_fraction"], 0.0684)
        self.assertEqual(derived["unit"], "fraction")
        self.assertEqual(derived["raw_rap_shr_percent"], 6.73)
        self.assertEqual(derived["raw_rap_tre_percent"], 0.11)
        self.assertFalse(derived["forced_sum_to_100"])
        self.assertFalse(derived["combined_included_in_composition_sum"])

    def test_f08_013_combined_null_if_either_null(self):
        self.assertIsNone(combined_modeled_woody_cover_fraction(0.10, None))
        self.assertIsNone(combined_modeled_woody_cover_fraction(None, 0.05))
        self.assertIsNone(combined_modeled_woody_cover_fraction(None, None))
        cases = [
            (10.0, None),
            (None, 5.0),
            (None, None),
        ]
        for shr, tre in cases:
            derived = derive_f08_from_rap_bands(
                raw_shr_percent=shr,
                raw_tre_percent=tre,
                source_year=2025,
                mask=True,
                geometry_hash="g",
                response_or_artifact_hash="h",
                applicability_status="IN_DOCUMENTED_PRODUCT_SCOPE",
                coverage_status="COVERAGE_UNQUANTIFIED",
            )
            self.assertIsNone(derived["combined_modeled_woody_cover_fraction"])
            self.assertFalse(derived["null_treated_as_zero"])

    def test_f08_neg_coverage_unquantified_not_complete(self):
        derived = derive_f08_from_rap_bands(
            raw_shr_percent=6.73,
            raw_tre_percent=0.11,
            source_year=2025,
            mask=True,
            geometry_hash="g",
            response_or_artifact_hash="h",
            applicability_status="IN_DOCUMENTED_PRODUCT_SCOPE",
            coverage_status="COVERAGE_UNQUANTIFIED",
        )
        signal = evaluate_f08_signal(derived)
        self.assertNotEqual(derived["input_quality_state"], "WOODY_CONTEXT_COMPLETE")
        self.assertNotEqual(signal["signal"], "CONTEXT_DEPENDENT")

    def test_f08_cper_reuse_fixture_values(self):
        f02 = PROFILE["factors"]["F02_HERBACEOUS_RESOURCE"]
        derived = derive_f08_reusing_f02_artifact(
            coverV3_artifact_path=COVER_V3,
            f02_factor=f02,
            geometry_hash=PROFILE["geometry_hash"],
        )
        signal = evaluate_f08_signal(derived)
        cover = json.loads(COVER_V3.read_text())
        row = cover["properties"]["cover"][1]
        # header: year, AFG, PFG, SHR, TRE, LTR, BGR
        shr_pct = row[3]
        tre_pct = row[4]
        self.assertAlmostEqual(derived["raw_rap_shr_percent"], shr_pct)
        self.assertAlmostEqual(derived["raw_rap_tre_percent"], tre_pct)
        self.assertAlmostEqual(derived["shrub_cover_fraction"], shr_pct / 100.0)
        self.assertAlmostEqual(derived["tree_cover_fraction"], tre_pct / 100.0)
        self.assertAlmostEqual(
            derived["combined_modeled_woody_cover_fraction"],
            shr_pct / 100.0 + tre_pct / 100.0,
        )
        self.assertEqual(
            derived["input_quality_state"],
            "WOODY_CONTEXT_AVAILABLE_COVERAGE_UNQUANTIFIED",
        )
        self.assertEqual(signal["signal"], "NEEDS_VERIFICATION")
        self.assertEqual(signal["ranking_effect"], "NONE")


if __name__ == "__main__":
    unittest.main()
