"""Generic Mireye entry: any US place, no Nambe special-case, fail closed."""

from __future__ import annotations

import unittest

from rangematch.advisor_agent import (
    OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED,
    OUTCOME_PARCEL_NOT_FOUND,
    OUTCOME_PARCEL_NEEDS_CONFIRMATION,
    TRACK_GENERIC,
    classify_advisor_place,
    reset_advisor_runs_for_tests,
    run_cper_advisor_agent,
    set_advisor_mireye_hooks_for_tests,
    _lookup_transport_result,
    _unit_test_mireye_request,
)
from rangematch.advisor_parcel_gate import (
    require_confirmed_parcel,
    stage_mireye_mapping_for_confirmation,
)
from rangematch.mireye_parcel_resolver import map_mireye_lookup_to_parcel
from rangematch.parcel_resolution import confirm_selected_parcel
from rangematch.parcel_resolution_store import get_parcel_resolution_store

NAMBE = "4213 Nambe Road, Indian Hills, CO 80454"
RURAL_TX = "480 Berdoll Ln, Cedar Creek, TX 78612"
FAIL_COLUMBUS = "100 Main St, Columbus"

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


def _resolved(address: str, *, lat: float, lng: float, ring: list, parcel_id: str) -> dict:
    return {
        "disposition": "resolved",
        "confidence": 0.94,
        "resolved_address": address.upper(),
        "match_method": "geocode_rooftop+point_in_parcel",
        "lat": lat,
        "lng": lng,
        "resolved_location": {"lat": lat, "lng": lng, "source": "address"},
        "fetched_at": "2026-08-13T04:00:00+00:00",
        "request_id": f"generic_entry_{parcel_id}",
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


class AdvisorGenericEntryTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_advisor_runs_for_tests()

    def test_classify_address_and_us_coordinates(self) -> None:
        addr = classify_advisor_place(NAMBE)
        self.assertEqual(addr["kind"], "address")
        self.assertEqual(addr["input_kind"], "ADDRESS")
        coord = classify_advisor_place("30.199699,-97.496411")
        self.assertEqual(coord["kind"], "coord")
        self.assertEqual(coord["input_kind"], "COORDINATE")

    def test_nambe_unique_polygon_requires_confirm_then_generic(self) -> None:
        payload = _resolved(NAMBE, lat=39.615, lng=-105.235, ring=NAMBE_POLYGON, parcel_id="NAMBE-LIVE")

        def lookup_fn(place: str, **kwargs):
            self.assertEqual(kwargs.get("kind"), "address")
            return _lookup_transport_result(
                ok=True, address=place, sanitized_response=payload, disposition="resolved"
            )

        set_advisor_mireye_hooks_for_tests(
            request_fn=_unit_test_mireye_request, lookup_fn=lookup_fn
        )
        first = run_cper_advisor_agent(address=NAMBE)
        self.assertEqual(first["investigation_outcome"], OUTCOME_PARCEL_NEEDS_CONFIRMATION)
        self.assertIsNone(first["brief"])
        self.assertIsNone(first["packet"])
        self.assertFalse(first["parcel_geometry_confirmed"])

        resolution_id, geometry_hash = _confirm(NAMBE, payload)
        second = run_cper_advisor_agent(
            address=NAMBE, parcel_resolution_id=resolution_id
        )
        self.assertEqual(
            second["investigation_outcome"], OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED
        )
        self.assertEqual(second["track"], TRACK_GENERIC)
        self.assertEqual(second["packet"]["technical_references"]["policy_scope"], "GENERIC_MINIMAL")
        self.assertFalse(second["packet"]["parcel"]["is_engineering_test_geometry"])
        self.assertEqual(second["geometry_hash"], geometry_hash)
        blob = repr(second["packet"]).lower()
        self.assertNotIn("engineering_test_geometry_cper", blob)
        self.assertNotIn("cper_f03", blob)

    def test_second_rural_parcel_is_same_generic_path_not_nambe(self) -> None:
        nambe_payload = _resolved(
            NAMBE, lat=39.615, lng=-105.235, ring=NAMBE_POLYGON, parcel_id="NAMBE-LIVE"
        )
        tx_payload = _resolved(
            RURAL_TX, lat=30.199699, lng=-97.496411, ring=TX_POLYGON, parcel_id="TX-BERDOLL"
        )
        nambe_id, nambe_hash = _confirm(NAMBE, nambe_payload)
        tx_id, tx_hash = _confirm(RURAL_TX, tx_payload)
        self.assertNotEqual(nambe_hash, tx_hash)

        nambe = run_cper_advisor_agent(address=NAMBE, parcel_resolution_id=nambe_id)
        rural = run_cper_advisor_agent(address=RURAL_TX, parcel_resolution_id=tx_id)
        self.assertEqual(nambe["track"], TRACK_GENERIC)
        self.assertEqual(rural["track"], TRACK_GENERIC)
        self.assertEqual(
            rural["packet"]["technical_references"]["policy_scope"], "GENERIC_MINIMAL"
        )
        self.assertEqual(rural["geometry_hash"], tx_hash)
        self.assertNotEqual(rural["geometry_hash"], nambe["geometry_hash"])
        rural_blob = repr(rural["packet"]).lower()
        self.assertNotIn("4213", rural_blob)
        self.assertNotIn("nambe", rural_blob)
        self.assertNotIn("engineering_test_geometry_cper", rural_blob)
        self.assertNotIn("indian hills", rural_blob)
        self.assertIsNotNone(rural.get("operating_profile"))

    def test_no_match_fails_closed_without_fake_report(self) -> None:
        def lookup_fn(place: str, **kwargs):
            return _lookup_transport_result(
                ok=True,
                address=place,
                disposition="no_match",
                sanitized_response={
                    "disposition": "no_match",
                    "reason": "unaddressed_or_no_match",
                    "hint": "the input named a different city than the best match found",
                },
            )

        set_advisor_mireye_hooks_for_tests(
            request_fn=_unit_test_mireye_request, lookup_fn=lookup_fn
        )
        result = run_cper_advisor_agent(address=FAIL_COLUMBUS)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_PARCEL_NOT_FOUND
        )
        self.assertEqual(result["failed_step"], "RESOLVE_PARCEL")
        self.assertIsNone(result["brief"])
        self.assertIsNone(result["packet"])
        self.assertIn("unaddressed_or_no_match", result.get("error") or "")

    def test_coordinate_lookup_uses_coord_kind(self) -> None:
        kinds: list[str] = []
        payload = _resolved(
            RURAL_TX, lat=30.199699, lng=-97.496411, ring=TX_POLYGON, parcel_id="TX-COORD"
        )

        def lookup_fn(place: str, **kwargs):
            kinds.append(str(kwargs.get("kind")))
            return _lookup_transport_result(
                ok=True,
                address=place,
                sanitized_response=payload,
                disposition="resolved",
                kind=str(kwargs.get("kind") or "address"),
            )

        set_advisor_mireye_hooks_for_tests(
            request_fn=_unit_test_mireye_request, lookup_fn=lookup_fn
        )
        result = run_cper_advisor_agent(address="30.199699,-97.496411")
        self.assertEqual(kinds, ["coord"])
        self.assertEqual(result["investigation_outcome"], OUTCOME_PARCEL_NEEDS_CONFIRMATION)
        self.assertIsNone(result["brief"])


if __name__ == "__main__":
    unittest.main()
