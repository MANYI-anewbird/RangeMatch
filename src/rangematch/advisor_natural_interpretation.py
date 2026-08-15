"""Phase 6: Natural Cattle Profile → advisor interpretation (LLM + fallback).

LLM narrates directional cattle meaning. It cannot author facts, status,
controlling factor, tools, access/infrastructure, or stocking claims.
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
    NATURAL_QUESTION_IDS,
    natural_catalog_ids,
    question_public,
    select_natural_environment_question,
)
from rangematch.advisor_schema import _load_schema
from rangematch.llm_provider import get_provider, is_live_llm_provider
from rangematch.natural_cattle_profile import BUYER_LABELS

SCHEMA_VERSION = "advisor_natural_foundation_interpretation@1.1.0"
PROMPT_VERSION = "RANGEMATCH_NATURAL_FOUNDATION_INTERPRETATION@1.5.0"
SOURCE_LIVE = "LIVE_LLM"
SOURCE_FALLBACK = "DETERMINISTIC_FALLBACK"

PROHIBITED = re.compile(
    r"(?:stocking rate|carrying capacity|herd size|AUM\b|buy this|do not buy|"
    r"has legal access|no legal access|easement|"
    r"water right|appraisal|purchase advice|"
    r"(?:has|with|proven|confirmed|already)\s+(?:no\s+)?water\s+on\s+the\s+parcel|"
    r"parcel\s+has\s+no\s+water|"
    r"\b(?:fences?|gates?|corrals?|barns?|road access|deeded access)\b)",
    re.I,
)

# These phrases usually announce generic filler rather than a parcel-specific
# insight. They are removed sentence-by-sentence before schema validation. The
# filter intentionally stays narrow: it never rewrites evidence or inference.
AI_SLOP_SENTENCE = re.compile(
    r"(?i)^\s*(?:"
    r"it is (?:important|worth) to (?:note|mention)|"
    r"it should be noted|"
    r"as (?:an|a) ai(?: language model)?|"
    r"based on the (?:information|data) (?:provided|available),?\s*$|"
    r"overall,? this (?:provides|represents|serves as) (?:a )?(?:useful )?(?:starting point|foundation)|"
    r"further (?:analysis|investigation|assessment) (?:is|will be) (?:needed|required)\.?\s*$"
    r")"
)

# These are not forbidden topics; they are conclusions that require evidence
# RangeMatch does not currently collect. Remove only the affected sentence so
# the LLM keeps its grounded narrative instead of falling back wholesale.
UNSUPPORTED_PROFESSIONAL_SENTENCE = re.compile(
    r"(?i)(?:"
    r"\bhoof health\b|"
    r"\b(?:best|optimal|highest-quality)\s+(?:grazing|forage)\s+(?:season|window)\b|"
    r"\bspring\s*[-–]\s*(?:early\s+)?summer\s+(?:grazing|forage)\s+window\b|"
    r"\b(?:would|will)\s+require\s+(?:substantial\s+)?water development\b|"
    r"\b(?:would|will|likely)\s+(?:need|require|plan for)\s+supplemental feed\b|"
    r"\bconfirm(?:s|ed|ing)?\s+(?:the\s+)?(?:land(?:'s)?\s+)?grazing capacity\b"
    r")"
)

# Point samples and nearby context may show that a water feature was not seen
# at one location. They cannot establish parcel-wide absence. The positive
# parcel-wide statement remains available when a true parcel observation exists.
PARCEL_WATER_ABSENCE_SENTENCE = re.compile(
    r"(?i)(?:"
    r"\b(?:no|without)\s+mapped\s+(?:surface\s+)?water\s+on\s+(?:the\s+)?parcel\b|"
    r"\b(?:the\s+)?parcel\s+(?:itself\s+)?(?:has|shows|contains)\s+no\s+mapped\s+(?:surface\s+)?water\b|"
    r"\b(?:the\s+)?parcel\s+lacks\s+mapped\s+(?:surface\s+)?water\b"
    r")"
)

NARRATIVE_LIMITS = {
    "land_character": 1000,
    "advisor_judgment": 700,
    "advisor_view": 600,
    "integrated_natural_reading": 2000,
    "intended_use_interpretation": 1200,
    "refinement_request": 400,
    "optional_copy_ready_request": 600,
}

LIST_LIMITS = {
    "operating_possibilities": (4, 260),
    "conditional_scenarios": (3, 300),
    "what_would_change_the_view": (3, 300),
}

LLM_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "land_character",
        "advisor_judgment",
        "operating_possibilities",
        "conditional_scenarios",
        "advisor_view",
        "integrated_natural_reading",
        "intended_use_interpretation",
        "what_would_change_the_view",
        "refinement_request",
        "optional_copy_ready_request",
        "cited_profile_refs",
        "knowledge_refs",
        "next_question_id",
    ],
    "properties": {
        "land_character": {"type": "string", "minLength": 40, "maxLength": 1000},
        "advisor_judgment": {"type": "string", "minLength": 30, "maxLength": 700},
        "operating_possibilities": {
            "type": "array",
            "minItems": 1,
            "maxItems": 4,
            "items": {"type": "string", "minLength": 12, "maxLength": 260},
        },
        "conditional_scenarios": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {"type": "string", "minLength": 12, "maxLength": 300},
        },
        "advisor_view": {"type": "string", "minLength": 20, "maxLength": 600},
        "integrated_natural_reading": {
            "type": "string",
            "minLength": 40,
            "maxLength": 2000,
        },
        "intended_use_interpretation": {
            "type": "string",
            "minLength": 20,
            "maxLength": 1200,
        },
        "what_would_change_the_view": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 8},
        },
        "refinement_request": {"type": "string", "minLength": 12, "maxLength": 400},
        "optional_copy_ready_request": {"type": ["string", "null"], "maxLength": 600},
        "cited_profile_refs": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string"},
        },
        "knowledge_refs": {"type": "array", "items": {"type": "string"}},
        "next_question_id": {"type": "string"},
    },
}

SYSTEM_PROMPT = """You are a senior buyer-side cattle natural-environment advisor for RangeMatch.
Return one JSON object: {"natural_foundation_interpretation": {...}} with only:
land_character, advisor_judgment, operating_possibilities, conditional_scenarios,
advisor_view, integrated_natural_reading, intended_use_interpretation,
what_would_change_the_view, refinement_request, optional_copy_ready_request,
cited_profile_refs, knowledge_refs, next_question_id.

You receive a deterministic Natural Cattle Profile, approved knowledge cards,
and Deal Context. Use them to form an insightful, directional interpretation of
THIS land for cattle. The buyer wants to understand what kind of natural place
this is, what the observed conditions make plausible, and what condition would
change that view. Write like an experienced advisor speaking to a buyer, not an
auditor describing data collection.

Narrative priorities:
1. land_character: synthesize the observed terrain, vegetation, water, climate,
   and soil into a recognizable physical portrait of the land.
2. advisor_judgment: give a directional, provisional judgment about the natural
   foundation for the intended cattle use. Lead with insight, not uncertainty.
3. operating_possibilities: develop 2-3 distinct, useful possibilities when the
   evidence supports them. Each item should combine at least two natural domains
   (for example terrain + forage, or water + climate), explain WHY that use pattern
   is plausible on this parcel, and identify the operating condition that keeps it
   plausible. Do not merely rename a cattle system or repeat advisor_judgment.
4. intended_use_interpretation: make this a compact scenario analysis, not a label.
   Explain how the user's stated or still-unknown cattle use changes the importance
   of water timing, seasonal forage, drought exposure, terrain distribution, and
   parcel scale. When use is unknown, compare the evidence burden for seasonal
   grazing with year-round cow-calf use and state which direction the current land
   picture more naturally supports. Aim for 80-140 words without inventing herd size.
5. conditional_scenarios: write decision pivots, not a missing-data list. Produce
   two concise scenarios when evidence allows: one condition that would materially
   strengthen the current view and one that would materially weaken it. Every item
   must follow this logic: "If [specific real-world condition is confirmed], then
   [how the current judgment changes], because [cattle-land implication]." Tie each
   scenario to the current controlling factor and intended use. Do not say only
   that more evidence or further investigation is needed, and do not repeat the
   refinement_request.
5. Put limitations and the one highest-value refinement request at the end.

Spatial and professional interpretation rules:
- POINT means one sampled location; CONTEXT means nearby. Neither can establish
  that the entire parcel has or lacks a condition.
- A parcel-wide mapped wetland footprint is environmental context, not proof of
  usable livestock water. Describe it as a mapped footprint whose persistence,
  accessibility, and cattle value are not established.
- Keep the Profile controlling factor authoritative. Other domains may be
  interacting risks, but do not rename one as the "main limiting factor."
- Do not infer hoof health, a best grazing season, required water development,
  supplemental-feed need, or grazing capacity from the current evidence.

Hard rules:
- Do not change status, confidence, controlling factor, evidence values, or hashes.
- Cite only cited_profile_refs and knowledge_refs present in the workbench.
- next_question_id must be exactly one id from allowed_question_ids.
- Do not select or invent tools, adapters, or data calls.
- Do not introduce roads, access, fences, title, or infrastructure into the primary narrative.
- Do not invent water sources, vegetation condition, forage availability, or stocking rates.
- Do not turn missing or SOURCE_UNAVAILABLE evidence into a negative land condition.
- Do not give legal, purchase, appraisal, or water-right conclusions.
- Omit those prohibited topics entirely; do not repeat them as disclaimers such as
  "not a stocking-rate opinion" or "does not establish legal access."
- Treat the Profile controlling factor as the highest-priority evidence question,
  not automatically as a negative land condition. A source conflict is not itself
  a terrain, water, forage, climate, or soil defect.
- You may make professional, directional inferences and describe plausible operating
  scenarios when grounded in cited Profile evidence and reviewed knowledge.
- Every paragraph must earn its place: state a parcel-specific insight, explain its
  cattle meaning, describe a supported possibility, or request one decision-changing
  input. Delete generic transitions, methodology narration, repeated caveats, and
  phrases such as "it is important to note" or "further investigation is needed."
- Prefer concrete subject-verb sentences. Mention the evidence only when it helps the
  buyer understand the land; do not narrate the search process or congratulate the data.
- Keep each sentence under 38 words when practical. Do not repeat the same conclusion
  in land_character, advisor_judgment, and advisor_view.
- Do not open advisor_judgment or land_character with what is missing, unavailable,
  insufficient, unknown, or impossible to assess.
- When operation_type is known, interpret how that intended use changes the reading.
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _profile_ref_ids(profile: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    overall = profile.get("overall_natural_foundation") or {}
    for ref in overall.get("supporting_refs") or []:
        ids.add(str(ref))
    for row in profile.get("domains") or []:
        if not isinstance(row, Mapping):
            continue
        for ref in row.get("supporting_refs") or []:
            ids.add(str(ref))
        ids.add(f"DOMAIN::{row.get('domain')}")
    ids.add("PROFILE")
    ids.add(f"STATUS::{overall.get('status')}")
    controlling = overall.get("controlling_factor") or {}
    if controlling.get("domain"):
        ids.add(f"CONTROLLING::{controlling.get('domain')}")
    return ids


def build_natural_interpretation_workbench(
    *,
    natural_cattle_profile: Mapping[str, Any],
    deal_context: Mapping[str, Any],
    knowledge_cards: list[dict[str, Any]] | None = None,
    previous_interpretation: Mapping[str, Any] | None = None,
    combined_environmental_evidence_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cards = (
        knowledge_cards
        if knowledge_cards is not None
        else load_approved_knowledge_cards(workbench="natural_cattle")
    )
    selected = select_natural_environment_question(
        deal_context=deal_context,
        natural_cattle_profile=natural_cattle_profile,
    )
    overall = natural_cattle_profile.get("overall_natural_foundation") or {}
    controlling = overall.get("controlling_factor") or {}
    domains = []
    for row in natural_cattle_profile.get("domains") or []:
        if not isinstance(row, Mapping):
            continue
        domains.append(
            {
                "domain": row.get("domain"),
                "buyer_label": row.get("buyer_label"),
                "reading": row.get("reading"),
                "confidence": row.get("confidence"),
                "supporting_refs": list(row.get("supporting_refs") or []),
                "limitations": list(row.get("limitations") or [])[:4],
                "conflict_refs": list(row.get("conflict_refs") or []),
            }
        )
    workbench = {
        "run_id": deal_context.get("run_id"),
        "deal_context_version": int(deal_context.get("context_version") or 1),
        "geometry_hash": deal_context.get("geometry_hash"),
        "species": deal_context.get("species") or "CATTLE",
        "operation_type": deal_context.get("operation_type") or "UNKNOWN",
        "user_answers": [
            {
                "field": row.get("field"),
                "value": row.get("value"),
                "provenance": row.get("provenance"),
            }
            for row in (deal_context.get("user_answers") or [])
            if isinstance(row, Mapping)
        ],
        "natural_cattle_profile": {
            "profile_hash": natural_cattle_profile.get("profile_hash"),
            "status": overall.get("status"),
            "headline": overall.get("headline"),
            "judgment": overall.get("judgment"),
            "confidence": overall.get("confidence"),
            "controlling_factor": {
                "domain": controlling.get("domain"),
                "reason": controlling.get("reason"),
                "resolved": controlling.get("resolved"),
            },
            "evidence_needed": list(overall.get("evidence_needed") or []),
            "limitations": list(overall.get("limitations") or []),
            "domains": domains,
        },
        "allowed_profile_refs": sorted(_profile_ref_ids(natural_cattle_profile)),
        "knowledge_cards": [
            {
                "knowledge_id": row.get("knowledge_id"),
                "topic": row.get("topic"),
                "statement": row.get("statement"),
                "allowed_use": row.get("allowed_use"),
                "prohibited_use": row.get("prohibited_use"),
            }
            for row in cards
            if not str(row.get("knowledge_id") or "").upper().startswith("LEGAL_ACCESS")
        ],
        "allowed_question_ids": sorted(natural_catalog_ids()),
        "selected_question_hint": question_public(selected),
        "selected_question_change_view": selected.get("change_view_text"),
        "locked_facts": {
            "status_is_authoritative_from_profile": True,
            "controlling_factor_is_authoritative_from_profile": True,
            "llm_may_not_change_physical_evidence": True,
            "human_access_infra_excluded_from_primary_narrative": True,
        },
    }
    allowed_refs = _profile_ref_ids(natural_cattle_profile)
    evidence_snapshot: list[dict[str, Any]] = []
    if isinstance(combined_environmental_evidence_packet, Mapping):
        for bucket in ("mireye_observations", "core_observations", "supplement_observations"):
            for observation in combined_environmental_evidence_packet.get(bucket) or []:
                if not isinstance(observation, Mapping):
                    continue
                observation_id = str(observation.get("observation_id") or "")
                if observation_id not in allowed_refs:
                    continue
                if observation.get("status") not in {"RETRIEVED", "PARTIAL"}:
                    continue
                if observation.get("value") is None:
                    continue
                evidence_snapshot.append(
                    {
                        "profile_ref": observation_id,
                        "domain": observation.get("domain"),
                        "field_id": observation.get("field_id"),
                        "value": observation.get("value"),
                        "unit": observation.get("unit"),
                        "spatial_semantics": observation.get("spatial_semantics"),
                        "provider": observation.get("provider"),
                        "source_name": observation.get("source_name"),
                    }
                )
    workbench["physical_evidence_snapshot"] = evidence_snapshot
    if previous_interpretation:
        workbench["previous_interpretation"] = {
            "interpretation_id": previous_interpretation.get("interpretation_id"),
            "advisor_view": previous_interpretation.get("advisor_view"),
            "integrated_natural_reading": previous_interpretation.get(
                "integrated_natural_reading"
            ),
            "intended_use_interpretation": previous_interpretation.get(
                "intended_use_interpretation"
            ),
        }
        workbench["revision_mode"] = True
    return workbench


def render_deterministic_natural_interpretation(
    *,
    natural_cattle_profile: Mapping[str, Any],
    deal_context: Mapping[str, Any],
    knowledge_cards: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Deterministic narrative fallback — never invents facts or access claims."""
    cards = (
        knowledge_cards
        if knowledge_cards is not None
        else load_approved_knowledge_cards(workbench="natural_cattle")
    )
    overall = natural_cattle_profile.get("overall_natural_foundation") or {}
    controlling = overall.get("controlling_factor") or {}
    status = str(overall.get("status") or "INSUFFICIENT_ENVIRONMENTAL_EVIDENCE")
    op = str(deal_context.get("operation_type") or "UNKNOWN").upper()
    ctrl_domain = controlling.get("domain")
    ctrl_label = BUYER_LABELS.get(str(ctrl_domain), "unresolved environmental factor")
    domain_bits = []
    cited: list[str] = []
    for row in natural_cattle_profile.get("domains") or []:
        if not isinstance(row, Mapping):
            continue
        label = row.get("buyer_label") or row.get("domain")
        conf = row.get("confidence")
        domain_bits.append(f"{label} looks {str(conf).lower()} from the Profile")
        for ref in row.get("supporting_refs") or []:
            cited.append(str(ref))
        cited.append(f"DOMAIN::{row.get('domain')}")
    if not cited:
        cited = ["PROFILE", f"STATUS::{status}"]

    advisor_view = str(overall.get("headline") or "Directional natural-foundation view")
    if len(advisor_view) < 20:
        advisor_view = f"Directional cattle natural-foundation view: {status}."

    integrated = (
        f"{overall.get('judgment') or 'The Profile supplies a directional natural foundation.'} "
        f"Controlling factor from the Profile: {ctrl_label}. "
        f"Reading Terrain, Forage, Water, Climate, and Soil together: "
        + "; ".join(domain_bits[:5])
        + ". "
        "This is an interpretation of sourced environmental evidence, not a stocking, "
        "legal-access, or purchase conclusion."
    )
    if op in {"SEASONAL_GRAZING", "YEAR_ROUND_COW_CALF"}:
        intended = (
            f"Intended use is framed as {op.replace('_', ' ').lower()}. "
            f"That frame changes how the controlling factor ({ctrl_label}) should be "
            "read for cattle timing and diligence, without inventing missing water or forage."
        )
    else:
        intended = (
            "Intended cattle use is not yet specified. Seasonal grazing versus "
            "year-round cow-calf would change how water and forage confidence should be weighed."
        )

    selected = select_natural_environment_question(
        deal_context=deal_context,
        natural_cattle_profile=natural_cattle_profile,
    )
    change_view = [
        str(selected.get("change_view_text") or "Answering the next environmental question would refine the view."),
        *(list(overall.get("evidence_needed") or [])[:2]),
    ]
    knowledge_refs = [
        str(card.get("knowledge_id"))
        for card in cards
        if card.get("knowledge_id")
        and not str(card.get("knowledge_id")).upper().startswith("LEGAL_ACCESS")
    ][:4]
    if "EVIDENCE_STATUS_INTERPRETATION_001" not in knowledge_refs:
        knowledge_refs.append("EVIDENCE_STATUS_INTERPRETATION_001")

    refinement = (
        selected.get("prompt")
        or "Share the cattle use you are evaluating and any local water or vegetation context."
    )
    copy_ready = (
        f"For this confirmed parcel: please confirm whether this is seasonal grazing "
        f"or year-round cow-calf, and share any known livestock-water or vegetation "
        f"history. Controlling factor in the Profile: {ctrl_label}."
    )

    return {
        "land_character": (
            "This parcel reads as a rangeland setting whose terrain, vegetation, water context, "
            "climate, and soil form one connected natural system. The available domain evidence "
            "supports a preliminary physical portrait while preserving differences between "
            "parcel-wide measurements, point samples, and nearby context."
        ),
        "advisor_judgment": (
            f"This parcel presents a {status.replace('_', ' ').lower()} for cattle. "
            f"The current evidence makes a cattle use worth considering, while {ctrl_label.lower()} "
            "remains the condition that most needs to be understood before the operating picture is treated as dependable."
        )[:700],
        "operating_possibilities": [
            "The observed natural pattern supports continued evaluation of a cattle use rather than an immediate natural-environment rejection.",
            f"A cattle plan may be plausible if the real-world {ctrl_label.lower()} condition supports the intended grazing period.",
        ],
        "conditional_scenarios": [
            f"If the {ctrl_label.lower()} condition is confirmed as workable for the intended season, the natural-foundation view becomes more favorable.",
            f"If field evidence shows the {ctrl_label.lower()} condition cannot support the intended use, that issue would become an operating constraint rather than an evidence question.",
        ],
        "advisor_view": advisor_view[:600],
        "integrated_natural_reading": integrated[:2000],
        "intended_use_interpretation": intended[:1200],
        "what_would_change_the_view": [str(x) for x in change_view if x][:5],
        "refinement_request": str(refinement)[:400],
        "optional_copy_ready_request": copy_ready[:600],
        "cited_profile_refs": sorted(set(cited))[:24] or ["PROFILE"],
        "knowledge_refs": knowledge_refs,
        "next_question_id": selected["question_id"],
    }


def validate_natural_foundation_interpretation(
    interpretation: Mapping[str, Any],
    *,
    natural_cattle_profile: Mapping[str, Any],
    deal_context: Mapping[str, Any],
    knowledge_cards: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    schema = _load_schema("advisor_natural_foundation_interpretation.schema.json")
    try:
        Draft202012Validator(schema).validate(interpretation)
    except Exception as exc:  # noqa: BLE001
        violations.append({"code": "SCHEMA", "message": str(exc)})
        return violations

    cards = (
        knowledge_cards
        if knowledge_cards is not None
        else load_approved_knowledge_cards(workbench="natural_cattle")
    )
    allowed_cards = {
        str(card.get("knowledge_id"))
        for card in cards
        if not str(card.get("knowledge_id") or "").upper().startswith("LEGAL_ACCESS")
    }
    allowed_refs = _profile_ref_ids(natural_cattle_profile)
    overall = natural_cattle_profile.get("overall_natural_foundation") or {}
    controlling = overall.get("controlling_factor") or {}

    if interpretation.get("status") != overall.get("status"):
        violations.append(
            {
                "code": "STATUS_MUTATION",
                "message": "interpretation status must equal Profile overall status",
            }
        )
    if interpretation.get("natural_cattle_profile_hash") != natural_cattle_profile.get(
        "profile_hash"
    ):
        violations.append(
            {
                "code": "PROFILE_HASH_MISMATCH",
                "message": "interpretation must bind the current Profile hash",
            }
        )
    ctrl = interpretation.get("controlling_factor") or {}
    if ctrl.get("domain") != controlling.get("domain") or bool(ctrl.get("resolved")) != bool(
        controlling.get("resolved")
    ):
        violations.append(
            {
                "code": "CONTROLLING_FACTOR_MUTATION",
                "message": "controlling_factor must match the deterministic Profile",
            }
        )

    for ref in interpretation.get("cited_profile_refs") or []:
        if str(ref) not in allowed_refs:
            violations.append(
                {
                    "code": "DANGLING_PROFILE_REF",
                    "message": f"cited_profile_refs unknown: {ref}",
                }
            )
    for ref in interpretation.get("knowledge_refs") or []:
        if str(ref) not in allowed_cards:
            violations.append(
                {
                    "code": "UNKNOWN_OR_EXCLUDED_KNOWLEDGE_REF",
                    "message": f"knowledge_refs not on natural workbench: {ref}",
                }
            )
        if str(ref).upper().startswith("LEGAL_ACCESS"):
            violations.append(
                {
                    "code": "LEGAL_ACCESS_IN_PRIMARY_WORKBENCH",
                    "message": str(ref),
                }
            )

    qid = (interpretation.get("next_question") or {}).get("question_id")
    if qid not in NATURAL_QUESTION_IDS:
        violations.append(
            {
                "code": "QUESTION_NOT_IN_NATURAL_CATALOG",
                "message": str(qid),
            }
        )
    if qid == "Q_ACCESS_DOCUMENTS":
        violations.append(
            {
                "code": "ACCESS_QUESTION_FORBIDDEN",
                "message": "HUMAN_ACCESS_INFRA excluded from primary narrative path",
            }
        )

    blob = " ".join(
        [
            str(interpretation.get("land_character") or ""),
            str(interpretation.get("advisor_judgment") or ""),
            " ".join(str(x) for x in interpretation.get("operating_possibilities") or []),
            " ".join(str(x) for x in interpretation.get("conditional_scenarios") or []),
            str(interpretation.get("advisor_view") or ""),
            str(interpretation.get("integrated_natural_reading") or ""),
            str(interpretation.get("intended_use_interpretation") or ""),
            str(interpretation.get("refinement_request") or ""),
            str(interpretation.get("optional_copy_ready_request") or ""),
        ]
    )
    if PROHIBITED.search(blob):
        violations.append(
            {
                "code": "PROHIBITED_CLAIM",
                "message": "narrative contains stocking, access, or invented-condition language",
            }
        )
    for key in ("land_character", "advisor_judgment"):
        if re.match(
            r"(?i)^\s*(?:the\s+)?(?:evidence|data|assessment|parcel|property)?\s*"
            r"(?:is|are|remains?|cannot|does\s+not)?\s*"
            r"(?:insufficient|unavailable|unknown|unclear|missing|cannot\s+assess)",
            str(interpretation.get(key) or ""),
        ):
            violations.append(
                {
                    "code": "AUDIT_FIRST_NARRATIVE",
                    "message": f"{key} must lead with land insight rather than missing evidence",
                }
            )

    if int(interpretation.get("deal_context_version") or 0) != int(
        deal_context.get("context_version") or 1
    ):
        violations.append(
            {
                "code": "DEAL_CONTEXT_VERSION_MISMATCH",
                "message": "interpretation deal_context_version must match Deal Context",
            }
        )
    return violations


def _assemble_interpretation(
    *,
    draft: Mapping[str, Any],
    natural_cattle_profile: Mapping[str, Any],
    deal_context: Mapping[str, Any],
    source: str,
    violations: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    def _sentences(value: Any) -> list[str]:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if not text:
            return []
        return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]

    def _trim_at_sentence(value: Any, limit: int) -> str:
        """Remove exact filler/repetition, then fit complete sentences to limit."""
        kept: list[str] = []
        seen: set[str] = set()
        first_allowed: str | None = None
        for sentence in _sentences(value):
            if AI_SLOP_SENTENCE.match(sentence):
                continue
            if UNSUPPORTED_PROFESSIONAL_SENTENCE.search(sentence):
                continue
            if PARCEL_WATER_ABSENCE_SENTENCE.search(sentence):
                continue
            if re.search(r"(?i)\b(?:main|primary) limiting factor\b", sentence):
                controlling_label = BUYER_LABELS.get(
                    str(controlling.get("domain")), ""
                ).lower()
                if controlling_label and controlling_label not in sentence.lower():
                    continue
            # A provider sometimes appends one unnecessary disclaimer such as
            # "this is not a stocking-rate opinion" to otherwise grounded,
            # useful prose.  Removing that sentence is presentation-safe; it
            # must not discard the entire validated interpretation and replace
            # it with the low-information deterministic template.
            if PROHIBITED.search(sentence):
                continue
            if first_allowed is None:
                first_allowed = sentence
            fingerprint = re.sub(r"[^a-z0-9]+", " ", sentence.lower()).strip()
            if not fingerprint or fingerprint in seen:
                continue
            seen.add(fingerprint)
            candidate = " ".join(kept + [sentence]).strip()
            if len(candidate) <= limit:
                kept.append(sentence)
                continue
            break
        if kept:
            return " ".join(kept)

        # If every sentence was filtered, return an empty field so the caller
        # can apply a safe field-level fallback. Never resurrect the original
        # prohibited text here.
        if first_allowed is None:
            return ""

        # If the model returned one overlong allowed sentence, preserve its wording and
        # terminate at a word boundary. This is safer than discarding the entire
        # validated evidence run for a presentation-only length defect.
        text = re.sub(r"\s+", " ", first_allowed).strip()
        if len(text) <= limit:
            return text
        clipped = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:")
        return clipped + "." if clipped else ""

    def _list_field(value: Any) -> list[Any]:
        # Some OpenAI-compatible providers return a single string for a
        # schema-declared array. Preserve it as one item; never explode it
        # into one-character entries via list("..."). Validation still owns
        # item type, length, and reference checks.
        if value is None:
            return []
        if isinstance(value, list):
            return list(value)
        if isinstance(value, str):
            return [value]
        return [value]

    def _narrative(value: Any, field: str) -> str | None:
        if value is None and field == "optional_copy_ready_request":
            return None
        return _trim_at_sentence(value, NARRATIVE_LIMITS[field])

    def _narrative_list(value: Any, field: str) -> list[str]:
        def _structured_item(item: Any) -> Any:
            if not isinstance(item, Mapping):
                return item

            if field == "operating_possibilities":
                possibility = str(item.get("possibility") or "").strip()
                why = str(
                    item.get("why_plausible")
                    or item.get("reason")
                    or item.get("cattle_meaning")
                    or ""
                ).strip()
                if not possibility:
                    return ""
                if why:
                    return f"{possibility.rstrip('.!?')}. {why}"
                return possibility

            if field == "conditional_scenarios":
                condition = str(item.get("condition") or "").strip()
                if not condition:
                    return ""
                impact = str(item.get("impact") or "").strip().lower()
                already_directional = bool(
                    re.search(
                        r"(?i)\b(?:strengthen|strengthens|stronger|weaken|weakens|weaker)\b",
                        condition,
                    )
                )
                if impact.startswith("strength") and not already_directional:
                    condition = f"{condition.rstrip('.!?')}. This would strengthen the current view."
                elif impact.startswith("weaken") and not already_directional:
                    condition = f"{condition.rstrip('.!?')}. This would weaken the current view."
                return condition

            # Unknown object shapes must fail schema validation instead of being
            # rendered through str(dict) as Python/JSON syntax.
            return ""

        max_items, max_chars = LIST_LIMITS[field]
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in _list_field(value):
            text = _trim_at_sentence(_structured_item(item), max_chars)
            fingerprint = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
            if not text or fingerprint in seen:
                continue
            seen.add(fingerprint)
            cleaned.append(text)
            if len(cleaned) == max_items:
                break
        return cleaned

    overall = natural_cattle_profile.get("overall_natural_foundation") or {}
    controlling = overall.get("controlling_factor") or {}
    selected_id = str(draft.get("next_question_id") or "")
    selected = select_natural_environment_question(
        deal_context=deal_context,
        natural_cattle_profile=natural_cattle_profile,
    )
    if selected_id in NATURAL_QUESTION_IDS:
        from rangematch.advisor_question import QUESTION_CATALOG

        selected = dict(QUESTION_CATALOG[selected_id])
    operating_possibilities = _narrative_list(
        draft.get("operating_possibilities"), "operating_possibilities"
    ) or [
        (
            "The combined terrain and vegetation readings make a bounded cattle evaluation "
            f"plausible, provided the parcel-wide {BUYER_LABELS.get(str(controlling.get('domain')), 'natural').lower()} "
            "condition and grazing-season livestock water are verified."
        )
    ]
    conditional_scenarios = _narrative_list(
        draft.get("conditional_scenarios"), "conditional_scenarios"
    ) or [
        "If field forage condition supports the intended grazing window, the current natural-foundation view would strengthen."
    ]
    # A provider may return an empty change list even when the rest of its
    # interpretation is useful and grounded.  This presentation defect must
    # not discard the entire LLM narrative. Reuse the already-normalized
    # conditional pivots as the safe, evidence-bound field-level fallback.
    what_would_change_the_view = _narrative_list(
        draft.get("what_would_change_the_view"), "what_would_change_the_view"
    ) or list(conditional_scenarios)
    return {
        "schema_version": SCHEMA_VERSION,
        "interpretation_id": f"nfi_{uuid4().hex[:16]}",
        "run_id": str(deal_context.get("run_id") or ""),
        "deal_context_version": int(deal_context.get("context_version") or 1),
        "natural_cattle_profile_hash": str(natural_cattle_profile.get("profile_hash") or ""),
        "status": overall.get("status"),
        "controlling_factor": {
            "domain": controlling.get("domain"),
            "reason": controlling.get("reason") or "unresolved",
            "resolved": bool(controlling.get("resolved")),
        },
        "land_character": _narrative(draft.get("land_character"), "land_character"),
        "advisor_judgment": _narrative(draft.get("advisor_judgment"), "advisor_judgment"),
        "operating_possibilities": operating_possibilities,
        "conditional_scenarios": conditional_scenarios,
        "advisor_view": _narrative(draft.get("advisor_view"), "advisor_view"),
        "integrated_natural_reading": _narrative(
            draft.get("integrated_natural_reading"), "integrated_natural_reading"
        ),
        "intended_use_interpretation": _narrative(
            draft.get("intended_use_interpretation"), "intended_use_interpretation"
        ),
        "what_would_change_the_view": what_would_change_the_view,
        "refinement_request": _narrative(
            draft.get("refinement_request"), "refinement_request"
        ),
        "optional_copy_ready_request": _narrative(
            draft.get("optional_copy_ready_request"), "optional_copy_ready_request"
        ),
        "cited_profile_refs": _list_field(draft.get("cited_profile_refs")),
        "knowledge_refs": _list_field(draft.get("knowledge_refs")),
        "next_question": question_public(selected),
        "source": source,
        "validation_status": "PASSED" if not violations else "FAILED",
        "validation_violations": list(violations or []),
        "created_at": _utc_now(),
        "provenance": {
            "prompt_version": PROMPT_VERSION,
            "llm_authored_facts": False,
            "profile_status_authoritative": True,
            "human_access_infra_in_primary_narrative": False,
            "sentence_level_narrative_normalization": True,
            "field_level_empty_list_fallback": True,
        },
    }


def generate_natural_foundation_interpretation(
    *,
    natural_cattle_profile: Mapping[str, Any],
    deal_context: Mapping[str, Any],
    knowledge_cards: list[dict[str, Any]] | None = None,
    previous_interpretation: Mapping[str, Any] | None = None,
    provider_name: str | None = None,
    force_fallback: bool = False,
    combined_environmental_evidence_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Profile + cards + Deal Context → LLM narrative or deterministic fallback."""
    cards = (
        knowledge_cards
        if knowledge_cards is not None
        else load_approved_knowledge_cards(workbench="natural_cattle")
    )
    workbench = build_natural_interpretation_workbench(
        natural_cattle_profile=natural_cattle_profile,
        deal_context=deal_context,
        knowledge_cards=cards,
        previous_interpretation=previous_interpretation,
        combined_environmental_evidence_packet=combined_environmental_evidence_packet,
    )

    def _fallback(reason: str) -> dict[str, Any]:
        draft = render_deterministic_natural_interpretation(
            natural_cattle_profile=natural_cattle_profile,
            deal_context=deal_context,
            knowledge_cards=cards,
        )
        assembled = _assemble_interpretation(
            draft=draft,
            natural_cattle_profile=natural_cattle_profile,
            deal_context=deal_context,
            source=SOURCE_FALLBACK,
        )
        violations = validate_natural_foundation_interpretation(
            assembled,
            natural_cattle_profile=natural_cattle_profile,
            deal_context=deal_context,
            knowledge_cards=cards,
        )
        assembled["validation_status"] = "PASSED" if not violations else "FAILED"
        assembled["validation_violations"] = violations
        assembled["provenance"] = {
            **(assembled.get("provenance") or {}),
            "fallback_reason": reason,
            "llm_used": False,
        }
        return assembled

    requested = (provider_name or "FIXTURE").strip().upper()
    if force_fallback or requested == "FIXTURE" or not is_live_llm_provider(requested):
        return _fallback("fixture_or_forced_fallback")

    try:
        provider = get_provider(requested)
        completion = provider.complete_json(
            system=SYSTEM_PROMPT,
            user=json.dumps({"workbench": workbench}, ensure_ascii=False),
            prompt_version=PROMPT_VERSION,
            fixture_key=None,
            response_schema={
                "type": "object",
                "additionalProperties": False,
                "required": ["natural_foundation_interpretation"],
                "properties": {
                    "natural_foundation_interpretation": LLM_OUTPUT_SCHEMA,
                },
            },
        )
        if completion.content is None:
            return _fallback(completion.error_code or "LLM_UNAVAILABLE")
        draft = (completion.content or {}).get("natural_foundation_interpretation") or {}
        if not isinstance(draft, Mapping):
            return _fallback("llm_payload_not_object")
        assembled = _assemble_interpretation(
            draft=draft,
            natural_cattle_profile=natural_cattle_profile,
            deal_context=deal_context,
            source=SOURCE_LIVE,
        )
        violations = validate_natural_foundation_interpretation(
            assembled,
            natural_cattle_profile=natural_cattle_profile,
            deal_context=deal_context,
            knowledge_cards=cards,
        )
        if violations:
            first = violations[0]
            return _fallback(
                "validation_failed:"
                f"{first.get('code')}:"
                f"{first.get('message')}"
            )
        assembled["validation_status"] = "PASSED"
        assembled["validation_violations"] = []
        assembled["provenance"] = {
            **(assembled.get("provenance") or {}),
            "llm_used": True,
            "provider": requested,
            "model_id": completion.model_id,
        }
        return assembled
    except Exception as exc:  # noqa: BLE001 — never fail the evidence run
        return _fallback(f"llm_error:{type(exc).__name__}")


def interpretation_withdraws_with_profile(
    *,
    before: Mapping[str, Any],
    after_profile: Mapping[str, Any],
    deal_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Gate helper: regenerate interpretation after Profile evidence withdrawal."""
    return generate_natural_foundation_interpretation(
        natural_cattle_profile=after_profile,
        deal_context=deal_context,
        previous_interpretation=before,
        force_fallback=True,
    )
