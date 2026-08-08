"""TIGER/Line 2025 All Roads adapter for F07.

Canonical source only. OSM is not consulted. Edges fallback is documented in
the audit package but not implemented in this adapter.
"""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import shapefile
from shapely.geometry import mapping, shape
from shapely.ops import transform as shapely_transform
from pyproj import CRS, Transformer

from rangematch.f06_derivation import (
    SOURCE_CRS_DEFAULT,
    _extract_geometry_and_meta,
    _project_geometry,
    select_working_crs,
    sha256_file,
)
from rangematch.f07_derivation import (
    CANONICAL_SOURCE_ID,
    SEARCH_WINDOW_DEFAULT_M,
    derive_f07_from_inputs,
)

ADAPTER_ID = "F07_TIGER_LINE_2025_ALL_ROADS_ADAPTER@0.1.0"
TIGER_YEAR = "2025"
COUNTY_ZIP_URL = (
    "https://www2.census.gov/geo/tiger/TIGER2025/COUNTY/tl_2025_us_county.zip"
)
ROADS_ZIP_URL_PATTERN = (
    "https://www2.census.gov/geo/tiger/TIGER2025/ROADS/tl_2025_{county_fips}_roads.zip"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def download_url_to_path(url: str, destination: Path, *, timeout_s: int = 180) -> dict[str, Any]:
    """Download URL with curl (system certs) and record provenance."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        payload = destination.read_bytes()
        return {
            "url": url,
            "path": str(destination),
            "sha256": _sha256_bytes(payload),
            "bytes": len(payload),
            "cache_hit": True,
            "fetched_at": None,
        }
    fetched_at = _now_iso()
    completed = subprocess.run(
        [
            "curl",
            "-fsSL",
            "--connect-timeout",
            "30",
            "--max-time",
            str(timeout_s),
            "-o",
            str(destination),
            url,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 or not destination.exists():
        raise RuntimeError(
            f"Failed to download {url}: rc={completed.returncode} stderr={completed.stderr}"
        )
    payload = destination.read_bytes()
    return {
        "url": url,
        "path": str(destination),
        "sha256": _sha256_bytes(payload),
        "bytes": len(payload),
        "cache_hit": False,
        "fetched_at": fetched_at,
    }


def _shapefile_reader_from_zip(zip_path: Path) -> shapefile.Reader:
    zf = zipfile.ZipFile(zip_path)
    shp_names = [n for n in zf.namelist() if n.lower().endswith(".shp")]
    if not shp_names:
        raise RuntimeError(f"No .shp found in {zip_path}")
    base = shp_names[0][:-4]
    return shapefile.Reader(
        shp=io.BytesIO(zf.read(base + ".shp")),
        dbf=io.BytesIO(zf.read(base + ".dbf")),
        shx=io.BytesIO(zf.read(base + ".shx")),
    )


def resolve_counties_intersecting_search_window(
    parcel_geojson: Mapping[str, Any],
    *,
    search_window_m: float = SEARCH_WINDOW_DEFAULT_M,
    cache_dir: str | Path,
    source_crs: str = SOURCE_CRS_DEFAULT,
) -> dict[str, Any]:
    """Return county FIPS intersecting the projected parcel search window."""
    cache = Path(cache_dir)
    county_zip = cache / "tl_2025_us_county.zip"
    download_meta = download_url_to_path(COUNTY_ZIP_URL, county_zip)

    geom, _meta, extract_error = _extract_geometry_and_meta(parcel_geojson)
    if extract_error or geom is None or geom.is_empty:
        return {
            "ok": False,
            "reason": "PARCEL_GEOMETRY_UNUSABLE",
            "requested_county_fips": [],
            "county_download": download_meta,
            "extraction_error": extract_error,
        }
    crs_choice = select_working_crs(geom)
    if not crs_choice["ok"]:
        return {
            "ok": False,
            "reason": "CRS_UNSUPPORTED",
            "requested_county_fips": [],
            "county_download": download_meta,
            "crs_selection": crs_choice,
        }

    working_crs = crs_choice["working_crs"]
    parcel_proj = _project_geometry(geom, source_crs, working_crs)
    fetch_region = parcel_proj.buffer(float(search_window_m))
    to_wgs = Transformer.from_crs(
        CRS.from_user_input(working_crs), CRS.from_epsg(4326), always_xy=True
    )
    fetch_wgs = shapely_transform(to_wgs.transform, fetch_region)
    minx, miny, maxx, maxy = fetch_wgs.bounds

    reader = _shapefile_reader_from_zip(county_zip)
    fields = [f[0] for f in reader.fields[1:]]
    requested: list[str] = []
    matched: list[dict[str, Any]] = []
    for sr in reader.iterShapeRecords():
        county_geom = shape(sr.shape.__geo_interface__)
        if county_geom.is_empty:
            continue
        b = county_geom.bounds
        if b[2] < minx or b[0] > maxx or b[3] < miny or b[1] > maxy:
            continue
        county_proj = _project_geometry(county_geom, source_crs, working_crs)
        if not county_proj.intersects(fetch_region):
            continue
        props = {fields[i]: sr.record[i] for i in range(len(fields))}
        geoid = str(props.get("GEOID") or "")
        if len(geoid) != 5:
            statefp = str(props.get("STATEFP") or "").zfill(2)
            countyfp = str(props.get("COUNTYFP") or "").zfill(3)
            geoid = f"{statefp}{countyfp}"
        requested.append(geoid)
        matched.append(
            {
                "county_fips": geoid,
                "name": props.get("NAME"),
                "statefp": props.get("STATEFP"),
                "countyfp": props.get("COUNTYFP"),
            }
        )

    requested = sorted(set(requested))
    return {
        "ok": True,
        "reason": None,
        "requested_county_fips": requested,
        "counties": sorted(matched, key=lambda item: item["county_fips"]),
        "search_window_m": float(search_window_m),
        "working_crs": working_crs,
        "crs_selection": crs_choice,
        "fetch_region_bounds_wgs84": [minx, miny, maxx, maxy],
        "county_download": download_meta,
        "adapter_id": ADAPTER_ID,
    }


def load_county_all_roads_in_window(
    county_fips: str,
    fetch_region_proj,
    *,
    working_crs: str,
    cache_dir: str | Path,
    source_crs: str = SOURCE_CRS_DEFAULT,
) -> dict[str, Any]:
    """Download one county All Roads zip and return features intersecting fetch region."""
    cache = Path(cache_dir)
    url = ROADS_ZIP_URL_PATTERN.format(county_fips=county_fips)
    zip_path = cache / f"tl_2025_{county_fips}_roads.zip"
    download_meta = download_url_to_path(url, zip_path)

    to_wgs = Transformer.from_crs(
        CRS.from_user_input(working_crs), CRS.from_epsg(4326), always_xy=True
    )
    fetch_wgs = shapely_transform(to_wgs.transform, fetch_region_proj)
    minx, miny, maxx, maxy = fetch_wgs.bounds

    reader = _shapefile_reader_from_zip(zip_path)
    fields = [f[0] for f in reader.fields[1:]]
    features: list[dict[str, Any]] = []
    for sr in reader.iterShapeRecords():
        geom = shape(sr.shape.__geo_interface__)
        if geom.is_empty or geom.geom_type not in {"LineString", "MultiLineString"}:
            continue
        b = geom.bounds
        if b[2] < minx or b[0] > maxx or b[3] < miny or b[1] > maxy:
            continue
        geom_proj = _project_geometry(geom, source_crs, working_crs)
        if not geom_proj.intersects(fetch_region_proj):
            continue
        props = {fields[i]: sr.record[i] for i in range(len(fields))}
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "LINEARID": props.get("LINEARID"),
                    "MTFCC": props.get("MTFCC"),
                    "FULLNAME": props.get("FULLNAME"),
                    "COUNTYFP": county_fips[2:],
                    "STATEFP": county_fips[:2],
                    "COUNTY_FIPS": county_fips,
                },
                "geometry": mapping(geom),
            }
        )
    return {
        "county_fips": county_fips,
        "ok": True,
        "feature_count_in_window": len(features),
        "features": features,
        "download": download_meta,
        "url": url,
    }


def collect_tiger_2025_all_roads_for_parcel(
    parcel_geojson: Mapping[str, Any],
    *,
    cache_dir: str | Path,
    search_window_m: float = SEARCH_WINDOW_DEFAULT_M,
    source_crs: str = SOURCE_CRS_DEFAULT,
) -> dict[str, Any]:
    """Resolve counties, download All Roads for each, assemble window FeatureCollection."""
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    county_resolution = resolve_counties_intersecting_search_window(
        parcel_geojson,
        search_window_m=search_window_m,
        cache_dir=cache,
        source_crs=source_crs,
    )
    if not county_resolution.get("ok"):
        return {
            "ok": False,
            "road_source_id": CANONICAL_SOURCE_ID,
            "osm_consulted": False,
            "edges_fallback_used": False,
            "county_resolution": county_resolution,
            "requested_county_fips": [],
            "loaded_county_fips": [],
            "roads_geojson": {"type": "FeatureCollection", "features": []},
            "county_downloads": [],
            "adapter_id": ADAPTER_ID,
        }

    geom, _meta, _err = _extract_geometry_and_meta(parcel_geojson)
    working_crs = county_resolution["working_crs"]
    parcel_proj = _project_geometry(geom, source_crs, working_crs)
    fetch_region = parcel_proj.buffer(float(search_window_m))

    requested = list(county_resolution["requested_county_fips"])
    loaded: list[str] = []
    features: list[dict[str, Any]] = []
    county_downloads: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for fips in requested:
        try:
            loaded_county = load_county_all_roads_in_window(
                fips,
                fetch_region,
                working_crs=working_crs,
                cache_dir=cache,
                source_crs=source_crs,
            )
            loaded.append(fips)
            features.extend(loaded_county["features"])
            county_downloads.append(
                {
                    "county_fips": fips,
                    "ok": True,
                    "feature_count_in_window": loaded_county["feature_count_in_window"],
                    "download": loaded_county["download"],
                    "url": loaded_county["url"],
                }
            )
        except Exception as exc:  # noqa: BLE001 - record per-county failure for PARTIAL/UNKNOWN
            failures.append({"county_fips": fips, "ok": False, "error": str(exc)})
            county_downloads.append(
                {"county_fips": fips, "ok": False, "error": str(exc)}
            )

    # Deterministic feature order for artifact hashing.
    features.sort(
        key=lambda f: (
            str((f.get("properties") or {}).get("LINEARID") or ""),
            json.dumps(f.get("geometry"), sort_keys=True),
        )
    )
    roads_geojson = {
        "type": "FeatureCollection",
        "name": "F07_TIGER2025_ALL_ROADS_SEARCH_WINDOW",
        "properties": {
            "road_source_id": CANONICAL_SOURCE_ID,
            "road_product_vintage": TIGER_YEAR,
            "requested_county_fips": requested,
            "loaded_county_fips": sorted(set(loaded)),
            "search_window_m": float(search_window_m),
            "adapter_id": ADAPTER_ID,
            "osm_consulted": False,
            "edges_fallback_used": False,
        },
        "features": features,
    }
    artifact_hash = _sha256_bytes(
        json.dumps(roads_geojson, sort_keys=True, separators=(",", ":")).encode()
    )
    return {
        "ok": len(failures) == 0 and bool(requested),
        "road_source_id": CANONICAL_SOURCE_ID,
        "osm_consulted": False,
        "edges_fallback_used": False,
        "county_resolution": county_resolution,
        "requested_county_fips": requested,
        "loaded_county_fips": sorted(set(loaded)),
        "missing_county_fips": sorted(set(requested) - set(loaded)),
        "roads_geojson": roads_geojson,
        "road_artifact_hash": artifact_hash,
        "county_downloads": county_downloads,
        "failures": failures,
        "adapter_id": ADAPTER_ID,
        "feature_count_in_window": len(features),
    }


def derive_f07_via_tiger_adapter(
    parcel_geojson: Mapping[str, Any],
    *,
    cache_dir: str | Path,
    search_window_m: float = SEARCH_WINDOW_DEFAULT_M,
    geometry_hash: str | None = None,
    geometry_reference: str | None = None,
    geometry_id: str | None = None,
    derived_at: str | None = None,
    collection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Collect TIGER 2025 All Roads and derive F07 in one call."""
    collected = dict(
        collection
        or collect_tiger_2025_all_roads_for_parcel(
            parcel_geojson,
            cache_dir=cache_dir,
            search_window_m=search_window_m,
        )
    )
    derived = derive_f07_from_inputs(
        parcel_geojson,
        collected["roads_geojson"],
        requested_county_fips=collected["requested_county_fips"],
        loaded_county_fips=collected["loaded_county_fips"],
        geometry_hash=geometry_hash,
        geometry_reference=geometry_reference,
        geometry_id=geometry_id,
        search_window_m=search_window_m,
        road_source_id=CANONICAL_SOURCE_ID,
        road_product_vintage=TIGER_YEAR,
        road_artifact_hash=collected.get("road_artifact_hash"),
        derived_at=derived_at,
    )
    derived["adapter"] = {
        "adapter_id": ADAPTER_ID,
        "osm_consulted": False,
        "edges_fallback_used": False,
        "requested_county_fips": collected["requested_county_fips"],
        "loaded_county_fips": collected["loaded_county_fips"],
        "missing_county_fips": collected.get("missing_county_fips"),
        "county_downloads": collected.get("county_downloads"),
        "county_resolution": {
            "fetch_region_bounds_wgs84": collected.get("county_resolution", {}).get(
                "fetch_region_bounds_wgs84"
            ),
            "county_download": collected.get("county_resolution", {}).get(
                "county_download"
            ),
            "counties": collected.get("county_resolution", {}).get("counties"),
        },
        "feature_count_in_window": collected.get("feature_count_in_window"),
        "collection_ok": collected.get("ok"),
    }
    derived["_collection"] = collected
    return derived


def run_cper_f07_live_gate(
    *,
    repo_root: str | Path,
    cache_dir: str | Path | None = None,
    write_artifacts: bool = True,
) -> dict[str, Any]:
    """Execute the CPER F07 live gate against TIGER/Line 2025 All Roads."""
    root = Path(repo_root)
    geometry_path = root / "test-data/engineering_test_geometry_cper_001.geojson"
    profile_path = root / "test-data/land-profiles/land_profile_cper_001.json"
    out_dir = root / "test-data/live-results/cper"
    cache = Path(cache_dir) if cache_dir else out_dir / "tiger2025_cache"

    parcel = json.loads(geometry_path.read_text())
    collection = collect_tiger_2025_all_roads_for_parcel(parcel, cache_dir=cache)
    derived = derive_f07_via_tiger_adapter(
        parcel,
        cache_dir=cache,
        geometry_hash=sha256_file(geometry_path),
        geometry_reference="test-data/engineering_test_geometry_cper_001.geojson",
        geometry_id="ENGINEERING_TEST_GEOMETRY_CPER_001",
        collection=collection,
    )
    collection_artifact = derived.pop("_collection", collection)

    live_gate = {
        "live_gate_id": "F07_TIGER2025_ALL_ROADS_CPER",
        "status": (
            "LIVE_VERIFIED"
            if derived.get("input_quality_state")
            in {"ROAD_CONTEXT_COMPLETE", "NO_MAPPED_ROAD_IN_SEARCH_WINDOW"}
            else "LIVE_NEEDS_VERIFICATION"
        ),
        "road_source_id": CANONICAL_SOURCE_ID,
        "osm_consulted": False,
        "edges_fallback_used": False,
        "requested_county_fips": derived.get("county_coverage", {}).get(
            "requested_county_fips"
        ),
        "loaded_county_fips": derived.get("county_coverage", {}).get("loaded_county_fips"),
        "county_coverage_status": derived.get("county_coverage", {}).get("status"),
        "input_quality_state": derived.get("input_quality_state"),
        "signal": None,
        "ranking_effect": "NONE",
        "adapter_id": ADAPTER_ID,
        "derived_at": derived.get("derived_at"),
    }
    from rangematch.f07_derivation import evaluate_f07_signal

    signal = evaluate_f07_signal(derived)
    live_gate["signal"] = signal["signal"]
    live_gate["explanation_code"] = signal["explanation_code"]

    if write_artifacts:
        out_dir.mkdir(parents=True, exist_ok=True)
        roads_path = out_dir / "f07_tiger2025_all_roads_search_window.geojson"
        roads_path.write_text(json.dumps(collection_artifact["roads_geojson"]) + "\n")
        derived["result_reference"] = (
            "test-data/live-results/cper/f07_derivation_result_2026-08-08.json"
        )
        derived["source_fixture_references"] = [
            "test-data/live-results/cper/f07_tiger2025_all_roads_search_window.geojson"
        ]
        derived["live_gate"] = live_gate
        result_path = out_dir / "f07_derivation_result_2026-08-08.json"
        result_path.write_text(json.dumps(derived, indent=2) + "\n")

        # Slim factor into land profile + regenerate MatchResult/demo.
        from rangematch.demo_report import write_demo_closure
        from rangematch.engine import evaluate_land_profile

        factor = {
            "factor_id": derived["factor_id"],
            "input_quality_state": derived["input_quality_state"],
            "derivation_spec": derived["derivation_spec"],
            "algorithm_version": derived["algorithm_version"],
            "road_source_id": derived["road_source_id"],
            "road_product": derived["road_product"],
            "road_product_vintage": derived["road_product_vintage"],
            "search_window_m": derived["search_window_m"],
            "source_crs": derived["source_crs"],
            "working_crs": derived.get("working_crs"),
            "crs_selection": derived.get("crs_selection"),
            "geometry_id": derived.get("geometry_id"),
            "geometry_reference": derived.get("geometry_reference"),
            "geometry_hash": derived.get("geometry_hash"),
            "geometry_validity": derived.get("geometry_validity"),
            "county_coverage": derived.get("county_coverage"),
            "mapped_road_feature_count_in_search_window": derived.get(
                "mapped_road_feature_count_in_search_window"
            ),
            "road_parcel_contact_status": derived.get("road_parcel_contact_status"),
            "road_parcel_contact_detail": derived.get("road_parcel_contact_detail"),
            "nearest_mapped_road_distance_m": derived.get(
                "nearest_mapped_road_distance_m"
            ),
            "nearest_road_feature_id": derived.get("nearest_road_feature_id"),
            "nearest_road_class_context": derived.get("nearest_road_class_context"),
            "nearest_road_fullname": derived.get("nearest_road_fullname"),
            "nearest_feature_tie_break": derived.get("nearest_feature_tie_break"),
            "road_source_coverage_status": derived.get("road_source_coverage_status"),
            "road_artifact_hash": derived.get("road_artifact_hash"),
            "osm_consulted": False,
            "edges_fallback_used": False,
            "ranking_effect": "NONE",
            "derived_at": derived.get("derived_at"),
            "provenance": derived.get("provenance"),
            "adapter": derived.get("adapter"),
            "live_gate": live_gate,
            "limitations": derived.get("limitations"),
            "unknowns": derived.get("unknowns"),
            "prohibited_interpretations_applied": True,
            "result_reference": derived["result_reference"],
            "source_fixture_references": derived["source_fixture_references"],
        }
        profile = json.loads(profile_path.read_text())
        profile["factors"]["F07_ROAD_AND_PHYSICAL_ACCESS"] = factor
        profile_path.write_text(json.dumps(profile, indent=2) + "\n")
        match_result = evaluate_land_profile(profile)
        (root / "test-data/land-profiles/match_result_cper_001.json").write_text(
            json.dumps(match_result, indent=2) + "\n"
        )
        write_demo_closure(
            profile_path,
            html_output=root
            / "test-data/land-profiles/land_profile_cper_001_demo_closure.html",
            json_output=root
            / "test-data/land-profiles/land_profile_cper_001_demo_closure.json",
        )
        gate_doc = {
            "live_gate": live_gate,
            "measurements": {
                "mapped_road_feature_count_in_search_window": derived.get(
                    "mapped_road_feature_count_in_search_window"
                ),
                "road_parcel_contact_status": derived.get("road_parcel_contact_status"),
                "road_parcel_contact_detail": derived.get("road_parcel_contact_detail"),
                "nearest_mapped_road_distance_m": derived.get(
                    "nearest_mapped_road_distance_m"
                ),
                "nearest_road_feature_id": derived.get("nearest_road_feature_id"),
                "nearest_road_class_context": derived.get("nearest_road_class_context"),
                "search_window_m": derived.get("search_window_m"),
                "working_crs": derived.get("working_crs"),
            },
            "county_coverage": derived.get("county_coverage"),
            "provenance": derived.get("provenance"),
            "adapter": derived.get("adapter"),
        }
        (out_dir / "f07_live_gate_cper_2026-08-08.json").write_text(
            json.dumps(gate_doc, indent=2) + "\n"
        )

    return {"live_gate": live_gate, "derived": derived}
