"""Executable golden tests for F05 climate/drought derivation and engine wiring."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from rangematch.engine import evaluate_land_profile
from rangematch.f05_derivation import (
    classify_f05_input_quality,
    derive_f05_from_fixture_dir,
    derive_f05_parcel_facts,
    validate_canonical_precip,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "test-data/live-results/cper"
PROFILE = json.loads((ROOT / "test-data/land-profiles/land_profile_cper_001.json").read_text())
GEO_HASH = PROFILE["geometry_hash"]


class F05DerivationGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.derived = derive_f05_from_fixture_dir(FIXTURE_DIR, geometry_hash=GEO_HASH)
        cls.precip = json.loads(
            (
                FIXTURE_DIR
                / "cper_noaa_ncei_annprcp_normals_1991_2020_2026-08-07.json"
            ).read_text()
        )

    def test_canonical_noaa_complete(self):
        self.assertEqual(self.derived["input_quality_state"], "CLIMATE_CONTEXT_COMPLETE")
        self.assertEqual(self.derived["canonical_precipitation"]["value_mm"], 345.74)
        self.assertEqual(self.derived["canonical_precipitation"]["role"], "CANONICAL_LAND_FACT")
        self.assertIsNone(self.derived["canonical_precipitation"]["suitability_signal"])
        self.assertTrue(validate_canonical_precip(self.precip)["complete"])

    def test_missing_provenance_incomplete(self):
        precip = deepcopy(self.precip)
        precip["file_sha256"] = None
        self.assertFalse(validate_canonical_precip(precip)["complete"])
        state = classify_f05_input_quality(precip=precip, mireye_fields={})
        self.assertEqual(state, "CLIMATE_CONTEXT_INCOMPLETE")

    def test_missing_or_invalid_unit_incomplete(self):
        precip = deepcopy(self.precip)
        precip["unit"] = "inches_without_conversion_flag"
        self.assertFalse(validate_canonical_precip(precip)["unit_ok"])
        state = classify_f05_input_quality(precip=precip)
        self.assertEqual(state, "CLIMATE_CONTEXT_INCOMPLETE")

    def test_missing_normals_period_incomplete(self):
        precip = deepcopy(self.precip)
        precip.pop("normals_period")
        state = classify_f05_input_quality(precip=precip)
        self.assertEqual(state, "CLIMATE_CONTEXT_INCOMPLETE")

    def test_unconfirmed_coverage_incomplete(self):
        precip = deepcopy(self.precip)
        precip["parcel_coverage"]["coverage_status"] = "UNCONFIRMED"
        state = classify_f05_input_quality(precip=precip)
        self.assertEqual(state, "CLIMATE_CONTEXT_INCOMPLETE")

    def test_noaa_acis_mireye_conflict_not_averaged(self):
        comparisons = [
            {
                "source": "ACIS_GRIDDATA",
                "role": "SECONDARY_QA_OR_FALLBACK",
                "value_mm": 364.83,
                "canonical_value_mm": 345.74,
                "material_conflict": True,
                "resolution": "RETAIN_DIFFERENCE_TRIGGER_VERIFICATION",
                "averaged": False,
            }
        ]
        factor = derive_f05_parcel_facts(
            precip=self.precip,
            mireye={"fields": {}},
            geometry_hash=GEO_HASH,
            secondary_comparisons=comparisons,
        )
        self.assertEqual(factor["input_quality_state"], "CONFLICTING_SOURCES")
        self.assertEqual(factor["canonical_precipitation"]["value_mm"], 345.74)
        self.assertFalse(any(item.get("averaged") for item in factor["secondary_comparisons"]))

    def test_mireye_point_only(self):
        state = classify_f05_input_quality(
            precip=None,
            mireye_fields={"drought_category": {"value": "D3"}},
        )
        self.assertEqual(state, "POINT_CLIMATE_ONLY")

    def test_all_missing(self):
        self.assertEqual(classify_f05_input_quality(precip=None), "MISSING")


class F05EngineIntegrationTests(unittest.TestCase):
    def _f05(self, profile=None, operation="COW_CALF_OPERATION"):
        result = evaluate_land_profile(profile or PROFILE)
        return result["operation_results"][operation]["factor_evaluations"][
            "F05_CLIMATE_DROUGHT_EXPOSURE"
        ]

    def test_cper_canonical_noaa_is_context_dependent(self):
        for operation in ("COW_CALF_OPERATION", "SHEEP_GRAZING"):
            factor = self._f05(operation=operation)
            self.assertEqual(factor["signal"], "CONTEXT_DEPENDENT")
            self.assertEqual(factor["ranking_effect"], "NONE")
            self.assertEqual(factor["explanation_code"], "F05_EXPL_CONTEXT_ONLY")
            self.assertEqual(factor["canonical_precip_mm"], 345.74)
            self.assertFalse(factor["mutates_f02"])
            self.assertFalse(factor["mutates_f03"])
            self.assertFalse(factor["mutates_f04"])

    def test_missing_provenance_needs_verification(self):
        profile = deepcopy(PROFILE)
        profile["factors"]["F05_CLIMATE_DROUGHT_EXPOSURE"]["provenance"][
            "response_or_artifact_hash"
        ] = None
        factor = self._f05(profile)
        self.assertEqual(factor["signal"], "NEEDS_VERIFICATION")
        self.assertEqual(factor["explanation_code"], "F05_EXPL_INCOMPLETE")

    def test_missing_or_invalid_unit_needs_verification(self):
        profile = deepcopy(PROFILE)
        profile["factors"]["F05_CLIMATE_DROUGHT_EXPOSURE"]["canonical_precipitation"][
            "unit"
        ] = "unknown_unit"
        factor = self._f05(profile)
        self.assertEqual(factor["signal"], "NEEDS_VERIFICATION")

    def test_missing_normals_period_needs_verification(self):
        profile = deepcopy(PROFILE)
        profile["factors"]["F05_CLIMATE_DROUGHT_EXPOSURE"]["canonical_precipitation"].pop(
            "normals_period"
        )
        factor = self._f05(profile)
        self.assertEqual(factor["signal"], "NEEDS_VERIFICATION")

    def test_unconfirmed_coverage_needs_verification(self):
        profile = deepcopy(PROFILE)
        f05 = profile["factors"]["F05_CLIMATE_DROUGHT_EXPOSURE"]
        f05["parcel_coverage"]["status"] = "UNCONFIRMED"
        f05["parcel_coverage"]["detail"] = "UNCONFIRMED"
        f05["coverage"]["status"] = "UNKNOWN"
        factor = self._f05(profile)
        self.assertEqual(factor["signal"], "NEEDS_VERIFICATION")

    def test_source_conflict_needs_verification_without_averaging(self):
        profile = deepcopy(PROFILE)
        f05 = profile["factors"]["F05_CLIMATE_DROUGHT_EXPOSURE"]
        f05["secondary_comparisons"] = [
            {
                "source": "ACIS_GRIDDATA",
                "value_mm": 364.83,
                "canonical_value_mm": 345.74,
                "material_conflict": True,
                "averaged": False,
            }
        ]
        f05["source_conflicts"] = list(f05["secondary_comparisons"])
        factor = self._f05(profile)
        self.assertEqual(factor["signal"], "NEEDS_VERIFICATION")
        self.assertEqual(factor["explanation_code"], "F05_EXPL_CONFLICT")
        self.assertEqual(factor["canonical_precip_mm"], 345.74)

    def test_mireye_point_only_needs_verification(self):
        profile = deepcopy(PROFILE)
        profile["factors"]["F05_CLIMATE_DROUGHT_EXPOSURE"] = {
            "input_quality_state": "POINT_CLIMATE_ONLY",
            "mireye_point_qa": PROFILE["factors"]["F05_CLIMATE_DROUGHT_EXPOSURE"][
                "mireye_point_qa"
            ],
        }
        factor = self._f05(profile)
        self.assertEqual(factor["signal"], "NEEDS_VERIFICATION")
        self.assertEqual(factor["explanation_code"], "F05_EXPL_POINT_NOT_PARCEL_PRECIP")

    def test_all_missing_unknown(self):
        profile = deepcopy(PROFILE)
        profile["factors"].pop("F05_CLIMATE_DROUGHT_EXPOSURE")
        factor = self._f05(profile)
        self.assertEqual(factor["signal"], "UNKNOWN")
        self.assertEqual(factor["explanation_code"], "F05_EXPL_MISSING")

    def test_identical_inputs_identical_results(self):
        self.assertEqual(
            evaluate_land_profile(PROFILE),
            evaluate_land_profile(deepcopy(PROFILE)),
        )

    def test_cow_sheep_remain_peer_hold(self):
        result = evaluate_land_profile(PROFILE)
        cow = result["operation_results"]["COW_CALF_OPERATION"]
        sheep = result["operation_results"]["SHEEP_GRAZING"]
        self.assertEqual(cow["decision_label"], sheep["decision_label"])
        self.assertEqual(cow["decision_label"], "HOLD")
        self.assertIsNone(cow["ranking_position"])
        self.assertIsNone(sheep["ranking_position"])
        self.assertEqual(
            cow["factor_evaluations"]["F05_CLIMATE_DROUGHT_EXPOSURE"],
            sheep["factor_evaluations"]["F05_CLIMATE_DROUGHT_EXPOSURE"],
        )
        self.assertFalse(result["cross_profile_comparison"]["ranking_permitted"])

    def test_f05_does_not_mutate_f02_f03_f04(self):
        result = evaluate_land_profile(PROFILE)
        factors = result["operation_results"]["COW_CALF_OPERATION"]["factor_evaluations"]
        self.assertEqual(factors["F02_HERBACEOUS_RESOURCE"]["signal"], "NEEDS_VERIFICATION")
        self.assertEqual(factors["F03_LIVESTOCK_WATER"]["signal"], "NEEDS_VERIFICATION")
        self.assertEqual(
            factors["F04_SOIL_WETNESS_ECOLOGICAL_SITE"]["signal"], "CONTEXT_DEPENDENT"
        )
        self.assertEqual(factors["F05_CLIMATE_DROUGHT_EXPOSURE"]["signal"], "CONTEXT_DEPENDENT")

    def test_prohibited_precip_proxy(self):
        profile = deepcopy(PROFILE)
        profile["factors"]["F05_CLIMATE_DROUGHT_EXPOSURE"]["input_quality_state"] = (
            "PROHIBITED_PRECIP_PROXY"
        )
        factor = self._f05(profile)
        self.assertEqual(factor["signal"], "NEEDS_VERIFICATION")
        self.assertEqual(factor["explanation_code"], "F05_EXPL_PRECIP_PROXY_PROHIBITED")


if __name__ == "__main__":
    unittest.main()
