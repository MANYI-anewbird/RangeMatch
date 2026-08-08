"""F03 Demo Completion Gate audit checks."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from rangematch.engine import evaluate_land_profile
from rangematch.explanation import explain_match_result
from rangematch.geometry_replace import replace_geometry

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "test-data/land-profiles/land_profile_cper_001.json"
FIVE_SUMMARY = (
    ROOT / "test-data/cross-parcel-validation/f03_five_parcel_remote_collection_summary.json"
)
LIVE_PARCELS = (
    "XPV_CPER_001",
    "XPV_KONZA_001",
    "XPV_REYNOLDS_001",
    "XPV_ORDWAY_001",
    "XPV_KBS_MCSE_001",
)


class TestF03DemoCompletionGate(unittest.TestCase):
    def test_cper_f03_demo_summary_fields(self):
        profile = json.loads(PROFILE_PATH.read_text())
        f03 = profile["factors"]["F03_LIVESTOCK_WATER"]
        summary = f03["remote_evidence_summary"]
        self.assertEqual(f03["input_quality_state"], "MAPPED_CANDIDATES_ONLY")
        self.assertEqual(summary["total_mapped_candidates"], 9)
        self.assertEqual(summary["deterministically_sampled_for_remote_review"], 3)
        self.assertEqual(summary["remotely_supported"], 2)
        self.assertEqual(summary["sampled_but_still_mapped"], 1)
        self.assertEqual(summary["field_verified"], 0)
        self.assertEqual(summary["unreviewed_candidates"], 6)
        self.assertEqual(f03["field_verified_count"], 0)
        self.assertFalse(summary["synthetic_field_evidence_demo"]["part_of_cper_live_profile"])
        self.assertEqual(summary["synthetic_field_evidence_demo"]["status"], "TEST_ONLY")

        result = evaluate_land_profile(profile)
        f03_eval = result["operation_results"]["COW_CALF_OPERATION"]["factor_evaluations"][
            "F03_LIVESTOCK_WATER"
        ]
        self.assertEqual(f03_eval["signal"], "NEEDS_VERIFICATION")
        self.assertEqual(f03_eval["ranking_effect"], "NONE")
        self.assertEqual(f03_eval["input_quality_state"], "MAPPED_CANDIDATES_ONLY")
        self.assertEqual(f03_eval["field_verified_count"], 0)

        explanation = explain_match_result(result, profile)
        joined = " ".join(explanation["narrative_constraints"]).lower()
        self.assertIn("does not have verified livestock water", joined)
        self.assertIn("remotely_supported candidates are not usable", joined)
        self.assertNotIn("cper has verified livestock water", joined)

    def test_five_frozen_parcels_field_verified_zero(self):
        for parcel_id in LIVE_PARCELS:
            path = (
                ROOT
                / "test-data/cross-parcel-validation"
                / parcel_id
                / "f03_remote_pilot"
                / "remote_pilot_result.json"
            )
            payload = json.loads(path.read_text())
            self.assertEqual(payload.get("field_verified_count"), 0, msg=parcel_id)

    def test_sampling_disclosure_15_of_80(self):
        summary = json.loads(FIVE_SUMMARY.read_text())
        available = sum(p["available"] for p in summary["parcels"])
        sampled = sum(p["sampled"] for p in summary["parcels"])
        self.assertEqual(available, 80)
        self.assertEqual(sampled, 15)
        self.assertEqual(summary["field_verified_count_total"], 0)
        self.assertTrue(summary["collection_gate"]["passed"])

    def test_remote_adapters_never_field_verified_in_live_results(self):
        for parcel_id in LIVE_PARCELS:
            path = (
                ROOT
                / "test-data/cross-parcel-validation"
                / parcel_id
                / "f03_remote_pilot"
                / "remote_pilot_result.json"
            )
            payload = json.loads(path.read_text())
            for row in payload.get("candidates") or []:
                self.assertNotEqual(
                    row.get("after_remote_level"),
                    "FIELD_VERIFIED_LIVESTOCK_WATER",
                    msg=f"{parcel_id}:{row.get('candidate_id')}",
                )

    def test_geometry_replacement_requires_f03_relink(self):
        profile = json.loads(PROFILE_PATH.read_text())
        replaced = replace_geometry(
            profile,
            ROOT / "test-data/engineering_test_geometry_cper_002.geojson",
            geometry_reference="test-data/engineering_test_geometry_cper_002.geojson",
        )
        f03 = replaced["factors"]["F03_LIVESTOCK_WATER"]
        self.assertEqual(f03["geometry_replacement_status"], "EVIDENCE_INVALIDATED")
        self.assertTrue(f03.get("f03_evidence_relink_required"))
        self.assertEqual(f03.get("field_verified_count"), 0)

    def test_synthetic_demo_not_in_live_validation_stats(self):
        summary = json.loads(FIVE_SUMMARY.read_text())
        blob = json.dumps(summary)
        self.assertNotIn("SYNTHETIC_PARCEL_F03", blob)
        self.assertEqual(summary["field_verified_count_total"], 0)
        for parcel in summary["parcels"]:
            self.assertEqual(parcel.get("FIELD_VERIFIED_LIVESTOCK_WATER"), 0)
            self.assertTrue(str(parcel["parcel_id"]).startswith("XPV_"))
        demo = json.loads(
            (
                ROOT / "test-data/f03_field_evidence_demo/field_evidence_demo_result.json"
            ).read_text()
        )
        self.assertTrue(demo["field_evidence_workflow_gate"]["passed"])
        self.assertTrue(demo["live_parcel_separation"]["all_field_verified_counts_zero"])
        # Synthetic FIELD_VERIFIED outcomes must not leak into the five-parcel summary.
        self.assertGreater(demo["suite"]["field_verified_count"], 0)
        self.assertEqual(summary["field_verified_count_total"], 0)


if __name__ == "__main__":
    unittest.main()
