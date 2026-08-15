"""Slice 6: thin grounded chat — six intents, read-only, fail-soft.

Never mutates Packet / Combined Evidence Packet, Deal Context, Operating
Conclusion, Natural Cattle Profile, or Natural Foundation Interpretation.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from jsonschema import Draft202012Validator

from rangematch.advisor_insight import load_approved_knowledge_cards
from rangematch.advisor_schema import _load_schema
from rangematch.llm_provider import get_provider, is_live_llm_provider

SCHEMA_VERSION = "RANGEMATCH_ADVISOR_CHAT_TURN@0.1.0"
PROMPT_VERSION = "RANGEMATCH_ADVISOR_CHAT@0.1.0"
SOURCE_LIVE = "LIVE_LLM"
SOURCE_FALLBACK = "DETERMINISTIC_FALLBACK"

INTENTS = (
    "OVERALL_CATTLE_CASE",
    "WATER",
    "FEED",
    "MOVEMENT",
    "ACCESS",
    "NEXT_ACTION",
    "OUT_OF_SCOPE",
)
SUPPORTED_INTENTS = frozenset(INTENTS) - {"OUT_OF_SCOPE"}

SUGGESTED_QUESTIONS: list[dict[str, str]] = [
    {
        "intent": "OVERALL_CATTLE_CASE",
        "prompt": "What is the current cattle operating conclusion for this parcel?",
    },
    {
        "intent": "WATER",
        "prompt": "What does the evidence say about livestock water on this tract?",
    },
    {
        "intent": "FEED",
        "prompt": "How should I read feed or forage context from the public evidence?",
    },
    {
        "intent": "MOVEMENT",
        "prompt": "How do terrain and parcel form affect livestock movement here?",
    },
    {
        "intent": "ACCESS",
        "prompt": "What is known about physical road contact versus documentary access?",
    },
    {
        "intent": "NEXT_ACTION",
        "prompt": "What should I do next, and what spend class does that imply?",
    },
]

PROHIBITED = re.compile(
    r"(?:stocking rate|carrying capacity|herd size|buy this|do not buy|"
    r"has legal access|no legal access|"
    r"\b(?:a well|the well|wells|stock tank|fences?|gates?|corrals?|barns?)\b)",
    re.I,
)
INTERNAL_ID_IN_PROSE = re.compile(
    r"\b(?:OBS|VAR|F\d{2}|ACTION|BOTTLENECK|CLAIM|PACKET|"
    r"LIVESTOCK_WATER_DILIGENCE|LEGAL_ACCESS_DILIGENCE|"
    r"RAP_INTERPRETATION|EVIDENCE_STATUS_INTERPRETATION)_[A-Z0-9_]+\b",
    re.I,
)

CHAT_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "intent",
        "judgment",
        "answer",
        "evidence_refs",
        "knowledge_refs",
        "missing_evidence",
        "suggested_follow_up",
    ],
    "properties": {
        "intent": {"type": "string", "enum": list(INTENTS)},
        "judgment": {"type": "string", "minLength": 12, "maxLength": 280},
        "answer": {"type": "string", "minLength": 40, "maxLength": 1600},
        "evidence_refs": {"type": "array", "items": {"type": "string"}},
        "knowledge_refs": {"type": "array", "items": {"type": "string"}},
        "missing_evidence": {"type": "array", "items": {"type": "string"}},
        "suggested_follow_up": {"type": "string", "minLength": 8, "maxLength": 280},
    },
}

CHAT_BUNDLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["chat_turn"],
    "properties": {"chat_turn": CHAT_OUTPUT_SCHEMA},
}

SYSTEM_PROMPT = """You are a buyer-side cattle diligence chat for RangeMatch.
Return JSON: {"chat_turn": {...}} with intent, judgment, answer, evidence_refs,
knowledge_refs, missing_evidence, suggested_follow_up.

Rules:
- Answer only from the workbench (conclusion, deal context, packet, knowledge).
- Prefer judgment-first prose. Mention preliminary once.
- Keep judgment under 180 characters; put explanation in answer.
- Treat Deal Context as current. Never ask for or describe as unknown a field
  already present in user_answers or operation_type.
- Cite only refs present in the workbench.
- Put refs only in evidence_refs/knowledge_refs. Never expose internal IDs such
  as OBS_*, ACTION_*, or knowledge-card IDs in judgment, answer, or follow-up.
- Do not invent wells, fences, gates, drinkers, stocking rates, or legal access.
- Do not change or propose edits to physical evidence.
- If the question is outside the six supported intents, set intent=OUT_OF_SCOPE
  and suggest one supported follow-up question.
"""


class AdvisorChatError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def suggested_chat_questions() -> list[dict[str, str]]:
    return [dict(row) for row in SUGGESTED_QUESTIONS]


def classify_chat_intent(message: str) -> str:
    text = (message or "").strip().lower()
    if not text:
        return "OUT_OF_SCOPE"
    # Price / buy / appraisal / stocking → out of scope first.
    if re.search(
        r"\b(buy|purchase|price|offer|appraisal|loan|mortgage|stocking rate|"
        r"carrying capacity|how many (cows|head)|roi|return)\b",
        text,
    ):
        return "OUT_OF_SCOPE"
    if re.search(r"\b(next (step|action|spend)|what should i (do|ask)|follow[- ]?up)\b", text):
        return "NEXT_ACTION"
    if re.search(r"\b(water|drink|hydrograph|nhd|tank|pond|well)\b", text):
        return "WATER"
    if re.search(r"\b(feed|forage|grass|rap|production|pasture)\b", text):
        return "FEED"
    if re.search(r"\b(move|movement|terrain|slope|cross|paddock|parcel form)\b", text):
        return "MOVEMENT"
    if re.search(r"\b(access|entrance|title|easement|road contact|deed)\b", text):
        return "ACCESS"
    if re.search(
        r"\b(overall|conclusion|operating (case|picture|reading)|how does this (ranch|tract) read)\b",
        text,
    ):
        return "OVERALL_CATTLE_CASE"
    if re.search(r"\b(cattle|cow[- ]?calf|seasonal grazing|diligence)\b", text):
        return "OVERALL_CATTLE_CASE"
    return "OUT_OF_SCOPE"


def _packet_observation_rows(packet: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    """Buyer Packet observations or Combined Environmental Evidence Packet buckets."""
    if not isinstance(packet, Mapping):
        return []
    rows: list[Mapping[str, Any]] = []
    for row in packet.get("observations") or []:
        if isinstance(row, Mapping):
            rows.append(row)
    for key in ("mireye_observations", "core_observations", "supplement_observations"):
        for row in packet.get(key) or []:
            if isinstance(row, Mapping):
                rows.append(row)
    return rows


def _obs_ids(packet: Mapping[str, Any] | None) -> list[str]:
    ids: list[str] = []
    for row in _packet_observation_rows(packet):
        if row.get("observation_id"):
            ids.append(str(row["observation_id"]))
    if isinstance(packet, Mapping):
        for row in packet.get("bottleneck_candidates") or []:
            if isinstance(row, Mapping) and row.get("bottleneck_id"):
                ids.append(str(row["bottleneck_id"]))
    return ids


def chat_view_from_natural_foundation(
    interpretation: Mapping[str, Any],
) -> dict[str, Any]:
    """Project Natural Foundation Interpretation into the chat advisor-view shape.

    Chat remains read-only: this builds a transient view object and never writes
    back to the run record's interpretation or profile.
    """
    controlling = interpretation.get("controlling_factor") or {}
    next_q = interpretation.get("next_question") or {}
    reason = str(controlling.get("reason") or "").strip()
    domain = controlling.get("domain")
    if domain and reason:
        primary = f"{domain}: {reason}"
    else:
        primary = reason or str(interpretation.get("advisor_view") or "Natural foundation still provisional.")
    return {
        "conclusion_id": interpretation.get("interpretation_id"),
        "status": interpretation.get("status"),
        "headline": interpretation.get("advisor_judgment")
        or interpretation.get("advisor_view"),
        "summary": interpretation.get("integrated_natural_reading")
        or interpretation.get("land_character"),
        "primary_constraint": primary,
        "next_action": interpretation.get("refinement_request"),
        "next_spend_class": "REMOTE_INFORMATION_REQUEST",
        "confidence": "DIRECTIONAL",
        "next_question": next_q.get("prompt") if isinstance(next_q, Mapping) else None,
        "evidence_refs": list(interpretation.get("cited_profile_refs") or [])[:8],
        "knowledge_refs": list(interpretation.get("knowledge_refs") or [])[:8],
        "missing_evidence": list(interpretation.get("what_would_change_the_view") or [])[
            :8
        ],
    }


def build_chat_workbench(
    *,
    packet: Mapping[str, Any],
    deal_context: Mapping[str, Any],
    operating_conclusion: Mapping[str, Any],
    operating_profile: Mapping[str, Any] | None = None,
    knowledge_cards: list[dict[str, Any]] | None = None,
    user_message: str,
    classified_intent: str,
) -> dict[str, Any]:
    cards = knowledge_cards if knowledge_cards is not None else load_approved_knowledge_cards()
    observation_rows = _packet_observation_rows(packet)
    return {
        "user_message": user_message,
        "classified_intent_hint": classified_intent,
        "supported_intents": sorted(SUPPORTED_INTENTS),
        "suggested_questions": suggested_chat_questions(),
        "deal_context": {
            "context_version": deal_context.get("context_version"),
            "operation_type": deal_context.get("operation_type"),
            "diligence_stage": deal_context.get("diligence_stage"),
            "user_answers": [
                {"field": row.get("field"), "value": row.get("value")}
                for row in (deal_context.get("user_answers") or [])
                if isinstance(row, Mapping)
            ],
        },
        "operating_conclusion": {
            "status": operating_conclusion.get("status"),
            "headline": operating_conclusion.get("headline"),
            "summary": operating_conclusion.get("summary"),
            "primary_constraint": operating_conclusion.get("primary_constraint"),
            "next_action": operating_conclusion.get("next_action"),
            "next_spend_class": operating_conclusion.get("next_spend_class"),
            "confidence": operating_conclusion.get("confidence"),
            "next_question": operating_conclusion.get("next_question"),
            "evidence_refs": list(operating_conclusion.get("evidence_refs") or [])[:8],
            "knowledge_refs": list(operating_conclusion.get("knowledge_refs") or [])[:8],
            "missing_evidence": list(operating_conclusion.get("missing_evidence") or [])[:8],
        },
        "operating_profile": {
            "domain_attention_order": (operating_profile or {}).get("domain_attention_order"),
            "action_execution_order": (operating_profile or {}).get("action_execution_order"),
            "overall_natural_foundation": (operating_profile or {}).get(
                "overall_natural_foundation"
            ),
        },
        "observations": [
            {
                "observation_id": row.get("observation_id"),
                "label": row.get("label") or row.get("title") or row.get("field_id"),
                "summary": (
                    row.get("summary")
                    or row.get("statement")
                    or str(row.get("value") or "")
                )[:180],
            }
            for row in observation_rows
            if isinstance(row, Mapping)
        ][:16],
        "allowed_evidence_refs": _obs_ids(packet) or ["PACKET"],
        "knowledge_cards": [
            {
                "knowledge_id": row.get("knowledge_id"),
                "topic": row.get("topic"),
                "statement": row.get("statement"),
            }
            for row in cards
        ][:12],
    }


def _pick_knowledge(cards: list[dict[str, Any]], *preferred: str) -> list[str]:
    ids = [str(row.get("knowledge_id")) for row in cards if row.get("knowledge_id")]
    out = [kid for kid in preferred if kid in ids]
    return out[:3] or ids[:1]


def render_deterministic_chat_turn(
    *,
    run_id: str,
    user_message: str,
    intent: str,
    packet: Mapping[str, Any],
    deal_context: Mapping[str, Any],
    operating_conclusion: Mapping[str, Any],
    knowledge_cards: list[dict[str, Any]] | None = None,
    violations: list[dict[str, str]] | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cards = knowledge_cards if knowledge_cards is not None else load_approved_knowledge_cards()
    evidence = list(operating_conclusion.get("evidence_refs") or [])[:4]
    if not evidence:
        evidence = (_obs_ids(packet) or ["PACKET"])[:3]
    missing = list(operating_conclusion.get("missing_evidence") or [])[:3]
    operation = str(deal_context.get("operation_type") or "UNKNOWN")
    headline = str(operating_conclusion.get("headline") or "Provisional cattle operating reading")
    constraint = str(
        operating_conclusion.get("primary_constraint")
        or "The next diligence step still controls the case."
    )
    next_action = str(
        operating_conclusion.get("next_action") or "Request the next cheap diligence document."
    )
    spend = str(operating_conclusion.get("next_spend_class") or "REMOTE_INFORMATION_REQUEST")
    follow = next(
        (row["prompt"] for row in SUGGESTED_QUESTIONS if row["intent"] == "NEXT_ACTION"),
        "What should I do next, and what spend class does that imply?",
    )
    if operation in {"SEASONAL_GRAZING", "YEAR_ROUND_COW_CALF"}:
        missing = [
            item
            for item in missing
            if "operation type is still unknown" not in str(item).lower()
            and "operation has not yet been defined" not in str(item).lower()
            and "needs one operating answer" not in str(item).lower()
        ]

    if intent == "OUT_OF_SCOPE":
        judgment = "That question is outside this parcel chat's supported scope."
        answer = (
            "This chat only answers overall cattle operating case, water, feed, movement, "
            "access, and next action for the confirmed parcel. It will not give purchase, "
            "price, appraisal, loan, or precise stocking advice. Ask one of the suggested "
            "supported questions instead."
        )
        knowledge = _pick_knowledge(cards, "EVIDENCE_STATUS_INTERPRETATION_001")
        follow = SUGGESTED_QUESTIONS[0]["prompt"]
        missing = missing or ["A supported intent question has not been asked yet."]
    elif intent == "WATER":
        judgment = "Mapped water is investigation leads only, not proven drinkers."
        operation_context = (
            "For the stated seasonal grazing plan, the question is whether a reliable "
            "source is available during the grazing months."
            if operation == "SEASONAL_GRAZING"
            else "For the stated year-round cow-calf plan, continuous water reliability is required."
            if operation == "YEAR_ROUND_COW_CALF"
            else "The intended operating season still controls how much water reliability is required."
        )
        answer = (
            f"{operation_context} For this parcel, the current operating constraint is: {constraint} "
            "Public hydrography or water-related observations can guide a field inventory, "
            "but they do not establish usable livestock water, year-round reliability, or "
            "a legal right. Treat any seller water claim in Deal Context as unverified user "
            "context until documents or a narrow visit check it."
        )
        knowledge = _pick_knowledge(cards, "LIVESTOCK_WATER_DILIGENCE_001")
        follow = SUGGESTED_QUESTIONS[1]["prompt"]
    elif intent == "FEED":
        judgment = "Feed context is provisional and must stay tied to parcel observations."
        answer = (
            "Public forage or production context can frame attention, but it does not "
            f"finish a cattle operating claim by itself. The live conclusion still reads: "
            f"{headline} Keep feed notes subordinate to the controlling constraint and the "
            "next defined diligence spend."
        )
        knowledge = _pick_knowledge(cards, "RAP_INTERPRETATION_001", "EVIDENCE_STATUS_INTERPRETATION_001")
        follow = SUGGESTED_QUESTIONS[2]["prompt"]
    elif intent == "MOVEMENT":
        judgment = "Movement reading follows terrain and parcel form, not invented infrastructure."
        answer = (
            "Terrain, parcel shape, and road contact can change how cattle would use the "
            "tract, but the chat will not invent fences, gates, or corrals. Use movement "
            "context to prioritize what a visit should check after cheaper paper steps, "
            f"while the operating constraint remains: {constraint}"
        )
        knowledge = _pick_knowledge(cards, "EVIDENCE_STATUS_INTERPRETATION_001")
        follow = SUGGESTED_QUESTIONS[3]["prompt"]
    elif intent == "ACCESS":
        judgment = "Road contact is physical context, not a legal-access conclusion."
        answer = (
            "Public layers may show road contact or entrance geometry, but that is not a "
            "recorded access or title conclusion. Keep documentary access ahead of travel "
            "when the conclusion still sequences paper before a field walk. "
            f"Current next action: {next_action}"
        )
        knowledge = _pick_knowledge(cards, "LEGAL_ACCESS_DILIGENCE_001")
        follow = SUGGESTED_QUESTIONS[4]["prompt"]
    elif intent == "NEXT_ACTION":
        judgment = f"Next spend stays {spend.replace('_', ' ').lower()}."
        answer = (
            f"Do this next: {next_action} "
            f"Buyer operation type in Deal Context is {operation}. "
            "Chat will not rewrite the Operating Conclusion; it only restates the current "
            "validated next step for this parcel."
        )
        knowledge = _pick_knowledge(
            cards, "LEGAL_ACCESS_DILIGENCE_001", "EVIDENCE_STATUS_INTERPRETATION_001"
        )
        next_q = operating_conclusion.get("next_question")
        if isinstance(next_q, Mapping):
            follow = str(next_q.get("prompt") or follow)
        elif isinstance(next_q, str) and next_q.strip():
            follow = next_q.strip()
    else:  # OVERALL_CATTLE_CASE
        judgment = headline[:280] if len(headline) >= 12 else "The cattle case remains provisional."
        answer = (
            f"{operating_conclusion.get('summary') or headline} "
            f"Primary constraint: {constraint} "
            f"Confidence is {operating_conclusion.get('confidence') or 'LOW'}. "
            "This is a provisional reading grounded in the confirmed parcel evidence and "
            "current Deal Context, not a buy or stocking decision."
        )
        knowledge = list(operating_conclusion.get("knowledge_refs") or [])[:3] or _pick_knowledge(
            cards, "EVIDENCE_STATUS_INTERPRETATION_001"
        )
        follow = SUGGESTED_QUESTIONS[0]["prompt"]

    return {
        "schema_version": SCHEMA_VERSION,
        "turn_id": f"chat_{uuid4().hex[:16]}",
        "run_id": run_id,
        "deal_context_version": int(deal_context.get("context_version") or 1),
        "intent": intent,
        "user_message": user_message,
        "judgment": judgment,
        "answer": answer,
        "evidence_refs": evidence,
        "knowledge_refs": knowledge,
        "missing_evidence": missing
        or ["Developed livestock-water systems are not verified from public layers alone."],
        "suggested_follow_up": follow,
        "source": SOURCE_FALLBACK,
        "validation_status": "PASSED",
        "validation_violations": [],
        "created_at": _utc_now(),
        "provenance": {
            **(provenance or {"provider_status": "DETERMINISTIC"}),
            "provider_attempt_status": "FAILED" if violations else "NOT_ATTEMPTED",
            "provider_attempt_violations": list(violations or []),
        },
    }


def validate_chat_turn(
    turn: Mapping[str, Any] | Any,
    *,
    workbench: Mapping[str, Any],
) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    if not isinstance(turn, Mapping):
        return [
            {
                "code": "CHAT_TYPE_INVALID",
                "message": f"chat_turn must be object, got {type(turn).__name__}",
            }
        ]
    schema = _load_schema("advisor_chat_turn.schema.json")
    for err in sorted(
        Draft202012Validator(schema).iter_errors(dict(turn)),
        key=lambda item: list(item.absolute_path),
    ):
        path = ".".join(str(part) for part in err.absolute_path) or "$"
        violations.append({"code": "CHAT_SCHEMA_INVALID", "message": f"{path}: {err.message}"})
    if violations:
        return violations

    allowed = {
        str(ref) for ref in (workbench.get("allowed_evidence_refs") or []) if ref
    } | {"PACKET"}
    # Also allow refs already on the operating conclusion in the workbench.
    for ref in (workbench.get("operating_conclusion") or {}).get("evidence_refs") or []:
        allowed.add(str(ref))
    for ref in turn.get("evidence_refs") or []:
        if str(ref) not in allowed:
            violations.append({"code": "CHAT_EVIDENCE_REF_UNKNOWN", "message": str(ref)})

    card_ids = {
        str(row.get("knowledge_id"))
        for row in workbench.get("knowledge_cards") or []
        if isinstance(row, Mapping) and row.get("knowledge_id")
    }
    for ref in turn.get("knowledge_refs") or []:
        if str(ref) not in card_ids:
            violations.append({"code": "CHAT_KNOWLEDGE_REF_UNKNOWN", "message": str(ref)})

    prose = " ".join(
        [
            str(turn.get("judgment") or ""),
            str(turn.get("answer") or ""),
            str(turn.get("suggested_follow_up") or ""),
        ]
    )
    hit = PROHIBITED.search(prose)
    if hit:
        violations.append({"code": "CHAT_PROHIBITED", "message": hit.group(0)})
    internal_id = INTERNAL_ID_IN_PROSE.search(prose)
    if internal_id:
        violations.append(
            {"code": "CHAT_INTERNAL_ID_IN_PROSE", "message": internal_id.group(0)}
        )

    operation = str((workbench.get("deal_context") or {}).get("operation_type") or "UNKNOWN").upper()
    normalized = prose.lower()
    stale_unknown = (
        "operation has not yet been defined",
        "operation is not yet defined",
        "operation type is still unknown",
        "needs one operating answer",
        "seasonal vs year-round",
        "seasonal or year-round",
        "before the cattle case is clear",
    )
    if operation in {"SEASONAL_GRAZING", "YEAR_ROUND_COW_CALF"} and any(
        phrase in normalized for phrase in stale_unknown
    ):
        violations.append(
            {
                "code": "CHAT_STALE_DEAL_CONTEXT",
                "message": f"chat contradicts current operation_type={operation}",
            }
        )
    return violations


def generate_chat_turn(
    *,
    run_id: str,
    user_message: str,
    packet: Mapping[str, Any],
    deal_context: Mapping[str, Any],
    operating_conclusion: Mapping[str, Any],
    operating_profile: Mapping[str, Any] | None = None,
    provider_name: str | None = None,
    knowledge_cards: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return one validated chat turn. Never mutates inputs. Fail-soft on LLM errors."""
    message = str(user_message or "").strip()
    if not message:
        raise AdvisorChatError("CHAT_MESSAGE_REQUIRED", "user_message is required")
    if len(message) > 1200:
        raise AdvisorChatError("CHAT_MESSAGE_TOO_LONG", "user_message exceeds 1200 characters")

    cards = knowledge_cards if knowledge_cards is not None else load_approved_knowledge_cards()
    classified = classify_chat_intent(message)
    workbench = build_chat_workbench(
        packet=packet,
        deal_context=deal_context,
        operating_conclusion=operating_conclusion,
        operating_profile=operating_profile,
        knowledge_cards=cards,
        user_message=message,
        classified_intent=classified,
    )
    requested = (provider_name or "FIXTURE").strip().upper()
    provenance_base = {
        "provider": requested,
        "prompt_version": PROMPT_VERSION,
        "classified_intent": classified,
    }

    def _fallback(violations: list[dict[str, str]], provenance: dict[str, Any]) -> dict[str, Any]:
        return render_deterministic_chat_turn(
            run_id=run_id,
            user_message=message,
            intent=classified,
            packet=packet,
            deal_context=deal_context,
            operating_conclusion=operating_conclusion,
            knowledge_cards=cards,
            violations=violations,
            provenance=provenance,
        )

    try:
        if requested == "FIXTURE":
            return _fallback([], {**provenance_base, "provider_status": "FIXTURE", "llm_used": False})

        provider = get_provider(requested)
        completion = provider.complete_json(
            system=SYSTEM_PROMPT,
            user=json.dumps(workbench, ensure_ascii=False),
            prompt_version=PROMPT_VERSION,
            fixture_key=None,
            response_schema=CHAT_BUNDLE_SCHEMA if is_live_llm_provider(requested) else None,
        )
        provenance = {
            **provenance_base,
            "llm_used": completion.provider_status == "OK",
            "provider_status": completion.provider_status,
            "model_id": completion.model_id,
            "generated_at": completion.generated_at,
            "error_code": completion.error_code,
            "request_id": completion.request_id,
            "retry_count": completion.retry_count,
        }
        if not isinstance(completion.content, dict):
            return _fallback(
                [
                    {
                        "code": completion.error_code or "LLM_UNAVAILABLE",
                        "message": completion.error_message or type(completion.content).__name__,
                    }
                ],
                provenance,
            )
        draft = completion.content.get("chat_turn")
        if not isinstance(draft, dict):
            return _fallback(
                [{"code": "CHAT_TURN_MISSING", "message": type(draft).__name__}],
                provenance,
            )
        intent = str(draft.get("intent") or classified)
        if intent not in INTENTS:
            intent = classified
        assembled = {
            "schema_version": SCHEMA_VERSION,
            "turn_id": f"chat_{uuid4().hex[:16]}",
            "run_id": run_id,
            "deal_context_version": int(deal_context.get("context_version") or 1),
            "intent": intent,
            "user_message": message,
            "judgment": draft.get("judgment"),
            "answer": draft.get("answer"),
            "evidence_refs": list(draft.get("evidence_refs") or []),
            "knowledge_refs": list(draft.get("knowledge_refs") or []),
            "missing_evidence": list(draft.get("missing_evidence") or []),
            "suggested_follow_up": draft.get("suggested_follow_up"),
            "source": SOURCE_LIVE if provenance.get("llm_used") else SOURCE_FALLBACK,
            "validation_status": "PASSED",
            "validation_violations": [],
            "created_at": _utc_now(),
            "provenance": provenance,
        }
        violations = validate_chat_turn(assembled, workbench=workbench)
        if violations:
            return _fallback(violations, provenance)
        return assembled
    except AdvisorChatError:
        raise
    except Exception as exc:  # noqa: BLE001 — Slice 6 hard gate
        return _fallback(
            [{"code": "CHAT_PIPELINE_EXCEPTION", "message": type(exc).__name__}],
            {**provenance_base, "provider_status": "FAILED_EXTERNAL", "llm_used": False},
        )
