"""Advisor LLM workbench, Knowledge Cards, and insight-record Validator."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from rangematch.advisor_brief import generate_deterministic_brief
from rangematch.advisor_contract import packet_hash

REPO_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = REPO_ROOT / "test-data" / "advisor" / "knowledge"
WORKBENCH_SCHEMA = "RANGEMATCH_ADVISOR_LLM_WORKBENCH@0.1.0"
TRIAL_CARD_IDS = frozenset(
    {
        "LEGAL_ACCESS_DILIGENCE_001",
        "LIVESTOCK_WATER_DILIGENCE_001",
        "RAP_INTERPRETATION_001",
        "EVIDENCE_STATUS_INTERPRETATION_001",
        "TERRAIN_CATTLE_INTERPRETATION_001",
        "CLIMATE_HAZARD_CATTLE_INTERPRETATION_001",
        "SOIL_ECOLOGY_CATTLE_INTERPRETATION_001",
    }
)
# Primary natural-foundation workbench: LEGAL_ACCESS / title cards excluded.
NATURAL_FOUNDATION_CARD_IDS = frozenset(
    {
        "LIVESTOCK_WATER_DILIGENCE_001",
        "RAP_INTERPRETATION_001",
        "EVIDENCE_STATUS_INTERPRETATION_001",
        "TERRAIN_CATTLE_INTERPRETATION_001",
        "CLIMATE_HAZARD_CATTLE_INTERPRETATION_001",
        "SOIL_ECOLOGY_CATTLE_INTERPRETATION_001",
    }
)
TRIAL_STATUSES = frozenset({"APPROVED", "PROVISIONAL_FOR_CPER_TEST"})
DEFERRED_PRECIP = {
    "action_id": "ACTION_REPEAT_PRECIP",
    "action_type": "DOCUMENT_REQUEST",
    "cost_class": "DESKTOP",
    "role": "DEFERRED_COMPARISON",
    "why_now": "Annual precipitation is already measured; a repeat lookup does not change the current decision.",
    "can_establish": [],
    "cannot_establish": ["whether a weekend visit has a job"],
}

SUITABILITY = re.compile(
    r"\b(suitable|unsuitable|carrying capacity|stocking rate|buy this|worth flying to|lowest cost and highest)\b",
    re.I,
)
LEGAL_VERDICT = re.compile(
    r"\b(has legal access|no legal access|easement is valid|you own a right)\b",
    re.I,
)
KITCHEN_LEAK = re.compile(r"\b(F0[1-8]|HOLD|VAR_F\d|ACTION_[A-Z0-9_]+|geometry_hash)\b", re.I)
WELL_AS_FACT = re.compile(r"\b(this (tract|parcel|ranch) has a well|there is a well)\b", re.I)

CARD_REQUIRED = (
    "knowledge_id",
    "topic",
    "statement",
    "source_id",
    "source_title",
    "source_url_or_citation",
    "source_publisher",
    "source_date",
    "reviewed_by",
    "reviewed_at",
    "review_basis",
    "effective_jurisdictions",
    "review_status",
    "allowed_use",
    "prohibited_use",
    "content_hash",
    "expires_or_review_after",
    "version",
)
INSIGHT_REQUIRED = (
    "insight_id",
    "recommendation",
    "reasoning_type",
    "packet_refs",
    "context_refs",
    "knowledge_refs",
)
REASONING_TYPES = {
    "SUPPORTED_INTERPRETATION",
    "DOMAIN_PRIOR",
    "CONDITIONAL_SCENARIO",
    "DILIGENCE_QUESTION",
    "INFORMATION_VALUE",
}


def _add(violations: list[dict[str, str]], code: str, message: str) -> None:
    violations.append({"code": code, "message": message})


def knowledge_content_hash(card: dict[str, Any]) -> str:
    payload = {
        "knowledge_id": card.get("knowledge_id"),
        "statement": card.get("statement"),
        "version": card.get("version"),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    return f"sha256:{digest}"


def load_approved_knowledge_cards(
    *,
    repo_root: Path | None = None,
    workbench: str = "legacy",
) -> list[dict[str, Any]]:
    """Load Demo-approved Knowledge Cards. Not a national knowledge base.

    workbench:
      - legacy: historical trial set (includes LEGAL_ACCESS for LEGACY Demo)
      - natural_cattle: primary environmental selector; excludes LEGAL_ACCESS_*
    """
    root = (repo_root or REPO_ROOT) / "test-data" / "advisor" / "knowledge"
    allowed = (
        NATURAL_FOUNDATION_CARD_IDS
        if workbench == "natural_cattle"
        else TRIAL_CARD_IDS
    )
    cards = []
    if not root.is_dir():
        return cards
    for path in sorted(root.glob("*.json")):
        card = json.loads(path.read_text(encoding="utf-8"))
        if card.get("knowledge_id") not in allowed:
            continue
        if card.get("review_status") not in TRIAL_STATUSES:
            continue
        if workbench == "natural_cattle":
            topic = str(card.get("topic") or "").lower()
            kid = str(card.get("knowledge_id") or "").upper()
            if topic in {"legal_access", "title", "access"} or kid.startswith(
                "LEGAL_ACCESS"
            ):
                continue
        cards.append(card)
    return cards


def validate_knowledge_card(card: dict[str, Any]) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for key in CARD_REQUIRED:
        if not card.get(key) and card.get(key) != []:
            _add(violations, "KNOWLEDGE_CARD_FIELD_MISSING", f"missing {key}")
    if card.get("review_status") not in TRIAL_STATUSES:
        _add(violations, "KNOWLEDGE_CARD_NOT_USABLE", str(card.get("knowledge_id")))
    expected = knowledge_content_hash(card)
    if card.get("content_hash") != expected:
        _add(violations, "KNOWLEDGE_CARD_HASH_MISMATCH", str(card.get("knowledge_id")))
    if "legal_conclusion" not in (card.get("prohibited_use") or []):
        _add(violations, "KNOWLEDGE_CARD_LEGAL_BAND_MISSING", str(card.get("knowledge_id")))
    if card.get("topic") == "legal_access":
        allowed = set(card.get("allowed_use") or [])
        if allowed - {"diligence_question", "conditional_reasoning"}:
            _add(violations, "LEGAL_CARD_USE_TOO_WIDE", str(card.get("knowledge_id")))
    return violations


def build_cper_action_policy(actions: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(actions, key=lambda row: int(row.get("execution_order") or 0))
    ids = {str(row.get("action_id")) for row in ordered}
    first = [str(ordered[0]["action_id"])] if ordered else []
    deps: dict[str, list[str]] = {}
    if (
        "ACTION_WATER_FIELD_CATEGORY" in ids
        and "ACTION_ACCESS_DOCUMENTS" in ids
        and first == ["ACTION_ACCESS_DOCUMENTS"]
    ):
        deps["ACTION_WATER_FIELD_CATEGORY"] = ["ACTION_ACCESS_DOCUMENTS"]
    return {
        "allowed_first_actions": first,
        "action_dependencies": deps,
        "allowed_permutations": None,
    }


def project_advisor_llm_workbench(
    packet: dict[str, Any],
    *,
    mireye_live: dict[str, Any] | None = None,
    knowledge_cards: list[dict[str, Any]] | None = None,
    report_locale: str = "en-US",
    audience: str = "ORDINARY_BUYER",
    unified_output: dict[str, Any] | None = None,
    operating_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    actions = list(packet.get("actions") or [])
    policy = packet.get("action_policy") or build_cper_action_policy(actions)
    brief = generate_deterministic_brief(packet, unified_output=unified_output)
    visit_purpose = (brief.get("page_one_advisor") or {}).get("visit_purpose")
    cards = knowledge_cards if knowledge_cards is not None else load_approved_knowledge_cards()
    objects = []
    for row in packet.get("candidate_objects") or []:
        geometry = row.get("geometry") or {}
        objects.append(
            {
                "candidate_id": row.get("candidate_id"),
                "candidate_type": row.get("candidate_type"),
                "display_name": row.get("display_name"),
                "review_status": row.get("review_status"),
                "evidence_state": row.get("evidence_state"),
                "field_navigation_precision": geometry.get("field_navigation_precision"),
            }
        )
    observations = []
    for row in packet.get("observations") or []:
        observations.append(
            {
                "observation_id": row.get("observation_id"),
                "label": row.get("label"),
                "value": row.get("value"),
                "unit": row.get("unit"),
                "time_period": row.get("time_period"),
                "evidence_state": row.get("evidence_state"),
                "allowed_support": list(row.get("allowed_support") or []),
                "prohibited_support": list(row.get("prohibited_support") or []),
            }
        )
    candidates = [
        {
            "action_id": row.get("action_id"),
            "execution_order": row.get("execution_order"),
            "action_type": row.get("action_type"),
            "cost_class": row.get("cost_class"),
            "can_establish": list(row.get("can_establish") or []),
            "cannot_establish": list(row.get("cannot_establish") or []),
            "role": "PACKET",
        }
        for row in actions
    ]
    if not any(row.get("action_id") == DEFERRED_PRECIP["action_id"] for row in candidates):
        candidates.append(dict(DEFERRED_PRECIP))
    profile_slice = None
    profile_hash = None
    thesis_inputs: list[str] = []
    if operating_profile:
        from rangematch.livestock_operating_profile import profile_for_llm

        profile_slice = profile_for_llm(operating_profile)
        profile_hash = operating_profile.get("profile_hash")
        thesis_inputs = list(profile_slice.get("operating_thesis_inputs") or [])
    return {
        "schema_version": WORKBENCH_SCHEMA,
        "packet_hash": packet_hash(packet),
        "report_locale": report_locale,
        "audience": audience,
        "visit_purpose": visit_purpose,
        "observations": observations,
        "claim_gaps": list(packet.get("claim_evidence_gaps") or []),
        "candidate_objects": objects,
        "bottleneck_candidates": [
            {
                "bottleneck_id": row.get("bottleneck_id"),
                "bottleneck_rank": row.get("bottleneck_rank"),
                "title": row.get("title"),
                "decision_impact": row.get("decision_impact"),
                "information_gain": row.get("information_gain"),
                "cost_class": row.get("cost_class"),
            }
            for row in (packet.get("bottlenecks") or [])
        ],
        "action_candidates": candidates,
        "action_policy": policy,
        "execution_order": [
            str(row.get("action_id"))
            for row in sorted(actions, key=lambda item: int(item.get("execution_order") or 0))
        ],
        "knowledge_cards": cards,
        "mireye_contexts": _mireye_context_rows(mireye_live),
        "prohibited_inferences": list(packet.get("prohibited_inferences") or []),
        "reading_budget": {
            "recommendation_max_chars": 140,
            "first_screen_sections": [1, 2, 3],
        },
        "operating_profile": profile_slice,
        "operating_profile_hash": profile_hash,
        "operating_thesis_inputs": thesis_inputs,
    }


def _mireye_context_rows(mireye_live: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not mireye_live:
        return []
    rows = []
    lookup = mireye_live.get("lookup") or {}
    rows.append(
        {
            "context_id": "MIREYE_LOOKUP",
            "endpoint": lookup.get("endpoint") or "/v1/lookup",
            "ok": bool(lookup.get("ok")),
            "error_class": lookup.get("error_class"),
            "canonical_for_parcel_facts": False,
        }
    )
    for name, row in (mireye_live.get("contexts") or {}).items():
        rows.append(
            {
                "context_id": f"MIREYE_{name}",
                "endpoint": "/v1/fetch" if "LAND" in name or "HAZARD" in name else "/v1/lookup",
                "ok": (row or {}).get("status") == "SUCCEEDED",
                "error_class": (row or {}).get("error_class"),
                "canonical_for_parcel_facts": False,
            }
        )
    return rows


def compute_depends_on(insight: dict[str, Any]) -> dict[str, Any]:
    action_refs = list(insight.get("considered_actions") or [])
    action_refs.extend(insight.get("llm_recommended_order") or [])
    for row in insight.get("rejected_actions") or []:
        action_refs.append(str(row.get("action_id") or ""))
    for row in insight.get("conditions") or []:
        action_refs.append(str(row.get("if_action_id") or ""))
        action_refs.append(str(row.get("then_action_id") or ""))
    packet_refs = [str(item) for item in (insight.get("packet_refs") or []) if item]
    clean_actions = sorted({item for item in action_refs if item})
    return {
        "packet_refs": packet_refs,
        "action_refs": clean_actions,
        "knowledge_refs": [str(item) for item in (insight.get("knowledge_refs") or []) if item],
        "context_refs": [str(item) for item in (insight.get("context_refs") or []) if item],
    }


def compute_withdraw_when(depends_on: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for ref in depends_on.get("packet_refs") or []:
        rows.append({"ref": ref, "events": ["REMOVED", "FAILED", "DOWNGRADED"]})
    for ref in depends_on.get("action_refs") or []:
        rows.append({"ref": ref, "events": ["REMOVED"]})
    for ref in depends_on.get("knowledge_refs") or []:
        rows.append({"ref": ref, "events": ["REMOVED", "EXPIRED"]})
    for ref in depends_on.get("context_refs") or []:
        rows.append({"ref": ref, "events": ["REMOVED", "FAILED"]})
    return rows


def candidate_action_ids(workbench: dict[str, Any]) -> set[str]:
    return {
        str(row.get("action_id"))
        for row in (workbench.get("action_candidates") or [])
        if row.get("action_id")
    }


def validate_recommended_order(
    order: list[str],
    workbench: dict[str, Any],
) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    policy = workbench.get("action_policy") or {}
    allowed_first = [str(item) for item in (policy.get("allowed_first_actions") or [])]
    deps = policy.get("action_dependencies") or {}
    perms = policy.get("allowed_permutations")
    known = candidate_action_ids(workbench)
    if any(item not in known for item in order):
        _add(violations, "RECOMMENDED_ACTION_UNKNOWN", ",".join(order))
        return violations
    if order and allowed_first and order[0] not in allowed_first:
        _add(violations, "ILLEGAL_FIRST_ACTION", order[0])
    seen: set[str] = set()
    for item in order:
        for prerequisite in deps.get(item) or []:
            if prerequisite not in seen:
                _add(violations, "ACTION_DEPENDENCY_VIOLATION", f"{item} before {prerequisite}")
        seen.add(item)
    if perms:
        legal = {tuple(row) for row in perms}
        if tuple(order) not in legal:
            _add(violations, "ORDER_NOT_IN_ALLOWED_PERMUTATIONS", ",".join(order))
    return violations


def _workbench_packet_ids(workbench: dict[str, Any]) -> set[str]:
    ids = {str(row.get("observation_id")) for row in (workbench.get("observations") or [])}
    ids.update(str(row.get("bottleneck_id")) for row in (workbench.get("bottleneck_candidates") or []))
    ids.update(str(row.get("claim_id")) for row in (workbench.get("claim_gaps") or []))
    ids.update(str(row.get("candidate_id")) for row in (workbench.get("candidate_objects") or []))
    ids.discard("None")
    ids.discard("")
    return ids


def validate_insight_record(
    insight: dict[str, Any],
    workbench: dict[str, Any],
    *,
    withdrawn_refs: set[str] | None = None,
) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for key in INSIGHT_REQUIRED:
        if key not in insight:
            _add(violations, "INSIGHT_FIELD_MISSING", key)
    if insight.get("reasoning_type") not in REASONING_TYPES:
        _add(violations, "INSIGHT_REASONING_TYPE", str(insight.get("reasoning_type")))
    rec = str(insight.get("recommendation") or "")
    if len(rec) > 140:
        _add(violations, "RECOMMENDATION_TOO_LONG", rec)
    if SUITABILITY.search(rec) or LEGAL_VERDICT.search(rec) or WELL_AS_FACT.search(rec):
        _add(violations, "INSIGHT_PROHIBITED_INFERENCE", rec)
    if KITCHEN_LEAK.search(rec):
        _add(violations, "INSIGHT_KITCHEN_LEAK", rec)
    if "withdrawal_rule" in insight:
        _add(violations, "INSIGHT_AUTHORED_WITHDRAWAL_RULE", "model must not author withdrawal_rule")

    packet_ids = _workbench_packet_ids(workbench)
    card_ids = {str(row.get("knowledge_id")) for row in (workbench.get("knowledge_cards") or [])}
    context_ids = {str(row.get("context_id")) for row in (workbench.get("mireye_contexts") or [])}
    known_actions = candidate_action_ids(workbench)

    for ref in insight.get("packet_refs") or []:
        if ref not in packet_ids:
            _add(violations, "INSIGHT_PACKET_REF_UNKNOWN", str(ref))
    for ref in insight.get("knowledge_refs") or []:
        if ref not in card_ids:
            _add(violations, "INSIGHT_KNOWLEDGE_REF_UNKNOWN", str(ref))
    for ref in insight.get("context_refs") or []:
        if ref not in context_ids:
            _add(violations, "INSIGHT_CONTEXT_REF_UNKNOWN", str(ref))

    reasoning = insight.get("reasoning_type")
    if reasoning != "DOMAIN_PRIOR" and not (insight.get("packet_refs") or insight.get("context_refs")):
        _add(violations, "INSIGHT_UNGROUNDED", str(insight.get("insight_id")))
    if reasoning == "SUPPORTED_INTERPRETATION" and not insight.get("packet_refs"):
        _add(violations, "INTERPRETATION_NEEDS_PACKET_REF", str(insight.get("insight_id")))
    if insight.get("context_refs") and not insight.get("packet_refs"):
        if reasoning == "SUPPORTED_INTERPRETATION":
            _add(violations, "MIREYE_AS_PARCEL_FACT", str(insight.get("insight_id")))

    considered = [str(item) for item in (insight.get("considered_actions") or [])]
    rejected = [str(row.get("action_id") or "") for row in (insight.get("rejected_actions") or [])]
    for action_id in (*considered, *rejected, *(insight.get("llm_recommended_order") or [])):
        if action_id and action_id not in known_actions:
            _add(violations, "INSIGHT_ACTION_NOT_CANDIDATE", action_id)

    packet_action_count = sum(
        1
        for row in (workbench.get("action_candidates") or [])
        if row.get("role") == "PACKET"
    )
    if reasoning == "INFORMATION_VALUE":
        if packet_action_count + 1 >= 2 and not considered:
            _add(violations, "INFORMATION_VALUE_NEEDS_CONSIDERED", str(insight.get("insight_id")))
        comparable = packet_action_count + int(
            any(row.get("action_id") == DEFERRED_PRECIP["action_id"] for row in (workbench.get("action_candidates") or []))
        )
        if comparable >= 2 and not rejected:
            _add(violations, "INFORMATION_VALUE_NEEDS_REJECTED", str(insight.get("insight_id")))
        if "lowest cost" in rec.lower() and "highest" in rec.lower():
            _add(violations, "INVENTED_INFORMATION_VALUE_RANK", rec)

    if insight.get("llm_recommended_order"):
        violations.extend(
            validate_recommended_order(list(insight["llm_recommended_order"]), workbench)
        )
        if insight["llm_recommended_order"] == workbench.get("execution_order"):
            pass
        if set(insight["llm_recommended_order"]) == set(workbench.get("execution_order") or []) and insight[
            "llm_recommended_order"
        ] != list(workbench.get("execution_order") or []):
            # allowed when rails pass; keep both
            pass

    withdrawn = withdrawn_refs or set()
    depends = compute_depends_on(insight)
    for ref in (
        *(depends.get("packet_refs") or []),
        *(depends.get("action_refs") or []),
        *(depends.get("knowledge_refs") or []),
        *(depends.get("context_refs") or []),
    ):
        if ref in withdrawn:
            _add(violations, "INSIGHT_NOT_WITHDRAWN", f"{insight.get('insight_id')} still cites {ref}")

    for card_id in insight.get("knowledge_refs") or []:
        card = next(
            (row for row in (workbench.get("knowledge_cards") or []) if row.get("knowledge_id") == card_id),
            None,
        )
        if card and "parcel_fact" in (card.get("prohibited_use") or []) and reasoning == "SUPPORTED_INTERPRETATION":
            if not insight.get("packet_refs"):
                _add(violations, "KNOWLEDGE_AS_PARCEL_FACT", str(card_id))
    return violations


def validate_insight_bundle(
    insights: list[dict[str, Any]],
    workbench: dict[str, Any],
    *,
    withdrawn_refs: set[str] | None = None,
) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for card in workbench.get("knowledge_cards") or []:
        violations.extend(validate_knowledge_card(card))
    for insight in insights:
        violations.extend(
            validate_insight_record(insight, workbench, withdrawn_refs=withdrawn_refs)
        )
    return violations
