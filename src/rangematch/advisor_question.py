"""Deterministic high-value question selection for Slice 4.

The LLM may propose wording, but the selected question_id must come from this
catalog. Slice 4 does not accept answers.
"""

from __future__ import annotations

from typing import Any, Mapping

QUESTION_CATALOG: dict[str, dict[str, Any]] = {
    "Q_OPERATION_TYPE": {
        "question_id": "Q_OPERATION_TYPE",
        "prompt": (
            "Are you evaluating this property for seasonal grazing or a "
            "year-round cow-calf operation?"
        ),
        "allowed_field": "operation_type",
        "what_would_change_view_ref": "CHANGE_OPERATION_TYPE",
        "change_view_text": (
            "Knowing seasonal versus year-round cow-calf changes how water "
            "demand and visit purpose should be read."
        ),
    },
    "Q_SELLER_WATER_CLAIM": {
        "question_id": "Q_SELLER_WATER_CLAIM",
        "prompt": (
            "Is the seller claiming a developed year-round livestock-water "
            "system on this parcel?"
        ),
        "allowed_field": "seller_water_claim",
        "what_would_change_view_ref": "CHANGE_SELLER_WATER_CLAIM",
        "change_view_text": (
            "A named developed-water claim would sharpen whether the next spend "
            "is a document request or a narrow field inventory."
        ),
    },
    "Q_ACCESS_DOCUMENTS": {
        "question_id": "Q_ACCESS_DOCUMENTS",
        "prompt": (
            "Do you already have recorded access or title material for the "
            "entrance used to reach this tract?"
        ),
        "allowed_field": "access_documents_on_hand",
        "what_would_change_view_ref": "CHANGE_ACCESS_PAPER_STATUS",
        "change_view_text": (
            "Whether access paper is already in hand decides if travel can wait "
            "behind a cheaper document request."
        ),
    },
    "Q_USER_WATER_INFORMATION": {
        "question_id": "Q_USER_WATER_INFORMATION",
        "prompt": (
            "What livestock-water information do you already have for this parcel "
            "(developed drinkers, seasonal sources, or none confirmed yet)?"
        ),
        "allowed_field": "user_supplied_water_information",
        "what_would_change_view_ref": "CHANGE_USER_WATER_INFORMATION",
        "change_view_text": (
            "Buyer-supplied water context refines how incomplete mapped hydrography "
            "should be read without inventing drinkers."
        ),
    },
    "Q_VEGETATION_OR_GRAZING_HISTORY": {
        "question_id": "Q_VEGETATION_OR_GRAZING_HISTORY",
        "prompt": (
            "Do you have any local vegetation or recent grazing history for this "
            "parcel that is not already in the environmental profile?"
        ),
        "allowed_field": "user_supplied_vegetation_or_grazing_history",
        "what_would_change_view_ref": "CHANGE_VEGETATION_HISTORY",
        "change_view_text": (
            "Local vegetation or grazing history can narrow forage confidence "
            "without converting RAP into a stocking rate."
        ),
    },
}

# Primary natural-foundation catalog: no access/title questions.
NATURAL_QUESTION_IDS = frozenset(
    {
        "Q_OPERATION_TYPE",
        "Q_USER_WATER_INFORMATION",
        "Q_VEGETATION_OR_GRAZING_HISTORY",
        "Q_SELLER_WATER_CLAIM",
    }
)


def _profile_statement_types(profile: Mapping[str, Any] | None) -> set[str]:
    types: set[str] = set()
    if not isinstance(profile, Mapping):
        return types
    domains = profile.get("operating_domains") or {}
    if not isinstance(domains, Mapping):
        return types
    for bucket in domains.values():
        if not isinstance(bucket, Mapping):
            continue
        for row in bucket.get("statements") or []:
            if isinstance(row, Mapping) and row.get("statement_type"):
                types.add(str(row["statement_type"]))
    return types


def _answered_fields(deal_context: Mapping[str, Any] | None) -> set[str]:
    fields: set[str] = set()
    if not isinstance(deal_context, Mapping):
        return fields
    for row in deal_context.get("user_answers") or []:
        if isinstance(row, Mapping) and row.get("field"):
            fields.add(str(row["field"]))
    return fields


def select_one_question(
    *,
    deal_context: Mapping[str, Any] | None,
    operating_profile: Mapping[str, Any] | None,
    packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Pick exactly one catalog question from current evidence and context."""
    answered = _answered_fields(deal_context)
    operation_type = str((deal_context or {}).get("operation_type") or "UNKNOWN").upper()
    statement_types = _profile_statement_types(operating_profile)
    attention = list((operating_profile or {}).get("domain_attention_order") or [])
    first_actions = list((operating_profile or {}).get("action_execution_order") or [])
    first_action = first_actions[0] if first_actions else ""

    # Prefer operation type when still unknown — highest leverage for cattle reading.
    if operation_type == "UNKNOWN" and "operation_type" not in answered:
        return dict(QUESTION_CATALOG["Q_OPERATION_TYPE"])

    water_stressed = bool(
        statement_types
        & {
            "WATER_INVENTORY_UNAVAILABLE",
            "NO_MAPPED_HYDROGRAPHY_LEADS",
            "DRAWABLE_WATER_NONE",
        }
    ) or (attention and attention[0] == "DRINK")
    if water_stressed and "seller_water_claim" not in answered:
        return dict(QUESTION_CATALOG["Q_SELLER_WATER_CLAIM"])

    if first_action == "ACTION_ACCESS_DOCUMENTS" and "access_documents_on_hand" not in answered:
        return dict(QUESTION_CATALOG["Q_ACCESS_DOCUMENTS"])

    if "seller_water_claim" not in answered:
        return dict(QUESTION_CATALOG["Q_SELLER_WATER_CLAIM"])
    if "access_documents_on_hand" not in answered:
        return dict(QUESTION_CATALOG["Q_ACCESS_DOCUMENTS"])
    # Last resort still returns one catalog question (never invent).
    return dict(QUESTION_CATALOG["Q_OPERATION_TYPE"])


def select_natural_environment_question(
    *,
    deal_context: Mapping[str, Any] | None,
    natural_cattle_profile: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Deterministic environmental question for the Natural Cattle path.

    Priority: operation_type once → Water when controlling/incomplete → other gaps.
    Never returns Q_ACCESS_DOCUMENTS.
    """
    answered = _answered_fields(deal_context)
    operation_type = str((deal_context or {}).get("operation_type") or "UNKNOWN").upper()
    if operation_type == "UNKNOWN" and "operation_type" not in answered:
        return dict(QUESTION_CATALOG["Q_OPERATION_TYPE"])

    overall = (natural_cattle_profile or {}).get("overall_natural_foundation") or {}
    controlling = overall.get("controlling_factor") or {}
    domains = {
        str(row.get("domain")): row
        for row in (natural_cattle_profile or {}).get("domains") or []
        if isinstance(row, Mapping)
    }
    water = domains.get("WATER") or {}
    water_incomplete = water.get("confidence") in {"LOW", "INSUFFICIENT"}
    controlling_water = controlling.get("domain") == "WATER"

    if (
        (controlling_water or water_incomplete)
        and "user_supplied_water_information" not in answered
        and "seller_water_claim" not in answered
    ):
        return dict(QUESTION_CATALOG["Q_USER_WATER_INFORMATION"])

    forage = domains.get("FEED_VEGETATION") or {}
    if (
        forage.get("confidence") in {"LOW", "INSUFFICIENT"}
        and "user_supplied_vegetation_or_grazing_history" not in answered
    ):
        return dict(QUESTION_CATALOG["Q_VEGETATION_OR_GRAZING_HISTORY"])

    if "user_supplied_water_information" not in answered:
        return dict(QUESTION_CATALOG["Q_USER_WATER_INFORMATION"])
    if "user_supplied_vegetation_or_grazing_history" not in answered:
        return dict(QUESTION_CATALOG["Q_VEGETATION_OR_GRAZING_HISTORY"])
    return dict(QUESTION_CATALOG["Q_OPERATION_TYPE"])


def natural_catalog_ids() -> set[str]:
    return set(NATURAL_QUESTION_IDS)


def question_public(row: Mapping[str, Any]) -> dict[str, str]:
    return {
        "question_id": str(row["question_id"]),
        "prompt": str(row["prompt"]),
        "allowed_field": str(row["allowed_field"]),
        "what_would_change_view_ref": str(row["what_would_change_view_ref"]),
    }


def catalog_ids() -> set[str]:
    return set(QUESTION_CATALOG)
