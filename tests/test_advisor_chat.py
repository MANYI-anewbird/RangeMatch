"""Slice 6: thin grounded chat — six intents, read-only, fail-soft."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from rangematch.advisor_agent import (
    COLLECTION_MODE_MIREYE_FIRST,
    DEMO_SCENARIO_NAMBE_CATTLE_V1,
    NAMBE_DEMO_ADDRESS,
    RUN_MODE_VERIFIED_DEMO,
    enqueue_advisor_run,
    execute_advisor_run,
    get_advisor_chat,
    get_advisor_run,
    post_advisor_chat,
    reset_advisor_runs_for_tests,
    run_cper_advisor_agent,
    set_advisor_mireye_hooks_for_tests,
    _lookup_transport_result,
    _unit_test_mireye_request,
)
from rangematch.advisor_chat import (
    SOURCE_FALLBACK,
    AdvisorChatError,
    build_chat_workbench,
    chat_view_from_natural_foundation,
    classify_chat_intent,
    generate_chat_turn,
    render_deterministic_chat_turn,
    suggested_chat_questions,
    validate_chat_turn,
)
from rangematch.mireye_first_collection import manifest_field_ids
from rangematch.mireye_parcel_resolver import map_mireye_lookup_to_parcel
from rangematch.parcel_resolution import confirm_selected_parcel
from rangematch.parcel_resolution_store import get_parcel_resolution_store
from rangematch.api import app
from rangematch.llm_provider import LLMCompletion
from rangematch.advisor_parcel_gate import (
    require_confirmed_parcel,
    stage_mireye_mapping_for_confirmation,
)

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
        "request_id": "chat_nambe_1",
        "parcel": {
            "parcel_id": "NAMBE-CHAT-1",
            "apn": "NAMBE-CHAT-1",
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


class ChatSlice6Tests(unittest.TestCase):
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

    def test_classify_supported_and_out_of_scope(self) -> None:
        self.assertEqual(
            classify_chat_intent("What is the current cattle operating conclusion?"),
            "OVERALL_CATTLE_CASE",
        )
        self.assertEqual(classify_chat_intent("Tell me about livestock water"), "WATER")
        self.assertEqual(classify_chat_intent("What about feed and forage?"), "FEED")
        self.assertEqual(classify_chat_intent("How does terrain affect movement?"), "MOVEMENT")
        self.assertEqual(classify_chat_intent("Is road contact legal access?"), "ACCESS")
        self.assertEqual(classify_chat_intent("What should I do next?"), "NEXT_ACTION")
        self.assertEqual(classify_chat_intent("Should I buy this ranch at this price?"), "OUT_OF_SCOPE")
        self.assertEqual(len(suggested_chat_questions()), 6)

    def test_chat_is_read_only_and_grounded(self) -> None:
        result = self._nambe()
        packet_hash = result["packet_hash"]
        context_version = result["deal_context"]["context_version"]
        conclusion_id = result["operating_conclusion"]["conclusion_id"]

        body = post_advisor_chat(
            result["run_id"],
            message="What does the evidence say about livestock water on this tract?",
            provider_name="FIXTURE",
        )
        turn = body["turn"]
        self.assertEqual(turn["intent"], "WATER")
        self.assertTrue(turn["judgment"])
        self.assertTrue(turn["answer"])
        self.assertTrue(turn["evidence_refs"])
        self.assertTrue(turn["suggested_follow_up"])
        self.assertEqual(turn["source"], SOURCE_FALLBACK)

        again = get_advisor_chat(result["run_id"])
        self.assertEqual(len(again["turns"]), 1)
        self.assertEqual(len(again["suggested_questions"]), 6)

        # Re-fetch run via execute path fields still intact on store.
        from rangematch.advisor_agent import get_advisor_run

        latest = get_advisor_run(result["run_id"])
        self.assertEqual(latest["packet_hash"], packet_hash)
        self.assertEqual(latest["deal_context"]["context_version"], context_version)
        self.assertEqual(latest["operating_conclusion"]["conclusion_id"], conclusion_id)

    def test_out_of_scope_stays_bounded(self) -> None:
        result = self._nambe()
        body = post_advisor_chat(
            result["run_id"],
            message="What stocking rate and purchase price should I use?",
            provider_name="FIXTURE",
        )
        self.assertEqual(body["turn"]["intent"], "OUT_OF_SCOPE")
        self.assertIn("supported", body["turn"]["answer"].lower())

    def test_api_chat_endpoints(self) -> None:
        result = self._nambe()
        client = TestClient(app)
        got = client.get(f"/v1/advisor/runs/{result['run_id']}/chat")
        self.assertEqual(got.status_code, 200, got.text)
        self.assertEqual(len(got.json()["suggested_questions"]), 6)

        posted = client.post(
            f"/v1/advisor/runs/{result['run_id']}/chat",
            json={
                "message": "What should I do next, and what spend class does that imply?",
                "provider": "FIXTURE",
            },
        )
        self.assertEqual(posted.status_code, 200, posted.text)
        self.assertEqual(posted.json()["turn"]["intent"], "NEXT_ACTION")

        bad = client.post(
            f"/v1/advisor/runs/{result['run_id']}/chat",
            json={"message": ""},
        )
        self.assertEqual(bad.status_code, 422)

    def test_malformed_llm_falls_back(self) -> None:
        result = self._nambe()
        bad = LLMCompletion(
            content={"chat_turn": "nope"},
            provider="DEEPSEEK",
            model_id="mock",
            prompt_version="test",
            generated_at="2026-08-14T00:00:00+00:00",
            provider_status="OK",
        )
        provider = MagicMock()
        provider.complete_json.return_value = bad
        with patch("rangematch.advisor_chat.get_provider", return_value=provider):
            turn = generate_chat_turn(
                run_id=result["run_id"],
                user_message="What is the current cattle operating conclusion for this parcel?",
                packet=result["packet"],
                deal_context=result["deal_context"],
                operating_conclusion=result["operating_conclusion"],
                operating_profile=result.get("operating_profile"),
                provider_name="DEEPSEEK",
            )
        self.assertEqual(turn["source"], SOURCE_FALLBACK)
        self.assertEqual(turn["intent"], "OVERALL_CATTLE_CASE")

    def test_chat_allows_free_form_prose_under_schema_only_gate(self) -> None:
        result = self._nambe()
        deal = dict(result["deal_context"])
        deal["context_version"] = 2
        deal["operation_type"] = "SEASONAL_GRAZING"
        deal["user_answers"] = [
            {
                "field": "operation_type",
                "value": "SEASONAL_GRAZING",
                "provenance": "USER_SUPPLIED_UNVERIFIED",
            }
        ]
        conclusion = dict(result["operating_conclusion"])
        conclusion["deal_context_version"] = 2
        workbench = build_chat_workbench(
            packet=result["packet"],
            deal_context=deal,
            operating_conclusion=conclusion,
            operating_profile=result.get("operating_profile"),
            user_message="What does the evidence say about water?",
            classified_intent="WATER",
        )
        free_form = {
            "schema_version": "RANGEMATCH_ADVISOR_CHAT_TURN@0.1.0",
            "turn_id": "chat_free_form",
            "run_id": result["run_id"],
            "deal_context_version": 2,
            "intent": "WATER",
            "user_message": "What does the evidence say about water?",
            "judgment": "OBS_WATER_COUNT shows only mapped water leads.",
            "answer": (
                "The LIVESTOCK_WATER_DILIGENCE_001 card says these mapped features "
                "do not prove a usable livestock-water system, and seasonal or "
                "year-round use still shapes how to read that gap."
            ),
            "evidence_refs": list(conclusion.get("evidence_refs") or [])[:1],
            "knowledge_refs": [],
            "missing_evidence": ["A usable livestock-water source is not verified."],
            "suggested_follow_up": "What seller record should I request next?",
            "source": "LIVE_LLM",
            "validation_status": "PASSED",
            "validation_violations": [],
            "created_at": "2026-08-14T00:00:00+00:00",
        }
        self.assertEqual(validate_chat_turn(free_form, workbench=workbench), [])
        self.assertIn("cattle_knowledge", workbench)
        self.assertIn("place_materials", workbench)

    def test_water_fallback_uses_seasonal_context_after_answer(self) -> None:
        result = self._nambe()
        deal = dict(result["deal_context"])
        deal["context_version"] = 2
        deal["operation_type"] = "SEASONAL_GRAZING"
        deal["user_answers"] = [
            {
                "field": "operation_type",
                "value": "SEASONAL_GRAZING",
                "provenance": "USER_SUPPLIED_UNVERIFIED",
            }
        ]
        conclusion = dict(result["operating_conclusion"])
        conclusion["deal_context_version"] = 2
        conclusion["headline"] = (
            "Seasonal cattle use is worth investigating, but do not plan around water yet"
        )
        conclusion["primary_constraint"] = (
            "Can the seller show a reliable livestock-water source for the intended grazing months?"
        )
        conclusion["missing_evidence"] = [
            "Buyer operation type is still UNKNOWN in Deal Context.",
            "Developed livestock-water systems are not verified from public layers alone.",
        ]
        turn = render_deterministic_chat_turn(
            run_id=result["run_id"],
            user_message="What do we know about livestock water?",
            intent="WATER",
            packet=result["packet"],
            deal_context=deal,
            operating_conclusion=conclusion,
        )
        self.assertEqual(turn["deal_context_version"], 2)
        self.assertIn("seasonal grazing", turn["answer"].lower())
        self.assertNotIn("seasonal or year-round", turn["answer"].lower())
        self.assertNotIn("operation type is still unknown", " ".join(turn["missing_evidence"]).lower())

    def test_chat_without_conclusion_fails(self) -> None:
        with self.assertRaises(KeyError):
            post_advisor_chat("advisor_missing_run", message="hello")

        # Succeeded run path is covered above; empty message is rejected before store work.
        with self.assertRaises(AdvisorChatError) as exc:
            generate_chat_turn(
                run_id="run_chat_empty",
                user_message="   ",
                packet={"observations": []},
                deal_context={"context_version": 1},
                operating_conclusion={"headline": "x" * 20, "summary": "y" * 40},
            )
        self.assertEqual(exc.exception.code, "CHAT_MESSAGE_REQUIRED")


def _mireye_fetch_ok_response(body: dict) -> tuple[dict, dict]:
    field_ids = list(body.get("fields") or [])
    fields = {}
    for fid in field_ids:
        if fid == "nearest_waterbody_name":
            fields[fid] = {"value": None, "source": "USGS_NHDPLUS_HR"}
            continue
        if fid in {"wetland_fraction_of_parcel", "wetland_acres_on_parcel"}:
            fields[fid] = {
                "value": 0.01 if "fraction" in fid else 0.5,
                "source": "USFWS_NWI",
                "confidence": "medium",
            }
            continue
        if fid in {
            "nearest_usgs_gage_name",
            "nearest_usgs_gage_distance_m",
            "nearest_usgs_gage_daily_discharge_cfs",
            "soil_restrictive_layer_depth_cm",
            "soil_restrictive_layer_kind",
            "soil_ponding_frequency_class",
        }:
            continue
        fields[fid] = {
            "value": 1 if fid.startswith("intersects") else f"fixture_{fid}",
            "source": "TEST_SOURCE",
            "confidence": "medium",
        }
    response = {
        "fields": fields,
        "partial_failures": [],
        "fetched_at": "2026-08-14T00:00:00+00:00",
        "request_id": "chat_mireye_fetch_1",
    }
    transport = {
        "ok": True,
        "http_status": 200,
        "endpoint": "/v1/fetch",
        "error_class": None,
    }
    return response, transport


class MireyeFirstChatGroundingTests(unittest.TestCase):
    """Nambe main path: Combined Packet + Profile + Interpretation + Deal Context → Chat."""

    def setUp(self) -> None:
        reset_advisor_runs_for_tests()
        get_parcel_resolution_store().clear()

    def tearDown(self) -> None:
        set_advisor_mireye_hooks_for_tests(request_fn=None, lookup_fn=None)
        reset_advisor_runs_for_tests()

    def _nambe_mireye_first(self) -> dict:
        payload = _payload()
        resolution_id = _confirm(payload)

        def lookup_fn(place: str, **kwargs):
            return _lookup_transport_result(
                ok=True,
                address=place,
                disposition="resolved",
                sanitized_response=payload,
            )

        def request_fn(*, endpoint: str, body: dict):
            self.assertEqual(endpoint, "/v1/fetch")
            self.assertEqual(set(body.get("fields") or []), set(manifest_field_ids()))
            return _mireye_fetch_ok_response(body)

        set_advisor_mireye_hooks_for_tests(request_fn=request_fn, lookup_fn=lookup_fn)
        result = run_cper_advisor_agent(
            address=NAMBE_DEMO_ADDRESS,
            fixture_id=None,
            parcel_resolution_id=resolution_id,
            collection_mode=COLLECTION_MODE_MIREYE_FIRST,
        )
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(result["collection_mode"], COLLECTION_MODE_MIREYE_FIRST)
        self.assertIsNone(result["packet"])
        self.assertIsNone(result["operating_conclusion"])
        self.assertIsInstance(result["combined_environmental_evidence_packet"], dict)
        self.assertIsInstance(result["natural_cattle_profile"], dict)
        self.assertIsInstance(result["natural_foundation_interpretation"], dict)
        self.assertIsInstance(result["deal_context"], dict)
        return result

    def test_mireye_first_chat_is_grounded_and_read_only(self) -> None:
        result = self._nambe_mireye_first()
        combined_before = result["combined_environmental_evidence_packet"]
        profile_before = result["natural_cattle_profile"]
        interpretation_before = result["natural_foundation_interpretation"]
        context_before = result["deal_context"]

        body = post_advisor_chat(
            result["run_id"],
            message="What does the evidence say about livestock water on this tract?",
            provider_name="FIXTURE",
        )
        turn = body["turn"]
        self.assertEqual(turn["intent"], "WATER")
        self.assertTrue(turn["judgment"])
        self.assertTrue(turn["answer"])
        self.assertTrue(turn["evidence_refs"])
        self.assertEqual(turn["source"], SOURCE_FALLBACK)

        latest = get_advisor_run(result["run_id"])
        self.assertEqual(
            latest["combined_environmental_evidence_packet"], combined_before
        )
        self.assertEqual(latest["natural_cattle_profile"], profile_before)
        self.assertEqual(
            latest["natural_foundation_interpretation"], interpretation_before
        )
        self.assertEqual(latest["deal_context"], context_before)
        self.assertIsNone(latest["packet"])
        self.assertIsNone(latest["operating_conclusion"])

    def test_mireye_first_api_chat_returns_200(self) -> None:
        result = self._nambe_mireye_first()
        client = TestClient(app)
        got = client.get(f"/v1/advisor/runs/{result['run_id']}/chat")
        self.assertEqual(got.status_code, 200, got.text)

        posted = client.post(
            f"/v1/advisor/runs/{result['run_id']}/chat",
            json={
                "message": "What is the current cattle operating conclusion for this parcel?",
                "provider": "FIXTURE",
            },
        )
        self.assertEqual(posted.status_code, 200, posted.text)
        payload = posted.json()
        self.assertEqual(payload["turn"]["intent"], "OVERALL_CATTLE_CASE")
        self.assertNotIn("CHAT_RUN_INCOMPLETE", posted.text)

        latest = get_advisor_run(result["run_id"])
        self.assertEqual(
            latest["combined_environmental_evidence_packet"]["packet_hash"],
            result["combined_environmental_evidence_packet"]["packet_hash"],
        )
        self.assertEqual(
            latest["natural_cattle_profile"]["profile_hash"],
            result["natural_cattle_profile"]["profile_hash"],
        )
        self.assertEqual(
            latest["natural_foundation_interpretation"]["interpretation_id"],
            result["natural_foundation_interpretation"]["interpretation_id"],
        )
        self.assertEqual(
            latest["deal_context"]["context_version"],
            result["deal_context"]["context_version"],
        )

    def test_chat_view_from_natural_foundation_projects_interpretation(self) -> None:
        result = self._nambe_mireye_first()
        view = chat_view_from_natural_foundation(
            result["natural_foundation_interpretation"]
        )
        self.assertEqual(
            view["conclusion_id"],
            result["natural_foundation_interpretation"]["interpretation_id"],
        )
        self.assertTrue(view["headline"])
        self.assertTrue(view["evidence_refs"])
        workbench = build_chat_workbench(
            packet=result["combined_environmental_evidence_packet"],
            deal_context=result["deal_context"],
            operating_conclusion=view,
            operating_profile=result["natural_cattle_profile"],
            user_message="What should I do next?",
            classified_intent="NEXT_ACTION",
        )
        self.assertTrue(workbench["allowed_evidence_refs"])
        self.assertTrue(workbench["observations"] or workbench["allowed_evidence_refs"])
        self.assertTrue(workbench["cattle_knowledge"])
        self.assertTrue(workbench["place_materials"]["natural_cattle_profile"]["domains"])
        self.assertTrue(
            all(
                not str(row.get("knowledge_id") or "").startswith("LEGAL_ACCESS")
                for row in workbench["cattle_knowledge"]
            )
        )


if __name__ == "__main__":
    unittest.main()
