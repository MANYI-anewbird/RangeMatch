"""Live USGS 3DEP adapter for deterministic parcel-wide F01 terrain context.

Implements the frozen F01 v0.1 derivation: locked 1/3 arc-second source,
approximately 10 m UTM export, cell-center parcel mask, Horn slope, and
circular aspect summaries. It creates context only and no suitability rule.
"""

from __future__ import annotations

import hashlib
import json
import math
import ssl
import time
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib.parse import urlencode
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener
from urllib.error import HTTPError, URLError

import numpy as np
from pyproj import Transformer
from shapely import contains_xy
from shapely.geometry import shape
from shapely.ops import transform

DEM_SERVICE = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer"
ADAPTER_ID = "USGS_3DEP_F01_ADAPTER@0.1.0"
DERIVATION_SPEC = "F01_TOPOGRAPHY_DERIVATION_SPEC.yaml@0.1.0"

JsonGet = Callable[[str, float], dict[str, Any]]
BytesGet = Callable[[str, float], bytes]


class F01AdapterError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _http_json(url: str, timeout: float) -> dict[str, Any]:
    payload = _read_with_retry(url, timeout=timeout, accept="application/json")
    value = json.loads(payload.decode("utf-8"))
    if isinstance(value, dict) and value.get("error"):
        error = value["error"] or {}
        raise F01AdapterError(
            f"USGS_3DEP_SERVICE_ERROR:{error.get('code')}:{error.get('message')}"
        )
    if not isinstance(value, dict):
        raise F01AdapterError("USGS_3DEP_JSON_RESPONSE_NOT_OBJECT")
    return value


def _http_bytes(url: str, timeout: float) -> bytes:
    return _read_with_retry(url, timeout=timeout, accept="image/tiff,*/*")


def _read_with_retry(
    url: str,
    *,
    timeout: float,
    accept: str,
    attempts: int = 3,
) -> bytes:
    """Retry only transient USGS transport/service failures; preserve the cause."""
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with _urlopen_no_proxy(url, timeout=timeout, accept=accept) as response:
                return response.read()
        except HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 500, 502, 503, 504} or attempt + 1 >= attempts:
                try:
                    detail = exc.read().decode("utf-8", errors="replace")[:500]
                except Exception:  # pragma: no cover - error bodies are optional
                    detail = ""
                raise F01AdapterError(
                    f"USGS_3DEP_HTTP_{exc.code}:{detail or 'no_error_body'}"
                ) from exc
        except (URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 >= attempts:
                raise F01AdapterError(
                    f"USGS_3DEP_TRANSPORT_FAILED:{type(exc).__name__}"
                ) from exc
        time.sleep(0.4 * (attempt + 1))
    raise F01AdapterError(f"USGS_3DEP_RETRY_EXHAUSTED:{type(last_error).__name__}")


def _urlopen_no_proxy(url: str, *, timeout: float, accept: str = "application/json"):
    if not str(url).startswith("https://"):
        raise F01AdapterError("USGS_3DEP_NON_HTTPS_URL_REJECTED")
    try:
        import certifi

        context = ssl.create_default_context(cafile=certifi.where())
    except Exception:  # pragma: no cover - certifi is a runtime dependency
        context = ssl.create_default_context()
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=context))
    request = Request(url, headers={"Accept": accept, "User-Agent": "RangeMatch/0.1"}, method="GET")
    return opener.open(request, timeout=timeout)  # noqa: S310 - HTTPS enforced above


def _utm_epsg(lon: float, lat: float) -> str:
    zone = int((lon + 180) // 6) + 1
    return f"EPSG:{32600 + zone if lat >= 0 else 32700 + zone}"


def _stats(values: np.ndarray) -> dict[str, float]:
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


def derive_f01_from_dem_bytes(
    *,
    geometry: Mapping[str, Any],
    geometry_id: str,
    geometry_hash: str,
    dem_bytes: bytes,
    locked_source: Mapping[str, Any],
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    import rasterio
    from rasterio.io import MemoryFile

    feature = geometry["features"][0]
    parcel_wgs84 = shape(feature["geometry"])
    with MemoryFile(dem_bytes) as memfile, memfile.open() as dataset:
        elevation = dataset.read(1).astype("float64")
        to_working = Transformer.from_crs("EPSG:4326", dataset.crs, always_xy=True).transform
        parcel = transform(to_working, parcel_wgs84)
        xres = float(dataset.transform.a)
        yres = float(-dataset.transform.e)
        rows, cols = np.indices(elevation.shape)
        xs, ys = rasterio.transform.xy(dataset.transform, rows, cols, offset="center")
        xs = np.asarray(xs).reshape(elevation.shape)
        ys = np.asarray(ys).reshape(elevation.shape)
        parcel_mask = contains_xy(parcel, xs, ys)
        z1, z2, z3 = elevation[:-2, :-2], elevation[:-2, 1:-1], elevation[:-2, 2:]
        z4, z6 = elevation[1:-1, :-2], elevation[1:-1, 2:]
        z7, z8, z9 = elevation[2:, :-2], elevation[2:, 1:-1], elevation[2:, 2:]
        dzdx = ((z3 + 2 * z6 + z9) - (z1 + 2 * z4 + z7)) / (8 * xres)
        dzd_south = ((z7 + 2 * z8 + z9) - (z1 + 2 * z2 + z3)) / (8 * yres)
        dzd_north = -dzd_south
        gradient = np.hypot(dzdx, dzd_north)
        slope_inner = np.degrees(np.arctan(gradient))
        aspect_inner = np.degrees(np.arctan2(-dzdx, -dzd_north)) % 360
        slope = np.full(elevation.shape, np.nan)
        aspect = np.full(elevation.shape, np.nan)
        slope[1:-1, 1:-1] = slope_inner
        aspect[1:-1, 1:-1] = np.where(gradient == 0, np.nan, aspect_inner)
        elevation_values = elevation[parcel_mask & np.isfinite(elevation)]
        slope_values = slope[parcel_mask & np.isfinite(slope)]
        aspect_values = aspect[parcel_mask & np.isfinite(aspect)]
        parcel_cells = int(np.count_nonzero(parcel_mask))
        working_crs = str(dataset.crs)
        cell_area_m2 = xres * yres

    if parcel_cells == 0 or elevation_values.size == 0 or slope_values.size == 0:
        raise F01AdapterError("F01_PARCEL_MASK_HAS_NO_VALID_DEM_CELLS")
    elev = _stats(elevation_values)
    slope_stats = _stats(slope_values)
    coverage_fraction = min(elevation_values.size, slope_values.size) / parcel_cells
    summary = {
        "elevation_median_m": elev["median"],
        "slope_median_degrees": slope_stats["median"],
        "slope_p90_degrees": slope_stats["p90"],
        "mean_eastness": float(np.nanmean(np.sin(np.deg2rad(aspect_values)))) if aspect_values.size else None,
        "mean_northness": float(np.nanmean(np.cos(np.deg2rad(aspect_values)))) if aspect_values.size else None,
    }
    return {
        "factor_id": "F01_TOPOGRAPHY",
        "input_quality_state": "PARCEL_COMPLETE" if coverage_fraction == 1.0 else "PARCEL_INCOMPLETE",
        "derivation_spec": DERIVATION_SPEC,
        "algorithm_version": ADAPTER_ID,
        "adapter_id": ADAPTER_ID,
        "canonical_source_id": "USGS_3DEP_1_3_ARC_SECOND_SEAMLESS_DEM",
        "ranking_effect": "NONE",
        "summary": summary,
        "elevation_m": elev,
        "slope_degrees": slope_stats,
        "coverage": {
            "status": "COMPLETE" if coverage_fraction == 1.0 else "PARTIAL",
            "parcel_cell_count": parcel_cells,
            "valid_elevation_cell_count": int(elevation_values.size),
            "valid_slope_cell_count": int(slope_values.size),
            "cell_area_m2": cell_area_m2,
            "coverage_fraction": float(coverage_fraction),
        },
        "source": {
            "product": "USGS_3DEP_1_3_ARC_SECOND_SEAMLESS_DEM",
            "service": f"{DEM_SERVICE}/exportImage",
            "surface": "bare_earth",
            "mosaic_method": "esriMosaicLockRaster",
            "source_object_id": locked_source.get("OBJECTID"),
            "source_tile_name": locked_source.get("Name"),
            "source_title": locked_source.get("title"),
            "source_url": locked_source.get("URL"),
            "source_publication_date": str(locked_source.get("pubdate")),
            "vertical_datum": locked_source.get("VerticalDatum"),
            "source_raster_sha256": hashlib.sha256(dem_bytes).hexdigest(),
            "source_crs": working_crs,
            "working_crs": working_crs,
        },
        "geometry_id": geometry_id,
        "geometry_hash": geometry_hash,
        "retrieved_at": retrieved_at or _utc_now(),
        "provenance": {
            "canonical_source_id": "USGS_3DEP_1_3_ARC_SECOND_SEAMLESS_DEM",
            "source_product_and_version": "USGS_3DEP_1_3_ARC_SECOND_SEAMLESS_DEM",
            "geometry_hash": geometry_hash,
            "response_or_artifact_hash": hashlib.sha256(dem_bytes).hexdigest(),
            "algorithm_version": ADAPTER_ID,
            "derivation_spec_version": DERIVATION_SPEC,
            "working_crs": working_crs,
            "source_crs": "EPSG:4326",
        },
        "limitations": [
            "Terrain statistics are parcel context, not carrying capacity or profitability.",
            "No universal slope suitability threshold is approved.",
            "USGS 3DEP does not establish rock cover or accessible grazing area.",
        ],
        "prohibited_interpretations_applied": True,
    }


def collect_f01_from_usgs_3dep(
    *,
    geometry: Mapping[str, Any],
    geometry_id: str,
    geometry_hash: str,
    json_get: JsonGet | None = None,
    bytes_get: BytesGet | None = None,
) -> dict[str, Any]:
    json_get = json_get or _http_json
    bytes_get = bytes_get or _http_bytes
    parcel = shape(geometry["features"][0]["geometry"])
    west, south, east, north = parcel.bounds
    centroid = parcel.centroid
    epsg = _utm_epsg(float(centroid.x), float(centroid.y))
    wkid = int(epsg.split(":")[1])
    envelope = {
        "xmin": west - 0.002,
        "ymin": south - 0.002,
        "xmax": east + 0.002,
        "ymax": north + 0.002,
        "spatialReference": {"wkid": 4326},
    }
    query = f"{DEM_SERVICE}/query?" + urlencode({
        "geometry": json.dumps(envelope), "geometryType": "esriGeometryEnvelope",
        "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "outFields": "*",
        "returnGeometry": "false", "f": "json",
    })
    catalog = json_get(query, 180)
    candidates = []
    for feature in catalog.get("features") or []:
        attrs = feature.get("attributes") or {}
        title, name, lowps = str(attrs.get("title") or ""), str(attrs.get("Name") or ""), attrs.get("LowPS")
        if "1/3 Arc Second" in title or (isinstance(lowps, (int, float)) and 8 <= float(lowps) <= 12 and name):
            candidates.append(attrs)
    if not candidates:
        raise F01AdapterError("NO_1_3_ARC_SECOND_3DEP_SOURCE_FOR_PARCEL")
    candidates.sort(key=lambda item: (item.get("Best") is None, -(item.get("Best") or 0)))
    locked = candidates[0]
    to_utm = Transformer.from_crs("EPSG:4326", epsg, always_xy=True).transform
    parcel_utm = transform(to_utm, parcel)
    minx, miny, maxx, maxy = parcel_utm.bounds
    pad = 60.0
    export = f"{DEM_SERVICE}/exportImage?" + urlencode({
        "bbox": f"{minx-pad},{miny-pad},{maxx+pad},{maxy+pad}", "bboxSR": wkid,
        "imageSR": wkid,
        "size": f"{max(80, math.ceil((maxx-minx+2*pad)/10))},{max(80, math.ceil((maxy-miny+2*pad)/10))}",
        "format": "tiff", "pixelType": "F32", "noDataInterpretation": "esriNoDataMatchAny",
        "interpolation": "RSP_BilinearInterpolation",
        "mosaicRule": json.dumps({"mosaicMethod": "esriMosaicLockRaster", "lockRasterIds": [locked["OBJECTID"]]}),
        "f": "json",
    })
    export_meta = json_get(export, 180)
    href = export_meta.get("href")
    if not href:
        raise F01AdapterError("USGS_3DEP_EXPORT_MISSING_HREF")
    dem = bytes_get(str(href), 300)
    return derive_f01_from_dem_bytes(
        geometry=geometry, geometry_id=geometry_id, geometry_hash=geometry_hash,
        dem_bytes=dem, locked_source=locked,
    )
