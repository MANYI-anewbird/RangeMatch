"""Render the six-section buyer report from validated insight fields."""

from __future__ import annotations

import re
from typing import Any, Mapping

from rangematch.advisor_brief import MESSAGE_BODIES

REPORT_SCHEMA = "RANGEMATCH_ADVISOR_BUYER_REPORT@0.1.0"
COPY_INTERNAL_ID = re.compile(
    r"\b(?:ACTION|OBS|BOTTLENECK|CLAIM|VAR_F|INSIGHT)_[A-Z0-9_]+\b"
)


def validate_buyer_copy_quality(report: Mapping[str, Any]) -> list[dict[str, str]]:
    """Reject structurally valid prose that still reads like internal model output."""
    sections = report.get("sections") or {}
    violations: list[dict[str, str]] = []
    recommendation = str(sections.get("recommendation") or "").strip()
    why = str(sections.get("why") or "").strip()
    all_copy = " ".join(str(value or "") for value in sections.values())
    if recommendation and recommendation.rstrip(".!").lower() in why.lower():
        violations.append(
            {
                "code": "BUYER_COPY_REPEATS_RECOMMENDATION",
                "message": "why repeats the recommendation instead of explaining it",
            }
        )
    if "not first:" in all_copy.lower():
        violations.append(
            {
                "code": "BUYER_COPY_INTERNAL_REASONING_LABEL",
                "message": "buyer copy exposes the internal 'Not first' comparison label",
            }
        )
    leaked = COPY_INTERNAL_ID.search(all_copy)
    if leaked:
        violations.append(
            {
                "code": "BUYER_COPY_INTERNAL_ID",
                "message": leaked.group(0),
            }
        )
    if why and why[-1] not in ".!?":
        violations.append(
            {
                "code": "BUYER_COPY_INCOMPLETE_SENTENCE",
                "message": "why must end as a complete sentence",
            }
        )
    return violations


def render_buyer_report(
    insights: list[dict[str, Any]],
    workbench: dict[str, Any],
    packet: dict[str, Any],
    *,
    source: str,
    provenance: dict[str, Any],
    violations: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    info = next(
        (row for row in insights if row.get("reasoning_type") == "INFORMATION_VALUE"),
        None,
    )
    leaps = [
        row
        for row in insights
        if row.get("reasoning_type") == "SUPPORTED_INTERPRETATION"
    ]
    priors = [
        row
        for row in insights
        if row.get("reasoning_type") in {"DOMAIN_PRIOR", "DILIGENCE_QUESTION"}
    ]
    first_action = (workbench.get("execution_order") or ["ACTION_ACCESS_DOCUMENTS"])[0]
    recommendation = str((info or {}).get("recommendation") or "").strip()
    if not recommendation:
        recommendation = "Request access documents before booking the trip."
    why = _why(info, workbench)
    listing = _listing_jumps(leaps, packet)
    do_now = _do_now(packet, info)
    if_changes = _if_changes(info)
    reminders = _reminders(priors)
    return {
        "schema_version": REPORT_SCHEMA,
        "packet_hash": workbench.get("packet_hash"),
        "validation_status": "FAILED" if violations else "PASSED",
        "source": source,
        "sections": {
            "recommendation": recommendation[:140],
            "why": why,
            "listing_jumps": listing,
            "do_now": do_now,
            "if_changes": if_changes,
            "professional_reminders": reminders,
        },
        "insight_ids": [str(row.get("insight_id")) for row in insights if row.get("insight_id")],
        "insights": list(insights or []),
        "validation_violations": list(violations or []),
        "provenance": {
            **provenance,
            "knowledge_scope": "DEMO_APPROVED_FOUR_CARDS",
            "fallback_first_action": first_action,
        },
    }


def render_deterministic_buyer_report(
    workbench: dict[str, Any],
    packet: dict[str, Any],
    *,
    provenance: dict[str, Any],
    violations: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return render_buyer_report(
        [],
        workbench,
        packet,
        source="DETERMINISTIC_FALLBACK",
        provenance=provenance,
        violations=violations,
    )


def _why(info: dict[str, Any] | None, workbench: dict[str, Any]) -> str:
    water = next(
        (
            row
            for row in (workbench.get("bottleneck_candidates") or [])
            if row.get("bottleneck_id") == "BOTTLENECK_WATER_EVIDENCE"
        ),
        None,
    )
    title = (water or {}).get("title") or "Livestock water is the larger operating-evidence gap"
    rejected = []
    for row in (info or {}).get("rejected_actions") or []:
        if isinstance(row, Mapping):
            reason = str(row.get("reason") or "").strip()
            if reason:
                rejected.append(reason)
        elif str(row).strip():
            rejected.append(str(row).strip())
    title = title.rstrip(". ") + "."
    if rejected:
        deferred = rejected[0].rstrip(". ")
        return (
            f"{title} Access documents can be reviewed before travel and determine whether "
            f"a visit has a defined job. Defer the competing step for now because {deferred.lower()}."
        )
    return (
        f"{title} Access documents can be reviewed before travel and determine whether "
        "a visit has a defined job."
    )


def _listing_jumps(leaps: list[dict[str, Any]], packet: dict[str, Any]) -> str:
    if leaps:
        return " ".join(str(row.get("recommendation") or "").strip() for row in leaps if row.get("recommendation"))
    gaps = list(packet.get("claim_evidence_gaps") or [])
    if not gaps:
        return (
            "No listing packet was supplied. Public evidence can support slope, rainfall, "
            "a vegetation snapshot, mapped hydrography leads, and road contact. "
            "A legal entrance and operating water still require transaction documents."
        )
    parts = []
    for gap in gaps[:3]:
        claim = gap.get("claim") or gap.get("claim_id")
        support = gap.get("supported_portion") or "current public evidence"
        parts.append(f"“{claim}” goes past {support}.")
    return " ".join(parts)


def _do_now(packet: dict[str, Any], info: dict[str, Any] | None) -> str:
    order = list((info or {}).get("llm_recommended_order") or [])
    first = order[0] if order else None
    specs = list(packet.get("copy_ready_message_specs") or [])
    chosen = next((row for row in specs if row.get("bound_action_id") == first), None)
    if chosen is None and specs:
        chosen = specs[0]
    if chosen is None:
        return "Copy the title/counsel request for access paper."
    body = MESSAGE_BODIES.get(str(chosen.get("template_id") or ""))
    if body:
        return body
    return "Ask title or counsel for the recorded entrance basis before booking travel."


def _if_changes(info: dict[str, Any] | None) -> str:
    cond = ((info or {}).get("conditions") or [None])[0]
    if not cond:
        return (
            "If the entrance basis holds, the next job is a water-focused field walk. "
            "If it does not, pause the trip. Neither result proves year-round drinking water."
        )
    still = ", ".join(cond.get("still_cannot_establish") or []) or "year-round stock water"
    return (
        "If access documentation supports an entrance, schedule a water-focused field visit. "
        f"If it does not, pause the trip. Either way this still cannot establish {still}."
    )


def _reminders(priors: list[dict[str, Any]]) -> str:
    texts = [str(row.get("recommendation") or "").strip() for row in priors if row.get("recommendation")]
    if texts:
        return " ".join(texts)
    return (
        "Mapped water is a lead, not a drinker. RAP is a growth snapshot, not a stocking plan. "
        "Mireye context at the centroid is not a parcel-wide proof."
    )
