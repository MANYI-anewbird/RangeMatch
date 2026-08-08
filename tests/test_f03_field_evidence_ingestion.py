"""Tests for F03 field/operator evidence ingestion workflow (synthetic only)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from rangematch.f03_field_evidence import (
    EVIDENCE_USE_LIMIT_TEST_ONLY,
    FIXTURE_TYPE_SYNTHETIC,
    LIVE_PARCEL_IDS,
    factor_input_quality_from_ingestion,
    ingest_field_evidence_package,
    validate_evidence_package,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "test-data/f03_field_evidence_fixtures"
LIVE_REMOTE_ROOT = ROOT / "test-data/cross-parcel-validation"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


class TestF03FieldEvidenceIngestion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (FIXTURE_DIR / "manifest.json").exists():
            import runpy

            runpy.run_path(str(ROOT / "scripts/build_f03_field_evidence_fixtures.py"))

    def test_fixtures_are_synthetic_test_only(self):
        manifest = load_fixture("manifest.json")
        self.assertEqual(manifest["fixture_type"], FIXTURE_TYPE_SYNTHETIC)
        self.assertEqual(manifest["evidence_use_limit"], EVIDENCE_USE_LIMIT_TEST_ONLY)
        self.assertFalse(manifest["live_parcels_touched"])
        for name in manifest["fixtures"]:
            if name == "manifest.json":
                continue
            pkg = load_fixture(name)
            self.assertEqual(pkg["fixture_type"], FIXTURE_TYPE_SYNTHETIC)
            self.assertEqual(pkg["evidence_use_limit"], EVIDENCE_USE_LIMIT_TEST_ONLY)
            self.assertNotIn(pkg["parcel_context"]["parcel_id"], LIVE_PARCEL_IDS)

    def test_valid_field_verified(self):
        outcome = ingest_field_evidence_package(
            load_fixture("valid_field_verified_livestock_water.json")
        )
        self.assertTrue(outcome["accepted"])
        self.assertEqual(
            outcome["verification_level"], "FIELD_VERIFIED_LIVESTOCK_WATER"
        )
        self.assertEqual(
            outcome["factor_input_quality_state"], "VERIFIED_WATER_SYSTEM_CONTEXT"
        )
        self.assertFalse(outcome["wrote_to_live_parcel_profile"])

    def test_physical_source_unverified_system(self):
        outcome = ingest_field_evidence_package(
            load_fixture("physical_source_unverified_system.json")
        )
        self.assertEqual(
            outcome["verification_level"], "FIELD_VERIFIED_LIVESTOCK_WATER"
        )
        self.assertEqual(
            outcome["factor_input_quality_state"], "PHYSICAL_SOURCE_UNVERIFIED_SYSTEM"
        )

    def test_verified_water_system_context(self):
        outcome = ingest_field_evidence_package(
            load_fixture("verified_water_system_context.json")
        )
        self.assertEqual(
            outcome["verification_level"], "FIELD_VERIFIED_LIVESTOCK_WATER"
        )
        self.assertEqual(
            outcome["factor_input_quality_state"], "VERIFIED_WATER_SYSTEM_CONTEXT"
        )

    def test_conflicting_sources(self):
        outcome = ingest_field_evidence_package(load_fixture("conflicting_sources.json"))
        self.assertIn("CONFLICTING_SOURCES", outcome["reason_codes"])
        self.assertEqual(outcome["factor_input_quality_state"], "CONFLICTING_SOURCES")
        self.assertNotEqual(
            outcome["verification_level"], "FIELD_VERIFIED_LIVESTOCK_WATER"
        )

    def test_missing_legal_access_blocks_field_verified(self):
        outcome = ingest_field_evidence_package(
            load_fixture("missing_legal_access.json")
        )
        self.assertNotEqual(
            outcome["verification_level"], "FIELD_VERIFIED_LIVESTOCK_WATER"
        )
        self.assertIn("LEGAL_ACCESS_UNRESOLVED", outcome["reason_codes"])

    def test_missing_capacity_rationale_rejected(self):
        pkg = load_fixture("missing_capacity_rationale.json")
        validation = validate_evidence_package(pkg)
        self.assertFalse(validation["ok"])
        self.assertIn("capacity.unknown_rationale_missing", validation["blocking_issues"])
        outcome = ingest_field_evidence_package(pkg)
        self.assertFalse(outcome["accepted"])
        self.assertNotEqual(
            outcome["verification_level"], "FIELD_VERIFIED_LIVESTOCK_WATER"
        )

    def test_invalid_evidence_hash_rejected(self):
        pkg = load_fixture("invalid_evidence_hash.json")
        validation = validate_evidence_package(pkg)
        self.assertFalse(validation["ok"])
        self.assertTrue(
            any("hash" in issue for issue in validation["blocking_issues"])
        )
        outcome = ingest_field_evidence_package(pkg)
        self.assertFalse(outcome["accepted"])

    def test_stale_evidence_remains_visible_as_limitation(self):
        outcome = ingest_field_evidence_package(load_fixture("stale_evidence.json"))
        self.assertEqual(
            outcome["verification_level"], "FIELD_VERIFIED_LIVESTOCK_WATER"
        )
        self.assertTrue(outcome["freshness"]["stale"])
        self.assertTrue(
            any("stale" in str(x).lower() for x in outcome["limitations"])
        )
        self.assertIn("STALE_EVIDENCE_RECORDED_AS_LIMITATION", outcome["reason_codes"])

    def test_geometry_mismatch_requires_relink(self):
        outcome = ingest_field_evidence_package(load_fixture("geometry_mismatch.json"))
        self.assertIn("GEOMETRY_MISMATCH_REQUIRES_RELINK", outcome["reason_codes"])
        self.assertNotEqual(
            outcome["verification_level"], "FIELD_VERIFIED_LIVESTOCK_WATER"
        )

    def test_reviewed_equivalent_pathway(self):
        outcome = ingest_field_evidence_package(
            load_fixture("reviewed_equivalent_field_verified.json")
        )
        self.assertEqual(outcome["evidence_class"], "REVIEWED_EQUIVALENT")
        self.assertEqual(
            outcome["verification_level"], "FIELD_VERIFIED_LIVESTOCK_WATER"
        )

    def test_mixed_requires_qualified_field_basis(self):
        outcome = ingest_field_evidence_package(
            load_fixture("mixed_with_qualified_field_basis.json")
        )
        self.assertEqual(
            outcome["verification_level"], "FIELD_VERIFIED_LIVESTOCK_WATER"
        )

        broken = load_fixture("mixed_with_qualified_field_basis.json")
        broken["dimensions"]["physical_presence"].pop("qualified_field_basis", None)
        broken["qualified_field_basis_required"] = True
        outcome_bad = ingest_field_evidence_package(broken)
        self.assertNotEqual(
            outcome_bad["verification_level"], "FIELD_VERIFIED_LIVESTOCK_WATER"
        )

    def test_mapped_to_field_verified_jump_prohibited(self):
        outcome = ingest_field_evidence_package(
            load_fixture("mapped_to_field_verified_jump_rejected.json")
        )
        self.assertEqual(outcome["verification_level"], "MAPPED_CANDIDATE")
        self.assertIn("SKIP_REMOTELY_SUPPORTED_PROHIBITED", outcome["reason_codes"])

    def test_live_parcel_write_prohibited(self):
        pkg = load_fixture("valid_field_verified_livestock_water.json")
        pkg["parcel_context"]["parcel_id"] = "XPV_CPER_001"
        outcome = ingest_field_evidence_package(pkg)
        self.assertIn("LIVE_PARCEL_WRITE_PROHIBITED", outcome["reason_codes"])
        self.assertFalse(outcome["wrote_to_live_parcel_profile"])
        self.assertNotEqual(
            outcome["verification_level"], "FIELD_VERIFIED_LIVESTOCK_WATER"
        )

    def test_unknown_water_quality_requires_diligence(self):
        pkg = load_fixture("physical_source_unverified_system.json")
        pkg["dimensions"]["capacity_and_quality"]["water_quality"] = {
            "status": "unknown",
            "diligence_required": False,
            "evidence_source_ids": [],
        }
        validation = validate_evidence_package(pkg)
        self.assertFalse(validation["ok"])
        self.assertIn(
            "water_quality.diligence_required_must_be_true_when_unknown",
            validation["blocking_issues"],
        )

    def test_factor_mapping_helpers(self):
        self.assertEqual(
            factor_input_quality_from_ingestion(
                verification_levels=["FIELD_VERIFIED_LIVESTOCK_WATER"],
                has_conflict=True,
            ),
            "CONFLICTING_SOURCES",
        )

    def test_live_remote_pilots_remain_field_verified_zero(self):
        for parcel_id in sorted(LIVE_PARCEL_IDS):
            path = (
                LIVE_REMOTE_ROOT
                / parcel_id
                / "f03_remote_pilot"
                / "remote_pilot_result.json"
            )
            self.assertTrue(path.exists(), msg=f"missing {path}")
            payload = json.loads(path.read_text())
            self.assertEqual(payload.get("field_verified_count"), 0)
            self.assertFalse(payload.get("field_verified_manufactured", False))

    def test_no_ranking_or_suitability(self):
        outcome = ingest_field_evidence_package(
            load_fixture("valid_field_verified_livestock_water.json")
        )
        self.assertEqual(outcome["ranking_effect"], "NONE")
        self.assertFalse(outcome["suitability_thresholds_added"])
        self.assertFalse(outcome["cow_sheep_ranking_added"])


if __name__ == "__main__":
    unittest.main()
