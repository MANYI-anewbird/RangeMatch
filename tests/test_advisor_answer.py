"""Slice 5: answer → Deal Context v2 → revised conclusion + what_changed."""

from __future__ import annotations

import copy
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from rangematch.advisor_agent import (
    DEMO_SCENARIO_NAMBE_CATTLE_V1,
    NAMBE_DEMO_ADDRESS,
    RUN_MODE_CUSTOM,
    RUN_MODE_VERIFIED_DEMO,
    enqueue_advisor_run,
    execute_advisor_run,
    reset_advisor_runs_for_tests,
    set_advisor_mireye_hooks_for_tests,
    submit_advisor_answer,
    _lookup_transport_result,
    _unit_test_mireye_request,
)
from rangematch.advisor_answer import AdvisorAnswerError
from rangematch.advisor_conclusion import (
    CHANGE_STATUS_CHANGED,
    CHANGE_STATUS_NARROWED,
    CHANGE_STATUS_NONE,
    SOURCE_FALLBACK,
    build_what_changed,
)
from rangematch.advisor_parcel_gate import (
    require_confirmed_parcel,
    stage_mireye_mapping_for_confirmation,
)
from rangematch.api import app
from rangematch.llm_provider import LLMCompletion
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
        "request_id": f"ans_{parcel_id}",
        "parcel": {
            "parcel_id": parcel_id,
            "apn": parcel_id,
            "address": address.upper(),
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        },
        "fields": {},
        "partial_failures": [],
    }


def _confirm(address: str, payload: dict) -> str:
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


class AnswerSlice5Tests(unittest.TestCase):
    def setUp(self) -> None:
        reset_advisor_runs_for_tests()
        get_parcel_resolution_store().clear()

    def tearDown(self) -> None:
        set_advisor_mireye_hooks_for_tests(request_fn=None, lookup_fn=None)
        reset_advisor_runs_for_tests()

    def _run(
        self,
        address: str,
        payload: dict,
        *,
        run_mode: str = RUN_MODE_CUSTOM,
        demo_scenario_id: str | None = None,
    ) -> dict:
        resolution_id = _confirm(address, payload)

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

    def _nambe(self) -> dict:
        return self._run(
            NAMBE_DEMO_ADDRESS,
            _payload(
                NAMBE_DEMO_ADDRESS,
                lat=39.615,
                lng=-105.235,
                ring=NAMBE_POLYGON,
                parcel_id="NAMBE-ANS-1",
            ),
            run_mode=RUN_MODE_VERIFIED_DEMO,
            demo_scenario_id=DEMO_SCENARIO_NAMBE_CATTLE_V1,
        )

    def test_seasonal_answer_revises_conclusion_and_keeps_initial(self) -> None:
        result = self._nambe()
        initial = result["initial_operating_conclusion"]
        packet_hash = result["packet_hash"]
        self.assertEqual(initial["deal_context_version"], 1)
        self.assertEqual(result["deal_context"]["context_version"], 1)
        qid = initial["next_question"]["question_id"]
        self.assertEqual(qid, "Q_OPERATION_TYPE")

        updated = submit_advisor_answer(
            result["run_id"],
            question_id=qid,
            answer="SEASONAL_GRAZING",
            expected_context_version=1,
            expected_geometry_hash=result["geometry_hash"],
            provider_name="FIXTURE",
        )
        self.assertEqual(updated["deal_context"]["context_version"], 2)
        self.assertEqual(updated["deal_context"]["operation_type"], "SEASONAL_GRAZING")
        self.assertEqual(
            updated["deal_context"]["user_answers"][0]["provenance"],
            "USER_SUPPLIED_UNVERIFIED",
        )
        self.assertEqual(updated["packet_hash"], packet_hash)
        self.assertEqual(
            updated["initial_operating_conclusion"]["conclusion_id"],
            initial["conclusion_id"],
        )
        revised = updated["revised_operating_conclusion"]
        self.assertIsNotNone(revised)
        self.assertEqual(revised["deal_context_version"], 2)
        self.assertEqual(updated["operating_conclusion"]["conclusion_id"], revised["conclusion_id"])
        self.assertNotEqual(revised["conclusion_id"], initial["conclusion_id"])
        change = updated["conclusion_change"]
        self.assertIn(
            change["change_status"],
            {CHANGE_STATUS_CHANGED, CHANGE_STATUS_NARROWED, CHANGE_STATUS_NONE},
        )
        self.assertEqual(change["user_answer"]["value"], "SEASONAL_GRAZING")
        self.assertEqual(change["change_status"], CHANGE_STATUS_CHANGED)
        self.assertTrue(change["fields_changed"])

    def test_binding_mismatches_fail_closed(self) -> None:
        result = self._nambe()
        qid = result["operating_conclusion"]["next_question"]["question_id"]
        with self.assertRaises(AdvisorAnswerError) as wrong_q:
            submit_advisor_answer(
                result["run_id"],
                question_id="Q_ACCESS_DOCUMENTS",
                answer="YES",
                expected_context_version=1,
                expected_geometry_hash=result["geometry_hash"],
            )
        self.assertEqual(wrong_q.exception.code, "ANSWER_QUESTION_MISMATCH")

        with self.assertRaises(AdvisorAnswerError) as wrong_v:
            submit_advisor_answer(
                result["run_id"],
                question_id=qid,
                answer="SEASONAL_GRAZING",
                expected_context_version=9,
                expected_geometry_hash=result["geometry_hash"],
            )
        self.assertEqual(wrong_v.exception.code, "ANSWER_CONTEXT_VERSION_MISMATCH")

        with self.assertRaises(AdvisorAnswerError) as wrong_g:
            submit_advisor_answer(
                result["run_id"],
                question_id=qid,
                answer="SEASONAL_GRAZING",
                expected_context_version=1,
                expected_geometry_hash="f" * 64,
            )
        self.assertEqual(wrong_g.exception.code, "ANSWER_GEOMETRY_MISMATCH")

        # Stale retry after a successful answer.
        submit_advisor_answer(
            result["run_id"],
            question_id=qid,
            answer="SEASONAL_GRAZING",
            expected_context_version=1,
            expected_geometry_hash=result["geometry_hash"],
        )
        with self.assertRaises(AdvisorAnswerError) as stale:
            submit_advisor_answer(
                result["run_id"],
                question_id=qid,
                answer="YEAR_ROUND_COW_CALF",
                expected_context_version=1,
                expected_geometry_hash=result["geometry_hash"],
            )
        self.assertIn(stale.exception.code, {
            "ANSWER_CONTEXT_VERSION_MISMATCH",
            "ANSWER_QUESTION_MISMATCH",
            "ANSWER_CONCLUSION_STALE",
        })

    def test_api_answer_and_isolation(self) -> None:
        nambe = self._nambe()
        custom = self._run(
            "480 Berdoll Ln, Cedar Creek, TX 78612",
            _payload(
                "480 Berdoll Ln, Cedar Creek, TX 78612",
                lat=30.205,
                lng=-97.495,
                ring=TX_POLYGON,
                parcel_id="TX-ANS-1",
            ),
        )
        self.assertNotEqual(nambe["run_id"], custom["run_id"])
        self.assertNotEqual(
            nambe["deal_context"]["deal_context_id"],
            custom["deal_context"]["deal_context_id"],
        )

        client = TestClient(app)
        qid = nambe["operating_conclusion"]["next_question"]["question_id"]
        ok = client.post(
            f"/v1/advisor/runs/{nambe['run_id']}/answers",
            json={
                "question_id": qid,
                "answer": "SEASONAL_GRAZING",
                "expected_context_version": 1,
                "expected_geometry_hash": nambe["geometry_hash"],
                "provider": "FIXTURE",
            },
        )
        self.assertEqual(ok.status_code, 200, ok.text)
        body = ok.json()
        self.assertEqual(body["deal_context"]["context_version"], 2)
        self.assertEqual(body["operating_conclusion"]["deal_context_version"], 2)
        self.assertEqual(custom["deal_context"]["context_version"], 1)

        bad = client.post(
            f"/v1/advisor/runs/{nambe['run_id']}/answers",
            json={
                "question_id": "Q_ACCESS_DOCUMENTS",
                "answer": "YES",
                "expected_context_version": 2,
                "expected_geometry_hash": nambe["geometry_hash"],
            },
        )
        self.assertEqual(bad.status_code, 409)

    def test_malformed_llm_still_revises_deterministically(self) -> None:
        result = self._nambe()
        qid = result["operating_conclusion"]["next_question"]["question_id"]
        bad = LLMCompletion(
            content={"operating_conclusion": None},
            provider="DEEPSEEK",
            model_id="mock",
            prompt_version="test",
            generated_at="2026-08-14T00:00:00+00:00",
            provider_status="OK",
        )
        provider = MagicMock()
        provider.complete_json.return_value = bad
        with patch("rangematch.advisor_conclusion.get_provider", return_value=provider):
            updated = submit_advisor_answer(
                result["run_id"],
                question_id=qid,
                answer="YEAR_ROUND_COW_CALF",
                expected_context_version=1,
                expected_geometry_hash=result["geometry_hash"],
                provider_name="DEEPSEEK",
            )
        self.assertEqual(updated["revised_operating_conclusion"]["source"], SOURCE_FALLBACK)
        self.assertEqual(updated["revised_operating_conclusion"]["deal_context_version"], 2)
        revised_text = " ".join(
            str(updated["revised_operating_conclusion"].get(field) or "")
            for field in ("headline", "summary", "primary_constraint")
        ).lower()
        self.assertIn("year-round", revised_text)
        self.assertNotIn("operation has not yet been defined", revised_text)

    def test_what_changed_honest_when_identical(self) -> None:
        before = {
            "conclusion_id": "concl_before01",
            "deal_context_version": 1,
            "status": "CONDITIONAL",
            "headline": "Same headline for honesty check",
            "summary": "Same summary text remains after the answer lands.",
            "primary_constraint": "Same primary constraint remains in place.",
            "confidence": "LOW",
            "next_action": "Request access or title documents before travel.",
            "next_spend_class": "DOCUMENT_REVIEW",
            "next_question": {"question_id": "Q_OPERATION_TYPE"},
        }
        after = copy.deepcopy(before)
        after["conclusion_id"] = "concl_after0001"
        after["deal_context_version"] = 2
        change = build_what_changed(
            before,
            after,
            user_answer={"question_id": "Q_OPERATION_TYPE", "value": "OTHER"},
        )
        self.assertEqual(change["change_status"], CHANGE_STATUS_NONE)


if __name__ == "__main__":
    unittest.main()
