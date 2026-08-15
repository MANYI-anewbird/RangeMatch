"""Slice 3: minimal Deal Context create / read / update / isolation."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from rangematch.advisor_agent import (
    DEMO_SCENARIO_NAMBE_CATTLE_V1,
    NAMBE_DEMO_ADDRESS,
    RUN_MODE_CUSTOM,
    RUN_MODE_VERIFIED_DEMO,
    TRACK_GENERIC,
    enqueue_advisor_run,
    execute_advisor_run,
    get_advisor_deal_context,
    nambe_demo_scenario_claims,
    reset_advisor_runs_for_tests,
    run_cper_advisor_agent,
    set_advisor_mireye_hooks_for_tests,
    update_advisor_deal_context,
    _lookup_transport_result,
    _unit_test_mireye_request,
)
from rangematch.advisor_deal_context import (
    DealContextError,
    create_deal_context,
    get_deal_context_for_run,
    update_deal_context,
)
from rangematch.advisor_parcel_gate import (
    require_confirmed_parcel,
    stage_mireye_mapping_for_confirmation,
)
from rangematch.api import app
from rangematch.mireye_parcel_resolver import map_mireye_lookup_to_parcel
from rangematch.parcel_resolution import confirm_selected_parcel
from rangematch.parcel_resolution_store import get_parcel_resolution_store

NAMBE_POLYGON = [
    [-105.24, 39.62],
    [-105.23, 39.62],
    [-105.23, 39.61],
    [-105.24, 39.61],
    [-105.24, 39.62],
]
TX_POLYGON = [
    [-97.50, 30.21],
    [-97.49, 30.21],
    [-97.49, 30.20],
    [-97.50, 30.20],
    [-97.50, 30.21],
]
RURAL_TX = "480 Berdoll Ln, Cedar Creek, TX 78612"


def _payload(address: str, *, lat: float, lng: float, ring: list, parcel_id: str) -> dict:
    return {
        "disposition": "resolved",
        "confidence": 0.94,
        "resolved_address": address.upper(),
        "match_method": "geocode_rooftop+point_in_parcel",
        "lat": lat,
        "lng": lng,
        "resolved_location": {"lat": lat, "lng": lng, "source": "address"},
        "fetched_at": "2026-08-14T00:00:00+00:00",
        "request_id": f"deal_{parcel_id}",
        "parcel": {
            "parcel_id": parcel_id,
            "apn": parcel_id,
            "address": address.upper(),
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        },
        "fields": {},
        "partial_failures": [],
    }


def _confirm(address: str, payload: dict) -> tuple[str, str]:
    mapping = map_mireye_lookup_to_parcel(payload)
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
    return confirmed["resolution_id"], binding["geometry_hash"]


class DealContextSlice3Tests(unittest.TestCase):
    def setUp(self) -> None:
        reset_advisor_runs_for_tests()
        get_parcel_resolution_store().clear()

    def tearDown(self) -> None:
        set_advisor_mireye_hooks_for_tests(request_fn=None, lookup_fn=None)
        reset_advisor_runs_for_tests()

    def _run_confirmed(
        self,
        address: str,
        payload: dict,
        *,
        run_mode: str = RUN_MODE_CUSTOM,
        demo_scenario_id: str | None = None,
    ) -> dict:
        resolution_id, _ = _confirm(address, payload)

        def lookup_fn(place: str, **kwargs):
            return _lookup_transport_result(
                ok=True,
                address=place,
                disposition="resolved",
                sanitized_response=payload,
            )

        set_advisor_mireye_hooks_for_tests(
            request_fn=_unit_test_mireye_request, lookup_fn=lookup_fn
        )
        queued = enqueue_advisor_run(
            address=address if run_mode == RUN_MODE_CUSTOM else None,
            fixture_id=None,
            parcel_resolution_id=resolution_id,
            run_mode=run_mode,
            demo_scenario_id=demo_scenario_id,
        )
        return execute_advisor_run(queued["run_id"])

    def test_create_read_update_bumps_version_and_keeps_history(self) -> None:
        result = self._run_confirmed(
            NAMBE_DEMO_ADDRESS,
            _payload(
                NAMBE_DEMO_ADDRESS,
                lat=39.615,
                lng=-105.235,
                ring=NAMBE_POLYGON,
                parcel_id="NAMBE-DEAL-1",
            ),
            run_mode=RUN_MODE_VERIFIED_DEMO,
            demo_scenario_id=DEMO_SCENARIO_NAMBE_CATTLE_V1,
        )
        self.assertEqual(result["track"], TRACK_GENERIC)
        self.assertIsNotNone(result.get("operating_profile"))
        context = result.get("deal_context")
        self.assertIsNotNone(context)
        self.assertEqual(context["context_version"], 1)
        self.assertEqual(context["operation_type"], "UNKNOWN")
        self.assertEqual(context["diligence_stage"], "SCREENING")
        self.assertEqual(context["species"], "CATTLE")
        self.assertEqual(context["run_id"], result["run_id"])
        self.assertEqual(context["geometry_hash"], result["geometry_hash"])
        self.assertTrue(context["seller_claims"])
        self.assertTrue(
            all(row["provenance"] == "DEMO_SCENARIO_CLAIM" for row in context["seller_claims"])
        )

        fetched = get_advisor_deal_context(result["run_id"])
        self.assertEqual(fetched["deal_context_id"], context["deal_context_id"])
        self.assertEqual(fetched["context_version"], 1)

        updated = update_advisor_deal_context(
            result["run_id"],
            expected_geometry_hash=result["geometry_hash"],
            expected_context_version=1,
            operation_type="SEASONAL_GRAZING",
            append_answer={
                "field": "operation_type",
                "value": "SEASONAL_GRAZING",
            },
        )
        self.assertEqual(updated["context_version"], 2)
        self.assertEqual(updated["operation_type"], "SEASONAL_GRAZING")
        self.assertEqual(len(updated["user_answers"]), 1)
        self.assertEqual(updated["user_answers"][0]["provenance"], "USER_SUPPLIED_UNVERIFIED")
        self.assertEqual(len(updated["version_history"]), 1)
        self.assertEqual(updated["version_history"][0]["context_version"], 1)
        self.assertEqual(updated["version_history"][0]["operation_type"], "UNKNOWN")

        again = get_deal_context_for_run(result["run_id"])
        self.assertEqual(again["context_version"], 2)
        self.assertEqual(again["version_history"][0]["context_version"], 1)

    def test_geometry_and_run_mismatch_fail_closed(self) -> None:
        result = self._run_confirmed(
            RURAL_TX,
            _payload(
                RURAL_TX,
                lat=30.199699,
                lng=-97.496411,
                ring=TX_POLYGON,
                parcel_id="TX-DEAL-1",
            ),
        )
        geo = result["geometry_hash"]
        with self.assertRaises(DealContextError) as wrong_geo:
            update_advisor_deal_context(
                result["run_id"],
                expected_geometry_hash="0" * 64,
                operation_type="SEASONAL_GRAZING",
            )
        self.assertEqual(wrong_geo.exception.code, "DEAL_CONTEXT_GEOMETRY_MISMATCH")

        with self.assertRaises(DealContextError) as wrong_run:
            update_deal_context(
                run_id="advisor_does_not_exist",
                expected_geometry_hash=geo,
                operation_type="SEASONAL_GRAZING",
            )
        self.assertEqual(wrong_run.exception.code, "DEAL_CONTEXT_NOT_FOUND")

        with self.assertRaises(DealContextError) as stale:
            update_advisor_deal_context(
                result["run_id"],
                expected_geometry_hash=geo,
                expected_context_version=99,
                operation_type="OTHER",
            )
        self.assertEqual(stale.exception.code, "DEAL_CONTEXT_VERSION_MISMATCH")

    def test_custom_and_nambe_demo_contexts_are_isolated(self) -> None:
        custom = self._run_confirmed(
            RURAL_TX,
            _payload(
                RURAL_TX,
                lat=30.199699,
                lng=-97.496411,
                ring=TX_POLYGON,
                parcel_id="TX-DEAL-2",
            ),
            run_mode=RUN_MODE_CUSTOM,
        )
        demo = self._run_confirmed(
            NAMBE_DEMO_ADDRESS,
            _payload(
                NAMBE_DEMO_ADDRESS,
                lat=39.615,
                lng=-105.235,
                ring=NAMBE_POLYGON,
                parcel_id="NAMBE-DEAL-2",
            ),
            run_mode=RUN_MODE_VERIFIED_DEMO,
            demo_scenario_id=DEMO_SCENARIO_NAMBE_CATTLE_V1,
        )
        self.assertNotEqual(custom["run_id"], demo["run_id"])
        self.assertNotEqual(
            custom["deal_context"]["deal_context_id"],
            demo["deal_context"]["deal_context_id"],
        )
        self.assertEqual(custom["deal_context"]["run_mode"], RUN_MODE_CUSTOM)
        self.assertEqual(demo["deal_context"]["run_mode"], RUN_MODE_VERIFIED_DEMO)
        self.assertEqual(custom["deal_context"]["seller_claims"], [])
        self.assertEqual(
            {row["claim_id"] for row in demo["deal_context"]["seller_claims"]},
            {row["claim_id"] for row in nambe_demo_scenario_claims()},
        )

        update_advisor_deal_context(
            custom["run_id"],
            expected_geometry_hash=custom["geometry_hash"],
            append_answer={"field": "note", "value": "custom-only"},
        )
        demo_ctx = get_advisor_deal_context(demo["run_id"])
        self.assertEqual(demo_ctx["context_version"], 1)
        self.assertEqual(demo_ctx["user_answers"], [])

        with self.assertRaises(DealContextError):
            update_deal_context(
                run_id=demo["run_id"],
                expected_geometry_hash=custom["geometry_hash"],
                append_answer={"field": "stolen", "value": True},
            )

    def test_api_get_and_patch_deal_context(self) -> None:
        result = self._run_confirmed(
            NAMBE_DEMO_ADDRESS,
            _payload(
                NAMBE_DEMO_ADDRESS,
                lat=39.615,
                lng=-105.235,
                ring=NAMBE_POLYGON,
                parcel_id="NAMBE-DEAL-API",
            ),
            run_mode=RUN_MODE_VERIFIED_DEMO,
            demo_scenario_id=DEMO_SCENARIO_NAMBE_CATTLE_V1,
        )
        client = TestClient(app)
        got = client.get(f"/v1/advisor/runs/{result['run_id']}/deal-context")
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.json()["context_version"], 1)

        patched = client.patch(
            f"/v1/advisor/runs/{result['run_id']}/deal-context",
            json={
                "expected_geometry_hash": result["geometry_hash"],
                "expected_context_version": 1,
                "diligence_stage": "PRE_VISIT",
                "append_answer": {
                    "field": "diligence_stage",
                    "value": "PRE_VISIT",
                },
            },
        )
        self.assertEqual(patched.status_code, 200)
        body = patched.json()
        self.assertEqual(body["context_version"], 2)
        self.assertEqual(body["diligence_stage"], "PRE_VISIT")

        rejected = client.patch(
            f"/v1/advisor/runs/{result['run_id']}/deal-context",
            json={
                "expected_geometry_hash": "f" * 64,
                "operation_type": "OTHER",
            },
        )
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(rejected.json()["detail"], "DEAL_CONTEXT_GEOMETRY_MISMATCH")

    def test_standalone_create_rejects_second_context_for_same_run(self) -> None:
        create_deal_context(
            run_id="advisor_unit_deal_001",
            parcel_resolution_id="pres_1",
            geometry_hash="a" * 64,
            seller_claims=[],
            run_mode="CUSTOM",
        )
        with self.assertRaises(DealContextError) as exc:
            create_deal_context(
                run_id="advisor_unit_deal_001",
                parcel_resolution_id="pres_1",
                geometry_hash="a" * 64,
                seller_claims=[],
                run_mode="CUSTOM",
            )
        self.assertEqual(exc.exception.code, "DEAL_CONTEXT_EXISTS")


if __name__ == "__main__":
    unittest.main()
