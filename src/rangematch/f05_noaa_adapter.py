"""NOAA/NCEI Direct Climate Normals adapter for canonical F05 precipitation."""

from __future__ import annotations

import hashlib
import math
import os
import statistics
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from netCDF4 import Dataset
from shapely.geometry import shape

from rangematch.f05_derivation import derive_f05_parcel_facts

ADAPTER_ID = "NOAA_NCEI_DIRECT_NORMALS_ADAPTER@0.1.0"
NORMALS_PERIOD = "1991-2020"
R_EARTH_M = 6371008.8
DEFAULT_CACHE = Path(__file__).resolve().parents[2] / "test-data/live-results/cper/cache/prcp-1991_2020-monthly-normals-v1.0.nc"
SOURCE_URL = "https://www.ncei.noaa.gov/data/oceans/archive/arc0196/0245564/1.1/data/0-data/prcp-1991_2020-monthly-normals-v1.0.nc"


class F05NOAAAdapterError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@lru_cache(maxsize=4)
def _sha256_file(path_text: str, size: int, mtime_ns: int) -> str:
    digest = hashlib.sha256()
    with Path(path_text).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_normals_path(path: str | Path | None = None) -> Path:
    candidate = Path(path or os.environ.get("NOAA_NCEI_NORMALS_NETCDF_PATH") or DEFAULT_CACHE).resolve()
    if not candidate.is_file():
        raise F05NOAAAdapterError("NOAA_NCEI_NORMALS_NETCDF_NOT_AVAILABLE")
    return candidate


def collect_f05_from_noaa_normals(
    *,
    geometry: Mapping[str, Any],
    geometry_id: str,
    geometry_hash: str,
    mireye_context: Mapping[str, Any] | None = None,
    netcdf_path: str | Path | None = None,
) -> dict[str, Any]:
    path = resolve_normals_path(netcdf_path)
    parcel = shape(geometry["features"][0]["geometry"])
    west, south, east, north = map(float, parcel.bounds)
    centroid = parcel.centroid
    clon, clat = float(centroid.x), float(centroid.y)
    with Dataset(path) as ds:
        lon = np.asarray(ds.variables["lon"][:], dtype=float)
        lat = np.asarray(ds.variables["lat"][:], dtype=float)
        variable = ds.variables["annprcp_norm"]
        ann = np.asarray(variable[:], dtype=float)
        fill = getattr(variable, "_FillValue", None)
        units = str(variable.units)
        dlat = float(np.median(np.diff(np.sort(np.unique(lat)))))
        dlon = float(np.median(np.diff(np.sort(np.unique(lon)))))
        lon_idx = np.where((lon + dlon / 2 >= west) & (lon - dlon / 2 <= east))[0]
        lat_idx = np.where((lat + dlat / 2 >= south) & (lat - dlat / 2 <= north))[0]
        values: list[float] = []
        cells: list[dict[str, float]] = []
        for i in lat_idx:
            for j in lon_idx:
                value = float(ann[i, j])
                if (fill is not None and np.isclose(value, float(fill))) or not np.isfinite(value):
                    continue
                values.append(value)
                cells.append({"lat": float(lat[i]), "lon": float(lon[j]), "annprcp_norm_mm": value})
        method = "bbox_intersecting_grid_cells_mean"
        if not values:
            i, j = int(np.abs(lat - clat).argmin()), int(np.abs(lon - clon).argmin())
            value = float(ann[i, j])
            if not np.isfinite(value):
                raise F05NOAAAdapterError("NOAA_ANNPRCP_NO_VALID_CELL")
            values, cells = [value], [{"lat": float(lat[i]), "lon": float(lon[j]), "annprcp_norm_mm": value}]
            method = "nearest_cell_to_centroid_fallback"

    stat = path.stat()
    file_hash = _sha256_file(str(path), stat.st_size, stat.st_mtime_ns)
    parcel_area_approx = abs(
        math.radians(north - south) * R_EARTH_M
        * math.radians(east - west) * R_EARTH_M
        * math.cos(math.radians(clat))
    )
    coverage_status = (
        "COMPLETE_SINGLE_CELL_COVERS_SMALL_PARCEL"
        if len(cells) == 1
        else "COMPLETE_CELLS_INTERSECT_PARCEL_BBOX"
    )
    mean_mm = float(statistics.mean(values))
    precip = {
        "variable_id": "VAR_F05_MEAN_ANNUAL_PRECIPITATION",
        "geometry_id": geometry_id,
        "geometry_sha256": geometry_hash,
        "value_mm": round(mean_mm, 2),
        "value_inches": round(mean_mm / 25.4, 3),
        "unit": "millimeter",
        "aggregation": {"method": method, "cell_count": len(cells), "cell_values_mm": [round(v, 2) for v in values], "cells": cells},
        "normals_period": NORMALS_PERIOD,
        "spatial_resolution": {"nominal": "1/24 degree (~4 km)", "delta_lat_deg": dlat, "delta_lon_deg": dlon},
        "parcel_coverage": {
            "parcel_bbox": [west, south, east, north],
            "parcel_area_m2_approx": round(parcel_area_approx, 2),
            "intersecting_cell_count": len(cells),
            "coverage_status": coverage_status,
            "spatial_support": "PARCEL_BBOX_INTERSECTING_GRID_CELLS",
        },
        "source": {
            "organization": "NOAA National Centers for Environmental Information (NCEI)",
            "product": "1991-2020 Gridded Monthly/Annual Precipitation Normals",
            "variable": "annprcp_norm",
            "file": path.name,
            "source_url": SOURCE_URL,
            "access_path": "NOAA_NCEI_DIRECT_CLIMATE_NORMALS_NETCDF",
            "units_in_file": units,
        },
        "fetched_at": _utc_now(),
        "file_sha256": file_hash,
        "file_bytes": stat.st_size,
        "role": "CANONICAL_LAND_FACT",
        "adapter_id": ADAPTER_ID,
    }
    factor = derive_f05_parcel_facts(
        precip=precip,
        mireye=mireye_context,
        geometry_hash=geometry_hash,
    )
    factor["algorithm_version"] = ADAPTER_ID
    factor["canonical_source_id"] = "NOAA_NCEI_DIRECT_CLIMATE_NORMALS_NETCDF"
    factor["ranking_effect"] = "NONE"
    return factor
