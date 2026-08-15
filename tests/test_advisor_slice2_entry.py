"""Slice 2: free-form entry outcomes + isolated verified Nambe demo run."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from rangematch.advisor_agent import (
    DEMO_SCENARIO_NAMBE_CATTLE_V1,
    NAMBE_DEMO_ADDRESS,
    OUTCOME_PARCEL_NEEDS_CONFIRMATION,
    OUTCOME_PARCEL_NOT_FOUND,
    OUTCOME_PARCEL_SERVICE_UNAVAILABLE,
    RUN_MODE_CUSTOM,
    RUN_MODE_VERIFIED_DEMO,
    TRACK_GENERIC,
    enqueue_advisor_run,
    execute_advisor_run,
    nambe_demo_scenario_claims,
    reset_advisor_runs_for_tests,
    run_cper_advisor_agent,
    set_advisor_mireye_hooks_for_tests,
    _lookup_transport_result,
    _unit_test_mireye_request,
)
from rangematch.api import app
from rangematch.mireye_parcel_resolver import map_mireye_lookup_to_parcel
from rangematch.advisor_parcel_gate import stage_mireye_mapping_for_confirmation
from rangematch.parcel_resolution import confirm_selected_parcel
from rangematch.parcel_resolution_store import get_parcel_resolution_store


NAMBE_POLYGON = [
    [-105.24, 39.62],
    [-105.23, 39.62],
    [-105.23, 39.61],
    [-105.24, 39.61],
    [-105.24, 39.62],
]


def _nambe_payload() -> dict:
    return {
        "disposition": "resolved",
        "confidence": 0.94,
        "resolved_address": NAMBE_DEMO_ADDRESS.upper(),
        "match_method": "geocode_rooftop+point_in_parcel",
        "lat": 39.615,
        "lng": -105.235,
        "resolved_location": {"lat": 39.615, "lng": -105.235, "source": "address"},
        "fetched_at": "2026-08-14T00:00:00+00:00",
        "request_id": "slice2_nambe",
        "parcel": {
            "parcel_id": "NAMBE-DEMO-001",
            "apn": "NAMBE-DEMO-001",
            "address": NAMBE_DEMO_ADDRESS.upper(),
            "geometry": {"type": "Polygon", "coordinates": [NAMBE_POLYGON]},
        },
        "fields": {},
        "partial_failures": [],
    }


def _confirm_nambe() -> str:
    mapping = map_mireye_lookup_to_parcel(_nambe_payload())
    staged = stage_mireye_mapping_for_confirmation(
        address=NAMBE_DEMO_ADDRESS, mapping=mapping
    )
    candidate_id = staged["selection"]["selected_candidate_id"]
    geometry_hash = staged["candidates"][0]["geometry_hash"]
    confirmed = confirm_selected_parcel(
        staged,
        candidate_id=candidate_id,
        confirm_boundary=True,
        expected_geometry_hash=geometry_hash,
    )
    get_parcel_resolution_store().put(confirmed)
    return confirmed["resolution_id"]


class Slice2PlaceEntryTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_advisor_runs_for_tests()
        get_parcel_resolution_store().clear()

    def tearDown(self) -> None:
        set_advisor_mireye_hooks_for_tests(request_fn=None, lookup_fn=None)
        reset_advisor_runs_for_tests()

    def test_business_no_match_is_parcel_not_found_not_service_failure(self) -> None:
        def lookup_fn(place: str, **kwargs):
            return _lookup_transport_result(
                ok=True,
                address=place,
                disposition="no_match",
                sanitized_response={
                    "disposition": "no_match",
                    "reason": "unaddressed_or_no_match",
                },
            )

        set_advisor_mireye_hooks_for_tests(
            request_fn=_unit_test_mireye_request, lookup_fn=lookup_fn
        )
        failed = run_cper_advisor_agent(
            address="100 Main St, Columbus", fixture_id=None, run_mode=RUN_MODE_CUSTOM
        )
        self.assertEqual(failed["status"], "FAILED")
        self.assertEqual(failed["investigation_outcome"], OUTCOME_PARCEL_NOT_FOUND)
        self.assertIsNone(failed["packet"])
        self.assertIsNone(failed["brief"])
        self.assertNotEqual(
            failed["investigation_outcome"], OUTCOME_PARCEL_SERVICE_UNAVAILABLE
        )

    def test_http_404_transport_is_service_unavailable_not_not_found(self) -> None:
        def lookup_fn(place: str, **kwargs):
            return _lookup_transport_result(
                ok=False,
                address=place,
                error_class="HTTP_404",
                http_status=404,
            )

        set_advisor_mireye_hooks_for_tests(
            request_fn=_unit_test_mireye_request, lookup_fn=lookup_fn
        )
        failed = run_cper_advisor_agent(
            address="404 Missing Ranch, Nowhere, WY",
            fixture_id=None,
            run_mode=RUN_MODE_CUSTOM,
        )
        self.assertEqual(failed["investigation_outcome"], OUTCOME_PARCEL_SERVICE_UNAVAILABLE)
        self.assertNotEqual(failed["investigation_outcome"], OUTCOME_PARCEL_NOT_FOUND)
        self.assertIsNone(failed["packet"])

    def test_ambiguous_with_candidates_stays_needs_confirmation(self) -> None:
        def lookup_fn(place: str, **kwargs):
            return _lookup_transport_result(
                ok=True,
                address=place,
                disposition="clarify",
                sanitized_response={
                    "disposition": "clarify",
                    "confidence": 0.55,
                    "resolved_address": place,
                    "fetched_at": "2026-08-14T00:00:00+00:00",
                    "request_id": "slice2_clarify",
                    "candidates": [
                        {
                            "parcel_id": "A",
                            "address": "A RD",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [NAMBE_POLYGON],
                            },
                        },
                        {
                            "parcel_id": "B",
                            "address": "B RD",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [
                                    [
                                        [-105.22, 39.62],
                                        [-105.21, 39.62],
                                        [-105.21, 39.61],
                                        [-105.22, 39.61],
                                        [-105.22, 39.62],
                                    ]
                                ],
                            },
                        },
                    ],
                    "fields": {},
                    "partial_failures": [],
                },
            )

        set_advisor_mireye_hooks_for_tests(
            request_fn=_unit_test_mireye_request, lookup_fn=lookup_fn
        )
        result = run_cper_advisor_agent(
            address="200 Split Ranch Rd, Weld County, CO 80701",
            fixture_id=None,
            run_mode=RUN_MODE_CUSTOM,
        )
        self.assertEqual(result["investigation_outcome"], OUTCOME_PARCEL_NEEDS_CONFIRMATION)
        self.assertGreaterEqual(len(result.get("parcel_candidates") or []), 2)
        self.assertIsNone(result["packet"])

    def test_failed_custom_does_not_auto_start_nambe(self) -> None:
        calls: list[str] = []

        def lookup_fn(place: str, **kwargs):
            calls.append(place)
            return _lookup_transport_result(
                ok=False,
                address=place,
                error_class="TIMEOUT",
                http_status=None,
            )

        set_advisor_mireye_hooks_for_tests(
            request_fn=_unit_test_mireye_request, lookup_fn=lookup_fn
        )
        failed = run_cper_advisor_agent(
            address="Timeout Ranch, Slow County, WY",
            fixture_id=None,
            run_mode=RUN_MODE_CUSTOM,
        )
        self.assertEqual(failed["investigation_outcome"], OUTCOME_PARCEL_SERVICE_UNAVAILABLE)
        self.assertEqual(calls, ["Timeout Ranch, Slow County, WY"])
        self.assertNotIn(NAMBE_DEMO_ADDRESS, calls)
        self.assertEqual(failed["run_mode"], RUN_MODE_CUSTOM)

    def test_verified_demo_creates_isolated_new_run(self) -> None:
        def lookup_fn(place: str, **kwargs):
            if "Timeout" in place:
                return _lookup_transport_result(
                    ok=False, address=place, error_class="TIMEOUT"
                )
            return _lookup_transport_result(
                ok=True,
                address=place,
                disposition="resolved",
                sanitized_response=_nambe_payload(),
            )

        set_advisor_mireye_hooks_for_tests(
            request_fn=_unit_test_mireye_request, lookup_fn=lookup_fn
        )
        failed = run_cper_advisor_agent(
            address="Timeout Ranch, Slow County, WY",
            fixture_id=None,
            run_mode=RUN_MODE_CUSTOM,
        )
        failed_id = failed["run_id"]

        queued = enqueue_advisor_run(
            run_mode=RUN_MODE_VERIFIED_DEMO,
            demo_scenario_id=DEMO_SCENARIO_NAMBE_CATTLE_V1,
        )
        self.assertNotEqual(queued["run_id"], failed_id)
        self.assertEqual(queued["run_mode"], RUN_MODE_VERIFIED_DEMO)
        self.assertEqual(queued["demo_scenario_id"], DEMO_SCENARIO_NAMBE_CATTLE_V1)
        self.assertEqual(queued["address"], NAMBE_DEMO_ADDRESS)
        self.assertIsNone(queued.get("fixture_id"))

        resolution_id = _confirm_nambe()
        demo = enqueue_advisor_run(
            run_mode=RUN_MODE_VERIFIED_DEMO,
            demo_scenario_id=DEMO_SCENARIO_NAMBE_CATTLE_V1,
            parcel_resolution_id=resolution_id,
        )
        result = execute_advisor_run(demo["run_id"])
        self.assertEqual(result["run_mode"], RUN_MODE_VERIFIED_DEMO)
        self.assertEqual(result["address"], NAMBE_DEMO_ADDRESS)
        self.assertEqual(result["track"], TRACK_GENERIC)
        claims = (result.get("packet") or {}).get("listing_claims") or []
        self.assertTrue(claims)
        self.assertTrue(all(row.get("provenance") == "DEMO_SCENARIO_CLAIM" for row in claims))
        self.assertEqual(
            {row["claim_id"] for row in claims},
            {row["claim_id"] for row in nambe_demo_scenario_claims()},
        )
        blob = repr(result.get("packet")).lower()
        self.assertNotIn("timeout ranch", blob)
        self.assertNotIn("slow county", blob)

    def test_api_verified_demo_does_not_require_client_address(self) -> None:
        client = TestClient(app)
        response = client.post(
            "/v1/advisor/runs",
            json={
                "run_mode": "VERIFIED_DEMO",
                "demo_scenario_id": "NAMBE_CATTLE_V1",
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["run_mode"], "VERIFIED_DEMO")
        self.assertEqual(body["demo_scenario_id"], "NAMBE_CATTLE_V1")
        self.assertEqual(body["address"], NAMBE_DEMO_ADDRESS)


if __name__ == "__main__":
    unittest.main()
