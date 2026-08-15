"""Place cleanup is language-only. Mireye still locates the parcel."""

from __future__ import annotations

import unittest

from rangematch.advisor_agent import (
    OUTCOME_PARCEL_NOT_FOUND,
    classify_advisor_place,
    reset_advisor_runs_for_tests,
    run_cper_advisor_agent,
    set_advisor_mireye_hooks_for_tests,
    _lookup_transport_result,
    _unit_test_mireye_request,
)
from rangematch.advisor_place import (
    _apply_llm_payload,
    place_needs_llm_cleanup,
    prepare_advisor_place,
)


class AdvisorPlaceCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_advisor_runs_for_tests()

    def test_standard_street_skips_llm(self) -> None:
        for raw in (
            "4213 Nambe Rd",
            "4213 Nambe Road, Indian Hills",
            "4213 Nambe Road, Indian Hills, CO 80454",
        ):
            self.assertFalse(place_needs_llm_cleanup(raw), raw)
            prepared = prepare_advisor_place(raw, provider_name="FIXTURE")
            self.assertEqual(prepared["status"], "DIRECT")
            self.assertFalse(prepared["llm_used"])
            self.assertEqual(prepared["lookup_input"], raw)
            self.assertEqual(prepared["input_kind"], "ADDRESS")

    def test_coordinates_skip_llm(self) -> None:
        self.assertFalse(place_needs_llm_cleanup("40.82, -104.76"))
        prepared = prepare_advisor_place("40.82, -104.76", provider_name="FIXTURE")
        self.assertEqual(prepared["status"], "DIRECT")
        self.assertEqual(prepared["input_kind"], "COORDINATE")
        self.assertFalse(prepared["llm_used"])
        classified = classify_advisor_place("40.82, -104.76")
        self.assertEqual(classified["kind"], "coord")

    def test_messy_near_nunn_is_tidied_then_still_needs_mireye(self) -> None:
        self.assertTrue(place_needs_llm_cleanup("near Nunn Colorado"))
        prepared = prepare_advisor_place("near Nunn Colorado", provider_name="FIXTURE")
        self.assertEqual(prepared["status"], "CLEANED")
        self.assertTrue(prepared["llm_used"])
        self.assertEqual(prepared["lookup_input"], "Nunn, CO")
        self.assertIsNone(prepared["latitude"])
        self.assertIsNone(prepared["longitude"])

        seen: list[str] = []

        def lookup_fn(place: str, **kwargs):
            seen.append(place)
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
        result = run_cper_advisor_agent(address="near Nunn Colorado")
        self.assertEqual(seen, ["Nunn, CO"])
        self.assertEqual(
            result["investigation_outcome"], OUTCOME_PARCEL_NOT_FOUND
        )
        self.assertIsNone(result["brief"])
        self.assertFalse(result["parcel_geometry_confirmed"])
        self.assertTrue((result.get("place_normalization") or {}).get("llm_used"))

    def test_llm_invented_coordinates_are_rejected(self) -> None:
        prepared = _apply_llm_payload(
            "near Nunn Colorado",
            {
                "input_type": "COORDINATE",
                "normalized_address": None,
                "latitude": 40.82,
                "longitude": -104.76,
                "needs_user": None,
            },
        )
        self.assertEqual(prepared["status"], "NEEDS_MORE")
        self.assertIn("invent", (prepared.get("message") or "").lower())

    def test_llm_invented_nambe_from_nunn_is_rejected(self) -> None:
        prepared = _apply_llm_payload(
            "near Nunn Colorado",
            {
                "input_type": "ADDRESS",
                "normalized_address": "4213 Nambe Road, Indian Hills, CO 80454",
                "latitude": None,
                "longitude": None,
                "needs_user": None,
            },
        )
        self.assertEqual(prepared["status"], "NEEDS_MORE")

    def test_vague_input_asks_for_state_or_coords(self) -> None:
        prepared = prepare_advisor_place("that ranch", provider_name="FIXTURE")
        self.assertEqual(prepared["status"], "NEEDS_MORE")
        result = run_cper_advisor_agent(address="that ranch")
        self.assertEqual(result["failed_step"], "ACCEPT_PLACE")
        self.assertIsNone(result["brief"])
        self.assertIn("state", (result.get("error") or "").lower())


if __name__ == "__main__":
    unittest.main()
