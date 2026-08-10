from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from rangematch.f04_sda_adapter import F04SDAAdapterError, collect_f04_from_usda_sda


ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "test-data/live-results/cper"
GEOMETRY = json.loads((ROOT / "test-data/engineering_test_geometry_cper_001.geojson").read_text())


class F04SDAAdapterTests(unittest.TestCase):
    def test_replays_audited_sda_payloads_without_directional_score(self):
        tables = [
            json.loads((LIVE / "cper_sda_mapunit_component_ecosite_2026-08-07.json").read_text()),
            json.loads((LIVE / "cper_sda_horizons_2026-08-07.json").read_text()),
            json.loads((LIVE / "cper_sda_restrictions_2026-08-07.json").read_text()),
            json.loads((LIVE / "cper_sda_monthly_wetness_2026-08-07.json").read_text()),
        ]
        spatial = json.loads((LIVE / "cper_sda_spatial_coverage_2026-08-07.json").read_text())
        with patch("rangematch.f04_sda_adapter._post_query", side_effect=tables) as post, patch(
            "rangematch.f04_sda_adapter._fetch_wfs_spatial_coverage", return_value=spatial
        ):
            factor = collect_f04_from_usda_sda(
                geometry=GEOMETRY,
                geometry_id="CPER_TEST",
                geometry_hash="a" * 64,
            )
        self.assertEqual(post.call_count, 4)
        self.assertEqual(factor["factor_id"], "F04_SOIL_WETNESS_ECOLOGICAL_SITE")
        self.assertEqual(factor["input_quality_state"], "PARCEL_COMPLETE")
        self.assertEqual(factor["ranking_effect"], "NONE")
        self.assertFalse(factor["directional_signal_allowed"])
        self.assertFalse(factor["adapter"]["edit_access_fetched"])

    def test_rejects_multiple_features(self):
        invalid = {"type": "FeatureCollection", "features": [*GEOMETRY["features"], *GEOMETRY["features"]]}
        with self.assertRaises(F04SDAAdapterError):
            collect_f04_from_usda_sda(
                geometry=invalid,
                geometry_id="BAD",
                geometry_hash="b" * 64,
            )


if __name__ == "__main__":
    unittest.main()
