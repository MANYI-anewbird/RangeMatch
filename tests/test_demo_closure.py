"""Tests for constrained explanation and demo Factor closure."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from rangematch.demo_report import build_demo_closure_payload, write_demo_closure
from rangematch.engine import evaluate_land_profile
from rangematch.explanation import explain_match_result


ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads((ROOT / "test-data/land-profiles/land_profile_cper_001.json").read_text())
PROFILE_PATH = ROOT / "test-data/land-profiles/land_profile_cper_001.json"


class ExplanationTests(unittest.TestCase):
    def test_explanation_is_bound_to_match_result(self):
        result = evaluate_land_profile(PROFILE)
        explanation = explain_match_result(result, PROFILE)
        self.assertEqual(explanation["bound_to_input_sha256"], result["input_sha256"])
        self.assertFalse(explanation["llm_override_permitted"])
        self.assertFalse(explanation["may_alter_decision_labels"])
        self.assertFalse(explanation["may_invent_scores_or_thresholds"])
        self.assertEqual(len(explanation["operation_summaries"]), 2)

    def test_explanation_refuses_override_flag(self):
        result = evaluate_land_profile(PROFILE)
        result["llm_override_permitted"] = True
        with self.assertRaises(ValueError):
            explain_match_result(result, PROFILE)


class DemoClosureTests(unittest.TestCase):
    def test_demo_payload_has_required_sections(self):
        result = evaluate_land_profile(PROFILE)
        payload = build_demo_closure_payload(PROFILE, result)
        self.assertEqual(
            payload["sections"],
            [
                "Parcel Summary",
                "Factor Evidence",
                "Operation Comparison",
                "Unknowns",
                "Diligence Actions",
                "Source Trace",
            ],
        )
        self.assertEqual(len(payload["factor_evidence"]), 8)
        self.assertFalse(payload["cross_profile_comparison"]["ranking_permitted"])
        labels = {item["decision_label"] for item in payload["operation_comparison"]}
        self.assertEqual(labels, {"HOLD"})

    def test_f02_factor_row_includes_limitations_and_unknowns(self):
        payload = build_demo_closure_payload(PROFILE)
        f02 = next(
            item
            for item in payload["factor_evidence"]
            if item["factor_id"] == "F02_HERBACEOUS_RESOURCE"
        )
        self.assertTrue(f02["limitations"])
        self.assertTrue(f02["unknowns"])
        joined_limits = " ".join(f02["limitations"]).lower()
        joined_unknowns = " ".join(f02["unknowns"]).lower()
        self.assertIn("coverage_unquantified", joined_limits + " " + f02["coverage"].lower())
        self.assertIn("palatability", joined_unknowns)
        self.assertIn("nutritive", joined_unknowns)
        f01 = next(
            item
            for item in payload["factor_evidence"]
            if item["factor_id"] == "F01_TOPOGRAPHY"
        )
        html = __import__("rangematch.demo_report", fromlist=["render_demo_html"]).render_demo_html(
            payload
        )
        if not f01["unknowns"]:
            self.assertIn("No additional Factor-specific unknowns recorded", html)
        self.assertNotIn(">None recorded<", html)

    def test_demo_artifacts_are_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "profile.json"
            profile_path.write_text(json.dumps(PROFILE))
            html_a = Path(tmp) / "a.html"
            json_a = Path(tmp) / "a.json"
            html_b = Path(tmp) / "b.html"
            json_b = Path(tmp) / "b.json"
            write_demo_closure(profile_path, html_output=html_a, json_output=json_a)
            write_demo_closure(profile_path, html_output=html_b, json_output=json_b)
            self.assertEqual(json_a.read_text(), json_b.read_text())
            self.assertEqual(html_a.read_text(), html_b.read_text())
            html = html_a.read_text()
            self.assertIn("Parcel Summary", html)
            self.assertIn("F04_SOIL_WETNESS_ECOLOGICAL_SITE", html)
            self.assertIn("HOLD does not mean the land is unsuitable", html)
            self.assertIn("not a positive suitability score", html.lower())
            self.assertNotIn("numeric suitability score", html.lower())

    def test_missing_factor_still_renders(self):
        profile = deepcopy(PROFILE)
        profile["factors"].pop("F04_SOIL_WETNESS_ECOLOGICAL_SITE")
        payload = build_demo_closure_payload(profile)
        signals = {
            item["factor_id"]: item["signal"] for item in payload["factor_evidence"]
        }
        self.assertEqual(signals["F04_SOIL_WETNESS_ECOLOGICAL_SITE"], "UNKNOWN")


class CliSubprocessTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "rangematch.cli", *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_documented_demo_closure_command_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            html_output = Path(tmp) / "demo.html"
            json_output = Path(tmp) / "demo.json"
            completed = self._run(
                "demo-closure",
                str(PROFILE_PATH),
                "--html-output",
                str(html_output),
                "--json-output",
                str(json_output),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["demo_closure_version"], "0.1.0")
            self.assertIn("Parcel Summary", payload["sections"])
            self.assertTrue(html_output.exists())
            self.assertTrue(json_output.exists())
            self.assertIn("F04_SOIL_WETNESS_ECOLOGICAL_SITE", html_output.read_text())

    def test_evaluate_subcommand_and_legacy_bare_profile(self):
        evaluate = self._run("evaluate", str(PROFILE_PATH))
        self.assertEqual(evaluate.returncode, 0, evaluate.stderr)
        evaluate_payload = json.loads(evaluate.stdout)
        self.assertEqual(
            evaluate_payload["operation_results"]["COW_CALF_OPERATION"]["decision_label"],
            "HOLD",
        )

        legacy = self._run(str(PROFILE_PATH))
        self.assertEqual(legacy.returncode, 0, legacy.stderr)
        legacy_payload = json.loads(legacy.stdout)
        self.assertEqual(legacy_payload["input_sha256"], evaluate_payload["input_sha256"])


if __name__ == "__main__":
    unittest.main()
