"""Deterministic F06 parcel-configuration derivation from parcel geometry.

Implements docs/F06_PARCEL_CONFIGURATION_DERIVATION_SPEC.yaml@0.1.0.
No suitability thresholds, fencing cost, carrying capacity, or species ranking.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from pyproj import CRS, Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform as shapely_transform

DERIVATION_SPEC_VERSION = "F06_PARCEL_CONFIGURATION_DERIVATION_SPEC.yaml@0.1.0"
ALGORITHM_VERSION = "F06_PARCEL_CONFIGURATION_DERIVATION@0.1.0"
FACTOR_ID = "F06_PARCEL_CONFIGURATION"
INTERNATIONAL_ACRE_M2 = 4046.8564224
SOURCE_CRS_DEFAULT = "EPSG:4326"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utm_zone_from_longitude(lon: float) -> int:
    return int(math.floor((lon + 180.0) / 6.0)) + 1


def utm_epsg_for_lonlat(lon: float, lat: float) -> str:
    zone = utm_zone_from_longitude(lon)
    if lat >= 0:
        return f"EPSG:{32600 + zone}"
    return f"EPSG:{32700 + zone}"


def _normalize_source_crs(source_crs: str | None) -> str | None:
    if source_crs is None:
        return None
    text = str(source_crs).strip()
    if not text:
        return None
    return text.upper().replace(" ", "")


def source_crs_is_supported_wgs84(source_crs: str | None) -> bool:
    """v0.1 accepts only EPSG:4326 as source CRS for UTM zone selection."""
    return _normalize_source_crs(source_crs) == "EPSG:4326"


def _extract_geometry_and_meta(
    geojson: Mapping[str, Any],
) -> tuple[Any, dict[str, Any], dict[str, Any] | None]:
    """Return shapely geometry, metadata, and optional extraction error.

    FeatureCollection is allowed only when it contains exactly one Feature.
    v0.1 does not silently measure features[0] and does not auto-union.
    """
    gtype = geojson.get("type")
    meta: dict[str, Any] = {
        "geometry_id": None,
        "geometry_reference": None,
        "feature_count": None,
    }
    if gtype == "FeatureCollection":
        features = geojson.get("features") or []
        meta["feature_count"] = len(features)
        if len(features) == 0:
            return None, meta, {
                "reason": "FEATURE_COLLECTION_EMPTY",
                "feature_count": 0,
            }
        if len(features) > 1:
            return None, meta, {
                "reason": "FEATURE_COLLECTION_MULTIPLE_FEATURES",
                "feature_count": len(features),
            }
        feature = features[0]
        props = feature.get("properties") or {}
        meta["geometry_id"] = feature.get("id") or props.get("geometry_id")
        geom = feature.get("geometry")
        return (shape(geom) if geom else None), meta, None
    if gtype == "Feature":
        meta["feature_count"] = 1
        props = geojson.get("properties") or {}
        meta["geometry_id"] = geojson.get("id") or props.get("geometry_id")
        geom = geojson.get("geometry")
        return (shape(geom) if geom else None), meta, None
    if gtype in {"Polygon", "MultiPolygon"}:
        meta["feature_count"] = 1
        return shape(dict(geojson)), meta, None
    if gtype == "GeometryCollection":
        return None, meta, {
            "reason": "GEOMETRY_COLLECTION_NOT_ACCEPTED",
            "geometry_type": "GeometryCollection",
        }
    return None, meta, {
        "reason": "UNSUPPORTED_GEOJSON_TYPE",
        "geometry_type": gtype,
    }


def _lonlat_bounds(geom) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = geom.bounds
    return float(minx), float(miny), float(maxx), float(maxy)


def select_working_crs(geom) -> dict[str, Any]:
    """Select local UTM from centroid; reject zone crossing / unsupported lon/lat."""
    if geom is None or geom.is_empty:
        return {
            "ok": False,
            "reason": "EMPTY_GEOMETRY",
            "working_crs": None,
        }
    minx, miny, maxx, maxy = _lonlat_bounds(geom)
    if minx < -180.0 or maxx > 180.0 or miny < -90.0 or maxy > 90.0:
        return {
            "ok": False,
            "reason": "PARCEL_OUTSIDE_VALID_LON_LAT_BOUNDS",
            "working_crs": None,
            "bounds_wgs84": [minx, miny, maxx, maxy],
        }
    if miny < -80.0 or maxy > 84.0:
        return {
            "ok": False,
            "reason": "PARCEL_OUTSIDE_SUPPORTED_UTM_LATITUDE",
            "working_crs": None,
            "bounds_wgs84": [minx, miny, maxx, maxy],
        }
    corners = [
        (minx, miny),
        (minx, maxy),
        (maxx, miny),
        (maxx, maxy),
    ]
    zones = {utm_zone_from_longitude(lon) for lon, _lat in corners}
    if len(zones) > 1:
        return {
            "ok": False,
            "reason": "PARCEL_CROSSES_UTM_ZONE_BOUNDARY",
            "working_crs": None,
            "utm_zones": sorted(zones),
            "bounds_wgs84": [minx, miny, maxx, maxy],
        }
    centroid = geom.centroid
    epsg = utm_epsg_for_lonlat(float(centroid.x), float(centroid.y))
    return {
        "ok": True,
        "reason": None,
        "working_crs": epsg,
        "utm_zone": next(iter(zones)),
        "centroid_wgs84": [float(centroid.x), float(centroid.y)],
        "bounds_wgs84": [minx, miny, maxx, maxy],
    }


def _unmeasurable_payload(
    base: dict[str, Any],
    *,
    input_quality_state: str,
    geometry_coverage_status: str,
    geometry_validity: str = "UNKNOWN",
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        **base,
        "input_quality_state": input_quality_state,
        "geometry_coverage_status": geometry_coverage_status,
        "geometry_validity": geometry_validity,
        "working_crs": None,
        "area_m2": None,
        "perimeter_m": None,
        "compactness": None,
        "polygon_part_count": None,
    }
    if extra:
        payload.update(dict(extra))
    return payload


def _project_geometry(geom, source_crs: str, working_crs: str):
    transformer = Transformer.from_crs(
        CRS.from_user_input(source_crs),
        CRS.from_user_input(working_crs),
        always_xy=True,
    )
    return shapely_transform(transformer.transform, geom)


def _polygon_part_count(geom) -> int | None:
    if geom is None or geom.is_empty:
        return None
    gtype = geom.geom_type
    if gtype == "Polygon":
        return 1
    if gtype == "MultiPolygon":
        return len(geom.geoms)
    return None


def _exterior_perimeter_m(projected_geom) -> float:
    """Sum exterior-ring lengths only; holes excluded per v0.1 policy."""
    if projected_geom.geom_type == "Polygon":
        return float(projected_geom.exterior.length)
    if projected_geom.geom_type == "MultiPolygon":
        return float(sum(part.exterior.length for part in projected_geom.geoms))
    return float(projected_geom.length)


def _has_holes(geom) -> bool:
    if geom.geom_type == "Polygon":
        return bool(geom.interiors)
    if geom.geom_type == "MultiPolygon":
        return any(bool(part.interiors) for part in geom.geoms)
    return False


def compactness_isoperimetric(area_m2: float, perimeter_m: float) -> float | None:
    if area_m2 is None or perimeter_m is None:
        return None
    if area_m2 <= 0 or perimeter_m <= 0:
        return None
    return (4.0 * math.pi * area_m2) / (perimeter_m * perimeter_m)


def validate_f06_factor_completeness(factor: Mapping[str, Any]) -> dict[str, Any]:
    """Check required provenance/measurement fields for PARCEL_GEOMETRY_COMPLETE."""
    issues: list[str] = []
    required = (
        "geometry_hash",
        "source_crs",
        "working_crs",
        "algorithm_version",
        "area_m2",
        "perimeter_m",
        "geometry_validity",
        "geometry_coverage_status",
    )
    for field in required:
        if factor.get(field) in (None, "", []):
            issues.append(f"{field}_missing")
    if factor.get("geometry_coverage_status") != "PARCEL_GEOMETRY_COMPLETE":
        issues.append("geometry_coverage_status_not_complete")
    if factor.get("geometry_validity") not in {"VALID", "REPAIRED_FOR_MEASUREMENT"}:
        issues.append("geometry_validity_not_usable")
    return {"complete": not issues, "issues": issues}


def derive_f06_from_geometry(
    geojson: Mapping[str, Any] | None,
    *,
    geometry_hash: str | None = None,
    geometry_reference: str | None = None,
    geometry_id: str | None = None,
    source_crs: str = SOURCE_CRS_DEFAULT,
    derived_at: str | None = None,
    conflicting_geometry_hashes: list[str] | None = None,
) -> dict[str, Any]:
    """Derive F06 Factor payload from parcel GeoJSON.

    v0.1 does not automatically repair invalid geometry.
    Area uses standard polygon semantics (holes subtracted by shapely area).
    Perimeter uses exterior rings only.
    """
    as_of = derived_at or _now_iso()
    base = {
        "factor_id": FACTOR_ID,
        "derivation_spec": DERIVATION_SPEC_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "source_crs": source_crs,
        "derived_at": as_of,
        "ranking_effect": "NONE",
        "geometry_reference": geometry_reference,
        "geometry_id": geometry_id,
        "geometry_hash": geometry_hash,
        "display_conversions": {
            "area_ha_formula": "area_m2 / 10000",
            "area_acre_formula": f"area_m2 / {INTERNATIONAL_ACRE_M2}",
            "acre_convention": "international_acre",
            "are_land_facts": False,
        },
        "limitations": [
            "Parcel area is geometric context, not grazable area or carrying capacity.",
            "Parcel perimeter is not fencing cost.",
            "Compactness is not operational efficiency or suitability.",
            "Measurements use projected UTM meters; not a legal survey acreage.",
            "v0.1 perimeter excludes interior rings/holes.",
            "v0.1 does not automatically repair invalid geometry.",
            "Geodesic QA is deferred and not required for v0.1.",
        ],
        "unknowns": [],
        "prohibited_interpretations_applied": True,
    }

    if conflicting_geometry_hashes:
        base.update(
            {
                "input_quality_state": "CONFLICTING_SOURCES",
                "geometry_coverage_status": "COVERAGE_UNQUANTIFIED",
                "geometry_validity": "UNKNOWN",
                "conflicting_geometry_hashes": list(conflicting_geometry_hashes),
                "working_crs": None,
                "area_m2": None,
                "perimeter_m": None,
                "compactness": None,
                "polygon_part_count": None,
            }
        )
        return base

    if not source_crs_is_supported_wgs84(source_crs):
        return _unmeasurable_payload(
            base,
            input_quality_state="CRS_UNSUPPORTED",
            geometry_coverage_status="CRS_UNSUPPORTED",
            geometry_validity="UNKNOWN",
            extra={
                "crs_selection": {
                    "ok": False,
                    "reason": "SOURCE_CRS_NOT_EPSG_4326",
                    "working_crs": None,
                    "source_crs": source_crs,
                    "supported_source_crs_v0_1": SOURCE_CRS_DEFAULT,
                },
                "limitations": base["limitations"]
                + [
                    "v0.1 accepts only EPSG:4326 source coordinates for UTM selection; "
                    "reproject to WGS84 before measurement or wait for a reviewed "
                    "non-4326 source-CRS path."
                ],
            },
        )

    if geojson is None:
        return _unmeasurable_payload(
            base,
            input_quality_state="MISSING",
            geometry_coverage_status="EMPTY_GEOMETRY",
            geometry_validity="UNKNOWN",
            extra={
                "unknowns": ["No parcel geometry is available for F06 derivation."],
            },
        )

    geom, meta, extract_error = _extract_geometry_and_meta(geojson)
    if geometry_id is None:
        base["geometry_id"] = meta.get("geometry_id")
    if meta.get("feature_count") is not None:
        base["feature_count"] = meta["feature_count"]
    if geometry_hash is None and geometry_reference:
        path = Path(geometry_reference)
        if path.exists():
            geometry_hash = sha256_file(path)
            base["geometry_hash"] = geometry_hash

    if extract_error is not None:
        reason = extract_error.get("reason")
        if reason == "FEATURE_COLLECTION_EMPTY":
            coverage = "EMPTY_GEOMETRY"
            limitation = (
                "FeatureCollection contains zero Features; v0.1 requires exactly one "
                "Polygon/MultiPolygon Feature."
            )
        elif reason == "FEATURE_COLLECTION_MULTIPLE_FEATURES":
            coverage = "INVALID_UNUSABLE"
            limitation = (
                "FeatureCollection contains multiple Features; v0.1 does not silently "
                "measure the first Feature and does not auto-union geometries."
            )
        else:
            coverage = "INVALID_UNUSABLE"
            limitation = (
                "GeoJSON type is not accepted for F06 v0.1 measurement without an "
                "explicit single Polygon/MultiPolygon Feature."
            )
        return _unmeasurable_payload(
            base,
            input_quality_state="GEOMETRY_INVALID_OR_EMPTY",
            geometry_coverage_status=coverage,
            geometry_validity="UNKNOWN",
            extra={
                "extraction_error": dict(extract_error),
                "limitations": base["limitations"] + [limitation],
            },
        )

    if geom is None or geom.is_empty:
        return _unmeasurable_payload(
            base,
            input_quality_state="GEOMETRY_INVALID_OR_EMPTY",
            geometry_coverage_status="EMPTY_GEOMETRY",
            geometry_validity="INVALID" if geom is not None else "UNKNOWN",
        )

    if geom.geom_type not in {"Polygon", "MultiPolygon"}:
        return _unmeasurable_payload(
            base,
            input_quality_state="GEOMETRY_INVALID_OR_EMPTY",
            geometry_coverage_status="INVALID_UNUSABLE",
            geometry_validity="INVALID",
            extra={
                "geometry_type": geom.geom_type,
                "limitations": base["limitations"]
                + ["Only Polygon/MultiPolygon geometries are accepted for F06 v0.1."],
            },
        )

    validity = "VALID" if geom.is_valid else "INVALID"
    if validity == "INVALID":
        base.update(
            {
                "input_quality_state": "GEOMETRY_INVALID_OR_EMPTY",
                "geometry_coverage_status": "INVALID_UNUSABLE",
                "geometry_validity": "INVALID",
                "geometry_type": geom.geom_type,
                "working_crs": None,
                "area_m2": None,
                "perimeter_m": None,
                "compactness": None,
                "polygon_part_count": _polygon_part_count(geom),
                "automatic_repair_applied": False,
                "limitations": base["limitations"]
                + [
                    "Geometry is invalid; v0.1 automatic repair is prohibited. "
                    "Provide a valid boundary before measurement."
                ],
            }
        )
        return base

    crs_choice = select_working_crs(geom)
    if not crs_choice["ok"]:
        base.update(
            {
                "input_quality_state": "CRS_UNSUPPORTED",
                "geometry_coverage_status": "CRS_UNSUPPORTED",
                "geometry_validity": validity,
                "geometry_type": geom.geom_type,
                "working_crs": None,
                "crs_selection": crs_choice,
                "area_m2": None,
                "perimeter_m": None,
                "compactness": None,
                "polygon_part_count": _polygon_part_count(geom),
            }
        )
        return base

    working_crs = crs_choice["working_crs"]
    projected = _project_geometry(geom, source_crs, working_crs)
    area_m2 = float(projected.area)  # holes subtracted by polygon semantics
    perimeter_m = _exterior_perimeter_m(projected)
    part_count = _polygon_part_count(geom)
    compactness = compactness_isoperimetric(area_m2, perimeter_m)
    has_holes = _has_holes(geom)

    limitations = list(base["limitations"])
    if has_holes:
        limitations.append(
            "Geometry contains holes; area subtracts hole interiors; "
            "v0.1 perimeter excludes hole rings."
        )
    if part_count and part_count > 1:
        limitations.append(
            "Multi-part geometry present; confirm operational vs drafting artifact."
        )

    result = {
        **base,
        "input_quality_state": "PARCEL_GEOMETRY_COMPLETE",
        "geometry_coverage_status": "PARCEL_GEOMETRY_COMPLETE",
        "geometry_validity": validity,
        "geometry_type": geom.geom_type,
        "working_crs": working_crs,
        "crs_selection": crs_choice,
        "polygon_part_count": part_count,
        "area_m2": area_m2,
        "perimeter_m": perimeter_m,
        "compactness": compactness,
        "has_holes": has_holes,
        "automatic_repair_applied": False,
        "display_only": {
            "area_ha": area_m2 / 10000.0,
            "area_acre_international": area_m2 / INTERNATIONAL_ACRE_M2,
        },
        "limitations": limitations,
        "provenance": {
            "source_reference": geometry_reference or "PARCEL_GEOMETRY",
            "fetched_at": as_of,
            "geometry_hash": geometry_hash,
            "response_or_artifact_hash": geometry_hash,
            "algorithm_version": ALGORITHM_VERSION,
            "working_crs": working_crs,
            "source_crs": source_crs,
        },
        # Canonical GeoJSON fragment hash for reproducibility of measured shape.
        "measured_geometry_geojson_hash": _sha256_bytes(
            json.dumps(mapping(geom), sort_keys=True, separators=(",", ":")).encode()
        ),
    }

    completeness = validate_f06_factor_completeness(result)
    if not completeness["complete"]:
        result["input_quality_state"] = "PARCEL_INCOMPLETE"
        result["geometry_coverage_status"] = "COVERAGE_UNQUANTIFIED"
        result["completeness_issues"] = completeness["issues"]
    return result


def derive_f06_from_geometry_path(
    geometry_path: str | Path,
    *,
    geometry_reference: str | None = None,
    geometry_id: str | None = None,
    source_crs: str = SOURCE_CRS_DEFAULT,
) -> dict[str, Any]:
    path = Path(geometry_path)
    geojson = json.loads(path.read_text())
    return derive_f06_from_geometry(
        geojson,
        geometry_hash=sha256_file(path),
        geometry_reference=geometry_reference or str(path),
        geometry_id=geometry_id,
        source_crs=source_crs,
    )


def evaluate_f06_signal(factor: Mapping[str, Any] | None) -> dict[str, Any]:
    """Map F06 Factor payload to deterministic signal / explanation."""
    if not factor:
        return {
            "factor_id": FACTOR_ID,
            "signal": "UNKNOWN",
            "ranking_effect": "NONE",
            "explanation_code": "F06_EXPL_MISSING",
            "input_quality_state": "MISSING",
        }
    state = factor.get("input_quality_state") or "MISSING"
    mapping_states = {
        "PARCEL_GEOMETRY_COMPLETE": ("CONTEXT_DEPENDENT", "F06_EXPL_CONTEXT_ONLY"),
        "CRS_UNSUPPORTED": ("NEEDS_VERIFICATION", "F06_EXPL_CRS_UNSUPPORTED"),
        "GEOMETRY_INVALID_OR_EMPTY": ("NEEDS_VERIFICATION", "F06_EXPL_GEOMETRY_UNUSABLE"),
        "PARCEL_INCOMPLETE": ("NEEDS_VERIFICATION", "F06_EXPL_INCOMPLETE_PROVENANCE"),
        "CONFLICTING_SOURCES": ("NEEDS_VERIFICATION", "F06_EXPL_CONFLICT"),
        "MISSING": ("UNKNOWN", "F06_EXPL_MISSING"),
    }
    signal, explanation = mapping_states.get(
        state, ("NEEDS_VERIFICATION", "F06_EXPL_UNRECOGNIZED")
    )
    return {
        "factor_id": FACTOR_ID,
        "signal": signal,
        "ranking_effect": "NONE",
        "explanation_code": explanation,
        "input_quality_state": state,
        "area_m2": factor.get("area_m2"),
        "perimeter_m": factor.get("perimeter_m"),
        "compactness": factor.get("compactness"),
        "polygon_part_count": factor.get("polygon_part_count"),
        "geometry_validity": factor.get("geometry_validity"),
        "geometry_coverage_status": factor.get("geometry_coverage_status"),
        "working_crs": factor.get("working_crs"),
        "algorithm_version": factor.get("algorithm_version"),
    }
