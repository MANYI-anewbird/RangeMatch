"""Evidence-bound Advisor Narrative: the LLM owns the argument, not the facts."""

from __future__ import annotations

import re
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from rangematch.advisor_insight import candidate_action_ids, validate_recommended_order

NARRATIVE_SCHEMA = "RANGEMATCH_ADVISOR_NARRATIVE@0.1.0"
INTERNAL_ID = re.compile(r"\b(?:ACTION|OBS|BOTTLENECK|CLAIM|VAR_F|INSIGHT)_[A-Z0-9_]+\b")
PROHIBITED = re.compile(
    r"\b(?:suitable|unsuitable|stocking rate|carrying capacity|buy this|do not buy|"
    r"has legal access|no legal access|year-round water is verified|ranch(?:'s)? viability|"
    r"operations? can commence|operations? commence|livestock acquisition|alternative properties|"
    r"water rights?|legal disputes?|operational failure|overstocking|land degradation|"
    r"high risk|medium risk|low risk|positive aspect|positive factor|promising|"
    r"favorable for various uses|significant landholding|operational potential|"
    r"operational planning|lawful basis|lawful entrance)\b",
    re.I,
)

ADVISOR_NARRATIVE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version", "thesis", "executive_memo", "evidence_chain",
        "action_pivot", "conditional_path", "client_summary", "professional_boundary",
    ],
    "properties": {
        "schema_version": {"type": "string", "const": NARRATIVE_SCHEMA},
        "thesis": {"type": "string", "minLength": 20, "maxLength": 320},
        "executive_memo": {"type": "string", "minLength": 180, "maxLength": 2200},
        "evidence_chain": {
            "type": "array", "minItems": 2, "maxItems": 4,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["point", "evidence_refs", "context_refs", "knowledge_refs", "interpretation", "decision_effect"],
                "properties": {
                    "point": {"type": "string", "minLength": 8, "maxLength": 240},
                    "evidence_refs": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                    "context_refs": {"type": "array", "items": {"type": "string"}},
                    "knowledge_refs": {"type": "array", "items": {"type": "string"}},
                    "interpretation": {"type": "string", "minLength": 40, "maxLength": 900},
                    "decision_effect": {"type": "string", "minLength": 20, "maxLength": 600},
                },
            },
        },
        "action_pivot": {
            "type": "object", "additionalProperties": False,
            "required": ["largest_gap", "first_action_id", "first_action_reason", "deferred_action_ids", "deferred_reason"],
            "properties": {
                "largest_gap": {"type": "string", "minLength": 15, "maxLength": 500},
                "first_action_id": {"type": "string"},
                "first_action_reason": {"type": "string", "minLength": 30, "maxLength": 500},
                "deferred_action_ids": {"type": "array", "items": {"type": "string"}},
                "deferred_reason": {"type": "string", "minLength": 20, "maxLength": 400},
            },
        },
        "conditional_path": {
            "type": "object", "additionalProperties": False,
            "required": ["if_favorable", "if_unfavorable", "still_unknown"],
            "properties": {
                "if_favorable": {"type": "string", "minLength": 30, "maxLength": 500},
                "if_unfavorable": {"type": "string", "minLength": 30, "maxLength": 500},
                "still_unknown": {"type": "string", "minLength": 20, "maxLength": 400},
            },
        },
        "client_summary": {"type": "string", "minLength": 60, "maxLength": 700},
        "professional_boundary": {"type": "string", "minLength": 30, "maxLength": 500},
    },
}

ADVISOR_NARRATIVE_BUNDLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["narrative"],
    "properties": {"narrative": ADVISOR_NARRATIVE_OUTPUT_SCHEMA},
}


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def validate_advisor_narrative(narrative: Mapping[str, Any] | Any, workbench: Mapping[str, Any]) -> list[dict[str, str]]:
    """Type → JSON Schema → semantic. Never raises on malformed model objects."""
    violations: list[dict[str, str]] = []
    if not isinstance(narrative, Mapping):
        return [
            {
                "code": "NARRATIVE_TYPE_INVALID",
                "message": f"narrative must be object, got {type(narrative).__name__}",
            }
        ]
    for field in ("action_pivot", "conditional_path"):
        value = narrative.get(field)
        if value is not None and not isinstance(value, Mapping):
            violations.append(
                {
                    "code": "NARRATIVE_TYPE_INVALID",
                    "message": f"{field} must be object, got {type(value).__name__}",
                }
            )
    for err in sorted(
        Draft202012Validator(ADVISOR_NARRATIVE_OUTPUT_SCHEMA).iter_errors(dict(narrative)),
        key=lambda item: list(item.absolute_path),
    ):
        path = ".".join(str(part) for part in err.absolute_path) or "$"
        violations.append({"code": "NARRATIVE_SCHEMA_INVALID", "message": f"{path}: {err.message}"})
    if violations:
        return violations
    packet_ids = {
        str(row.get("observation_id")) for row in workbench.get("observations") or []
    } | {
        str(row.get("bottleneck_id")) for row in workbench.get("bottleneck_candidates") or []
    } | {
        str(row.get("claim_id")) for row in workbench.get("claim_gaps") or []
    } | {
        str(row.get("candidate_id")) for row in workbench.get("candidate_objects") or []
    }
    context_ids = {str(row.get("context_id")) for row in workbench.get("mireye_contexts") or []}
    knowledge_ids = {str(row.get("knowledge_id")) for row in workbench.get("knowledge_cards") or []}
    for index, row in enumerate(narrative.get("evidence_chain") or []):
        if not isinstance(row, Mapping):
            violations.append({"code": "NARRATIVE_TYPE_INVALID", "message": f"evidence_chain[{index}]"})
            continue
        refs = [str(ref) for ref in row.get("evidence_refs") or []]
        if not refs:
            violations.append({"code": "NARRATIVE_POINT_UNGROUNDED", "message": str(index)})
        for ref in refs:
            if ref not in packet_ids:
                violations.append({"code": "NARRATIVE_PACKET_REF_UNKNOWN", "message": ref})
        for ref in row.get("context_refs") or []:
            if ref not in context_ids:
                violations.append({"code": "NARRATIVE_CONTEXT_REF_UNKNOWN", "message": str(ref)})
        for ref in row.get("knowledge_refs") or []:
            if ref not in knowledge_ids:
                violations.append({"code": "NARRATIVE_KNOWLEDGE_REF_UNKNOWN", "message": str(ref)})
    pivot = _as_mapping(narrative.get("action_pivot"))
    path_obj = _as_mapping(narrative.get("conditional_path"))
    first = str(pivot.get("first_action_id") or "")
    deferred = [str(item) for item in pivot.get("deferred_action_ids") or []]
    known_actions = candidate_action_ids(dict(workbench))
    for action in [first, *deferred]:
        if action and action not in known_actions:
            violations.append({"code": "NARRATIVE_ACTION_UNKNOWN", "message": action})
    if first:
        violations.extend(validate_recommended_order([first], dict(workbench)))
    chain_refs = {
        str(ref)
        for row in narrative.get("evidence_chain") or []
        if isinstance(row, Mapping)
        for ref in row.get("evidence_refs") or []
    }
    available_observations = {str(row.get("observation_id")) for row in workbench.get("observations") or []}
    for ref in ("OBS_ROAD", "OBS_WATER_COUNT"):
        if ref in available_observations and ref not in chain_refs:
            violations.append({"code": "NARRATIVE_DECISION_ANCHOR_MISSING", "message": ref})
    first_reason = str(pivot.get("first_action_reason") or "").lower()
    if first == "ACTION_ACCESS_DOCUMENTS":
        if "access" not in first_reason and "entrance" not in first_reason:
            violations.append({"code": "NARRATIVE_FIRST_ACTION_CAUSAL_GAP", "message": "access-document reason must concern access"})
        if re.search(
            r"(?:confirm|establish|prove|clarif)(?:y|ies|ied|ying)?\s+(?:usable\s+)?(?:water|source)|"
            r"(?:water|source)(?:\s+availability)?\s+(?:is\s+)?(?:confirmed|established|proven|clarified)",
            first_reason,
        ):
            violations.append({"code": "NARRATIVE_FIRST_ACTION_OVERCLAIM", "message": "access documents do not establish water"})
    prose_parts = [
        narrative.get("thesis"), narrative.get("executive_memo"), narrative.get("client_summary"),
        narrative.get("professional_boundary"), pivot.get("largest_gap"), pivot.get("first_action_reason"),
        pivot.get("deferred_reason"), *path_obj.values(),
    ]
    for row in narrative.get("evidence_chain") or []:
        if not isinstance(row, Mapping):
            continue
        prose_parts.extend([row.get("point"), row.get("interpretation"), row.get("decision_effect")])
    prose = " ".join(str(item or "") for item in prose_parts)
    leaked = INTERNAL_ID.search(prose)
    if leaked:
        violations.append({"code": "NARRATIVE_INTERNAL_ID", "message": leaked.group(0)})
    protected_concepts = (
        r"(?:stocking rate|carrying capacity|suitability|water rights?|legal access|"
        r"usable livestock water|purchase recommendation|legal conclusion)"
    )
    prose_for_prohibited = re.sub(
        rf"\b(?:not|is not|isn't)\s+(?:a\s+|an\s+)?{protected_concepts}",
        "",
        prose,
        flags=re.I,
    )
    prose_for_prohibited = re.sub(
        rf"\b(?:does not|doesn't|cannot|can't)\s+(?:establish|confirm|prove|show|determine)\s+"
        rf"(?:a\s+|an\s+)?{protected_concepts}",
        "",
        prose_for_prohibited,
        flags=re.I,
    )
    prose_for_prohibited = re.sub(
        rf"\b(?:not|is not|isn't)\s+(?:proof|evidence|confirmation|a conclusion)\s+"
        rf"(?:of|about|for)\s+(?:a\s+|an\s+)?{protected_concepts}",
        "",
        prose_for_prohibited,
        flags=re.I,
    )
    forbidden = PROHIBITED.search(prose_for_prohibited)
    if forbidden:
        violations.append({"code": "NARRATIVE_PROHIBITED_CONCLUSION", "message": forbidden.group(0)})
    for item in prose_parts:
        if str(item or "").rstrip().endswith(("'", '"')):
            violations.append({"code": "NARRATIVE_BROKEN_PROSE", "message": str(item)})
            break
    sentence_parts = [
        narrative.get("thesis"), narrative.get("executive_memo"), narrative.get("client_summary"),
        narrative.get("professional_boundary"), pivot.get("largest_gap"), pivot.get("first_action_reason"),
        pivot.get("deferred_reason"), *path_obj.values(),
    ]
    for row in narrative.get("evidence_chain") or []:
        if not isinstance(row, Mapping):
            continue
        sentence_parts.extend([row.get("point"), row.get("interpretation"), row.get("decision_effect")])
    for item in sentence_parts:
        value = str(item or "").rstrip()
        if value and value[-1] not in ".?!":
            violations.append({"code": "NARRATIVE_INCOMPLETE_SENTENCE", "message": value[-80:]})
            break
    favorable = str(path_obj.get("if_favorable") or "").lower()
    if first == "ACTION_ACCESS_DOCUMENTS" and re.search(
        r"(?:confirm|establish|prove)(?:ed|es|s|ing)?\s+(?:usable\s+)?water|"
        r"water(?:\s+source|\s+availability)?\s+(?:is\s+)?(?:confirmed|established|proven)",
        favorable,
    ):
        violations.append({"code": "NARRATIVE_CONDITIONAL_OVERCLAIM", "message": "access result cannot establish water"})
    buyer_facing_fields = {
        "executive_memo": narrative.get("executive_memo"),
        "client_summary": narrative.get("client_summary"),
        "first_action_reason": pivot.get("first_action_reason"),
        "deferred_reason": pivot.get("deferred_reason"),
        "if_favorable": path_obj.get("if_favorable"),
        "if_unfavorable": path_obj.get("if_unfavorable"),
    }
    defensive_language = re.compile(
        r"\b(?:unknown|unproven|uncertain(?:ty)?|not confirmation|does not establish|"
        r"cannot proceed|cannot be justified|remains unresolved|lack of)\b",
        re.I,
    )
    for field, value in buyer_facing_fields.items():
        match = defensive_language.search(str(value or ""))
        if match:
            violations.append(
                {"code": "NARRATIVE_NOT_ADVISOR_VOICE", "message": f"{field}: {match.group(0)}"}
            )
    scope_terms = ("next diligence", "before travel", "before the trip", "document", "field review", "site visit")
    if not any(term in prose.lower() for term in scope_terms):
        violations.append(
            {"code": "NARRATIVE_DILIGENCE_SCOPE_MISSING", "message": "narrative must remain about the next diligence decision"}
        )
    if not (narrative.get("evidence_chain") or []):
        violations.append({"code": "NARRATIVE_CHAIN_MISSING", "message": "evidence_chain"})
    return violations
