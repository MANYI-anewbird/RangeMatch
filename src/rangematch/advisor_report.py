"""Render the six-section buyer report from validated insight fields."""

from __future__ import annotations

from typing import Any

from rangematch.advisor_brief import MESSAGE_BODIES

REPORT_SCHEMA = "RANGEMATCH_ADVISOR_BUYER_REPORT@0.1.0"


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
        "validation_violations": list(violations or []),
        "provenance": {
            **provenance,
            "knowledge_scope": "PROVISIONAL_CPER_TRIAL_THREE_CARDS",
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
    if info and info.get("rejected_actions"):
        return (
            f"{title}. Access paper is usually cheaper than a field trip and decides "
            "whether a visit has a job, so request it first. Repeating the precipitation "
            "lookup would not reduce the current decision uncertainty."
        )
    return (
        f"{title}. Access documents can be requested before travel and decide whether "
        "a weekend visit has a defined job."
    )


def _listing_jumps(leaps: list[dict[str, Any]], packet: dict[str, Any]) -> str:
    if leaps:
        return " ".join(str(row.get("recommendation") or "").strip() for row in leaps if row.get("recommendation"))
    gaps = list(packet.get("claim_evidence_gaps") or [])
    if not gaps:
        return "No listing claims were supplied. Read the public evidence, not a brochure."
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
