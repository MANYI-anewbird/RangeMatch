from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from rangematch.f03_nhd_adapter import F03NHDAdapterError, collect_f03_from_usgs_nhd


ROOT = Path(__file__).resolve().parents[1]
GEOMETRY = json.loads((ROOT / "test-data/engineering_test_geometry_cper_001.geojson").read_text())
LIVE = ROOT / "test-data/live-results/cper"


class F03NHDAdapterTests(unittest.TestCase):
    def test_replays_nhd_inventory_without_minting_verified_water(self):
        layers = [
            json.loads((LIVE / "cper_nhd_network_flowlines.geojson").read_text()),
            json.loads((LIVE / "cper_nhd_nonnetwork_flowlines.geojson").read_text()),
            json.loads((LIVE / "cper_nhd_areas.geojson").read_text()),
            json.loads((LIVE / "cper_nhd_waterbodies.geojson").read_text()),
        ]
        with patch("rangematch.f03_nhd_adapter._fetch_nhd_layer", side_effect=layers) as fetch:
            factor = collect_f03_from_usgs_nhd(
                geometry=GEOMETRY,
                geometry_id="CPER_TEST",
                geometry_hash="a" * 64,
            )
        self.assertEqual(fetch.call_count, 4)
        self.assertEqual(factor["factor_id"], "F03_LIVESTOCK_WATER")
        self.assertEqual(factor["input_quality_state"], "MAPPED_CANDIDATES_ONLY")
        self.assertGreater(factor["mapped_candidate_count"], 0)
        self.assertEqual(factor["field_verified_count"], 0)
        self.assertEqual(factor["remote_evidence_summary"]["remotely_supported"], 0)
        self.assertEqual(
            factor["remote_evidence_summary"]["imagery_review_status"],
            "PENDING_PROVENANCE_COMPLETE_REVIEW",
        )
        self.assertTrue(
            all(
                record["verification_level"]["status"] == "MAPPED_CANDIDATE"
                for record in factor["remote_review_queue"]
            )
        )
        self.assertEqual(factor["ranking_effect"], "NONE")

    def test_partial_layer_failure_is_visible(self):
        network = json.loads((LIVE / "cper_nhd_network_flowlines.geojson").read_text())
        with patch(
            "rangematch.f03_nhd_adapter._fetch_nhd_layer",
            side_effect=[network, RuntimeError("blocked"), RuntimeError("blocked"), RuntimeError("blocked")],
        ):
            factor = collect_f03_from_usgs_nhd(
                geometry=GEOMETRY,
                geometry_id="CPER_TEST",
                geometry_hash="b" * 64,
            )
        self.assertEqual(factor["coverage"]["status"], "PARTIAL")
        self.assertEqual(len(factor["coverage"]["failed_layers"]), 3)

    def test_all_layers_failed_raises(self):
        with patch(
            "rangematch.f03_nhd_adapter._fetch_nhd_layer",
            side_effect=RuntimeError("blocked"),
        ), self.assertRaises(F03NHDAdapterError):
            collect_f03_from_usgs_nhd(
                geometry=GEOMETRY,
                geometry_id="CPER_TEST",
                geometry_hash="c" * 64,
            )


if __name__ == "__main__":
    unittest.main()
