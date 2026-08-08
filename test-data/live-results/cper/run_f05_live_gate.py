"""Read-only F05 Climate/Drought live gate for the CPER engineering test geometry.

Primary precip path: NOAA/NCEI 1991-2020 gridded precipitation normals NetCDF.
Mireye: centroid point QA for drought/temperature/heat-day fields only.
No suitability rules, thresholds, or ranking effects are produced.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import ssl
import statistics
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
from netCDF4 import Dataset

PROJECT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
CACHE_DIR = OUT / "cache"
CACHE = CACHE_DIR / "prcp-1991_2020-monthly-normals-v1.0.nc"
GEO = PROJECT / "test-data/engineering_test_geometry_cper_001.geojson"
NOAA_URL = (
    "https://www.ncei.noaa.gov/data/oceans/archive/arc0196/0245564/1.1/data/0-data/"
    "prcp-1991_2020-monthly-normals-v1.0.nc"
)
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")
R_EARTH_M = 6371008.8


def load_env(path: Path) -> None:
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def ensure_noaa_normals() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if CACHE.exists() and CACHE.stat().st_size > 100_000_000:
        return CACHE
    print(f"Downloading NOAA NCEI normals to {CACHE} ...")
    req = Request(NOAA_URL, method="GET")
    with urlopen(req, timeout=600) as response, CACHE.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    return CACHE


def parcel_bbox(geojson: dict) -> tuple[float, float, float, float, float, float]:
    coords = geojson["features"][0]["geometry"]["coordinates"][0]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    west, east = min(lons), max(lons)
    south, north = min(lats), max(lats)
    return west, south, east, north, (west + east) / 2, (south + north) / 2


def sample_precipitation(cache: Path, geo_bytes: bytes, geojson: dict) -> dict:
    west, south, east, north, centroid_lng, centroid_lat = parcel_bbox(geojson)
    parcel_area_m2 = abs(
        math.radians(north - south)
        * R_EARTH_M
        * math.radians(east - west)
        * R_EARTH_M
        * math.cos(math.radians(centroid_lat))
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
            cells.append(
                {
                    "lat": float(lat[i]),
                    "lon": float(lon[j]),
                    "annprcp_norm_mm": value,
                }
            )
    method = "bbox_intersecting_cell_centers_mean"
    if not vals:
        i = int(np.abs(lat - centroid_lat).argmin())
        j = int(np.abs(lon - centroid_lng).argmin())
        value = float(ann[i, j])
        vals = [value]
        cells = [
            {
                "lat": float(lat[i]),
                "lon": float(lon[j]),
                "annprcp_norm_mm": value,
            }
        ]
        method = "nearest_cell_to_centroid_fallback"
    mean_mm = float(statistics.mean(vals))
    cell_area_m2 = abs(
        math.radians(dlat)
        * R_EARTH_M
        * math.radians(dlon)
        * R_EARTH_M
        * math.cos(math.radians(centroid_lat))
    )
    coverage_status = (
        "COMPLETE_SINGLE_CELL_COVERS_SMALL_PARCEL"
        if len(cells) == 1
        else "COMPLETE_CELLS_INTERSECT_PARCEL_BBOX"
        if vals
        else "FAILED"
    )
    result = {
        "variable_id": "VAR_F05_MEAN_ANNUAL_PRECIPITATION",
        "geometry_id": "ENGINEERING_TEST_GEOMETRY_CPER_001",
        "geometry_sha256": hashlib.sha256(geo_bytes).hexdigest(),
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
                "cells intersecting the CPER engineering rectangle."
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
            "title": getattr(ds, "title", None),
            "institution": getattr(ds, "institution", None),
            "naming_authority": getattr(ds, "naming_authority", None),
            "file": CACHE.name,
            "source_url": NOAA_URL,
            "product_page": "https://www.ncei.noaa.gov/products/land-based-station/us-climate-normals",
            "nclimgrid_reference": "https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc:C00332",
            "date_created_in_file": getattr(ds, "date_created", None),
            "units_in_file": units,
            "access_path": "NOAA_NCEI_DIRECT_HTTPS_NETCDF",
            "alternate_not_used": "PRISM retained as alternate/cross-check only.",
        },
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "local_cache_path": str(CACHE.relative_to(PROJECT)),
        "file_sha256": hashlib.sha256(CACHE.read_bytes()).hexdigest(),
        "file_bytes": CACHE.stat().st_size,
    }
    ds.close()
    return result


def fetch_mireye(centroid_lat: float, centroid_lng: float) -> dict:
    load_env(PROJECT / ".env")
    fields = [
        "drought_category",
        "mean_annual_dry_bulb_temperature_degc",
        "days_above_32c_annual_count",
    ]
    payload = {"lat": centroid_lat, "lng": centroid_lng, "fields": fields}
    request = Request(
        os.environ["MIREYE_API_BASE_URL"].rstrip("/") + "/v1/fetch",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + os.environ["MIREYE_API_KEY"],
        },
        method="POST",
    )
    context = ssl.create_default_context()
    try:
        import certifi

        context = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    with urlopen(request, context=context, timeout=90) as response:
        return json.loads(response.read())


def main() -> None:
    geo_bytes = GEO.read_bytes()
    geojson = json.loads(geo_bytes)
    west, south, east, north, centroid_lng, centroid_lat = parcel_bbox(geojson)
    cache = ensure_noaa_normals()
    precip = sample_precipitation(cache, geo_bytes, geojson)
    precip_path = OUT / f"cper_noaa_ncei_annprcp_normals_1991_2020_{DATE}.json"
    precip_path.write_text(json.dumps(precip, indent=2) + "\n")

    mireye = fetch_mireye(centroid_lat, centroid_lng)
    mireye_path = OUT / f"cper_mireye_f05_centroid_{DATE}.json"
    mireye_path.write_text(json.dumps(mireye, indent=2) + "\n")
    fields = mireye.get("fields", mireye)
    qa = {}
    mireye_ok = True
    for field_id in [
        "drought_category",
        "mean_annual_dry_bulb_temperature_degc",
        "days_above_32c_annual_count",
    ]:
        item = fields.get(field_id, {})
        status = item.get("status")
        qa[field_id] = {
            "value": item.get("value"),
            "unit": item.get("unit"),
            "status": status,
            "source": item.get("source"),
            "dataset_vintage": item.get("dataset_vintage"),
            "fetched_at": item.get("fetched_at"),
            "spatial_semantics": "POINT_CENTROID",
            "notes": item.get("notes"),
        }
        if status != "ok":
            mireye_ok = False

    precip_ok = precip["parcel_coverage"]["coverage_status"].startswith("COMPLETE")
    if precip_ok and mireye_ok:
        data_path_status = "LIVE_VERIFIED"
    elif precip_ok or mireye_ok:
        data_path_status = "PARTIAL"
    else:
        data_path_status = "FAILED"

    summary = {
        "gate_id": "F05_CLIMATE_DROUGHT_LIVE_DATA_GATE_CPER",
        "geometry_id": "ENGINEERING_TEST_GEOMETRY_CPER_001",
        "geometry_sha256": precip["geometry_sha256"],
        "date": DATE,
        "data_path_status": data_path_status,
        "signal_status": "NOT_YET_APPROVED",
        "ranking_effect": "NONE",
        "noaa_precipitation": {
            "value_mm": precip["value_mm"],
            "value_inches": precip["value_inches"],
            "normals_period": precip["normals_period"],
            "spatial_resolution": precip["spatial_resolution"]["nominal"],
            "parcel_coverage": precip["parcel_coverage"]["coverage_status"],
            "source_file": precip["source"]["file"],
            "access_path": precip["source"]["access_path"],
            "fixture": str(precip_path.relative_to(PROJECT)),
        },
        "mireye_point_qa": {
            "centroid": {"lat": centroid_lat, "lng": centroid_lng},
            "fields": qa,
            "fixture": str(mireye_path.relative_to(PROJECT)),
            "point_vs_parcel": "POINT_QA_ONLY_NOT_PARCEL_AGGREGATE",
        },
        "parcel_bbox": [west, south, east, north],
    }
    summary_path = OUT / f"cper_f05_live_gate_summary_{DATE}.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(
        {
            "data_path_status": data_path_status,
            "signal_status": "NOT_YET_APPROVED",
            "ranking_effect": "NONE",
            "precip_mm": precip["value_mm"],
            "summary": str(summary_path),
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
