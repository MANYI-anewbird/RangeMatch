import json
import unittest
from copy import deepcopy
from pathlib import Path

from rangematch.engine import evaluate_land_fact, evaluate_land_profile


ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads((ROOT / "test-data/land-profiles/land_profile_cper_001.json").read_text())


class LandFactGateTests(unittest.TestCase):
    def setUp(self):
        self.fact = deepcopy(PROFILE["factors"]["F02_HERBACEOUS_RESOURCE"]["land_facts"][0])

    def test_unquantified_coverage_is_limited_context(self):
        result = evaluate_land_fact(self.fact)
        self.assertEqual(result["gate_state"], "LIMITED_CONTEXT")
        self.assertTrue(result["use_as_context"])
        self.assertFalse(result["use_as_primary_factor_evidence"])

    def test_numeric_value_does_not_override_outside_scope(self):
        self.fact["applicability"]["domain_status"] = "OUTSIDE_DOCUMENTED_PRODUCT_SCOPE"
        result = evaluate_land_fact(self.fact)
        self.assertEqual(result["gate_state"], "NEEDS_VERIFICATION")
        self.assertFalse(result["use_as_context"])

    def test_unknown_applicability_requires_verification(self):
        self.fact["applicability"]["domain_status"] = "UNKNOWN"
        self.assertEqual(evaluate_land_fact(self.fact)["reason_code"], "APPLICABILITY_UNKNOWN")

    def test_raster_adapter_does_not_imply_complete_coverage(self):
        self.fact["coverage"]["adapter_status"] = "RASTER_VERIFIED"
        result = evaluate_land_fact(self.fact)
        self.assertEqual(result["reason_code"], "COVERAGE_UNQUANTIFIED")

    def test_missing_provenance_blocks_verified_use(self):
        self.fact["provenance"]["response_or_artifact_hash"] = None
        self.assertEqual(evaluate_land_fact(self.fact)["reason_code"], "PROVENANCE_INCOMPLETE")


class VerticalSliceTests(unittest.TestCase):
    def test_cper_expected_signals(self):
        result = evaluate_land_profile(PROFILE)
        for operation in result["operation_results"].values():
            factors = operation["factor_evaluations"]
            self.assertEqual(factors["F01_TOPOGRAPHY"]["signal"], "CONTEXT_DEPENDENT")
            self.assertEqual(factors["F02_HERBACEOUS_RESOURCE"]["signal"], "NEEDS_VERIFICATION")
            self.assertEqual(factors["F03_LIVESTOCK_WATER"]["signal"], "NEEDS_VERIFICATION")
            self.assertEqual(factors["F03_LIVESTOCK_WATER"]["ranking_effect"], "NONE")
            self.assertEqual(
                factors["F04_SOIL_WETNESS_ECOLOGICAL_SITE"]["signal"], "CONTEXT_DEPENDENT"
            )
            self.assertEqual(
                factors["F04_SOIL_WETNESS_ECOLOGICAL_SITE"]["ranking_effect"], "NONE"
            )
            self.assertEqual(
                factors["F05_CLIMATE_DROUGHT_EXPOSURE"]["signal"], "CONTEXT_DEPENDENT"
            )
            self.assertEqual(
                factors["F05_CLIMATE_DROUGHT_EXPOSURE"]["ranking_effect"], "NONE"
            )
            self.assertEqual(
                factors["F05_CLIMATE_DROUGHT_EXPOSURE"]["canonical_precip_mm"], 345.74
            )
            self.assertEqual(
                factors["F06_PARCEL_CONFIGURATION"]["signal"], "CONTEXT_DEPENDENT"
            )
            self.assertEqual(
                factors["F06_PARCEL_CONFIGURATION"]["ranking_effect"], "NONE"
            )
            self.assertEqual(
                factors["F07_ROAD_AND_PHYSICAL_ACCESS"]["signal"], "CONTEXT_DEPENDENT"
            )
            self.assertEqual(
                factors["F07_ROAD_AND_PHYSICAL_ACCESS"]["ranking_effect"], "NONE"
            )
            f08 = factors["F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"]
            self.assertEqual(f08["signal"], "NEEDS_VERIFICATION")
            self.assertEqual(f08["ranking_effect"], "NONE")
            self.assertEqual(
                f08["input_quality_state"],
                "WOODY_CONTEXT_AVAILABLE_COVERAGE_UNQUANTIFIED",
            )
            self.assertEqual(f08["explanation_code"], "F08_EXPL_COVERAGE_UNQUANTIFIED")
            self.assertFalse(f08["browse_inferred"])
            self.assertFalse(f08["obstruction_inferred"])
            self.assertEqual(operation["decision_label"], "HOLD")
            self.assertIsNone(operation["ranking_position"])

    def test_no_cross_profile_ranking(self):
        result = evaluate_land_profile(PROFILE)
        self.assertFalse(result["cross_profile_comparison"]["ranking_permitted"])

    def test_llm_cannot_override(self):
        self.assertFalse(evaluate_land_profile(PROFILE)["llm_override_permitted"])

    def test_identical_inputs_produce_identical_results(self):
        self.assertEqual(evaluate_land_profile(PROFILE), evaluate_land_profile(deepcopy(PROFILE)))

    def test_missing_f02_remains_unknown(self):
        profile = deepcopy(PROFILE)
        profile["factors"]["F02_HERBACEOUS_RESOURCE"]["land_facts"] = []
        result = evaluate_land_profile(profile)
        signal = result["operation_results"]["COW_CALF_OPERATION"]["factor_evaluations"]["F02_HERBACEOUS_RESOURCE"]["signal"]
        self.assertEqual(signal, "UNKNOWN")

    def test_missing_f03_remains_unknown(self):
        profile = deepcopy(PROFILE)
        profile["factors"].pop("F03_LIVESTOCK_WATER")
        result = evaluate_land_profile(profile)
        signal = result["operation_results"]["SHEEP_GRAZING"]["factor_evaluations"]["F03_LIVESTOCK_WATER"]["signal"]
        self.assertEqual(signal, "UNKNOWN")

    def test_mapped_water_candidates_are_not_verified_systems(self):
        result = evaluate_land_profile(PROFILE)
        factor = result["operation_results"]["COW_CALF_OPERATION"]["factor_evaluations"]["F03_LIVESTOCK_WATER"]
        self.assertEqual(factor["mapped_candidate_count"], 9)
        self.assertEqual(factor["verified_livestock_water_system_count"], 0)
        self.assertEqual(factor["signal"], "NEEDS_VERIFICATION")


if __name__ == "__main__":
    unittest.main()
