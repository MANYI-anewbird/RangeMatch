"""Deterministic F05 climate/drought derivation from NOAA + Mireye fixtures.

Canonical precipitation is NOAA/NCEI Direct Climate Normals NetCDF
(`annprcp_norm`). ACIS and Mireye never replace that Land Fact. No suitability
thresholds are applied.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

DERIVATION_SPEC_VERSION = "F05_CLIMATE_DROUGHT_DETERMINISTIC_RULES.yaml@0.1.0"
FACTOR_ID = "F05_CLIMATE_DROUGHT_EXPOSURE"
CANONICAL_PRECIP_SOURCE = "NOAA_NCEI_DIRECT_CLIMATE_NORMALS_NETCDF"
CANONICAL_PRECIP_VARIABLE = "annprcp_norm"

ACCEPTED_PRECIP_UNITS = {
    "millimeter",
    "millimeters",
    "mm",
    "mm/year",
    "mm/yr",
    "mm year-1",
}

ACCEPTED_COVERAGE_STATUSES = {
    "COMPLETE",
    "COMPLETE_WITH_NUMERIC_TOLERANCE",
    "COMPLETE_SINGLE_CELL_COVERS_SMALL_PARCEL",
    "COMPLETE_CELLS_INTERSECT_PARCEL_BBOX",
}


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def validate_canonical_precip(precip: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate NOAA canonical precip Land Fact fields without suitability rules."""
    issues: list[str] = []
    if not precip:
        return {
            "complete": False,
            "issues": ["canonical_precipitation_missing"],
            "coverage_confirmed": False,
            "unit_ok": False,
            "period_ok": False,
            "value_ok": False,
            "provenance_ok": False,
        }

    value = precip.get("value_mm")
    value_ok = isinstance(value, (int, float)) and value == value  # not NaN
    if not value_ok:
        issues.append("canonical_precipitation_value_missing")

    unit = str(precip.get("unit") or "").strip().lower()
    unit_ok = unit in ACCEPTED_PRECIP_UNITS
    if not unit_ok:
        issues.append("canonical_precipitation_unit_missing_or_invalid")

    period = precip.get("normals_period") or precip.get("observation_period")
    period_ok = bool(period)
    if not period_ok:
        issues.append("normals_or_observation_period_missing")

    coverage = precip.get("parcel_coverage") or {}
    coverage_status = coverage.get("coverage_status") or coverage.get("status")
    coverage_confirmed = coverage_status in ACCEPTED_COVERAGE_STATUSES
    if not coverage_confirmed:
        issues.append("parcel_coverage_unconfirmed")

    provenance_fields = {
        "source_reference": (precip.get("source") or {}).get("access_path")
        or (precip.get("source") or {}).get("file"),
        "fetched_at": precip.get("fetched_at"),
        "geometry_hash": precip.get("geometry_sha256") or precip.get("geometry_hash"),
        "response_or_artifact_hash": precip.get("file_sha256")
        or precip.get("response_or_artifact_hash"),
    }
    provenance_ok = all(
        provenance_fields[field] not in (None, "", [])
        for field in (
            "source_reference",
            "fetched_at",
            "geometry_hash",
            "response_or_artifact_hash",
        )
    )
    if not provenance_ok:
        issues.append("canonical_precipitation_provenance_incomplete")

    source = precip.get("source") or {}
    access_path = source.get("access_path")
    variable = source.get("variable")
    if access_path and access_path != CANONICAL_PRECIP_SOURCE:
        issues.append("non_canonical_precip_access_path")
    if variable and variable != CANONICAL_PRECIP_VARIABLE:
        issues.append("non_canonical_precip_variable")

    complete = value_ok and unit_ok and period_ok and coverage_confirmed and provenance_ok
    return {
        "complete": complete,
        "issues": issues,
        "coverage_confirmed": coverage_confirmed,
        "unit_ok": unit_ok,
        "period_ok": period_ok,
        "value_ok": value_ok,
        "provenance_ok": provenance_ok,
        "provenance_fields": provenance_fields,
    }


def classify_f05_input_quality(
    *,
    precip: Mapping[str, Any] | None,
    mireye_fields: Mapping[str, Any] | None = None,
    secondary_comparisons: list[dict[str, Any]] | None = None,
    prohibited_precip_proxy: bool = False,
) -> str:
    """Classify F05 input quality without inventing suitability thresholds."""
    if prohibited_precip_proxy:
        return "PROHIBITED_PRECIP_PROXY"

    comparisons = secondary_comparisons or []
    if any(item.get("material_conflict") for item in comparisons):
        return "CONFLICTING_SOURCES"

    validation = validate_canonical_precip(precip)
    if validation["complete"]:
        return "CLIMATE_CONTEXT_COMPLETE"

    has_point = bool(mireye_fields)
    if precip is None and has_point:
        return "POINT_CLIMATE_ONLY"
    if precip is None and not has_point:
        return "MISSING"
    # Canonical precip present but provenance/period/units/coverage incomplete.
    return "CLIMATE_CONTEXT_INCOMPLETE"


def derive_f05_parcel_facts(
    *,
    precip: Mapping[str, Any],
    mireye: Mapping[str, Any] | None = None,
    geometry_hash: str,
    secondary_comparisons: list[dict[str, Any]] | None = None,
    prohibited_precip_proxy: bool = False,
) -> dict[str, Any]:
    """Build the F05 factor evidence block for a Land Profile."""
    mireye_fields = (mireye or {}).get("fields") or mireye or {}
    point_qa = {}
    for field_id in (
        "drought_category",
        "mean_annual_dry_bulb_temperature_degc",
        "days_above_32c_annual_count",
    ):
        item = mireye_fields.get(field_id) or {}
        if item:
            point_qa[field_id] = {
                "value": item.get("value"),
                "unit": item.get("unit"),
                "status": item.get("status"),
                "source": item.get("source"),
                "dataset_vintage": item.get("dataset_vintage"),
                "fetched_at": item.get("fetched_at"),
                "spatial_semantics": "POINT_CENTROID",
            }

    comparisons = list(secondary_comparisons or [])
    validation = validate_canonical_precip(precip)
    state = classify_f05_input_quality(
        precip=precip,
        mireye_fields=point_qa,
        secondary_comparisons=comparisons,
        prohibited_precip_proxy=prohibited_precip_proxy,
    )

    source = precip.get("source") or {}
    provenance = {
        "source_reference": source.get("access_path") or source.get("file") or CANONICAL_PRECIP_SOURCE,
        "fetched_at": precip.get("fetched_at"),
        "geometry_hash": precip.get("geometry_sha256") or geometry_hash,
        "response_or_artifact_hash": precip.get("file_sha256"),
        "derivation_spec_version": DERIVATION_SPEC_VERSION,
        "primary_path": CANONICAL_PRECIP_SOURCE,
        "canonical_variable": CANONICAL_PRECIP_VARIABLE,
        "acis_role": "SECONDARY_QA_OR_FALLBACK",
        "mireye_role": "POINT_QA_AND_FAST_CONTEXT",
    }

    coverage = precip.get("parcel_coverage") or {}
    return {
        "factor_id": FACTOR_ID,
        "input_quality_state": state,
        "derivation_spec": DERIVATION_SPEC_VERSION,
        "canonical_precipitation": {
            "variable_id": precip.get("variable_id") or "VAR_F05_MEAN_ANNUAL_PRECIPITATION",
            "value_mm": precip.get("value_mm"),
            "value_inches": precip.get("value_inches"),
            "unit": precip.get("unit"),
            "unit_normalized": "mm/year",
            "normals_period": precip.get("normals_period"),
            "spatial_resolution": precip.get("spatial_resolution"),
            "aggregation": precip.get("aggregation"),
            "source": source,
            "role": "CANONICAL_LAND_FACT",
            "suitability_signal": None,
        },
        "parcel_coverage": {
            "status": (
                "COMPLETE"
                if coverage.get("coverage_status") in ACCEPTED_COVERAGE_STATUSES
                else "UNCONFIRMED"
            ),
            "detail": coverage.get("coverage_status"),
            "spatial_support": coverage.get("spatial_support"),
            "parcel_bbox": coverage.get("parcel_bbox"),
            "intersecting_cell_count": coverage.get("intersecting_cell_count"),
            "coverage_calculated_from_polygon_intersection": False,
            "successful_query_implies_complete_coverage": False,
        },
        "mireye_point_qa": point_qa,
        "secondary_comparisons": comparisons,
        "source_conflicts": [
            item for item in comparisons if item.get("material_conflict")
        ],
        "validation": validation,
        "applicability": {
            "domain_status": "IN_DOCUMENTED_PRODUCT_SCOPE",
            "review_status": "VERIFIED_FOR_DATA_CAPABILITY",
            "basis": [
                "F05_CLIMATE_DROUGHT_ATOMICITY_AND_SOURCE_AUDIT",
                "F05_CLIMATE_DROUGHT_EVIDENCE_REGISTRY",
                "CPER_LIVE_DATA_GATE",
            ],
            "notes": (
                "F05 v0.1 is data-quality and context only; annprcp_norm is retained as a "
                "Land Fact and is not converted into suitability."
            ),
        },
        "coverage": {
            "status": (
                "COMPLETE"
                if coverage.get("coverage_status") in ACCEPTED_COVERAGE_STATUSES
                else "UNKNOWN"
            ),
            "detail": coverage.get("coverage_status"),
            "adapter_status": CANONICAL_PRECIP_SOURCE,
        },
        "quality": {
            "confidence_state": "SUPPORTED" if validation["complete"] else "NEEDS_VERIFICATION",
            "modeled": True,
            "canonical_precip_complete": validation["complete"],
            "directional_signal_approved": False,
            "numeric_thresholds_approved": False,
        },
        "provenance": provenance,
        "limitations": [
            "Mean annual precipitation is a Land Fact, not a suitability score.",
            "Current USDM class is current-condition context only, not drought history.",
            "Mireye point climate fields must not replace canonical NOAA parcel precipitation.",
            "ACIS precipitation series is secondary QA/fallback and is not the canonical runtime source.",
            "No precipitation, temperature, heat-day, or USDM suitability threshold is approved.",
            "F05 must not alter F02 forage, F03 livestock-water, or F04 wetness signals.",
            "Flood/FEMA hazard is out of scope for F05.",
        ],
        "unknowns": [
            "Drought-history summary method is not frozen.",
            "Precipitation seasonality and interannual variability methods are not frozen.",
            "No biological heat-stress threshold is approved for Cow-Calf or Sheep.",
        ],
        "ranking_effect": "NONE",
    }


def derive_f05_from_fixture_dir(
    fixture_dir: str | Path,
    *,
    geometry_hash: str,
    precip_name: str = "cper_noaa_ncei_annprcp_normals_1991_2020_2026-08-07.json",
    mireye_name: str = "cper_mireye_f05_centroid_2026-08-07.json",
    secondary_comparisons: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Derive F05 evidence from saved CPER live-gate fixtures."""
    root = Path(fixture_dir)
    precip = _load_json(root / precip_name)
    mireye = _load_json(root / mireye_name)
    factor = derive_f05_parcel_facts(
        precip=precip,
        mireye=mireye,
        geometry_hash=geometry_hash,
        secondary_comparisons=secondary_comparisons,
    )
    factor["result_reference"] = str(Path("test-data/live-results/cper") / "f05_derivation_result.json")
    factor["source_fixture_references"] = [
        f"test-data/live-results/cper/{precip_name}",
        f"test-data/live-results/cper/{mireye_name}",
    ]
    factor["artifact_hash"] = _sha256_json(
        {
            "precip": precip,
            "mireye": mireye,
            "secondary_comparisons": secondary_comparisons or [],
        }
    )
    return factor
