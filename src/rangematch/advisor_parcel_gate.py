"""Advisor gate: full investigation requires PARCEL_CONFIRMED.

Reuses parcel_resolution confirm records — does not invent a parallel schema.
Contract: docs/ADVISOR_PARCEL_CONFIRMATION_GATE.md
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping
from uuid import uuid4

from rangematch.mireye_parcel_resolver import ADAPTER_ID as MIREYE_ADAPTER_ID
from rangematch.mireye_parcel_resolver import MireyeLookupMapping
from rangematch.parcel_resolution import (
    ADAPTER_VERSION,
    SCHEMA_VERSION,
    compute_geometry_hash,
    planner_parcel_input,
    validate_parcel_boundary_geometry,
)
from rangematch.parcel_resolution_store import get_parcel_resolution_store


class AdvisorParcelGateError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def require_confirmed_parcel(resolution: Mapping[str, Any]) -> dict[str, Any]:
    """Return Planner-ready binding or raise. Only PARCEL_CONFIRMED passes."""
    if resolution.get("status") != "PARCEL_CONFIRMED":
        raise AdvisorParcelGateError(
            "PARCEL_NOT_CONFIRMED",
            f"full Advisor investigation requires PARCEL_CONFIRMED; "
            f"got {resolution.get('status')}",
        )
    selection = resolution.get("selection") or {}
    method = selection.get("confirmation_method")
    if method != "USER_BOUNDARY_CONFIRMATION":
        raise AdvisorParcelGateError(
            "CONFIRMATION_METHOD_REQUIRED",
            "confirmation_method must be USER_BOUNDARY_CONFIRMATION",
        )
    if not selection.get("confirmed_at") or not selection.get("selected_candidate_id"):
        raise AdvisorParcelGateError(
            "CONFIRMATION_RECORD_INCOMPLETE",
            "selection must include selected_candidate_id and confirmed_at",
        )
    binding = planner_parcel_input(resolution)
    confirmed = resolution["confirmed_parcel"]
    provenance = dict(resolution.get("provenance") or {})
    return {
        "parcel_resolution_id": resolution.get("resolution_id"),
        "parcel_geometry": binding["parcel_geometry"],
        "geometry_hash": binding["geometry_hash"],
        "geometry_reference": binding["geometry_reference"],
        "geometry_id": binding.get("geometry_id")
        or selection.get("selected_candidate_id"),
        "source_crs": binding["source_crs"],
        "selected_candidate_id": selection.get("selected_candidate_id"),
        "confirmed_at": selection.get("confirmed_at"),
        "confirmation_method": method,
        "polygon_source": provenance.get("source")
        or (confirmed.get("provenance") or {}).get("source"),
        "provider": provenance.get("provider")
        or (confirmed.get("provenance") or {}).get("provider"),
        "location_resolved": True,
        "parcel_geometry_confirmed": True,
    }


def _validate_candidate(cand: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(dict(cand))
    errs = validate_parcel_boundary_geometry(
        out.get("parcel_geometry"),
        source_crs=str(out.get("source_crs") or ""),
    )
    out["validation_status"] = "VALID" if not errs else "INVALID"
    out["validation_errors"] = list(errs)
    if not errs and out.get("parcel_geometry"):
        out["geometry_hash"] = compute_geometry_hash(out["parcel_geometry"])
    return out


def stage_mireye_mapping_for_confirmation(
    *,
    address: str,
    mapping: MireyeLookupMapping,
    lookup_view: Mapping[str, Any] | None = None,
    store: Any | None = None,
    input_kind: str = "ADDRESS",
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict[str, Any]:
    """Persist a resolution record awaiting user selection/boundary confirmation."""
    candidates = [_validate_candidate(c) for c in list(mapping.candidates or [])]
    valid = [c for c in candidates if c.get("validation_status") == "VALID"]
    if not valid:
        raise AdvisorParcelGateError(
            "NO_CONFIRMABLE_POLYGON",
            "Mireye mapping has no valid parcel polygon to confirm",
        )

    resolution_id = f"pr_advisor_{uuid4().hex[:16]}"
    if len(valid) > 1:
        status = "NEEDS_USER_SELECTION"
        selection = {
            "selected_candidate_id": None,
            "confirmed_at": None,
            "confirmation_method": "PENDING",
        }
    else:
        status = "NEEDS_BOUNDARY_CONFIRMATION"
        selection = {
            "selected_candidate_id": valid[0]["candidate_id"],
            "confirmed_at": None,
            "confirmation_method": "PENDING",
        }

    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "resolution_id": resolution_id,
        "adapter_id": MIREYE_ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "provider_mode": "LIVE",
        "status": status,
        "scenario_id": None,
        "input": {
            "input_kind": "COORDINATE" if str(input_kind).upper() == "COORDINATE" else "ADDRESS",
            "raw_address": address,
            "normalized_address": mapping.normalized_address or address,
            "latitude": latitude,
            "longitude": longitude,
        },
        "geocode": {
            "status": mapping.geocode_status,
            "point": mapping.geocode_point,
            "confidence": mapping.confidence,
            "provider": "Mireye",
            "request_id": mapping.request_id,
            "retrieved_at": mapping.retrieved_at,
            "accuracy": mapping.accuracy,
            "accuracy_type": mapping.accuracy_type,
            "match_type": mapping.match_type,
            "normalized_address": mapping.normalized_address,
            "limitations": list(mapping.limitations or []),
        },
        "candidates": candidates,
        "selection": selection,
        "confirmed_parcel": None,
        "evidence_invalidation_required": False,
        "previous_geometry_hash": None,
        "provenance": {
            "source": (valid[0].get("provenance") or {}).get("source"),
            "provider": "Mireye",
            "request_id": mapping.request_id,
            "reference_id": valid[0].get("candidate_id"),
            "retrieved_at": mapping.retrieved_at,
            "source_crs": valid[0].get("source_crs"),
            "normalized_crs": "EPSG:4326",
            "confidence": mapping.confidence,
            "status": status,
            "mireye_disposition": mapping.disposition,
            "mireye_lookup": dict(lookup_view or {}),
        },
        "limitations": list(mapping.limitations or [])
        + [
            "Advisor staged this resolution after Mireye-first lookup.",
            "Boundary is not confirmed until USER_BOUNDARY_CONFIRMATION.",
        ],
        "errors": [],
    }
    active_store = store if store is not None else get_parcel_resolution_store()
    active_store.put(record)
    return deepcopy(record)


def load_confirmed_binding(parcel_resolution_id: str) -> dict[str, Any]:
    """Load a stored resolution and require PARCEL_CONFIRMED for Advisor continue."""
    record = get_parcel_resolution_store().get(parcel_resolution_id)
    if record is None:
        raise AdvisorParcelGateError(
            "RESOLUTION_NOT_FOUND",
            f"parcel_resolution_id not found: {parcel_resolution_id}",
        )
    return require_confirmed_parcel(record)
