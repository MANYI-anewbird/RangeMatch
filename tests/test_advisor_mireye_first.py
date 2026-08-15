"""Mireye-first Advisor entry + honest investigation outcomes (no live network)."""

from __future__ import annotations

import unittest

from rangematch.advisor_agent import (
    CPER_DEMO_ADDRESS,
    OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED,
    OUTCOME_EVIDENCE_INVESTIGATION_INCOMPLETE,
    OUTCOME_INVESTIGATION_COULD_NOT_COMPLETE,
    OUTCOME_PARCEL_NEEDS_CONFIRMATION,
    OUTCOME_PARCEL_NOT_FOUND,
    OUTCOME_PARCEL_SERVICE_UNAVAILABLE,
    reset_advisor_runs_for_tests,
    run_cper_advisor_agent,
    set_advisor_mireye_hooks_for_tests,
    _lookup_transport_result,
    _unit_test_mireye_request,
)


def _ok_lookup(address: str, response: dict) -> object:
    return _lookup_transport_result(
        ok=True,
        address=address,
        sanitized_response=response,
        disposition=str(response.get("disposition") or ""),
    )


def _fail_lookup(
    address: str,
    *,
    error_class: str,
    http_status: int | None = None,
) -> object:
    return _lookup_transport_result(
        ok=False,
        address=address,
        error_class=error_class,
        http_status=http_status,
        limitations=[f"unit test hook; simulated {error_class}"],
    )


class AdvisorMireyeFirstTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_advisor_runs_for_tests()

    def test_cper_still_completes_via_mireye_then_engineering_bind(self) -> None:
        result = run_cper_advisor_agent(address=CPER_DEMO_ADDRESS)
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED
        )
        self.assertTrue(result["location_resolved"])
        self.assertTrue(result["parcel_geometry_confirmed"])
        self.assertTrue(result["mireye_live"]["lookup"]["ok"])
        self.assertEqual(result["mireye_live"]["lookup"]["disposition"], "resolved")
        self.assertIsNotNone(result["brief"])
        self.assertIsNotNone(result["packet"])

    def test_unique_high_confidence_non_cper_is_incomplete_not_full_report(self) -> None:
        address = "300 Random Ranch Rd, Weld County, CO 80701"

        def lookup_fn(addr: str, **kwargs):
            return _ok_lookup(
                addr,
                {
                    "disposition": "resolved",
                    "confidence": 0.91,
                    "normalized_address": address,
                    "accuracy_type": "rooftop",
                    "accuracy": 1.0,
                    "match_type": "address",
                    "fetched_at": "2026-08-08T16:00:00+00:00",
                    "request_id": "advisor_unique_non_cper",
                    "lat": 40.5,
                    "lng": -104.9,
                    "resolved_location": {"lat": 40.5, "lng": -104.9, "source": "geocode"},
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
        limited = result["limited_investigation"]
        self.assertIsNotNone(limited)
        self.assertTrue(limited["cper_policy_blocked"])
        self.assertFalse(limited["full_buyer_report"])
        statuses = {row["step_id"]: row["status"] for row in result["steps"]}
        self.assertEqual(statuses["RESOLVE_PARCEL"], "SUCCEEDED")
        self.assertEqual(statuses["BUILD_AGENDA"], "SKIPPED")
        self.assertEqual(statuses["VALIDATE_BRIEF"], "SKIPPED")

    def test_multi_candidate_needs_confirmation(self) -> None:
        address = "302 Split Ranch Rd, Weld County, CO 80701"

        def lookup_fn(addr: str, **kwargs):
            return _ok_lookup(
                addr,
                {
                    "disposition": "clarify",
                    "confidence": 0.55,
                    "normalized_address": address,
                    "accuracy_type": "rooftop",
                    "fetched_at": "2026-08-08T16:00:00+00:00",
                    "request_id": "advisor_clarify",
                    "lat": 40.495,
                    "lng": -104.885,
                    "candidates": [
                        {
                            "label": "West tract",
                            "parcel_id": "A",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [
                                    [
                                        [-104.9, 40.5],
                                        [-104.89, 40.5],
                                        [-104.89, 40.49],
                                        [-104.9, 40.49],
                                        [-104.9, 40.5],
                                    ]
                                ],
                            },
                        },
                        {
                            "label": "East tract",
                            "parcel_id": "B",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [
                                    [
                                        [-104.88, 40.5],
                                        [-104.87, 40.5],
                                        [-104.87, 40.49],
                                        [-104.88, 40.49],
                                        [-104.88, 40.5],
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
        result = run_cper_advisor_agent(address=address)
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertIsNone(result["failed_step"])
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_PARCEL_NEEDS_CONFIRMATION
        )
        self.assertFalse(result["parcel_geometry_confirmed"])
        self.assertGreaterEqual(len(result["parcel_candidates"]), 2)
        self.assertTrue(result["parcel_resolution_id"])
        statuses = {row["step_id"]: row["status"] for row in result["steps"]}
        self.assertEqual(statuses["RESOLVE_PARCEL"], "NEEDS_CONFIRMATION")
        self.assertEqual(statuses["VALIDATE_BRIEF"], "SKIPPED")
        self.assertIsNone(result["brief"])

    def test_low_confidence_needs_confirmation(self) -> None:
        address = "305 Rural Mile Marker Rd, Weld County, CO 80701"

        def lookup_fn(addr: str, **kwargs):
            return _ok_lookup(
                addr,
                {
                    "disposition": "resolved",
                    "confidence": 0.5,
                    "normalized_address": address,
                    "accuracy_type": "range_interpolation",
                    "accuracy": 0.3,
                    "match_type": "range_interpolation",
                    "fetched_at": "2026-08-08T16:00:00+00:00",
                    "request_id": "advisor_low_conf",
                    "lat": 40.6,
                    "lng": -104.7,
                    "parcel": {
                        "parcel_id": "SHOULD_NOT_AUTO_USE",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [-104.7, 40.61],
                                    [-104.69, 40.61],
                                    [-104.69, 40.6],
                                    [-104.7, 40.6],
                                    [-104.7, 40.61],
                                ]
                            ],
                        },
                    },
                    "fields": {},
                    "partial_failures": [],
                },
            )

        set_advisor_mireye_hooks_for_tests(
            request_fn=_unit_test_mireye_request, lookup_fn=lookup_fn
        )
        result = run_cper_advisor_agent(address=address)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_PARCEL_NOT_FOUND
        )
        statuses = {row["step_id"]: row["status"] for row in result["steps"]}
        self.assertEqual(statuses["RESOLVE_PARCEL"], "FAILED")
        self.assertFalse(result["parcel_geometry_confirmed"])
        self.assertIsNone(result["packet"])
        self.assertIsNone(result["brief"])
        self.assertIn("geocode_quality_insufficient", (result.get("error") or "").lower())

    def test_http_404_could_not_complete_preserves_lookup_status(self) -> None:
        address = "404 Missing Ranch, Nowhere, WY"

        def lookup_fn(addr: str, **kwargs):
            return _fail_lookup(addr, error_class="HTTP_404", http_status=404)

        set_advisor_mireye_hooks_for_tests(
            request_fn=_unit_test_mireye_request, lookup_fn=lookup_fn
        )
        result = run_cper_advisor_agent(address=address)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["failed_step"], "RESOLVE_PARCEL")
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_PARCEL_SERVICE_UNAVAILABLE
        )
        self.assertFalse(result["location_resolved"])
        lookup = (result.get("mireye_live") or {}).get("lookup") or {}
        self.assertEqual(lookup.get("error_class"), "HTTP_404")
        self.assertEqual(lookup.get("http_status"), 404)

    def test_timeout_could_not_complete(self) -> None:
        address = "Timeout Ranch, Slow County, WY"

        def lookup_fn(addr: str, **kwargs):
            return _fail_lookup(addr, error_class="TIMEOUT", http_status=None)

        set_advisor_mireye_hooks_for_tests(
            request_fn=_unit_test_mireye_request, lookup_fn=lookup_fn
        )
        result = run_cper_advisor_agent(address=address)
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_PARCEL_SERVICE_UNAVAILABLE
        )
        lookup = (result.get("mireye_live") or {}).get("lookup") or {}
        self.assertEqual(lookup.get("error_class"), "TIMEOUT")

    def test_resolve_calls_mireye_before_any_fixture_scenario_match(self) -> None:
        """Even the CPER demo address must hit the lookup hook first."""
        calls: list[str] = []

        def lookup_fn(addr: str, **kwargs):
            calls.append(addr)
            return _fail_lookup(addr, error_class="FORCED_FIRST", http_status=503)

        set_advisor_mireye_hooks_for_tests(
            request_fn=_unit_test_mireye_request, lookup_fn=lookup_fn
        )
        result = run_cper_advisor_agent(address=CPER_DEMO_ADDRESS)
        self.assertEqual(calls, [CPER_DEMO_ADDRESS])
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_PARCEL_SERVICE_UNAVAILABLE
        )
        self.assertIsNone(result["brief"])


if __name__ == "__main__":
    unittest.main()
