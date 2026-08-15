"""Request-time Advisor Agent: place, agenda, re-run, fail closed."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from rangematch.advisor_agent import (
    CPER_DEMO_ADDRESS,
    OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED,
    OUTCOME_EVIDENCE_INVESTIGATION_INCOMPLETE,
    OUTCOME_PARCEL_SERVICE_UNAVAILABLE,
    reset_advisor_runs_for_tests,
    run_cper_advisor_agent,
    set_advisor_mireye_hooks_for_tests,
    _lookup_transport_result,
    _unit_test_mireye_request,
)
from rangematch.advisor_contract import packet_hash, validate_three_page

ROOT = Path(__file__).resolve().parents[1]
PACKET_PATH = ROOT / "test-data" / "advisor" / "cper_buyer_evidence_packet.json"


class AdvisorAgentRunTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_advisor_runs_for_tests()

    def test_run_executes_agenda_and_returns_this_run_identity(self) -> None:
        first = run_cper_advisor_agent(address=CPER_DEMO_ADDRESS)
        self.assertEqual(first["status"], "SUCCEEDED")
        self.assertEqual(first["address"], CPER_DEMO_ADDRESS)
        self.assertFalse(first["llm_used"])
        self.assertTrue(first["run_id"].startswith("advisor_"))
        self.assertEqual(
            [row["label"] for row in first["steps"]],
            [
                "Accept place",
                "Resolve parcel",
                "Call Mireye",
                "Build agenda",
                "Run agenda",
                "Compare claims",
                "Order actions",
                "Validate brief",
            ],
        )
        self.assertEqual([row["status"] for row in first["steps"]], ["SUCCEEDED"] * 8)
        self.assertEqual(first["mireye_live"]["mode"], "UNIT_TEST_HOOK")
        self.assertTrue(first["mireye_live"]["allow_network"])
        self.assertTrue(first["mireye_live"]["lookup"]["ok"])
        self.assertEqual(first["mireye_live"]["lookup"]["disposition"], "resolved")
        self.assertEqual(
            first["investigation_outcome"], OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED
        )
        self.assertTrue(first["location_resolved"])
        self.assertTrue(first["parcel_geometry_confirmed"])
        self.assertGreaterEqual(len(first["agenda"]), 8)
        self.assertTrue(all(row["status"] != "PENDING" for row in first["agenda"]))
        mireye = next(
            row for row in first["agenda"] if row["step_id"] == "S03_MIREYE_PROPERTY"
        )
        self.assertEqual(mireye["status"], "BLOCKED_EXTERNAL")
        self.assertTrue(
            any("BLOCKED_EXTERNAL" in item for item in first["limitations"])
        )
        self.assertEqual(first["packet_hash"], packet_hash(first["packet"]))
        self.assertEqual(first["brief"]["packet_hash"], first["packet_hash"])
        self.assertEqual(validate_three_page(first["brief"], first["packet"]), [])
        self.assertEqual(
            first["brief"]["page_one_advisor"]["visit_purpose"],
            "VISIT_DEPENDS_ON_DOCUMENT",
        )
        second = run_cper_advisor_agent(address=CPER_DEMO_ADDRESS)
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertEqual(first["packet_hash"], second["packet_hash"])

    def test_failed_step_clears_artifacts_and_names_the_step(self) -> None:
        result = run_cper_advisor_agent(fail_step="RUN_AGENDA")
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["failed_step"], "RUN_AGENDA")
        self.assertIsNone(result["packet"])
        self.assertIsNone(result["brief"])
        statuses = {row["step_id"]: row["status"] for row in result["steps"]}
        self.assertEqual(statuses["ACCEPT_PLACE"], "SUCCEEDED")
        self.assertEqual(statuses["RESOLVE_PARCEL"], "SUCCEEDED")
        self.assertEqual(statuses["CALL_MIREYE"], "SUCCEEDED")
        self.assertEqual(statuses["BUILD_AGENDA"], "SUCCEEDED")
        self.assertEqual(statuses["RUN_AGENDA"], "FAILED")
        self.assertEqual(statuses["COMPARE_CLAIMS"], "PENDING")

    def test_unknown_place_fails_at_resolve(self) -> None:
        result = run_cper_advisor_agent(address="Unknown Ranch, Nowhere, WY")
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["failed_step"], "RESOLVE_PARCEL")
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_PARCEL_SERVICE_UNAVAILABLE
        )
        self.assertIsNone(result["brief"])

    def test_empty_place_fails_at_accept(self) -> None:
        result = run_cper_advisor_agent(fixture_id="SOME_OTHER_RANCH")
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["failed_step"], "ACCEPT_PLACE")
        self.assertIsNone(result["brief"])

    def test_non_cper_unique_resolve_returns_limited_investigation(self) -> None:
        address = "100 Demo Ranch Rd, Weld County, CO 80701"

        def lookup_fn(addr: str, **kwargs):
            return _lookup_transport_result(
                ok=True,
                address=addr,
                disposition="resolved",
                sanitized_response={
                    "disposition": "resolved",
                    "confidence": 0.9,
                    "normalized_address": address,
                    "accuracy_type": "rooftop",
                    "accuracy": 1.0,
                    "match_type": "address",
                    "fetched_at": "2026-08-08T16:00:00+00:00",
                    "request_id": "advisor_non_cper_demo",
                    "lat": 40.5,
                    "lng": -104.9,
                    "resolved_location": {
                        "lat": 40.5,
                        "lng": -104.9,
                        "source": "geocode",
                    },
                    "parcel_unavailable": True,
                    "parcel_unavailable_reason": "no_parcel_at_point",
                    "fields": {},
                    "partial_failures": [],
                },
            )

        set_advisor_mireye_hooks_for_tests(
            request_fn=_unit_test_mireye_request, lookup_fn=lookup_fn
        )
        result = run_cper_advisor_agent(address=address)
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_EVIDENCE_INVESTIGATION_INCOMPLETE
        )
        self.assertTrue(result["location_resolved"])
        self.assertFalse(result["parcel_geometry_confirmed"])
        self.assertIsNone(result["brief"])
        self.assertIsNone(result["packet"])
        self.assertTrue(result["limited_investigation"]["cper_policy_blocked"])

    def test_cper_packet_stays_bound_to_this_run(self) -> None:
        live = run_cper_advisor_agent()
        fixture = json.loads(PACKET_PATH.read_text(encoding="utf-8"))
        self.assertEqual(live["status"], "SUCCEEDED")
        self.assertEqual(validate_three_page(live["brief"], live["packet"]), [])
        if live["packet_hash"] != packet_hash(fixture):
            self.assertEqual(live["packet"]["parcel"]["parcel_id"], fixture["parcel"]["parcel_id"])
