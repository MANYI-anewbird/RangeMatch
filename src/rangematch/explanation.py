"""Constrained explanation bound to a deterministic MatchResult.

The explanation layer may restate structured engine outputs. It may not invent
scores, thresholds, rankings, or scientific claims absent from the MatchResult.
"""

from __future__ import annotations

from typing import Any


OPERATION_LABELS = {
    "COW_CALF_OPERATION": "Cow-Calf Operation",
    "SHEEP_GRAZING": "Sheep Grazing",
}

FACTOR_LABELS = {
    "F01_TOPOGRAPHY": "Topography",
    "F02_HERBACEOUS_RESOURCE": "Herbaceous Resource",
    "F03_LIVESTOCK_WATER": "Livestock Water",
    "F04_SOIL_WETNESS_ECOLOGICAL_SITE": "Soil, Wetness, and Ecological Site",
    "F05_CLIMATE_DROUGHT_EXPOSURE": "Climate and Drought Exposure",
    "F06_PARCEL_CONFIGURATION": "Parcel Configuration",
    "F07_ROAD_AND_PHYSICAL_ACCESS": "Road and Physical Access",
    "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE": "Woody and Shrub Vegetation Structure",
}


def explain_match_result(
    match_result: dict[str, Any],
    land_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a structured explanation strictly from MatchResult fields."""
    if match_result.get("llm_override_permitted") is True:
        raise ValueError("Explanation refused: MatchResult permits LLM override")

    operation_summaries = []
    for operation_id, body in (match_result.get("operation_results") or {}).items():
        factor_lines = []
        for factor_id, evaluation in (body.get("factor_evaluations") or {}).items():
            factor_lines.append(
                {
                    "factor_id": factor_id,
                    "label": FACTOR_LABELS.get(factor_id, factor_id),
                    "signal": evaluation.get("signal"),
                    "ranking_effect": evaluation.get("ranking_effect"),
                    "explanation_code": evaluation.get("explanation_code"),
                }
            )
        operation_summaries.append(
            {
                "operation_id": operation_id,
                "label": OPERATION_LABELS.get(operation_id, operation_id),
                "decision_label": body.get("decision_label"),
                "decision_reason": body.get("decision_reason"),
                "ranking_position": body.get("ranking_position"),
                "factors": factor_lines,
            }
        )

    profile_meta = {
        "land_profile_id": match_result.get("land_profile_id"),
        "land_profile_version": match_result.get("land_profile_version"),
        "geometry_id": (land_profile or {}).get("geometry_id"),
        "supported_use": (land_profile or {}).get("supported_use"),
    }

    narrative = [
        "This is a preliminary screening result produced by the deterministic Matching Engine.",
        "Cow-Calf and Sheep are evaluated as peer operations. No cross-profile ranking is permitted in this vertical slice.",
        "Signals describe evidence quality and reviewed qualitative context. They are not carrying capacity, profitability, or success probability.",
        "Missing or unverified inputs remain UNKNOWN or NEEDS_VERIFICATION and are listed as diligence actions.",
    ]

    f03 = ((land_profile or {}).get("factors") or {}).get("F03_LIVESTOCK_WATER") or {}
    if f03.get("remote_evidence_summary") or f03.get("demo_statements"):
        narrative.extend(
            [
                "CPER does not have verified livestock water in this live profile.",
                "REMOTELY_SUPPORTED candidates are not usable livestock-water systems.",
                "FIELD_VERIFIED remains zero; verified_count == 0 does not mean the land has no water.",
                "Unsampled mapped water candidates are UNREVIEWED, not absent or rejected.",
                "Synthetic field-evidence demos are TEST_ONLY and are not part of CPER live evidence.",
            ]
        )

    return {
        "explanation_schema_version": "0.1.0",
        "bound_to_input_sha256": match_result.get("input_sha256"),
        "engine_version": match_result.get("engine_version"),
        "llm_override_permitted": False,
        "may_alter_decision_labels": False,
        "may_invent_scores_or_thresholds": False,
        "parcel": profile_meta,
        "narrative_constraints": narrative,
        "operation_summaries": operation_summaries,
        "cross_profile_comparison": match_result.get("cross_profile_comparison"),
        "unknowns": list(match_result.get("unknowns") or []),
        "diligence_actions": list(match_result.get("diligence_actions") or []),
        "disclaimer": (
            "Preliminary screening only. The land did not fail; the match remains "
            "incomplete until additional reviewed Factors and field verification are available."
        ),
    }
