"""Offline replay tests for shared F02/F08 RAP production adapter."""

import json
import unittest
from pathlib import Path

from rangematch.f02_rap_adapter import collect_f02_f08_from_rap

ROOT = Path(__file__).resolve().parents[1]


class F02RAPAdapterTests(unittest.TestCase):
    def test_single_cover_artifact_shared_with_f08(self):
        geometry = json.loads((ROOT / "test-data/engineering_test_geometry_cper_001.geojson").read_text())
        cover = json.loads((ROOT / "test-data/live-results/cper/rap_coverV3_2025.json").read_text())
        production = json.loads((ROOT / "test-data/live-results/cper/rap_productionV3_2025.json").read_text())
        calls = []

        def post(url, payload, timeout):
            calls.append(url)
            return cover if url.endswith("coverV3") else production

        result = collect_f02_f08_from_rap(
            geometry=geometry, geometry_id="cper", geometry_hash="a" * 64,
            applicability_status="IN_DOCUMENTED_PRODUCT_SCOPE",
            post_json=post,
        )
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["cover_request_count"], 1)
        self.assertFalse(result["duplicate_coverV3_fetch"])
        f02 = result["factors"]["F02_HERBACEOUS_RESOURCE"]
        f08 = result["factors"]["F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"]
        cover_fact = f02["land_facts"][0]
        self.assertEqual(
            cover_fact["provenance"]["response_or_artifact_hash"],
            f08["provenance"]["response_or_artifact_hash"],
        )
        self.assertEqual(f08["shrub_cover_fraction"], 0.06727234043361567)
        self.assertEqual(f08["tree_cover_fraction"], 0.0010557150211526738)
        self.assertEqual(f08["ranking_effect"], "NONE")
        self.assertNotIn("browse_availability", f08)

    def test_successful_masked_live_response_is_in_scope_but_coverage_unquantified(self):
        geometry = json.loads((ROOT / "test-data/engineering_test_geometry_cper_001.geojson").read_text())
        cover = json.loads((ROOT / "test-data/live-results/cper/rap_coverV3_2025.json").read_text())
        production = json.loads((ROOT / "test-data/live-results/cper/rap_productionV3_2025.json").read_text())
        result = collect_f02_f08_from_rap(
            geometry=geometry, geometry_id="cper", geometry_hash="b" * 64,
            post_json=lambda url, _payload, _timeout: cover if url.endswith("coverV3") else production,
        )
        f02 = result["factors"]["F02_HERBACEOUS_RESOURCE"]
        f08 = result["factors"]["F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"]
        self.assertEqual(
            f02["land_facts"][0]["applicability"]["domain_status"],
            "IN_DOCUMENTED_PRODUCT_SCOPE",
        )
        self.assertEqual(f02["input_quality_state"], "COVERAGE_UNQUANTIFIED")
        self.assertEqual(
            f08["input_quality_state"],
            "WOODY_CONTEXT_AVAILABLE_COVERAGE_UNQUANTIFIED",
        )
        self.assertIsNotNone(f02["land_facts"][0]["coverage"]["requested_area_m2"])

    def test_explicit_unknown_applicability_remains_fail_closed(self):
        geometry = json.loads((ROOT / "test-data/engineering_test_geometry_cper_001.geojson").read_text())
        cover = json.loads((ROOT / "test-data/live-results/cper/rap_coverV3_2025.json").read_text())
        production = json.loads((ROOT / "test-data/live-results/cper/rap_productionV3_2025.json").read_text())
        result = collect_f02_f08_from_rap(
            geometry=geometry,
            geometry_id="cper",
            geometry_hash="c" * 64,
            applicability_status="UNKNOWN",
            post_json=lambda url, _payload, _timeout: cover if url.endswith("coverV3") else production,
        )
        self.assertEqual(
            result["factors"]["F02_HERBACEOUS_RESOURCE"]["input_quality_state"],
            "RAP_OUTSIDE_OR_UNKNOWN_APPLICABILITY",
        )


if __name__ == "__main__":
    unittest.main()
