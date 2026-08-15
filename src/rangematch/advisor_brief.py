"""Deterministic three-page Advisor Brief. No LLM. Page 3 is real kitchen content."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from rangematch.advisor_contract import (
    REPO_ROOT,
    has_drawable_geometry,
    land_fact_index,
    packet_hash,
    validate_packet,
)
from rangematch.advisor_visit import (
    derive_authoritative_visit_purpose,
    field_drawable_objects,
)

BRIEF_SCHEMA = "RANGEMATCH_ADVISOR_THREE_PAGE@0.1.0"

CLAIM_OUTRUN_LINES = {
    "CLAIM_WATER_001": (
        "“Excellent year-round water” goes past mapped hydrography. "
        "The map is a lead, not a drinker."
    ),
    "CLAIM_ACCESS_001": (
        "“Easy county-road access” goes past physical road contact. "
        "Contact is not a recorded entrance."
    ),
    "CLAIM_FORAGE_001": (
        "“Productive pasture ready for cattle” goes past a modeled growth snapshot. "
        "That snapshot is not a stocking plan."
    ),
}

MESSAGE_BODIES = {
    "ASK_WATER_TYPE_LOCATION_RECORDS": (
        "The listing’s “excellent year-round water” — is that a well, a tank, a pond, "
        "or a seasonal channel? Please send the location and any well log, pump record, "
        "water-quality, or maintenance material you have."
    ),
    "ASK_RECORDED_ENTRANCE": (
        "Please confirm whether the mapped road contact is a recorded legal entrance, "
        "and whether title, easements, or exceptions support or limit access at that location."
    ),
    "REVIEW_MAPPED_WATER_AREAS": (
        "Review the mapped water feature areas on the report map — reaches and ponds, "
        "not invented pins. Record the date, visible water, livestock access, fence, pipe, "
        "tank, or pump signs. This visit cannot confirm year-round flow, water quality, "
        "or the legal right to use the water."
    ),
    "WAIT_FOR_ACCESS_PAPER_BEFORE_FLIGHT": (
        "We are not deciding to abandon this tract. The listing’s access and drinking-water "
        "lines still lack supporting materials. We will get the access paper first, then "
        "decide whether a site visit is worth the time and airfare."
    ),
    "WAIT_FOR_ACCESS_PAPER_PUBLIC_EVIDENCE": (
        "We are not deciding to abandon this tract. Public maps show road contact and "
        "hydrography leads, but they do not prove a recorded entrance or usable drinking "
        "water. Get the access paper first, then decide whether a site visit is worth the trip."
    ),
    "ASK_SELLER_DEVELOPED_WATER": (
        "Does anyone claim a developed livestock-water source on this tract — a well, tank, "
        "pond, or similar — and if so, where is it and what records exist? A mapped-hydrography "
        "search returning no leads is not an absence finding on the ground."
    ),
    "ASK_FOR_WATER_LOCATION_OR_INVENTORY": (
        "We have mapped hydrography identities, but no drawable location yet. Please send a "
        "usable location or help us build a field inventory. Do not treat a catalog identity "
        "as a pin or as a drinker."
    ),
    "F03_INVENTORY_UNAVAILABLE": (
        "The mapped-water inventory is currently unavailable. That is not an absence finding. "
        "Please say whether any developed source is claimed, and send location and records if it is."
    ),
    "CONFIRM_PARCEL_BEFORE_DILIGENCE": (
        "Please confirm the working parcel outline before we spend on access paper, a water "
        "walk, or a flight. Other diligence waits on that confirmation."
    ),
    "TITLE_REVIEW_ALREADY_ACTIVE": (
        "Title or counsel is already reviewing the entrance question. Do not send a second "
        "copy of the same access request. Use that cycle; the next new spend is water evidence."
    ),
    "INTERPRET_RAP_NOT_STOCKING": (
        "The modeled vegetation / RAP production figure is a snapshot only. Do not treat it as "
        "available forage or a herd-size plan."
    ),
}


def _load_unified_output(
    packet: dict[str, Any], *, repo_root: Path | None = None
) -> dict[str, Any] | None:
    ref = (packet.get("technical_references") or {}).get("unified_output")
    if not ref:
        return None
    path = Path(ref)
    if not path.is_absolute():
        path = (repo_root or REPO_ROOT) / ref
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _obs_map(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["observation_id"]): row
        for row in (packet.get("observations") or [])
        if row.get("observation_id")
    }


def _obs_has_value(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    if row.get("evidence_state") == "SOURCE_UNAVAILABLE":
        return False
    return row.get("value") is not None


def _page_one(packet: dict[str, Any]) -> dict[str, Any]:
    obs = _obs_map(packet)
    objects = list(packet.get("candidate_objects") or [])
    drawable = field_drawable_objects(objects)
    f03_status = (packet.get("technical_references") or {}).get("f03_status")
    water = obs.get("OBS_WATER_COUNT") or {}
    if f03_status == "FAILED" or water.get("evidence_state") == "SOURCE_UNAVAILABLE":
        water_clause = (
            "mapped-water inventory is currently unavailable — that is not proof the ground has none"
        )
    elif objects and not drawable:
        water_clause = (
            f"{len(objects)} mapped water identities exist, but none can be placed on a map yet"
        )
    elif drawable:
        water_clause = (
            f"{len(objects)} mapped water identities, {len(drawable)} of which can be reviewed as map areas"
        )
    elif water.get("value") == 0:
        water_clause = (
            "the mapped-hydrography search returned no leads — that is not proof the ground has none"
        )
    else:
        water_clause = "mapped-water evidence still needs a next ask"
    slope_ok = _obs_has_value(obs.get("OBS_SLOPE"))
    precip_ok = _obs_has_value(obs.get("OBS_PRECIP"))
    rap_ok = _obs_has_value(obs.get("OBS_RAP_PROD"))
    road_ok = _obs_has_value(obs.get("OBS_ROAD"))
    if slope_ok and precip_ok and rap_ok and road_ok:
        tract = (
            "This tract already has a usable public-data portrait: gentle typical slope, "
            f"measured rainfall, a recent vegetation snapshot, {water_clause}, "
            "and a road that meets the boundary. The useful question is whether drinking water "
            "and a legal entrance can be established, not whether the public maps look complete."
        )
    else:
        portrait = [
            "slope is on file" if slope_ok else "slope is not yet available",
            "rainfall is measured" if precip_ok else "rainfall is not yet available",
            "a vegetation snapshot is on file" if rap_ok else "no vegetation snapshot yet",
            "a mapped-road distance is on file" if road_ok else "no mapped-road distance yet",
        ]
        tract = (
            "This tract has a confirmed outline. "
            f"{'; '.join(portrait)}. Water: {water_clause}. "
            "The useful question is whether drinking water and a legal entrance can be "
            "established, not whether missing public layers can be invented."
        )
    gaps = list(packet.get("claim_evidence_gaps") or [])
    outruns: list[str] = []
    if not gaps and not packet.get("listing_claims"):
        outruns = []
    for gap in gaps[:3]:
        claim_id = str(gap.get("claim_id") or "")
        if claim_id in CLAIM_OUTRUN_LINES:
            outruns.append(CLAIM_OUTRUN_LINES[claim_id])
            continue
        claim = str(gap.get("claim") or "This listing line")
        supported = str(gap.get("supported_portion") or "available public evidence")
        unsupported = list(gap.get("unsupported_portion") or [])
        first = unsupported[0] if unsupported else "the listed conclusion"
        outruns.append(f"“{claim}” goes past {supported}. That does not prove {first}.")

    actions = sorted(
        packet.get("actions") or [], key=lambda row: int(row.get("execution_order") or 0)
    )
    do_today: list[str] = []
    today_copy = {
        "ACTION_ACCESS_DOCUMENTS": (
            "Ask title or the listing side for the access paper: deed, easement, or recorded entrance."
        ),
        "ACTION_WATER_FIELD_CATEGORY": (
            "Ask what “excellent water” refers to — well, tank, pond, or seasonal channel — "
            "and for any records they have."
            if packet.get("listing_claims")
            else "If a developed water source is in play, ask for its type, location, and records."
        ),
        "ACTION_ASK_SELLER_WATER": (
            "Ask whether anyone claims a developed water source — well, tank, or pond — and for location and records."
        ),
        "ACTION_WATER_LOCATION_OR_INVENTORY": (
            "Ask for a usable water location or build a field inventory; mapped identities cannot be drawn yet."
        ),
        "ACTION_WATER_SOURCE_UNAVAILABLE": (
            "Treat mapped-water inventory as unavailable and ask whether a developed source is claimed."
        ),
        "ACTION_CONFIRM_PARCEL": (
            "Confirm the parcel outline before spending on documents or a visit."
        ),
        "ACTION_INTERPRET_RAP_FORAGE": (
            "Treat modeled RAP / herbaceous production as a snapshot only — not a herd-size plan."
        ),
    }
    for action in actions[:2]:
        line = today_copy.get(str(action.get("action_id"))) or str(action.get("why_now") or "").strip()
        if line:
            do_today.append(line)
        if len(do_today) == 2:
            break

    action_ids = {row.get("action_id") for row in actions}
    stage = str((packet.get("decision_context") or {}).get("current_stage") or "")
    visit = derive_authoritative_visit_purpose(packet)
    visit_purpose = visit["visit_state"]
    if "ACTION_CONFIRM_PARCEL" in action_ids:
        visit_guidance = (
            "Do not fly or start field work on an unconfirmed outline. Confirm the parcel first."
        )
        what_changes = (
            "Once the outline is confirmed, reopen access paper and water evidence. "
            "Do not convert the RAP number into a herd size."
        )
    elif stage in {"FIELD_VISIT_ALREADY_BOOKED", "FIELD_FOLLOW_UP"} and drawable:
        visit_guidance = (
            "The visit is already booked and has a defined purpose: inspect mapped water areas "
            "and any seller-named supply. This walk cannot prove year-round use or legal right."
        )
        what_changes = (
            "Record what is visible on the visit date. Keep title review on a separate track. "
            "Do not convert the RAP number into a herd size."
        )
    elif "ACTION_ACCESS_DOCUMENTS" in action_ids:
        visit_guidance = (
            "The trip depends on access documentation. If the entrance basis holds, the visit "
            "has a defined purpose: inspect mapped water areas and any seller-claimed infrastructure."
        )
        what_changes = (
            "If the access paper holds, the next spend is the water walk. If the seller cannot "
            "show an entrance basis, pause the trip and give title the question. Either way, "
            "do not convert the RAP number into a herd size."
        )
    elif drawable:
        visit_guidance = (
            "A visit has a defined purpose: inspect mapped water areas and any seller-named supply. "
            "Do not treat map areas as drinkers or pins."
        )
        what_changes = (
            "Complete the water walk and keep listing claims from becoming operating facts. "
            "Do not convert the RAP number into a herd size."
        )
    else:
        visit_guidance = (
            "Do not fly to look for water that the map cannot yet place. Get a location, a "
            "seller-claimed source, or a confirmed entrance first."
        )
        what_changes = (
            "Next spend is the missing location or access paper, not a search for absence. "
            "Do not convert the RAP number into a herd size."
        )
    return {
        "how_the_tract_reads": tract,
        "listing_outruns_evidence": outruns,
        "do_today": do_today[:2],
        "visit_purpose": visit_purpose,
        "visit_guidance": visit_guidance,
        "what_changes_next": what_changes,
        "what_not_to_recheck": [
            (
                "Do not pay for another annual-precipitation lookup. That number is already measured."
                if precip_ok
                else (
                    "Do not invent a precipitation number. The climate lookup is not "
                    "available on this run."
                )
            )
        ],
    }


def _page_two(packet: dict[str, Any]) -> dict[str, Any]:
    has_listing = bool(packet.get("listing_claims") or packet.get("claim_evidence_gaps"))
    messages = []
    for spec in packet.get("copy_ready_message_specs") or []:
        template_id = str(spec.get("template_id") or "")
        body = MESSAGE_BODIES.get(template_id)
        if body is None:
            action = next(
                (
                    row
                    for row in (packet.get("actions") or [])
                    if row.get("action_id") == spec.get("bound_action_id")
                ),
                {},
            )
            can_do = "; ".join(action.get("can_establish") or []) or "the requested record"
            cannot = "; ".join(action.get("cannot_establish") or []) or "legal or year-round conclusions"
            body = (
                f"Please help with this diligence step: {can_do}. "
                f"This request cannot establish {cannot}."
            )
        messages.append(
            {
                "message_id": spec.get("message_id"),
                "audience": spec.get("audience"),
                "bound_action_id": spec.get("bound_action_id"),
                "bound_claim_id": spec.get("bound_claim_id"),
                "body": body,
            }
        )
    return {
        "page_mode": "LISTING_CLAIMS" if has_listing else "PUBLIC_EVIDENCE",
        "headline": (
            "What the listing language actually has behind it"
            if has_listing
            else "What public evidence supports — and what still requires transaction documents"
        ),
        "messages": messages,
    }


def _map_layer(obj: dict[str, Any]) -> dict[str, Any]:
    geometry = obj.get("geometry") or {}
    return {
        "layer_id": obj.get("candidate_id"),
        "candidate_type": obj.get("candidate_type"),
        "display_name": obj.get("display_name"),
        "kind": geometry.get("kind"),
        "bbox": list(geometry.get("bbox") or []),
        "centroid": geometry.get("centroid"),
        "field_navigation_precision": geometry.get("field_navigation_precision"),
        "review_status": obj.get("review_status"),
        "evidence_state": obj.get("evidence_state"),
    }


def _kitchen_observation(
    obs: dict[str, Any], fact: dict[str, Any] | None
) -> dict[str, Any]:
    fact = fact or {}
    return {
        "observation_id": obs.get("observation_id"),
        "label": obs.get("label"),
        "land_fact_ref": obs.get("land_fact_ref"),
        "value": obs.get("value"),
        "display_value": obs.get("display_value"),
        "unit": obs.get("unit"),
        "time_period": obs.get("time_period"),
        "evidence_state": obs.get("evidence_state"),
        "spatial_meaning": obs.get("spatial_meaning"),
        "source_id": obs.get("source_id"),
        "source_version": fact.get("source_version"),
        "geometry_hash": fact.get("geometry_hash"),
        "coverage": fact.get("coverage"),
        "applicability_status": fact.get("applicability_status"),
        "confidence_or_quality_status": fact.get("confidence_or_quality_status"),
        "limitations": list(fact.get("limitations") or []),
        "derivation_algorithm_version": fact.get("derivation_algorithm_version"),
        "allowed_support": list(obs.get("allowed_support") or []),
        "prohibited_support": list(obs.get("prohibited_support") or []),
    }


def _mireye_provenance(mireye_live: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    live = dict(mireye_live or {})
    rows: list[dict[str, Any]] = []
    lookup = live.get("lookup") or {}
    if lookup:
        rows.append(
            {
                "source_id": "MIREYE_LOOKUP",
                "role": "PARCEL_ENTRY",
                "ok": bool(lookup.get("ok")),
                "canonical_for_parcel_facts": False,
                "spatial_meaning": "address_or_location_recognition",
            }
        )
    labels = {
        "PROPERTY_DILIGENCE_CONTEXT": "property_context",
        "POINT_LAND_CONTEXT": "centroid_land_context",
        "POINT_HAZARD_CONTEXT": "centroid_hazard_context",
    }
    for key, meaning in labels.items():
        row = (live.get("contexts") or {}).get(key)
        if row is None:
            continue
        rows.append(
            {
                "source_id": f"MIREYE_{key}",
                "role": "CONTEXT_ONLY",
                "ok": (row or {}).get("status") == "SUCCEEDED",
                "canonical_for_parcel_facts": False,
                "spatial_meaning": meaning,
            }
        )
    return rows


def _source_notes(packet: dict[str, Any], facts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for obs in packet.get("observations") or []:
        fact = facts.get(str(obs.get("land_fact_ref") or "")) or {}
        source_id = str(obs.get("source_id") or fact.get("source_id") or "UNSPECIFIED_SOURCE")
        key = f"{source_id}|{obs.get('land_fact_ref')}"
        if key in seen:
            continue
        seen.add(key)
        notes.append(
            {
                "source_id": source_id,
                "source_version": fact.get("source_version"),
                "land_fact_ref": obs.get("land_fact_ref"),
                "time_period": obs.get("time_period") or fact.get("temporal_semantics"),
                "spatial_meaning": obs.get("spatial_meaning") or fact.get("spatial_semantics"),
            }
        )
    refs = packet.get("technical_references") or {}
    if refs.get("f03_candidate_inventory"):
        notes.append(
            {
                "source_id": "USGS_NHDPLUS_HR",
                "source_version": None,
                "land_fact_ref": None,
                "artifact_ref": refs.get("f03_candidate_inventory"),
                "time_period": None,
                "spatial_meaning": "mapped hydrography candidates",
            }
        )
    if refs.get("f03_remote_pilot"):
        notes.append(
            {
                "source_id": "F03_REMOTE_PILOT",
                "source_version": None,
                "land_fact_ref": None,
                "artifact_ref": refs.get("f03_remote_pilot"),
                "time_period": None,
                "spatial_meaning": "sampled remote review",
            }
        )
    for row in refs.get("mireye_context_refs") or []:
        if not isinstance(row, Mapping):
            continue
        notes.append(
            {
                "source_id": str(row.get("source_id") or "MIREYE_CONTEXT"),
                "source_version": None,
                "land_fact_ref": None,
                "role": row.get("role") or "CONTEXT_ONLY",
                "canonical_for_parcel_facts": False,
                "spatial_meaning": row.get("spatial_meaning") or "mireye_context",
            }
        )
    return notes


def _coverage_and_limitations(
    packet: dict[str, Any], facts: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for obs in packet.get("observations") or []:
        fact = facts.get(str(obs.get("land_fact_ref") or "")) or {}
        coverage = fact.get("coverage") or {}
        rows.append(
            {
                "land_fact_ref": obs.get("land_fact_ref"),
                "coverage_status": coverage.get("normalized_status"),
                "applicability_status": fact.get("applicability_status"),
                "limitations": list(fact.get("limitations") or []),
                "prohibited_support": list(obs.get("prohibited_support") or []),
            }
        )
    for inference in packet.get("prohibited_inferences") or []:
        rows.append(
            {
                "land_fact_ref": None,
                "coverage_status": None,
                "applicability_status": None,
                "limitations": [f"packet prohibits inference: {inference}"],
                "prohibited_support": [inference],
            }
        )
    return rows


def _engine_appendix(
    packet: dict[str, Any], unified_output: dict[str, Any] | None
) -> dict[str, Any]:
    refs = packet.get("technical_references") or {}
    operations = []
    if unified_output:
        for operation_id, row in (unified_output.get("operations") or {}).items():
            if not isinstance(row, dict):
                continue
            operations.append(
                {
                    "operation_id": operation_id,
                    "decision_label": row.get("decision_label"),
                    "decision_reason": row.get("decision_reason"),
                }
            )
    return {
        "engine_ledger_present": bool(unified_output),
        "unified_output_ref": refs.get("unified_output"),
        "hold_confined_to_appendix": True,
        "engine_version": None if not unified_output else unified_output.get("engine_version"),
        "engine_input_hash": None if not unified_output else unified_output.get("engine_input_hash"),
        "match_result_hash": None if not unified_output else unified_output.get("match_result_hash"),
        "explanation_binding_hash": None
        if not unified_output
        else unified_output.get("explanation_binding_hash"),
        "operation_decisions": operations,
        "policy": refs.get("policy"),
        "policy_scope": refs.get("policy_scope"),
        "f03_status": refs.get("f03_status"),
        "drawable_object_count": refs.get("drawable_object_count"),
        "f03_candidate_inventory": refs.get("f03_candidate_inventory"),
        "f03_remote_pilot": refs.get("f03_remote_pilot"),
        "candidate_object_count_in_packet": refs.get("candidate_object_count_in_packet"),
    }


def _page_three(
    packet: dict[str, Any],
    *,
    facts: dict[str, dict[str, Any]],
    unified_output: dict[str, Any] | None,
    packet_violations: list[dict[str, str]],
    bound_hash: str,
    mireye_live: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    parcel = packet.get("parcel") or {}
    objects = list(packet.get("candidate_objects") or [])
    observations = [
        _kitchen_observation(obs, facts.get(str(obs.get("land_fact_ref") or "")))
        for obs in (packet.get("observations") or [])
    ]
    return {
        "parcel_summary": {
            "parcel_id": parcel.get("parcel_id"),
            "geometry_hash": parcel.get("geometry_hash"),
            "confirmation_status": parcel.get("confirmation_status"),
            "display_label": parcel.get("display_label"),
            "is_engineering_test_geometry": parcel.get("is_engineering_test_geometry"),
        },
        "map_layers": [
            _map_layer(obj) for obj in objects if has_drawable_geometry(obj.get("geometry") or {})
        ],
        "observations": observations,
        "candidate_objects": objects,
        "source_notes": _source_notes(packet, facts),
        "mireye_provenance": _mireye_provenance(mireye_live)
        or list((packet.get("technical_references") or {}).get("mireye_context_refs") or []),
        "coverage_and_limitations": _coverage_and_limitations(packet, facts),
        "engine_appendix": _engine_appendix(packet, unified_output),
        "validation_record": {
            "packet_hash": bound_hash,
            "packet_violations": packet_violations,
            "generator": "DETERMINISTIC_TEMPLATE",
            "llm_used": False,
        },
        "hold_confined_to_appendix": True,
        "unified_output_ref": (packet.get("technical_references") or {}).get("unified_output"),
        "engine_ledger_present": bool(unified_output),
    }


def generate_deterministic_brief(
    packet: dict[str, Any],
    *,
    land_facts: dict[str, dict[str, Any]] | None = None,
    unified_output: dict[str, Any] | None = None,
    repo_root: Path | None = None,
    mireye_live: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a complete three-page Brief from a Packet. Fail-closed facts preferred."""
    uo = unified_output if unified_output is not None else _load_unified_output(
        packet, repo_root=repo_root
    )
    facts = land_facts if land_facts is not None else (land_fact_index(uo) if uo else {})
    bound_hash = packet_hash(packet)
    packet_violations = validate_packet(packet, land_facts=facts or None, repo_root=repo_root)
    passed = not packet_violations
    return {
        "schema_version": BRIEF_SCHEMA,
        "packet_hash": bound_hash,
        "validation_status": "PASSED" if passed else "FAILED",
        "validation_violations": packet_violations,
        "page_one_advisor": _page_one(packet),
        "page_two_actions": _page_two(packet),
        "page_three_kitchen": _page_three(
            packet,
            facts=facts,
            unified_output=uo,
            packet_violations=packet_violations,
            bound_hash=bound_hash,
            mireye_live=mireye_live,
        ),
        "report_provenance": {
            "displayable": passed,
            "generator": "DETERMINISTIC_TEMPLATE",
            "llm_used": False,
        },
    }
