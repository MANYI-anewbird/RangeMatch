"""Derive CPER mapped-water candidate inventory and Euclidean distance context."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely import contains_xy, distance, points, union_all
from shapely.geometry import shape
from shapely.ops import transform


PROJECT = Path("/Users/hongmanyi/RangeMatch")
PARCEL_PATH = PROJECT / "test-data/engineering_test_geometry_cper_001.geojson"
SOURCE_FILES = {
    "NetworkNHDFlowline": PROJECT / "test-data/live-results/cper/cper_nhd_network_flowlines.geojson",
    "NonNetworkNHDFlowline": PROJECT / "test-data/live-results/cper/cper_nhd_nonnetwork_flowlines.geojson",
    "NHDArea": PROJECT / "test-data/live-results/cper/cper_nhd_areas.geojson",
    "NHDWaterbody": PROJECT / "test-data/live-results/cper/cper_nhd_waterbodies.geojson",
}
OUTPUT_PATH = Path("/tmp/cper_f03_candidate_distance_result_2026-08-07.json")
WORKING_CRS = "EPSG:32613"
CELL_SIZE_M = 10.0


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_geometry_hash(geometry) -> str:
    return hashlib.sha256(geometry.wkb).hexdigest()


parcel_bytes = PARCEL_PATH.read_bytes()
parcel_data = json.loads(parcel_bytes)
parcel_wgs84 = shape(parcel_data["features"][0]["geometry"])
project = Transformer.from_crs("EPSG:4326", WORKING_CRS, always_xy=True).transform
parcel = transform(project, parcel_wgs84)

inventory = []
candidate_geometries = []
response_hashes = {}
for layer_name, path in SOURCE_FILES.items():
    raw = path.read_bytes()
    response_hashes[layer_name] = hash_bytes(raw)
    collection = json.loads(raw)
    for index, feature in enumerate(collection.get("features", [])):
        properties = feature.get("properties") or {}
        geometry_wgs84 = shape(feature["geometry"])
        geometry = transform(project, geometry_wgs84)
        source_feature_id = (
            properties.get("permanent_identifier")
            or properties.get("permanent_Identifier")
            or str(properties.get("OBJECTID"))
        )
        candidate_id = f"USGS_NHDPLUS_HR:{layer_name}:{source_feature_id}"
        inventory.append(
            {
                "candidate_id": candidate_id,
                "source": "USGS_NHDPLUS_HR",
                "source_layer": layer_name,
                "source_feature_id": source_feature_id,
                "object_id": properties.get("OBJECTID"),
                "geometry_type": geometry.geom_type,
                "geometry_hash": canonical_geometry_hash(geometry),
                "intersects_parcel": bool(geometry.intersects(parcel)),
                "verification_status": "MAPPED_CANDIDATE",
                "gnis_name": properties.get("gnis_name"),
                "ftype": properties.get("ftype"),
                "fcode": properties.get("fcode"),
                "reachcode": properties.get("reachcode"),
                "source_feature_date_epoch_ms": properties.get("fdate"),
                "permitted_interpretation": "Mapped hydrography candidate context only; not verified livestock water.",
            }
        )
        candidate_geometries.append(geometry)

minx, miny, maxx, maxy = parcel.bounds
xs = np.arange(np.floor(minx / CELL_SIZE_M) * CELL_SIZE_M + CELL_SIZE_M / 2, maxx, CELL_SIZE_M)
ys = np.arange(np.floor(miny / CELL_SIZE_M) * CELL_SIZE_M + CELL_SIZE_M / 2, maxy, CELL_SIZE_M)
xx, yy = np.meshgrid(xs, ys)
inside = contains_xy(parcel, xx, yy)
cell_x = xx[inside]
cell_y = yy[inside]

if candidate_geometries:
    candidates = union_all(candidate_geometries)
    values = distance(points(cell_x, cell_y), candidates)
    values = np.asarray(values, dtype=float)
    quantiles = np.percentile(values, [10, 25, 50, 75, 90], method="linear")
    distance_summary = {
        "valid_cell_count": int(values.size),
        "minimum": float(values.min()),
        "maximum": float(values.max()),
        "mean": float(values.mean()),
        "median": float(quantiles[2]),
        "p10": float(quantiles[0]),
        "p25": float(quantiles[1]),
        "p75": float(quantiles[3]),
        "p90": float(quantiles[4]),
    }
else:
    distance_summary = None

result = {
    "result_id": "CPER_F03_CANDIDATE_DISTANCE_2026_08_07",
    "derivation_spec": "F03_CANDIDATE_WATER_DERIVATION_SPEC.yaml@0.1.0",
    "quality_state": "CANDIDATE_INVENTORY_COMPLETE",
    "geometry_id": "ENGINEERING_TEST_GEOMETRY_CPER_001",
    "geometry_sha256": hash_bytes(parcel_bytes),
    "source_service": "USGS_NHDPLUS_HR_MapServer_11.3",
    "source_layer_ids": [3, 4, 8, 9],
    "raw_response_hashes": response_hashes,
    "working_crs": WORKING_CRS,
    "cell_size_m": CELL_SIZE_M,
    "grid_origin_m": {"x": float(xs[0]), "y": float(ys[0])},
    "parcel_cell_count": int(cell_x.size),
    "candidate_count": len(inventory),
    "candidate_inventory": inventory,
    "euclidean_distance_to_mapped_candidate_m": distance_summary,
    "verified_livestock_water_candidate_count": 0,
    "euclidean_distance_to_verified_livestock_water_m": None,
    "factor_input_quality_state": "MAPPED_CANDIDATES_ONLY",
    "factor_signal": "NEEDS_VERIFICATION",
    "prohibited_interpretation": [
        "mapped candidate equals livestock source",
        "Euclidean distance equals traversable distance",
        "parcel intersection proves reliability, capacity, quality, or legal access",
    ],
}
OUTPUT_PATH.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({k: result[k] for k in ["quality_state", "parcel_cell_count", "candidate_count", "euclidean_distance_to_mapped_candidate_m", "factor_signal"]}, indent=2))
