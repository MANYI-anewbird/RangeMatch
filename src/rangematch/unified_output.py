"""Unified output envelope projection for F01–F08 Product Prototype.

Projects existing Land Profile + MatchResult into RANGEMATCH_UNIFIED_OUTPUT@0.1.0.
Does not alter Factor science, decisions, ranking, or source fixtures.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

CONTRACT_VERSION = "RANGEMATCH_UNIFIED_OUTPUT@0.1.0"
SCHEMA_RELATIVE_PATH = "docs/schemas/rangematch_unified_output.schema.json"

FACTOR_IDS = (
    "F01_TOPOGRAPHY",
    "F02_HERBACEOUS_RESOURCE",
    "F03_LIVESTOCK_WATER",
    "F04_SOIL_WETNESS_ECOLOGICAL_SITE",
    "F05_CLIMATE_DROUGHT_EXPOSURE",
    "F06_PARCEL_CONFIGURATION",
    "F07_ROAD_AND_PHYSICAL_ACCESS",
    "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE",
)

SUPPORTED_OPERATIONS = ("COW_CALF_OPERATION", "SHEEP_GRAZING")
ALLOWED_MODES = ("GOAL_DIRECTED", "DISCOVERY")
ALLOWED_DECISION_LABELS = ("ADVANCE", "REVIEW", "HOLD", "REDIRECT", "REJECT")
ALLOWED_SIGNALS = ("CONTEXT_DEPENDENT", "NEEDS_VERIFICATION", "UNKNOWN")

BUYER_SECTIONS = (
    "Property",
    "Land & Resources",
    "Resilience & Hazards",
    "Operation Comparison",
    "Diligence Plan",
)

# Keys excluded from canonical MatchResult hashing.
_HASH_EXCLUDED_KEY_EXACT = frozenset(
    {
        "created_at",
        "fetched_at",
        "derived_at",
        "accessed_at",
        "cache_hit",
        "request_id",
        "transient_request_id",
        "ui_order",
        "presentation_order",
        "llm_prose",
        "llm_explanation",
        "explanation_text",
        "explanation_prose",
    }
)
_HASH_EXCLUDED_KEY_SUFFIXES = ("_path", "_cache_dir", "_cache_path")
_HASH_EXCLUDED_KEY_PREFIXES = ("llm_", "ui_", "cache_")
_CACHE_PATH_RE = re.compile(r"(^|/)(cache|tiger2025_cache)(/|$)", re.IGNORECASE)

# Coverage alias → normalized_status. Source status is always preserved separately.
COVERAGE_NORMALIZATION = {
    "COMPLETE": "COMPLETE",
    "COMPLETE_RANGELAND_COVERAGE": "COMPLETE",
    "COMPLETE_WITH_NUMERIC_TOLERANCE": "COMPLETE",
    "PARTIAL": "PARTIAL",
    "PARTIAL_RANGELAND_COVERAGE": "PARTIAL",
    "COVERAGE_UNQUANTIFIED": "UNQUANTIFIED",
    "UNQUANTIFIED": "UNQUANTIFIED",
    "OUTSIDE_SUPPORTED_GEOGRAPHY": "OUTSIDE_SCOPE",
    "OUTSIDE_DOCUMENTED_PRODUCT_SCOPE": "OUTSIDE_SCOPE",
    "OUTSIDE_SCOPE": "OUTSIDE_SCOPE",
    "MISSING": "UNKNOWN",
    "UNKNOWN": "UNKNOWN",
    "NOT_APPLICABLE": "NOT_APPLICABLE",
}

F07_LEGAL_DILIGENCE_KEYWORDS = (
    "legal access",
    "usable entrance",
    "landlocked",
    "easement",
    "deeded",
    "passability",
    "private ranch road",
    "gate",
)


class UnifiedOutputError(ValueError):
    """Raised when unified-output validation fails."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_schema(repo_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[2]
    return json.loads((root / SCHEMA_RELATIVE_PATH).read_text())


def normalize_coverage_status(source_status: Any) -> str:
    if source_status is None or source_status == "":
        return "UNKNOWN"
    key = str(source_status).strip()
    return COVERAGE_NORMALIZATION.get(key, "UNKNOWN")


def build_coverage_record(
    source_status: Any,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "normalized_status": normalize_coverage_status(source_status),
        "source_status": None if source_status is None else str(source_status),
        "details": dict(details or {}),
    }


def _should_exclude_hash_key(key: str) -> bool:
    if key in _HASH_EXCLUDED_KEY_EXACT:
        return True
    if any(key.startswith(prefix) for prefix in _HASH_EXCLUDED_KEY_PREFIXES):
        return True
    if any(key.endswith(suffix) for suffix in _HASH_EXCLUDED_KEY_SUFFIXES):
        return True
    return False


def _sanitize_for_hash(value: Any) -> Any:
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_s = str(key)
            if _should_exclude_hash_key(key_s):
                continue
            if isinstance(item, str) and _CACHE_PATH_RE.search(item):
                continue
            sanitized = _sanitize_for_hash(item)
            if sanitized is not None or item is None:
                out[key_s] = sanitized
        return out
    if isinstance(value, list):
        return [_sanitize_for_hash(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_for_hash(item) for item in value]
    return value


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_canonical(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def hash_match_result(match_result: Mapping[str, Any]) -> str:
    """Deterministic MatchResult hash excluding volatile / UI / prose fields."""
    sanitized = _sanitize_for_hash(deepcopy(dict(match_result)))
    return sha256_canonical(sanitized)


def validate_one_parcel_geometry(geometry: Mapping[str, Any] | None) -> None:
    """Reject multi-parcel / batch geometries. One Feature only."""
    if geometry is None:
        return
    gtype = geometry.get("type")
    if gtype == "FeatureCollection":
        features = geometry.get("features") or []
        if len(features) != 1:
            raise UnifiedOutputError(
                f"one_parcel_only: FeatureCollection must contain exactly one Feature; got {len(features)}"
            )
    elif gtype == "Feature":
        return
    elif gtype in {"Polygon", "MultiPolygon"}:
        return
    else:
        raise UnifiedOutputError(
            f"one_parcel_only: unsupported geometry type for product run: {gtype}"
        )


def validate_run_mode(
    mode: str,
    intended_operation: str | None,
) -> None:
    if mode not in ALLOWED_MODES:
        raise UnifiedOutputError(f"invalid mode: {mode}")
    if mode == "DISCOVERY":
        if intended_operation is not None:
            raise UnifiedOutputError(
                "DISCOVERY requires intended_operation=null"
            )
    elif mode == "GOAL_DIRECTED":
        if intended_operation not in SUPPORTED_OPERATIONS:
            raise UnifiedOutputError(
                "GOAL_DIRECTED requires intended_operation in "
                f"{SUPPORTED_OPERATIONS}"
            )


def _extract_source_coverage(factor: Mapping[str, Any]) -> tuple[Any, dict[str, Any]]:
    coverage = factor.get("coverage")
    if isinstance(coverage, Mapping):
        status = coverage.get("status")
        details = {k: v for k, v in coverage.items() if k != "status"}
        return status, details
    # Land-fact based Factors (F02): use first land_fact coverage if present.
    for fact in factor.get("land_facts") or []:
        if isinstance(fact, Mapping) and isinstance(fact.get("coverage"), Mapping):
            cov = fact["coverage"]
            status = cov.get("status")
            details = {k: v for k, v in cov.items() if k != "status"}
            return status, details
    # F07 uses road_source_coverage_status
    if factor.get("road_source_coverage_status") is not None:
        return factor.get("road_source_coverage_status"), {
            "county_coverage": factor.get("county_coverage"),
        }
    if factor.get("coverage_status") is not None:
        return factor.get("coverage_status"), {}
    return None, {}


def _project_land_fact(
    fact: Mapping[str, Any],
    *,
    default_geometry_hash: str | None,
    default_algorithm: str | None,
) -> dict[str, Any]:
    observation = fact.get("observation") or {}
    source = fact.get("source") or {}
    provenance = fact.get("provenance") or {}
    applicability = fact.get("applicability") or {}
    quality = fact.get("quality") or {}
    coverage_obj = fact.get("coverage") if isinstance(fact.get("coverage"), Mapping) else {}
    source_status = coverage_obj.get("status")
    coverage_details = {k: v for k, v in coverage_obj.items() if k != "status"}

    raw_value = None
    if "raw_rap_shr_percent" in provenance and fact.get("variable_id") == "VAR_F08_SHRUB_COVER_FRACTION":
        raw_value = provenance.get("raw_rap_shr_percent")
    elif "raw_rap_tre_percent" in provenance and fact.get("variable_id") == "VAR_F08_TREE_COVER_FRACTION":
        raw_value = provenance.get("raw_rap_tre_percent")
    elif "raw_value" in fact:
        raw_value = fact.get("raw_value")
    elif "raw_value" in observation:
        raw_value = observation.get("raw_value")

    return {
        "variable_id": fact.get("variable_id"),
        "value": observation.get("value"),
        "unit": observation.get("unit"),
        "raw_value": raw_value,
        "spatial_semantics": observation.get("spatial_semantics"),
        "temporal_semantics": observation.get("temporal_semantics"),
        "geometry_hash": provenance.get("geometry_hash") or default_geometry_hash,
        "source_id": (
            provenance.get("canonical_source_id")
            or provenance.get("source_reference")
            or source.get("product")
        ),
        "source_version": source.get("version") or provenance.get("source_product_and_version"),
        "artifact_hash": provenance.get("response_or_artifact_hash"),
        "derivation_algorithm_version": (
            provenance.get("algorithm_version")
            or provenance.get("derivation_spec_version")
            or default_algorithm
        ),
        "applicability_status": applicability.get("domain_status"),
        "coverage": build_coverage_record(source_status, coverage_details),
        "confidence_or_quality_status": quality.get("confidence_state"),
        "limitations": list(fact.get("limitations") or []),
    }


def _project_scalar_measurements_as_facts(
    factor_id: str,
    factor: Mapping[str, Any],
    geometry_hash: str | None,
) -> list[dict[str, Any]]:
    """Project common scalar factor fields when land_facts[] is absent."""
    projected: list[dict[str, Any]] = []
    algorithm = factor.get("algorithm_version") or factor.get("derivation_spec")
    source_status, details = _extract_source_coverage(factor)
    coverage = build_coverage_record(source_status, details)
    applicability_status = None
    if isinstance(factor.get("applicability"), Mapping):
        applicability_status = factor["applicability"].get("domain_status")
    elif factor.get("applicability_status") is not None:
        applicability_status = factor.get("applicability_status")

    def add(variable_id: str, value: Any, unit: str | None, *, raw_value: Any = None) -> None:
        if value is None and raw_value is None:
            return
        projected.append(
            {
                "variable_id": variable_id,
                "value": value,
                "unit": unit,
                "raw_value": raw_value,
                "spatial_semantics": "parcel_aggregate",
                "temporal_semantics": None,
                "geometry_hash": geometry_hash or factor.get("geometry_hash"),
                "source_id": factor.get("canonical_source_id") or factor.get("road_source_id"),
                "source_version": factor.get("road_product_vintage") or factor.get("algorithm_version"),
                "artifact_hash": (
                    (factor.get("provenance") or {}).get("response_or_artifact_hash")
                    or factor.get("response_or_artifact_hash")
                    or factor.get("road_artifact_hash")
                ),
                "derivation_algorithm_version": algorithm,
                "applicability_status": applicability_status,
                "coverage": coverage,
                "confidence_or_quality_status": None,
                "limitations": list(factor.get("limitations") or [])[:1],
            }
        )

    if factor_id == "F01_TOPOGRAPHY":
        summary = factor.get("summary") or {}
        add("VAR_F01_ELEVATION_MEDIAN_M", summary.get("elevation_median_m"), "m")
        add("VAR_F01_SLOPE_MEDIAN_DEGREES", summary.get("slope_median_degrees"), "degree")
    elif factor_id == "F03_LIVESTOCK_WATER":
        add(
            "VAR_F03_MAPPED_WATER_CANDIDATE_COUNT",
            factor.get("mapped_candidate_count"),
            "count",
        )
        add(
            "VAR_F03_FIELD_VERIFIED_LIVESTOCK_WATER_COUNT",
            factor.get("field_verified_count")
            if factor.get("field_verified_count") is not None
            else factor.get("verified_livestock_water_system_count"),
            "count",
        )
        distance_context = factor.get("euclidean_distance_to_mapped_candidate_m") or {}
        add(
            "VAR_F03_EUCLIDEAN_DISTANCE_TO_MAPPED_CANDIDATE_MEDIAN_M",
            distance_context.get("median"),
            "m",
        )
    elif factor_id == "F04_SOIL_WETNESS_ECOLOGICAL_SITE":
        parcel_coverage = factor.get("parcel_coverage") or {}
        add(
            "VAR_F04_SDA_VALID_COVERAGE_FRACTION",
            parcel_coverage.get("coverage_fraction"),
            "fraction",
        )
        add(
            "VAR_F04_KNOWN_COMPONENT_SHARE",
            factor.get("known_component_share"),
            "fraction",
        )
    elif factor_id == "F05_CLIMATE_DROUGHT_EXPOSURE":
        precip = factor.get("canonical_precipitation") or {}
        add(
            precip.get("variable_id") or "VAR_F05_MEAN_ANNUAL_PRECIPITATION",
            precip.get("value_mm"),
            precip.get("unit_normalized") or "mm/year",
        )
    elif factor_id == "F06_PARCEL_CONFIGURATION":
        add("VAR_F06_AREA_M2", factor.get("area_m2") or (factor.get("measurements") or {}).get("area_m2"), "m2")
        add(
            "VAR_F06_PERIMETER_M",
            factor.get("perimeter_m") or (factor.get("measurements") or {}).get("perimeter_m"),
            "m",
        )
    elif factor_id == "F07_ROAD_AND_PHYSICAL_ACCESS":
        add(
            "VAR_F07_NEAREST_MAPPED_ROAD_DISTANCE_M",
            factor.get("nearest_mapped_road_distance_m"),
            "m",
        )
        add(
            "VAR_F07_MAPPED_ROAD_FEATURE_COUNT_IN_SEARCH_WINDOW",
            factor.get("mapped_road_feature_count_in_search_window"),
            "count",
        )
    elif factor_id == "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE":
        add(
            "VAR_F08_SHRUB_COVER_FRACTION",
            factor.get("shrub_cover_fraction"),
            "fraction",
            raw_value=factor.get("raw_rap_shr_percent"),
        )
        add(
            "VAR_F08_TREE_COVER_FRACTION",
            factor.get("tree_cover_fraction"),
            "fraction",
            raw_value=factor.get("raw_rap_tre_percent"),
        )
        add(
            "VAR_F08_COMBINED_MODELED_WOODY_COVER_FRACTION",
            factor.get("combined_modeled_woody_cover_fraction"),
            "fraction",
        )
    elif factor_id == "F05_CLIMATE_DROUGHT_EXPOSURE":
        precip = factor.get("canonical_precip") or factor.get("precipitation") or {}
        if isinstance(precip, Mapping):
            add("VAR_F05_MEAN_ANNUAL_PRECIP_MM", precip.get("value_mm"), precip.get("unit") or "mm")
        elif factor.get("canonical_precip_mm") is not None:
            add("VAR_F05_MEAN_ANNUAL_PRECIP_MM", factor.get("canonical_precip_mm"), "mm")
    return projected


def project_factor_result(
    factor_id: str,
    profile_factor: Mapping[str, Any] | None,
    evaluation: Mapping[str, Any] | None,
    *,
    geometry_hash: str | None,
) -> dict[str, Any]:
    profile_factor = profile_factor or {}
    evaluation = evaluation or {}
    signal = evaluation.get("signal") or "UNKNOWN"
    if signal not in ALLOWED_SIGNALS:
        signal = "UNKNOWN"

    land_facts_raw = profile_factor.get("land_facts") or []
    land_facts = [
        _project_land_fact(
            fact,
            default_geometry_hash=geometry_hash,
            default_algorithm=profile_factor.get("algorithm_version")
            or profile_factor.get("derivation_spec"),
        )
        for fact in land_facts_raw
        if isinstance(fact, Mapping)
    ]
    if not land_facts:
        land_facts = _project_scalar_measurements_as_facts(
            factor_id, profile_factor, geometry_hash
        )

    source_status, details = _extract_source_coverage(profile_factor)
    if source_status is None and evaluation.get("coverage_status") is not None:
        source_status = evaluation.get("coverage_status")

    applicability = profile_factor.get("applicability")
    if not isinstance(applicability, Mapping):
        applicability = {
            "domain_status": profile_factor.get("applicability_status")
            or evaluation.get("applicability_status")
        }

    provenance = profile_factor.get("provenance")
    if not isinstance(provenance, Mapping):
        provenance = {
            "geometry_hash": profile_factor.get("geometry_hash") or geometry_hash,
            "response_or_artifact_hash": profile_factor.get("response_or_artifact_hash")
            or profile_factor.get("road_artifact_hash"),
            "algorithm_version": profile_factor.get("algorithm_version"),
        }

    return {
        "factor_id": factor_id,
        "factor_version": profile_factor.get("algorithm_version")
        or profile_factor.get("derivation_spec")
        or evaluation.get("algorithm_version"),
        "input_quality_state": evaluation.get("input_quality_state")
        or profile_factor.get("input_quality_state")
        or "MISSING",
        "signal": signal,
        "ranking_effect": evaluation.get("ranking_effect")
        or profile_factor.get("ranking_effect")
        or "NONE",
        "land_facts": land_facts,
        "applicability": dict(applicability),
        "coverage": build_coverage_record(source_status, details),
        "provenance": dict(provenance),
        "limitations": list(profile_factor.get("limitations") or []),
        "unknowns": list(profile_factor.get("unknowns") or []),
        "diligence_actions": list(profile_factor.get("diligence_actions") or []),
        "explanation_code": evaluation.get("explanation_code"),
        "evaluation_extras": {
            k: v
            for k, v in evaluation.items()
            if k
            not in {
                "factor_id",
                "signal",
                "ranking_effect",
                "explanation_code",
                "input_quality_state",
            }
        },
    }


def project_jurisdiction(
    land_profile: Mapping[str, Any],
    *,
    mireye_context: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Jurisdiction container is required; values may be null."""
    explicit = land_profile.get("jurisdiction")
    if isinstance(explicit, Mapping) and explicit.get("resolution_status"):
        return {
            "resolution_status": explicit.get("resolution_status"),
            "county": explicit.get("county"),
            "state": explicit.get("state"),
            "county_fips": explicit.get("county_fips"),
            "zoning": explicit.get("zoning"),
            "notes": explicit.get("notes"),
        }

    county = state = county_fips = zoning = None
    for item in mireye_context or []:
        if item.get("context_type") != "PROPERTY_DILIGENCE_CONTEXT":
            continue
        fields = item.get("fields") or {}
        candidate = item.get("parcel_candidate") or {}
        county = county or fields.get("county") or fields.get("county_name") or candidate.get("county")
        state = state or fields.get("state") or fields.get("state_code") or candidate.get("state")
        county_fips = county_fips or fields.get("county_fips") or fields.get("fips") or candidate.get("county_fips")
        zoning = zoning or fields.get("zoning") or candidate.get("zoning")

    # Infer from F07 county coverage when present (CPER Weld / 08123).
    f07 = (land_profile.get("factors") or {}).get("F07_ROAD_AND_PHYSICAL_ACCESS") or {}
    cov = f07.get("county_coverage") or {}
    loaded = cov.get("loaded_county_fips") or []
    if loaded and not county_fips:
        county_fips = loaded[0]
        if county_fips == "08123":
            county = county or "Weld"
            state = state or "CO"

    if county or state or county_fips or zoning:
        status = "RESOLVED" if (county and state and county_fips) else "PARTIAL"
    else:
        # Prototype default when Property Diligence was not invoked.
        status = "NOT_REQUESTED"

    return {
        "resolution_status": status,
        "county": county,
        "state": state,
        "county_fips": county_fips,
        "zoning": zoning,
        "notes": None,
    }


def _is_legal_diligence_text(text: str) -> bool:
    lower = text.lower()
    return any(token in lower for token in F07_LEGAL_DILIGENCE_KEYWORDS)


def _operation_presentation_order(
    mode: str,
    intended_operation: str | None,
) -> dict[str, int | None]:
    """UI order only — not scientific priority."""
    if mode == "GOAL_DIRECTED" and intended_operation in SUPPORTED_OPERATIONS:
        peer = (
            "SHEEP_GRAZING"
            if intended_operation == "COW_CALF_OPERATION"
            else "COW_CALF_OPERATION"
        )
        return {intended_operation: 0, peer: 1}
    return {"COW_CALF_OPERATION": 0, "SHEEP_GRAZING": 1}


def project_operations(
    match_result: Mapping[str, Any],
    *,
    mode: str,
    intended_operation: str | None,
    global_unknowns: Sequence[str],
) -> dict[str, Any]:
    order = _operation_presentation_order(mode, intended_operation)
    ranking_permitted = bool(
        (match_result.get("cross_profile_comparison") or {}).get("ranking_permitted")
    )
    operations: dict[str, Any] = {}
    for operation_id in SUPPORTED_OPERATIONS:
        body = (match_result.get("operation_results") or {}).get(operation_id) or {}
        factor_evals = body.get("factor_evaluations") or {}
        supporting = []
        limiting = []
        for fid, ev in factor_evals.items():
            sig = (ev or {}).get("signal")
            if sig == "CONTEXT_DEPENDENT":
                supporting.append(fid)
            elif sig in {"NEEDS_VERIFICATION", "UNKNOWN"}:
                limiting.append(fid)
        decision = body.get("decision_label") or "HOLD"
        if decision not in ALLOWED_DECISION_LABELS:
            raise UnifiedOutputError(f"invalid decision_label: {decision}")
        operations[operation_id] = {
            "operation_id": operation_id,
            "operation_profile_version": match_result.get("land_profile_version"),
            "decision_label": decision,
            "decision_reason": body.get("decision_reason"),
            "factor_evaluations": deepcopy(factor_evals),
            "hard_constraints": [],
            "supporting_signals": supporting,
            "limiting_signals": limiting,
            "unknowns": list(global_unknowns),
            "confidence_limitation": body.get("decision_reason")
            or "Evidence remains incomplete for a stronger decision label.",
            "ranking_permission": ranking_permitted,
            "ranking_position": body.get("ranking_position"),
            "presentation_priority": order.get(operation_id),
        }
    return operations


def _uniq_strings(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def build_buyer_report(
    factors: Mapping[str, Any],
    operations: Mapping[str, Any],
    *,
    mireye_context: Sequence[Mapping[str, Any]],
    global_unknowns: Sequence[str],
    global_diligence: Sequence[str],
    mode: str,
    intended_operation: str | None,
) -> dict[str, Any]:
    f07 = factors.get("F07_ROAD_AND_PHYSICAL_ACCESS") or {}
    f07_unknowns = list(f07.get("unknowns") or [])
    f07_limits = list(f07.get("limitations") or [])
    f07_actions = list(f07.get("diligence_actions") or [])

    f07_physical_limits = [x for x in f07_limits if not _is_legal_diligence_text(x)]
    f07_physical_unknowns = [x for x in f07_unknowns if not _is_legal_diligence_text(x)]
    f07_physical_actions = [x for x in f07_actions if not _is_legal_diligence_text(x)]
    f07_legal_limits = [x for x in f07_limits if _is_legal_diligence_text(x)]
    f07_legal_unknowns = [x for x in f07_unknowns if _is_legal_diligence_text(x)]
    f07_legal_actions = [x for x in f07_actions if _is_legal_diligence_text(x)]
    global_legal = [x for x in global_diligence if _is_legal_diligence_text(x)]
    global_legal_unknowns = [x for x in global_unknowns if _is_legal_diligence_text(x)]

    def section(
        section_id: str,
        factor_ids: list[str],
        *,
        extras_unknowns: list[str] | None = None,
        extras_limits: list[str] | None = None,
        extras_actions: list[str] | None = None,
        mireye_types: list[str] | None = None,
        highlights: list[Any] | None = None,
        skip_factor_text: bool = False,
    ) -> dict[str, Any]:
        unknowns: list[str] = []
        limitations: list[str] = []
        actions: list[str] = []
        if not skip_factor_text:
            for fid in factor_ids:
                fr = factors.get(fid) or {}
                # F07 legal/access texts are reserved for Diligence Plan.
                if fid == "F07_ROAD_AND_PHYSICAL_ACCESS":
                    unknowns.extend(f07_physical_unknowns)
                    limitations.extend(f07_physical_limits)
                    actions.extend(f07_physical_actions)
                else:
                    unknowns.extend(fr.get("unknowns") or [])
                    limitations.extend(fr.get("limitations") or [])
                    actions.extend(fr.get("diligence_actions") or [])
                if fr.get("coverage", {}).get("normalized_status") == "UNQUANTIFIED":
                    limitations.append(
                        f"{fid} coverage_status remains unquantified (source preserved)."
                    )
        unknowns.extend(extras_unknowns or [])
        limitations.extend(extras_limits or [])
        actions.extend(extras_actions or [])

        return {
            "section_id": section_id,
            "factor_ids": factor_ids,
            "highlights": highlights or [
                {
                    "factor_id": fid,
                    "signal": (factors.get(fid) or {}).get("signal"),
                    "input_quality_state": (factors.get(fid) or {}).get(
                        "input_quality_state"
                    ),
                }
                for fid in factor_ids
            ],
            "unknowns": _uniq_strings(unknowns),
            "limitations": _uniq_strings(limitations),
            "diligence_actions": _uniq_strings(actions),
            "mireye_context_types": mireye_types or [],
        }

    op_highlights = []
    ordered_ops = sorted(
        operations.items(),
        key=lambda kv: (
            kv[1].get("presentation_priority")
            if kv[1].get("presentation_priority") is not None
            else 99
        ),
    )
    for op_id, body in ordered_ops:
        op_highlights.append(
            {
                "operation_id": op_id,
                "decision_label": body.get("decision_label"),
                "ranking_permission": body.get("ranking_permission"),
                "limiting_signals": body.get("limiting_signals"),
                "presentation_priority": body.get("presentation_priority"),
            }
        )
    if mode == "DISCOVERY":
        op_highlights.append(
            {
                "qualification": (
                    "Comparison applies only to currently supported Profiles "
                    "(Cow-Calf and Sheep Grazing)."
                )
            }
        )
    if mode == "GOAL_DIRECTED":
        op_highlights.append(
            {
                "qualification": (
                    f"Intended operation {intended_operation} is presented first; "
                    "no scientific priority or modified rules."
                )
            }
        )

    hazard_types = [
        item.get("context_type")
        for item in mireye_context
        if item.get("context_type") == "POINT_HAZARD_CONTEXT"
    ]
    property_mireye = [
        item.get("context_type")
        for item in mireye_context
        if item.get("context_type") == "PROPERTY_DILIGENCE_CONTEXT"
    ]

    return {
        "Property": section(
            "Property",
            ["F06_PARCEL_CONFIGURATION", "F07_ROAD_AND_PHYSICAL_ACCESS"],
            mireye_types=[t for t in property_mireye if t],
            highlights=[
                {
                    "f07_projection": "physical_road_context",
                    "canonical_factor_id": "F07_ROAD_AND_PHYSICAL_ACCESS",
                    "road_parcel_contact_status": (
                        (factors.get("F07_ROAD_AND_PHYSICAL_ACCESS") or {})
                        .get("evaluation_extras", {})
                        .get("road_parcel_contact_status")
                    ),
                    "signal": (factors.get("F07_ROAD_AND_PHYSICAL_ACCESS") or {}).get(
                        "signal"
                    ),
                },
                {
                    "factor_id": "F06_PARCEL_CONFIGURATION",
                    "signal": (factors.get("F06_PARCEL_CONFIGURATION") or {}).get(
                        "signal"
                    ),
                },
            ],
        ),
        "Land & Resources": section(
            "Land & Resources",
            [
                "F01_TOPOGRAPHY",
                "F02_HERBACEOUS_RESOURCE",
                "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE",
                "F04_SOIL_WETNESS_ECOLOGICAL_SITE",
                "F03_LIVESTOCK_WATER",
            ],
            mireye_types=["POINT_LAND_CONTEXT"]
            if any(i.get("context_type") == "POINT_LAND_CONTEXT" for i in mireye_context)
            else [],
        ),
        "Resilience & Hazards": section(
            "Resilience & Hazards",
            ["F05_CLIMATE_DROUGHT_EXPOSURE"],
            mireye_types=[t for t in hazard_types if t],
        ),
        "Operation Comparison": {
            "section_id": "Operation Comparison",
            "factor_ids": list(FACTOR_IDS),
            "highlights": op_highlights,
            "unknowns": list(global_unknowns),
            "limitations": [
                "No numeric suitability score is authorized.",
                "ranking_effect NONE cannot create cross-profile ranking.",
                "HOLD does not mean unsuitable.",
            ],
            "diligence_actions": list(global_diligence),
            "mireye_context_types": [],
        },
        "Diligence Plan": section(
            "Diligence Plan",
            [],
            skip_factor_text=True,
            extras_unknowns=f07_legal_unknowns + global_legal_unknowns,
            extras_limits=f07_legal_limits
            + [
                "Dynamic regulatory/land-rights findings are non-canonical and not F09.",
                "F07 remains one canonical Factor result; legal-access items are surfaced here.",
            ],
            extras_actions=_uniq_strings(
                f07_legal_actions + global_legal + list(global_diligence)
            ),
            highlights=[
                {
                    "f07_projection": "legal_access_diligence",
                    "canonical_factor_id": "F07_ROAD_AND_PHYSICAL_ACCESS",
                }
            ],
        ),
    }


def project_unified_output(
    land_profile: Mapping[str, Any],
    match_result: Mapping[str, Any],
    *,
    mode: str = "DISCOVERY",
    intended_operation: str | None = None,
    planned_actions: Sequence[str] | None = None,
    run_id: str | None = None,
    created_at: str | None = None,
    mireye_context: Sequence[Mapping[str, Any]] | None = None,
    dynamic_diligence_findings: Sequence[Mapping[str, Any]] | None = None,
    geometry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project Land Profile + MatchResult into the unified output envelope."""
    validate_run_mode(mode, intended_operation)
    validate_one_parcel_geometry(geometry)

    planned = list(planned_actions or [])
    mireye = [dict(item) for item in (mireye_context or [])]
    for item in mireye:
        if item.get("context_type") not in {
            "PROPERTY_DILIGENCE_CONTEXT",
            "POINT_LAND_CONTEXT",
            "POINT_HAZARD_CONTEXT",
        }:
            raise UnifiedOutputError(
                f"invalid mireye context_type: {item.get('context_type')}"
            )
        item.setdefault("partial_failures", [])
        item.setdefault("fields", {})

    # planned_actions must not mutate MatchResult — we only attach them to findings routing.
    findings = [dict(item) for item in (dynamic_diligence_findings or [])]
    for finding in findings:
        if planned and "related_planned_actions" not in finding:
            finding["related_planned_actions"] = list(planned)
        finding.setdefault("professional_verification_required", True)

    engine_input_hash = match_result.get("input_sha256")
    if not engine_input_hash:
        raise UnifiedOutputError("match_result.input_sha256 (engine_input_hash) is required")
    match_result_hash = hash_match_result(match_result)
    explanation_binding_hash = match_result_hash

    geometry_hash = land_profile.get("geometry_hash")
    profile_factors = land_profile.get("factors") or {}
    first_op = next(iter((match_result.get("operation_results") or {}).values()), {})
    evaluations = first_op.get("factor_evaluations") or {}

    factors: dict[str, Any] = {}
    for factor_id in FACTOR_IDS:
        factors[factor_id] = project_factor_result(
            factor_id,
            profile_factors.get(factor_id),
            evaluations.get(factor_id),
            geometry_hash=geometry_hash,
        )

    global_unknowns = list(match_result.get("unknowns") or [])
    global_diligence = list(match_result.get("diligence_actions") or [])
    operations = project_operations(
        match_result,
        mode=mode,
        intended_operation=intended_operation,
        global_unknowns=global_unknowns,
    )
    buyer_report = build_buyer_report(
        factors,
        operations,
        mireye_context=mireye,
        global_unknowns=global_unknowns,
        global_diligence=global_diligence,
        mode=mode,
        intended_operation=intended_operation,
    )

    f06 = profile_factors.get("F06_PARCEL_CONFIGURATION") or {}
    geometry_validity = f06.get("geometry_validity") or {
        "usable": f06.get("input_quality_state") == "PARCEL_GEOMETRY_COMPLETE"
    }

    envelope = {
        "contract_version": CONTRACT_VERSION,
        "run_id": run_id or f"run_{(land_profile.get('land_profile_id') or 'unknown')}",
        "mode": mode,
        "intended_operation": intended_operation,
        "planned_actions": planned,
        "created_at": created_at or _now_iso(),
        "engine_version": match_result.get("engine_version"),
        "engine_input_hash": engine_input_hash,
        "match_result_hash": match_result_hash,
        "explanation_binding_hash": explanation_binding_hash,
        "parcel": {
            "geometry_id": land_profile.get("geometry_id"),
            "geometry_hash": geometry_hash,
            "geometry_reference": land_profile.get("geometry_reference"),
            "source_crs": f06.get("source_crs") or "EPSG:4326",
            "address": land_profile.get("address"),
            "apn": land_profile.get("apn"),
            "parcel_id": land_profile.get("parcel_id"),
            "jurisdiction": project_jurisdiction(land_profile, mireye_context=mireye),
            "geometry_validity": geometry_validity,
        },
        "mireye_context": mireye,
        "factors": factors,
        "operations": operations,
        "cross_profile_comparison": {
            "ranking_permitted": bool(
                (match_result.get("cross_profile_comparison") or {}).get(
                    "ranking_permitted"
                )
            ),
            "reason": (match_result.get("cross_profile_comparison") or {}).get("reason"),
            "numeric_score": None,
        },
        "buyer_report": buyer_report,
        "dynamic_diligence_findings": findings,
        "unknowns": global_unknowns,
        "diligence_actions": global_diligence,
        "constraints": {
            "parcels_per_run": 1,
            "f09_authorized": False,
            "batch_workflow_authorized": False,
            "planned_actions_mutate_factors": False,
        },
    }
    validate_unified_output(envelope)
    return envelope


def validate_unified_output(envelope: Mapping[str, Any]) -> None:
    """Structural validation aligned to the JSON Schema required fields."""
    if envelope.get("contract_version") != CONTRACT_VERSION:
        raise UnifiedOutputError("contract_version mismatch")
    if envelope.get("mode") not in ALLOWED_MODES:
        raise UnifiedOutputError("invalid mode")
    validate_run_mode(envelope["mode"], envelope.get("intended_operation"))
    if envelope.get("explanation_binding_hash") != envelope.get("match_result_hash"):
        raise UnifiedOutputError(
            "explanation_binding_hash must equal match_result_hash"
        )
    if not isinstance(envelope.get("parcel"), Mapping):
        raise UnifiedOutputError("parcel required")
    jurisdiction = envelope["parcel"].get("jurisdiction")
    if not isinstance(jurisdiction, Mapping) or "resolution_status" not in jurisdiction:
        raise UnifiedOutputError("jurisdiction.resolution_status required")
    if jurisdiction["resolution_status"] not in {
        "RESOLVED",
        "PARTIAL",
        "UNKNOWN",
        "NOT_REQUESTED",
    }:
        raise UnifiedOutputError("invalid jurisdiction.resolution_status")
    factors = envelope.get("factors") or {}
    for factor_id in FACTOR_IDS:
        if factor_id not in factors:
            raise UnifiedOutputError(f"missing factor: {factor_id}")
        fr = factors[factor_id]
        for field in (
            "factor_id",
            "factor_version",
            "input_quality_state",
            "signal",
            "ranking_effect",
            "land_facts",
            "applicability",
            "coverage",
            "provenance",
            "limitations",
            "unknowns",
            "diligence_actions",
            "explanation_code",
        ):
            if field not in fr:
                raise UnifiedOutputError(f"{factor_id} missing {field}")
        cov = fr.get("coverage") or {}
        if "normalized_status" not in cov or "source_status" not in cov:
            raise UnifiedOutputError(f"{factor_id} coverage missing normalized/source")
        if cov["normalized_status"] not in {
            "COMPLETE",
            "PARTIAL",
            "UNQUANTIFIED",
            "OUTSIDE_SCOPE",
            "UNKNOWN",
            "NOT_APPLICABLE",
        }:
            raise UnifiedOutputError(f"{factor_id} invalid normalized_status")
    operations = envelope.get("operations") or {}
    for op in SUPPORTED_OPERATIONS:
        if op not in operations:
            raise UnifiedOutputError(f"missing operation: {op}")
        if operations[op].get("decision_label") not in ALLOWED_DECISION_LABELS:
            raise UnifiedOutputError(f"{op} invalid decision_label")
    report = envelope.get("buyer_report") or {}
    for section in BUYER_SECTIONS:
        if section not in report:
            raise UnifiedOutputError(f"missing buyer section: {section}")
    constraints = envelope.get("constraints") or {}
    if constraints.get("parcels_per_run") != 1:
        raise UnifiedOutputError("parcels_per_run must be 1")
    if constraints.get("f09_authorized") is not False:
        raise UnifiedOutputError("f09_authorized must be false")
    if constraints.get("batch_workflow_authorized") is not False:
        raise UnifiedOutputError("batch_workflow_authorized must be false")
    if constraints.get("planned_actions_mutate_factors") is not False:
        raise UnifiedOutputError("planned_actions_mutate_factors must be false")


def assert_explanation_binding(
    explanation: Mapping[str, Any],
    envelope: Mapping[str, Any],
) -> None:
    """Explanation must bind to match_result_hash."""
    bound = (
        explanation.get("bound_to_match_result_hash")
        or explanation.get("bound_to_input_sha256")
    )
    # Prefer explicit match_result_hash binding when present.
    expected = envelope["match_result_hash"]
    if explanation.get("bound_to_match_result_hash") is not None:
        if explanation["bound_to_match_result_hash"] != expected:
            raise UnifiedOutputError("explanation not bound to match_result_hash")
        return
    # Compatibility: existing explanation binds to engine input hash.
    if bound != envelope.get("engine_input_hash") and bound != expected:
        raise UnifiedOutputError(
            "explanation binding mismatch against engine_input_hash/match_result_hash"
        )


def project_from_paths(
    land_profile_path: str | Path,
    match_result_path: str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    from rangematch.engine import evaluate_land_profile

    profile = json.loads(Path(land_profile_path).read_text())
    if match_result_path:
        match_result = json.loads(Path(match_result_path).read_text())
    else:
        match_result = evaluate_land_profile(profile)
    return project_unified_output(profile, match_result, **kwargs)
