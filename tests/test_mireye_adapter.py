"""Offline tests for Unified Mireye Context Adapter."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from rangematch.mireye_adapter import (
    ADAPTER_ID,
    ADAPTER_VERSION,
    CONTEXT_HAZARD,
    CONTEXT_LAND,
    CONTEXT_PROPERTY,
    MireyeAdapterError,
    assert_no_credentials,
    build_factor_usage_refs,
    collect_live_mireye_contexts,
    normalize_from_fixture,
    normalize_mireye_context,
    sanitize_for_storage,
)


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "test-data/mireye-normalized/raw"
NORM = ROOT / "test-data/mireye-normalized/normalized"
LOC = {"lat": 40.825, "lng": -104.7625}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _norm(context_type: str, name: str):
    return normalize_from_fixture(
        context_type=context_type,
        raw_path=RAW / name,
        requested_location=LOC,
        point_role="PARCEL_CENTROID_QA",
        parcel_geometry_hash="fixture_geom_hash_cper_001",
        api_base_url="https://api.mireye.com",
    )


class MireyeAdapterOfflineTests(unittest.TestCase):
    def test_00_live_collection_normalizes_three_independent_contexts(self):
        raw_by_endpoint = {
            "/v1/lookup": _load(RAW / "lookup_resolved.json"),
            ("/v1/fetch", "terrain"): _load(RAW / "point_land_complete.json"),
            ("/v1/fetch", "flood_risk"): _load(RAW / "point_hazard_complete.json"),
        }

        def fake_request(*, endpoint, body):
            key = endpoint if endpoint == "/v1/lookup" else (endpoint, body["preset"])
            return deepcopy(raw_by_endpoint[key]), {"ok": True, "http_status": 200}

        result = collect_live_mireye_contexts(
            lat=LOC["lat"],
            lng=LOC["lng"],
            parcel_geometry_hash="fixture_geom_hash_cper_001",
            request_fn=fake_request,
        )
        self.assertEqual(set(result["contexts"]), {CONTEXT_PROPERTY, CONTEXT_LAND, CONTEXT_HAZARD})
        self.assertEqual(result["errors"], {})
        self.assertFalse(result["canonical_for_parcel_facts"])
        for context in result["contexts"].values():
            self.assertFalse(context["authority"]["canonical_for_parcel_facts"])

    def test_00b_live_collection_preserves_one_context_failure(self):
        def fake_request(*, endpoint, body):
            if endpoint == "/v1/lookup":
                raise MireyeAdapterError("UPSTREAM_TIMEOUT")
            name = "point_land_complete.json" if body["preset"] == "terrain" else "point_hazard_complete.json"
            return _load(RAW / name), {"ok": True, "http_status": 200}

        result = collect_live_mireye_contexts(
            lat=LOC["lat"],
            lng=LOC["lng"],
            parcel_geometry_hash="fixture_geom_hash_cper_001",
            request_fn=fake_request,
        )
        self.assertIn(CONTEXT_PROPERTY, result["errors"])
        self.assertEqual(set(result["contexts"]), {CONTEXT_LAND, CONTEXT_HAZARD})
    def test_01_complete_lookup_response(self):
        ctx = _norm(CONTEXT_PROPERTY, "lookup_resolved.json")
        self.assertEqual(ctx["context_type"], CONTEXT_PROPERTY)
        self.assertEqual(ctx["response_status"]["status"], "COMPLETE")
        self.assertEqual(ctx["resolution"]["disposition"], "RESOLVED")
        self.assertEqual(ctx["resolution"]["parcel_grade"], "A")
        self.assertEqual(ctx["resolution"]["confidence"], "high")
        self.assertEqual(ctx["resolution"]["normalized_address"], "CPER HQ Rd, Nunn, CO")
        self.assertFalse(ctx["resolution"]["legal_title_verified"])
        self.assertFalse(ctx["resolution"]["zoning_legality_confirmed"])
        self.assertEqual(ctx["parcel_candidate"]["parcel_id"], "CPER-FIXTURE-001")
        self.assertFalse(ctx["authority"]["canonical_for_parcel_facts"])
        golden = _load(NORM / "lookup_resolved.normalized.json")
        self.assertEqual(ctx["context_id"], golden["context_id"])
        self.assertEqual(
            ctx["provenance"]["raw_response_hash"],
            golden["provenance"]["raw_response_hash"],
        )

    def test_02_clarify_lookup(self):
        ctx = _norm(CONTEXT_PROPERTY, "lookup_clarify.json")
        self.assertEqual(ctx["resolution"]["disposition"], "CLARIFY")
        self.assertEqual(ctx["response_status"]["status"], "PARTIAL")

    def test_03_no_match_lookup(self):
        ctx = _norm(CONTEXT_PROPERTY, "lookup_no_match.json")
        self.assertEqual(ctx["resolution"]["disposition"], "NO_MATCH")
        self.assertEqual(ctx["response_status"]["status"], "FAILED")
        self.assertEqual(ctx["resolution"]["reason"], "no_geocode_hit")

    def test_04_complete_land_read(self):
        ctx = _norm(CONTEXT_LAND, "point_land_complete.json")
        self.assertEqual(ctx["response_status"]["status"], "COMPLETE")
        self.assertIn("slope_degrees", ctx["fields"])
        self.assertIn("lcms_class", ctx["fields"])
        self.assertIn("land_use_class", ctx["fields"])
        self.assertEqual(ctx["request"]["preset"], "terrain")
        self.assertEqual(ctx["request"]["endpoint"], "/v1/fetch")
        self.assertEqual(ctx["partial_failures"], [])
        golden = _load(NORM / "point_land_complete.normalized.json")
        self.assertEqual(ctx, golden)

    def test_05_partial_land_read(self):
        ctx = _norm(CONTEXT_LAND, "point_land_partial.json")
        self.assertEqual(ctx["response_status"]["status"], "PARTIAL")
        self.assertTrue(ctx["partial_failures"])
        elev_fail = [f for f in ctx["partial_failures"] if f["field_id"] == "elevation"]
        self.assertTrue(elev_fail)
        self.assertEqual(elev_fail[0]["normalized_effect"], "UNKNOWN")
        self.assertIsNone(ctx["fields"]["elevation"]["value"])

    def test_06_complete_hazard_read(self):
        ctx = _norm(CONTEXT_HAZARD, "point_hazard_complete.json")
        self.assertEqual(ctx["response_status"]["status"], "COMPLETE")
        self.assertEqual(ctx["request"]["preset"], "flood_risk")
        self.assertIn("tree_canopy_pct", ctx["fields"])
        self.assertIn("ndvi_current", ctx["fields"])
        self.assertEqual(ctx["fields"]["flood_zone"]["value"], "X")

    def test_07_fema_null_partial_failure_unknown(self):
        ctx = _norm(CONTEXT_HAZARD, "point_hazard_fema_partial.json")
        self.assertEqual(ctx["response_status"]["status"], "PARTIAL")
        fema = [f for f in ctx["partial_failures"] if f["field_id"] == "flood_zone"]
        self.assertTrue(fema)
        self.assertEqual(fema[0]["normalized_effect"], "UNKNOWN")
        self.assertIsNone(ctx["fields"]["flood_zone"]["value"])

    def test_08_null_field_preserved(self):
        ctx = _norm(CONTEXT_HAZARD, "point_hazard_null_field.json")
        self.assertIsNone(ctx["fields"]["ndvi_current"]["value"])
        # absent null without error is preserved; not auto-failed
        self.assertEqual(ctx["fields"]["ndvi_current"]["notes"], "no observation")

    def test_09_source_provenance_retained(self):
        ctx = _norm(CONTEXT_LAND, "point_land_complete.json")
        elev = ctx["fields"]["elevation"]
        self.assertEqual(elev["source"], "USGS_3DEP_COG")
        self.assertTrue(elev["source_url"])
        self.assertEqual(elev["confidence"], "medium")
        self.assertTrue(elev["dataset_vintage"])
        self.assertTrue(elev["fetched_at"])
        self.assertEqual(ctx["provenance"]["adapter_version"], ADAPTER_VERSION)
        self.assertEqual(ctx["provenance"]["api_base_url"], "https://api.mireye.com")
        self.assertTrue(ctx["provenance"]["raw_response_hash"])
        self.assertTrue(ctx["provenance"]["request_hash"])

    def test_10_point_authority_not_parcel_canonical(self):
        for name, ctype in (
            ("point_land_complete.json", CONTEXT_LAND),
            ("point_hazard_complete.json", CONTEXT_HAZARD),
            ("lookup_resolved.json", CONTEXT_PROPERTY),
        ):
            ctx = _norm(ctype, name)
            self.assertIs(ctx["authority"]["canonical_for_parcel_facts"], False)
            self.assertIn("POINT_QA", ctx["authority"]["permitted_uses"])
            self.assertEqual(ctx["location"]["spatial_semantics"], "POINT")

    def test_11_factor_refs_do_not_duplicate_land_facts(self):
        ctx = _norm(CONTEXT_LAND, "point_land_complete.json")
        refs = ctx["factor_usage_refs"]
        self.assertTrue(refs)
        # refs point at context_id + field_id only; no embedded Mireye values
        for ref in refs:
            self.assertEqual(ref["context_id"], ctx["context_id"])
            self.assertIn(ref["field_id"], ctx["fields"])
            self.assertNotIn("value", ref)
        # same field may be referenced by multiple factors without copying values
        lcms_refs = [r for r in refs if r["field_id"] == "lcms_class"]
        factors = {r["factor_id"] for r in lcms_refs}
        self.assertIn("F02_HERBACEOUS_RESOURCE", factors)
        self.assertIn("F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE", factors)
        rebuilt = build_factor_usage_refs(ctx["context_id"], ctx["fields"])
        self.assertEqual(refs, rebuilt)

    def test_12_deterministic_context_hash(self):
        a = _norm(CONTEXT_LAND, "point_land_complete.json")
        b = _norm(CONTEXT_LAND, "point_land_complete.json")
        self.assertEqual(a["context_id"], b["context_id"])
        self.assertEqual(
            a["provenance"]["raw_response_hash"], b["provenance"]["raw_response_hash"]
        )
        self.assertEqual(a["request"]["request_hash"], b["request"]["request_hash"])
        self.assertEqual(a, b)

    def test_13_credentials_absent(self):
        dirty = {
            "lat": 40.825,
            "lng": -104.7625,
            "fetched_at": "2026-08-07T20:55:50+00:00",
            "api_key": "mireye_secret_should_not_persist",
            "fields": {
                "elevation": {
                    "value": 1,
                    "unit": "meters",
                    "source": "USGS_3DEP_COG",
                    "source_url": "https://www.usgs.gov/3d-elevation-program",
                    "confidence": "medium",
                    "fetched_at": "2026-08-07T20:55:50+00:00",
                    "dataset_vintage": None,
                    "ttl_seconds": 1,
                    "notes": "Bearer sk-abcdefghijklmnopqrstuvwxyz",
                    "status": "ok",
                }
            },
            "partial_failures": [],
        }
        safe = sanitize_for_storage(dirty)
        self.assertNotIn("api_key", safe)
        self.assertNotIn("mireye_secret", json.dumps(safe))
        ctx = normalize_mireye_context(
            context_type=CONTEXT_LAND,
            raw_response=dirty,
            requested_location=LOC,
            point_role="PARCEL_CENTROID_QA",
            api_base_url="https://user:pass@api.mireye.com",
        )
        blob = json.dumps(ctx)
        self.assertNotIn("mireye_secret", blob)
        self.assertNotIn("user:pass@", ctx["provenance"]["api_base_url"])
        assert_no_credentials(ctx, label="normalized")
        for path in NORM.glob("*.json"):
            assert_no_credentials(path.read_text(encoding="utf-8"), label=str(path))
        for path in RAW.glob("*.json"):
            assert_no_credentials(path.read_text(encoding="utf-8"), label=str(path))

    def test_14_invalid_response_fails_closed(self):
        with self.assertRaises(MireyeAdapterError):
            normalize_mireye_context(
                context_type=CONTEXT_LAND,
                raw_response=_load(RAW / "invalid_response.json"),
                requested_location=LOC,
            )
        with self.assertRaises(MireyeAdapterError):
            normalize_mireye_context(
                context_type=CONTEXT_PROPERTY,
                raw_response={"fields": {}},
                requested_location=LOC,
            )
        with self.assertRaises(MireyeAdapterError):
            normalize_mireye_context(
                context_type=CONTEXT_LAND,
                raw_response=None,
                requested_location=LOC,
            )
        with self.assertRaises(MireyeAdapterError):
            normalize_mireye_context(
                context_type="NOT_A_CONTEXT",
                raw_response={"fields": {}},
                requested_location=LOC,
            )

    def test_adapter_identity_and_no_value_mutation(self):
        raw = _load(RAW / "point_land_complete.json")
        original = deepcopy(raw["fields"]["slope_degrees"]["value"])
        ctx = _norm(CONTEXT_LAND, "point_land_complete.json")
        self.assertEqual(ctx["adapter_id"], ADAPTER_ID)
        self.assertEqual(ctx["fields"]["slope_degrees"]["value"], original)
        self.assertEqual(ctx["location"]["point_role"], "PARCEL_CENTROID_QA")

    def test_resolve_mireye_api_token_prefers_token_over_key(self):
        import os

        from rangematch.mireye_adapter import resolve_mireye_api_token

        old_token = os.environ.pop("MIREYE_API_TOKEN", None)
        old_key = os.environ.pop("MIREYE_API_KEY", None)
        try:
            self.assertIsNone(resolve_mireye_api_token())
            os.environ["MIREYE_API_KEY"] = "legacy-key"
            self.assertEqual(resolve_mireye_api_token(), "legacy-key")
            os.environ["MIREYE_API_TOKEN"] = "canonical-token"
            self.assertEqual(resolve_mireye_api_token(), "canonical-token")
        finally:
            if old_token is None:
                os.environ.pop("MIREYE_API_TOKEN", None)
            else:
                os.environ["MIREYE_API_TOKEN"] = old_token
            if old_key is None:
                os.environ.pop("MIREYE_API_KEY", None)
            else:
                os.environ["MIREYE_API_KEY"] = old_key


if __name__ == "__main__":
    unittest.main()
