"""Slice 7: one-page Cattle Operating Snapshot projection and render checks."""

from __future__ import annotations

import re
import unittest

from fastapi.testclient import TestClient

from rangematch.advisor_agent import (
    DEMO_SCENARIO_NAMBE_CATTLE_V1,
    NAMBE_DEMO_ADDRESS,
    RUN_MODE_VERIFIED_DEMO,
    enqueue_advisor_run,
    execute_advisor_run,
    reset_advisor_runs_for_tests,
    set_advisor_mireye_hooks_for_tests,
    submit_advisor_answer,
    _lookup_transport_result,
    _unit_test_mireye_request,
)
from rangematch.advisor_parcel_gate import (
    require_confirmed_parcel,
    stage_mireye_mapping_for_confirmation,
)
from rangematch.advisor_snapshot import (
    SnapshotError,
    project_cattle_operating_snapshot,
    render_cattle_operating_snapshot_pdf,
    validate_snapshot_view,
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


def _payload() -> dict:
    address = NAMBE_DEMO_ADDRESS
    return {
        "disposition": "resolved",
        "confidence": 0.94,
        "resolved_address": address.upper(),
        "match_method": "geocode_rooftop+point_in_parcel",
        "lat": 39.615,
        "lng": -105.235,
        "resolved_location": {"lat": 39.615, "lng": -105.235, "source": "address"},
        "fetched_at": "2026-08-14T00:00:00+00:00",
        "request_id": "snap_nambe_1",
        "parcel": {
            "parcel_id": "NAMBE-SNAP-1",
            "apn": "NAMBE-SNAP-1",
            "address": address.upper(),
            "geometry": {"type": "Polygon", "coordinates": [NAMBE_POLYGON]},
        },
        "fields": {},
        "partial_failures": [],
    }


def _confirm(payload: dict) -> str:
    address = NAMBE_DEMO_ADDRESS
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
    require_confirmed_parcel(confirmed)
    return confirmed["resolution_id"]


def _pdf_page_count(payload: bytes) -> int:
    """Render-check helper without adding a PDF reader dependency."""
    # Prefer the Pages dictionary Count written by fpdf2.
    counts = re.findall(rb"/Type\s*/Pages\b.*?/Count\s+(\d+)", payload, flags=re.S)
    if counts:
        return int(counts[-1])
    # Fallback: leaf page objects (exclude /Type /Pages).
    return len(re.findall(rb"/Type\s*/Page\b(?!\s*/)", payload))


class SnapshotSlice7Tests(unittest.TestCase):
    def setUp(self) -> None:
        reset_advisor_runs_for_tests()
        get_parcel_resolution_store().clear()

    def tearDown(self) -> None:
        set_advisor_mireye_hooks_for_tests(request_fn=None, lookup_fn=None)
        reset_advisor_runs_for_tests()

    def _nambe(self) -> dict:
        payload = _payload()
        resolution_id = _confirm(payload)

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
            address=None,
            fixture_id=None,
            parcel_resolution_id=resolution_id,
            run_mode=RUN_MODE_VERIFIED_DEMO,
            demo_scenario_id=DEMO_SCENARIO_NAMBE_CATTLE_V1,
        )
        return execute_advisor_run(queued["run_id"])

    def test_initial_snapshot_has_snapshot_and_appendix_pages(self) -> None:
        result = self._nambe()
        view = project_cattle_operating_snapshot(result)
        self.assertEqual(view["what_changed"]["mode"], "QUESTION_OPEN")
        self.assertEqual(
            view["footer"]["deal_context_version"],
            result["deal_context"]["context_version"],
        )
        self.assertEqual(
            view["footer"]["deal_context_version"],
            result["operating_conclusion"]["deal_context_version"],
        )
        self.assertFalse(validate_snapshot_view(view))
        payload = render_cattle_operating_snapshot_pdf(view)
        self.assertTrue(payload.startswith(b"%PDF"))
        self.assertEqual(_pdf_page_count(payload), 2)
        self.assertTrue(view["appendix"]["rows"])
        self.assertTrue(all(row["result"] for row in view["appendix"]["rows"]))
        self.assertNotIn(
            "Mapped hydrography candidate count",
            {row["evidence"] for row in view["appendix"]["rows"]},
        )
        # No Factor dump / observation IDs in buyer sections.
        joined = " ".join(
            [
                view["headline"],
                view["summary"],
                view["primary_constraint"],
                *[row["reading"] for row in view["why"]],
                view["what_changed"]["agent_asked"],
                view["next_move"]["action"],
            ]
        )
        self.assertIsNone(re.search(r"\b(?:OBS_|BOTTLENECK_|F0[1-8]\b)", joined))

    def test_answered_snapshot_binds_context_v2(self) -> None:
        result = self._nambe()
        qid = result["operating_conclusion"]["next_question"]["question_id"]
        updated = submit_advisor_answer(
            result["run_id"],
            question_id=qid,
            answer="SEASONAL_GRAZING",
            expected_context_version=1,
            expected_geometry_hash=result["geometry_hash"],
            provider_name="FIXTURE",
        )
        view = project_cattle_operating_snapshot(updated)
        self.assertEqual(view["what_changed"]["mode"], "ANSWERED")
        self.assertEqual(view["footer"]["deal_context_version"], 2)
        self.assertEqual(view["what_changed"]["buyer_answered"], "Seasonal Grazing")
        self.assertNotIn("primary_constraint", view["what_changed"]["update_summary"])
        self.assertNotIn("confidence", view["what_changed"]["update_summary"])
        self.assertIn("seasonal plan", view["what_changed"]["update_summary"].lower())
        self.assertTrue(view["next_move"]["copy_and_send"].startswith("Please "))
        payload = render_cattle_operating_snapshot_pdf(view)
        self.assertEqual(_pdf_page_count(payload), 2)

        client = TestClient(app)
        response = client.get(
            f"/v1/advisor/runs/{updated['run_id']}/cattle-operating-snapshot.pdf"
        )
        self.assertEqual(response.status_code, 200, response.text[:200])
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertEqual(_pdf_page_count(response.content), 2)

    def test_api_initial_download(self) -> None:
        result = self._nambe()
        client = TestClient(app)
        response = client.get(
            f"/v1/advisor/runs/{result['run_id']}/cattle-operating-snapshot.pdf"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(_pdf_page_count(response.content), 2)
        # Legacy path still available.
        legacy = client.get(f"/v1/advisor/runs/{result['run_id']}/buyer-brief.pdf")
        self.assertEqual(legacy.status_code, 200)

    def test_version_mismatch_fails_closed(self) -> None:
        result = self._nambe()
        broken = dict(result)
        broken["operating_conclusion"] = dict(result["operating_conclusion"])
        broken["operating_conclusion"]["deal_context_version"] = 99
        with self.assertRaises(SnapshotError) as exc:
            project_cattle_operating_snapshot(broken)
        self.assertEqual(exc.exception.code, "SNAPSHOT_CONTEXT_VERSION_MISMATCH")


if __name__ == "__main__":
    unittest.main()
