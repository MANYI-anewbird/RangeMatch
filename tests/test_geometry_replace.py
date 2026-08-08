"""Tests for minimal geometry replacement reusability path."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rangematch.engine import evaluate_land_profile
from rangematch.geometry_replace import geometry_file_sha256, replace_geometry


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "test-data/land-profiles/land_profile_cper_001.json"
GEOMETRY_001 = ROOT / "test-data/engineering_test_geometry_cper_001.geojson"
GEOMETRY_002 = ROOT / "test-data/engineering_test_geometry_cper_002.geojson"


class GeometryReplaceTests(unittest.TestCase):
    def test_replacement_changes_hashes_and_invalidates_factors(self):
        original = json.loads(PROFILE_PATH.read_text())
        original_result = evaluate_land_profile(original)
        replaced = replace_geometry(
            original,
            GEOMETRY_002,
            geometry_reference="test-data/engineering_test_geometry_cper_002.geojson",
        )
        replaced_result = evaluate_land_profile(replaced)

        self.assertEqual(replaced["geometry_id"], "ENGINEERING_TEST_GEOMETRY_CPER_002")
        self.assertEqual(
            replaced["geometry_hash"], geometry_file_sha256(GEOMETRY_002)
        )
        self.assertNotEqual(replaced["geometry_hash"], original.get("geometry_hash"))
        self.assertNotEqual(
            replaced_result["input_sha256"], original_result["input_sha256"]
        )
        self.assertIn("F05_CLIMATE_DROUGHT_EXPOSURE", original["factors"])
        self.assertIn(
            "canonical_precipitation",
            original["factors"]["F05_CLIMATE_DROUGHT_EXPOSURE"],
        )
        for factor_id, factor in replaced["factors"].items():
            self.assertEqual(factor["input_quality_state"], "MISSING", factor_id)
            self.assertEqual(factor["geometry_replacement_status"], "EVIDENCE_INVALIDATED")
        f05_replaced = replaced["factors"]["F05_CLIMATE_DROUGHT_EXPOSURE"]
        self.assertNotIn("canonical_precipitation", f05_replaced)
        self.assertNotIn("mireye_point_qa", f05_replaced)
        for operation in replaced_result["operation_results"].values():
            self.assertEqual(operation["decision_label"], "HOLD")
            for factor_id, evaluation in operation["factor_evaluations"].items():
                if factor_id == "F02_HERBACEOUS_RESOURCE":
                    self.assertEqual(evaluation["signal"], "UNKNOWN")
                else:
                    self.assertIn(evaluation["signal"], {"UNKNOWN", "NEEDS_VERIFICATION"})
            f05_eval = operation["factor_evaluations"]["F05_CLIMATE_DROUGHT_EXPOSURE"]
            self.assertEqual(f05_eval["signal"], "UNKNOWN")
            self.assertEqual(f05_eval["explanation_code"], "F05_EXPL_MISSING")
            self.assertIsNone(f05_eval.get("canonical_precip_mm"))
        self.assertTrue(
            any("F01–F08" in item for item in replaced.get("unknowns") or [])
        )

    def test_original_geometry_hash_matches_file(self):
        # The stored CPER hash is the locked engineering geometry hash used across
        # live-gate fixtures; replacement must still diverge from it.
        self.assertTrue(PROFILE_PATH.read_text())
        self.assertNotEqual(
            geometry_file_sha256(GEOMETRY_001),
            geometry_file_sha256(GEOMETRY_002),
        )

    def test_cli_replace_geometry_subprocess(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "replaced.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "rangematch.cli",
                    "replace-geometry",
                    str(PROFILE_PATH),
                    str(GEOMETRY_002),
                    "--output",
                    str(output),
                    "--geometry-reference",
                    "test-data/engineering_test_geometry_cper_002.geojson",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            saved = json.loads(output.read_text())
            self.assertEqual(payload["geometry_id"], saved["geometry_id"])
            self.assertTrue(payload["factor_evidence_invalidated"])
            self.assertEqual(
                saved["geometry_reference"],
                "test-data/engineering_test_geometry_cper_002.geojson",
            )


if __name__ == "__main__":
    unittest.main()
