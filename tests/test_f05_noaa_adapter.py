"""Offline tests for canonical NOAA/NCEI F05 adapter."""

import json
import unittest
from pathlib import Path

from rangematch.f05_noaa_adapter import collect_f05_from_noaa_normals

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "test-data/live-results/cper-live-confirmed-parcel/f01"


class F05NOAAAdapterTests(unittest.TestCase):
    def test_confirmed_parcel_noaa_normals_context_only(self):
        geometry = json.loads((LIVE / "confirmed_parcel_geometry.geojson").read_text())
        factor = collect_f05_from_noaa_normals(
            geometry=geometry,
            geometry_id="parcel",
            geometry_hash="a" * 64,
        )
        self.assertEqual(factor["input_quality_state"], "CLIMATE_CONTEXT_COMPLETE")
        self.assertEqual(factor["canonical_precipitation"]["value_mm"], 345.74)
        self.assertEqual(factor["canonical_precipitation"]["normals_period"], "1991-2020")
        self.assertEqual(factor["canonical_precipitation"]["suitability_signal"], None)
        self.assertEqual(factor["ranking_effect"], "NONE")
        self.assertTrue(factor["validation"]["complete"])
        self.assertNotIn("carrying_capacity", factor)


if __name__ == "__main__":
    unittest.main()
