"""Authoritative field-visit purpose. Shared by Brief and Operating Profile."""

from __future__ import annotations

from typing import Any, Mapping

from rangematch.advisor_contract import drawable_objects

VISIT_PURPOSE_DEFINED = "VISIT_PURPOSE_DEFINED"
VISIT_DEPENDS_ON_DOCUMENT = "VISIT_DEPENDS_ON_DOCUMENT"
NO_DEFINED_VISIT_PURPOSE_YET = "NO_DEFINED_VISIT_PURPOSE_YET"


def field_drawable_objects(objects: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Objects that can be placed on a field route: AREA_ONLY and drawable geometry."""
    rows: list[dict[str, Any]] = []
    for obj in drawable_objects(list(objects or [])):
        precision = (obj.get("geometry") or {}).get("field_navigation_precision")
        if precision == "AREA_ONLY":
            rows.append(obj)
    return rows


def _ordered_action_ids(packet: Mapping[str, Any]) -> list[str]:
    return [
        str(row.get("action_id"))
        for row in sorted(
            packet.get("actions") or [],
            key=lambda item: int(item.get("execution_order") or 0),
        )
        if row.get("action_id")
    ]


def derive_authoritative_visit_purpose(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministic visit_state + purpose_type. No free-text purpose."""
    drawable = field_drawable_objects(list(packet.get("candidate_objects") or []))
    drawable_ids = [
        str(row.get("candidate_id"))
        for row in drawable
        if row.get("candidate_id")
    ]
    ordered = _ordered_action_ids(packet)
    action_ids = set(ordered)
    stage = str((packet.get("decision_context") or {}).get("current_stage") or "")
    water_actions = [
        aid
        for aid in ordered
        if aid.startswith("ACTION_WATER") or aid == "ACTION_ASK_SELLER_WATER"
    ]

    if "ACTION_CONFIRM_PARCEL" in action_ids:
        return {
            "visit_state": NO_DEFINED_VISIT_PURPOSE_YET,
            "bound_action_ids": ["ACTION_CONFIRM_PARCEL"],
            "purpose_type": "CONFIRM_PARCEL",
            "object_refs": [],
        }
    if stage in {"FIELD_VISIT_ALREADY_BOOKED", "FIELD_FOLLOW_UP"} and drawable_ids:
        return {
            "visit_state": VISIT_PURPOSE_DEFINED,
            "bound_action_ids": water_actions[:1],
            "purpose_type": "WATER_FIELD_REVIEW",
            "object_refs": list(drawable_ids),
        }
    if "ACTION_ACCESS_DOCUMENTS" in action_ids:
        bound = ["ACTION_ACCESS_DOCUMENTS", *water_actions[:1]]
        if drawable_ids:
            return {
                "visit_state": VISIT_DEPENDS_ON_DOCUMENT,
                "bound_action_ids": bound,
                "purpose_type": "WATER_FIELD_REVIEW_AFTER_ACCESS_DOCUMENT",
                "object_refs": list(drawable_ids),
            }
        return {
            "visit_state": VISIT_DEPENDS_ON_DOCUMENT,
            "bound_action_ids": bound,
            "purpose_type": "WATER_INVENTORY_AFTER_ACCESS_DOCUMENT",
            "object_refs": [],
        }
    if drawable_ids:
        return {
            "visit_state": VISIT_PURPOSE_DEFINED,
            "bound_action_ids": water_actions[:1],
            "purpose_type": "WATER_FIELD_REVIEW",
            "object_refs": list(drawable_ids),
        }
    return {
        "visit_state": NO_DEFINED_VISIT_PURPOSE_YET,
        "bound_action_ids": ordered[:2],
        "purpose_type": "NO_DEFINED_VISIT_PURPOSE",
        "object_refs": [],
    }
