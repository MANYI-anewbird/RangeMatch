#!/usr/bin/env python3
"""F03 five-parcel provenance-complete remote evidence collection.

Applies the CPER remote-evidence workflow to all five frozen XPV parcels with
deterministic candidate sampling (stable candidate_id order, max 3).

Does not manufacture FIELD_VERIFIED_LIVESTOCK_WATER.
Does not change F03 runtime rules, suitability thresholds, or species ranking.
"""

from __future__ import annotations

import hashlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from rangematch.f03_verification import (  # noqa: E402
    CONTRACT_VERSION,
    SELECTION_METHOD_STABLE_CANDIDATE_ID_ORDER,
    apply_remote_enrichment,
    build_mapped_candidate_from_nhd,
    factor_input_quality_from_levels,
    remote_presence_provenance_complete,
    stable_sample_f03_candidates,
)

AS_OF = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
REVIEW_DATE = AS_OF[:10]
REVIEWER_OR_ADAPTER_ID = "rangematch.f03_five_parcel_remote_collection/v1"
STAC_SEARCH = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
STAC_ITEM_TMPL = (
    "https://planetarycomputer.microsoft.com/api/stac/v1/collections/naip/items/{item_id}"
)
SAS_SIGN = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"
MAX_CANDIDATES = 3
BBOX_PAD_DEG = 0.00035

PARCELS: list[dict[str, Any]] = [
    {
        "parcel_id": "XPV_CPER_001",
        "geometry_path": PROJECT / "test-data/engineering_test_geometry_cper_001.geojson",
        "inventory_path": PROJECT
        / "test-data/live-results/cper/cper_f03_candidate_distance_result_2026-08-07.json",
        "land_profile_path": PROJECT / "test-data/land-profiles/land_profile_cper_001.json",
        "nhd_geojson_paths": [
            PROJECT / "test-data/live-results/cper/cper_nhd_waterbodies.geojson",
            PROJECT / "test-data/live-results/cper/cper_nhd_network_flowlines.geojson",
            PROJECT / "test-data/live-results/cper/cper_nhd_nonnetwork_flowlines.geojson",
            PROJECT / "test-data/live-results/cper/cper_nhd_areas.geojson",
        ],
        "out_dir": PROJECT
        / "test-data/cross-parcel-validation/XPV_CPER_001/f03_remote_pilot",
    },
    {
        "parcel_id": "XPV_KONZA_001",
        "geometry_path": PROJECT / "test-data/engineering_test_geometry_konza_001.geojson",
        "inventory_path": PROJECT
        / "test-data/cross-parcel-validation/XPV_KONZA_001/live-results/"
        "f03_candidate_distance_result.json",
        "land_profile_path": PROJECT
        / "test-data/cross-parcel-validation/XPV_KONZA_001/land_profile.json",
        "nhd_geojson_paths": [
            PROJECT
            / "test-data/cross-parcel-validation/XPV_KONZA_001/live-results/"
            "nhd_nhdwaterbody.geojson",
            PROJECT
            / "test-data/cross-parcel-validation/XPV_KONZA_001/live-results/"
            "nhd_networknhdflowline.geojson",
            PROJECT
            / "test-data/cross-parcel-validation/XPV_KONZA_001/live-results/"
            "nhd_nonnetworknhdflowline.geojson",
            PROJECT
            / "test-data/cross-parcel-validation/XPV_KONZA_001/live-results/"
            "nhd_nhdarea.geojson",
        ],
        "out_dir": PROJECT
        / "test-data/cross-parcel-validation/XPV_KONZA_001/f03_remote_pilot",
    },
    {
        "parcel_id": "XPV_REYNOLDS_001",
        "geometry_path": PROJECT / "test-data/engineering_test_geometry_reynolds_001.geojson",
        "inventory_path": PROJECT
        / "test-data/cross-parcel-validation/XPV_REYNOLDS_001/live-results/"
        "f03_candidate_distance_result.json",
        "land_profile_path": PROJECT
        / "test-data/cross-parcel-validation/XPV_REYNOLDS_001/land_profile.json",
        "nhd_geojson_paths": [
            PROJECT
            / "test-data/cross-parcel-validation/XPV_REYNOLDS_001/live-results/"
            "nhd_nhdwaterbody.geojson",
            PROJECT
            / "test-data/cross-parcel-validation/XPV_REYNOLDS_001/live-results/"
            "nhd_networknhdflowline.geojson",
            PROJECT
            / "test-data/cross-parcel-validation/XPV_REYNOLDS_001/live-results/"
            "nhd_nonnetworknhdflowline.geojson",
            PROJECT
            / "test-data/cross-parcel-validation/XPV_REYNOLDS_001/live-results/"
            "nhd_nhdarea.geojson",
        ],
        "out_dir": PROJECT
        / "test-data/cross-parcel-validation/XPV_REYNOLDS_001/f03_remote_pilot",
    },
    {
        "parcel_id": "XPV_ORDWAY_001",
        "geometry_path": PROJECT / "test-data/engineering_test_geometry_ordway_001.geojson",
        "inventory_path": PROJECT
        / "test-data/cross-parcel-validation/XPV_ORDWAY_001/live-results/"
        "f03_candidate_distance_result.json",
        "land_profile_path": PROJECT
        / "test-data/cross-parcel-validation/XPV_ORDWAY_001/land_profile.json",
        "nhd_geojson_paths": [
            PROJECT
            / "test-data/cross-parcel-validation/XPV_ORDWAY_001/live-results/"
            "nhd_nhdwaterbody.geojson",
            PROJECT
            / "test-data/cross-parcel-validation/XPV_ORDWAY_001/live-results/"
            "nhd_networknhdflowline.geojson",
            PROJECT
            / "test-data/cross-parcel-validation/XPV_ORDWAY_001/live-results/"
            "nhd_nonnetworknhdflowline.geojson",
            PROJECT
            / "test-data/cross-parcel-validation/XPV_ORDWAY_001/live-results/"
            "nhd_nhdarea.geojson",
        ],
        "out_dir": PROJECT
        / "test-data/cross-parcel-validation/XPV_ORDWAY_001/f03_remote_pilot",
    },
    {
        "parcel_id": "XPV_KBS_MCSE_001",
        "geometry_path": PROJECT / "test-data/engineering_test_geometry_kbs_mcse_001.geojson",
        "inventory_path": PROJECT
        / "test-data/cross-parcel-validation/XPV_KBS_MCSE_001/live-results/"
        "f03_candidate_distance_result.json",
        "land_profile_path": PROJECT
        / "test-data/cross-parcel-validation/XPV_KBS_MCSE_001/land_profile.json",
        "nhd_geojson_paths": [
            PROJECT
            / "test-data/cross-parcel-validation/XPV_KBS_MCSE_001/live-results/"
            "nhd_nhdwaterbody.geojson",
            PROJECT
            / "test-data/cross-parcel-validation/XPV_KBS_MCSE_001/live-results/"
            "nhd_networknhdflowline.geojson",
            PROJECT
            / "test-data/cross-parcel-validation/XPV_KBS_MCSE_001/live-results/"
            "nhd_nonnetworknhdflowline.geojson",
            PROJECT
            / "test-data/cross-parcel-validation/XPV_KBS_MCSE_001/live-results/"
            "nhd_nhdarea.geojson",
        ],
        "out_dir": PROJECT
        / "test-data/cross-parcel-validation/XPV_KBS_MCSE_001/f03_remote_pilot",
    },
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_inventory(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text())
    return list(payload.get("candidate_inventory") or payload.get("candidates") or [])


def f03_before_state(land_profile_path: Path) -> dict[str, Any]:
    profile = json.loads(land_profile_path.read_text())
    f03 = (profile.get("factors") or {}).get("F03_LIVESTOCK_WATER") or {}
    return {
        "input_quality_state": f03.get("input_quality_state"),
        "mapped_candidate_count": f03.get("mapped_candidate_count"),
        "verified_livestock_water_system_count": f03.get(
            "verified_livestock_water_system_count"
        ),
    }


def _iter_coords(geom: dict[str, Any]):
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "Point":
        yield coords
    elif gtype in {"MultiPoint", "LineString"}:
        for c in coords:
            yield c
    elif gtype in {"MultiLineString", "Polygon"}:
        for part in coords:
            for c in part:
                yield c
    elif gtype == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                for c in ring:
                    yield c
    elif gtype == "GeometryCollection":
        for child in geom.get("geometries") or []:
            yield from _iter_coords(child)


def geometry_bbox(geom: dict[str, Any], pad: float = BBOX_PAD_DEG) -> list[float]:
    xs = []
    ys = []
    for x, y, *rest in _iter_coords(geom):
        xs.append(float(x))
        ys.append(float(y))
    if not xs:
        raise ValueError("empty geometry")
    return [
        min(xs) - pad,
        min(ys) - pad,
        max(xs) + pad,
        max(ys) + pad,
    ]


def geometry_hash(geom: dict[str, Any]) -> str:
    canonical = json.dumps(geom, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(canonical)


def find_nhd_feature(
    nhd_paths: list[Path], source_feature_id: str
) -> tuple[dict[str, Any] | None, Path | None]:
    target = str(source_feature_id)
    for path in nhd_paths:
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        for feature in data.get("features") or []:
            props = feature.get("properties") or {}
            for key in (
                "permanent_identifier",
                "Permanent_Identifier",
                "nhdplusid",
                "NHDPlusID",
                "OBJECTID",
                "objectid",
            ):
                if str(props.get(key)) == target:
                    return feature, path
            if target in {str(v) for v in props.values()}:
                return feature, path
    return None, None


def freshness_status(acquisition_date: str, review_date: str) -> str:
    try:
        acq = datetime.fromisoformat(acquisition_date)
        rev = datetime.fromisoformat(review_date)
        years = (rev - acq).days / 365.25
        if years <= 3:
            return f"ACQUISITION_{acquisition_date}_WITHIN_THREE_YEARS_OF_REVIEW"
        return f"ACQUISITION_{acquisition_date}_OLDER_THAN_THREE_YEARS"
    except ValueError:
        return f"ACQUISITION_{acquisition_date}_FRESHNESS_UNPARSED"


def _session():
    import requests

    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": "RangeMatchF03RemoteCollection/1.0"})
    return session


def fetch_naip_package(
    *,
    candidate: dict[str, Any],
    bbox: list[float],
    parcel_hash: str,
    candidate_geom_hash: str,
    artifact_dir: Path,
) -> dict[str, Any]:
    """Retrieve NAIP STAC item + local GeoTIFF crop. Raises on hard failure."""
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_bounds
    from rasterio.warp import transform_bounds

    session = _session()
    search = session.post(
        STAC_SEARCH,
        json={
            "collections": ["naip"],
            "bbox": bbox,
            "datetime": "2018-01-01T00:00:00Z/2025-12-31T23:59:59Z",
            "limit": 5,
        },
        timeout=90,
    )
    search.raise_for_status()
    items = (search.json().get("features") or [])
    if not items:
        raise RuntimeError("NAIP_STAC_NO_ITEMS")
    items = sorted(
        items,
        key=lambda item: (
            (item.get("properties") or {}).get("datetime") or "",
            item.get("id") or "",
        ),
        reverse=True,
    )
    item = items[0]
    item_id = item["id"]
    stac_url = STAC_ITEM_TMPL.format(item_id=item_id)
    stac_path = artifact_dir / f"naip_stac_item_{item_id}.json"
    # Re-fetch canonical item JSON for stable fixture hash.
    item_resp = session.get(stac_url, timeout=90)
    item_resp.raise_for_status()
    item = item_resp.json()
    stac_path.write_text(json.dumps(item, indent=2) + "\n")

    href = ((item.get("assets") or {}).get("image") or {}).get("href")
    if not href:
        raise RuntimeError("NAIP_STAC_IMAGE_ASSET_MISSING")
    signed = session.get(SAS_SIGN, params={"href": href}, timeout=60)
    signed.raise_for_status()
    signed_href = signed.json()["href"]

    feature_id = str(candidate.get("source_feature_id"))
    crop_path = artifact_dir / f"naip_crop_{feature_id}.tif"
    west, south, east, north = bbox
    with rasterio.open(signed_href) as dataset:
        dest_crs = dataset.crs
        left, bottom, right, top = transform_bounds(
            "EPSG:4326", dest_crs, west, south, east, north, densify_pts=21
        )
        # Keep crop modest for fixture size.
        width = max(64, min(768, int((right - left) / max(dataset.res[0], 1e-6))))
        height = max(64, min(768, int((top - bottom) / max(dataset.res[1], 1e-6))))
        transform = from_bounds(left, bottom, right, top, width, height)
        count = min(3, dataset.count)
        data = np.zeros((count, height, width), dtype=dataset.dtypes[0])
        dataset.read(
            indexes=list(range(1, count + 1)),
            out=data,
            window=dataset.window(left, bottom, right, top),
            resampling=Resampling.bilinear,
        )
        profile = dataset.profile.copy()
        profile.update(
            {
                "height": height,
                "width": width,
                "transform": transform,
                "count": count,
                "compress": "deflate",
            }
        )
        with rasterio.open(crop_path, "w", **profile) as dst:
            dst.write(data)

    acquisition = (item.get("properties") or {}).get("datetime") or ""
    acquisition_date = acquisition[:10] if acquisition else "unknown"
    gsd = (item.get("properties") or {}).get("naip:gsd")
    year = (item.get("properties") or {}).get("naip:year")
    product_name = f"NAIP {year or acquisition_date[:4]} {gsd or '?'} m orthoimagery"
    artifact_hash = sha256_file(crop_path)
    stac_hash = sha256_file(stac_path)
    provenance = {
        "provider": "USDA Farm Service Agency (via Microsoft Planetary Computer STAC)",
        "product_name": product_name,
        "source_url": stac_url,
        "item_id_or_artifact_reference": (
            f"stac:naip/{item_id}; "
            f"local_artifact={crop_path.relative_to(PROJECT)}; "
            f"stac_fixture={stac_path.relative_to(PROJECT)}"
        ),
        "imagery_acquisition_date": acquisition_date,
        "review_date": REVIEW_DATE,
        "reviewer_or_adapter_id": REVIEWER_OR_ADAPTER_ID,
        "candidate_geometry_hash": candidate_geom_hash,
        "parcel_geometry_hash": parcel_hash,
        "response_or_artifact_hash": artifact_hash,
        "supporting_artifact_hashes": {
            "naip_crop_geotiff": artifact_hash,
            "stac_item_json": stac_hash,
        },
        "supported_claim": (
            "Physical hydrographic feature context visible in NAIP imagery within "
            f"the exported bbox covering source_feature_id={feature_id}."
        ),
        "unsupported_claims": [
            "livestock_accessibility",
            "seasonal_reliability_beyond_nhd_fcode",
            "legal_access",
            "deliverable_capacity",
            "water_quality",
            "operable_livestock_water_system",
            "field_verification",
        ],
        "limitations": [
            "Remote orthoimagery confirms landscape presence context only.",
            "Feature visibility is not proof of usable livestock water.",
            "Single NAIP date does not establish seasonal class by itself.",
            "SAS-signed COG URLs expire; reproducible package is local GeoTIFF + STAC JSON.",
        ],
        "freshness_status": freshness_status(acquisition_date, REVIEW_DATE),
        "bbox_wgs84_export": bbox,
        "stac_item_id": item_id,
        "producer_url": (
            "https://www.fsa.usda.gov/programs-and-services/aerial-photography/"
            "imagery-programs/naip-imagery/"
        ),
    }
    gate = remote_presence_provenance_complete(provenance)
    if not gate["complete"]:
        raise RuntimeError(
            "PROVENANCE_INCOMPLETE_AFTER_FETCH:" + ",".join(gate["missing_fields"])
        )
    return {
        "source": "imagery",
        "observation_date": acquisition_date,
        "review_note": (
            "Five-parcel remote collection: USDA NAIP STAC item via Microsoft "
            "Planetary Computer; local GeoTIFF crop hashed and retained."
        ),
        "evidence_source_ids": [
            "USDA_FSA_NAIP",
            "MICROSOFT_PLANETARY_COMPUTER_STAC",
            "USGS_NHDPLUS_HR",
        ],
        "provenance": provenance,
        "data_path_status": "OK",
        "local_crop_artifact": str(crop_path.relative_to(PROJECT)),
        "stac_item_id": item_id,
        "stac_url": stac_url,
        "imagery_acquisition_date": acquisition_date,
        "product_name": product_name,
    }


def attempt_presence_package(
    *,
    candidate: dict[str, Any],
    nhd_paths: list[Path],
    parcel_hash: str,
    artifact_dir: Path,
) -> dict[str, Any]:
    feature_id = str(candidate.get("source_feature_id"))
    feature, nhd_path = find_nhd_feature(nhd_paths, feature_id)
    if feature is None or not feature.get("geometry"):
        return {
            "data_path_status": "FAILED",
            "failure_code": "NHD_GEOMETRY_NOT_FOUND",
            "failure_detail": f"No local NHD geometry for source_feature_id={feature_id}",
            "reviewed_presence": {
                "review_note": "NHD geometry lookup failed; cannot form provenance package.",
                "provenance": {},
            },
        }
    try:
        geom = feature["geometry"]
        bbox = geometry_bbox(geom)
        cand_hash = candidate.get("geometry_hash") or geometry_hash(geom)
        package = fetch_naip_package(
            candidate=candidate,
            bbox=bbox,
            parcel_hash=parcel_hash,
            candidate_geom_hash=cand_hash,
            artifact_dir=artifact_dir,
        )
        return {
            "data_path_status": "OK",
            "candidate_geometry_hash": cand_hash,
            "bbox_wgs84": bbox,
            "nhd_source_path": str(nhd_path.relative_to(PROJECT)) if nhd_path else None,
            "reviewed_presence": {
                "source": package["source"],
                "observation_date": package["observation_date"],
                "review_note": package["review_note"],
                "evidence_source_ids": package["evidence_source_ids"],
                "provenance": package["provenance"],
            },
            "evidence_source_used": {
                "provider": "USDA Farm Service Agency",
                "product": package["product_name"],
                "access_path": "Microsoft Planetary Computer STAC (naip collection)",
                "stac_item_id": package["stac_item_id"],
                "stac_url": package["stac_url"],
                "local_crop_artifact": package["local_crop_artifact"],
                "imagery_acquisition_date": package["imagery_acquisition_date"],
            },
        }
    except Exception as exc:  # noqa: BLE001 - data-path isolation
        return {
            "data_path_status": "FAILED",
            "failure_code": type(exc).__name__,
            "failure_detail": str(exc)[:500],
            "failure_traceback": traceback.format_exc(limit=4)[:1500],
            "candidate_geometry_hash": candidate.get("geometry_hash"),
            "reviewed_presence": {
                "review_note": (
                    "Imagery/source retrieval failed; candidate remains "
                    "MAPPED_CANDIDATE. Failure is a data-path status, not a land problem."
                ),
                "provenance": {},
            },
        }


def process_parcel(cfg: dict[str, Any]) -> dict[str, Any]:
    parcel_id = cfg["parcel_id"]
    out_dir: Path = cfg["out_dir"]
    artifact_dir = out_dir / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    inventory = load_inventory(cfg["inventory_path"])
    sampling = stable_sample_f03_candidates(inventory, max_n=MAX_CANDIDATES)
    selected = sampling["selected"]
    parcel_hash = sha256_file(cfg["geometry_path"])
    before = f03_before_state(cfg["land_profile_path"])

    results = []
    data_path_statuses = []
    evidence_sources = []
    conflicts = []

    for raw in selected:
        presence_attempt = attempt_presence_package(
            candidate=raw,
            nhd_paths=cfg["nhd_geojson_paths"],
            parcel_hash=parcel_hash,
            artifact_dir=artifact_dir,
        )
        data_path_statuses.append(
            {
                "candidate_id": raw.get("candidate_id"),
                "status": presence_attempt["data_path_status"],
                "failure_code": presence_attempt.get("failure_code"),
                "failure_detail": presence_attempt.get("failure_detail"),
            }
        )
        if presence_attempt.get("evidence_source_used"):
            evidence_sources.append(presence_attempt["evidence_source_used"])

        mapped = build_mapped_candidate_from_nhd(
            {
                **raw,
                "as_of": AS_OF,
                "geometry_hash": presence_attempt.get("candidate_geometry_hash")
                or raw.get("geometry_hash"),
            }
        )
        reviewed = presence_attempt.get("reviewed_presence")
        enriched = apply_remote_enrichment(
            mapped,
            seasonal_from_fcode=True,
            reviewed_presence=reviewed,
        )
        level = enriched["promotion_evaluation"]["verification_level"]
        if level == "FIELD_VERIFIED_LIVESTOCK_WATER":
            raise AssertionError(f"{parcel_id}: remote path produced FIELD_VERIFIED")

        presence = enriched["dimensions"]["physical_presence"]
        provenance = presence.get("provenance")
        prov_complete = (
            remote_presence_provenance_complete(provenance)["complete"]
            if provenance
            else False
        )
        if enriched.get("unresolved_material_conflict"):
            conflicts.append(raw.get("candidate_id"))

        row = {
            "candidate_id": enriched.get("candidate_id"),
            "source_layer": enriched.get("source_layer"),
            "source_feature_id": enriched.get("source_feature_id"),
            "fcode": enriched.get("fcode"),
            "gnis_name": enriched.get("gnis_name"),
            "candidate_geometry_hash": presence_attempt.get("candidate_geometry_hash")
            or raw.get("geometry_hash"),
            "baseline_level": "MAPPED_CANDIDATE",
            "after_remote_level": level,
            "reason_codes": enriched["promotion_evaluation"]["reason_codes"],
            "seasonal_reliability": enriched["dimensions"]["seasonal_reliability"],
            "physical_presence": presence,
            "evidence_use_limit": enriched.get("evidence_use_limit"),
            "provenance_complete": prov_complete,
            "data_path_status": presence_attempt["data_path_status"],
            "failure_code": presence_attempt.get("failure_code"),
            "reviewed_presence_attempted": reviewed is not None,
            "field_verified": False,
            "evidence_source_used": presence_attempt.get("evidence_source_used"),
        }
        results.append(row)

        if level == "REMOTELY_SUPPORTED_CANDIDATE" and provenance:
            prov_path = out_dir / f"presence_provenance_{raw.get('source_feature_id')}.json"
            prov_path.write_text(json.dumps(provenance, indent=2) + "\n")

    levels = [row["after_remote_level"] for row in results]
    hist = {level: levels.count(level) for level in sorted(set(levels))}
    after_state = factor_input_quality_from_levels(levels)
    # Parcel Factor state remains MAPPED_CANDIDATES_ONLY until field-verified systems exist.
    field_verified_count = sum(1 for level in levels if level == "FIELD_VERIFIED_LIVESTOCK_WATER")
    remotely_supported_count = hist.get("REMOTELY_SUPPORTED_CANDIDATE", 0)
    mapped_count = hist.get("MAPPED_CANDIDATE", 0)
    provenance_complete_count = sum(1 for row in results if row["provenance_complete"])
    failed_paths = [s for s in data_path_statuses if s["status"] != "OK"]

    summary = {
        "pilot_id": f"F03_REMOTE_ONLY_PILOT_{parcel_id}",
        "pilot_version": "five_parcel_collection_v1",
        "contract_version": CONTRACT_VERSION,
        "adapter_authorization": "APPROVED_FOR_SMALL_SCALE_PILOT",
        "parcel_id": parcel_id,
        "parcel_geometry_hash": parcel_hash,
        "as_of": AS_OF,
        "scope": "MAPPED_CANDIDATE → remote enrichment → REMOTELY_SUPPORTED|MAPPED",
        "selection_method": SELECTION_METHOD_STABLE_CANDIDATE_ID_ORDER,
        "selection": {
            "method": sampling["selection_method"],
            "max_n": sampling["max_n"],
            "available_count": sampling["available_count"],
            "sampled_count": sampling["sampled_count"],
            "selection_keys": sampling["selection_keys"],
            "selection_not_based_on_expected_promotion": True,
        },
        "evidence_source_used": evidence_sources[0] if evidence_sources else None,
        "evidence_sources": evidence_sources,
        "data_path_statuses": data_path_statuses,
        "data_path_failures": failed_paths,
        "conflicts": conflicts,
        "provenance_gate_passed": remotely_supported_count > 0
        and all(
            row["provenance_complete"]
            for row in results
            if row["after_remote_level"] == "REMOTELY_SUPPORTED_CANDIDATE"
        ),
        "field_verified_manufactured": False,
        "field_verified_count": field_verified_count,
        "candidate_count": len(results),
        "level_histogram": hist,
        "counts": {
            "available": sampling["available_count"],
            "sampled": sampling["sampled_count"],
            "MAPPED_CANDIDATE": mapped_count,
            "REMOTELY_SUPPORTED_CANDIDATE": remotely_supported_count,
            "FIELD_VERIFIED_LIVESTOCK_WATER": field_verified_count,
            "provenance_complete": provenance_complete_count,
        },
        "parcel_factor_state_before": before,
        "parcel_factor_state_after": {
            "input_quality_state": after_state,
            "sampled_mapped_count": mapped_count,
            "sampled_remotely_supported_count": remotely_supported_count,
            "sampled_field_verified_count": field_verified_count,
            "note": (
                "Parcel Land Fact input_quality_state remains MAPPED_CANDIDATES_ONLY "
                "because field_verified_count stays 0; remote support does not change "
                "runtime Factor rules."
            ),
        },
        "parcel_input_quality_state": after_state,
        "runtime_rules_changed": False,
        "suitability_thresholds_added": False,
        "cow_sheep_ranking_added": False,
        "ranking_effect": "NONE",
        "candidates": results,
        "next_gate": (
            "Five-parcel remote collection complete for review. "
            "Do not begin field/operator evidence ingestion until accepted."
        ),
    }
    out_path = out_dir / "remote_pilot_result.json"
    out_path.write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def collection_gate_passed(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    reasons = []
    ok = True
    if len(summaries) != 5:
        ok = False
        reasons.append("EXPECTED_FIVE_PARCEL_SUMMARIES")
    for summary in summaries:
        if summary.get("field_verified_count", 1) != 0:
            ok = False
            reasons.append(f"{summary['parcel_id']}:FIELD_VERIFIED_NONZERO")
        if summary.get("runtime_rules_changed") is not False:
            ok = False
            reasons.append(f"{summary['parcel_id']}:RUNTIME_RULES_CHANGED")
        if summary.get("ranking_effect") != "NONE":
            ok = False
            reasons.append(f"{summary['parcel_id']}:RANKING_EFFECT")
        if summary.get("selection_method") != SELECTION_METHOD_STABLE_CANDIDATE_ID_ORDER:
            ok = False
            reasons.append(f"{summary['parcel_id']}:SELECTION_METHOD")
        for row in summary.get("candidates") or []:
            if row.get("after_remote_level") == "FIELD_VERIFIED_LIVESTOCK_WATER":
                ok = False
                reasons.append(f"{summary['parcel_id']}:REMOTE_PRODUCED_FIELD_VERIFIED")
            if (
                row.get("after_remote_level") == "REMOTELY_SUPPORTED_CANDIDATE"
                and not row.get("provenance_complete")
            ):
                ok = False
                reasons.append(f"{summary['parcel_id']}:REMOTE_WITHOUT_PROVENANCE")
    return {"passed": ok, "reasons": reasons}


def main() -> None:
    summaries = []
    for cfg in PARCELS:
        print(f"Processing {cfg['parcel_id']} ...", flush=True)
        summary = process_parcel(cfg)
        summaries.append(summary)
        print(
            json.dumps(
                {
                    "parcel_id": summary["parcel_id"],
                    "available": summary["counts"]["available"],
                    "sampled": summary["counts"]["sampled"],
                    "level_histogram": summary["level_histogram"],
                    "data_path_failures": len(summary["data_path_failures"]),
                    "provenance_gate_passed": summary["provenance_gate_passed"],
                },
                indent=2,
            ),
            flush=True,
        )

    gate = collection_gate_passed(summaries)
    out_by_parcel = {cfg["parcel_id"]: cfg["out_dir"] for cfg in PARCELS}
    aggregate = {
        "collection_id": "F03_FIVE_PARCEL_REMOTE_COLLECTION",
        "as_of": AS_OF,
        "contract_version": CONTRACT_VERSION,
        "selection_method": SELECTION_METHOD_STABLE_CANDIDATE_ID_ORDER,
        "runtime_rules_changed": False,
        "ranking_effect": "NONE",
        "suitability_thresholds_added": False,
        "cow_sheep_ranking_added": False,
        "field_verified_count_total": sum(s["field_verified_count"] for s in summaries),
        "collection_gate": gate,
        "parcels": [
            {
                "parcel_id": s["parcel_id"],
                "available": s["counts"]["available"],
                "sampled": s["counts"]["sampled"],
                "MAPPED_CANDIDATE": s["counts"]["MAPPED_CANDIDATE"],
                "REMOTELY_SUPPORTED_CANDIDATE": s["counts"]["REMOTELY_SUPPORTED_CANDIDATE"],
                "FIELD_VERIFIED_LIVESTOCK_WATER": s["counts"][
                    "FIELD_VERIFIED_LIVESTOCK_WATER"
                ],
                "provenance_complete": s["counts"]["provenance_complete"],
                "data_path_failures": s["data_path_failures"],
                "conflicts": s["conflicts"],
                "parcel_factor_state_before": s["parcel_factor_state_before"],
                "parcel_factor_state_after": s["parcel_factor_state_after"],
                "result_path": str(
                    (out_by_parcel[s["parcel_id"]] / "remote_pilot_result.json").relative_to(
                        PROJECT
                    )
                ),
            }
            for s in summaries
        ],
    }
    agg_path = (
        PROJECT
        / "test-data/cross-parcel-validation/f03_five_parcel_remote_collection_summary.json"
    )
    agg_path.write_text(json.dumps(aggregate, indent=2) + "\n")
    print(
        json.dumps(
            {
                "wrote": str(agg_path.relative_to(PROJECT)),
                "collection_gate_passed": gate["passed"],
                "gate_reasons": gate["reasons"],
                "field_verified_count_total": aggregate["field_verified_count_total"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
