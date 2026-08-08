"""Minimal geometry replacement for demo reusability validation.

This path proves the CPER fixture is not a hard-coded singleton input. It does
not fetch new remote Factor data. Parcel-derived evidence tied to the previous
geometry is invalidated so provenance and hashes cannot silently drift.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


def geometry_file_sha256(geometry_path: str | Path) -> str:
    payload = Path(geometry_path).read_bytes()
    return hashlib.sha256(payload).hexdigest()


def _geometry_id_from_file(geometry_path: Path, geojson: dict[str, Any]) -> str:
    features = geojson.get("features") or []
    if features:
        feature = features[0]
        feature_id = feature.get("id")
        if feature_id:
            return str(feature_id)
        props = feature.get("properties") or {}
        if props.get("geometry_id"):
            return str(props["geometry_id"])
    return geometry_path.stem


def _invalidate_factor(
    factor: dict[str, Any],
    *,
    new_geometry_hash: str,
    factor_id: str | None = None,
) -> dict[str, Any]:
    invalidated = {
        "input_quality_state": "MISSING",
        "geometry_replacement_status": "EVIDENCE_INVALIDATED",
        "geometry_hash": new_geometry_hash,
        "limitations": [
            "Parcel geometry changed. Previous parcel-derived evidence was invalidated.",
            "Re-run approved data collection before using this Factor as screening evidence.",
        ],
        "unknowns": [
            "Factor evidence is unknown until regenerated for the replacement geometry."
        ],
    }
    if factor.get("derivation_spec"):
        invalidated["derivation_spec"] = factor["derivation_spec"]
    if factor_id == "F03_LIVESTOCK_WATER" or factor.get("evidence_contract"):
        invalidated["f03_evidence_relink_required"] = True
        invalidated["field_verified_count"] = 0
        invalidated["verified_livestock_water_system_count"] = 0
        invalidated["limitations"].append(
            "F03 candidate, remote, and field/operator evidence must be re-linked or "
            "recollected for the replacement geometry; prior verification levels are void."
        )
    return invalidated


def replace_geometry(
    profile: dict[str, Any],
    geometry_path: str | Path,
    *,
    geometry_reference: str | None = None,
) -> dict[str, Any]:
    """Return a new Land Profile bound to a replacement geometry."""
    path = Path(geometry_path)
    geojson = json.loads(path.read_text())
    new_hash = geometry_file_sha256(path)
    new_profile = deepcopy(profile)

    old_geometry_id = new_profile.get("geometry_id")
    old_reference = new_profile.get("geometry_reference")
    old_hash = new_profile.get("geometry_hash")

    new_profile["geometry_id"] = _geometry_id_from_file(path, geojson)
    new_profile["geometry_reference"] = geometry_reference or str(path)
    new_profile["geometry_hash"] = new_hash
    new_profile["geometry_replacement"] = {
        "replaced_geometry_id": old_geometry_id,
        "replaced_geometry_reference": old_reference,
        "replaced_geometry_hash": old_hash,
        "replacement_geometry_hash": new_hash,
        "factor_evidence_invalidated": True,
        "live_data_refetch_performed": False,
    }
    new_profile["supported_use"] = new_profile.get(
        "supported_use", "ENGINEERING_VALIDATION_ONLY"
    )

    factors = new_profile.get("factors") or {}
    refreshed_factors = {}
    for factor_id, factor in factors.items():
        refreshed_factors[factor_id] = _invalidate_factor(
            factor if isinstance(factor, dict) else {},
            new_geometry_hash=new_hash,
            factor_id=factor_id,
        )
    new_profile["factors"] = refreshed_factors

    unknowns = list(new_profile.get("unknowns") or [])
    unknowns.append(
        "Geometry was replaced; F01–F08 parcel-derived evidence must be regenerated."
    )
    new_profile["unknowns"] = sorted(set(unknowns))
    return new_profile


def write_replaced_profile(
    profile_path: str | Path,
    geometry_path: str | Path,
    output_path: str | Path,
    *,
    geometry_reference: str | None = None,
) -> dict[str, Any]:
    profile = json.loads(Path(profile_path).read_text())
    replaced = replace_geometry(
        profile,
        geometry_path,
        geometry_reference=geometry_reference,
    )
    Path(output_path).write_text(json.dumps(replaced, indent=2) + "\n")
    return replaced
