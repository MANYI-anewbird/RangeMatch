"""Fixture tests for Mireye /lookup → parcel resolution live adapter."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from rangematch.mireye_parcel_resolver import (
    PROVENANCE_SOURCE,
    map_mireye_lookup_to_parcel,
)
from rangematch.parcel_resolution import (
    ADAPTER_LIVE,
    LiveParcelResolver,
    confirm_selected_parcel,
    start_parcel_resolution,
)


ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "test-data" / "mireye-parcel-lookup"


def _scenario(name: str) -> dict:
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


class MireyeLookupMappingTests(unittest.TestCase):
    def test_resolved_with_parcel_maps_to_candidates(self):
        raw = _scenario("resolved_with_parcel")["lookup_response"]
        mapped = map_mireye_lookup_to_parcel(raw)
        self.assertEqual(mapped.disposition, "resolved")
        self.assertIsNone(mapped.terminal_status)
        self.assertEqual(mapped.geocode_status, "OK")
        self.assertEqual(len(mapped.candidates), 1)
        self.assertEqual(
            mapped.candidates[0]["provenance"]["source"], PROVENANCE_SOURCE
        )
        # Owner must be redacted
        blob = json.dumps(mapped.candidates)
        self.assertNotIn("MUST_BE_REDACTED", blob)
        self.assertIsNone(mapped.candidates[0]["attributes"].get("owner"))

    def test_resolved_accepts_geojson_string_geometry_from_live_contract(self):
        raw = _scenario("resolved_with_parcel")["lookup_response"]
        raw["parcel"]["geometry"] = json.dumps(raw["parcel"]["geometry"])
        mapped = map_mireye_lookup_to_parcel(raw)
        self.assertIsNone(mapped.terminal_status)
        self.assertEqual(len(mapped.candidates), 1)
        self.assertEqual(
            mapped.candidates[0]["parcel_geometry"]["features"][0]["geometry"]["type"],
            "Polygon",
        )

    def test_resolved_parcel_unavailable(self):
        raw = _scenario("resolved_parcel_unavailable")["lookup_response"]
        mapped = map_mireye_lookup_to_parcel(raw)
        self.assertEqual(mapped.terminal_status, "PARCEL_DATA_UNAVAILABLE")
        self.assertTrue(mapped.parcel_unavailable)
        self.assertEqual(mapped.parcel_unavailable_reason, "regrid_quota_exhausted")
        self.assertEqual(mapped.candidates, [])

    def test_clarify_with_parcels(self):
        raw = _scenario("clarify_with_parcels")["lookup_response"]
        mapped = map_mireye_lookup_to_parcel(raw)
        self.assertIsNone(mapped.terminal_status)
        self.assertEqual(len(mapped.candidates), 2)
        blob = json.dumps(mapped.candidates)
        self.assertNotIn("REDACT_ME", blob)

    def test_clarify_points_only_ambiguous(self):
        raw = _scenario("clarify_points_only")["lookup_response"]
        mapped = map_mireye_lookup_to_parcel(raw)
        self.assertEqual(mapped.terminal_status, "AMBIGUOUS")
        self.assertEqual(mapped.candidates, [])

    def test_no_match(self):
        raw = _scenario("no_match")["lookup_response"]
        mapped = map_mireye_lookup_to_parcel(raw)
        self.assertEqual(mapped.terminal_status, "NO_MATCH")

    def test_geocode_quality_blocks_even_if_parcel_present(self):
        raw = _scenario("geocode_range_interpolation")["lookup_response"]
        mapped = map_mireye_lookup_to_parcel(raw)
        self.assertEqual(mapped.terminal_status, "GEOCODE_QUALITY_INSUFFICIENT")
        self.assertEqual(mapped.geocode_status, "GEOCODE_QUALITY_INSUFFICIENT")
        self.assertEqual(mapped.candidates, [])

    def test_apn_not_supported(self):
        raw = _scenario("apn_not_supported")["lookup_response"]
        mapped = map_mireye_lookup_to_parcel(raw)
        self.assertEqual(mapped.terminal_status, "NO_MATCH")
        self.assertTrue(
            any("apn_not_supported" in (e.get("message") or "") for e in mapped.errors)
        )


class MireyeLiveResolverFixtureTests(unittest.TestCase):
    def test_unconfigured_live_stays_blocked(self):
        record = start_parcel_resolution(
            "123 Main St, Denver, CO 80202",
            mode="LIVE",
        )
        self.assertEqual(record["status"], "BLOCKED_EXTERNAL")
        self.assertEqual(record["adapter_id"], ADAPTER_LIVE)
        blob = json.dumps(record)
        self.assertNotIn("engineering_test_geometry_cper", blob)
        self.assertIn("No network call was made", " ".join(record["limitations"]))

    def test_resolved_with_parcel_needs_confirmation_not_auto_confirm(self):
        sc = _scenario("resolved_with_parcel")
        record = start_parcel_resolution(
            sc["raw_address"],
            mode="LIVE",
            scenario_id="resolved_with_parcel",
        )
        self.assertEqual(record["status"], "NEEDS_BOUNDARY_CONFIRMATION")
        self.assertEqual(record["provider_mode"], "LIVE")
        self.assertEqual(len(record["candidates"]), 1)
        self.assertEqual(record["geocode"]["accuracy_type"], "rooftop")
        self.assertEqual(
            record["candidates"][0]["provenance"]["source"], PROVENANCE_SOURCE
        )
        self.assertNotEqual(record["status"], "PARCEL_CONFIRMED")

    def test_confirm_after_mireye_resolved(self):
        sc = _scenario("resolved_with_parcel")
        record = start_parcel_resolution(
            sc["raw_address"],
            mode="LIVE",
            scenario_id="resolved_with_parcel",
        )
        cand = record["candidates"][0]
        confirmed = confirm_selected_parcel(
            record,
            candidate_id=cand["candidate_id"],
            expected_geometry_hash=cand["geometry_hash"],
            confirm_boundary=True,
            resolver=LiveParcelResolver(fixture_scenario_id="resolved_with_parcel"),
        )
        self.assertEqual(confirmed["status"], "PARCEL_CONFIRMED")
        self.assertEqual(
            confirmed["provenance"]["source"], PROVENANCE_SOURCE
        )

    def test_parcel_unavailable_visible(self):
        sc = _scenario("resolved_parcel_unavailable")
        record = start_parcel_resolution(
            sc["raw_address"],
            mode="LIVE",
            scenario_id="resolved_parcel_unavailable",
        )
        self.assertEqual(record["status"], "PARCEL_DATA_UNAVAILABLE")
        self.assertEqual(record["candidates"], [])
        self.assertEqual(
            record["provenance"].get("parcel_unavailable_reason"),
            "regrid_quota_exhausted",
        )
        blob = json.dumps(record)
        self.assertNotIn("engineering_test_geometry_cper", blob)

    def test_clarify_requires_selection(self):
        sc = _scenario("clarify_with_parcels")
        record = start_parcel_resolution(
            sc["raw_address"],
            mode="LIVE",
            scenario_id="clarify_with_parcels",
        )
        self.assertEqual(record["status"], "NEEDS_USER_SELECTION")
        self.assertEqual(len(record["candidates"]), 2)

    def test_clarify_points_only(self):
        sc = _scenario("clarify_points_only")
        record = start_parcel_resolution(
            sc["raw_address"],
            mode="LIVE",
            scenario_id="clarify_points_only",
        )
        self.assertEqual(record["status"], "AMBIGUOUS")

    def test_no_match_fixture(self):
        sc = _scenario("no_match")
        record = start_parcel_resolution(
            sc["raw_address"],
            mode="LIVE",
            scenario_id="no_match",
        )
        self.assertEqual(record["status"], "NO_MATCH")

    def test_geocode_quality_insufficient(self):
        sc = _scenario("geocode_range_interpolation")
        record = start_parcel_resolution(
            sc["raw_address"],
            mode="LIVE",
            scenario_id="geocode_range_interpolation",
        )
        self.assertEqual(record["status"], "GEOCODE_QUALITY_INSUFFICIENT")
        self.assertEqual(record["geocode"]["accuracy_type"], "range_interpolation")
        self.assertEqual(record["candidates"], [])

    def test_address_mismatch_refuses_substitution(self):
        with self.assertRaises(Exception) as ctx:
            start_parcel_resolution(
                "Totally Different Address, CO",
                mode="LIVE",
                scenario_id="resolved_with_parcel",
            )
        self.assertIn("MIREYE_LOOKUP_ADDRESS_MISMATCH", str(ctx.exception))


class MireyeLiveResolverAPITests(unittest.TestCase):
    def setUp(self) -> None:
        from fastapi.testclient import TestClient

        from rangematch.api import app, reset_store_for_tests

        reset_store_for_tests()
        self.client = TestClient(app)

    def test_api_live_fixture_resolved(self):
        sc = _scenario("resolved_with_parcel")
        r = self.client.post(
            "/v1/parcel-resolutions",
            json={
                "address": sc["raw_address"],
                "resolver_mode": "LIVE",
                "fixture_scenario_id": "resolved_with_parcel",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["status"], "NEEDS_BOUNDARY_CONFIRMATION")
        self.assertEqual(body["provider_mode"], "LIVE")

    def test_api_live_without_fixture_still_blocked(self):
        r = self.client.post(
            "/v1/parcel-resolutions",
            json={
                "address": "999 Nowhere Rd, Denver, CO 80202",
                "resolver_mode": "LIVE",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "BLOCKED_EXTERNAL")

    def test_api_live_parcel_unavailable(self):
        sc = _scenario("resolved_parcel_unavailable")
        r = self.client.post(
            "/v1/parcel-resolutions",
            json={
                "address": sc["raw_address"],
                "resolver_mode": "LIVE",
                "fixture_scenario_id": "resolved_parcel_unavailable",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "PARCEL_DATA_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
