import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from shapely import contains_xy
from shapely.geometry import shape
from shapely.ops import transform


GEOMETRY_PATH = Path("/Users/hongmanyi/RangeMatch/test-data/engineering_test_geometry_cper_001.geojson")
RASTER_PATH = Path("/tmp/cper_3dep_locked_13_buffered_utm13.tif")
OUTPUT_PATH = Path("/tmp/cper_f01_derivation_result_2026-08-07.json")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stats(values: np.ndarray) -> dict:
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


geojson_bytes = GEOMETRY_PATH.read_bytes()
feature_collection = json.loads(geojson_bytes)
parcel_wgs84 = shape(feature_collection["features"][0]["geometry"])

with rasterio.open(RASTER_PATH) as dataset:
    elevation = dataset.read(1).astype("float64")
    transform_to_working = Transformer.from_crs("EPSG:4326", dataset.crs, always_xy=True).transform
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

    result = {
        "result_id": "CPER_F01_DERIVATION_2026_08_07",
        "derivation_spec": "F01_TOPOGRAPHY_DERIVATION_SPEC.yaml@0.1.0",
        "quality_state": "PARCEL_COMPLETE",
        "quality_reason": "The export was locked to the queried 1/3 arc-second catalog item and includes source identifier, acquisition date, publication date, datum, service publication date, request contract, and raster hash.",
        "processing_timestamp": datetime.now(timezone.utc).isoformat(),
        "source": {
            "product": "USGS_3DEP_1_3_ARC_SECOND_SEAMLESS_DEM",
            "service": "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage",
            "service_current_version": 11.3,
            "service_data_published_through": "2026-07-20",
            "service_copyright_date": "2026-07-23",
            "surface": "bare_earth",
            "mosaic_method": "esriMosaicLockRaster",
            "source_object_id": 4878,
            "source_tile_ids": ["USGS_13_n41w105"],
            "source_tile_name": "n41w105",
            "source_title": "USGS 1/3 Arc Second n41w105 20260708",
            "source_url": "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/n41w105/USGS_13_n41w105.tif",
            "source_acquisition_date": "2021-09-22",
            "source_publication_date": "2026-07-08",
            "source_start_date": "1948-01-01",
            "source_end_date": "2021-09-22",
            "vertical_datum": "North American Vertical Datum of 1988 (NAVD 88)",
            "source_raster_sha256": sha256(RASTER_PATH),
            "source_width": dataset.width,
            "source_height": dataset.height,
            "source_crs": str(dataset.crs),
            "source_bounds": list(dataset.bounds),
            "source_dtype": dataset.dtypes[0],
            "source_nodata": dataset.nodata,
        },
        "geometry": {
            "geometry_id": "ENGINEERING_TEST_GEOMETRY_CPER_001",
            "geometry_sha256": hashlib.sha256(geojson_bytes).hexdigest(),
            "input_crs": "EPSG:4326",
            "working_crs": str(dataset.crs),
            "parcel_cell_count": parcel_cell_count,
            "cell_area_m2": cell_area,
            "represented_cell_center_area_m2": parcel_cell_count * cell_area,
        },
        "algorithm": {
            "target_cell_size_x_m": xres,
            "target_cell_size_y_m": yres,
            "slope": "Horn 3x3; degrees; edges excluded",
            "aspect": "Horn 3x3 downhill azimuth clockwise from north; flat cells undefined; edges excluded",
            "parcel_inclusion": "cell center inside parcel",
            "percentile_method": "linear interpolation (NumPy method=linear; Hyndman-Fan type 7)",
            "numpy_version": np.__version__,
            "rasterio_version": rasterio.__version__,
        },
        "elevation_m": {
            "valid_cell_count": int(elevation_values.size),
            "coverage_fraction": float(elevation_values.size / parcel_cell_count),
            **stats(elevation_values),
        },
        "slope_degrees": {
            "valid_cell_count": int(slope_values.size),
            "coverage_fraction": float(slope_values.size / parcel_cell_count),
            **stats(slope_values),
        },
        "aspect": {
            "valid_cell_count": int(aspect_values.size),
            "undefined_flat_cell_count": int(np.count_nonzero(parcel_mask & ~np.isfinite(aspect))),
            "coverage_fraction": float(aspect_values.size / parcel_cell_count),
            "mean_eastness": float(np.mean(np.sin(np.radians(aspect_values)))),
            "mean_northness": float(np.mean(np.cos(np.radians(aspect_values)))),
        },
        "prohibited_interpretation": [
            "species suitability score",
            "slope rejection threshold",
            "usable grazing area",
            "hard exclusion",
        ],
    }

OUTPUT_PATH.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
