"""RangeMatch Cattle Operating Snapshot with a buyer-facing evidence appendix.

Renders the latest validated Operating Conclusion + Deal Context only.
Kitchen / Factor dumps stay out of the PDF.
"""

from __future__ import annotations

import re
import json
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Mapping

SNAPSHOT_SCHEMA = "RANGEMATCH_CATTLE_OPERATING_SNAPSHOT@0.1.0"
MAX_BODY_WORDS = 400
MAX_SUMMARY_WORDS = 230
MAX_ROW_WORDS = 55
MAX_FOOTER_WORDS = 80
MAX_HEADLINE_WORDS = 30
MAX_NARRATIVE_WORDS = 680

NARRATIVE_PROMPT_VERSION = "RANGEMATCH_SNAPSHOT_WRITER@0.1.0"
NARRATIVE_FIELDS = (
    "bottom_line",
    "what_changed",
    "ranch_reading",
    "next_steps",
    "copy_and_send",
)
NARRATIVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": list(NARRATIVE_FIELDS),
    "properties": {
        "bottom_line": {"type": "string", "minLength": 80, "maxLength": 3600},
        "what_changed": {"type": "string", "minLength": 50, "maxLength": 3600},
        "ranch_reading": {"type": "string", "minLength": 100, "maxLength": 3600},
        "next_steps": {"type": "string", "minLength": 80, "maxLength": 3600},
        "copy_and_send": {"type": "string", "minLength": 40, "maxLength": 2400},
    },
}
NARRATIVE_BUNDLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["snapshot_narrative"],
    "properties": {"snapshot_narrative": NARRATIVE_SCHEMA},
}

SNAPSHOT_WRITER_PROMPT = """You are a senior buyer-side ranch advisor writing a one-page cattle operating snapshot.
Write a coherent professional narrative, not a dashboard and not a list of missing data.
Return JSON with snapshot_narrative containing exactly five prose fields:
bottom_line, what_changed, ranch_reading, next_steps, copy_and_send.

Reason across the physical evidence, cattle knowledge, current Deal Context, and the
validated operating conclusion. Lead with a provisional judgment. Explain what the
buyer's answer changed, how feed/water/movement/access work together, and what to do next.
You may make directional operating inferences and conditional recommendations.

Hard boundaries:
- Do not invent wells, tanks, fences, gates, facilities, water reliability, legal access,
  water rights, forage quality, or stocking capacity.
- Do not provide stocking rate, herd size, suitability score, appraisal, or buy/no-buy advice.
- Do not say the forage can support cattle or that the property is ready/not ready for cattle.
  Say instead what the evidence suggests and which operating premise remains unverified.
- Do not tell the buyer to avoid an unrelated spend unless the validated next-action policy says so.
- Mapped hydrography is a lead, never proof of usable livestock water.
- Put internal references only in JSON reference fields supplied elsewhere. Never expose
  OBS_*, ACTION_*, Factor IDs, hashes, knowledge-card IDs, source codes, or status enums.
- State uncertainty inside the reasoning naturally; do not produce an unknown-data checklist.
- Use 450-650 total words. Write for a non-technical ranch buyer.
- copy_and_send must be one standalone 40-100 word request beginning with "Please".
  It must not repeat or summarize the report.
- bottom_line must not repeat the separate operating-conclusion headline.
- next_steps should introduce two concise requests on separate lines: livestock-water
  source details, then recorded entrance/access documents. Follow with the condition
  that gives a field visit a clear purpose.
"""

INTERNAL_LEAK = re.compile(
    r"\b(?:OBS_|BOTTLENECK_|CLAIM_|ACTION_|FACTOR_|F0[1-8]_|MIREYE-|concl_|deal_|ans_|chat_)"
    r"|(?:\bF0[1-8]\b)|(?:packet_hash)|(?:unified_output)",
    re.I,
)


class SnapshotError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _plain(text: Any) -> str:
    raw = str(text or "")
    return (
        raw.replace("—", "-")
        .replace("–", "-")
        .replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("•", "-")
    )


def _words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text or ""))


def _clip_words(text: str, limit: int) -> str:
    tokens = re.findall(r"\S+|\s+", text or "")
    count = 0
    out: list[str] = []
    for token in tokens:
        if token.isspace():
            out.append(token)
            continue
        count += 1
        if count > limit:
            break
        out.append(token)
    return "".join(out).strip()


def _sentence_pack(parts: list[str], *, max_sentences: int = 5) -> str:
    sentences: list[str] = []
    for part in parts:
        chunk = _plain(part).strip()
        if not chunk:
            continue
        if chunk[-1] not in ".!?":
            chunk += "."
        sentences.append(chunk)
        if len(sentences) >= max_sentences:
            break
    return " ".join(sentences)


DOMAIN_READINGS = {
    "FEED": {
        "MODELED_PRODUCTION_SNAPSHOT": (
            "Modeled vegetation production offers forage context only, not available feed.",
            "Modeled production snapshot",
        ),
        "PRECIPITATION_CONTEXT": (
            "Precipitation context informs forage attention without proving usable feed.",
            "Precipitation observation",
        ),
        "_default": (
            "Public forage context frames attention but does not finish a feed claim.",
            "Vegetation context leads",
        ),
    },
    "DRINK": {
        "MAPPED_HYDROGRAPHY_LEAD_COUNT": (
            "Mapped hydrography count is a lead list only, not a livestock-water inventory.",
            "Mapped hydrography leads",
        ),
        "DRAWABLE_WATER_LEAD_COUNT": (
            "Drawable mapped water features are investigation leads, not proven drinkers.",
            "Drawable water leads",
        ),
        "DRAWABLE_WATER_NONE": (
            "No drawable mapped water leads appear; this is not an absence-of-water finding.",
            "No drawable mapped leads",
        ),
        "WATER_INVENTORY_UNAVAILABLE": (
            "Livestock-water inventory is unavailable from public layers for this parcel.",
            "Water source unavailable",
        ),
        "NO_MAPPED_HYDROGRAPHY_LEADS": (
            "No mapped hydrography leads appear; this does not prove dry ground.",
            "No mapped hydrography leads",
        ),
        "_default": (
            "Livestock-water use is not established from public layers alone.",
            "Mapped water leads only",
        ),
    },
    "MOVE": {
        "PARCEL_AREA_CONTEXT": (
            "Parcel area frames movement scale without inventing grazable acres.",
            "Parcel area context",
        ),
        "SLOPE_MEDIAN_CONTEXT": (
            "Median slope shapes movement effort without inventing fences or facilities.",
            "Slope context",
        ),
        "ROAD_BOUNDARY_RELATIONSHIP": (
            "Road contact is physical context, not a documentary access conclusion.",
            "Road-boundary relationship",
        ),
        "PARCEL_COMPACTNESS": (
            "Parcel compactness affects how cattle would work the tract.",
            "Parcel compactness",
        ),
        "PARCEL_FRAGMENTATION": (
            "Fragmentation can complicate movement without inventing cross-fences.",
            "Parcel fragmentation",
        ),
        "DRAWABLE_WATER_DISTRIBUTION": (
            "Water-lead distribution can pull movement patterns; it is not infrastructure.",
            "Water-lead distribution",
        ),
        "_default": (
            "Terrain and parcel form affect movement reading without inventing infrastructure.",
            "Parcel geometry context",
        ),
    },
}


def _domain_reading(profile: Mapping[str, Any] | None, domain: str) -> tuple[str, str]:
    catalog = DOMAIN_READINGS[domain]
    domains = (profile or {}).get("operating_domains") or {}
    bucket = None
    if isinstance(domains, Mapping):
        bucket = domains.get(domain) or domains.get(domain.lower())
    if not isinstance(bucket, Mapping):
        return catalog["_default"]
    statements = [
        row for row in (bucket.get("statements") or []) if isinstance(row, Mapping)
    ]
    if not statements:
        return catalog["_default"]
    top = statements[0]
    statement_type = str(top.get("statement_type") or "")
    reading, basis = catalog.get(statement_type) or catalog["_default"]
    # Prefer buyer-safe reading; never print observation IDs from value_refs.
    reading = _clip_words(_plain(reading), MAX_ROW_WORDS)
    basis = _clip_words(_plain(basis), 12)
    return reading, basis


def _copy_ready_questions(conclusion: Mapping[str, Any], change: Mapping[str, Any] | None) -> list[str]:
    questions: list[str] = []
    live = (conclusion.get("next_question") or {}).get("prompt")
    if live:
        questions.append(_plain(live))
    if change and change.get("user_answer"):
        # After an answer, prefer the new live question plus a document ask.
        questions = []
        if live:
            questions.append(_plain(live))
    questions.append(
        "Can you provide the recorded entrance or title basis used to reach this tract?"
    )
    # Deduplicate while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for row in questions:
        key = row.lower()
        if key in seen or not row:
            continue
        seen.add(key)
        out.append(row)
        if len(out) >= 2:
            break
    return out


def _copy_and_send(conclusion: Mapping[str, Any]) -> str:
    """Create one buyer-safe request from validated conclusion fields."""
    spend = str(conclusion.get("next_spend_class") or "")
    if spend == "DOCUMENT_REVIEW":
        return (
            "Please send the recorded access or easement material for the property, "
            "together with a list of livestock-water sources showing each source type, "
            "approximate location, and normal months of use."
        )
    if spend == "TARGETED_FIELD_VISIT":
        return (
            "Please identify the livestock-water sources and entrance that should be "
            "inspected, including their approximate locations and normal months of use."
        )
    return (
        "Please describe the intended cattle use and any claimed livestock-water system, "
        "then send the supporting access and water records available for this property."
    )


def _fallback_snapshot_narrative(
    *,
    conclusion: Mapping[str, Any],
    deal: Mapping[str, Any],
    change: Mapping[str, Any] | None,
    profile: Mapping[str, Any] | None,
) -> dict[str, str]:
    operation = str(deal.get("operation_type") or "UNKNOWN").upper()
    seasonal = operation == "SEASONAL_GRAZING"
    bottom = (
        "This property has enough of a physical operating picture to continue investigating, "
        "but its cattle-water story is not yet strong enough to plan around. The confirmed "
        "parcel has generally manageable terrain, a measurable vegetation signal and road "
        "contact at the boundary. None of those observations currently appears to be the main "
        "obstacle to seasonal cattle use. The controlling question is water: this review did not "
        "return a usable mapped-water inventory, and no developed livestock-water system has "
        "been supplied by the seller or buyer. That does not mean the property has no water. It "
        "means water cannot yet be included confidently in the operating plan."
        if seasonal
        else str(conclusion.get("summary") or conclusion.get("headline") or "")
    )
    changed = (
        "You said that the intended use is seasonal grazing rather than a year-round cow-calf "
        "operation. That narrows the question. This review does not need to establish twelve "
        "months of water availability for the operating concept you described. It does need "
        "evidence that cattle can obtain reliable water during the intended grazing months, in "
        "locations that allow reasonable use of the parcel. The overall view therefore remains "
        "conditional, but the next investigation can now be much more specific."
        if seasonal
        else str((change or {}).get("summary") or "The intended operation still needs to be defined before the water requirement can be narrowed.")
    )
    ranch = (
        "The terrain does not presently stand out as the main operating constraint. The vegetation "
        "data indicate recent herbaceous growth, but the satellite estimate should not be converted "
        "into available forage or herd size without field condition, plant composition and grazing-history "
        "evidence. A mapped road reaches the parcel boundary. That is useful physical context, but the "
        "entrance should still be checked against title or recorded access documents. Water remains the "
        "primary operating question because neither mapped evidence nor seller-supplied records currently "
        "identify the sources cattle would actually use."
    )
    next_steps = (
        "Before arranging a general property visit, request:\n"
        "1. A list of every livestock-water source, including source type, approximate location and normal months of use.\n"
        "2. The deed, easement or title material supporting the claimed entrance.\n"
        "If the seller identifies a credible "
        "seasonal water system and the entrance documents support access, the field visit has a clear "
        "purpose: inspect those water sources and determine how cattle would move between water and forage areas. "
        "If the seller cannot identify a working system, that is important operating information to learn "
        "before building a grazing plan around the property."
    )
    copy_send = (
        "Please send the recorded access or easement material for the property, together with a list of "
        "livestock-water sources showing each source type, approximate location, normal months of use and "
        "any available maintenance or drought-season records. Please include recent photographs or a simple "
        "map if those materials are already available."
    )
    return {
        "bottom_line": _plain(bottom),
        "what_changed": _plain(changed),
        "ranch_reading": _plain(ranch),
        "next_steps": _plain(next_steps),
        "copy_and_send": _plain(copy_send),
    }


def _validate_snapshot_narrative(narrative: Mapping[str, Any] | Any) -> list[dict[str, str]]:
    from jsonschema import Draft202012Validator

    if not isinstance(narrative, Mapping):
        return [{"code": "SNAPSHOT_NARRATIVE_TYPE", "message": type(narrative).__name__}]
    violations: list[dict[str, str]] = []
    for err in Draft202012Validator(NARRATIVE_SCHEMA).iter_errors(dict(narrative)):
        violations.append({"code": "SNAPSHOT_NARRATIVE_SCHEMA", "message": err.message})
    prose = " ".join(str(narrative.get(field) or "") for field in NARRATIVE_FIELDS)
    if _words(prose) > MAX_NARRATIVE_WORDS:
        violations.append({"code": "SNAPSHOT_NARRATIVE_WORDS", "message": "narrative too long"})
    copy_text = str(narrative.get("copy_and_send") or "").strip()
    copy_words = _words(copy_text)
    if not copy_text.lower().startswith("please ") or not 40 <= copy_words <= 100:
        violations.append(
            {
                "code": "SNAPSHOT_COPY_REQUEST_INVALID",
                "message": "copy_and_send must be one 40-100 word request beginning with Please",
            }
        )
    hit = INTERNAL_LEAK.search(prose)
    if hit:
        violations.append({"code": "SNAPSHOT_NARRATIVE_INTERNAL_ID", "message": hit.group(0)})
    prohibited = re.search(
        r"\b(?:stocking rate|carrying capacity|herd size|buy this|do not buy|"
        r"has legal access|no legal access|(?:not )?ready for (?:seasonal )?cattle|"
        r"support cattle|supports cattle|do not spend|don't spend)\b",
        prose,
        re.I,
    )
    if prohibited:
        violations.append({"code": "SNAPSHOT_NARRATIVE_PROHIBITED", "message": prohibited.group(0)})
    return violations


def generate_snapshot_narrative(
    run: Mapping[str, Any], *, provider_name: str | None = None
) -> dict[str, Any]:
    from rangematch.llm_provider import (
        configured_provider_name,
        get_provider,
        is_live_llm_provider,
    )

    conclusion = run.get("operating_conclusion") or {}
    deal = run.get("deal_context") or {}
    profile = run.get("operating_profile") or {}
    change = run.get("conclusion_change") if isinstance(run.get("conclusion_change"), Mapping) else None
    fallback = _fallback_snapshot_narrative(
        conclusion=conclusion, deal=deal, change=change, profile=profile
    )
    requested = (provider_name or configured_provider_name()).strip().upper()
    if requested == "FIXTURE":
        return {"content": fallback, "source": "DETERMINISTIC_FALLBACK", "validation_status": "PASSED"}

    packet = run.get("packet") or {}
    workbench = {
        "address": run.get("address"),
        "parcel_confirmed": run.get("parcel_geometry_confirmed"),
        "deal_context": {
            "operation_type": deal.get("operation_type"),
            "diligence_stage": deal.get("diligence_stage"),
            "seller_claims": deal.get("seller_claims") or [],
            "user_answers": deal.get("user_answers") or [],
        },
        "operating_conclusion": {
            key: conclusion.get(key)
            for key in (
                "headline", "summary", "primary_constraint", "next_action",
                "next_spend_class", "missing_evidence", "what_would_change_view"
            )
        },
        "conclusion_change": change,
        "operating_profile": {
            "domain_attention_order": profile.get("domain_attention_order"),
            "operating_thesis_inputs": profile.get("operating_thesis_inputs"),
            "operating_domains": profile.get("operating_domains"),
        },
        "observations": [
            {
                "label": row.get("label") or row.get("title"),
                "value": row.get("value"),
                "unit": row.get("unit"),
                "evidence_state": row.get("evidence_state"),
                "summary": row.get("summary") or row.get("statement"),
            }
            for row in (packet.get("observations") or [])
            if isinstance(row, Mapping)
        ][:20],
    }
    try:
        completion = get_provider(requested).complete_json(
            system=SNAPSHOT_WRITER_PROMPT,
            user=json.dumps(workbench, ensure_ascii=False),
            prompt_version=NARRATIVE_PROMPT_VERSION,
            response_schema=NARRATIVE_BUNDLE_SCHEMA if is_live_llm_provider(requested) else None,
        )
        content = (completion.content or {}).get("snapshot_narrative")
        violations = _validate_snapshot_narrative(content)
        if completion.provider_status == "OK" and not violations:
            return {"content": dict(content), "source": "LIVE_LLM", "validation_status": "PASSED"}
        return {
            "content": fallback,
            "source": "DETERMINISTIC_FALLBACK",
            "validation_status": "PASSED",
            "provider_attempt_status": completion.provider_status,
            "provider_attempt_violations": violations,
        }
    except Exception as exc:  # noqa: BLE001 - PDF must remain downloadable
        return {
            "content": fallback,
            "source": "DETERMINISTIC_FALLBACK",
            "validation_status": "PASSED",
            "provider_attempt_status": "FAILED_EXTERNAL",
            "provider_attempt_violations": [{"code": "SNAPSHOT_WRITER_EXCEPTION", "message": type(exc).__name__}],
        }


def project_cattle_operating_snapshot(run: Mapping[str, Any]) -> dict[str, Any]:
    """Project a one-page print model from the latest conclusion + context."""
    conclusion = run.get("operating_conclusion")
    deal = run.get("deal_context")
    if not isinstance(conclusion, Mapping):
        raise SnapshotError(
            "SNAPSHOT_CONCLUSION_REQUIRED",
            "Operating Conclusion is required before exporting the Snapshot",
        )
    if not isinstance(deal, Mapping):
        raise SnapshotError(
            "SNAPSHOT_CONTEXT_REQUIRED",
            "Deal Context is required before exporting the Snapshot",
        )

    context_version = int(deal.get("context_version") or 0)
    conclusion_version = int(conclusion.get("deal_context_version") or 0)
    if context_version < 1 or conclusion_version != context_version:
        raise SnapshotError(
            "SNAPSHOT_CONTEXT_VERSION_MISMATCH",
            f"conclusion deal_context_version={conclusion_version} "
            f"!= deal_context.context_version={context_version}",
        )

    profile = run.get("operating_profile") if isinstance(run.get("operating_profile"), Mapping) else None
    change = run.get("conclusion_change") if isinstance(run.get("conclusion_change"), Mapping) else None
    initial = (
        run.get("initial_operating_conclusion")
        if isinstance(run.get("initial_operating_conclusion"), Mapping)
        else None
    )
    narrative_result = generate_snapshot_narrative(run)
    narrative = narrative_result["content"]

    headline = _clip_words(_plain(conclusion.get("headline") or ""), MAX_HEADLINE_WORDS)
    summary = _sentence_pack([str(conclusion.get("summary") or "")], max_sentences=6)
    summary = _clip_words(summary, MAX_SUMMARY_WORDS)

    feed_reading, feed_basis = _domain_reading(profile, "FEED")
    drink_reading, drink_basis = _domain_reading(profile, "DRINK")
    move_reading, move_basis = _domain_reading(profile, "MOVE")

    if change and change.get("user_answer"):
        asked = _plain(
            ((initial or {}).get("next_question") or {}).get("prompt")
            or "The Agent asked one high-information diligence question."
        )
        answered = change.get("user_answer") or {}
        value = answered.get("value")
        if isinstance(value, bool):
            answer_text = "Yes" if value else "No"
        else:
            answer_text = str(value or "").replace("_", " ").title()
        update = _plain(change.get("summary") or "The conclusion was updated after this answer.")
        what_changed = {
            "mode": "ANSWERED",
            "agent_asked": asked,
            "buyer_answered": answer_text,
            "update_summary": update,
            "change_status": change.get("change_status"),
        }
    else:
        what_changed = {
            "mode": "QUESTION_OPEN",
            "agent_asked": _plain(
                (conclusion.get("next_question") or {}).get("prompt")
                or "No high-information question is currently attached."
            ),
            "buyer_answered": None,
            "update_summary": None,
            "change_status": None,
        }

    spend = str(conclusion.get("next_spend_class") or "REMOTE_INFORMATION_REQUEST")
    next_move = {
        "action": _plain(conclusion.get("next_action") or "Request the next cheap diligence document."),
        "spend_class": spend,
        "questions": _copy_ready_questions(conclusion, change),
        "conditional": _plain(
            (conclusion.get("what_would_change_view") or [None])[0]
            or "A verified answer or document would refine the controlling constraint."
        ),
        "copy_and_send": _copy_and_send(conclusion),
    }

    source_families = []
    packet = run.get("packet") if isinstance(run.get("packet"), Mapping) else {}
    notes = packet.get("source_notes") if isinstance(packet.get("source_notes"), list) else []
    for row in notes[:4]:
        if isinstance(row, Mapping):
            family = row.get("family") or row.get("source_family") or row.get("label")
            if family:
                source_families.append(_plain(family))
    if not source_families:
        source_families = ["Federal parcel-clipped adapters", "Mireye parcel entry"]

    footer = {
        "parcel_confirmed": bool(run.get("parcel_geometry_confirmed")),
        "mireye_role": "parcel entry / context only - not parcel-wide proof",
        "source_families": source_families[:3],
        "run_id": str(run.get("run_id") or ""),
        "geometry_hash": str(run.get("geometry_hash") or deal.get("geometry_hash") or ""),
        "operating_profile_hash": str(
            run.get("operating_profile_hash")
            or (profile or {}).get("profile_hash")
            or conclusion.get("operating_profile_hash")
            or ""
        ),
        "packet_hash": str(run.get("packet_hash") or ""),
        "deal_context_version": context_version,
        "intended_use": str(deal.get("operation_type") or "UNKNOWN"),
        "conclusion_source": str(conclusion.get("source") or "DETERMINISTIC_FALLBACK"),
        "validation_status": str(conclusion.get("validation_status") or "PASSED"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "boundary": (
            "No stocking-rate, legal-access, or water-right conclusion. "
            "Mapped hydrography is not usable livestock water."
        ),
    }

    source_labels = {
        "NOAA_NCEI_DIRECT_CLIMATE_NORMALS_NETCDF": "NOAA climate normals",
        "USGS_3DEP_1_3_ARC_SECOND_SEAMLESS_DEM": "USGS 3DEP terrain",
        "CONFIRMED_GEOMETRY": "Confirmed parcel geometry",
        "USDA_ARS_RAP_V3": "USDA ARS Rangeland Analysis Platform",
        "US_CENSUS_TIGER_LINE_2025_ALL_ROADS": "U.S. Census TIGER/Line roads",
        "USGS_NHDPLUS_HR": "USGS NHDPlus HR hydrography",
    }
    unit_labels = {
        "mm/year": "mm/year",
        "degree": "degrees",
        "m2": "m2",
        "pound_per_acre": "lb/acre",
        "m": "m",
    }
    evidence_rows: list[dict[str, str]] = []
    observations = packet.get("observations") if isinstance(packet.get("observations"), list) else []
    from rangematch.advisor_property_context_appendix import (
        is_appendix_only_observation,
        project_additional_property_context,
    )

    for observation in observations:
        if not isinstance(observation, Mapping):
            continue
        # HUMAN_ACCESS_INFRA_APPENDIX_ONLY: keep these out of environmental evidence.
        if is_appendix_only_observation(observation):
            continue
        state = str(observation.get("evidence_state") or "").upper()
        value = observation.get("display_value")
        if value in (None, ""):
            value = observation.get("value")
        if value in (None, "") or state in {"SOURCE_UNAVAILABLE", "FAILED", "NOT_AVAILABLE"}:
            continue
        if isinstance(value, float):
            formatted_value = f"{value:,.2f}".rstrip("0").rstrip(".")
        elif isinstance(value, int):
            formatted_value = f"{value:,}"
        else:
            formatted_value = _plain(value)
        unit = unit_labels.get(str(observation.get("unit") or ""), _plain(observation.get("unit") or ""))
        result = f"{formatted_value} {unit}".strip()
        period = _plain(observation.get("time_period") or "")
        if period:
            result = f"{result} ({period.replace('_', ' ')})"
        evidence_rows.append(
            {
                "evidence": _plain(observation.get("label") or "Retrieved evidence"),
                "result": result,
                "status": state.replace("_", " ").title(),
                "source": source_labels.get(
                    str(observation.get("source_id") or ""),
                    _plain(observation.get("source_id") or "Source recorded"),
                ),
            }
        )

    property_context = project_additional_property_context(packet)

    address = _plain(run.get("address") or (packet.get("parcel") or {}).get("display_label") or "Confirmed parcel")
    view = {
        "schema_version": SNAPSHOT_SCHEMA,
        "title": "RangeMatch Cattle Operating Snapshot",
        "address": address,
        "headline": headline,
        "summary": summary,
        "primary_constraint": _plain(conclusion.get("primary_constraint") or ""),
        "status": str(conclusion.get("status") or "CONDITIONAL"),
        "confidence": str(conclusion.get("confidence") or "LOW"),
        "why": [
            {"domain": "Feed", "reading": feed_reading, "basis": feed_basis},
            {"domain": "Drink", "reading": drink_reading, "basis": drink_basis},
            {"domain": "Movement", "reading": move_reading, "basis": move_basis},
        ],
        "what_changed": what_changed,
        "next_move": next_move,
        "narrative": narrative,
        "narrative_source": narrative_result.get("source"),
        "appendix": {
            "title": "Appendix - Evidence Retrieved",
            "subtitle": "Natural evidence and additional property context",
            "rows": evidence_rows,
            "additional_property_context": property_context,
        },
        "page1_property_context_pointer": (
            property_context.get("page1_pointer")
            if property_context.get("enabled")
            else None
        ),
        "footer": footer,
    }
    violations = validate_snapshot_view(view)
    if violations:
        raise SnapshotError("SNAPSHOT_VIEW_INVALID", violations[0]["message"])
    return view


def validate_snapshot_view(view: Mapping[str, Any]) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    body_parts = [
        str(view.get("headline") or ""),
        str(view.get("summary") or ""),
        str(view.get("primary_constraint") or ""),
    ]
    narrative = view.get("narrative") or {}
    if isinstance(narrative, Mapping):
        body_parts.extend(str(narrative.get(field) or "") for field in NARRATIVE_FIELDS)
    changed = view.get("what_changed") or {}
    if isinstance(changed, Mapping):
        body_parts.extend(
            [
                str(changed.get("agent_asked") or ""),
                str(changed.get("buyer_answered") or ""),
                str(changed.get("update_summary") or ""),
            ]
        )
    nxt = view.get("next_move") or {}
    if isinstance(nxt, Mapping):
        body_parts.append(str(nxt.get("action") or ""))
        body_parts.append(str(nxt.get("conditional") or ""))
        body_parts.append(str(nxt.get("copy_and_send") or ""))
        body_parts.extend([str(q) for q in (nxt.get("questions") or [])])

    body_text = " ".join(body_parts)
    # Legacy projection fields remain validated separately. The rendered
    # narrative has its own larger one-page budget.
    legacy_text = " ".join(body_parts[:3])
    if _words(legacy_text) > MAX_BODY_WORDS:
        violations.append(
            {
                "code": "SNAPSHOT_WORD_BUDGET",
                "message": f"body exceeds {MAX_BODY_WORDS} words",
            }
        )
    if _words(str(view.get("summary") or "")) > MAX_SUMMARY_WORDS:
        violations.append({"code": "SNAPSHOT_SUMMARY_WORDS", "message": "summary too long"})
    if _words(str(view.get("headline") or "")) > MAX_HEADLINE_WORDS:
        violations.append({"code": "SNAPSHOT_HEADLINE_WORDS", "message": "headline too long"})

    footer = view.get("footer") or {}
    footer_prose = " ".join(
        [
            str(footer.get("mireye_role") or ""),
            " ".join(footer.get("source_families") or []),
            str(footer.get("boundary") or ""),
        ]
    )
    if _words(footer_prose) > MAX_FOOTER_WORDS:
        violations.append({"code": "SNAPSHOT_FOOTER_WORDS", "message": "footer prose too long"})

    # Buyer prose must not leak internal IDs; hashes live only in footer metadata.
    prose_for_leak = body_text
    hit = INTERNAL_LEAK.search(prose_for_leak)
    if hit:
        violations.append({"code": "SNAPSHOT_INTERNAL_LEAK", "message": hit.group(0)})

    from rangematch.advisor_property_context_appendix import (
        validate_property_context_against_primary,
    )

    appendix = view.get("appendix") if isinstance(view.get("appendix"), Mapping) else {}
    property_context = (
        appendix.get("additional_property_context")
        if isinstance(appendix, Mapping)
        else None
    )
    violations.extend(
        validate_property_context_against_primary(
            property_context=property_context if isinstance(property_context, Mapping) else None,
            primary_prose=body_text,
        )
    )
    return violations


def render_cattle_operating_snapshot_pdf(view: Mapping[str, Any]) -> bytes:
    """Render a two-page US Letter report: advisor view plus evidence appendix."""
    try:
        from fpdf import FPDF
    except ModuleNotFoundError as exc:
        raise RuntimeError("DEPENDENCY_MISSING:fpdf2") from exc

    violations = validate_snapshot_view(view)
    if violations:
        raise SnapshotError("SNAPSHOT_VIEW_INVALID", violations[0]["message"])

    pdf = FPDF(format="Letter", unit="mm")
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(14, 12, 14)
    ink = (25, 37, 29)
    forest = (24, 74, 48)
    gray = (96, 109, 100)
    line = (207, 217, 208)
    pale = (232, 239, 231)

    pdf.add_page()
    page_bottom = 272.0
    y = 12.0

    def write(text: Any, *, size: float = 9, style: str = "", leading: float = 4.2,
              color: tuple[int, int, int] = ink, width: float = 182.0,
              align: str = "L") -> None:
        nonlocal y
        pdf.set_xy(14, y)
        pdf.set_font("Helvetica", style, size)
        pdf.set_text_color(*color)
        before = pdf.get_y()
        pdf.multi_cell(width, leading, _plain(text), border=0, align=align)
        y = pdf.get_y() + 0.6
        if y > page_bottom:
            raise SnapshotError(
                "SNAPSHOT_PAGE_OVERFLOW",
                f"content overflow at y={y:.1f}mm (started {before:.1f})",
            )

    def rule() -> None:
        nonlocal y
        pdf.set_draw_color(*line)
        pdf.line(14, y, 196, y)
        y += 2.2

    def section_gap(amount: float = 3.4) -> None:
        nonlocal y
        y += amount
        if y > page_bottom:
            raise SnapshotError(
                "SNAPSHOT_PAGE_OVERFLOW",
                f"content overflow at y={y:.1f}mm",
            )

    # Brand bar
    pdf.set_fill_color(*forest)
    pdf.rect(0, 0, 216, 3, style="F")
    write("RANGEMATCH", size=10, style="B", color=forest, leading=4.4, align="C")
    write(
        str(view.get("title") or "Cattle Operating Snapshot"),
        size=23,
        style="B",
        leading=9.2,
        align="C",
    )
    write(str(view.get("address") or ""), size=11.5, color=gray, leading=5.0, align="C")
    y += 1.0
    rule()

    narrative = view.get("narrative") or {}
    write("Bottom line", size=14, style="B", color=forest, leading=5.8)
    write(str(narrative.get("bottom_line") or view.get("summary") or ""), size=10.2, leading=4.55)
    section_gap()

    write("What your answer changed", size=14, style="B", color=forest, leading=5.8)
    write(str(narrative.get("what_changed") or ""), size=10.2, leading=4.55)
    section_gap()

    write("How the ranch currently reads", size=14, style="B", color=forest, leading=5.8)
    write(str(narrative.get("ranch_reading") or ""), size=10.2, leading=4.55)
    section_gap()

    write("What I would do next", size=14, style="B", color=forest, leading=5.8)
    write(str(narrative.get("next_steps") or ""), size=10.2, leading=4.55)
    section_gap()

    write("Copy and send", size=14, style="B", color=forest, leading=5.8)
    pdf.set_fill_color(*pale)
    pdf.rect(14, y, 182, 5.4, style="F")
    write(str(narrative.get("copy_and_send") or ""), size=10.2, leading=4.55)
    section_gap(3.0)

    footer = view.get("footer") or {}
    confirmed = "confirmed" if footer.get("parcel_confirmed") else "not confirmed"
    raw_use = str(footer.get("intended_use") or "UNKNOWN").upper()
    use_label = {
        "SEASONAL_GRAZING": "seasonal use",
        "YEAR_ROUND_COW_CALF": "year-round cow-calf use",
    }.get(raw_use, raw_use.replace("_", " ").lower())
    use_phrase = (
        f"together with the intended {use_label}"
        if use_label != "unknown"
        else "together with the buyer information currently available"
    )
    write(
        f"Preliminary cattle-operating interpretation based on the {confirmed} parcel, "
        "public terrain, vegetation, climate, road and available hydrography evidence, "
        f"{use_phrase}.",
        size=8.6,
        color=gray,
        leading=3.8,
    )
    write(
        "Not a stocking-rate, title or water-right opinion.",
        size=8.3,
        color=gray,
        leading=3.7,
    )
    pointer = view.get("page1_property_context_pointer")
    if pointer:
        write(str(pointer), size=8.3, color=gray, leading=3.7)

    # Page 2: evidence appendix. Empty/unavailable observations are intentionally omitted.
    pdf.add_page()
    y = 12.0
    pdf.set_fill_color(*forest)
    pdf.rect(0, 0, 216, 3, style="F")
    write("RANGEMATCH", size=10, style="B", color=forest, leading=4.4, align="C")
    write("Appendix", size=23, style="B", leading=9.2, align="C")
    appendix = view.get("appendix") if isinstance(view.get("appendix"), Mapping) else {}
    write(
        str(appendix.get("subtitle") or "Evidence retrieved for this confirmed parcel"),
        size=11.5,
        color=gray,
        leading=5.0,
        align="C",
    )
    y += 2.0

    rows = appendix.get("rows") if isinstance(appendix.get("rows"), list) else []
    columns = [
        ("Evidence", 48.0),
        ("Result", 42.0),
        ("Evidence status", 34.0),
        ("Source", 58.0),
    ]

    def wrap_cell(text: Any, width: float, *, size: float = 9.2, style: str = "") -> list[str]:
        pdf.set_font("Helvetica", style, size)
        words = _plain(text).split()
        if not words:
            return [""]
        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if pdf.get_string_width(candidate) <= width - 4.0:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    write("Environmental Evidence Retrieved", size=12, style="B", color=forest, leading=5.2)
    y += 0.6

    x = 14.0
    header_height = 9.0
    pdf.set_fill_color(*forest)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9.2)
    for label, width in columns:
        pdf.rect(x, y, width, header_height, style="F")
        pdf.set_xy(x + 2.0, y + 2.2)
        pdf.cell(width - 4.0, 4.2, label)
        x += width
    y += header_height

    for index, row in enumerate(rows):
        values = [row.get("evidence"), row.get("result"), row.get("status"), row.get("source")]
        wrapped = [wrap_cell(value, width) for value, (_, width) in zip(values, columns)]
        row_height = max(12.0, max(len(lines) for lines in wrapped) * 4.3 + 4.0)
        if y + row_height > page_bottom - 12.0:
            raise SnapshotError("SNAPSHOT_APPENDIX_OVERFLOW", "evidence table exceeds appendix page")
        x = 14.0
        if index % 2 == 0:
            pdf.set_fill_color(244, 247, 243)
            pdf.rect(x, y, 182.0, row_height, style="F")
        pdf.set_draw_color(*line)
        for lines, (_, width) in zip(wrapped, columns):
            pdf.rect(x, y, width, row_height)
            pdf.set_text_color(*ink)
            pdf.set_font("Helvetica", "", 9.2)
            line_y = y + 3.0
            for line_text in lines:
                pdf.set_xy(x + 2.0, line_y)
                pdf.cell(width - 4.0, 4.2, line_text)
                line_y += 4.3
            x += width
        y += row_height

    y += 4.0
    write(
        "Only evidence with a retrieved, non-empty value is shown. Missing, failed or unavailable fields are omitted rather than displayed as empty rows.",
        size=8.6,
        color=gray,
        leading=3.9,
    )

    property_context = (
        appendix.get("additional_property_context")
        if isinstance(appendix.get("additional_property_context"), Mapping)
        else {}
    )
    if property_context.get("enabled") and isinstance(property_context.get("rows"), list):
        section_gap(2.5)
        write(
            str(property_context.get("title") or "Additional Property Context"),
            size=12,
            style="B",
            color=forest,
            leading=5.2,
        )
        write(
            "Already-retrieved mapped property context. It does not affect the natural-foundation judgment.",
            size=8.6,
            color=gray,
            leading=3.9,
        )
        y += 1.0
        ctx_columns = [
            ("Topic", 32.0),
            ("What we can say", 50.0),
            ("How to read it", 50.0),
            ("What it does not establish", 50.0),
        ]
        x = 14.0
        pdf.set_fill_color(*forest)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 8.4)
        for label, width in ctx_columns:
            pdf.rect(x, y, width, header_height, style="F")
            pdf.set_xy(x + 1.5, y + 2.2)
            pdf.cell(width - 3.0, 4.0, label)
            x += width
        y += header_height

        for index, row in enumerate(property_context.get("rows") or []):
            if not isinstance(row, Mapping):
                continue
            values = [
                row.get("topic"),
                row.get("what_we_can_say"),
                row.get("how_to_read_it"),
                row.get("what_it_does_not_establish"),
            ]
            wrapped = [
                wrap_cell(value, width, size=8.2) for value, (_, width) in zip(values, ctx_columns)
            ]
            row_height = max(14.0, max(len(lines) for lines in wrapped) * 3.9 + 4.0)
            if y + row_height > page_bottom - 8.0:
                raise SnapshotError(
                    "SNAPSHOT_APPENDIX_OVERFLOW",
                    "additional property context exceeds appendix page",
                )
            x = 14.0
            if index % 2 == 0:
                pdf.set_fill_color(244, 247, 243)
                pdf.rect(x, y, 182.0, row_height, style="F")
            pdf.set_draw_color(*line)
            for lines, (_, width) in zip(wrapped, ctx_columns):
                pdf.rect(x, y, width, row_height)
                pdf.set_text_color(*ink)
                pdf.set_font("Helvetica", "", 8.2)
                line_y = y + 2.6
                for line_text in lines:
                    pdf.set_xy(x + 1.5, line_y)
                    pdf.cell(width - 3.0, 3.8, line_text)
                    line_y += 3.9
                x += width
            y += row_height

    y += 4.0
    write(
        "These measurements describe the parcel evidence available to this review; they are not a stocking-rate, title, water-right or purchase opinion.",
        size=8.6,
        color=gray,
        leading=3.9,
    )

    if pdf.page_no() != 2:
        raise SnapshotError(
            "SNAPSHOT_PAGE_COUNT",
            f"expected exactly 2 pages, got {pdf.page_no()}",
        )

    buffer = BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()
