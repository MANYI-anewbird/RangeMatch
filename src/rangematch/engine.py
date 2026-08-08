"""Pure deterministic evaluation for the first RangeMatch vertical slice."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any


SUPPORTED_OPERATIONS = ("COW_CALF_OPERATION", "SHEEP_GRAZING")
REQUIRED_PROVENANCE = (
    "source_reference",
    "fetched_at",
    "geometry_hash",
    "response_or_artifact_hash",
)


def _provenance_complete(fact: dict[str, Any]) -> bool:
    provenance = fact.get("provenance") or {}
    return all(provenance.get(field) not in (None, "", []) for field in REQUIRED_PROVENANCE)


def evaluate_land_fact(fact: dict[str, Any]) -> dict[str, Any]:
    """Apply applicability, coverage, and provenance gates in frozen order."""
    applicability = (fact.get("applicability") or {}).get("domain_status", "UNKNOWN")
    coverage = (fact.get("coverage") or {}).get("status", "UNKNOWN")

    if applicability == "OUTSIDE_DOCUMENTED_PRODUCT_SCOPE":
        return {
            "gate_state": "NEEDS_VERIFICATION",
            "use_as_context": False,
            "use_as_primary_factor_evidence": False,
            "confidence_cap": "NEEDS_VERIFICATION",
            "reason_code": "OUTSIDE_PRODUCT_SCOPE",
        }
    if applicability == "UNKNOWN":
        return {
            "gate_state": "NEEDS_VERIFICATION",
            "use_as_context": False,
            "use_as_primary_factor_evidence": False,
            "confidence_cap": "NEEDS_VERIFICATION",
            "reason_code": "APPLICABILITY_UNKNOWN",
        }
    if not _provenance_complete(fact):
        return {
            "gate_state": "NEEDS_VERIFICATION",
            "use_as_context": False,
            "use_as_primary_factor_evidence": False,
            "confidence_cap": "NEEDS_VERIFICATION",
            "reason_code": "PROVENANCE_INCOMPLETE",
        }
    if coverage == "COVERAGE_UNQUANTIFIED":
        return {
            "gate_state": "LIMITED_CONTEXT",
            "use_as_context": True,
            "use_as_primary_factor_evidence": False,
            "confidence_cap": "LIMITED_BY_UNQUANTIFIED_COVERAGE",
            "reason_code": "COVERAGE_UNQUANTIFIED",
        }
    if coverage in {"PARTIAL", "UNKNOWN", "OUTSIDE_SUPPORTED_GEOGRAPHY"}:
        return {
            "gate_state": "NEEDS_VERIFICATION",
            "use_as_context": coverage == "PARTIAL",
            "use_as_primary_factor_evidence": False,
            "confidence_cap": "NEEDS_VERIFICATION",
            "reason_code": f"COVERAGE_{coverage}",
        }
    if coverage in {"COMPLETE", "NOT_APPLICABLE"}:
        return {
            "gate_state": "PASSED",
            "use_as_context": True,
            "use_as_primary_factor_evidence": True,
            "confidence_cap": "SUPPORTED",
            "reason_code": "GATES_PASSED",
        }
    return {
        "gate_state": "NEEDS_VERIFICATION",
        "use_as_context": False,
        "use_as_primary_factor_evidence": False,
        "confidence_cap": "UNKNOWN",
        "reason_code": "UNRECOGNIZED_COVERAGE_STATE",
    }


def _evaluate_f01(factor: dict[str, Any]) -> dict[str, Any]:
    state = factor.get("input_quality_state", "MISSING")
    mapping = {
        "PARCEL_COMPLETE": ("CONTEXT_DEPENDENT", "F01_EXPL_CONTEXT_REQUIRED"),
        "POINT_ONLY": ("NEEDS_VERIFICATION", "F01_EXPL_POINT_NOT_PARCEL"),
        "PARCEL_INCOMPLETE": ("NEEDS_VERIFICATION", "F01_EXPL_INCOMPLETE_PROVENANCE"),
        "CONFLICTING_SOURCES": ("NEEDS_VERIFICATION", "F01_EXPL_CONFLICT"),
        "MISSING": ("UNKNOWN", "F01_EXPL_MISSING"),
    }
    signal, explanation = mapping.get(state, ("NEEDS_VERIFICATION", "F01_EXPL_UNRECOGNIZED"))
    return {
        "factor_id": "F01_TOPOGRAPHY",
        "signal": signal,
        "ranking_effect": "NONE",
        "explanation_code": explanation,
        "input_quality_state": state,
    }


def _evaluate_f02(factor: dict[str, Any]) -> dict[str, Any]:
    facts = factor.get("land_facts") or []
    gate_results = [evaluate_land_fact(fact) for fact in facts]
    reason_codes = {result["reason_code"] for result in gate_results}

    if not facts:
        signal, explanation = "UNKNOWN", "F02_EXPL_MISSING"
    elif "OUTSIDE_PRODUCT_SCOPE" in reason_codes or "APPLICABILITY_UNKNOWN" in reason_codes:
        signal, explanation = "NEEDS_VERIFICATION", "F02_EXPL_SCOPE"
    elif "PROVENANCE_INCOMPLETE" in reason_codes:
        signal, explanation = "NEEDS_VERIFICATION", "F02_EXPL_PROVENANCE"
    elif "COVERAGE_UNQUANTIFIED" in reason_codes or any(
        code.startswith("COVERAGE_") for code in reason_codes
    ):
        signal, explanation = "NEEDS_VERIFICATION", "F02_EXPL_COVERAGE"
    elif all(result["gate_state"] == "PASSED" for result in gate_results):
        signal, explanation = "CONTEXT_DEPENDENT", "F02_EXPL_CONTEXT_ONLY"
    else:
        signal, explanation = "NEEDS_VERIFICATION", "F02_EXPL_UNRECOGNIZED"

    return {
        "factor_id": "F02_HERBACEOUS_RESOURCE",
        "signal": signal,
        "ranking_effect": "NONE",
        "explanation_code": explanation,
        "land_fact_gates": gate_results,
    }


def _evaluate_f03(factor: dict[str, Any]) -> dict[str, Any]:
    state = factor.get("input_quality_state", "MISSING")
    mapping = {
        "MAPPED_CANDIDATES_ONLY": ("NEEDS_VERIFICATION", "F03_EXPL_CANDIDATES_NOT_VERIFIED"),
        "PHYSICAL_SOURCE_UNVERIFIED_SYSTEM": ("NEEDS_VERIFICATION", "F03_EXPL_SYSTEM_UNVERIFIED"),
        "VERIFIED_WATER_SYSTEM_CONTEXT": ("CONTEXT_DEPENDENT", "F03_EXPL_CONTEXT_REQUIRED"),
        "CONFLICTING_SOURCES": ("NEEDS_VERIFICATION", "F03_EXPL_CONFLICT"),
        "MISSING": ("UNKNOWN", "F03_EXPL_MISSING"),
    }
    signal, explanation = mapping.get(state, ("NEEDS_VERIFICATION", "F03_EXPL_UNRECOGNIZED"))
    result = {
        "factor_id": "F03_LIVESTOCK_WATER",
        "signal": signal,
        "ranking_effect": "NONE",
        "explanation_code": explanation,
        "input_quality_state": state,
        "mapped_candidate_count": factor.get("mapped_candidate_count"),
        "verified_livestock_water_system_count": factor.get(
            "verified_livestock_water_system_count"
        ),
        "field_verified_count": factor.get("field_verified_count")
        if factor.get("field_verified_count") is not None
        else factor.get("verified_livestock_water_system_count"),
    }
    summary = factor.get("remote_evidence_summary")
    if isinstance(summary, dict):
        # Pass-through demo evidence depth only; does not change Factor signal.
        result["remote_evidence_summary"] = summary
    if factor.get("demo_statements"):
        result["demo_statements"] = list(factor.get("demo_statements") or [])
    return result


def _evaluate_f04(factor: dict[str, Any]) -> dict[str, Any]:
    if not factor:
        state = "MISSING"
    else:
        state = factor.get("input_quality_state", "MISSING")
    mapping = {
        "PARCEL_COMPLETE": ("CONTEXT_DEPENDENT", "F04_EXPL_CONTEXT_ONLY"),
        "POINT_ONLY": ("NEEDS_VERIFICATION", "F04_EXPL_POINT_NOT_PARCEL"),
        "PARCEL_INCOMPLETE": ("NEEDS_VERIFICATION", "F04_EXPL_INCOMPLETE"),
        "CONFLICTING_SOURCES": ("NEEDS_VERIFICATION", "F04_EXPL_CONFLICT"),
        "MISSING": ("UNKNOWN", "F04_EXPL_MISSING"),
    }
    signal, explanation = mapping.get(state, ("NEEDS_VERIFICATION", "F04_EXPL_UNRECOGNIZED"))

    provenance = factor.get("provenance") or {}
    coverage = factor.get("coverage") or factor.get("parcel_coverage") or {}
    if state == "PARCEL_COMPLETE":
        if any(
            provenance.get(field) in (None, "", [])
            for field in REQUIRED_PROVENANCE
        ):
            signal, explanation = "NEEDS_VERIFICATION", "F04_EXPL_INCOMPLETE"
            state = "PARCEL_INCOMPLETE"
        elif coverage.get("status") not in {"COMPLETE", "COMPLETE_WITH_NUMERIC_TOLERANCE"}:
            if coverage.get("detail") != "COMPLETE_WITH_NUMERIC_TOLERANCE":
                signal, explanation = "NEEDS_VERIFICATION", "F04_EXPL_INCOMPLETE"
                state = "PARCEL_INCOMPLETE"

    return {
        "factor_id": "F04_SOIL_WETNESS_ECOLOGICAL_SITE",
        "signal": signal,
        "ranking_effect": "NONE",
        "explanation_code": explanation,
        "input_quality_state": state,
        "component_count": (factor.get("quality") or {}).get("component_count"),
        "ecological_site_count": len(factor.get("ecological_site_references") or []),
    }


_F05_ACCEPTED_UNITS = {
    "millimeter",
    "millimeters",
    "mm",
    "mm/year",
    "mm/yr",
    "mm year-1",
}
_F05_ACCEPTED_COVERAGE = {
    "COMPLETE",
    "COMPLETE_WITH_NUMERIC_TOLERANCE",
    "COMPLETE_SINGLE_CELL_COVERS_SMALL_PARCEL",
    "COMPLETE_CELLS_INTERSECT_PARCEL_BBOX",
}


def _evaluate_f05(factor: dict[str, Any]) -> dict[str, Any]:
    """Evaluate F05 climate/drought as data-quality and context only."""
    if not factor:
        state = "MISSING"
    else:
        state = factor.get("input_quality_state", "MISSING")

    mapping = {
        "CLIMATE_CONTEXT_COMPLETE": ("CONTEXT_DEPENDENT", "F05_EXPL_CONTEXT_ONLY"),
        "CLIMATE_CONTEXT_INCOMPLETE": ("NEEDS_VERIFICATION", "F05_EXPL_INCOMPLETE"),
        "POINT_CLIMATE_ONLY": ("NEEDS_VERIFICATION", "F05_EXPL_POINT_NOT_PARCEL_PRECIP"),
        "PROHIBITED_PRECIP_PROXY": ("NEEDS_VERIFICATION", "F05_EXPL_PRECIP_PROXY_PROHIBITED"),
        "CONFLICTING_SOURCES": ("NEEDS_VERIFICATION", "F05_EXPL_CONFLICT"),
        "MISSING": ("UNKNOWN", "F05_EXPL_MISSING"),
    }
    signal, explanation = mapping.get(state, ("NEEDS_VERIFICATION", "F05_EXPL_UNRECOGNIZED"))

    precip = factor.get("canonical_precipitation") or {}
    provenance = factor.get("provenance") or {}
    coverage = factor.get("parcel_coverage") or factor.get("coverage") or {}
    conflicts = factor.get("source_conflicts") or []

    # ACIS/Mireye must never silently become the canonical precip value.
    if precip.get("role") not in (None, "CANONICAL_LAND_FACT") and state == "CLIMATE_CONTEXT_COMPLETE":
        signal, explanation = "NEEDS_VERIFICATION", "F05_EXPL_INCOMPLETE"
        state = "CLIMATE_CONTEXT_INCOMPLETE"

    if conflicts or any(
        item.get("material_conflict") for item in (factor.get("secondary_comparisons") or [])
    ):
        signal, explanation = "NEEDS_VERIFICATION", "F05_EXPL_CONFLICT"
        state = "CONFLICTING_SOURCES"

    if state == "CLIMATE_CONTEXT_COMPLETE":
        unit = str(precip.get("unit") or "").strip().lower()
        period = precip.get("normals_period") or precip.get("observation_period")
        coverage_status = coverage.get("detail") or coverage.get("status")
        coverage_ok = (
            coverage.get("status") in {"COMPLETE", "COMPLETE_WITH_NUMERIC_TOLERANCE"}
            or coverage_status in _F05_ACCEPTED_COVERAGE
        )
        if any(provenance.get(field) in (None, "", []) for field in REQUIRED_PROVENANCE):
            signal, explanation = "NEEDS_VERIFICATION", "F05_EXPL_INCOMPLETE"
            state = "CLIMATE_CONTEXT_INCOMPLETE"
        elif precip.get("value_mm") is None:
            signal, explanation = "NEEDS_VERIFICATION", "F05_EXPL_INCOMPLETE"
            state = "CLIMATE_CONTEXT_INCOMPLETE"
        elif unit not in _F05_ACCEPTED_UNITS:
            signal, explanation = "NEEDS_VERIFICATION", "F05_EXPL_INCOMPLETE"
            state = "CLIMATE_CONTEXT_INCOMPLETE"
        elif not period:
            signal, explanation = "NEEDS_VERIFICATION", "F05_EXPL_INCOMPLETE"
            state = "CLIMATE_CONTEXT_INCOMPLETE"
        elif not coverage_ok:
            signal, explanation = "NEEDS_VERIFICATION", "F05_EXPL_INCOMPLETE"
            state = "CLIMATE_CONTEXT_INCOMPLETE"

    return {
        "factor_id": "F05_CLIMATE_DROUGHT_EXPOSURE",
        "signal": signal,
        "ranking_effect": "NONE",
        "explanation_code": explanation,
        "input_quality_state": state,
        "canonical_precip_mm": precip.get("value_mm"),
        "canonical_precip_unit": precip.get("unit_normalized") or precip.get("unit"),
        "normals_period": precip.get("normals_period"),
        "mutates_f02": False,
        "mutates_f03": False,
        "mutates_f04": False,
    }


def _evaluate_f06(factor: dict[str, Any]) -> dict[str, Any]:
    from rangematch.f06_derivation import evaluate_f06_signal

    return evaluate_f06_signal(factor or None)


def _evaluate_f07(factor: dict[str, Any]) -> dict[str, Any]:
    from rangematch.f07_derivation import evaluate_f07_signal

    return evaluate_f07_signal(factor or None)


def _evaluate_f08(factor: dict[str, Any]) -> dict[str, Any]:
    from rangematch.f08_derivation import evaluate_f08_signal

    return evaluate_f08_signal(factor or None)


def evaluate_land_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Return a reproducible two-operation MatchResult without LLM judgment."""
    factors = profile.get("factors") or {}
    factor_results = {
        "F01_TOPOGRAPHY": _evaluate_f01(factors.get("F01_TOPOGRAPHY", {})),
        "F02_HERBACEOUS_RESOURCE": _evaluate_f02(
            factors.get("F02_HERBACEOUS_RESOURCE", {})
        ),
        "F03_LIVESTOCK_WATER": _evaluate_f03(
            factors.get("F03_LIVESTOCK_WATER", {})
        ),
        "F04_SOIL_WETNESS_ECOLOGICAL_SITE": _evaluate_f04(
            factors.get("F04_SOIL_WETNESS_ECOLOGICAL_SITE", {})
        ),
        "F05_CLIMATE_DROUGHT_EXPOSURE": _evaluate_f05(
            factors.get("F05_CLIMATE_DROUGHT_EXPOSURE", {})
        ),
        "F06_PARCEL_CONFIGURATION": _evaluate_f06(
            factors.get("F06_PARCEL_CONFIGURATION", {})
        ),
        "F07_ROAD_AND_PHYSICAL_ACCESS": _evaluate_f07(
            factors.get("F07_ROAD_AND_PHYSICAL_ACCESS", {})
        ),
        "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE": _evaluate_f08(
            factors.get("F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE", {})
        ),
    }
    operation_results = {}
    for operation in SUPPORTED_OPERATIONS:
        operation_results[operation] = {
            "decision_label": "HOLD",
            "decision_reason": (
                "Shared Factor evidence is implemented as data-quality/context only; "
                "material verification remains incomplete and no directional suitability "
                "threshold is approved."
            ),
            "factor_evaluations": deepcopy(factor_results),
            "ranking_position": None,
        }

    unknowns = list(profile.get("unknowns") or [])
    if factor_results["F02_HERBACEOUS_RESOURCE"]["signal"] == "NEEDS_VERIFICATION":
        unknowns.append("F02 eligible, masked, no-data, and valid parcel areas are not quantified.")
    if factor_results["F03_LIVESTOCK_WATER"]["signal"] == "NEEDS_VERIFICATION":
        f03 = factors.get("F03_LIVESTOCK_WATER") or {}
        summary = f03.get("remote_evidence_summary") or {}
        if summary:
            unknowns.append(
                "F03 has mapped candidates and optional remote support, but no FIELD_VERIFIED "
                "livestock-water system; REMOTELY_SUPPORTED does not mean usable livestock water."
            )
            unknowns.append(
                "F03 water reliability, capacity, quality, livestock accessibility, and legal "
                "access remain unresolved; verified_count == 0 does not mean the land has no water."
            )
            if summary.get("unreviewed_candidates"):
                unknowns.append(
                    "F03 unsampled mapped candidates are UNREVIEWED, not absent or rejected."
                )
        else:
            unknowns.append(
                "F03 mapped water candidates are not verified livestock-water systems; "
                "reliability, capacity, quality, legal access, and traversable distance remain unknown."
            )
    if factor_results["F04_SOIL_WETNESS_ECOLOGICAL_SITE"]["signal"] in {
        "CONTEXT_DEPENDENT",
        "NEEDS_VERIFICATION",
    }:
        unknowns.append(
            "F04 soil, wetness, and ecological-site facts are context only; they do not establish current vegetation state, forage productivity, or operation ranking."
        )
    if factor_results["F05_CLIMATE_DROUGHT_EXPOSURE"]["signal"] in {
        "CONTEXT_DEPENDENT",
        "NEEDS_VERIFICATION",
    }:
        unknowns.append(
            "F05 climate and drought facts are context only; mean annual precipitation and current USDM class do not establish suitability, carrying capacity, or forage/water failure."
        )
    if factor_results["F06_PARCEL_CONFIGURATION"]["signal"] in {
        "CONTEXT_DEPENDENT",
        "NEEDS_VERIFICATION",
        "UNKNOWN",
    }:
        unknowns.append(
            "F06 parcel area, perimeter, and compactness are geometric context only; "
            "they do not establish suitability, fencing cost, carrying capacity, or access."
        )
    if factor_results["F07_ROAD_AND_PHYSICAL_ACCESS"]["signal"] in {
        "CONTEXT_DEPENDENT",
        "NEEDS_VERIFICATION",
        "UNKNOWN",
    }:
        unknowns.append(
            "F07 mapped road proximity/contact is physical context only; "
            "it does not establish legal access, usable entrance, travel time, or landlocked certainty."
        )
    if factor_results["F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"]["signal"] in {
        "CONTEXT_DEPENDENT",
        "NEEDS_VERIFICATION",
        "UNKNOWN",
    }:
        unknowns.append(
            "F08 shrub/tree fractional cover is woody-structure context only; "
            "it does not establish browse availability, obstruction, herbaceous failure, "
            "or Cow-Calf versus Sheep ranking; shared RAP coverage may remain unquantified."
        )

    canonical_input = json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
    input_hash = hashlib.sha256(canonical_input).hexdigest()
    return {
        "match_result_schema_version": "0.1.0",
        "engine_version": "0.1.0",
        "input_sha256": input_hash,
        "land_profile_id": profile.get("land_profile_id"),
        "land_profile_version": profile.get("version"),
        "supported_operations": list(SUPPORTED_OPERATIONS),
        "operation_results": operation_results,
        "cross_profile_comparison": {
            "ranking_permitted": False,
            "reason": (
                "Implemented Factors have no ranking effect; F02 coverage is unquantified, "
                "F03 water systems are unverified, F05 has no approved climate suitability "
                "threshold, F06 geometry metrics are context only, F07 mapped roads do "
                "not establish legal access, and F08 woody cover does not establish browse, "
                "obstruction, or species ranking; no reviewed differential rule is active."
            ),
        },
        "unknowns": sorted(set(unknowns)),
        "diligence_actions": [
            "Quantify RAP eligible, masked, no-data, and valid parcel areas when raster access is available.",
            "Verify botanical composition, palatability, and nutritive value with reviewed local or field evidence.",
            "Verify livestock-water source operation, seasonal reliability, capacity, quality, legal access, and animal-access routes in field and records; do not treat REMOTELY_SUPPORTED or verified_count == 0 as proof of usable or absent water.",
            "Review remaining UNREVIEWED mapped water candidates if remote or field evidence becomes available; unreviewed is not absent or rejected.",
            "Field-verify soil restrictive layers, wetness interpretation, and whether ecological-site reference communities match current vegetation.",
            "Retain canonical NOAA/NCEI precipitation normals with period, unit, coverage, and provenance; treat current USDM as current-condition context only.",
            "Treat F06 area/perimeter/compactness as geometric context only; do not infer fencing cost, carrying capacity, or suitability.",
            "Treat F07 mapped road contact/distance as physical context only; verify legal access and usable entrance separately; do not infer landlocked certainty from an empty search window.",
            "Treat F08 shrub/tree fractions and combined modeled woody cover as vegetation-structure context only; do not infer browse, obstruction, herbaceous failure, or Cow-Calf versus Sheep ranking; keep F02/F08 RAP artifact/year/mask/coverage aligned.",
            "Evaluate the remaining approved shared Factors before an ADVANCE, REDIRECT, or REJECT decision.",
        ],
        "llm_override_permitted": False,
    }
