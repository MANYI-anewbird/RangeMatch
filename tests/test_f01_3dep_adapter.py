"""Offline replay tests for the production USGS 3DEP F01 adapter."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from rangematch.f01_3dep_adapter import F01AdapterError, collect_f01_from_usgs_3dep


ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "test-data/live-results/cper-live-confirmed-parcel/f01"


class F013DEPAdapterTests(unittest.TestCase):
    def test_offline_replay_matches_live_gate(self):
        geometry = json.loads((FIX / "confirmed_parcel_geometry.geojson").read_text())
        catalog = json.loads((FIX / "usgs_3dep_catalog_query.json").read_text())
        export = json.loads((FIX / "usgs_3dep_export_contract.json").read_text())
        dem = (FIX / "dem_locked_13_buffered.tif").read_bytes()

        def json_get(url: str, timeout: float):
            self.assertGreater(timeout, 0)
            return catalog if "/query?" in url else export

        def bytes_get(url: str, timeout: float):
            self.assertEqual(url, export["href"])
            return dem

        factor = collect_f01_from_usgs_3dep(
            geometry=geometry,
            geometry_id="8b82c68b-6127-47e1-8b05-7abe8376cc95",
            geometry_hash="3ae9eb7a1e03213bcacd6b0d0c8bca18e6cef3603a60d08c8c893bf543fdc42c",
            json_get=json_get,
            bytes_get=bytes_get,
        )
        expected = json.loads((FIX / "f01_derivation_result.json").read_text())
        self.assertEqual(factor["input_quality_state"], "PARCEL_COMPLETE")
        self.assertEqual(factor["coverage"]["coverage_fraction"], 1.0)
        self.assertEqual(factor["coverage"]["status"], "COMPLETE")
        self.assertEqual(factor["canonical_source_id"], "USGS_3DEP_1_3_ARC_SECOND_SEAMLESS_DEM")
        self.assertEqual(
            factor["provenance"]["response_or_artifact_hash"],
            factor["source"]["source_raster_sha256"],
        )
        for key, value in expected["summary"].items():
            self.assertAlmostEqual(factor["summary"][key], value, places=10)
        self.assertEqual(factor["ranking_effect"], "NONE")
        self.assertNotIn("suitability_score", factor)
        self.assertNotIn("carrying_capacity", factor)

    def test_missing_reviewed_source_fails_closed(self):
        geometry = json.loads((FIX / "confirmed_parcel_geometry.geojson").read_text())
        with self.assertRaises(F01AdapterError):
            collect_f01_from_usgs_3dep(
                geometry=geometry,
                geometry_id="geom",
                geometry_hash="a" * 64,
                json_get=lambda _url, _timeout: {"features": []},
                bytes_get=lambda _url, _timeout: b"",
            )


if __name__ == "__main__":
    unittest.main()
