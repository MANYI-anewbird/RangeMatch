"""Deterministic F07 road / physical-access context derivation.

Implements docs/F07_ROAD_PHYSICAL_ACCESS_DERIVATION_SPEC.yaml@0.1.0.
Mapped roads are physical proximity context only — not legal access, entrance,
suitability, travel time, profitability, carrying capacity, or species ranking.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from shapely.geometry import mapping, shape

from rangematch.f06_derivation import (
    SOURCE_CRS_DEFAULT,
    _extract_geometry_and_meta,
    _project_geometry,
    select_working_crs,
    sha256_file,
    source_crs_is_supported_wgs84,
)

DERIVATION_SPEC_VERSION = "F07_ROAD_PHYSICAL_ACCESS_DERIVATION_SPEC.yaml@0.1.0"
ALGORITHM_VERSION = "F07_ROAD_PHYSICAL_ACCESS_DERIVATION@0.1.0"
ALGORITHM_VERSION_EDGES_FALLBACK = (
    "F07_ROAD_PHYSICAL_ACCESS_DERIVATION_EDGES_FALLBACK@0.1.0"
)
FACTOR_ID = "F07_ROAD_AND_PHYSICAL_ACCESS"
CANONICAL_SOURCE_ID = "US_CENSUS_TIGER_LINE_2025_ALL_ROADS"
EDGES_FALLBACK_SOURCE_ID = "US_CENSUS_TIGER_LINE_EDGES_ROAD_FILTERED"
SEARCH_WINDOW_DEFAULT_M = 5000.0
TIGER_2025_ROADS_URL_PATTERN = (
    "https://www2.census.gov/geo/tiger/TIGER2025/ROADS/"
    "tl_2025_{county_fips}_roads.zip"
)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_road_feature_id(properties: Mapping[str, Any] | None, index: int) -> str:
    props = properties or {}
    for key in ("LINEARID", "linearid", "FEATURE_ID", "feature_id", "id"):
        value = props.get(key)
        if value is not None and str(value).strip() != "":
            return str(value)
    return f"GENERATED_{index:06d}"


def evaluate_county_coverage(
    requested_county_fips: Sequence[str] | None,
    loaded_county_fips: Sequence[str] | None,
) -> dict[str, Any]:
    requested = [str(x) for x in (requested_county_fips or []) if str(x).strip()]
    loaded = [str(x) for x in (loaded_county_fips or []) if str(x).strip()]
    req_set = set(requested)
    loaded_set = set(loaded)
    if not req_set:
        status = "UNKNOWN"
    elif req_set <= loaded_set:
        status = "COMPLETE"
    elif loaded_set & req_set:
        status = "PARTIAL"
    else:
        status = "UNKNOWN"
    return {
        "requested_county_fips": sorted(req_set),
        "loaded_county_fips": sorted(loaded_set),
        "missing_county_fips": sorted(req_set - loaded_set),
        "status": status,
    }


def _contact_detail(parcel, road) -> str | None:
    """Return INTERSECTS, TOUCHES, or None when no contact."""
    if parcel.touches(road):
        return "TOUCHES"
    if parcel.intersects(road):
        return "INTERSECTS"
    return None


def _iter_road_features(roads_geojson: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not roads_geojson:
        return []
    gtype = roads_geojson.get("type")
    if gtype == "FeatureCollection":
        return [f for f in (roads_geojson.get("features") or []) if isinstance(f, dict)]
    if gtype == "Feature":
        return [dict(roads_geojson)]
    if gtype in {"LineString", "MultiLineString"}:
        return [
            {
                "type": "Feature",
                "properties": {},
                "geometry": dict(roads_geojson),
            }
        ]
    return []


def _road_class_context(properties: Mapping[str, Any] | None) -> str | None:
    props = properties or {}
    for key in ("MTFCC", "mtfcc", "road_class", "class"):
        value = props.get(key)
        if value is not None and str(value).strip() != "":
            return str(value)
    return None


def derive_f07_from_inputs(
    parcel_geojson: Mapping[str, Any] | None,
    roads_geojson: Mapping[str, Any] | None,
    *,
    requested_county_fips: Sequence[str] | None,
    loaded_county_fips: Sequence[str] | None,
    geometry_hash: str | None = None,
    geometry_reference: str | None = None,
    geometry_id: str | None = None,
    source_crs: str = SOURCE_CRS_DEFAULT,
    search_window_m: float = SEARCH_WINDOW_DEFAULT_M,
    road_source_id: str = CANONICAL_SOURCE_ID,
    road_product_vintage: str = "2025",
    road_artifact_hash: str | None = None,
    derived_at: str | None = None,
) -> dict[str, Any]:
    """Derive F07 Factor payload from parcel geometry and mapped road features."""
    as_of = derived_at or _now_iso()
    algorithm_version = ALGORITHM_VERSION
    county_coverage = evaluate_county_coverage(requested_county_fips, loaded_county_fips)

    base: dict[str, Any] = {
        "factor_id": FACTOR_ID,
        "derivation_spec": DERIVATION_SPEC_VERSION,
        "algorithm_version": algorithm_version,
        "road_source_id": road_source_id,
        "road_product": (
            "TIGER/Line 2025 All Roads"
            if road_source_id == CANONICAL_SOURCE_ID
            else str(road_source_id)
        ),
        "edges_fallback_used": False,
        "road_product_vintage": road_product_vintage,
        "search_window_m": float(search_window_m),
        "source_crs": source_crs,
        "derived_at": as_of,
        "ranking_effect": "NONE",
        "geometry_reference": geometry_reference,
        "geometry_id": geometry_id,
        "geometry_hash": geometry_hash,
        "county_coverage": county_coverage,
        "osm_consulted": False,
        "limitations": [
            "Mapped road proximity/contact is physical context only.",
            "Mapped roads do not establish legal access, easement, or deeded right-of-way.",
            "Centerline contact does not prove a usable driveway, gate, or entrance.",
            "Euclidean parcel-to-centerline distance is not network drive distance or travel time.",
            "Search window is a retrieval parameter, not a too-far suitability threshold.",
            "Absence of mapped roads in the window does not prove the parcel is landlocked.",
            "OSM is deferred from F07 v0.1 and was not consulted.",
        ],
        "unknowns": [],
        "prohibited_interpretations_applied": True,
    }

    if str(road_source_id).upper().startswith("OSM") or "OPENSTREETMAP" in str(
        road_source_id
    ).upper():
        return {
            **base,
            "input_quality_state": "ROAD_SOURCE_INCOMPLETE",
            "road_source_coverage_status": "UNKNOWN",
            "geometry_validity": "UNKNOWN",
            "working_crs": None,
            "mapped_road_feature_count_in_search_window": None,
            "road_parcel_contact_status": "UNKNOWN",
            "nearest_mapped_road_distance_m": None,
            "nearest_road_class_context": None,
            "nearest_road_feature_id": None,
            "limitations": base["limitations"]
            + ["OSM sources are deferred from F07 v0.1 and must not be used."],
        }

    if road_source_id == EDGES_FALLBACK_SOURCE_ID:
        return {
            **base,
            "input_quality_state": "ROAD_SOURCE_INCOMPLETE",
            "road_source_coverage_status": "UNKNOWN",
            "geometry_validity": "UNKNOWN",
            "working_crs": None,
            "mapped_road_feature_count_in_search_window": None,
            "road_parcel_contact_status": "UNKNOWN",
            "nearest_mapped_road_distance_m": None,
            "nearest_road_class_context": None,
            "nearest_road_feature_id": None,
            "edges_fallback_used": False,
            "limitations": base["limitations"]
            + [
                "TIGER Edges road-filtered fallback is documented only in F07 v0.1 and "
                "is not implemented unless a confirmed All Roads failure authorizes it."
            ],
        }

    if road_source_id != CANONICAL_SOURCE_ID:
        return {
            **base,
            "input_quality_state": "ROAD_SOURCE_INCOMPLETE",
            "road_source_coverage_status": "UNKNOWN",
            "geometry_validity": "UNKNOWN",
            "working_crs": None,
            "mapped_road_feature_count_in_search_window": None,
            "road_parcel_contact_status": "UNKNOWN",
            "nearest_mapped_road_distance_m": None,
            "nearest_road_class_context": None,
            "nearest_road_feature_id": None,
            "limitations": base["limitations"]
            + [
                f"Unrecognized road_source_id={road_source_id}; v0.1 accepts only "
                f"{CANONICAL_SOURCE_ID}."
            ],
        }

    if not source_crs_is_supported_wgs84(source_crs):
        return {
            **base,
            "input_quality_state": "CRS_UNSUPPORTED",
            "road_source_coverage_status": "CRS_UNSUPPORTED",
            "geometry_validity": "UNKNOWN",
            "working_crs": None,
            "mapped_road_feature_count_in_search_window": None,
            "road_parcel_contact_status": "UNKNOWN",
            "nearest_mapped_road_distance_m": None,
            "nearest_road_class_context": None,
            "nearest_road_feature_id": None,
            "crs_selection": {
                "ok": False,
                "reason": "SOURCE_CRS_NOT_EPSG_4326",
                "source_crs": source_crs,
            },
        }

    if parcel_geojson is None:
        return {
            **base,
            "input_quality_state": "MISSING",
            "road_source_coverage_status": "MISSING",
            "geometry_validity": "UNKNOWN",
            "working_crs": None,
            "mapped_road_feature_count_in_search_window": None,
            "road_parcel_contact_status": "UNKNOWN",
            "nearest_mapped_road_distance_m": None,
            "nearest_road_class_context": None,
            "nearest_road_feature_id": None,
            "unknowns": ["No parcel geometry is available for F07 derivation."],
        }

    geom, meta, extract_error = _extract_geometry_and_meta(parcel_geojson)
    if geometry_id is None:
        base["geometry_id"] = meta.get("geometry_id")
    if geometry_hash is None and geometry_reference:
        path = Path(geometry_reference)
        if path.exists():
            geometry_hash = sha256_file(path)
            base["geometry_hash"] = geometry_hash

    if extract_error is not None or geom is None or geom.is_empty:
        return {
            **base,
            "input_quality_state": "GEOMETRY_INVALID_OR_EMPTY",
            "road_source_coverage_status": "UNKNOWN",
            "geometry_validity": "INVALID" if geom is not None and not geom.is_empty else "UNKNOWN",
            "extraction_error": extract_error,
            "working_crs": None,
            "mapped_road_feature_count_in_search_window": None,
            "road_parcel_contact_status": "UNKNOWN",
            "nearest_mapped_road_distance_m": None,
            "nearest_road_class_context": None,
            "nearest_road_feature_id": None,
        }

    if geom.geom_type not in {"Polygon", "MultiPolygon"}:
        return {
            **base,
            "input_quality_state": "GEOMETRY_INVALID_OR_EMPTY",
            "road_source_coverage_status": "UNKNOWN",
            "geometry_validity": "INVALID",
            "geometry_type": geom.geom_type,
            "working_crs": None,
            "mapped_road_feature_count_in_search_window": None,
            "road_parcel_contact_status": "UNKNOWN",
            "nearest_mapped_road_distance_m": None,
            "nearest_road_class_context": None,
            "nearest_road_feature_id": None,
        }

    if not geom.is_valid:
        return {
            **base,
            "input_quality_state": "GEOMETRY_INVALID_OR_EMPTY",
            "road_source_coverage_status": "UNKNOWN",
            "geometry_validity": "INVALID",
            "geometry_type": geom.geom_type,
            "working_crs": None,
            "mapped_road_feature_count_in_search_window": None,
            "road_parcel_contact_status": "UNKNOWN",
            "nearest_mapped_road_distance_m": None,
            "nearest_road_class_context": None,
            "nearest_road_feature_id": None,
            "automatic_repair_applied": False,
        }

    crs_choice = select_working_crs(geom)
    if not crs_choice["ok"]:
        return {
            **base,
            "input_quality_state": "CRS_UNSUPPORTED",
            "road_source_coverage_status": "CRS_UNSUPPORTED",
            "geometry_validity": "VALID",
            "working_crs": None,
            "crs_selection": crs_choice,
            "mapped_road_feature_count_in_search_window": None,
            "road_parcel_contact_status": "UNKNOWN",
            "nearest_mapped_road_distance_m": None,
            "nearest_road_class_context": None,
            "nearest_road_feature_id": None,
        }

    # Incomplete county coverage: do not silently present complete measurements.
    if county_coverage["status"] != "COMPLETE":
        coverage_status = county_coverage["status"]  # PARTIAL or UNKNOWN
        return {
            **base,
            "input_quality_state": "ROAD_SOURCE_INCOMPLETE",
            "road_source_coverage_status": coverage_status,
            "geometry_validity": "VALID",
            "geometry_type": geom.geom_type,
            "working_crs": crs_choice["working_crs"],
            "crs_selection": crs_choice,
            "mapped_road_feature_count_in_search_window": None,
            "road_parcel_contact_status": "UNKNOWN",
            "nearest_mapped_road_distance_m": None,
            "nearest_road_class_context": None,
            "nearest_road_feature_id": None,
            "road_artifact_hash": road_artifact_hash,
            "limitations": base["limitations"]
            + [
                "County All Roads coverage is incomplete for the search window; "
                f"requested={county_coverage['requested_county_fips']} "
                f"loaded={county_coverage['loaded_county_fips']}. "
                "v0.1 does not silently measure under PARTIAL/UNKNOWN coverage."
            ],
        }

    working_crs = crs_choice["working_crs"]
    parcel_proj = _project_geometry(geom, source_crs, working_crs)
    fetch_region = parcel_proj.buffer(float(search_window_m))

    candidates: list[dict[str, Any]] = []
    for index, feature in enumerate(_iter_road_features(roads_geojson)):
        road_geom_raw = feature.get("geometry")
        if not road_geom_raw:
            continue
        road_geom = shape(road_geom_raw)
        if road_geom.is_empty:
            continue
        if road_geom.geom_type not in {"LineString", "MultiLineString"}:
            continue
        road_proj = _project_geometry(road_geom, source_crs, working_crs)
        if not road_proj.intersects(fetch_region):
            continue
        props = feature.get("properties") or {}
        feature_id = stable_road_feature_id(props, index)
        distance_m = float(parcel_proj.distance(road_proj))
        detail = _contact_detail(parcel_proj, road_proj)
        candidates.append(
            {
                "feature_id": feature_id,
                "distance_m": distance_m,
                "contact_detail": detail,
                "mtfcc": _road_class_context(props),
                "fullname": props.get("FULLNAME") or props.get("fullname"),
                "geometry_type": road_geom.geom_type,
            }
        )

    # Deterministic order for reproducibility of ties and counts.
    candidates.sort(key=lambda item: (item["distance_m"], item["feature_id"]))

    count = len(candidates)
    intersects = [c for c in candidates if c["contact_detail"] == "INTERSECTS"]
    touches = [c for c in candidates if c["contact_detail"] == "TOUCHES"]

    if intersects:
        contact_status = "INTERSECTS"
    elif touches:
        contact_status = "TOUCHES"
    elif count > 0:
        contact_status = "NO_CONTACT_IN_WINDOW"
    else:
        contact_status = "NO_MAPPED_ROAD_IN_SEARCH_WINDOW"

    nearest = candidates[0] if candidates else None
    quality_state = (
        "NO_MAPPED_ROAD_IN_SEARCH_WINDOW"
        if contact_status == "NO_MAPPED_ROAD_IN_SEARCH_WINDOW"
        else "ROAD_CONTEXT_COMPLETE"
    )

    result = {
        **base,
        "input_quality_state": quality_state,
        "road_source_coverage_status": "ROAD_CONTEXT_COMPLETE"
        if quality_state == "ROAD_CONTEXT_COMPLETE"
        else "NO_MAPPED_ROAD_IN_SEARCH_WINDOW",
        "geometry_validity": "VALID",
        "geometry_type": geom.geom_type,
        "working_crs": working_crs,
        "crs_selection": crs_choice,
        "mapped_road_feature_count_in_search_window": count,
        "road_parcel_contact_status": contact_status,
        "road_parcel_contact_detail": {
            "intersects_feature_count": len(intersects),
            "touches_feature_count": len(touches),
            "no_contact_feature_count": count - len(intersects) - len(touches),
        },
        "nearest_mapped_road_distance_m": None if nearest is None else nearest["distance_m"],
        "nearest_road_feature_id": None if nearest is None else nearest["feature_id"],
        "nearest_road_class_context": None if nearest is None else nearest["mtfcc"],
        "nearest_road_fullname": None if nearest is None else nearest.get("fullname"),
        "nearest_feature_tie_break": {
            "primary": "distance_m_ascending",
            "secondary": "stable_feature_id_ascending",
            "preferred_stable_id": "LINEARID",
        },
        "road_artifact_hash": road_artifact_hash
        or (
            _sha256_bytes(
                json.dumps(roads_geojson, sort_keys=True, separators=(",", ":")).encode()
            )
            if roads_geojson is not None
            else None
        ),
        "provenance": {
            "road_source_id": road_source_id,
            "road_product_vintage": road_product_vintage,
            "fetched_at": as_of,
            "geometry_hash": geometry_hash,
            "response_or_artifact_hash": road_artifact_hash,
            "algorithm_version": algorithm_version,
            "working_crs": working_crs,
            "source_crs": source_crs,
            "search_window_m": float(search_window_m),
            "requested_county_fips": county_coverage["requested_county_fips"],
            "loaded_county_fips": county_coverage["loaded_county_fips"],
        },
        "measured_parcel_geojson_hash": _sha256_bytes(
            json.dumps(mapping(geom), sort_keys=True, separators=(",", ":")).encode()
        ),
    }
    if quality_state == "NO_MAPPED_ROAD_IN_SEARCH_WINDOW":
        result["unknowns"] = [
            "No mapped TIGER 2025 All Roads features intersect the declared search window; "
            "unmapped private/ranch roads and legal access remain unknown."
        ]
    return result


def derive_f07_from_geometry_path(
    geometry_path: str | Path,
    roads_geojson: Mapping[str, Any] | None,
    *,
    requested_county_fips: Sequence[str],
    loaded_county_fips: Sequence[str],
    geometry_reference: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    path = Path(geometry_path)
    parcel = json.loads(path.read_text())
    return derive_f07_from_inputs(
        parcel,
        roads_geojson,
        requested_county_fips=requested_county_fips,
        loaded_county_fips=loaded_county_fips,
        geometry_hash=sha256_file(path),
        geometry_reference=geometry_reference or str(path),
        **kwargs,
    )


def evaluate_f07_signal(factor: Mapping[str, Any] | None) -> dict[str, Any]:
    """Map F07 Factor payload to deterministic signal / explanation."""
    if not factor:
        return {
            "factor_id": FACTOR_ID,
            "signal": "UNKNOWN",
            "ranking_effect": "NONE",
            "explanation_code": "F07_EXPL_MISSING",
            "input_quality_state": "MISSING",
        }
    state = factor.get("input_quality_state") or "MISSING"
    mapping_states = {
        "ROAD_CONTEXT_COMPLETE": ("CONTEXT_DEPENDENT", "F07_EXPL_CONTEXT_ONLY"),
        "NO_MAPPED_ROAD_IN_SEARCH_WINDOW": (
            "CONTEXT_DEPENDENT",
            "F07_EXPL_NO_MAPPED_ROAD_IN_WINDOW",
        ),
        "ROAD_SOURCE_INCOMPLETE": ("NEEDS_VERIFICATION", "F07_EXPL_SOURCE_INCOMPLETE"),
        "CRS_UNSUPPORTED": ("NEEDS_VERIFICATION", "F07_EXPL_CRS_UNSUPPORTED"),
        "GEOMETRY_INVALID_OR_EMPTY": ("NEEDS_VERIFICATION", "F07_EXPL_GEOMETRY_UNUSABLE"),
        "CONFLICTING_SOURCES": ("NEEDS_VERIFICATION", "F07_EXPL_CONFLICT"),
        "MISSING": ("UNKNOWN", "F07_EXPL_MISSING"),
    }
    signal, explanation = mapping_states.get(
        state, ("NEEDS_VERIFICATION", "F07_EXPL_UNRECOGNIZED")
    )
    return {
        "factor_id": FACTOR_ID,
        "signal": signal,
        "ranking_effect": "NONE",
        "explanation_code": explanation,
        "input_quality_state": state,
        "mapped_road_feature_count_in_search_window": factor.get(
            "mapped_road_feature_count_in_search_window"
        ),
        "road_parcel_contact_status": factor.get("road_parcel_contact_status"),
        "nearest_mapped_road_distance_m": factor.get("nearest_mapped_road_distance_m"),
        "nearest_road_feature_id": factor.get("nearest_road_feature_id"),
        "nearest_road_class_context": factor.get("nearest_road_class_context"),
        "search_window_m": factor.get("search_window_m"),
        "road_source_id": factor.get("road_source_id"),
        "road_source_coverage_status": factor.get("road_source_coverage_status"),
        "county_coverage": factor.get("county_coverage"),
        "algorithm_version": factor.get("algorithm_version"),
        "legal_access_inferred": False,
    }
