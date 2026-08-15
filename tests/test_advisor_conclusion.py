"""Slice 4: initial Operating Conclusion + one catalog question."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from rangematch.advisor_agent import (
    DEMO_SCENARIO_NAMBE_CATTLE_V1,
    NAMBE_DEMO_ADDRESS,
    RUN_MODE_VERIFIED_DEMO,
    TRACK_GENERIC,
    enqueue_advisor_run,
    execute_advisor_run,
    get_advisor_deal_context,
    get_advisor_operating_conclusion,
    reset_advisor_runs_for_tests,
    set_advisor_mireye_hooks_for_tests,
    _lookup_transport_result,
    _unit_test_mireye_request,
)
from rangematch.advisor_conclusion import (
    SOURCE_FALLBACK,
    SOURCE_LIVE,
    generate_operating_conclusion,
    render_deterministic_conclusion,
    validate_operating_conclusion,
)
from rangematch.advisor_parcel_gate import (
    require_confirmed_parcel,
    stage_mireye_mapping_for_confirmation,
)
from rangematch.advisor_question import QUESTION_CATALOG, select_one_question
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
        "request_id": f"concl_{parcel_id}",
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


class OperatingConclusionSlice4Tests(unittest.TestCase):
    def setUp(self) -> None:
        reset_advisor_runs_for_tests()
        get_parcel_resolution_store().clear()

    def tearDown(self) -> None:
        set_advisor_mireye_hooks_for_tests(request_fn=None, lookup_fn=None)
        reset_advisor_runs_for_tests()

    def _run_nambe(self) -> dict:
        address = NAMBE_DEMO_ADDRESS
        payload = _payload(
            address,
            lat=39.615,
            lng=-105.235,
            ring=NAMBE_POLYGON,
            parcel_id="NAMBE-CONCL-1",
        )
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
            address=None,
            fixture_id=None,
            parcel_resolution_id=resolution_id,
            run_mode=RUN_MODE_VERIFIED_DEMO,
            demo_scenario_id=DEMO_SCENARIO_NAMBE_CATTLE_V1,
        )
        return execute_advisor_run(queued["run_id"])

    def test_nambe_run_attaches_conclusion_and_preserves_deal_context(self) -> None:
        result = self._run_nambe()
        self.assertEqual(result["track"], TRACK_GENERIC)
        conclusion = result.get("operating_conclusion")
        self.assertIsInstance(conclusion, dict)
        self.assertEqual(conclusion["deal_context_version"], 1)
        self.assertEqual(conclusion["run_id"], result["run_id"])
        self.assertIn(conclusion["status"], {"CONDITIONAL", "EVIDENCE_SUPPORTS_NEXT_STAGE", "OPERATING_CLAIM_NOT_SUPPORTED"})
        self.assertTrue(conclusion["headline"])
        self.assertTrue(conclusion["evidence_refs"])
        self.assertTrue(conclusion["what_would_change_view"])
        question = conclusion["next_question"]
        self.assertEqual(question["question_id"], "Q_OPERATION_TYPE")
        self.assertIn(question["question_id"], QUESTION_CATALOG)
        self.assertEqual(conclusion["source"], SOURCE_FALLBACK)
        self.assertEqual(conclusion["confidence"], "LOW")

        context = result["deal_context"]
        self.assertEqual(context["context_version"], 1)
        fetched_ctx = get_advisor_deal_context(result["run_id"])
        self.assertEqual(fetched_ctx["context_version"], 1)
        fetched = get_advisor_operating_conclusion(result["run_id"])
        self.assertEqual(fetched["conclusion_id"], conclusion["conclusion_id"])

    def test_api_get_conclusion(self) -> None:
        result = self._run_nambe()
        client = TestClient(app)
        got = client.get(f"/v1/advisor/runs/{result['run_id']}/conclusion")
        self.assertEqual(got.status_code, 200, got.text)
        body = got.json()
        self.assertEqual(body["conclusion_id"], result["operating_conclusion"]["conclusion_id"])
        self.assertEqual(body["next_question"]["question_id"], "Q_OPERATION_TYPE")

        missing = client.get("/v1/advisor/runs/advisor_missing/conclusion")
        self.assertEqual(missing.status_code, 404)

    def test_question_catalog_prefers_operation_type_when_unknown(self) -> None:
        selected = select_one_question(
            deal_context={"operation_type": "UNKNOWN", "user_answers": []},
            operating_profile={"domain_attention_order": ["DRINK"]},
            packet={},
        )
        self.assertEqual(selected["question_id"], "Q_OPERATION_TYPE")

    def test_malformed_llm_falls_back_without_raising(self) -> None:
        packet = {
            "observations": [
                {"observation_id": "OBS_ACCESS_1", "label": "Access lead"},
            ],
            "actions": [
                {
                    "action_id": "ACTION_ACCESS_DOCUMENTS",
                    "execution_order": 1,
                    "title": "Request access paper",
                }
            ],
        }
        profile = {
            "profile_hash": "a" * 64,
            "domain_attention_order": ["DRINK"],
            "action_execution_order": ["ACTION_ACCESS_DOCUMENTS"],
        }
        deal = {
            "run_id": "run_concl_test",
            "context_version": 1,
            "geometry_hash": "b" * 64,
            "operation_type": "UNKNOWN",
            "diligence_stage": "SCREENING",
            "seller_claims": [],
            "user_answers": [],
        }
        bad = LLMCompletion(
            content={"operating_conclusion": "not-an-object"},
            provider="DEEPSEEK",
            model_id="mock",
            prompt_version="test",
            generated_at="2026-08-14T00:00:00+00:00",
            provider_status="OK",
            error_code=None,
            error_message=None,
            request_id="req_1",
            retry_count=0,
        )
        provider = MagicMock()
        provider.complete_json.return_value = bad
        with patch("rangematch.advisor_conclusion.get_provider", return_value=provider):
            conclusion = generate_operating_conclusion(
                run_id="run_concl_test",
                packet=packet,
                operating_profile=profile,
                deal_context=deal,
                provider_name="DEEPSEEK",
                knowledge_cards=[
                    {
                        "knowledge_id": "LIVESTOCK_WATER_DILIGENCE_001",
                        "topic": "water",
                        "statement": "Mapped hydrography is not drinking water.",
                        "allowed_use": ["interpret"],
                        "prohibited_use": ["invent"],
                    }
                ],
            )
        self.assertEqual(conclusion["source"], SOURCE_FALLBACK)
        self.assertEqual(conclusion["validation_status"], "PASSED")
        self.assertEqual(conclusion["validation_violations"], [])
        self.assertEqual(conclusion["provenance"]["provider_attempt_status"], "FAILED")
        self.assertTrue(conclusion["provenance"]["provider_attempt_violations"])
        self.assertEqual(conclusion["next_question"]["question_id"], "Q_OPERATION_TYPE")
        self.assertEqual(deal["context_version"], 1)

    def test_prohibited_prose_rejected_then_fallback(self) -> None:
        packet = {
            "observations": [{"observation_id": "OBS_1", "label": "obs"}],
            "actions": [],
        }
        profile = {"profile_hash": "c" * 64, "domain_attention_order": ["MOVE"]}
        deal = {
            "run_id": "run_bad_prose",
            "context_version": 1,
            "geometry_hash": "d" * 64,
            "operation_type": "UNKNOWN",
            "user_answers": [],
            "seller_claims": [],
        }
        selected = select_one_question(
            deal_context=deal, operating_profile=profile, packet=packet
        )
        draft = {
            "schema_version": "RANGEMATCH_ADVISOR_OPERATING_CONCLUSION@0.1.0",
            "conclusion_id": "concl_badprose01",
            "run_id": "run_bad_prose",
            "deal_context_version": 1,
            "operating_profile_hash": "c" * 64,
            "status": "CONDITIONAL",
            "headline": "This ranch supports a stocking rate of 40 cows",
            "summary": (
                "Public evidence is enough to decide buy this ranch today with "
                "year-round drinking water already proven."
            ),
            "primary_constraint": "The wells and fences already settle the case.",
            "confidence": "LOW",
            "evidence_refs": ["OBS_1"],
            "knowledge_refs": [],
            "missing_evidence": [],
            "what_would_change_view": [selected["change_view_text"]],
            "next_action": "Buy immediately after a tour.",
            "next_spend_class": "TARGETED_FIELD_VISIT",
            "next_question": {
                "question_id": selected["question_id"],
                "prompt": selected["prompt"],
                "allowed_field": selected["allowed_field"],
                "what_would_change_view_ref": selected["what_would_change_view_ref"],
            },
            "source": "LIVE_LLM",
            "validation_status": "PASSED",
            "created_at": "2026-08-14T00:00:00+00:00",
        }
        from rangematch.advisor_conclusion import build_conclusion_workbench

        workbench = build_conclusion_workbench(
            packet=packet,
            operating_profile=profile,
            deal_context=deal,
            knowledge_cards=[],
        )
        violations = validate_operating_conclusion(
            draft, workbench=workbench, selected_question=selected
        )
        self.assertTrue(violations)
        codes = {row["code"] for row in violations}
        self.assertIn("CONCLUSION_PROHIBITED", codes)

        fallback = render_deterministic_conclusion(
            run_id="run_bad_prose",
            packet=packet,
            operating_profile=profile,
            deal_context=deal,
            knowledge_cards=[],
            violations=violations,
        )
        clean = validate_operating_conclusion(
            fallback, workbench=workbench, selected_question=selected
        )
        self.assertEqual(clean, [])

    def test_string_list_fields_from_llm_are_coerced_not_character_split(self) -> None:
        packet = {
            "observations": [
                {"observation_id": "OBS_1", "label": "obs"},
                {"observation_id": "OBS_ROAD", "label": "road"},
            ],
            "actions": [
                {
                    "action_id": "ACTION_ACCESS_DOCUMENTS",
                    "execution_order": 1,
                    "title": "Request access paper",
                }
            ],
        }
        profile = {
            "profile_hash": "e" * 64,
            "domain_attention_order": ["DRINK"],
            "action_execution_order": ["ACTION_ACCESS_DOCUMENTS"],
        }
        deal = {
            "run_id": "run_string_list",
            "context_version": 1,
            "geometry_hash": "f" * 64,
            "operation_type": "UNKNOWN",
            "diligence_stage": "SCREENING",
            "seller_claims": [],
            "user_answers": [],
        }
        selected = select_one_question(
            deal_context=deal, operating_profile=profile, packet=packet
        )
        change_text = str(selected["change_view_text"])
        good = LLMCompletion(
            content={
                "operating_conclusion": {
                    "status": "CONDITIONAL",
                    "headline": "Conditional cattle case pending cheap diligence",
                    "summary": (
                        "Public evidence frames a preliminary cattle operating picture. "
                        "Hydrography layers remain inventory leads pending field check."
                    ),
                    "primary_constraint": (
                        "Livestock-water reliability is still unverified from public layers."
                    ),
                    "confidence": "LOW",
                    "evidence_refs": ["OBS_1", "OBS_ROAD"],
                    "knowledge_refs": ["LIVESTOCK_WATER_DILIGENCE_001"],
                    "missing_evidence": "Buyer operation type is still UNKNOWN.",
                    # Classic DeepSeek slip: prose string instead of string[].
                    "what_would_change_view": change_text,
                    "next_action": "Request access or title documents before travel.",
                    "next_spend_class": "DOCUMENT_REVIEW",
                    "next_question_id": selected["question_id"],
                }
            },
            provider="DEEPSEEK",
            model_id="mock",
            prompt_version="test",
            generated_at="2026-08-14T00:00:00+00:00",
            provider_status="OK",
            error_code=None,
            error_message=None,
            request_id="req_str",
            retry_count=0,
        )
        provider = MagicMock()
        provider.complete_json.return_value = good
        with patch("rangematch.advisor_conclusion.get_provider", return_value=provider):
            conclusion = generate_operating_conclusion(
                run_id="run_string_list",
                packet=packet,
                operating_profile=profile,
                deal_context=deal,
                provider_name="DEEPSEEK",
                knowledge_cards=[
                    {
                        "knowledge_id": "LIVESTOCK_WATER_DILIGENCE_001",
                        "topic": "water",
                        "statement": "Mapped hydrography is not drinking water.",
                        "allowed_use": ["interpret"],
                        "prohibited_use": ["invent"],
                    }
                ],
            )
        self.assertEqual(conclusion["source"], SOURCE_LIVE)
        self.assertEqual(conclusion["validation_status"], "PASSED")
        self.assertEqual(conclusion["what_would_change_view"], [change_text])
        self.assertNotEqual(list(change_text), conclusion["what_would_change_view"])

    def test_confidence_and_spend_aliases_normalize_to_schema(self) -> None:
        from rangematch.advisor_conclusion import (
            _normalize_confidence,
            _normalize_spend_class,
        )

        self.assertEqual(_normalize_confidence("medium"), "MODERATE")
        self.assertEqual(_normalize_confidence("HIGH"), "MODERATE")
        self.assertEqual(_normalize_spend_class("DOCUMENT_AND_FIELD_VISIT"), "DOCUMENT_REVIEW")
        self.assertEqual(_normalize_spend_class("field-visit"), "TARGETED_FIELD_VISIT")

    def test_seasonal_answer_rejects_stale_undefined_operation_prose(self) -> None:
        packet = {
            "observations": [
                {"observation_id": "OBS_1", "label": "obs"},
                {"observation_id": "OBS_ROAD", "label": "road"},
            ],
            "actions": [
                {
                    "action_id": "ACTION_ACCESS_DOCUMENTS",
                    "execution_order": 1,
                    "title": "Request access paper",
                }
            ],
        }
        profile = {
            "profile_hash": "9" * 64,
            "domain_attention_order": ["DRINK"],
            "action_execution_order": ["ACTION_ACCESS_DOCUMENTS"],
        }
        deal = {
            "run_id": "run_seasonal_revise",
            "context_version": 2,
            "geometry_hash": "8" * 64,
            "operation_type": "SEASONAL_GRAZING",
            "diligence_stage": "SCREENING",
            "seller_claims": [],
            "user_answers": [
                {
                    "field": "operation_type",
                    "value": "SEASONAL_GRAZING",
                    "provenance": "USER_SUPPLIED_UNVERIFIED",
                }
            ],
        }
        previous = {
            "conclusion_id": "concl_prev_seasonal",
            "deal_context_version": 1,
            "status": "CONDITIONAL",
            "headline": "The property needs one operating answer before the cattle case is clear",
            "summary": "The intended operation has not yet been defined.",
            "primary_constraint": "Is the intended cattle use seasonal or year-round?",
            "next_action": "Request access or title documents before travel.",
            "next_spend_class": "DOCUMENT_REVIEW",
            "next_question": {
                "question_id": "Q_OPERATION_TYPE",
                "prompt": "Are you evaluating this property for seasonal grazing or a year-round cow-calf operation?",
            },
        }
        selected = select_one_question(
            deal_context=deal, operating_profile=profile, packet=packet
        )
        stale = LLMCompletion(
            content={
                "operating_conclusion": {
                    "status": "CONDITIONAL",
                    "headline": "The property needs one operating answer before the cattle case is clear",
                    "summary": (
                        "Public evidence frames a preliminary cattle operating picture, "
                        "but the intended operation has not yet been defined."
                    ),
                    "primary_constraint": (
                        "Is the intended cattle use seasonal grazing or a year-round "
                        "cow-calf operation?"
                    ),
                    "confidence": "MODERATE",
                    "evidence_refs": ["OBS_1", "OBS_ROAD"],
                    "knowledge_refs": ["LIVESTOCK_WATER_DILIGENCE_001"],
                    "missing_evidence": ["Buyer operation type is still UNKNOWN."],
                    "what_would_change_view": [str(selected["change_view_text"])],
                    "next_action": "Ask whether the seller claims developed livestock water.",
                    "next_spend_class": "REMOTE_INFORMATION_REQUEST",
                    "next_question_id": selected["question_id"],
                }
            },
            provider="DEEPSEEK",
            model_id="mock",
            prompt_version="test",
            generated_at="2026-08-14T00:00:00+00:00",
            provider_status="OK",
            error_code=None,
            error_message=None,
            request_id="req_seasonal",
            retry_count=0,
        )
        provider = MagicMock()
        provider.complete_json.return_value = stale
        with patch("rangematch.advisor_conclusion.get_provider", return_value=provider):
            conclusion = generate_operating_conclusion(
                run_id="run_seasonal_revise",
                packet=packet,
                operating_profile=profile,
                deal_context=deal,
                provider_name="DEEPSEEK",
                previous_conclusion=previous,
                knowledge_cards=[
                    {
                        "knowledge_id": "LIVESTOCK_WATER_DILIGENCE_001",
                        "topic": "water",
                        "statement": "Mapped hydrography is not drinking water.",
                        "allowed_use": ["interpret"],
                        "prohibited_use": ["invent"],
                    }
                ],
            )
        self.assertEqual(conclusion["source"], SOURCE_FALLBACK)
        self.assertEqual(conclusion["validation_status"], "PASSED")
        self.assertEqual(conclusion["provenance"]["provider_attempt_status"], "FAILED")
        codes = {
            row["code"]
            for row in conclusion["provenance"]["provider_attempt_violations"]
        }
        self.assertIn("CONCLUSION_CONTEXT_OPERATION_MISMATCH", codes)
        prose = " ".join(
            [
                str(conclusion["headline"]),
                str(conclusion["summary"]),
                str(conclusion["primary_constraint"]),
            ]
        ).lower()
        self.assertIn("seasonal", prose)
        self.assertNotIn("has not yet been defined", prose)


if __name__ == "__main__":
    unittest.main()
