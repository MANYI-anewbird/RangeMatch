#!/usr/bin/env python3
"""Provenance-complete F03 remote-only verification pilot (CPER).

Authorized scope:
  MAPPED_CANDIDATE → remote enrichment → REMOTELY_SUPPORTED or remains MAPPED

Presence confirmation for REMOTELY_SUPPORTED requires a reproducible imagery
artifact with complete provenance. Unverifiable prose notes are rejected and
the candidate remains MAPPED_CANDIDATE / ENGINEERING_VALIDATION_ONLY.

Does NOT manufacture FIELD_VERIFIED_LIVESTOCK_WATER.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from rangematch.f03_verification import (  # noqa: E402
    CONTRACT_VERSION,
    apply_remote_enrichment,
    build_mapped_candidate_from_nhd,
    factor_input_quality_from_levels,
    remote_presence_provenance_complete,
)

INVENTORY = (
    PROJECT
    / "test-data/live-results/cper/cper_f03_candidate_distance_result_2026-08-07.json"
)
PARCEL_GEO = PROJECT / "test-data/engineering_test_geometry_cper_001.geojson"
OUT_DIR = PROJECT / "test-data/cross-parcel-validation/XPV_CPER_001/f03_remote_pilot"
ARTIFACT_DIR = OUT_DIR / "artifacts"

# USDA FSA NAIP 2023 item retrieved via Microsoft Planetary Computer STAC.
NAIP_STAC_ITEM_ID = "co_m_4010410_ne_13_030_20230925_20240104"
NAIP_STAC_URL = (
    "https://planetarycomputer.microsoft.com/api/stac/v1/collections/naip/items/"
    + NAIP_STAC_ITEM_ID
)
NAIP_CROP = ARTIFACT_DIR / "naip_2023_flowline_156614135_crop.tif"
NAIP_STAC_JSON = ARTIFACT_DIR / f"naip_stac_item_{NAIP_STAC_ITEM_ID}.json"
TARGET_FEATURE_ID = "156614135"

AS_OF = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
REVIEW_DATE = AS_OF[:10]
REVIEWER_OR_ADAPTER_ID = "rangematch.f03_remote_pilot/provenance_v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_pilot_candidates(inventory: list[dict]) -> list[dict]:
    """Pick one intermittent stream, one ephemeral stream, one waterbody."""
    by_role = {"intermittent": None, "ephemeral": None, "waterbody": None}
    for row in inventory:
        fcode = row.get("fcode")
        layer = row.get("source_layer")
        try:
            code = int(fcode) if fcode is not None else None
        except (TypeError, ValueError):
            code = None
        if (
            by_role["intermittent"] is None
            and code == 46003
            and str(row.get("source_feature_id")) == TARGET_FEATURE_ID
        ):
            by_role["intermittent"] = row
        elif by_role["intermittent"] is None and code == 46003:
            by_role["intermittent"] = row
        elif by_role["ephemeral"] is None and code == 46007:
            by_role["ephemeral"] = row
        elif by_role["waterbody"] is None and layer == "NHDWaterbody":
            by_role["waterbody"] = row
    # Prefer exact target feature when present.
    for row in inventory:
        if str(row.get("source_feature_id")) == TARGET_FEATURE_ID:
            by_role["intermittent"] = row
            break
    selected = [row for row in by_role.values() if row is not None]
    if len(selected) < 3:
        selected = inventory[:3]
    return selected


def build_naip_presence_package(candidate: dict, parcel_hash: str) -> dict | None:
    """Build provenance-complete NAIP presence package, or None if artifacts missing."""
    if not NAIP_CROP.exists() or not NAIP_STAC_JSON.exists():
        return None
    artifact_hash = sha256_file(NAIP_CROP)
    stac_hash = sha256_file(NAIP_STAC_JSON)
    stac = json.loads(NAIP_STAC_JSON.read_text())
    acquisition = (stac.get("properties") or {}).get("datetime") or "2023-09-25T16:00:00Z"
    provenance = {
        "provider": "USDA Farm Service Agency (via Microsoft Planetary Computer STAC)",
        "product_name": "NAIP 2023 Colorado 30 cm orthoimagery",
        "source_url": NAIP_STAC_URL,
        "item_id_or_artifact_reference": (
            f"stac:naip/{NAIP_STAC_ITEM_ID}; "
            f"local_artifact={NAIP_CROP.relative_to(PROJECT)}; "
            f"stac_fixture={NAIP_STAC_JSON.relative_to(PROJECT)}"
        ),
        "imagery_acquisition_date": acquisition[:10],
        "review_date": REVIEW_DATE,
        "reviewer_or_adapter_id": REVIEWER_OR_ADAPTER_ID,
        "candidate_geometry_hash": candidate.get("geometry_hash"),
        "parcel_geometry_hash": parcel_hash,
        "response_or_artifact_hash": artifact_hash,
        "supporting_artifact_hashes": {
            "naip_crop_geotiff": artifact_hash,
            "stac_item_json": stac_hash,
        },
        "supported_claim": (
            "Physical channel/corridor visible in 2023-09-25 NAIP imagery within "
            "the exported bbox covering NHDPlus HR flowline "
            f"{candidate.get('source_feature_id')}."
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
            "Channel visibility is not proof of flowing water on the acquisition date.",
            "Single NAIP date does not establish perennial/intermittent class by itself; "
            "seasonal class in this pilot still comes from NHD FCode 46003.",
            "SAS-signed COG URLs expire; reproducible package is the local GeoTIFF + STAC JSON.",
        ],
        "freshness_status": "ACQUISITION_2023-09-25_WITHIN_THREE_YEARS_OF_REVIEW",
        "bbox_wgs84_export": [-104.77002, 40.8199, -104.7609, 40.82055],
        "stac_item_id": NAIP_STAC_ITEM_ID,
        "producer_url": (
            "https://www.fsa.usda.gov/programs-and-services/aerial-photography/"
            "imagery-programs/naip-imagery/"
        ),
    }
    gate = remote_presence_provenance_complete(provenance)
    if not gate["complete"]:
        return None
    return {
        "source": "imagery",
        "observation_date": provenance["imagery_acquisition_date"],
        "review_note": (
            "Deterministic remote pilot: USDA NAIP 2023 STAC item retrieved via "
            "Microsoft Planetary Computer; local GeoTIFF crop hashed and retained."
        ),
        "evidence_source_ids": [
            "USDA_FSA_NAIP_2023",
            "MICROSOFT_PLANETARY_COMPUTER_STAC",
            "USGS_NHDPLUS_HR",
        ],
        "provenance": provenance,
    }


def main() -> None:
    payload = json.loads(INVENTORY.read_text())
    inventory = payload.get("candidate_inventory") or payload.get("candidates") or []
    selected = select_pilot_candidates(inventory)
    parcel_hash = sha256_file(PARCEL_GEO)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    provenance_gate_passed = False
    for raw in selected:
        mapped = build_mapped_candidate_from_nhd({**raw, "as_of": AS_OF})
        reviewed = None
        if str(raw.get("source_feature_id")) == TARGET_FEATURE_ID:
            reviewed = build_naip_presence_package(raw, parcel_hash)
            if reviewed is None:
                # Explicit fall-back: unverifiable note must not retain REMOTELY_SUPPORTED.
                reviewed = {
                    "review_note": "Artifacts missing; cannot form provenance-complete package.",
                    "provenance": {},
                }

        enriched = apply_remote_enrichment(
            mapped,
            seasonal_from_fcode=True,
            reviewed_presence=reviewed,
        )
        level = enriched["promotion_evaluation"]["verification_level"]
        assert level != "FIELD_VERIFIED_LIVESTOCK_WATER"
        if level == "REMOTELY_SUPPORTED_CANDIDATE":
            provenance_gate_passed = True

        presence = enriched["dimensions"]["physical_presence"]
        results.append(
            {
                "candidate_id": enriched.get("candidate_id"),
                "source_layer": enriched.get("source_layer"),
                "source_feature_id": enriched.get("source_feature_id"),
                "fcode": enriched.get("fcode"),
                "gnis_name": enriched.get("gnis_name"),
                "candidate_geometry_hash": raw.get("geometry_hash"),
                "baseline_level": "MAPPED_CANDIDATE",
                "after_remote_level": level,
                "reason_codes": enriched["promotion_evaluation"]["reason_codes"],
                "seasonal_reliability": enriched["dimensions"]["seasonal_reliability"],
                "physical_presence": presence,
                "evidence_use_limit": enriched.get("evidence_use_limit"),
                "provenance_complete": remote_presence_provenance_complete(
                    presence.get("provenance")
                )["complete"]
                if presence.get("provenance")
                else False,
                "reviewed_presence_attempted": reviewed is not None,
                "field_verified": False,
            }
        )

    levels = [row["after_remote_level"] for row in results]
    summary = {
        "pilot_id": "F03_REMOTE_ONLY_PILOT_CPER_001",
        "pilot_version": "provenance_v1",
        "contract_version": CONTRACT_VERSION,
        "adapter_authorization": "APPROVED_FOR_SMALL_SCALE_PILOT",
        "parcel_id": "XPV_CPER_001",
        "parcel_geometry_hash": parcel_hash,
        "as_of": AS_OF,
        "scope": "MAPPED_CANDIDATE → remote enrichment → REMOTELY_SUPPORTED|MAPPED",
        "evidence_source_used": {
            "provider": "USDA Farm Service Agency",
            "product": "NAIP 2023 30 cm",
            "access_path": "Microsoft Planetary Computer STAC (naip collection)",
            "stac_item_id": NAIP_STAC_ITEM_ID,
            "stac_url": NAIP_STAC_URL,
            "local_crop_artifact": str(NAIP_CROP.relative_to(PROJECT)),
            "imagery_acquisition_date": "2023-09-25",
        },
        "provenance_gate_passed": provenance_gate_passed,
        "field_verified_manufactured": False,
        "field_verified_count": 0,
        "candidate_count": len(results),
        "level_histogram": {level: levels.count(level) for level in sorted(set(levels))},
        "parcel_input_quality_state": factor_input_quality_from_levels(levels),
        "runtime_rules_changed": False,
        "suitability_thresholds_added": False,
        "cow_sheep_ranking_added": False,
        "ranking_effect": "NONE",
        "candidates": results,
        "next_gate": (
            "CPER single-parcel pilot retained for targeted reproduction. "
            "Five-parcel collection uses scripts/run_f03_five_parcel_remote_collection.py "
            "with STABLE_CANDIDATE_ID_ORDER_MAX_3. "
            "Do not attempt FIELD_VERIFIED without real field/operator evidence."
        ),
    }

    out_path = OUT_DIR / "remote_pilot_result.json"
    out_path.write_text(json.dumps(summary, indent=2) + "\n")

    # Persist a standalone provenance package for the promoted candidate.
    for row in results:
        if row["after_remote_level"] == "REMOTELY_SUPPORTED_CANDIDATE":
            prov_path = OUT_DIR / "presence_provenance_156614135.json"
            prov_path.write_text(
                json.dumps(row["physical_presence"].get("provenance") or {}, indent=2) + "\n"
            )

    print(
        json.dumps(
            {
                "wrote": str(out_path.relative_to(PROJECT)),
                "level_histogram": summary["level_histogram"],
                "field_verified_count": 0,
                "parcel_input_quality_state": summary["parcel_input_quality_state"],
                "provenance_gate_passed": provenance_gate_passed,
                "evidence_source": summary["evidence_source_used"]["stac_item_id"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
