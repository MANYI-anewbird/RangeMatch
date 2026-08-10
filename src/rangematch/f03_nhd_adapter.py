"""Live USGS NHDPlus HR candidate-water adapter for F03 confirmed parcels.

This runtime adapter discovers and normalizes mapped hydrography candidates.
It never creates FIELD_VERIFIED livestock water. Imagery review is a separate,
provenance-complete human/reviewed-evidence action under the frozen contract.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
from pyproj import Transformer
from shapely import contains_xy, distance, points
from shapely.geometry import shape
from shapely.ops import transform, unary_union

from rangematch.f03_verification import (
    apply_remote_enrichment,
    build_mapped_candidate_from_nhd,
    factor_input_quality_from_levels,
    stable_sample_f03_candidates,
)
from rangematch.f06_derivation import select_working_crs


NHD_SERVICE = "https://hydro.nationalmap.gov/arcgis/rest/services/NHDPlus_HR/MapServer"
NHD_LAYERS = {
    "NetworkNHDFlowline": 3,
    "NonNetworkNHDFlowline": 4,
    "NHDArea": 8,
    "NHDWaterbody": 9,
}
ADAPTER_ID = "F03_USGS_NHDPLUS_HR_ADAPTER@0.1.0"
DERIVATION_SPEC = "F03_CANDIDATE_WATER_DERIVATION_SPEC.yaml@0.1.0"
EVIDENCE_CONTRACT = "F03_VERIFIED_WATER_EVIDENCE_CONTRACT.yaml@0.1.1"


class F03NHDAdapterError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _property(properties: Mapping[str, Any], *names: str) -> Any:
    lowered = {str(key).lower(): value for key, value in properties.items()}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def _fetch_nhd_layer(
    layer_id: int,
    bbox: tuple[float, float, float, float],
    *,
    timeout_s: int = 180,
) -> dict[str, Any]:
    params = {
        "geometry": ",".join(str(value) for value in bbox),
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": 4326,
        "f": "geojson",
        "resultRecordCount": 2000,
    }
    url = f"{NHD_SERVICE}/{layer_id}/query?{urlencode(params)}"
    try:
        import requests

        session = requests.Session()
        session.trust_env = False
        response = session.get(url, headers={"User-Agent": "RangeMatch/0.1"}, timeout=timeout_s)
        response.raise_for_status()
        payload = response.json()
    except ImportError:
        request = Request(url, headers={"User-Agent": "RangeMatch/0.1"})
        with urlopen(request, timeout=timeout_s) as response:
            payload = json.loads(response.read())
    if not isinstance(payload, dict) or "features" not in payload:
        raise F03NHDAdapterError(f"NHD layer {layer_id} returned no FeatureCollection")
    return payload


def _distance_distribution(parcel, candidates: list[Any], *, cell_size_m: float = 10.0) -> dict[str, Any]:
    minx, miny, maxx, maxy = parcel.bounds
    xs = np.arange(np.floor(minx / cell_size_m) * cell_size_m + cell_size_m / 2, maxx, cell_size_m)
    ys = np.arange(np.floor(miny / cell_size_m) * cell_size_m + cell_size_m / 2, maxy, cell_size_m)
    xx, yy = np.meshgrid(xs, ys)
    inside = contains_xy(parcel, xx, yy)
    cell_x, cell_y = xx[inside], yy[inside]
    if not candidates or not cell_x.size:
        return {
            "valid_cell_count": int(cell_x.size),
            "minimum": None,
            "median": None,
            "p90": None,
            "maximum": None,
        }
    values = np.asarray(distance(points(cell_x, cell_y), unary_union(candidates)), dtype=float)
    return {
        "valid_cell_count": int(values.size),
        "minimum": float(values.min()),
        "median": float(np.percentile(values, 50, method="linear")),
        "p90": float(np.percentile(values, 90, method="linear")),
        "maximum": float(values.max()),
    }


def collect_f03_from_usgs_nhd(
    *,
    geometry: Mapping[str, Any],
    geometry_id: str,
    geometry_hash: str,
    query_pad_degrees: float = 0.01,
) -> dict[str, Any]:
    """Collect mapped candidates and prepare the stable remote-review queue."""
    features = list(geometry.get("features") or [])
    if geometry.get("type") != "FeatureCollection" or len(features) != 1:
        raise F03NHDAdapterError("F03 requires exactly one confirmed parcel Feature")
    parcel_wgs84 = shape(features[0].get("geometry"))
    if parcel_wgs84.is_empty or not parcel_wgs84.is_valid:
        raise F03NHDAdapterError("F03 parcel geometry is invalid or empty")
    crs = select_working_crs(parcel_wgs84)
    if not crs.get("ok"):
        raise F03NHDAdapterError(f"F03 working CRS unavailable: {crs.get('reason')}")
    working_crs = str(crs["working_crs"])
    project = Transformer.from_crs("EPSG:4326", working_crs, always_xy=True).transform
    parcel = transform(project, parcel_wgs84)
    west, south, east, north = parcel_wgs84.bounds
    bbox = (
        west - query_pad_degrees,
        south - query_pad_degrees,
        east + query_pad_degrees,
        north + query_pad_degrees,
    )
    raw_layers: dict[str, Any] = {}
    layer_errors: dict[str, str] = {}
    inventory: list[dict[str, Any]] = []
    candidate_geometries: list[Any] = []
    fetched_at = _utc_now()
    for layer_name, layer_id in NHD_LAYERS.items():
        try:
            collection = _fetch_nhd_layer(layer_id, bbox)
            raw_layers[layer_name] = collection
        except Exception as exc:  # noqa: BLE001 - partial layer failure is visible
            layer_errors[layer_name] = type(exc).__name__
            continue
        for feature in collection.get("features") or []:
            if not feature.get("geometry"):
                continue
            properties = feature.get("properties") or {}
            source_feature_id = _property(
                properties, "permanent_identifier", "permanentIdentifier", "OBJECTID"
            )
            raw = {
                "candidate_id": f"USGS_NHDPLUS_HR:{layer_name}:{source_feature_id}",
                "source": "USGS_NHDPLUS_HR",
                "source_layer": layer_name,
                "source_feature_id": str(source_feature_id),
                "object_id": _property(properties, "OBJECTID"),
                "gnis_name": _property(properties, "gnis_name", "GNIS_Name"),
                "ftype": _property(properties, "ftype", "FType"),
                "fcode": _property(properties, "fcode", "FCode"),
                "intersects_parcel": bool(shape(feature["geometry"]).intersects(parcel_wgs84)),
                "as_of": fetched_at,
            }
            inventory.append(raw)
            candidate_geometries.append(transform(project, shape(feature["geometry"])))
    if not raw_layers:
        raise F03NHDAdapterError("All NHDPlus HR layer queries failed")

    inventory.sort(key=lambda row: (row["candidate_id"], row["source_layer"]))
    mapped_records = [build_mapped_candidate_from_nhd(row) for row in inventory]
    sample = stable_sample_f03_candidates(mapped_records, max_n=3)
    # Seasonal FCode is useful context, but without a provenance-complete reviewed
    # image it cannot promote physical presence. These remain mapped candidates.
    sampled_records = [
        apply_remote_enrichment(record, seasonal_from_fcode=True, reviewed_presence=None)
        for record in sample["selected"]
    ]
    levels = [
        str((record.get("verification_level") or {}).get("status"))
        for record in mapped_records
    ]
    distances = _distance_distribution(parcel, candidate_geometries)
    return {
        "factor_id": "F03_LIVESTOCK_WATER",
        "input_quality_state": factor_input_quality_from_levels(levels),
        "derivation_spec": DERIVATION_SPEC,
        "evidence_contract": EVIDENCE_CONTRACT,
        "geometry_id": geometry_id,
        "geometry_hash": geometry_hash,
        "working_crs": working_crs,
        "query_bbox_wgs84": list(bbox),
        "mapped_candidate_count": len(mapped_records),
        "verified_livestock_water_system_count": 0,
        "field_verified_count": 0,
        "euclidean_distance_to_mapped_candidate_m": {
            key: distances.get(key) for key in ("minimum", "median", "p90", "maximum")
        },
        "euclidean_distance_to_verified_livestock_water_m": None,
        "remote_evidence_summary": {
            "total_mapped_candidates": len(mapped_records),
            "deterministically_sampled_for_remote_review": sample["sampled_count"],
            "remotely_supported": 0,
            "sampled_but_still_mapped": sample["sampled_count"],
            "field_verified": 0,
            "unreviewed_candidates": max(0, len(mapped_records) - sample["sampled_count"]),
            "unreviewed_status": "UNREVIEWED_NOT_ABSENT_OR_REJECTED",
            "selection_method": sample["selection_method"],
            "imagery_review_status": "PENDING_PROVENANCE_COMPLETE_REVIEW",
            "remotely_supported_does_not_mean_usable_livestock_water": True,
            "verified_count_zero_does_not_mean_no_water": True,
            "unresolved_dimensions": [
                "physical_presence",
                "seasonal_reliability_for_livestock_use",
                "deliverable_capacity",
                "water_quality",
                "livestock_accessibility",
                "legal_access",
            ],
        },
        "candidate_inventory": mapped_records,
        "remote_review_queue": sampled_records,
        "coverage": {
            "status": "PARTIAL" if layer_errors else "COMPLETE",
            "successful_layers": sorted(raw_layers),
            "failed_layers": sorted(layer_errors),
        },
        "provenance": {
            "source_reference": "USGS_NHDPLUS_HR",
            "retrieved_at": fetched_at,
            "response_or_artifact_hash": _hash_json(raw_layers),
            "adapter_id": ADAPTER_ID,
            "geometry_hash": geometry_hash,
        },
        "limitations": [
            "Mapped NHD hydrography features are candidate context, not verified livestock-water sources.",
            "No candidate is remotely supported until imagery presence review has complete provenance.",
            "Euclidean distance is not traversable livestock-access distance.",
            "Reliability, capacity, quality, legal access, infrastructure, and seasonal operation remain unknown.",
            "FIELD_VERIFIED remains zero without field/operator or reviewed-equivalent evidence.",
        ],
        "unknowns": [
            "Mapped candidate presence and livestock usability require verification.",
            "Water-system reliability, capacity, quality, accessibility, and legal access are unknown.",
        ],
        "ranking_effect": "NONE",
    }
