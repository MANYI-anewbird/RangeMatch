"""Tests for RangeMatch one-parcel FastAPI prototype."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from rangematch.api import REPLAY_LABEL, app, reset_store_for_tests


CPER_REF = "test-data/land-profiles/land_profile_cper_001.json"


def _terminal(client, created: dict) -> dict:
    """POST returns QUEUED; TestClient drains BackgroundTasks before return, so GET is terminal."""
    assert created.get("status") == "QUEUED", created.get("status")
    inv = created["investigation_id"]
    g = client.get(f"/v1/investigations/{inv}")
    assert g.status_code == 200, g.text
    body = g.json()
    assert body["status"] in {"COMPLETED", "PARTIAL", "FAILED", "BLOCKED_EXTERNAL", "BLOCKED_INPUT"}
    return body


class OneParcelAPITests(unittest.TestCase):
    def setUp(self) -> None:
        reset_store_for_tests()
        self.client = TestClient(app)

    def test_01_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "ok")
        self.assertIn(body["live_mireye_availability"], {
            "AVAILABLE",
            "BLOCKED_EXTERNAL",
            "NOT_CONFIGURED",
        })
        self.assertFalse(body["live_network_authorized"])
        self.assertNotIn("api_key", str(body).lower())
        self.assertNotIn("authorization", str(body).lower())

    def test_02_goal_directed_fixture_post_get(self):
        r = self.client.post(
            "/v1/investigations",
            json={
                "existing_land_profile_reference": CPER_REF,
                "mode": "GOAL_DIRECTED",
                "intended_operation": "COW_CALF_OPERATION",
                "planned_actions": [],
                "execution_source": "DEMO_FIXTURE",
                "mireye_mode": "BLOCKED_EXTERNAL",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        queued = r.json()
        self.assertEqual(queued["status"], "QUEUED")
        self.assertIsNone(queued.get("unified_output"))
        body = _terminal(self.client, queued)
        self.assertIn(body["status"], {"COMPLETED", "PARTIAL"})
        self.assertEqual(body["replay_label"], REPLAY_LABEL)
        self.assertIsNotNone(body.get("presentation"))
        self.assertEqual(
            body["presentation"]["operation_presentation_order"][0],
            "COW_CALF_OPERATION",
        )
        self.assertFalse(body["presentation"]["scientific_priority_change"])
        uo = body["unified_output"]
        self.assertEqual(uo["explanation_binding_hash"], uo["match_result_hash"])
        buyer = uo.get("buyer_report") or {}
        self.assertIn("Operation Comparison", buyer)
        inv = body["investigation_id"]
        g = self.client.get(f"/v1/investigations/{inv}")
        self.assertEqual(g.status_code, 200)
        self.assertEqual(g.json()["investigation_id"], inv)

    def test_03_discovery_fixture_post_get(self):
        r = self.client.post(
            "/v1/investigations",
            json={
                "existing_land_profile_reference": CPER_REF,
                "mode": "DISCOVERY",
                "intended_operation": None,
                "planned_actions": [],
                "execution_source": "DEMO_FIXTURE",
                "mireye_mode": "BLOCKED_EXTERNAL",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        queued = r.json()
        self.assertEqual(queued["status"], "QUEUED")
        self.assertEqual(queued["mode"], "DISCOVERY")
        self.assertIsNone(queued["intended_operation"])
        self.assertEqual(queued["replay_label"], REPLAY_LABEL)
        body = _terminal(self.client, queued)
        if body.get("presentation"):
            self.assertFalse(body["presentation"]["scientific_priority_change"])

    def test_04_five_section_report(self):
        created = _terminal(
            self.client,
            self.client.post(
                "/v1/investigations",
                json={
                    "existing_land_profile_reference": CPER_REF,
                    "mode": "GOAL_DIRECTED",
                    "intended_operation": "COW_CALF_OPERATION",
                    "execution_source": "DEMO_FIXTURE",
                    "mireye_mode": "BLOCKED_EXTERNAL",
                },
            ).json(),
        )
        r = self.client.get(f"/v1/investigations/{created['investigation_id']}/report")
        self.assertEqual(r.status_code, 200)
        sections = r.json()["sections"]
        for name in (
            "Property",
            "Land & Resources",
            "Resilience & Hazards",
            "Operation Comparison",
            "Diligence Plan",
        ):
            self.assertIn(name, sections)
        self.assertEqual(
            r.json()["explanation_binding_hash"], r.json()["match_result_hash"]
        )

    def test_05_trace_endpoint(self):
        created = self.client.post(
            "/v1/investigations",
            json={
                "existing_land_profile_reference": CPER_REF,
                "mode": "DISCOVERY",
                "execution_source": "DEMO_FIXTURE",
                "mireye_mode": "BLOCKED_EXTERNAL",
            },
        ).json()
        r = self.client.get(f"/v1/investigations/{created['investigation_id']}/trace")
        self.assertEqual(r.status_code, 200)
        trace = r.json()
        self.assertTrue(trace.get("steps"))
        self.assertIn("deterministic_execution_hash", trace)
        blob = str(trace).lower()
        self.assertNotIn("authorization", blob)
        self.assertNotIn("bearer ", blob)

    def test_06_mode_intended_operation_validation(self):
        r = self.client.post(
            "/v1/investigations",
            json={
                "existing_land_profile_reference": CPER_REF,
                "mode": "GOAL_DIRECTED",
                "intended_operation": None,
                "execution_source": "DEMO_FIXTURE",
            },
        )
        self.assertEqual(r.status_code, 422)

    def test_07_multiple_parcel_inputs_rejected(self):
        r = self.client.post(
            "/v1/investigations",
            json={
                "address": "1 Main St",
                "existing_land_profile_reference": CPER_REF,
                "mode": "DISCOVERY",
                "execution_source": "DEMO_FIXTURE",
            },
        )
        self.assertEqual(r.status_code, 422)

    def test_08_multiple_feature_geometry_rejected(self):
        r = self.client.post(
            "/v1/investigations",
            json={
                "parcel_geometry": {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {"type": "Point", "coordinates": [0, 0]},
                            "properties": {},
                        },
                        {
                            "type": "Feature",
                            "geometry": {"type": "Point", "coordinates": [1, 1]},
                            "properties": {},
                        },
                    ],
                },
                "mode": "DISCOVERY",
                "execution_source": "EXISTING_LAND_PROFILE",
            },
        )
        self.assertEqual(r.status_code, 422)

    def test_09_address_does_not_silently_use_fixture(self):
        r = self.client.post(
            "/v1/investigations",
            json={
                "address": "123 Ranch Rd, Nunn, CO",
                "mode": "GOAL_DIRECTED",
                "intended_operation": "COW_CALF_OPERATION",
                "execution_source": "DEMO_FIXTURE",
            },
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "BLOCKED_EXTERNAL")
        self.assertIsNone(body.get("unified_output"))
        lim = " ".join(body.get("limitations") or [])
        self.assertIn("no_automatic_fixture_substitution", lim)
        self.assertIn("no_fabricated_geometry", lim)

    def test_10_explicit_fixture_replay_label(self):
        r = self.client.post(
            "/v1/investigations",
            json={
                "existing_land_profile_reference": CPER_REF,
                "mode": "DISCOVERY",
                "execution_source": "DEMO_FIXTURE",
                "mireye_mode": "BLOCKED_EXTERNAL",
            },
        )
        queued = r.json()
        self.assertEqual(queued["status"], "QUEUED")
        self.assertEqual(queued["replay_label"], REPLAY_LABEL)
        self.assertIn(REPLAY_LABEL, queued["limitations"])
        body = _terminal(self.client, queued)
        self.assertIn(REPLAY_LABEL, body["limitations"])

    def test_11_mireye_blocked_external_visible(self):
        created = _terminal(
            self.client,
            self.client.post(
                "/v1/investigations",
                json={
                    "existing_land_profile_reference": CPER_REF,
                    "mode": "GOAL_DIRECTED",
                    "intended_operation": "COW_CALF_OPERATION",
                    "execution_source": "DEMO_FIXTURE",
                    "mireye_mode": "BLOCKED_EXTERNAL",
                },
            ).json(),
        )
        health = self.client.get("/health").json()
        self.assertIn(
            health["live_mireye_availability"], {"BLOCKED_EXTERNAL", "NOT_CONFIGURED"}
        )
        trace = self.client.get(
            f"/v1/investigations/{created['investigation_id']}/trace"
        ).json()
        mireye_steps = [
            s for s in trace["steps"] if str(s.get("tool_id", "")).startswith("mireye.")
        ]
        self.assertTrue(mireye_steps)
        self.assertTrue(
            all(s["status"] == "BLOCKED_EXTERNAL" for s in mireye_steps)
        )
        uo = created["unified_output"]
        self.assertTrue(
            any(
                m.get("disposition") == "BLOCKED_EXTERNAL"
                for m in (uo.get("mireye_context") or [])
            )
        )

    def test_12_existing_land_profile_reuse(self):
        r = self.client.post(
            "/v1/investigations",
            json={
                "existing_land_profile_reference": CPER_REF,
                "mode": "DISCOVERY",
                "execution_source": "EXISTING_LAND_PROFILE",
                "mireye_mode": "BLOCKED_EXTERNAL",
            },
        )
        self.assertEqual(r.status_code, 200)
        body = _terminal(self.client, r.json())
        self.assertIsNone(body.get("replay_label"))
        self.assertEqual(body["execution_source"], "EXISTING_LAND_PROFILE")
        self.assertIn(body["status"], {"COMPLETED", "PARTIAL"})

    def test_13_path_traversal_rejected(self):
        r = self.client.post(
            "/v1/investigations",
            json={
                "existing_land_profile_reference": "test-data/../../.env",
                "mode": "DISCOVERY",
                "execution_source": "EXISTING_LAND_PROFILE",
            },
        )
        self.assertEqual(r.status_code, 400)

    def test_14_no_batch_endpoint(self):
        r = self.client.get("/v1/investigations")
        self.assertEqual(r.status_code, 405)
        r2 = self.client.post("/v1/investigations/batch", json={})
        self.assertIn(r2.status_code, {404, 405, 422})

    def test_15_no_f09_icp_in_trace(self):
        created = self.client.post(
            "/v1/investigations",
            json={
                "existing_land_profile_reference": CPER_REF,
                "mode": "DISCOVERY",
                "execution_source": "DEMO_FIXTURE",
                "mireye_mode": "BLOCKED_EXTERNAL",
            },
        ).json()
        tools = {
            s["tool_id"]
            for s in self.client.get(
                f"/v1/investigations/{created['investigation_id']}/trace"
            ).json()["steps"]
        }
        self.assertTrue(all(not t.startswith("F09") for t in tools))
        self.assertNotIn("ICP_FINDER", tools)
        self.assertNotIn("BATCH_PARCEL_SEARCH", tools)

    def test_16_engine_labels_unchanged(self):
        body = _terminal(
            self.client,
            self.client.post(
                "/v1/investigations",
                json={
                    "existing_land_profile_reference": CPER_REF,
                    "mode": "GOAL_DIRECTED",
                    "intended_operation": "COW_CALF_OPERATION",
                    "execution_source": "DEMO_FIXTURE",
                    "mireye_mode": "BLOCKED_EXTERNAL",
                },
            ).json(),
        )
        ex = body["unified_output"].get("explanation") or {}
        self.assertFalse(ex.get("may_alter_decision_labels", True))
        self.assertFalse(ex.get("llm_override_permitted", True))

    def test_17_explanation_hash_binding(self):
        body = _terminal(
            self.client,
            self.client.post(
                "/v1/investigations",
                json={
                    "existing_land_profile_reference": CPER_REF,
                    "mode": "DISCOVERY",
                    "execution_source": "DEMO_FIXTURE",
                    "mireye_mode": "BLOCKED_EXTERNAL",
                },
            ).json(),
        )
        uo = body["unified_output"]
        self.assertEqual(uo["explanation_binding_hash"], uo["match_result_hash"])
        self.assertEqual(
            uo["explanation"]["bound_to_match_result_hash"], uo["match_result_hash"]
        )

    def test_18_credentials_absent_from_responses(self):
        body = self.client.post(
            "/v1/investigations",
            json={
                "existing_land_profile_reference": CPER_REF,
                "mode": "DISCOVERY",
                "execution_source": "DEMO_FIXTURE",
                "mireye_mode": "BLOCKED_EXTERNAL",
            },
        ).json()
        blob = str(body).lower()
        self.assertNotIn("authorization", blob)
        self.assertNotIn("api_key", blob)
        self.assertNotIn("bearer ", blob)

    def test_19_deterministic_repeated_execution_hashes(self):
        payload = {
            "existing_land_profile_reference": CPER_REF,
            "mode": "GOAL_DIRECTED",
            "intended_operation": "COW_CALF_OPERATION",
            "execution_source": "DEMO_FIXTURE",
            "mireye_mode": "BLOCKED_EXTERNAL",
        }
        a = _terminal(self.client, self.client.post("/v1/investigations", json=payload).json())
        b = _terminal(self.client, self.client.post("/v1/investigations", json=payload).json())
        self.assertEqual(
            a["deterministic_execution_hash"], b["deterministic_execution_hash"]
        )
        self.assertEqual(a["plan_sha256"], b["plan_sha256"])

    def test_20_unknown_investigation_404(self):
        r = self.client.get("/v1/investigations/inv_does_not_exist")
        self.assertEqual(r.status_code, 404)

    def test_21_intent_parse_goal_directed(self):
        r = self.client.post(
            "/v1/intent/parse",
            json={
                "user_request": (
                    "I want to know whether this parcel can support a cow-calf "
                    "operation, and I may drill a well."
                ),
                "existing_land_profile_reference": CPER_REF,
                "provider": "FIXTURE",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["intent_status"], "PARSED")
        self.assertEqual(body["mode"], "GOAL_DIRECTED")
        self.assertEqual(body["intended_operation"], "COW_CALF_OPERATION")
        self.assertIn("DRILL_WELL", body["planned_actions"])

    def test_22_intent_parse_batch_rejected(self):
        r = self.client.post(
            "/v1/intent/parse",
            json={
                "user_request": "Find the best 50 ranches in Colorado.",
                "provider": "FIXTURE",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["intent_status"], "REJECTED")
        self.assertEqual(body["rejection_code"], "REJECTED_OUT_OF_SCOPE_BATCH")

    def test_23_buyer_report_generate_and_get(self):
        created = self.client.post(
            "/v1/investigations",
            json={
                "existing_land_profile_reference": CPER_REF,
                "mode": "GOAL_DIRECTED",
                "intended_operation": "COW_CALF_OPERATION",
                "planned_actions": [],
                "execution_source": "DEMO_FIXTURE",
                "mireye_mode": "BLOCKED_EXTERNAL",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        inv = created.json()["investigation_id"]
        r = self.client.post(
            f"/v1/investigations/{inv}/buyer-report",
            json={"provider": "FIXTURE"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["validation_status"], "PASSED", body.get("validation_violations"))
        self.assertTrue(body["displayable"])
        self.assertIsNotNone(body["buyer_report"])
        self.assertIn("executive_summary", body["buyer_report"])
        blob = str(body).lower()
        self.assertNotIn("api_key", blob)
        self.assertNotIn("bearer ", blob)
        g = self.client.get(f"/v1/investigations/{inv}/buyer-report")
        self.assertEqual(g.status_code, 200)
        self.assertEqual(g.json()["validation_status"], "PASSED")

    def test_24_buyer_report_openai_without_key_not_fixture_substituted(self):
        import os

        for key in ("RANGEMATCH_LLM_API_KEY", "OPENAI_API_KEY"):
            os.environ.pop(key, None)
        created = self.client.post(
            "/v1/investigations",
            json={
                "existing_land_profile_reference": CPER_REF,
                "mode": "DISCOVERY",
                "intended_operation": None,
                "execution_source": "DEMO_FIXTURE",
                "mireye_mode": "BLOCKED_EXTERNAL",
            },
        ).json()
        inv = created["investigation_id"]
        r = self.client.post(
            f"/v1/investigations/{inv}/buyer-report",
            json={"provider": "OPENAI"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["validation_status"], "FAILED")
        self.assertFalse(body["displayable"])
        self.assertIsNone(body["buyer_report"])
        self.assertEqual(body["report_provenance"]["provider_status"], "NOT_CONFIGURED")

    def test_25_health_includes_llm_summary(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        llm = r.json().get("llm") or {}
        self.assertIn(llm.get("provider_status"), {"FIXTURE", "OK", "NOT_CONFIGURED"})
        self.assertNotIn("api_key_value", str(llm).lower())


    def test_26_async_queued_then_poll_trace(self):
        from rangematch.investigation_job import (
            flush_held_investigation_jobs_for_tests,
            set_hold_investigation_jobs_for_tests,
        )

        set_hold_investigation_jobs_for_tests(True)
        try:
            r = self.client.post(
                "/v1/investigations",
                json={
                    "existing_land_profile_reference": CPER_REF,
                    "mode": "DISCOVERY",
                    "execution_source": "DEMO_FIXTURE",
                    "mireye_mode": "BLOCKED_EXTERNAL",
                },
            )
            self.assertEqual(r.status_code, 200)
            queued = r.json()
            self.assertEqual(queued["status"], "QUEUED")
            inv = queued["investigation_id"]
            mid = self.client.get(f"/v1/investigations/{inv}").json()
            self.assertEqual(mid["status"], "QUEUED")
            self.assertIsNone(mid.get("unified_output"))
            trace = self.client.get(f"/v1/investigations/{inv}/trace").json()
            self.assertEqual(trace.get("execution_status"), "QUEUED")
            self.assertTrue(trace.get("steps"))
            self.assertTrue(all(s["status"] == "PENDING" for s in trace["steps"]))
            report = self.client.get(f"/v1/investigations/{inv}/report")
            self.assertEqual(report.status_code, 409)
            buyer = self.client.post(
                f"/v1/investigations/{inv}/buyer-report", json={"provider": "FIXTURE"}
            )
            self.assertEqual(buyer.status_code, 409)
            flush_held_investigation_jobs_for_tests()
            done = self.client.get(f"/v1/investigations/{inv}").json()
            self.assertIn(done["status"], {"COMPLETED", "PARTIAL"})
            self.assertIsNotNone(done.get("unified_output"))
        finally:
            set_hold_investigation_jobs_for_tests(False)

    def test_27_duplicate_job_claim_is_single_flight(self):
        from rangematch.investigation_job import run_investigation_job
        from rangematch.investigation_store import get_investigation_store

        queued = self.client.post(
            "/v1/investigations",
            json={
                "existing_land_profile_reference": CPER_REF,
                "mode": "DISCOVERY",
                "execution_source": "DEMO_FIXTURE",
                "mireye_mode": "BLOCKED_EXTERNAL",
            },
        ).json()
        inv = queued["investigation_id"]
        # Background already completed under TestClient; second claim must no-op.
        before = get_investigation_store().get(inv)
        run_investigation_job(inv)
        after = get_investigation_store().get(inv)
        self.assertEqual(before["status"], after["status"])
        self.assertEqual(
            before.get("deterministic_execution_hash"),
            after.get("deterministic_execution_hash"),
        )



if __name__ == "__main__":
    unittest.main()
