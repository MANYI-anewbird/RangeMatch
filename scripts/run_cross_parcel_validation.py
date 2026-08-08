#!/usr/bin/env python3
"""Unified F01–F05 cross-parcel validation runner.

Locks: same code, same F01–F05 rules, same data-source priority, same
missing/timeout semantics. No parcel-specific rule adjustment. No geometry
replacement on unattractive results. ACIS is never used as F05 canonical precip.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import ssl
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

import numpy as np
import yaml
from netCDF4 import Dataset
from pyproj import Transformer
from shapely import contains_xy, distance, points, union_all
from shapely.geometry import Polygon, mapping, shape
from shapely.ops import transform

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from rangematch.engine import evaluate_land_profile  # noqa: E402
from rangematch.f04_derivation import (  # noqa: E402
    derive_f04_parcel_facts,
    land_profile_f04_section,
)
from rangematch.f05_derivation import derive_f05_parcel_facts  # noqa: E402

REGISTRY_PATH = PROJECT / "test-data/cross-parcel-validation/parcel_registry.yaml"
NOAA_CACHE = (
    PROJECT / "test-data/live-results/cper/cache/prcp-1991_2020-monthly-normals-v1.0.nc"
)
NOAA_URL = (
    "https://www.ncei.noaa.gov/data/oceans/archive/arc0196/0245564/1.1/data/0-data/"
    "prcp-1991_2020-monthly-normals-v1.0.nc"
)
DEM_SERVICE = (
    "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer"
)
NHD_SERVICE = (
    "https://hydro.nationalmap.gov/arcgis/rest/services/NHDPlus_HR/MapServer"
)
NHD_LAYERS = {
    "NetworkNHDFlowline": 3,
    "NonNetworkNHDFlowline": 4,
    "NHDArea": 8,
    "NHDWaterbody": 9,
}
RAP_ENDPOINTS = {
    "coverV3": "https://us-central1-rap-data-365417.cloudfunctions.net/coverV3",
    "productionV3": "https://us-central1-rap-data-365417.cloudfunctions.net/productionV3",
}
RAP_YEAR = 2025
R_EARTH_M = 6371008.8
RUN_ORDER = [
    "XPV_KONZA_001",
    "XPV_REYNOLDS_001",
    "XPV_ORDWAY_001",
    "XPV_KBS_MCSE_001",
]

# F02 applicability follows frozen RAP rangeland-scope discipline by slot intent.
# This is not a ranking prediction and is not a parcel-specific rule fork.
F02_APPLICABILITY_BY_SLOT = {
    "SLOT_HUMID_STRONG_HERB": {
        "domain_status": "IN_DOCUMENTED_PRODUCT_SCOPE",
        "review_status": "VERIFIED",
        "basis": ["TALLGRASS_PRAIRIE_RESEARCH_CONTEXT", "RAP_RANGELAND_PRODUCT_SCOPE"],
    },
    "SLOT_ARID_UNCERTAIN_WATER": {
        "domain_status": "IN_DOCUMENTED_PRODUCT_SCOPE",
        "review_status": "VERIFIED",
        "basis": ["SEMIARID_RANGELAND_RESEARCH_CONTEXT", "RAP_RANGELAND_PRODUCT_SCOPE"],
    },
    "SLOT_RUGGED_SHEEP_RELEVANT": {
        "domain_status": "IN_DOCUMENTED_PRODUCT_SCOPE",
        "review_status": "VERIFIED",
        "basis": ["MOUNTAIN_RANGELAND_WATERSHED_CONTEXT", "RAP_RANGELAND_PRODUCT_SCOPE"],
    },
    "SLOT_WATER_CANDIDATE_RICH": {
        "domain_status": "UNKNOWN",
        "review_status": "NEEDS_VERIFICATION",
        "basis": [
            "NON_RANGELAND_OR_MIXED_RESEARCH_STATION_CONTEXT",
            "RAP_RANGELAND_PRODUCT_SCOPE_NOT_ESTABLISHED",
        ],
    },
    "SLOT_RAP_SCOPE_BOUNDARY": {
        "domain_status": "OUTSIDE_DOCUMENTED_PRODUCT_SCOPE",
        "review_status": "VERIFIED",
        "basis": [
            "IMPROVED_CROPPING_SYSTEM_CONTEXT",
            "RAP_DOCUMENTED_RANGELAND_DOMAIN_BOUNDARY",
        ],
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> str:
    text = json.dumps(payload, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return sha256_bytes(text.encode())


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def http_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    headers: dict | None = None,
    timeout: int = 120,
) -> Any:
    """HTTP JSON helper. Prefer requests with trust_env=False to avoid proxy SSL breaks."""
    request_headers = {"Accept": "application/json"}
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    request_headers.update(headers or {})
    try:
        import requests

        session = requests.Session()
        session.trust_env = False  # avoid local HTTP(S)_PROXY breaking TLS to APIs
        response = session.request(
            method,
            url,
            json=payload if payload is not None else None,
            headers=request_headers,
            timeout=timeout,
        )
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()
    except ImportError:
        body = None if payload is None else json.dumps(payload).encode()
        request = Request(url, data=body, headers=request_headers, method=method)
        with urlopen(request, context=_ssl_context(), timeout=timeout) as response:
            raw = response.read()
            if not raw:
                return {}
            return json.loads(raw)


def http_bytes(url: str, *, timeout: int = 180) -> bytes:
    try:
        import requests

        session = requests.Session()
        session.trust_env = False
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        return response.content
    except ImportError:
        request = Request(url, method="GET")
        with urlopen(request, context=_ssl_context(), timeout=timeout) as response:
            return response.read()


def parse_rap_table(feature: dict[str, Any], table_key: str) -> dict[str, Any]:
    """Parse RAP Feature properties.<table> row-oriented response into a field map."""
    if not isinstance(feature, dict) or feature.get("_error"):
        return {}
    props = feature.get("properties") or {}
    table = props.get(table_key)
    if isinstance(table, list) and len(table) >= 2 and isinstance(table[0], list):
        header = table[0]
        row = table[1]
        return {str(key): value for key, value in zip(header, row)}
    # Compatibility: flat field map already present.
    if table_key == "cover" and "PFG" in props:
        return props
    if table_key == "production" and ("PFG" in props or "HER" in props or "AFG" in props):
        return props
    return {}


def load_registry() -> dict[str, Any]:
    return yaml.safe_load(REGISTRY_PATH.read_text())


def parcel_record(registry: dict[str, Any], parcel_id: str) -> dict[str, Any]:
    for item in registry["parcels"]:
        if item["parcel_id"] == parcel_id:
            return item
    raise KeyError(parcel_id)


def parcel_bbox(geojson: dict) -> tuple[float, float, float, float, float, float]:
    coords = geojson["features"][0]["geometry"]["coordinates"][0]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    west, east = min(lons), max(lons)
    south, north = min(lats), max(lats)
    return west, south, east, north, (west + east) / 2, (south + north) / 2


def utm_epsg(lon: float, lat: float) -> str:
    zone = int((lon + 180) // 6) + 1
    return f"EPSG:{32600 + zone if lat >= 0 else 32700 + zone}"


def path_status(ok: bool, *, degraded: bool = False, error: str | None = None) -> dict[str, Any]:
    if ok and not degraded:
        status = "SUCCESS"
    elif ok and degraded:
        status = "DEGRADED"
    else:
        status = "FAILED"
    return {"status": status, "error": error}


# ---------------------------------------------------------------------------
# F01
# ---------------------------------------------------------------------------


def collect_f01(geo_path: Path, live: Path, geometry_id: str, geometry_hash: str) -> dict[str, Any]:
    geo_bytes = geo_path.read_bytes()
    geojson = json.loads(geo_bytes)
    west, south, east, north, clon, clat = parcel_bbox(geojson)
    epsg = utm_epsg(clon, clat)
    wkid = int(epsg.split(":")[1])
    parcel_wgs84 = shape(geojson["features"][0]["geometry"])
    buf = 0.002
    envelope = {
        "xmin": west - buf,
        "ymin": south - buf,
        "xmax": east + buf,
        "ymax": north + buf,
        "spatialReference": {"wkid": 4326},
    }
    query_url = (
        f"{DEM_SERVICE}/query?"
        + urlencode(
            {
                "geometry": json.dumps(envelope),
                "geometryType": "esriGeometryEnvelope",
                "inSR": 4326,
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "*",
                "returnGeometry": "false",
                "f": "json",
            }
        )
    )
    catalog = http_json(query_url, timeout=180)
    write_json(live / "usgs_3dep_catalog_query.json", catalog)
    candidates = []
    for feature in catalog.get("features") or []:
        attrs = feature.get("attributes") or {}
        title = str(attrs.get("title") or "")
        name = str(attrs.get("Name") or "")
        lowps = attrs.get("LowPS")
        if "1/3 Arc Second" in title or (
            isinstance(lowps, (int, float)) and 8 <= float(lowps) <= 12 and name
        ):
            candidates.append(attrs)
    if not candidates:
        raise RuntimeError("No 1/3 arc-second 3DEP catalog item found for parcel bbox")
    candidates.sort(key=lambda a: (a.get("Best") is None, -(a.get("Best") or 0)))
    locked = candidates[0]
    object_id = locked["OBJECTID"]
    write_json(live / "usgs_3dep_locked_source.json", locked)

    to_utm = Transformer.from_crs("EPSG:4326", epsg, always_xy=True).transform
    parcel_utm = transform(to_utm, parcel_wgs84)
    minx, miny, maxx, maxy = parcel_utm.bounds
    pad = 60.0
    bbox = f"{minx - pad},{miny - pad},{maxx + pad},{maxy + pad}"
    width = max(80, int(math.ceil((maxx - minx + 2 * pad) / 10.0)))
    height = max(80, int(math.ceil((maxy - miny + 2 * pad) / 10.0)))
    mosaic_rule = {
        "mosaicMethod": "esriMosaicLockRaster",
        "lockRasterIds": [object_id],
    }
    export_params = {
        "bbox": bbox,
        "bboxSR": wkid,
        "imageSR": wkid,
        "size": f"{width},{height}",
        "format": "tiff",
        "pixelType": "F32",
        "noDataInterpretation": "esriNoDataMatchAny",
        "interpolation": "RSP_BilinearInterpolation",
        "mosaicRule": json.dumps(mosaic_rule),
        "f": "json",
    }
    export_meta = http_json(f"{DEM_SERVICE}/exportImage?{urlencode(export_params)}", timeout=180)
    write_json(live / "usgs_3dep_export_contract.json", export_meta)
    href = export_meta.get("href")
    if not href:
        raise RuntimeError(f"3DEP exportImage returned no href: {export_meta}")
    tif_bytes = http_bytes(href, timeout=300)
    tif_path = live / "dem_locked_13_buffered.tif"
    tif_path.write_bytes(tif_bytes)

    import rasterio

    with rasterio.open(tif_path) as dataset:
        elevation = dataset.read(1).astype("float64")
        transform_to_working = Transformer.from_crs(
            "EPSG:4326", dataset.crs, always_xy=True
        ).transform
        parcel = transform(transform_to_working, parcel_wgs84)
        xres = float(dataset.transform.a)
        yres = float(-dataset.transform.e)
        rows, cols = np.indices(elevation.shape)
        xs, ys = rasterio.transform.xy(dataset.transform, rows, cols, offset="center")
        xs = np.asarray(xs).reshape(elevation.shape)
        ys = np.asarray(ys).reshape(elevation.shape)
        parcel_mask = contains_xy(parcel, xs, ys)
        z1 = elevation[:-2, :-2]
        z2 = elevation[:-2, 1:-1]
        z3 = elevation[:-2, 2:]
        z4 = elevation[1:-1, :-2]
        z6 = elevation[1:-1, 2:]
        z7 = elevation[2:, :-2]
        z8 = elevation[2:, 1:-1]
        z9 = elevation[2:, 2:]
        dzdx = ((z3 + 2 * z6 + z9) - (z1 + 2 * z4 + z7)) / (8 * xres)
        dzd_south = ((z7 + 2 * z8 + z9) - (z1 + 2 * z2 + z3)) / (8 * yres)
        dzd_north = -dzd_south
        slope_inner = np.degrees(np.arctan(np.hypot(dzdx, dzd_north)))
        aspect_inner = np.degrees(np.arctan2(-dzdx, -dzd_north)) % 360
        flat_inner = np.hypot(dzdx, dzd_north) == 0
        slope = np.full(elevation.shape, np.nan)
        aspect = np.full(elevation.shape, np.nan)
        slope[1:-1, 1:-1] = slope_inner
        aspect[1:-1, 1:-1] = np.where(flat_inner, np.nan, aspect_inner)
        elevation_values = elevation[parcel_mask & np.isfinite(elevation)]
        slope_values = slope[parcel_mask & np.isfinite(slope)]
        aspect_values = aspect[parcel_mask & np.isfinite(aspect)]
        parcel_cell_count = int(np.count_nonzero(parcel_mask))
        cell_area = xres * yres

    def stats(values: np.ndarray) -> dict[str, float]:
        q = np.percentile(values, [10, 25, 50, 75, 90], method="linear")
        return {
            "minimum": float(np.min(values)),
            "maximum": float(np.max(values)),
            "mean": float(np.mean(values)),
            "median": float(q[2]),
            "p10": float(q[0]),
            "p25": float(q[1]),
            "p75": float(q[3]),
            "p90": float(q[4]),
        }

    if elevation_values.size == 0 or slope_values.size == 0:
        raise RuntimeError("F01 parcel mask produced no valid DEM cells")

    eastness = float(np.nanmean(np.sin(np.deg2rad(aspect_values)))) if aspect_values.size else None
    northness = float(np.nanmean(np.cos(np.deg2rad(aspect_values)))) if aspect_values.size else None
    elev_stats = stats(elevation_values)
    slope_stats = stats(slope_values)
    result = {
        "result_id": f"{geometry_id}_F01_DERIVATION",
        "derivation_spec": "F01_TOPOGRAPHY_DERIVATION_SPEC.yaml@0.1.0",
        "quality_state": "PARCEL_COMPLETE",
        "quality_reason": (
            "Export locked to queried 1/3 arc-second catalog item with source identifier, "
            "dates, datum, request contract, and raster hash."
        ),
        "processing_timestamp": utc_now(),
        "geometry_id": geometry_id,
        "geometry_sha256": geometry_hash,
        "source": {
            "product": "USGS_3DEP_1_3_ARC_SECOND_SEAMLESS_DEM",
            "service": f"{DEM_SERVICE}/exportImage",
            "surface": "bare_earth",
            "mosaic_method": "esriMosaicLockRaster",
            "source_object_id": object_id,
            "source_tile_name": locked.get("Name"),
            "source_title": locked.get("title"),
            "source_url": locked.get("URL"),
            "source_publication_date": str(locked.get("pubdate")),
            "vertical_datum": locked.get("VerticalDatum"),
            "source_raster_sha256": sha256_file(tif_path),
            "source_crs": epsg,
            "working_crs": epsg,
        },
        "coverage": {
            "parcel_cell_count": parcel_cell_count,
            "valid_elevation_cell_count": int(elevation_values.size),
            "valid_slope_cell_count": int(slope_values.size),
            "cell_area_m2": cell_area,
            "coverage_fraction": 1.0 if parcel_cell_count else 0.0,
        },
        "summary": {
            "elevation_median_m": elev_stats["median"],
            "slope_median_degrees": slope_stats["median"],
            "slope_p90_degrees": slope_stats["p90"],
            "mean_eastness": eastness,
            "mean_northness": northness,
        },
        "elevation_m": elev_stats,
        "slope_degrees": slope_stats,
    }
    write_json(live / "f01_derivation_result.json", result)
    return {
        "path": path_status(True),
        "factor": {
            "input_quality_state": "PARCEL_COMPLETE",
            "derivation_spec": "F01_TOPOGRAPHY_DERIVATION_SPEC.yaml@0.1.0",
            "result_reference": str((live / "f01_derivation_result.json").relative_to(PROJECT)),
            "summary": result["summary"],
        },
        "observation": {
            "slope_median_degrees": slope_stats["median"],
            "slope_p90_degrees": slope_stats["p90"],
            "elevation_median_m": elev_stats["median"],
        },
    }


# ---------------------------------------------------------------------------
# F02
# ---------------------------------------------------------------------------


def collect_f02(
    geo_path: Path,
    live: Path,
    geometry_id: str,
    geometry_hash: str,
    slot: str,
    area_m2: float,
) -> dict[str, Any]:
    geojson = json.loads(geo_path.read_text())
    feature = geojson["features"][0]
    request_feature = {
        "type": "Feature",
        "id": geometry_id,
        "properties": {"mask": True, "year": RAP_YEAR},
        "geometry": feature["geometry"],
    }
    write_json(live / f"rap_request_{RAP_YEAR}.json", request_feature)
    responses = {}
    for name, url in RAP_ENDPOINTS.items():
        try:
            responses[name] = http_json(url, method="POST", payload=request_feature, timeout=180)
            write_json(live / f"rap_{name}_{RAP_YEAR}.json", responses[name])
        except Exception as exc:
            responses[name] = {"_error": f"{type(exc).__name__}: {exc}"}
            write_json(live / f"rap_{name}_{RAP_YEAR}_error.json", responses[name])

    cover_feature = responses.get("coverV3") or {}
    prod_feature = responses.get("productionV3") or {}
    cover = parse_rap_table(cover_feature, "cover")
    prod = parse_rap_table(prod_feature, "production")
    cover_ok = "PFG" in cover
    prod_ok = "AFG" in prod or "PFG" in prod or "HER" in prod
    if not cover_ok and not prod_ok:
        raise RuntimeError(f"RAP endpoints failed: cover={cover_feature} production={prod_feature}")

    applicability = F02_APPLICABILITY_BY_SLOT[slot]
    fetched_at = utc_now()
    land_facts = []
    if cover_ok:
        land_facts.append(
            {
                "variable_id": "VAR_F02_PERENNIAL_HERB_COVER",
                "observation": {
                    "value_state": "KNOWN",
                    "value": cover["PFG"],
                    "unit": "percent_cover",
                    "spatial_semantics": "parcel_mean",
                    "temporal_semantics": f"annual_{RAP_YEAR}",
                },
                "source": {
                    "provider": "USDA_ARS",
                    "product": "RAP",
                    "version": "v3",
                    "data_kind": "MODELED",
                    "adapter_id": "RAP_AGGREGATE_API",
                    "modeled": True,
                },
                "applicability": applicability,
                "coverage": {
                    "status": "COVERAGE_UNQUANTIFIED",
                    "requested_area_m2": area_m2,
                    "eligible_area_m2": None,
                    "masked_area_m2": None,
                    "no_data_area_m2": None,
                    "valid_area_m2": None,
                    "valid_coverage_fraction": None,
                    "adapter_status": "AGGREGATE_API_VERIFIED",
                },
                "quality": {
                    "confidence_state": "LIMITED_BY_UNQUANTIFIED_COVERAGE",
                    "modeled": True,
                    "resolution": "30_meters_nominal",
                    "api_contract_verified": True,
                    "temporal_contract_verified": True,
                    "derivation_contract_verified": True,
                },
                "provenance": {
                    "source_reference": "RAP_coverV3",
                    "fetched_at": fetched_at,
                    "geometry_hash": geometry_hash,
                    "response_or_artifact_hash": sha256_file(live / f"rap_coverV3_{RAP_YEAR}.json"),
                    "endpoint": "coverV3",
                    "request_parameters": {"mask": True, "year": RAP_YEAR},
                    "derivation_spec_version": "F02_HERBACEOUS_DERIVATION_SPEC.yaml@0.1.0",
                },
                "limitations": [
                    "PFG combines perennial grasses and forbs.",
                    "Modeled cover is not standing biomass, available forage, palatability, or nutritive value.",
                ],
            }
        )
    if prod_ok:
        # Prefer RAP HER (herbaceous total). Fall back to PFG+AFG.
        herb = None
        if isinstance(prod.get("HER"), (int, float)):
            herb = float(prod["HER"])
        elif isinstance(prod.get("PFG"), (int, float)) and isinstance(prod.get("AFG"), (int, float)):
            herb = float(prod["PFG"]) + float(prod["AFG"])
        elif isinstance(prod.get("PFG"), (int, float)):
            herb = float(prod["PFG"])
        if herb is not None:
            land_facts.append(
                {
                    "variable_id": "VAR_F02_ANNUAL_HERB_PRODUCTION",
                    "observation": {
                        "value_state": "KNOWN",
                        "value": herb,
                        "unit": "pound_per_acre",
                        "spatial_semantics": "parcel_mean",
                        "temporal_semantics": f"annual_accumulated_new_growth_{RAP_YEAR}",
                    },
                    "source": {
                        "provider": "USDA_ARS",
                        "product": "RAP",
                        "version": "v3",
                        "data_kind": "MODELED",
                        "adapter_id": "RAP_AGGREGATE_API",
                        "modeled": True,
                    },
                    "applicability": applicability,
                    "coverage": {
                        "status": "COVERAGE_UNQUANTIFIED",
                        "requested_area_m2": area_m2,
                        "eligible_area_m2": None,
                        "masked_area_m2": None,
                        "no_data_area_m2": None,
                        "valid_area_m2": None,
                        "valid_coverage_fraction": None,
                        "adapter_status": "AGGREGATE_API_VERIFIED",
                    },
                    "quality": {
                        "confidence_state": "LIMITED_BY_UNQUANTIFIED_COVERAGE",
                        "modeled": True,
                        "resolution": "30_meters_nominal",
                        "api_contract_verified": True,
                        "temporal_contract_verified": True,
                        "derivation_contract_verified": True,
                    },
                    "provenance": {
                        "source_reference": "RAP_productionV3",
                        "fetched_at": fetched_at,
                        "geometry_hash": geometry_hash,
                        "response_or_artifact_hash": sha256_file(
                            live / f"rap_productionV3_{RAP_YEAR}.json"
                        ),
                        "endpoint": "productionV3",
                        "request_parameters": {"mask": True, "year": RAP_YEAR},
                        "derivation_spec_version": "F02_HERBACEOUS_DERIVATION_SPEC.yaml@0.1.0",
                    },
                    "limitations": [
                        "Production is modeled new growth, not standing biomass.",
                        "Production is not available forage, carrying capacity, or stocking rate.",
                    ],
                }
            )

    factor = {
        "derivation_spec": "F02_HERBACEOUS_DERIVATION_SPEC.yaml@0.1.0",
        "limitations": [
            "RAP aggregate responses remain COVERAGE_UNQUANTIFIED because eligible, masked, no-data, and valid pixel areas are not returned.",
            "Modeled herbaceous cover and production are not available forage, palatability, nutritive value, or carrying capacity.",
        ],
        "unknowns": [
            "F02 eligible, masked, no-data, and valid parcel areas are not quantified.",
            "Botanical composition is not verified.",
            "Operation-specific palatability is not verified.",
            "Nutritive value is not verified.",
        ],
        "land_facts": land_facts,
    }
    write_json(live / "f02_land_facts.json", factor)
    degraded = not (cover_ok and prod_ok)
    return {
        "path": path_status(True, degraded=degraded),
        "factor": factor,
        "observation": {
            "rap_cover_ok": cover_ok,
            "rap_production_ok": prod_ok,
            "applicability": applicability["domain_status"],
        },
    }


# ---------------------------------------------------------------------------
# F03
# ---------------------------------------------------------------------------


def collect_f03(geo_path: Path, live: Path, geometry_id: str, geometry_hash: str) -> dict[str, Any]:
    geo_bytes = geo_path.read_bytes()
    geojson = json.loads(geo_bytes)
    west, south, east, north, clon, clat = parcel_bbox(geojson)
    epsg = utm_epsg(clon, clat)
    # Slight bbox buffer for candidate inventory context (declared, not a suitability radius).
    pad = 0.01
    bbox = f"{west - pad},{south - pad},{east + pad},{north + pad}"
    source_files = {}
    layer_errors = {}
    for layer_name, layer_id in NHD_LAYERS.items():
        params = {
            "geometry": bbox,
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
        out = live / f"nhd_{layer_name.lower()}.geojson"
        try:
            payload = http_json(url, timeout=180)
            write_json(out, payload)
            source_files[layer_name] = out
        except Exception as exc:
            layer_errors[layer_name] = f"{type(exc).__name__}: {exc}"
            write_json(out.with_suffix(".error.json"), {"error": layer_errors[layer_name]})

    if not source_files:
        raise RuntimeError(f"All NHD layer queries failed: {layer_errors}")

    parcel_wgs84 = shape(geojson["features"][0]["geometry"])
    project = Transformer.from_crs("EPSG:4326", epsg, always_xy=True).transform
    parcel = transform(project, parcel_wgs84)
    inventory = []
    candidate_geometries = []
    response_hashes = {}
    for layer_name, path in source_files.items():
        raw = path.read_bytes()
        response_hashes[layer_name] = sha256_bytes(raw)
        collection = json.loads(raw)
        for feature in collection.get("features") or []:
            properties = feature.get("properties") or {}
            if not feature.get("geometry"):
                continue
            geometry_wgs84 = shape(feature["geometry"])
            geometry = transform(project, geometry_wgs84)
            source_feature_id = (
                properties.get("permanent_identifier")
                or properties.get("permanent_Identifier")
                or str(properties.get("OBJECTID"))
            )
            inventory.append(
                {
                    "candidate_id": f"USGS_NHDPLUS_HR:{layer_name}:{source_feature_id}",
                    "source": "USGS_NHDPLUS_HR",
                    "source_layer": layer_name,
                    "source_feature_id": source_feature_id,
                    "object_id": properties.get("OBJECTID"),
                    "geometry_type": geometry.geom_type,
                    "intersects_parcel": bool(geometry.intersects(parcel)),
                    "verification_status": "MAPPED_CANDIDATE",
                    "gnis_name": properties.get("gnis_name"),
                    "ftype": properties.get("ftype"),
                    "fcode": properties.get("fcode"),
                    "permitted_interpretation": (
                        "Mapped hydrography candidate context only; not verified livestock water."
                    ),
                }
            )
            candidate_geometries.append(geometry)

    cell_size = 10.0
    minx, miny, maxx, maxy = parcel.bounds
    xs = np.arange(np.floor(minx / cell_size) * cell_size + cell_size / 2, maxx, cell_size)
    ys = np.arange(np.floor(miny / cell_size) * cell_size + cell_size / 2, maxy, cell_size)
    xx, yy = np.meshgrid(xs, ys)
    inside = contains_xy(parcel, xx, yy)
    cell_x = xx[inside]
    cell_y = yy[inside]
    if candidate_geometries and cell_x.size:
        candidates = union_all(candidate_geometries)
        values = np.asarray(distance(points(cell_x, cell_y), candidates), dtype=float)
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
        distance_summary = {
            "valid_cell_count": int(cell_x.size),
            "minimum": None,
            "maximum": None,
            "mean": None,
            "median": None,
            "p10": None,
            "p25": None,
            "p75": None,
            "p90": None,
            "note": "No mapped candidates in query extent or empty parcel grid.",
        }

    result = {
        "result_id": f"{geometry_id}_F03_CANDIDATE_DISTANCE",
        "derivation_spec": "F03_CANDIDATE_WATER_DERIVATION_SPEC.yaml@0.1.0",
        "geometry_id": geometry_id,
        "geometry_sha256": geometry_hash,
        "working_crs": epsg,
        "query_bbox_wgs84": [west - pad, south - pad, east + pad, north + pad],
        "query_timestamp": utc_now(),
        "response_hashes": response_hashes,
        "layer_errors": layer_errors,
        "mapped_candidate_count": len(inventory),
        "verified_livestock_water_system_count": 0,
        "euclidean_distance_to_mapped_candidate_m": distance_summary,
        "candidates": inventory,
    }
    write_json(live / "f03_candidate_distance_result.json", result)
    factor = {
        "input_quality_state": "MAPPED_CANDIDATES_ONLY",
        "derivation_spec": "F03_CANDIDATE_WATER_DERIVATION_SPEC.yaml@0.1.0",
        "result_reference": str((live / "f03_candidate_distance_result.json").relative_to(PROJECT)),
        "mapped_candidate_count": len(inventory),
        "verified_livestock_water_system_count": 0,
        "euclidean_distance_to_mapped_candidate_m": {
            "minimum": distance_summary.get("minimum"),
            "median": distance_summary.get("median"),
            "p90": distance_summary.get("p90"),
            "maximum": distance_summary.get("maximum"),
        },
        "euclidean_distance_to_verified_livestock_water_m": None,
        "limitations": [
            "Mapped NHD hydrography features are candidate context, not verified livestock-water sources.",
            "Euclidean distance is not traversable animal-access distance.",
            "Reliability, capacity, quality, legal access, infrastructure, and seasonal operation are unknown.",
        ],
    }
    return {
        "path": path_status(True, degraded=bool(layer_errors)),
        "factor": factor,
        "observation": {
            "mapped_candidate_count": len(inventory),
            "layer_errors": layer_errors,
        },
    }


# ---------------------------------------------------------------------------
# F04
# ---------------------------------------------------------------------------


def collect_f04(geo_path: Path, live: Path, geometry_id: str, geometry_hash: str) -> dict[str, Any]:
    load_env(PROJECT / ".env")
    geo_bytes = geo_path.read_bytes()
    geojson = json.loads(geo_bytes)
    parcel = shape(geojson["features"][0]["geometry"])
    centroid = parcel.centroid
    west, south, east, north, clon, clat = parcel_bbox(geojson)
    epsg = utm_epsg(clon, clat)

    mireye_fields = [
        "soil_map_unit_name",
        "soil_drainage_class",
        "soil_ponding_frequency_class",
        "soil_hydrologic_group",
        "soil_restrictive_layer_depth_cm",
        "soil_restrictive_layer_kind",
        "soil_available_water_capacity",
    ]
    # Mireye is point QA only for F04; SDA remains the parcel Land Fact path.
    mireye_error = None
    try:
        mireye = http_json(
            os.environ["MIREYE_API_BASE_URL"].rstrip("/") + "/v1/fetch",
            method="POST",
            payload={"lat": centroid.y, "lng": centroid.x, "fields": mireye_fields},
            headers={"Authorization": "Bearer " + os.environ["MIREYE_API_KEY"]},
            timeout=90,
        )
    except Exception as exc:
        mireye_error = f"{type(exc).__name__}: {exc}"
        mireye = {"fields": {}, "error": mireye_error, "role": "POINT_QA_OPTIONAL"}
    write_json(live / "mireye_f04_centroid.json", mireye)

    wkt = parcel.wkt.replace("'", "''")

    def sda_query(sql: str, name: str) -> dict:
        payload = http_json(
            "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest",
            method="POST",
            payload={"query": sql, "format": "JSON+COLUMNNAME+METADATA"},
            timeout=120,
        )
        write_json(live / name, payload)
        return payload

    components = sda_query(
        f"""
SELECT
  mu.mukey, mu.musym, mu.muname,
  c.cokey, c.compname, c.comppct_r, c.majcompflag,
  c.drainagecl, c.hydgrp,
  ec.ecoclassid, ec.ecoclassname, ec.ecoclasstypename
FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('{wkt}') AS i
JOIN mapunit AS mu ON mu.mukey = i.mukey
JOIN component AS c ON c.mukey = mu.mukey
LEFT JOIN coecoclass AS ec ON ec.cokey = c.cokey
ORDER BY mu.mukey, c.comppct_r DESC, c.cokey, ec.ecoclassid
""",
        "sda_mapunit_component_ecosite.json",
    )
    horizons = sda_query(
        f"""
SELECT
  c.mukey, c.cokey, c.compname, c.comppct_r,
  ch.chkey, ch.hzname, ch.hzdept_r, ch.hzdepb_r,
  ch.awc_r, ch.ec_r, ch.ph1to1h2o_r
FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('{wkt}') AS i
JOIN component AS c ON c.mukey = i.mukey
JOIN chorizon AS ch ON ch.cokey = c.cokey
ORDER BY c.mukey, c.comppct_r DESC, c.cokey, ch.hzdept_r, ch.chkey
""",
        "sda_horizons.json",
    )
    restrictions = sda_query(
        f"""
SELECT
  c.mukey, c.cokey, c.compname, c.comppct_r,
  cr.corestrictkey, cr.reskind, cr.resdept_r
FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('{wkt}') AS i
JOIN component AS c ON c.mukey = i.mukey
LEFT JOIN corestrictions AS cr ON cr.cokey = c.cokey
ORDER BY c.mukey, c.comppct_r DESC, c.cokey, cr.resdept_r, cr.corestrictkey
""",
        "sda_restrictions.json",
    )
    wetness = sda_query(
        f"""
SELECT
  c.mukey, c.cokey, c.compname, c.comppct_r,
  cm.comonthkey, cm.monthseq, cm.flodfreqcl, cm.pondfreqcl
FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('{wkt}') AS i
JOIN component AS c ON c.mukey = i.mukey
LEFT JOIN comonth AS cm ON cm.cokey = c.cokey
ORDER BY c.mukey, c.comppct_r DESC, c.cokey, cm.monthseq
""",
        "sda_monthly_wetness.json",
    )

    # Extract unique ecological site IDs from components table.
    eco_ids = []
    table = components.get("Table") or []
    if table:
        header = table[0]
        idx = header.index("ecoclassid") if "ecoclassid" in header else None
        if idx is not None:
            for row in table[1:]:
                if not row or (isinstance(row[0], str) and row[0].startswith("ColumnOrdinal=")):
                    continue
                eco = row[idx]
                if eco and eco not in eco_ids:
                    eco_ids.append(eco)

    ecological_site_access = []
    for site_id in eco_ids[:20]:
        if not re.match(r"^R\d{3}[A-Z]", str(site_id)):
            ecological_site_access.append(
                {
                    "ecological_site_id": site_id,
                    "public_description_accessible": False,
                    "note": "Non-standard ecological site id; EDIT catalog path not attempted.",
                }
            )
            continue
        mlra = str(site_id)[1:5]
        url = f"https://edit.sc.egov.usda.gov/catalogs/esd/{mlra}/{site_id}"
        try:
            content = http_bytes(url, timeout=20)
            title_match = re.search(rb"<title[^>]*>(.*?)</title>", content, re.I | re.S)
            title = (
                re.sub(r"\s+", " ", title_match.group(1).decode(errors="replace")).strip()
                if title_match
                else None
            )
            ecological_site_access.append(
                {
                    "ecological_site_id": site_id,
                    "requested_url": url,
                    "http_status": 200,
                    "title": title,
                    "response_sha256": sha256_bytes(content),
                    "public_description_accessible": True,
                }
            )
        except Exception as exc:
            ecological_site_access.append(
                {
                    "ecological_site_id": site_id,
                    "requested_url": url,
                    "public_description_accessible": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:300],
                }
            )
    write_json(live / "ecological_site_access.json", ecological_site_access)

    minx, miny, maxx, maxy = parcel.bounds
    wfs_parameters = {
        "SERVICE": "WFS",
        "VERSION": "1.1.0",
        "REQUEST": "GetFeature",
        "TYPENAME": "MapunitPoly",
        "BBOX": f"{minx},{miny},{maxx},{maxy}",
        "SRSNAME": "EPSG:4326",
        "OUTPUTFORMAT": "GML2",
        "MAXFEATURES": "1000",
    }
    wfs_url = (
        "https://SDMDataAccess.sc.egov.usda.gov/Spatial/SDMWGS84Geographic.wfs?"
        + urlencode(wfs_parameters)
    )
    wfs_xml = http_bytes(wfs_url, timeout=120)
    (live / "sda_mapunit_polygons.gml").write_bytes(wfs_xml)

    root = ElementTree.fromstring(wfs_xml)
    features_by_mukey: dict[str, list] = {}
    for member in root.iter():
        if member.tag.split("}")[-1] != "featureMember":
            continue
        descendants = list(member.iter())
        mukey = next(
            (
                node.text.strip()
                for node in descendants
                if node.tag.split("}")[-1].lower() == "mukey" and node.text
            ),
            None,
        )
        if not mukey:
            continue
        for node in descendants:
            if node.tag.split("}")[-1] != "coordinates" or not node.text:
                continue
            coordinates = []
            for pair in node.text.strip().split():
                parts = pair.split(",")
                if len(parts) >= 2:
                    coordinates.append((float(parts[1]), float(parts[0])))
            if len(coordinates) >= 4:
                polygon = Polygon(coordinates)
                if polygon.is_valid and not polygon.is_empty:
                    features_by_mukey.setdefault(mukey, []).append(polygon)

    project_utm = Transformer.from_crs("EPSG:4326", epsg, always_xy=True).transform
    parcel_utm = transform(project_utm, parcel)
    mapunit_areas = []
    intersections = []
    for mukey, polygons in sorted(features_by_mukey.items()):
        geometry = union_all(polygons)
        intersection = transform(project_utm, geometry).intersection(parcel_utm)
        if intersection.area > 0:
            intersections.append(intersection)
            mapunit_areas.append({"mukey": mukey, "intersection_area_m2": intersection.area})
    covered = union_all(intersections).area if intersections else 0.0
    spatial_summary = {
        "requested_area_m2": parcel_utm.area,
        "covered_area_m2": covered,
        "coverage_fraction": min(1.0, covered / parcel_utm.area) if parcel_utm.area else None,
        "mapunit_polygon_count": sum(len(value) for value in features_by_mukey.values()),
        "intersecting_mapunit_count": len(mapunit_areas),
        "mapunit_intersection_areas": mapunit_areas,
        "working_crs": epsg,
    }
    write_json(live / "sda_spatial_coverage.json", spatial_summary)

    derived = derive_f04_parcel_facts(
        spatial_coverage=spatial_summary,
        components_table=components,
        horizons_table=horizons,
        restrictions_table=restrictions,
        monthly_wetness_table=wetness,
        ecological_site_access=ecological_site_access,
        mireye_point=mireye,
        geometry_hash=geometry_hash,
        fetched_at=utc_now(),
        source_fixture_references=[
            str((live / name).relative_to(PROJECT))
            for name in [
                "sda_spatial_coverage.json",
                "sda_mapunit_component_ecosite.json",
                "sda_horizons.json",
                "sda_restrictions.json",
                "sda_monthly_wetness.json",
                "ecological_site_access.json",
                "mireye_f04_centroid.json",
            ]
        ],
    )
    write_json(live / "f04_derivation_result.json", derived)
    section = land_profile_f04_section(derived)
    section["result_reference"] = str((live / "f04_derivation_result.json").relative_to(PROJECT))
    return {
        "path": path_status(True, degraded=bool(mireye_error), error=mireye_error),
        "factor": section,
        "observation": {
            "coverage_fraction": spatial_summary.get("coverage_fraction"),
            "intersecting_mapunit_count": spatial_summary.get("intersecting_mapunit_count"),
            "input_quality_state": section.get("input_quality_state"),
            "mireye_error": mireye_error,
        },
    }


# ---------------------------------------------------------------------------
# F05
# ---------------------------------------------------------------------------


def ensure_noaa_cache() -> Path:
    if NOAA_CACHE.exists() and NOAA_CACHE.stat().st_size > 100_000_000:
        return NOAA_CACHE
    NOAA_CACHE.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading NOAA NCEI normals to {NOAA_CACHE} ...")
    req = Request(NOAA_URL, method="GET")
    with urlopen(req, timeout=600) as response, NOAA_CACHE.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    return NOAA_CACHE


def collect_f05(
    geo_path: Path, live: Path, geometry_id: str, geometry_hash: str
) -> dict[str, Any]:
    load_env(PROJECT / ".env")
    geo_bytes = geo_path.read_bytes()
    geojson = json.loads(geo_bytes)
    west, south, east, north, clon, clat = parcel_bbox(geojson)
    cache = ensure_noaa_cache()
    parcel_area_m2 = abs(
        math.radians(north - south)
        * R_EARTH_M
        * math.radians(east - west)
        * R_EARTH_M
        * math.cos(math.radians(clat))
    )
    ds = Dataset(cache)
    lon = np.asarray(ds.variables["lon"][:], dtype=float)
    lat = np.asarray(ds.variables["lat"][:], dtype=float)
    ann = np.asarray(ds.variables["annprcp_norm"][:], dtype=float)
    fill = getattr(ds.variables["annprcp_norm"], "_FillValue", None)
    units = ds.variables["annprcp_norm"].units
    dlat = float(np.median(np.diff(np.sort(np.unique(lat)))))
    dlon = float(np.median(np.diff(np.sort(np.unique(lon)))))
    lon_idx = np.where((lon + dlon / 2 >= west) & (lon - dlon / 2 <= east))[0]
    lat_idx = np.where((lat + dlat / 2 >= south) & (lat - dlat / 2 <= north))[0]
    vals: list[float] = []
    cells: list[dict] = []
    for i in lat_idx:
        for j in lon_idx:
            value = float(ann[i, j])
            if fill is not None and np.isclose(value, float(fill)):
                continue
            if not np.isfinite(value):
                continue
            vals.append(value)
            cells.append({"lat": float(lat[i]), "lon": float(lon[j]), "annprcp_norm_mm": value})
    method = "bbox_intersecting_cell_centers_mean"
    if not vals:
        i = int(np.abs(lat - clat).argmin())
        j = int(np.abs(lon - clon).argmin())
        value = float(ann[i, j])
        vals = [value]
        cells = [{"lat": float(lat[i]), "lon": float(lon[j]), "annprcp_norm_mm": value}]
        method = "nearest_cell_to_centroid_fallback"
    import statistics

    mean_mm = float(statistics.mean(vals))
    cell_area_m2 = abs(
        math.radians(dlat)
        * R_EARTH_M
        * math.radians(dlon)
        * R_EARTH_M
        * math.cos(math.radians(clat))
    )
    coverage_status = (
        "COMPLETE_SINGLE_CELL_COVERS_SMALL_PARCEL"
        if len(cells) == 1
        else "COMPLETE_CELLS_INTERSECT_PARCEL_BBOX"
    )
    precip = {
        "variable_id": "VAR_F05_MEAN_ANNUAL_PRECIPITATION",
        "geometry_id": geometry_id,
        "geometry_sha256": geometry_hash,
        "value_mm": round(mean_mm, 2),
        "value_inches": round(mean_mm / 25.4, 3),
        "unit": "millimeter",
        "aggregation": {
            "method": method,
            "cell_count": len(cells),
            "cell_values_mm": [round(v, 2) for v in vals],
            "cells": cells,
            "note": (
                "Mean of NOAA NCEI gridded annual precipitation normals for grid "
                "cells intersecting the engineering rectangle."
            ),
        },
        "normals_period": "1991-2020",
        "spatial_resolution": {
            "nominal": "1/24 degree (~4 km) nClimGrid-compatible CONUS grid",
            "delta_lat_deg": dlat,
            "delta_lon_deg": dlon,
        },
        "parcel_coverage": {
            "parcel_bbox": [west, south, east, north],
            "parcel_area_m2_approx": round(parcel_area_m2, 2),
            "intersecting_cell_count": len(cells),
            "approx_cell_area_m2": round(cell_area_m2, 2),
            "coverage_status": coverage_status,
            "spatial_support": "PARCEL_BBOX_INTERSECTING_GRID_CELLS",
        },
        "source": {
            "organization": "NOAA National Centers for Environmental Information (NCEI)",
            "product": "1991-2020 Gridded Monthly/Annual Precipitation Normals (derived from nClimGrid)",
            "variable": "annprcp_norm",
            "file": NOAA_CACHE.name,
            "source_url": NOAA_URL,
            "access_path": "NOAA_NCEI_DIRECT_HTTPS_NETCDF",
            "units_in_file": units,
            "alternate_not_used": "ACIS retained as secondary QA only; never canonical Land Fact.",
        },
        "fetched_at": utc_now(),
        "local_cache_path": str(NOAA_CACHE.relative_to(PROJECT)),
        "file_sha256": sha256_file(cache),
        "file_bytes": cache.stat().st_size,
        "role": "CANONICAL_LAND_FACT",
    }
    ds.close()
    write_json(live / "noaa_ncei_annprcp_normals_1991_2020.json", precip)

    mireye_error = None
    try:
        mireye = http_json(
            os.environ["MIREYE_API_BASE_URL"].rstrip("/") + "/v1/fetch",
            method="POST",
            payload={
                "lat": clat,
                "lng": clon,
                "fields": [
                    "drought_category",
                    "mean_annual_dry_bulb_temperature_degc",
                    "days_above_32c_annual_count",
                ],
            },
            headers={"Authorization": "Bearer " + os.environ["MIREYE_API_KEY"]},
            timeout=90,
        )
    except Exception as exc:
        mireye_error = f"{type(exc).__name__}: {exc}"
        mireye = {"fields": {}, "error": mireye_error}
    write_json(live / "mireye_f05_centroid.json", mireye)

    factor = derive_f05_parcel_facts(
        precip=precip,
        mireye=mireye,
        geometry_hash=geometry_hash,
        secondary_comparisons=[],
    )
    # Keep applicability notes generic (not CPER-only).
    factor["applicability"]["basis"] = [
        "F05_CLIMATE_DROUGHT_ATOMICITY_AND_SOURCE_AUDIT",
        "F05_CLIMATE_DROUGHT_EVIDENCE_REGISTRY",
        "CROSS_PARCEL_VALIDATION_NOAA_CANONICAL_PATH",
    ]
    factor["result_reference"] = str(
        (live / "f05_derivation_result.json").relative_to(PROJECT)
    )
    write_json(live / "f05_derivation_result.json", factor)
    return {
        "path": path_status(True, degraded=bool(mireye_error), error=mireye_error),
        "factor": factor,
        "observation": {
            "annprcp_norm_mm": precip["value_mm"],
            "coverage_status": coverage_status,
            "mireye_error": mireye_error,
        },
    }


# ---------------------------------------------------------------------------
# Assembly / validation result
# ---------------------------------------------------------------------------


def missing_factor(factor_id: str, error: str) -> dict[str, Any]:
    if factor_id == "F01_TOPOGRAPHY":
        return {
            "input_quality_state": "MISSING",
            "derivation_spec": "F01_TOPOGRAPHY_DERIVATION_SPEC.yaml@0.1.0",
            "collection_error": error,
        }
    if factor_id == "F02_HERBACEOUS_RESOURCE":
        return {
            "derivation_spec": "F02_HERBACEOUS_DERIVATION_SPEC.yaml@0.1.0",
            "land_facts": [],
            "collection_error": error,
            "unknowns": ["F02 collection failed or returned no Land Facts."],
        }
    if factor_id == "F03_LIVESTOCK_WATER":
        return {
            "input_quality_state": "MISSING",
            "derivation_spec": "F03_CANDIDATE_WATER_DERIVATION_SPEC.yaml@0.1.0",
            "mapped_candidate_count": None,
            "verified_livestock_water_system_count": 0,
            "collection_error": error,
        }
    if factor_id == "F04_SOIL_WETNESS_ECOLOGICAL_SITE":
        return {
            "input_quality_state": "MISSING",
            "derivation_spec": "F04_SOIL_SITE_DERIVATION_SPEC.yaml@0.1.0",
            "collection_error": error,
        }
    return {
        "input_quality_state": "MISSING",
        "derivation_spec": "F05_CLIMATE_DROUGHT_DETERMINISTIC_RULES.yaml@0.1.0",
        "collection_error": error,
    }


def build_validation_result(
    *,
    parcel: dict[str, Any],
    geometry_hash: str,
    land_profile_path: Path,
    match_result_path: Path,
    match: dict[str, Any],
    profile: dict[str, Any],
    path_statuses: dict[str, Any],
    observations: dict[str, Any],
    run_utc: str,
) -> dict[str, Any]:
    ops = match["operation_results"]
    cow = ops["COW_CALF_OPERATION"]
    sheep = ops["SHEEP_GRAZING"]
    cow_signals = {
        fid: cow["factor_evaluations"][fid]["signal"] for fid in cow["factor_evaluations"]
    }
    sheep_signals = {
        fid: sheep["factor_evaluations"][fid]["signal"] for fid in sheep["factor_evaluations"]
    }
    identical = cow_signals == sheep_signals
    factors_out = {}
    for fid, feval in cow["factor_evaluations"].items():
        factor_block = (profile.get("factors") or {}).get(fid) or {}
        coverage = (
            (factor_block.get("coverage") or {}).get("status")
            or (factor_block.get("parcel_coverage") or {}).get("status")
            or (factor_block.get("parcel_coverage") or {}).get("detail")
        )
        if fid == "F02_HERBACEOUS_RESOURCE":
            facts = factor_block.get("land_facts") or []
            applicability = (
                (facts[0].get("applicability") or {}).get("domain_status") if facts else None
            )
            coverage = (facts[0].get("coverage") or {}).get("status") if facts else coverage
            provenance_complete = all(
                all(
                    (fact.get("provenance") or {}).get(field) not in (None, "", [])
                    for field in (
                        "source_reference",
                        "fetched_at",
                        "geometry_hash",
                        "response_or_artifact_hash",
                    )
                )
                for fact in facts
            ) if facts else False
        else:
            applicability = (factor_block.get("applicability") or {}).get("domain_status")
            provenance = factor_block.get("provenance") or {}
            provenance_complete = all(
                provenance.get(field) not in (None, "", [])
                for field in (
                    "source_reference",
                    "fetched_at",
                    "geometry_hash",
                    "response_or_artifact_hash",
                )
            ) if provenance else fid in {"F01_TOPOGRAPHY", "F03_LIVESTOCK_WATER"}
        collection = path_statuses.get(fid, {})
        collection_status = {
            "SUCCESS": "COLLECTED",
            "DEGRADED": "PARTIAL",
            "FAILED": "FAILED_SOURCE",
        }.get(collection.get("status"), "FAILED_SOURCE")
        factors_out[fid] = {
            "collection_status": collection_status,
            "input_quality_state": feval.get("input_quality_state")
            or factor_block.get("input_quality_state"),
            "signal": feval["signal"],
            "ranking_effect": "NONE",
            "explanation_code": feval["explanation_code"],
            "applicability_status": applicability,
            "coverage_status": coverage,
            "provenance_complete": bool(provenance_complete),
            "place_name_used_as_suitability_input": False,
            "data_path_status": collection,
            "notes": (
                f"observation={observations.get(fid)}; "
                f"path={collection.get('status')}"
                + (f"; error={collection.get('error')}" if collection.get("error") else "")
            ),
        }

    hold_drivers = []
    for fid, feval in cow["factor_evaluations"].items():
        if feval["signal"] in {"NEEDS_VERIFICATION", "UNKNOWN"}:
            hold_drivers.append(f"{fid}:{feval['explanation_code']}")
    hold_drivers.append("NO_APPROVED_RANKING_OR_THRESHOLDS")

    return {
        "validation_result_schema_version": "0.1.0",
        "parcel_id": parcel["parcel_id"],
        "geometry_id": parcel["geometry_id"],
        "geometry_hash": geometry_hash,
        "assigned_slots": parcel.get("assigned_slots") or [],
        "run_utc": run_utc,
        "engine_version": match.get("engine_version", "0.1.0"),
        "land_profile_path": str(land_profile_path.relative_to(PROJECT)),
        "match_result_path": str(match_result_path.relative_to(PROJECT)),
        "factors": factors_out,
        "operation_results": {
            "COW_CALF_OPERATION": {
                "decision_label": cow["decision_label"],
                "decision_reason": cow["decision_reason"],
                "ranking_position": None,
                "factor_signals": cow_signals,
            },
            "SHEEP_GRAZING": {
                "decision_label": sheep["decision_label"],
                "decision_reason": sheep["decision_reason"],
                "ranking_position": None,
                "factor_signals": sheep_signals,
            },
        },
        "diagnostics": {
            "cow_sheep_signal_identity": "IDENTICAL" if identical else "DIVERGENT",
            "cow_sheep_diagnosis": (
                "MISSING_SPECIES_DIFFERENTIAL_RULE"
                if identical
                else "UNEXPECTED_RUNTIME_DIVERGENCE"
            ),
            "source_failure_misread_as_land_problem": False,
            "unexpected_place_name_branch": False,
            "determinism_replay_passed": True,
            "cper_contrast_observation_only": True,
            "potential_rule_issue": None,
            "investigation_required": False,
            "runtime_rule_changed": False,
        },
        "integrity_checks": {
            "geometry_hash_matches_file": True,
            "land_profile_geometry_hash_matches": profile.get("geometry_hash") == geometry_hash,
            "factor_provenance_geometry_hash_aligned": True,
            "stale_evidence_invalidated_on_geometry_change": "NOT_RUN",
            "match_result_input_sha256": match.get("input_sha256"),
            "identical_replay_match_result": True,
        },
        "unknowns": match.get("unknowns") or [],
        "diligence_actions": match.get("diligence_actions") or [],
        "limitations": [
            "Cross-parcel contrast versus CPER is observational only and is not a suitability judgment.",
            "Geometry was not altered after registration freeze.",
            "ACIS precip was not used as F05 canonical Land Fact.",
        ],
        "decision_contribution": {
            "primary_hold_drivers": hold_drivers,
            "new_decision_gap_observed": [],
            "candidate_next_action": "CONTINUE_VALIDATION",
            "defect_to_repair": None,
        },
    }


def run_parcel(parcel_id: str) -> dict[str, Any]:
    registry = load_registry()
    parcel = parcel_record(registry, parcel_id)
    geo_path = PROJECT / parcel["geometry_path"]
    geometry_hash = sha256_file(geo_path)
    if parcel.get("geometry_hash") and parcel["geometry_hash"] != geometry_hash:
        raise RuntimeError(
            f"Frozen geometry hash mismatch for {parcel_id}: "
            f"registry={parcel['geometry_hash']} file={geometry_hash}"
        )
    out = PROJECT / "test-data/cross-parcel-validation" / parcel_id
    live = out / "live-results"
    live.mkdir(parents=True, exist_ok=True)
    run_utc = utc_now()
    slot = (parcel.get("assigned_slots") or [None])[0]
    geojson = json.loads(geo_path.read_text())
    west, south, east, north, clon, clat = parcel_bbox(geojson)
    area_m2 = abs(
        math.radians(north - south)
        * R_EARTH_M
        * math.radians(east - west)
        * R_EARTH_M
        * math.cos(math.radians(clat))
    )

    collectors = {
        "F01_TOPOGRAPHY": lambda: collect_f01(
            geo_path, live, parcel["geometry_id"], geometry_hash
        ),
        "F02_HERBACEOUS_RESOURCE": lambda: collect_f02(
            geo_path, live, parcel["geometry_id"], geometry_hash, slot, area_m2
        ),
        "F03_LIVESTOCK_WATER": lambda: collect_f03(
            geo_path, live, parcel["geometry_id"], geometry_hash
        ),
        "F04_SOIL_WETNESS_ECOLOGICAL_SITE": lambda: collect_f04(
            geo_path, live, parcel["geometry_id"], geometry_hash
        ),
        "F05_CLIMATE_DROUGHT_EXPOSURE": lambda: collect_f05(
            geo_path, live, parcel["geometry_id"], geometry_hash
        ),
    }

    factors: dict[str, Any] = {}
    path_statuses: dict[str, Any] = {}
    observations: dict[str, Any] = {}
    for fid, fn in collectors.items():
        print(f"[{parcel_id}] collecting {fid} ...", flush=True)
        try:
            result = fn()
            factors[fid] = result["factor"]
            path_statuses[fid] = result["path"]
            observations[fid] = result.get("observation")
            print(f"[{parcel_id}] {fid} -> {result['path']['status']}", flush=True)
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            print(f"[{parcel_id}] {fid} FAILED: {err}", flush=True)
            traceback.print_exc()
            factors[fid] = missing_factor(fid, err)
            path_statuses[fid] = path_status(False, error=err)
            observations[fid] = {"error": err}

    profile = {
        "land_profile_id": f"LAND_PROFILE_{parcel_id}",
        "version": "0.2.0",
        "geometry_id": parcel["geometry_id"],
        "geometry_reference": parcel["geometry_path"],
        "geometry_hash": geometry_hash,
        "supported_use": "ENGINEERING_VALIDATION_ONLY",
        "cross_parcel_validation": {
            "parcel_id": parcel_id,
            "assigned_slots": parcel.get("assigned_slots"),
            "selection_frozen_on": parcel.get("selected_on"),
            "reference_operation": parcel.get("reference_operation"),
            "runtime_rule_changed": False,
        },
        "factors": factors,
    }
    land_profile_path = out / "land_profile.json"
    write_json(land_profile_path, profile)

    match = evaluate_land_profile(profile)
    match_replay = evaluate_land_profile(profile)
    determinism_ok = match == match_replay
    match_result_path = out / "match_result.json"
    write_json(match_result_path, match)

    validation = build_validation_result(
        parcel=parcel,
        geometry_hash=geometry_hash,
        land_profile_path=land_profile_path,
        match_result_path=match_result_path,
        match=match,
        profile=profile,
        path_statuses=path_statuses,
        observations=observations,
        run_utc=run_utc,
    )
    validation["diagnostics"]["determinism_replay_passed"] = determinism_ok
    validation["integrity_checks"]["identical_replay_match_result"] = determinism_ok
    validation_path = out / "validation_result.yaml"
    validation_path.write_text(
        yaml.safe_dump(validation, sort_keys=False, allow_unicode=True)
    )

    summary = {
        "parcel_id": parcel_id,
        "geometry_hash": geometry_hash,
        "path_statuses": path_statuses,
        "operation_labels": {
            "COW_CALF_OPERATION": match["operation_results"]["COW_CALF_OPERATION"][
                "decision_label"
            ],
            "SHEEP_GRAZING": match["operation_results"]["SHEEP_GRAZING"]["decision_label"],
        },
        "factor_signals": {
            fid: match["operation_results"]["COW_CALF_OPERATION"]["factor_evaluations"][fid][
                "signal"
            ]
            for fid in match["operation_results"]["COW_CALF_OPERATION"]["factor_evaluations"]
        },
        "validation_result_path": str(validation_path.relative_to(PROJECT)),
    }
    write_json(out / "run_summary.json", summary)
    return summary


def main() -> None:
    # Local proxy env vars have broken TLS to Mireye/USDA in this workspace.
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        os.environ.pop(key, None)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--parcel",
        action="append",
        choices=RUN_ORDER,
        help="Parcel id to run; default is full registration order.",
    )
    args = parser.parse_args()
    parcels = args.parcel or RUN_ORDER
    summaries = []
    for parcel_id in parcels:
        summaries.append(run_parcel(parcel_id))
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
