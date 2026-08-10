import unittest

from rangematch.investigation_job import _LiveCollectionProgress


class LiveCollectionProgressTests(unittest.TestCase):
    def test_live_adapter_status_is_visible_before_executor(self) -> None:
        snapshots: list[dict] = []
        plan = {
            "plan_sha256": "a" * 64,
            "canonical_factor_report_order": ["F01_TOPOGRAPHY"],
            "constraints": {"live_network": True},
            "steps": [
                {
                    "step_id": "S07_PEER_F01_TOPOGRAPHY",
                    "tool_id": "adapter.usgs_3dep",
                    "action": "FETCH",
                    "dependency_step_ids": [],
                    "factor_id": "F01_TOPOGRAPHY",
                }
            ],
        }

        progress = _LiveCollectionProgress(plan, snapshots.append)
        progress.set("adapter.usgs_3dep", "RUNNING")
        progress.set("adapter.usgs_3dep", "SUCCEEDED")

        self.assertEqual(snapshots[0]["steps"][0]["status"], "RUNNING")
        self.assertEqual(snapshots[1]["steps"][0]["status"], "SUCCEEDED")
        self.assertEqual(
            snapshots[1]["step_order_executed"], ["S07_PEER_F01_TOPOGRAPHY"]
        )

    def test_live_adapter_failure_remains_visible_and_grounded(self) -> None:
        snapshots: list[dict] = []
        plan = {
            "plan_sha256": "b" * 64,
            "steps": [
                {
                    "step_id": "S07_PEER_F03_LIVESTOCK_WATER",
                    "tool_id": "adapter.nhd_water_candidates",
                    "action": "FETCH",
                    "dependency_step_ids": [],
                    "factor_id": "F03_LIVESTOCK_WATER",
                }
            ],
        }

        progress = _LiveCollectionProgress(plan, snapshots.append)
        progress.set(
            "adapter.nhd_water_candidates",
            "PARTIAL",
            error="upstream_timeout",
        )

        step = snapshots[-1]["steps"][0]
        self.assertEqual(step["status"], "PARTIAL")
        self.assertEqual(step["failure"]["error_code"], "LIVE_COLLECTION_FAILED")
        self.assertEqual(step["failure"]["message"], "upstream_timeout")


if __name__ == "__main__":
    unittest.main()
