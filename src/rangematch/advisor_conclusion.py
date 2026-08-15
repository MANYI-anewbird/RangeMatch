"""Slice 4: initial Operating Conclusion + one catalog question.

Packet + Profile + Knowledge + Deal Context → workbench → DeepSeek JSON →
type/schema/semantic validation → conclusion, or deterministic fallback.
Does not accept answers or mutate Deal Context.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from jsonschema import Draft202012Validator

from rangematch.advisor_insight import load_approved_knowledge_cards
from rangematch.advisor_question import (
    QUESTION_CATALOG,
    catalog_ids,
    question_public,
    select_one_question,
)
from rangematch.advisor_schema import _load_schema
from rangematch.llm_provider import get_provider, is_live_llm_provider

SCHEMA_VERSION = "RANGEMATCH_ADVISOR_OPERATING_CONCLUSION@0.1.0"
PROMPT_VERSION = "RANGEMATCH_OPERATING_CONCLUSION@0.1.0"
SOURCE_LIVE = "LIVE_LLM"
SOURCE_FALLBACK = "DETERMINISTIC_FALLBACK"

STATUSES = frozenset(
    {
        "CONDITIONAL",
        "EVIDENCE_SUPPORTS_NEXT_STAGE",
        "OPERATING_CLAIM_NOT_SUPPORTED",
        "BLOCKED",
    }
)
SPEND_CLASSES = frozenset(
    {
        "REMOTE_INFORMATION_REQUEST",
        "DOCUMENT_REVIEW",
        "TARGETED_FIELD_VISIT",
        "SPECIALIST_REVIEW",
    }
)

PROHIBITED = re.compile(
    r"(?:stocking rate|carrying capacity|herd size|buy this|do not buy|"
    r"has legal access|no legal access|"
    # Affirmative access-to-water claims only — “seasonal or year-round” is allowed.
    r"(?:has|with|proven|confirmed|already)\s+year-round\s+(?:water|drinking)|"
    r"year-round\s+(?:water|drinking)\s+(?:is|are)\s+(?:already\s+)?"
    r"(?:proven|confirmed|available|present|verified|established)|"
    # Ban affirmative livestock-water claims, not the diligence vocabulary itself.
    r"(?:has|with|proven|confirmed|already)\s+usable livestock water|"
    r"usable livestock water\s+(?:is|are)\s+(?:already\s+)?"
    r"(?:proven|confirmed|available|present|verified|established)|"
    r"\b(?:a well|the well|wells|stock tank|fences?|gates?|corrals?|barns?)\b)",
    re.I,
)
NHD_AS_DRINKER = re.compile(
    r"\b(?:nhd|mapped (?:water|hydrography))\b.{0,40}\b"
    r"(?:drinking water|drinkers?|stock water|livestock water)\b",
    re.I,
)
NHD_NEGATION = re.compile(
    r"\b(?:not|never|cannot|can'?t|isn'?t|aren'?t|no longer|does not|do not)\b",
    re.I,
)

CONCLUSION_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "status",
        "headline",
        "summary",
        "primary_constraint",
        "confidence",
        "evidence_refs",
        "knowledge_refs",
        "missing_evidence",
        "what_would_change_view",
        "next_action",
        "next_spend_class",
        "next_question_id",
    ],
    "properties": {
        "status": {
            "type": "string",
            "enum": [
                "CONDITIONAL",
                "EVIDENCE_SUPPORTS_NEXT_STAGE",
                "OPERATING_CLAIM_NOT_SUPPORTED",
            ],
        },
        "headline": {"type": "string", "minLength": 12, "maxLength": 160},
        "summary": {"type": "string", "minLength": 40, "maxLength": 1200},
        "primary_constraint": {"type": "string", "minLength": 12, "maxLength": 400},
        "confidence": {"type": "string", "enum": ["LOW", "MODERATE"]},
        "evidence_refs": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        "knowledge_refs": {"type": "array", "items": {"type": "string"}},
        "missing_evidence": {"type": "array", "items": {"type": "string"}},
        "what_would_change_view": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 8},
        },
        "next_action": {"type": "string", "minLength": 8, "maxLength": 400},
        "next_spend_class": {
            "type": "string",
            "enum": list(SPEND_CLASSES),
        },
        "next_question_id": {"type": "string"},
    },
}

CHANGE_STATUS_CHANGED = "CONCLUSION_CHANGED"
CHANGE_STATUS_NARROWED = "UNCHANGED_BUT_NARROWED"
CHANGE_STATUS_NONE = "NO_MATERIAL_CHANGE"
CHANGE_STATUSES = frozenset(
    {CHANGE_STATUS_CHANGED, CHANGE_STATUS_NARROWED, CHANGE_STATUS_NONE}
)

COMPARE_FIELDS = (
    "status",
    "headline",
    "summary",
    "primary_constraint",
    "confidence",
    "next_action",
    "next_spend_class",
)
CORE_FIELDS = frozenset({"status", "headline", "summary", "primary_constraint", "confidence"})
NARROW_FIELDS = frozenset({"next_action", "next_spend_class", "next_question_id"})

CONCLUSION_BUNDLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["operating_conclusion"],
    "properties": {"operating_conclusion": CONCLUSION_OUTPUT_SCHEMA},
}

SYSTEM_PROMPT = """You are a senior buyer-side cattle diligence advisor for RangeMatch.
Return one JSON object: {"operating_conclusion": {...}} with only these fields:
status, headline, summary, primary_constraint, confidence, evidence_refs,
knowledge_refs, missing_evidence, what_would_change_view, next_action,
next_spend_class, next_question_id.

Rules:
- Form a provisional directional cattle operating conclusion for THIS parcel.
- Write summary as one coherent buyer-facing advisor narrative, not a field list.
  It must connect the parcel evidence to how cattle would use the property, name
  the controlling operating issue, and explain why the recommended next step is
  more useful than another broad data search. Use ordinary language and complete
  paragraphs. Do not print enum names, evidence IDs, Factor names, or API terms.
- The headline must be a plain-English judgment a buyer can repeat to another
  person. Do not use CONDITIONAL, confidence labels, or system vocabulary in it.
- Cite only evidence_refs and knowledge_refs present in the workbench.
- next_question_id must be exactly one id from allowed_question_ids.
- what_would_change_view must include the selected question's change_view_text idea.
- Do not invent wells, fences, gates, corrals, drinking water, or stocking rates.
- Do not claim livestock water is proven, confirmed, or already usable.
- Do not equate mapped hydrography with a verified drinker or stock-water system.
- Do not decide buy/no-buy or legal access.
- status may be CONDITIONAL, EVIDENCE_SUPPORTS_NEXT_STAGE, or OPERATING_CLAIM_NOT_SUPPORTED.
  Never output BLOCKED.
- Mention the preliminary nature once. Do not dump every unknown.
- If previous_conclusion is present, revise only interpretation, constraint wording,
  next action, and spend class from the new Deal Context. Never alter physical facts.
- When Deal Context operation_type is SEASONAL_GRAZING or YEAR_ROUND_COW_CALF, the
  revised headline, summary, or primary_constraint MUST explicitly reflect that
  operating frame. Never say the intended operation is still undefined, unknown,
  or needs one operating answer after the buyer has answered.
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _obs_ids(packet: Mapping[str, Any] | None) -> set[str]:
    ids: set[str] = set()
    if not isinstance(packet, Mapping):
        return ids
    for row in packet.get("observations") or []:
        if isinstance(row, Mapping) and row.get("observation_id"):
            ids.add(str(row["observation_id"]))
    for row in packet.get("bottleneck_candidates") or []:
        if isinstance(row, Mapping) and row.get("bottleneck_id"):
            ids.add(str(row["bottleneck_id"]))
    for row in packet.get("claim_gaps") or []:
        if isinstance(row, Mapping) and row.get("claim_id"):
            ids.add(str(row["claim_id"]))
    return ids


def _action_labels(packet: Mapping[str, Any] | None) -> list[str]:
    rows = []
    for row in (packet or {}).get("actions") or []:
        if not isinstance(row, Mapping):
            continue
        rows.append(
            {
                "action_id": row.get("action_id"),
                "title": row.get("title") or row.get("label"),
                "execution_order": row.get("execution_order"),
            }
        )
    return rows


def build_conclusion_workbench(
    *,
    packet: Mapping[str, Any],
    operating_profile: Mapping[str, Any] | None,
    deal_context: Mapping[str, Any],
    knowledge_cards: list[dict[str, Any]] | None = None,
    previous_conclusion: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cards = knowledge_cards if knowledge_cards is not None else load_approved_knowledge_cards()
    selected = select_one_question(
        deal_context=deal_context,
        operating_profile=operating_profile,
        packet=packet,
    )
    workbench = {
        "run_id": deal_context.get("run_id"),
        "deal_context_version": int(deal_context.get("context_version") or 1),
        "geometry_hash": deal_context.get("geometry_hash"),
        "operation_type": deal_context.get("operation_type"),
        "diligence_stage": deal_context.get("diligence_stage"),
        "seller_claims": list(deal_context.get("seller_claims") or []),
        "user_answers": [
            {
                "field": row.get("field"),
                "value": row.get("value"),
                "provenance": row.get("provenance"),
            }
            for row in (deal_context.get("user_answers") or [])
            if isinstance(row, Mapping)
        ],
        "operating_profile": {
            "profile_hash": (operating_profile or {}).get("profile_hash"),
            "domain_attention_order": (operating_profile or {}).get("domain_attention_order"),
            "action_execution_order": (operating_profile or {}).get("action_execution_order"),
            "operating_thesis_inputs": (operating_profile or {}).get("operating_thesis_inputs"),
            "available_domains": (operating_profile or {}).get("available_domains"),
            "field_visit_purpose": (operating_profile or {}).get("field_visit_purpose"),
        },
        "observations": [
            {
                "observation_id": row.get("observation_id"),
                "label": row.get("label") or row.get("title"),
                "summary": row.get("summary") or row.get("statement"),
            }
            for row in (packet.get("observations") or [])
            if isinstance(row, Mapping)
        ][:24],
        "allowed_evidence_refs": sorted(_obs_ids(packet) | {"PACKET"}),
        "actions": _action_labels(packet),
        "knowledge_cards": [
            {
                "knowledge_id": row.get("knowledge_id"),
                "topic": row.get("topic"),
                "statement": row.get("statement"),
                "allowed_use": row.get("allowed_use"),
                "prohibited_use": row.get("prohibited_use"),
            }
            for row in cards
        ],
        "allowed_question_ids": sorted(catalog_ids()),
        "selected_question_hint": question_public(selected),
        "selected_question_change_view": selected.get("change_view_text"),
    }
    if previous_conclusion:
        workbench["previous_conclusion"] = {
            "conclusion_id": previous_conclusion.get("conclusion_id"),
            "deal_context_version": previous_conclusion.get("deal_context_version"),
            "status": previous_conclusion.get("status"),
            "headline": previous_conclusion.get("headline"),
            "summary": previous_conclusion.get("summary"),
            "primary_constraint": previous_conclusion.get("primary_constraint"),
            "next_action": previous_conclusion.get("next_action"),
            "next_spend_class": previous_conclusion.get("next_spend_class"),
            "next_question": previous_conclusion.get("next_question"),
        }
        workbench["revision_mode"] = True
    return workbench


def _first_spend(packet: Mapping[str, Any] | None, profile: Mapping[str, Any] | None) -> tuple[str, str]:
    actions = list((profile or {}).get("action_execution_order") or [])
    if not actions:
        for row in sorted(
            (packet or {}).get("actions") or [],
            key=lambda item: int((item or {}).get("execution_order") or 0),
        ):
            if isinstance(row, Mapping) and row.get("action_id"):
                actions.append(str(row["action_id"]))
                break
    first = actions[0] if actions else "ACTION_ACCESS_DOCUMENTS"
    if first == "ACTION_ACCESS_DOCUMENTS":
        return (
            "Request access or title documents before travel.",
            "DOCUMENT_REVIEW",
        )
    if "WATER" in first:
        return (
            "After access paper, use any visit for a category-level water inventory.",
            "TARGETED_FIELD_VISIT",
        )
    return (
        "Obtain the missing seller or title document that unlocks the next diligence spend.",
        "REMOTE_INFORMATION_REQUEST",
    )


def render_deterministic_conclusion(
    *,
    run_id: str,
    packet: Mapping[str, Any],
    operating_profile: Mapping[str, Any] | None,
    deal_context: Mapping[str, Any],
    knowledge_cards: list[dict[str, Any]] | None = None,
    violations: list[dict[str, str]] | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cards = knowledge_cards if knowledge_cards is not None else load_approved_knowledge_cards()
    selected = select_one_question(
        deal_context=deal_context,
        operating_profile=operating_profile,
        packet=packet,
    )
    next_action, spend = _first_spend(packet, operating_profile)
    obs = sorted(_obs_ids(packet))
    evidence_refs = obs[:4] or ["PACKET"]
    knowledge_refs = [
        str(row.get("knowledge_id"))
        for row in cards
        if str(row.get("knowledge_id") or "")
        in {
            "LIVESTOCK_WATER_DILIGENCE_001",
            "LEGAL_ACCESS_DILIGENCE_001",
            "EVIDENCE_STATUS_INTERPRETATION_001",
            "RAP_INTERPRETATION_001",
        }
    ][:3]
    attention = list((operating_profile or {}).get("domain_attention_order") or [])
    theme = attention[0] if attention else "DRINK"
    change_text = str(selected.get("change_view_text") or "")
    operation = str(deal_context.get("operation_type") or "UNKNOWN").upper()
    answered = {
        str(row.get("field"))
        for row in (deal_context.get("user_answers") or [])
        if isinstance(row, Mapping) and row.get("field")
    }

    if operation == "SEASONAL_GRAZING":
        headline = (
            "Seasonal cattle use is worth investigating, but do not plan around water yet"
        )
        summary = (
            "Your seasonal grazing plan makes the water question narrower, not disappear. "
            "The terrain and vegetation evidence provide a useful preliminary picture and "
            "do not currently stand out as the first issue to spend money on. The controlling "
            "question is whether cattle can reach a reliable source during the months you "
            "intend to graze. Public water mapping cannot answer that by itself, so the next "
            "useful step is to obtain the seller's water description and the entrance paper "
            "before turning a general property visit into the next expense."
        )
        primary = (
            "Can the seller show a reliable livestock-water source for the intended grazing "
            "months, and can the claimed entrance be supported by the property documents?"
        )
        missing = [
            "Developed livestock-water systems are not verified from public layers alone.",
            "Recorded entrance or title basis is not confirmed in Deal Context.",
        ]
        confidence = "MODERATE"
        if "seller_water_claim" not in answered and selected["question_id"] == "Q_SELLER_WATER_CLAIM":
            next_action = (
                "Ask whether the seller claims a developed livestock-water system, "
                "then keep access paper ahead of travel."
            )
            spend = "REMOTE_INFORMATION_REQUEST"
        elif selected["question_id"] == "Q_ACCESS_DOCUMENTS":
            next_action = "Request access or title documents before travel."
            spend = "DOCUMENT_REVIEW"
    elif operation == "YEAR_ROUND_COW_CALF":
        headline = (
            "A year-round cow-calf plan makes reliable water the first operating test"
        )
        summary = (
            "A year-round cow-calf operation depends on a continuous drinking-water system, "
            "and the public evidence does not yet identify one that can be relied on. The "
            "terrain and vegetation information help describe the property, but they do not "
            "resolve that operating requirement. Before treating a site visit as the next "
            "major expense, ask the seller to identify every livestock-water source and send "
            "the entrance documents. That response will determine whether the visit should "
            "focus on inspecting a claimed system or whether the operating story remains too thin."
        )
        primary = (
            "Year-round demand makes livestock-water verification the controlling diligence "
            "risk after basic access paper is in hand."
        )
        missing = [
            "Year-round drinking reliability is not established from public evidence.",
            "Developed livestock-water systems are not verified from public layers alone.",
        ]
        confidence = "MODERATE"
        next_action = (
            "Confirm whether a developed livestock-water claim exists, then sequence "
            "access paper ahead of any field inventory."
        )
        spend = "REMOTE_INFORMATION_REQUEST"
    elif operation == "OTHER":
        headline = (
            "Cattle operating case remains conditional after a nonstandard operation note"
        )
        summary = (
            "The buyer noted an operation type outside the seasonal or year-round frames. "
            f"Public evidence still only supports a preliminary {theme.lower()} reading. "
            "The Agent keeps the next spend cheap and explicit rather than inventing a "
            "stocking or suitability judgment from remote layers alone."
        )
        primary = (
            "Without a standard seasonal or cow-calf frame, the controlling issue is still "
            "the next documented diligence step, not a finished operating claim."
        )
        missing = [
            "Buyer operation type is nonstandard and still needs a clearer cattle frame.",
            "Developed livestock-water systems are not verified from public layers alone.",
        ]
        confidence = "LOW"
    else:
        headline = "The property needs one operating answer before the cattle case is clear"
        summary = (
            "The parcel now has enough public evidence to form a preliminary cattle operating "
            "picture, but the intended operation has not yet been defined. Terrain and "
            "vegetation provide useful context; the larger unresolved issue is how the cattle "
            "would obtain water and whether that need is seasonal or year-round. Answering "
            "one operating question will let the advisor narrow the water requirement and "
            "recommend a more specific next request instead of sending you into another broad search."
        )
        primary = (
            "Is the intended cattle use seasonal grazing or a year-round cow-calf operation?"
        )
        missing = [
            "Buyer operation type is still UNKNOWN in Deal Context.",
            "Developed livestock-water systems are not verified from public layers alone.",
        ]
        confidence = "LOW"

    # Seller water claim answers refine next spend without inventing drinkers.
    for row in deal_context.get("user_answers") or []:
        if not isinstance(row, Mapping):
            continue
        if row.get("field") != "seller_water_claim":
            continue
        claimed = bool(row.get("value"))
        if claimed:
            primary = (
                "A seller developed-water claim is now in Deal Context as unverified user "
                "context; public layers still do not prove usable drinkers."
            )
            next_action = (
                "Keep access documents first, then use any visit for a category-level "
                "water inventory against the claimed system."
            )
            spend = "DOCUMENT_REVIEW"
            missing = [
                "Seller water claim remains USER_SUPPLIED_UNVERIFIED.",
                "Developed livestock-water systems are not verified from public layers alone.",
            ]
        else:
            primary = (
                "No developed-water seller claim is asserted, so remote hydrography stays "
                "investigation leads only and travel must stay narrowly justified."
            )
            next_action = (
                "Request access or title documents before considering a targeted water walk."
            )
            spend = "DOCUMENT_REVIEW"
        break

    for row in deal_context.get("user_answers") or []:
        if not isinstance(row, Mapping):
            continue
        if row.get("field") != "access_documents_on_hand":
            continue
        if bool(row.get("value")):
            next_action = (
                "With access paper already in hand, plan a targeted field inventory rather "
                "than a general ranch tour."
            )
            spend = "TARGETED_FIELD_VISIT"
            primary = (
                "Access paper is reported on hand as unverified user context; the remaining "
                "control is whether livestock-water use can be inventoried cheaply on site."
            )
        else:
            next_action = "Request access or title documents before travel."
            spend = "DOCUMENT_REVIEW"
        break

    conclusion = {
        "schema_version": SCHEMA_VERSION,
        "conclusion_id": f"concl_{uuid4().hex[:16]}",
        "run_id": run_id,
        "deal_context_version": int(deal_context.get("context_version") or 1),
        "operating_profile_hash": (operating_profile or {}).get("profile_hash"),
        "status": "CONDITIONAL",
        "headline": headline,
        "summary": summary,
        "primary_constraint": primary,
        "confidence": confidence,
        "evidence_refs": evidence_refs,
        "knowledge_refs": knowledge_refs,
        "missing_evidence": missing,
        "what_would_change_view": [change_text],
        "next_action": next_action,
        "next_spend_class": spend,
        "next_question": question_public(selected),
        "source": SOURCE_FALLBACK,
        # The deterministic object is itself valid. Provider/model rejection is
        # attempt telemetry, not a failed buyer-facing conclusion.
        "validation_status": "PASSED",
        "validation_violations": [],
        "created_at": _utc_now(),
        "provenance": {
            **(provenance or {"provider_status": "DETERMINISTIC"}),
            "provider_attempt_status": "FAILED" if violations else "NOT_ATTEMPTED",
            "provider_attempt_violations": list(violations or []),
        },
    }
    return conclusion


def build_what_changed(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    user_answer: Mapping[str, Any],
) -> dict[str, Any]:
    """Deterministic before/after diff. Never invents change for its own sake."""
    field_changes: list[dict[str, Any]] = []
    for key in COMPARE_FIELDS:
        left = before.get(key)
        right = after.get(key)
        if left != right:
            field_changes.append({"field": key, "before": left, "after": right})

    before_qid = (before.get("next_question") or {}).get("question_id")
    after_qid = (after.get("next_question") or {}).get("question_id")
    if before_qid != after_qid:
        field_changes.append(
            {
                "field": "next_question_id",
                "before": before_qid,
                "after": after_qid,
            }
        )

    changed_names = {row["field"] for row in field_changes}
    if not changed_names:
        status = CHANGE_STATUS_NONE
        summary = (
            "Conclusion did not change materially after this answer; the next diligence "
            "step is unchanged."
        )
    elif changed_names & CORE_FIELDS:
        status = CHANGE_STATUS_CHANGED
        answer_field = str(user_answer.get("field") or "")
        answer_value = str(user_answer.get("value") or "").upper()
        if answer_field == "operation_type" and answer_value == "SEASONAL_GRAZING":
            summary = (
                "Your seasonal plan narrows the water question to the months cattle would "
                "be on the property. It does not remove the need to verify a reliable source."
            )
        elif answer_field == "operation_type" and answer_value == "YEAR_ROUND_COW_CALF":
            summary = (
                "Your year-round plan makes continuous livestock-water reliability the "
                "first operating test before the property story can be trusted."
            )
        else:
            summary = (
                "Your answer changed how the operating constraint is framed and made the "
                "next diligence request more specific."
            )
    elif changed_names & NARROW_FIELDS:
        status = CHANGE_STATUS_NARROWED
        summary = (
            "Conclusion did not change, but the next step is more specific after this answer."
        )
    else:
        status = CHANGE_STATUS_NARROWED
        summary = (
            "Conclusion did not change, but the next step is more specific after this answer."
        )

    return {
        "change_status": status,
        "summary": summary,
        "fields_changed": field_changes,
        "before_conclusion_id": before.get("conclusion_id"),
        "after_conclusion_id": after.get("conclusion_id"),
        "before_deal_context_version": before.get("deal_context_version"),
        "after_deal_context_version": after.get("deal_context_version"),
        "user_answer": dict(user_answer),
    }


def validate_operating_conclusion(
    conclusion: Mapping[str, Any] | Any,
    *,
    workbench: Mapping[str, Any],
    selected_question: Mapping[str, Any],
) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    if not isinstance(conclusion, Mapping):
        return [
            {
                "code": "CONCLUSION_TYPE_INVALID",
                "message": f"operating_conclusion must be object, got {type(conclusion).__name__}",
            }
        ]

    schema = _load_schema("advisor_operating_conclusion.schema.json")
    for err in sorted(
        Draft202012Validator(schema).iter_errors(dict(conclusion)),
        key=lambda item: list(item.absolute_path),
    ):
        path = ".".join(str(part) for part in err.absolute_path) or "$"
        violations.append({"code": "CONCLUSION_SCHEMA_INVALID", "message": f"{path}: {err.message}"})
    if violations:
        return violations

    status = str(conclusion.get("status") or "")
    if status == "BLOCKED":
        violations.append(
            {
                "code": "CONCLUSION_BLOCKED_NOT_AUTHORIZED",
                "message": "LLM/fallback may not emit BLOCKED without an approved hard gate",
            }
        )
    if status not in STATUSES - {"BLOCKED"} and status != "BLOCKED":
        if status not in STATUSES:
            violations.append({"code": "CONCLUSION_STATUS_INVALID", "message": status})

    spend = str(conclusion.get("next_spend_class") or "")
    if spend not in SPEND_CLASSES:
        violations.append({"code": "CONCLUSION_SPEND_CLASS_INVALID", "message": spend})

    allowed_refs = {
        str(ref)
        for ref in (workbench.get("allowed_evidence_refs") or [])
        if ref
    }
    if not allowed_refs:
        allowed_refs = {
            str(row.get("observation_id"))
            for row in workbench.get("observations") or []
            if isinstance(row, Mapping) and row.get("observation_id")
        } | {"PACKET"}
    for ref in conclusion.get("evidence_refs") or []:
        if str(ref) not in allowed_refs:
            violations.append({"code": "CONCLUSION_EVIDENCE_REF_UNKNOWN", "message": str(ref)})

    card_ids = {
        str(row.get("knowledge_id"))
        for row in workbench.get("knowledge_cards") or []
        if isinstance(row, Mapping)
    }
    for ref in conclusion.get("knowledge_refs") or []:
        if str(ref) not in card_ids:
            violations.append({"code": "CONCLUSION_KNOWLEDGE_REF_UNKNOWN", "message": str(ref)})

    question = conclusion.get("next_question")
    if not isinstance(question, Mapping):
        violations.append({"code": "CONCLUSION_QUESTION_TYPE_INVALID", "message": "next_question"})
    else:
        qid = str(question.get("question_id") or "")
        if qid not in catalog_ids():
            violations.append({"code": "CONCLUSION_QUESTION_NOT_ALLOWED", "message": qid})
        if qid and qid != str(selected_question.get("question_id")):
            violations.append(
                {
                    "code": "CONCLUSION_QUESTION_MISMATCH",
                    "message": f"expected {selected_question.get('question_id')}, got {qid}",
                }
            )
        change_ref = str(question.get("what_would_change_view_ref") or "")
        expected_ref = str(selected_question.get("what_would_change_view_ref") or "")
        if change_ref and expected_ref and change_ref != expected_ref:
            violations.append({"code": "CONCLUSION_QUESTION_CHANGE_REF_MISMATCH", "message": change_ref})

    views = [str(item) for item in (conclusion.get("what_would_change_view") or [])]
    if not views:
        violations.append({"code": "CONCLUSION_CHANGE_VIEW_MISSING", "message": "what_would_change_view"})
    else:
        # Require the selected question's change idea to be represented.
        needle = str(selected_question.get("what_would_change_view_ref") or "")
        joined = " ".join(views).upper()
        if needle and needle not in joined and not any(
            str(selected_question.get("change_view_text") or "")[:40].lower() in item.lower()
            for item in views
        ):
            # Soft bind: at least one view must mention operation/water/access theme.
            theme_ok = any(
                token in joined
                for token in ("OPERATION", "SEASONAL", "WATER", "ACCESS", "DOCUMENT")
            )
            if not theme_ok:
                violations.append(
                    {
                        "code": "CONCLUSION_CHANGE_VIEW_UNBOUND",
                        "message": "what_would_change_view must bind to the selected question",
                    }
                )

    prose = " ".join(
        [
            str(conclusion.get("headline") or ""),
            str(conclusion.get("summary") or ""),
            str(conclusion.get("primary_constraint") or ""),
            str(conclusion.get("next_action") or ""),
            *views,
        ]
    )
    forbidden = PROHIBITED.search(prose)
    if forbidden:
        violations.append({"code": "CONCLUSION_PROHIBITED", "message": forbidden.group(0)})
    for match in NHD_AS_DRINKER.finditer(prose):
        span = prose[match.start() : match.end()]
        if NHD_NEGATION.search(span):
            continue
        violations.append(
            {
                "code": "CONCLUSION_NHD_AS_DRINKER",
                "message": "mapped hydrography is not drinking water",
            }
        )
        break

    # A revised conclusion must actually incorporate the current Deal Context.
    # Structural validity alone is insufficient: an answer cannot be accepted
    # while the prose still says that answer is unknown.
    operation = str(workbench.get("operation_type") or "UNKNOWN").upper()
    normalized_prose = prose.lower()
    stale_unknown = (
        "operation has not yet been defined",
        "operation is not yet defined",
        "operation type is still unknown",
        "intended operation has not yet been defined",
        "intended operation is still unknown",
        "needs one operating answer",
        "before the cattle case is clear",
        "operating answer before the cattle case",
    )
    if operation == "SEASONAL_GRAZING":
        if "seasonal" not in normalized_prose or any(
            phrase in normalized_prose for phrase in stale_unknown
        ):
            violations.append(
                {
                    "code": "CONCLUSION_CONTEXT_OPERATION_MISMATCH",
                    "message": "SEASONAL_GRAZING must be reflected in buyer-facing prose",
                }
            )
    elif operation == "YEAR_ROUND_COW_CALF":
        year_round_terms = ("year-round", "year round", "cow-calf", "cow calf")
        if not any(term in normalized_prose for term in year_round_terms) or any(
            phrase in normalized_prose for phrase in stale_unknown
        ):
            violations.append(
                {
                    "code": "CONCLUSION_CONTEXT_OPERATION_MISMATCH",
                    "message": "YEAR_ROUND_COW_CALF must be reflected in buyer-facing prose",
                }
            )
    return violations


def _as_str_list(value: Any) -> list[str]:
    """Normalize LLM list-or-string slips into a string list.

    DeepSeek sometimes returns a single prose string where the schema wants
    an array. ``list("abc")`` would explode into characters — reject that.
    """
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                out.append(text)
        return out
    text = str(value).strip()
    return [text] if text else []


def _normalize_confidence(value: Any) -> str:
    raw = str(value or "").strip().upper().replace(" ", "_")
    aliases = {
        "LOW": "LOW",
        "MODERATE": "MODERATE",
        "MEDIUM": "MODERATE",
        "MED": "MODERATE",
        "MID": "MODERATE",
        "HIGH": "MODERATE",  # schema has no HIGH; never invent certainty
    }
    return aliases.get(raw, "LOW")


def _normalize_spend_class(value: Any) -> str:
    raw = str(value or "").strip().upper().replace(" ", "_").replace("-", "_")
    aliases = {
        "REMOTE_INFORMATION_REQUEST": "REMOTE_INFORMATION_REQUEST",
        "DOCUMENT_REVIEW": "DOCUMENT_REVIEW",
        "TARGETED_FIELD_VISIT": "TARGETED_FIELD_VISIT",
        "SPECIALIST_REVIEW": "SPECIALIST_REVIEW",
        "DOCUMENT_AND_FIELD_VISIT": "DOCUMENT_REVIEW",
        "FIELD_VISIT": "TARGETED_FIELD_VISIT",
        "SITE_VISIT": "TARGETED_FIELD_VISIT",
        "REMOTE": "REMOTE_INFORMATION_REQUEST",
        "DOCUMENTS": "DOCUMENT_REVIEW",
        "DOCUMENT": "DOCUMENT_REVIEW",
    }
    if raw in SPEND_CLASSES:
        return raw
    return aliases.get(raw, "DOCUMENT_REVIEW")


def _assemble_from_model(
    draft: Mapping[str, Any],
    *,
    run_id: str,
    deal_context: Mapping[str, Any],
    operating_profile: Mapping[str, Any] | None,
    selected_question: Mapping[str, Any],
    provenance: dict[str, Any],
    source: str,
) -> dict[str, Any]:
    qid = str(draft.get("next_question_id") or selected_question.get("question_id"))
    catalog = QUESTION_CATALOG.get(qid) or selected_question
    return {
        "schema_version": SCHEMA_VERSION,
        "conclusion_id": f"concl_{uuid4().hex[:16]}",
        "run_id": run_id,
        "deal_context_version": int(deal_context.get("context_version") or 1),
        "operating_profile_hash": (operating_profile or {}).get("profile_hash"),
        "status": draft.get("status"),
        "headline": draft.get("headline"),
        "summary": draft.get("summary"),
        "primary_constraint": draft.get("primary_constraint"),
        "confidence": _normalize_confidence(draft.get("confidence")),
        "evidence_refs": _as_str_list(draft.get("evidence_refs")),
        "knowledge_refs": _as_str_list(draft.get("knowledge_refs")),
        "missing_evidence": _as_str_list(draft.get("missing_evidence")),
        "what_would_change_view": _as_str_list(draft.get("what_would_change_view")),
        "next_action": draft.get("next_action"),
        "next_spend_class": _normalize_spend_class(draft.get("next_spend_class")),
        "next_question": question_public(catalog),
        "source": source,
        "validation_status": "PASSED",
        "validation_violations": [],
        "created_at": _utc_now(),
        "provenance": {
            **provenance,
            "provider_attempt_status": provenance.get("provider_attempt_status")
            or ("OK" if provenance.get("llm_used") else "NOT_ATTEMPTED"),
        },
    }


def generate_operating_conclusion(
    *,
    run_id: str,
    packet: Mapping[str, Any],
    operating_profile: Mapping[str, Any] | None,
    deal_context: Mapping[str, Any],
    provider_name: str | None = None,
    knowledge_cards: list[dict[str, Any]] | None = None,
    previous_conclusion: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a validated conclusion. Never raises on malformed LLM output."""
    cards = knowledge_cards if knowledge_cards is not None else load_approved_knowledge_cards()
    workbench = build_conclusion_workbench(
        packet=packet,
        operating_profile=operating_profile,
        deal_context=deal_context,
        knowledge_cards=cards,
        previous_conclusion=previous_conclusion,
    )
    selected = select_one_question(
        deal_context=deal_context,
        operating_profile=operating_profile,
        packet=packet,
    )
    requested = (provider_name or "FIXTURE").strip().upper()
    provenance_base = {
        "provider": requested,
        "prompt_version": PROMPT_VERSION,
        "selected_question_id": selected["question_id"],
        "revision": bool(previous_conclusion),
    }

    def _fallback(violations: list[dict[str, str]], provenance: dict[str, Any]) -> dict[str, Any]:
        return render_deterministic_conclusion(
            run_id=run_id,
            packet=packet,
            operating_profile=operating_profile,
            deal_context=deal_context,
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
            response_schema=CONCLUSION_BUNDLE_SCHEMA if is_live_llm_provider(requested) else None,
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
        if completion.content is None:
            return _fallback(
                [
                    {
                        "code": completion.error_code or "LLM_UNAVAILABLE",
                        "message": completion.error_message or "provider returned no JSON",
                    }
                ],
                provenance,
            )
        if not isinstance(completion.content, dict):
            return _fallback(
                [
                    {
                        "code": "LLM_ROOT_TYPE_INVALID",
                        "message": type(completion.content).__name__,
                    }
                ],
                provenance,
            )
        draft = completion.content.get("operating_conclusion")
        if not isinstance(draft, dict):
            return _fallback(
                [
                    {
                        "code": "CONCLUSION_MISSING",
                        "message": f"got {type(draft).__name__}",
                    }
                ],
                provenance,
            )
        # Force catalog question id before assembly when model drifts.
        qid = str(draft.get("next_question_id") or "")
        if qid not in catalog_ids():
            draft = {**draft, "next_question_id": selected["question_id"]}
        assembled = _assemble_from_model(
            draft,
            run_id=run_id,
            deal_context=deal_context,
            operating_profile=operating_profile,
            selected_question=selected,
            provenance=provenance,
            source=SOURCE_LIVE if provenance.get("llm_used") else SOURCE_FALLBACK,
        )
        violations = validate_operating_conclusion(
            assembled, workbench=workbench, selected_question=selected
        )
        if violations:
            return _fallback(violations, provenance)
        return assembled
    except Exception as exc:  # noqa: BLE001 — Slice 4 hard gate
        return _fallback(
            [{"code": "CONCLUSION_PIPELINE_EXCEPTION", "message": type(exc).__name__}],
            {**provenance_base, "provider_status": "FAILED_EXTERNAL", "llm_used": False},
        )
