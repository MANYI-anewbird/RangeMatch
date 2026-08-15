"""Generic Buyer Evidence Packet projection (non-CPER).

Observation/object projection reuses advisor_packet helpers. Policy is a
minimal three-class diligence ranker — never build_cper_demo_policy.
Contract: docs/ADVISOR_GENERIC_EVIDENCE_PACKET.md
"""

from __future__ import annotations

from typing import Any, Mapping

from rangematch.advisor_packet import (
    F03_AVAILABLE,
    F03_FAILED,
    F03_NOT_PROVIDED,
    MissingPolicyError,
    _access_action,
    _action_policy_for,
    _confirm_action,
    _default_decision_context,
    _water_action,
    _water_mode,
    constrain_actions_to_objects,
    derive_claim_gaps,
    is_cper_engineering_fixture,
    project_buyer_evidence_packet,
    project_candidate_objects,
    project_observations,
)


def _forage_interpret_action(order: int) -> dict[str, Any]:
    return {
        "action_id": "ACTION_INTERPRET_RAP_FORAGE",
        "execution_order": order,
        "action_type": "DESKTOP_REVIEW",
        "specificity": "CATEGORY_LEVEL",
        "target_category": "FORAGE_OR_PRODUCTION",
        "candidate_id": None,
        "suggested_executor": "buyer or buyer-side advisor",
        "cost_class": "DESKTOP",
        "why_now": (
            "Modeled RAP / herbaceous production is a snapshot only; read it as a "
            "lead, not a stocking or purchase signal."
        ),
        "can_establish": [
            "that the modeled production figure must not be treated as available forage"
        ],
        "cannot_establish": [
            "carrying capacity",
            "ready for cattle",
            "grazable acres",
        ],
        "success_transition": "FORAGE_MODEL_BOUNDED",
        "failure_transition": "KEEP_FORAGE_AS_MODELED_ONLY",
    }


def build_generic_minimal_policy(
    listing_claims: list[dict[str, Any]],
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Minimal nationwide policy: access paper, water verify, RAP interpret."""
    ctx = dict(context or {})
    decision = ctx.get("decision_context") or {}
    objects = list(ctx.get("candidate_objects") or [])
    f03_status = str(ctx.get("f03_status") or F03_AVAILABLE)
    confirmation = str(ctx.get("confirmation_status") or "CONFIRMED")
    stage = str(decision.get("current_stage") or "PRE_VISIT")
    water_mode = _water_mode(objects, f03_status)
    water = _water_action(2, mode=water_mode)
    access = _access_action(1)
    forage = _forage_interpret_action(3)

    if confirmation != "CONFIRMED" or stage == "PARCEL_CONFIRMATION":
        actions = [_confirm_action()]
    elif stage in {"TITLE_REVIEW_ACTIVE", "DOCUMENT_REVIEW"}:
        water["execution_order"] = 1
        forage["execution_order"] = 2
        actions = [water, forage]
    elif stage in {"FIELD_VISIT_ALREADY_BOOKED", "FIELD_FOLLOW_UP"}:
        water["execution_order"] = 1
        access["execution_order"] = 2
        forage["execution_order"] = 3
        actions = [water, access, forage]
    else:
        actions = [access, water, forage]

    action_ids = {row["action_id"] for row in actions}
    water_id = water["action_id"] if water["action_id"] in action_ids else None
    access_id = access["action_id"] if access["action_id"] in action_ids else None
    forage_id = forage["action_id"] if forage["action_id"] in action_ids else None

    bottlenecks: list[dict[str, Any]] = []
    if "ACTION_CONFIRM_PARCEL" in action_ids:
        bottlenecks.append(
            {
                "bottleneck_id": "BOTTLENECK_PARCEL_CONFIRMATION",
                "bottleneck_rank": 1,
                "title": "Parcel outline is not confirmed",
                "supporting_observation_ids": ["OBS_AREA"],
                "affected_candidate_ids": [],
                "blocked_inferences": ["any diligence spend on an unconfirmed outline"],
                "decision_impact": "HIGH",
                "information_gain": "HIGH",
                "cost_class": "DESKTOP",
                "next_action_ids": ["ACTION_CONFIRM_PARCEL"],
            }
        )
    else:
        bottlenecks.extend(
            [
                {
                    "bottleneck_id": "BOTTLENECK_WATER_EVIDENCE",
                    "bottleneck_rank": 1,
                    "title": "Livestock-water use still lacks operating evidence",
                    "supporting_observation_ids": ["OBS_WATER_COUNT"],
                    "affected_candidate_ids": [],
                    "blocked_inferences": [
                        "usable livestock water",
                        "seasonal reliability",
                        "missing mapped leads means no water",
                    ],
                    "decision_impact": "HIGH",
                    "information_gain": "HIGH",
                    "cost_class": water["cost_class"],
                    "next_action_ids": [water_id] if water_id else [],
                },
                {
                    "bottleneck_id": "BOTTLENECK_LEGAL_ACCESS",
                    "bottleneck_rank": 2,
                    "title": "Legal entrance is unproven"
                    if access_id
                    else "Legal entrance review is already in motion",
                    "supporting_observation_ids": ["OBS_ROAD"],
                    "affected_candidate_ids": [],
                    "blocked_inferences": ["legal access", "usable entrance"],
                    "decision_impact": "HIGH",
                    "information_gain": "HIGH",
                    "cost_class": "DOCUMENT_REQUEST",
                    "next_action_ids": [access_id] if access_id else [],
                },
                {
                    "bottleneck_id": "BOTTLENECK_FORAGE_LEAP",
                    "bottleneck_rank": 3,
                    "title": "Modeled growth must not be read as stockable forage",
                    "supporting_observation_ids": ["OBS_RAP_PROD"],
                    "affected_candidate_ids": [],
                    "blocked_inferences": ["carrying capacity", "ready for cattle"],
                    "decision_impact": "MEDIUM",
                    "information_gain": "MEDIUM",
                    "cost_class": "DESKTOP",
                    "next_action_ids": [forage_id] if forage_id else [],
                },
            ]
        )

    gaps = derive_claim_gaps(listing_claims)
    claim_ids = {row.get("claim_id") for row in listing_claims}
    for gap in gaps:
        category = next(
            (
                row.get("category")
                for row in listing_claims
                if row.get("claim_id") == gap.get("claim_id")
            ),
            None,
        )
        if category == "LIVESTOCK_WATER":
            if f03_status == F03_FAILED:
                gap["supported_portion"] = "Mapped-water inventory is currently unavailable"
            elif not objects:
                gap["supported_portion"] = (
                    "No mapped hydrography leads were returned in the search"
                )
            elif water_mode == "LOCATION_OR_INVENTORY":
                gap["supported_portion"] = (
                    "Mapped hydrography identities exist, but none can be placed on a map"
                )
            if water_id:
                gap["recommended_action_id"] = water_id
                gap["recommended_message_id"] = "MSG_WATER"
        elif category == "LEGAL_ACCESS" and access_id:
            gap["recommended_action_id"] = "ACTION_ACCESS_DOCUMENTS"
            gap["recommended_message_id"] = "MSG_TITLE_ACCESS"
        elif category == "FORAGE_OR_PRODUCTION" and forage_id:
            gap["recommended_action_id"] = "ACTION_INTERPRET_RAP_FORAGE"
            gap["recommended_message_id"] = "MSG_FORAGE_INTERPRET"
        if "ACTION_CONFIRM_PARCEL" in action_ids:
            gap["recommended_action_id"] = "ACTION_CONFIRM_PARCEL"
            gap["recommended_message_id"] = "MSG_CONFIRM_PARCEL"

    messages: list[dict[str, Any]] = []
    if "ACTION_CONFIRM_PARCEL" in action_ids:
        messages.append(
            {
                "message_id": "MSG_CONFIRM_PARCEL",
                "audience": "PARTNER",
                "bound_action_id": "ACTION_CONFIRM_PARCEL",
                "bound_claim_id": None,
                "template_id": "CONFIRM_PARCEL_BEFORE_DILIGENCE",
            }
        )
        return {
            "bottlenecks": bottlenecks,
            "actions": actions,
            "action_policy": _action_policy_for(actions),
            "claim_evidence_gaps": gaps,
            "copy_ready_message_specs": messages,
        }

    if access_id:
        messages.append(
            {
                "message_id": "MSG_TITLE_ACCESS",
                "audience": "TITLE_OR_COUNSEL",
                "bound_action_id": "ACTION_ACCESS_DOCUMENTS",
                "bound_claim_id": "CLAIM_ACCESS_001"
                if "CLAIM_ACCESS_001" in claim_ids
                else None,
                "template_id": "ASK_RECORDED_ENTRANCE",
            }
        )
    if water_id:
        water_claim = next(
            (
                str(row.get("claim_id"))
                for row in listing_claims
                if row.get("category") == "LIVESTOCK_WATER" and row.get("claim_id")
            ),
            None,
        )
        if water_id == "ACTION_WATER_FIELD_CATEGORY":
            messages.append(
                {
                    "message_id": "MSG_WATER",
                    "audience": "LISTING_BROKER" if water_claim else "PARTNER",
                    "bound_action_id": water_id,
                    "bound_claim_id": water_claim,
                    "template_id": "ASK_WATER_TYPE_LOCATION_RECORDS"
                    if water_claim
                    else "ASK_SELLER_DEVELOPED_WATER",
                }
            )
            messages.append(
                {
                    "message_id": "MSG_FIELD_WATER",
                    "audience": "FIELD_VISITOR",
                    "bound_action_id": water_id,
                    "bound_claim_id": water_claim,
                    "template_id": "REVIEW_MAPPED_WATER_AREAS",
                }
            )
        elif water_id == "ACTION_WATER_LOCATION_OR_INVENTORY":
            messages.append(
                {
                    "message_id": "MSG_WATER",
                    "audience": "LISTING_BROKER" if water_claim else "PARTNER",
                    "bound_action_id": water_id,
                    "bound_claim_id": water_claim,
                    "template_id": "ASK_FOR_WATER_LOCATION_OR_INVENTORY",
                }
            )
        elif water_id == "ACTION_WATER_SOURCE_UNAVAILABLE":
            messages.append(
                {
                    "message_id": "MSG_WATER",
                    "audience": "LISTING_BROKER" if water_claim else "PARTNER",
                    "bound_action_id": water_id,
                    "bound_claim_id": water_claim,
                    "template_id": "F03_INVENTORY_UNAVAILABLE",
                }
            )
        else:
            messages.append(
                {
                    "message_id": "MSG_WATER",
                    "audience": "LISTING_BROKER" if water_claim else "PARTNER",
                    "bound_action_id": water_id,
                    "bound_claim_id": water_claim,
                    "template_id": "ASK_SELLER_DEVELOPED_WATER",
                }
            )
    if forage_id:
        forage_claim = next(
            (
                str(row.get("claim_id"))
                for row in listing_claims
                if row.get("category") == "FORAGE_OR_PRODUCTION" and row.get("claim_id")
            ),
            None,
        )
        messages.append(
            {
                "message_id": "MSG_FORAGE_INTERPRET",
                "audience": "PARTNER",
                "bound_action_id": "ACTION_INTERPRET_RAP_FORAGE",
                "bound_claim_id": forage_claim,
                "template_id": "INTERPRET_RAP_NOT_STOCKING",
            }
        )
    messages.append(
        {
            "message_id": "MSG_PARTNER_HOLD",
            "audience": "PARTNER",
            "bound_action_id": access_id or water_id or forage_id,
            "bound_claim_id": None,
            "template_id": (
                "WAIT_FOR_ACCESS_PAPER_BEFORE_FLIGHT"
                if listing_claims
                else "WAIT_FOR_ACCESS_PAPER_PUBLIC_EVIDENCE"
            ),
        }
    )

    return {
        "bottlenecks": bottlenecks[:3],
        "actions": actions,
        "action_policy": _action_policy_for(actions),
        "claim_evidence_gaps": gaps,
        "copy_ready_message_specs": messages,
    }


def project_coverage_index(unified_output: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Deterministic coverage/failure rows from UO land facts (no invention)."""
    from rangematch.advisor_contract import land_fact_index
    from rangematch.advisor_packet import OBSERVATION_SPECS

    facts = land_fact_index(dict(unified_output))
    rows: list[dict[str, Any]] = []
    for spec in OBSERVATION_SPECS:
        vid = spec["variable_id"]
        fact = facts.get(vid)
        if fact is None:
            rows.append(
                {
                    "variable_id": vid,
                    "status": "MISSING",
                    "coverage": None,
                    "limitations": ["land fact absent from Unified Output"],
                }
            )
            continue
        coverage = fact.get("coverage")
        status = "PRESENT"
        limitations = list(fact.get("limitations") or [])
        if isinstance(coverage, Mapping):
            if coverage.get("status"):
                status = str(coverage.get("status"))
            limitations.extend(list(coverage.get("limitations") or []))
        rows.append(
            {
                "variable_id": vid,
                "status": status,
                "coverage": coverage,
                "limitations": limitations,
            }
        )
    return rows


def project_generic_buyer_evidence_packet(
    unified_output: dict[str, Any],
    *,
    listing_claims: list[dict[str, Any]] | None = None,
    decision_context: dict[str, Any] | None = None,
    confirmation_status: str = "CONFIRMED",
    unified_output_ref: str,
    candidate_inventory: Mapping[str, Any] | list[dict[str, Any]] | None = None,
    remote_pilot: Mapping[str, Any] | None = None,
    f03_status: str | None = None,
    f03_inventory_ref: str | None = None,
    f03_remote_pilot_ref: str | None = None,
    mireye_context_refs: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Project a non-CPER Buyer Evidence Packet. Never inherits CPER fixtures."""
    if is_cper_engineering_fixture(unified_output):
        raise MissingPolicyError(
            "CPER engineering fixture must use project_cper_buyer_evidence_packet; "
            "generic projector refuses silent CPER assembly"
        )
    packet = project_buyer_evidence_packet(
        unified_output,
        listing_claims=listing_claims,
        decision_context=decision_context or _default_decision_context(None),
        confirmation_status=confirmation_status,
        unified_output_ref=unified_output_ref,
        candidate_inventory=candidate_inventory,
        remote_pilot=remote_pilot,
        policy=build_generic_minimal_policy,
        f03_status=f03_status,
        allow_missing_observations=True,
        f03_inventory_ref=f03_inventory_ref,
        f03_remote_pilot_ref=f03_remote_pilot_ref,
    )
    refs = dict(packet.get("technical_references") or {})
    refs["policy_scope"] = "GENERIC_MINIMAL"
    refs["coverage_by_variable"] = project_coverage_index(unified_output)
    if mireye_context_refs:
        refs["mireye_context_refs"] = [dict(row) for row in mireye_context_refs]
    # Defense: never leave CPER fixture paths on a generic packet.
    for key in ("f03_candidate_inventory", "f03_remote_pilot"):
        value = refs.get(key)
        if isinstance(value, str) and "cper" in value.lower():
            refs[key] = None
    packet["technical_references"] = refs
    packet["parcel"] = dict(packet.get("parcel") or {})
    packet["parcel"]["is_engineering_test_geometry"] = False
    if packet["parcel"].get("display_label") and "CPER" in str(
        packet["parcel"].get("display_label")
    ):
        packet["parcel"]["display_label"] = None
    return packet


# Re-export helpers tests may want when asserting object projection alone.
__all__ = [
    "build_generic_minimal_policy",
    "project_coverage_index",
    "project_generic_buyer_evidence_packet",
    "project_candidate_objects",
    "project_observations",
    "F03_AVAILABLE",
    "F03_FAILED",
    "F03_NOT_PROVIDED",
]
