"""Three honest Demo endings: complete, partial adapters, needs confirmation."""

from __future__ import annotations

import unittest

from rangematch.advisor_agent import (
    OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED,
    OUTCOME_PARCEL_NEEDS_CONFIRMATION,
    _unit_test_mireye_request,
    reset_advisor_runs_for_tests,
    run_cper_advisor_agent,
    set_advisor_factor_collect_for_tests,
    set_advisor_mireye_hooks_for_tests,
)
from rangematch.advisor_generic_collect import unit_test_factor_collect
from tests.test_advisor_generic_run import _confirm_unique
from tests.test_advisor_mireye_first import _ok_lookup


class AdvisorDemoAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_advisor_runs_for_tests()

    def test_complete_confirmed_path_emits_generic_brief(self) -> None:
        address, resolution_id, _ = _confirm_unique()
        result = run_cper_advisor_agent(
            address=address, parcel_resolution_id=resolution_id
        )
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED
        )
        self.assertEqual(result["brief"]["validation_status"], "PASSED")
        self.assertEqual(
            result["packet"]["technical_references"]["policy_scope"], "GENERIC_MINIMAL"
        )
        self.assertEqual(
            result["brief"]["page_two_actions"]["page_mode"], "PUBLIC_EVIDENCE"
        )
        self.assertFalse(result["packet"]["parcel"]["is_engineering_test_geometry"])

    def test_partial_adapters_still_complete_honestly(self) -> None:
        address, resolution_id, _ = _confirm_unique()

        def collect_fn(**_kwargs):
            base = unit_test_factor_collect()
            base["factor_errors"]["F05_CLIMATE_DROUGHT_EXPOSURE"] = (
                "DEPENDENCY_MISSING:netCDF4"
            )
            base["progress_notes"] = ["F05 unavailable — missing dependency netCDF4"]
            return base

        set_advisor_factor_collect_for_tests(collect_fn)
        result = run_cper_advisor_agent(
            address=address, parcel_resolution_id=resolution_id
        )
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED
        )
        precip = next(
            row
            for row in result["packet"]["observations"]
            if row["observation_id"] == "OBS_PRECIP"
        )
        self.assertEqual(precip["evidence_state"], "SOURCE_UNAVAILABLE")
        self.assertEqual(result["brief"]["validation_status"], "PASSED")

    def test_unconfirmed_address_stops_for_user(self) -> None:
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
                    "request_id": "advisor_clarify_acceptance",
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
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_PARCEL_NEEDS_CONFIRMATION
        )
        self.assertIsNone(result.get("brief"))
        self.assertFalse(result.get("parcel_geometry_confirmed"))


if __name__ == "__main__":
    unittest.main()
