"""Advisor parcel confirmation gate — no live network."""

from __future__ import annotations

import unittest

from rangematch.advisor_agent import (
    OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED,
    OUTCOME_PARCEL_NEEDS_CONFIRMATION,
    TRACK_GENERIC,
    reset_advisor_runs_for_tests,
    run_cper_advisor_agent,
    set_advisor_mireye_hooks_for_tests,
    _lookup_transport_result,
    _unit_test_mireye_request,
)
from rangematch.advisor_parcel_gate import (
    AdvisorParcelGateError,
    require_confirmed_parcel,
    stage_mireye_mapping_for_confirmation,
)
from rangematch.mireye_parcel_resolver import map_mireye_lookup_to_parcel
from rangematch.parcel_resolution import confirm_selected_parcel
from rangematch.parcel_resolution_store import get_parcel_resolution_store

from mireye_lookup_samples import UNIQUE_WITH_POLYGON


class AdvisorParcelGateTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_advisor_runs_for_tests()

    def test_require_confirmed_rejects_unconfirmed(self) -> None:
        mapping = map_mireye_lookup_to_parcel(UNIQUE_WITH_POLYGON)
        staged = stage_mireye_mapping_for_confirmation(
            address=UNIQUE_WITH_POLYGON["normalized_address"],
            mapping=mapping,
        )
        self.assertEqual(staged["status"], "NEEDS_BOUNDARY_CONFIRMATION")
        with self.assertRaises(AdvisorParcelGateError) as ctx:
            require_confirmed_parcel(staged)
        self.assertEqual(ctx.exception.code, "PARCEL_NOT_CONFIRMED")

    def test_unique_polygon_stages_resolution_and_needs_confirmation(self) -> None:
        address = UNIQUE_WITH_POLYGON["normalized_address"]

        def lookup_fn(addr: str, **kwargs):
            return _lookup_transport_result(
                ok=True,
                address=addr,
                disposition="resolved",
                sanitized_response=UNIQUE_WITH_POLYGON,
            )

        set_advisor_mireye_hooks_for_tests(
            request_fn=_unit_test_mireye_request, lookup_fn=lookup_fn
        )
        result = run_cper_advisor_agent(address=address)
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_PARCEL_NEEDS_CONFIRMATION
        )
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertFalse(result["parcel_geometry_confirmed"])
        self.assertTrue(result["parcel_resolution_id"])
        statuses = {row["step_id"]: row["status"] for row in result["steps"]}
        self.assertEqual(statuses["RESOLVE_PARCEL"], "NEEDS_CONFIRMATION")
        stored = get_parcel_resolution_store().get(result["parcel_resolution_id"])
        self.assertIsNotNone(stored)
        self.assertEqual(stored["status"], "NEEDS_BOUNDARY_CONFIRMATION")
        self.assertIsNone(result["brief"])

    def test_confirmed_non_cper_completes_generic_not_cper_report(self) -> None:
        address = UNIQUE_WITH_POLYGON["normalized_address"]
        mapping = map_mireye_lookup_to_parcel(UNIQUE_WITH_POLYGON)
        staged = stage_mireye_mapping_for_confirmation(address=address, mapping=mapping)
        candidate_id = staged["selection"]["selected_candidate_id"]
        geometry_hash = staged["candidates"][0]["geometry_hash"]
        confirmed = confirm_selected_parcel(
            staged,
            candidate_id=candidate_id,
            confirm_boundary=True,
            expected_geometry_hash=geometry_hash,
        )
        get_parcel_resolution_store().put(confirmed)
        binding = require_confirmed_parcel(confirmed)
        self.assertTrue(binding["parcel_geometry_confirmed"])
        self.assertEqual(binding["confirmation_method"], "USER_BOUNDARY_CONFIRMATION")

        result = run_cper_advisor_agent(
            address=address,
            parcel_resolution_id=confirmed["resolution_id"],
        )
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED
        )
        self.assertEqual(result["track"], TRACK_GENERIC)
        self.assertTrue(result["parcel_geometry_confirmed"])
        self.assertEqual(result["geometry_hash"], geometry_hash)
        self.assertIsNotNone(result["brief"])
        self.assertIsNotNone(result["packet"])
        self.assertEqual(
            result["packet"]["technical_references"]["policy_scope"], "GENERIC_MINIMAL"
        )
        self.assertFalse(result["packet"]["parcel"]["is_engineering_test_geometry"])
        self.assertIsNone(result["limited_investigation"])


if __name__ == "__main__":
    unittest.main()
