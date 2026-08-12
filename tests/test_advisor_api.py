"""HTTP surface for the Advisor Agent run chain."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from rangematch.advisor_agent import CPER_DEMO_ADDRESS
from rangematch.api import app, reset_store_for_tests


class AdvisorApiTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_store_for_tests()
        self.client = TestClient(app)

    def test_post_queues_then_get_completes_cper_address(self) -> None:
        created = self.client.post(
            "/v1/advisor/runs", json={"address": CPER_DEMO_ADDRESS}
        )
        self.assertEqual(created.status_code, 200, created.text)
        queued = created.json()
        self.assertIn(queued["status"], {"QUEUED", "RUNNING", "SUCCEEDED"})
        self.assertTrue(queued["run_id"])
        fetched = self.client.get(f"/v1/advisor/runs/{queued['run_id']}")
        self.assertEqual(fetched.status_code, 200)
        body = fetched.json()
        self.assertEqual(body["status"], "SUCCEEDED")
        self.assertTrue(body["packet_hash"])
        self.assertGreaterEqual(len(body["agenda"]), 8)
        self.assertEqual(body["mireye_live"]["mode"], "UNIT_TEST_HOOK")
        self.assertTrue(body["mireye_live"]["allow_network"])
        self.assertEqual(
            body["brief"]["page_one_advisor"]["visit_purpose"],
            "VISIT_DEPENDS_ON_DOCUMENT",
        )

    def test_unknown_place_is_a_named_failed_run(self) -> None:
        created = self.client.post(
            "/v1/advisor/runs", json={"address": "No Such Tract, Empty County, WY"}
        )
        self.assertEqual(created.status_code, 200)
        run_id = created.json()["run_id"]
        body = self.client.get(f"/v1/advisor/runs/{run_id}").json()
        self.assertEqual(body["status"], "FAILED")
        self.assertEqual(body["failed_step"], "RESOLVE_PARCEL")
        self.assertIsNone(body["brief"])
        self.assertIsNone(body["packet"])

    def test_buyer_explanation_uses_fixture_and_keeps_packet(self) -> None:
        created = self.client.post(
            "/v1/advisor/runs", json={"address": CPER_DEMO_ADDRESS}
        )
        run_id = created.json()["run_id"]
        self.client.get(f"/v1/advisor/runs/{run_id}")
        explained = self.client.post(
            f"/v1/advisor/runs/{run_id}/buyer-explanation",
            json={"provider": "FIXTURE"},
        )
        self.assertEqual(explained.status_code, 200, explained.text)
        body = explained.json()
        self.assertEqual(body["status"], "SUCCEEDED")
        self.assertEqual(body["buyer_explanation"]["source"], "STRUCTURED_FIXTURE")
        self.assertEqual(body["buyer_explanation"]["validation_status"], "PASSED")
        self.assertTrue(body["packet_hash"])

    def test_missing_run_is_404(self) -> None:
        response = self.client.get("/v1/advisor/runs/advisor_missing")
        self.assertEqual(response.status_code, 404)
