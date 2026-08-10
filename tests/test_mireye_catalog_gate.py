"""Tests for Mireye Field Catalog compatibility gate (offline)."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from rangematch.api import app, reset_store_for_tests
from rangematch.mireye_catalog_gate import (
    PINNED_CATALOG_VERSION,
    evaluate_catalog_compatibility,
    evaluate_fixture_catalog,
    fetch_mireye_field_catalog,
    load_catalog_fixture,
    mutate_catalog_major_version,
    mutate_catalog_missing_field,
    mutate_catalog_unit,
    parse_major_version,
    run_catalog_gate,
)


class CatalogGateUnitTests(unittest.TestCase):
    def test_parse_major(self):
        self.assertEqual(parse_major_version("0.14.0"), 0)
        self.assertEqual(parse_major_version("v1.2.3"), 1)
        self.assertIsNone(parse_major_version(None))

    def test_fixture_catalog_compatible(self):
        result = evaluate_fixture_catalog()
        self.assertEqual(result.status, "COMPATIBLE")
        self.assertTrue(result.compatible)
        self.assertEqual(result.observed_catalog_version, PINNED_CATALOG_VERSION)
        self.assertFalse(result.affects_parcel_resolution)
        self.assertEqual(result.missing_fields, [])
        self.assertEqual(result.unit_mismatches, [])

    def test_missing_field_fail_closed(self):
        catalog = mutate_catalog_missing_field(load_catalog_fixture(), "slope_degrees")
        result = evaluate_catalog_compatibility(catalog)
        self.assertEqual(result.status, "INCOMPATIBLE")
        self.assertFalse(result.compatible)
        self.assertIn("slope_degrees", result.missing_fields)
        self.assertFalse(result.affects_parcel_resolution)

    def test_unit_mismatch_fail_closed(self):
        catalog = mutate_catalog_unit(load_catalog_fixture(), "elevation", "feet")
        result = evaluate_catalog_compatibility(catalog)
        self.assertEqual(result.status, "INCOMPATIBLE")
        self.assertTrue(any(m["field"] == "elevation" for m in result.unit_mismatches))
        self.assertFalse(result.affects_parcel_resolution)

    def test_major_version_incompatible(self):
        catalog = mutate_catalog_major_version(load_catalog_fixture(), "1.0.0")
        result = evaluate_catalog_compatibility(catalog)
        self.assertEqual(result.status, "INCOMPATIBLE")
        self.assertTrue(
            any(e["code"] == "CATALOG_MAJOR_INCOMPATIBLE" for e in result.errors)
        )
        self.assertFalse(result.compatible)

    def test_http_304_not_modified(self):
        result = evaluate_catalog_compatibility(
            {},
            etag='W/"abc"',
            previous_etag='W/"abc"',
            http_status=304,
        )
        self.assertEqual(result.status, "NOT_MODIFIED")
        self.assertTrue(result.compatible)

    def test_live_fetch_gated_without_network(self):
        catalog, meta = fetch_mireye_field_catalog(allow_network=False)
        self.assertIsNone(catalog)
        self.assertEqual(meta["error_class"], "NETWORK_GATED")

    def test_run_live_without_allow_network_is_fetch_failed_not_parcel(self):
        result = run_catalog_gate(mode="LIVE", allow_network=False)
        self.assertEqual(result.status, "FETCH_FAILED")
        self.assertFalse(result.affects_parcel_resolution)
        self.assertFalse(result.compatible)


class CatalogGateAPITests(unittest.TestCase):
    def setUp(self) -> None:
        reset_store_for_tests()
        self.client = TestClient(app)

    def test_health_includes_compatible_fixture_gate(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        gate = r.json()["mireye_catalog_gate"]
        self.assertEqual(gate["status"], "COMPATIBLE")
        self.assertTrue(gate["compatible"])
        self.assertFalse(gate["affects_parcel_resolution"])

    def test_catalog_gate_endpoint_fixture(self):
        r = self.client.post("/v1/mireye/catalog-gate", json={"mode": "FIXTURE"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["status"], "COMPATIBLE")
        self.assertFalse(body["affects_parcel_resolution"])

    def test_catalog_gate_live_gated(self):
        r = self.client.post(
            "/v1/mireye/catalog-gate",
            json={"mode": "LIVE", "allow_network": False},
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["status"], "FETCH_FAILED")
        self.assertFalse(body["affects_parcel_resolution"])


if __name__ == "__main__":
    unittest.main()
