"""Cattle ranch operating narrative. LLM explains Profile; it does not invent facts."""

from __future__ import annotations

import re
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from rangematch.advisor_insight import candidate_action_ids, validate_recommended_order

RANCH_NARRATIVE_SCHEMA_ID = "RANGEMATCH_RANCH_OPERATING_NARRATIVE@0.1.0"
INTERNAL_ID = re.compile(
    r"\b(?:ACTION|OBS|BOTTLENECK|CLAIM|VAR_F|INSIGHT|FEED|DRINK|MOVE)_[A-Z0-9_]+\b"
)
PROHIBITED = re.compile(
    r"(?:suitable|unsuitable|stocking rate|carrying capacity|herd size|"
    r"buy this|do not buy|has legal access|no legal access|"
    r"year-round (?:water|drinking)|usable livestock water|"
    r"\b(?:a well|the well|wells|stock tank|fences?|gates?|corrals?|barns?|paddocks?)\b|"
    r"\b(?:unknown|unproven|uncertainty)\b)",
    re.I,
)
NHD_AS_DRINKER = re.compile(
    r"\b(?:nhd|mapped (?:water|hydrography)(?: leads?)?)\b.{0,40}\b"
    r"(?:drinking water|drinkers?|stock water|livestock water)\b",
    re.I,
)

RANCH_NARRATIVE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "operating_thesis",
        "ranch_reading",
        "how_livestock_would_use_it",
        "attention_pivot",
        "conditional_path",
        "client_summary",
    ],
    "properties": {
        "operating_thesis": {"type": "string", "minLength": 40, "maxLength": 420},
        "ranch_reading": {"type": "string", "minLength": 80, "maxLength": 1600},
        "how_livestock_would_use_it": {"type": "string", "minLength": 80, "maxLength": 1800},
        "attention_pivot": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "largest_operating_theme",
                "first_action_id",
                "why_theme_and_action_differ",
            ],
            "properties": {
                "largest_operating_theme": {"type": "string", "minLength": 20, "maxLength": 400},
                "first_action_id": {"type": "string"},
                "why_theme_and_action_differ": {"type": "string", "minLength": 30, "maxLength": 500},
            },
        },
        "conditional_path": {
            "type": "object",
            "additionalProperties": False,
            "required": ["if_access_holds", "if_access_fails"],
            "properties": {
                "if_access_holds": {"type": "string", "minLength": 30, "maxLength": 500},
                "if_access_fails": {"type": "string", "minLength": 30, "maxLength": 500},
            },
        },
        "client_summary": {"type": "string", "minLength": 40, "maxLength": 700},
    },
}

RANCH_NARRATIVE_BUNDLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["ranch_narrative"],
    "properties": {"ranch_narrative": RANCH_NARRATIVE_OUTPUT_SCHEMA},
}

RANCH_SYSTEM_PROMPT = """You are a senior buyer-side cattle diligence advisor for RangeMatch.
Write a preliminary cattle operating story from the Operating Profile and Packet.
This is pre-visit diligence, not a livestock assessment and not a purchase opinion.

Return one JSON object: {"ranch_narrative": RanchNarrative} with only:
operating_thesis, ranch_reading, how_livestock_would_use_it, attention_pivot,
conditional_path, client_summary.

Rules:
- Explain how feed context, water investigation leads, and movement context
  (area, median slope, parcel outline, road relationship) jointly shape the next spend.
- Call movement "movement context". Do not claim a complete livestock movement analysis.
- Water is mapped investigation leads, never drinking water, wells, tanks, or pins.
- Do not invent fences, gates, barns, corrals, wells, or facilities.
- Do not calculate stocking, herd size, carrying capacity, or suitability.
- Do not conclude legal access or buy/no-buy.
- Do not write an unknown/unproven checklist.
- Do not print internal IDs in prose.
- attention_pivot.first_action_id must be the Packet first allowed action.
- The largest operating theme may be water while the first action is still access documents.
- If DRAWABLE_WATER_NONE is a guardrail, do not narrate "water location unknown" as a card.
  Say the visit purpose is a category-level water inventory after access paper.
Every field must be complete sentences ending in punctuation.
"""


def _as_mapping(value: Any) -> dict[str, Any]:
    """Treat non-objects as empty. Prevents string/list crashes on .get/.values."""
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def ranch_narrative_to_compat(ranch: Mapping[str, Any]) -> dict[str, Any]:
    """Map ranch fields onto the existing PDF narrative slots."""
    pivot = _as_mapping(ranch.get("attention_pivot"))
    path = _as_mapping(ranch.get("conditional_path"))
    return {
        "thesis": ranch.get("operating_thesis"),
        "executive_memo": ranch.get("ranch_reading"),
        "client_summary": ranch.get("client_summary"),
        "action_pivot": {
            "largest_gap": pivot.get("largest_operating_theme"),
            "first_action_id": pivot.get("first_action_id"),
            "first_action_reason": pivot.get("why_theme_and_action_differ"),
            "deferred_action_ids": [],
            "deferred_reason": "Forage interpretation waits behind access paper and water inventory.",
        },
        "conditional_path": {
            "if_favorable": path.get("if_access_holds"),
            "if_unfavorable": path.get("if_access_fails"),
            "still_unknown": "Neither branch is a purchase conclusion.",
        },
    }


def render_deterministic_ranch_narrative(
    profile: Mapping[str, Any],
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    """Fail-soft cattle story from Profile + Packet. No invented infrastructure."""
    first = (
        list(profile.get("action_execution_order") or [])
        or [
            str(row.get("action_id"))
            for row in sorted(
                packet.get("actions") or [],
                key=lambda item: int(item.get("execution_order") or 0),
            )
        ]
    )
    first_action = first[0] if first else "ACTION_ACCESS_DOCUMENTS"
    types = {
        row.get("statement_type")
        for bucket in (profile.get("operating_domains") or {}).values()
        for row in (bucket.get("statements") or [])
    }
    feed = (
        "Modeled herbaceous production and rainfall are feed context only. "
        "They organize diligence; they are not available forage or a herd plan."
        if "MODELED_PRODUCTION_SNAPSHOT" in types or "PRECIPITATION_CONTEXT" in types
        else "Feed context is limited on this run. Do not invent a forage picture."
    )
    if "WATER_INVENTORY_UNAVAILABLE" in types:
        water = (
            "Mapped-water inventory was not obtained. That is not proof the ground has none. "
            "Ask whether a developed source is claimed after the access paper."
        )
    elif "NO_MAPPED_HYDROGRAPHY_LEADS" in types:
        water = (
            "The mapped-hydrography search returned no leads. That is not an absence finding. "
            "A field inventory is still a later diligence question."
        )
    elif "DRAWABLE_WATER_NONE" in types:
        water = (
            "Mapped hydrography identities exist as investigation leads, but none can be drawn "
            "as a field route yet. After access paper, the visit job is a category-level water inventory."
        )
    else:
        water = (
            "Mapped hydrography identities are investigation leads for a later field review. "
            "They are not drinkers and not a water-right conclusion."
        )
    move = (
        "Movement context comes from the confirmed outline, median slope, and mapped road "
        "relationship. That is terrain and access-paper context, not a livestock movement analysis."
    )
    return {
        "operating_thesis": (
            "This tract already has a preliminary cattle operating picture from public evidence. "
            "Water investigation is the largest operating theme; access documents remain the first spend."
        ),
        "ranch_reading": (
            "Read this as a cattle diligence object, not a scored ranch. "
            f"{feed} {water} {move} "
            "The useful question is which cheap document or field job comes next, not whether to buy."
        ),
        "how_livestock_would_use_it": (
            f"{feed} {water} {move} "
            "Together they set a defined next job: confirm the entrance basis, then use any visit "
            "for water inventory rather than a general ranch tour."
        ),
        "attention_pivot": {
            "largest_operating_theme": (
                "Water investigation is the largest cattle-operating theme on this tract."
            ),
            "first_action_id": first_action,
            "why_theme_and_action_differ": (
                "Access documents still come first because they are cheaper than travel and "
                "decide whether a water-focused visit has a defined job."
            ),
        },
        "conditional_path": {
            "if_access_holds": (
                "If the entrance basis holds, schedule a water-inventory visit and keep RAP "
                "as a modeled snapshot only."
            ),
            "if_access_fails": (
                "If the entrance basis cannot be shown, pause travel and give title the question. "
                "Do not spend on a search for absence."
            ),
        },
        "client_summary": (
            "Request the access paper first. If it holds, use the trip for a water inventory. "
            "Public feed and movement layers already did their job: they set the order."
        ),
    }


def validate_ranch_narrative(
    ranch: Mapping[str, Any] | Any,
    workbench: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Type → JSON Schema → semantic. Never raises on malformed model objects."""
    violations: list[dict[str, str]] = []
    if not isinstance(ranch, Mapping):
        return [
            {
                "code": "RANCH_NARRATIVE_TYPE_INVALID",
                "message": f"ranch_narrative must be object, got {type(ranch).__name__}",
            }
        ]
    # Explicit nested type gate before semantic .get/.values (jsonschema alone is not enough
    # if we walk fields afterward — string-instead-of-object is a known DeepSeek failure).
    for field in ("attention_pivot", "conditional_path"):
        value = ranch.get(field)
        if value is not None and not isinstance(value, Mapping):
            violations.append(
                {
                    "code": "RANCH_NARRATIVE_TYPE_INVALID",
                    "message": f"{field} must be object, got {type(value).__name__}",
                }
            )
    for err in sorted(
        Draft202012Validator(RANCH_NARRATIVE_OUTPUT_SCHEMA).iter_errors(dict(ranch)),
        key=lambda item: list(item.absolute_path),
    ):
        path = ".".join(str(part) for part in err.absolute_path) or "$"
        violations.append({"code": "RANCH_NARRATIVE_SCHEMA_INVALID", "message": f"{path}: {err.message}"})
    if violations:
        # Do not run semantic walks on structurally invalid payloads.
        return violations
    pivot = _as_mapping(ranch.get("attention_pivot"))
    path_obj = _as_mapping(ranch.get("conditional_path"))
    first = str(pivot.get("first_action_id") or "")
    known = candidate_action_ids(dict(workbench))
    if first and first not in known:
        violations.append({"code": "RANCH_ACTION_UNKNOWN", "message": first})
    if first:
        violations.extend(validate_recommended_order([first], dict(workbench)))
    parts = [
        ranch.get("operating_thesis"),
        ranch.get("ranch_reading"),
        ranch.get("how_livestock_would_use_it"),
        ranch.get("client_summary"),
        pivot.get("largest_operating_theme"),
        pivot.get("why_theme_and_action_differ"),
        *path_obj.values(),
    ]
    prose = " ".join(str(item or "") for item in parts)
    leaked = INTERNAL_ID.search(prose)
    if leaked:
        violations.append({"code": "RANCH_INTERNAL_ID", "message": leaked.group(0)})
    forbidden = PROHIBITED.search(prose)
    if forbidden:
        violations.append({"code": "RANCH_PROHIBITED_CONCLUSION", "message": forbidden.group(0)})
    if NHD_AS_DRINKER.search(prose):
        violations.append({"code": "RANCH_NHD_AS_DRINKER", "message": "mapped hydrography is not drinking water"})
    for item in parts:
        value = str(item or "").rstrip()
        if value and value[-1] not in ".?!":
            violations.append({"code": "RANCH_INCOMPLETE_SENTENCE", "message": value[-80:]})
            break
    thesis_ids = set(workbench.get("operating_thesis_inputs") or [])
    if "DRINK_DRAWABLE_WATER_NONE" in thesis_ids:
        violations.append({"code": "RANCH_GUARDRAIL_IN_THESIS", "message": "DRAWABLE_WATER_NONE"})
    return violations
