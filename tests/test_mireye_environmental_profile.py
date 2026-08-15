"""Phase 1: Mireye cattle-environment manifest, Profile schema, semantics gates."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from rangematch.mireye_environmental_profile import (
    MireyeEnvironmentalProfileError,
    buyer_evidence_rows,
    compute_manifest_hash,
    evaluate_catalog_drift,
    load_field_manifest,
    load_pinned_catalog,
    project_mireye_environmental_profile,
    resolve_spatial_semantics,
    validate_mireye_environmental_profile,
)

REPO = Path(__file__).resolve().parents[1]
NAMBE_PROFILE = (
    REPO
    / "test-data"
    / "mireye-environmental-profile"
    / "nambe_mireye_environmental_profile.json"
)
NAMBE_FIELDS = (
    REPO
    / "test-data"
    / "mireye-environmental-profile"
    / "nambe_mireye_field_values.json"
)


class ManifestAndDriftTests(unittest.TestCase):
    def test_manifest_hash_stable_and_self_consistent(self) -> None:
        manifest = load_field_manifest()
        self.assertEqual(manifest["manifest_hash"], compute_manifest_hash(manifest))
        self.assertEqual(manifest["catalog_ref"]["version"], "0.14.0")
        self.assertGreaterEqual(len(manifest["fields"]), 20)
        self.assertTrue(any(f["expected_spatial_semantics"] == "PARCEL" for f in manifest["fields"]))
        self.assertTrue(any(f["expected_spatial_semantics"] == "POINT" for f in manifest["fields"]))
        self.assertTrue(any(f["expected_spatial_semantics"] == "CONTEXT" for f in manifest["fields"]))

    def test_pinned_catalog_compatible(self) -> None:
        result = evaluate_catalog_drift(load_pinned_catalog())
        self.assertTrue(result["compatible"])
        self.assertFalse(result["fail_closed"])
        self.assertEqual(result["missing_fields"], [])

    def test_major_version_drift_fails_closed(self) -> None:
        catalog = load_pinned_catalog()
        catalog = copy.deepcopy(catalog)
        catalog["version"] = "1.0.0"
        result = evaluate_catalog_drift(catalog)
        self.assertTrue(result["fail_closed"])
        self.assertFalse(result["compatible"])
        self.assertTrue(any("major_version_drift" in r for r in result["reasons"]))

    def test_missing_required_field_fails_closed(self) -> None:
        catalog = copy.deepcopy(load_pinned_catalog())
        catalog["fields"] = [f for f in catalog["fields"] if f.get("name") != "elevation"]
        result = evaluate_catalog_drift(catalog)
        self.assertTrue(result["fail_closed"])
        self.assertIn("elevation", result["missing_fields"])


class SemanticsGateTests(unittest.TestCase):
    def test_point_cannot_promote_to_parcel(self) -> None:
        effective, reason = resolve_spatial_semantics(
            expected="PARCEL", returned="POINT"
        )
        self.assertEqual(effective, "POINT")
        self.assertIsNotNone(reason)
        self.assertIn("refused_promotion", str(reason))

    def test_unexpected_parcel_claim_rejected(self) -> None:
        effective, reason = resolve_spatial_semantics(
            expected="POINT", returned="PARCEL"
        )
        self.assertEqual(effective, "POINT")
        self.assertIsNotNone(reason)
        self.assertIn("rejected_unexpected_parcel_claim", str(reason))


class ProfileProjectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle = json.loads(NAMBE_FIELDS.read_text(encoding="utf-8"))
        self.parcel_ref = self.bundle["parcel_ref"]
        self.fields = self.bundle["fields"]
        self.fetched_at = self.bundle["fetched_at"]

    def test_nambe_fixture_is_schema_valid_and_non_empty(self) -> None:
        profile = json.loads(NAMBE_PROFILE.read_text(encoding="utf-8"))
        validate_mireye_environmental_profile(profile)
        self.assertGreater(profile["coverage_summary"]["retrieved_field_count"], 0)
        self.assertEqual(
            profile["coverage_summary"]["requested_field_count"],
            len(load_field_manifest()["fields"]),
        )
        for obs in profile["observations"]:
            if obs["status"] not in {"RETRIEVED", "PARTIAL"}:
                continue
            self.assertEqual(obs["provider"], "MIREYE")
            self.assertTrue(obs.get("source_name"))
            self.assertIn(obs["status"], {"RETRIEVED", "PARTIAL"})
            self.assertIn(obs["spatial_semantics"], {"POINT", "PARCEL", "CONTEXT"})

    def test_projector_reproduces_nambe_profile_shape(self) -> None:
        profile = project_mireye_environmental_profile(
            run_id="nambe_mireye_environmental_profile_phase1",
            parcel_ref=self.parcel_ref,
            field_values=self.fields,
            fetched_at=self.fetched_at,
            built_at=self.fetched_at,
        )
        self.assertEqual(profile["schema_version"], "mireye_environmental_profile@1.0.0")
        self.assertGreater(profile["coverage_summary"]["retrieved_field_count"], 0)
        self.assertEqual(profile["coverage_summary"]["parcel_count"], 2)
        canonical = [
            o["field_id"]
            for o in profile["observations"]
            if o["canonical_for_parcel_facts"]
        ]
        self.assertEqual(
            set(canonical),
            {"wetland_fraction_of_parcel", "wetland_acres_on_parcel"},
        )
        pointish = [
            o
            for o in profile["observations"]
            if o["spatial_semantics"] in {"POINT", "CONTEXT"} and o["status"] == "RETRIEVED"
        ]
        self.assertTrue(pointish)
        self.assertTrue(all(o["canonical_for_parcel_facts"] is False for o in pointish))

    def test_null_values_are_missing_not_buyer_rows(self) -> None:
        fields = copy.deepcopy(self.fields)
        fields["elevation"] = {"value": None}
        profile = project_mireye_environmental_profile(
            run_id="null_elevation",
            parcel_ref=self.parcel_ref,
            field_values=fields,
            fetched_at=self.fetched_at,
        )
        elev = next(o for o in profile["observations"] if o["field_id"] == "elevation")
        self.assertEqual(elev["status"], "MISSING")
        self.assertIsNone(elev["value"])
        buyer_ids = {r["field_id"] for r in buyer_evidence_rows(profile)}
        self.assertNotIn("elevation", buyer_ids)

    def test_point_claiming_parcel_is_rejected(self) -> None:
        fields = copy.deepcopy(self.fields)
        fields["elevation"] = {
            "value": 100.0,
            "spatial_semantics": "PARCEL",
            "geometry_hash": self.parcel_ref["geometry_hash"],
        }
        profile = project_mireye_environmental_profile(
            run_id="bad_elevation_parcel_claim",
            parcel_ref=self.parcel_ref,
            field_values=fields,
            fetched_at=self.fetched_at,
        )
        elev = next(o for o in profile["observations"] if o["field_id"] == "elevation")
        self.assertEqual(elev["status"], "REJECTED_BY_SEMANTICS_GATE")
        self.assertFalse(elev["canonical_for_parcel_facts"])
        self.assertNotIn("elevation", {r["field_id"] for r in buyer_evidence_rows(profile)})

    def test_parcel_field_with_wrong_geometry_hash_not_canonical(self) -> None:
        fields = copy.deepcopy(self.fields)
        fields["wetland_fraction_of_parcel"] = {
            "value": 0.1,
            "spatial_semantics": "PARCEL",
            "geometry_hash": "0" * 64,
            "source": "USFWS_NWI",
        }
        profile = project_mireye_environmental_profile(
            run_id="wrong_geom_parcel_field",
            parcel_ref=self.parcel_ref,
            field_values=fields,
            fetched_at=self.fetched_at,
        )
        obs = next(
            o
            for o in profile["observations"]
            if o["field_id"] == "wetland_fraction_of_parcel"
        )
        self.assertEqual(obs["status"], "RETRIEVED")
        self.assertFalse(obs["canonical_for_parcel_facts"])

    def test_coverage_counts_are_dynamic_not_constants(self) -> None:
        full = project_mireye_environmental_profile(
            run_id="full",
            parcel_ref=self.parcel_ref,
            field_values=self.fields,
            fetched_at=self.fetched_at,
        )
        sparse_fields = {
            "elevation": self.fields["elevation"],
            "slope_degrees": self.fields["slope_degrees"],
        }
        sparse = project_mireye_environmental_profile(
            run_id="sparse",
            parcel_ref=self.parcel_ref,
            field_values=sparse_fields,
            fetched_at=self.fetched_at,
        )
        self.assertNotEqual(
            full["coverage_summary"]["retrieved_field_count"],
            sparse["coverage_summary"]["retrieved_field_count"],
        )
        self.assertEqual(sparse["coverage_summary"]["retrieved_field_count"], 2)

    def test_unconfirmed_parcel_fails_closed(self) -> None:
        with self.assertRaises(MireyeEnvironmentalProfileError) as ctx:
            project_mireye_environmental_profile(
                run_id="unconfirmed",
                parcel_ref={
                    "parcel_resolution_id": "x",
                    "geometry_hash": "y",
                    "confirmed": False,
                },
                field_values={},
            )
        self.assertEqual(ctx.exception.code, "parcel_not_confirmed")


if __name__ == "__main__":
    unittest.main()
