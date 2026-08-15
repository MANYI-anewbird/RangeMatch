"""Phase 2: Mireye-first environmental collection (post-confirmation).

CONFIRM_PARCEL → F06 → /v1/fetch(manifest) → Mireye Environmental Profile.

This path does not run the fixed F01–F08 agenda and does not feed the buyer
LLM workbench. Demo/default remains LEGACY until Gap Detector + supplements.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from rangematch.f06_derivation import derive_f06_from_geometry
from rangematch.mireye_adapter import (
    ENDPOINT_FETCH,
    MireyeAdapterError,
    assert_no_credentials,
    normalize_field,
    sanitize_for_storage,
)
from rangematch.mireye_environmental_profile import (
    load_field_manifest,
    project_mireye_environmental_profile,
)

COLLECTION_MODE_LEGACY = "LEGACY"
COLLECTION_MODE_MIREYE_FIRST = "MIREYE_FIRST"
ALLOWED_COLLECTION_MODES = frozenset(
    {COLLECTION_MODE_LEGACY, COLLECTION_MODE_MIREYE_FIRST}
)

OUTCOME_ENVIRONMENTAL_PROFILE_COMPLETED = "ENVIRONMENTAL_PROFILE_COMPLETED"
OUTCOME_ENVIRONMENTAL_PROFILE_PARTIAL = "ENVIRONMENTAL_PROFILE_PARTIAL"

FetchRequestFn = Callable[..., tuple[dict[str, Any], dict[str, Any]]]


def manifest_field_ids(manifest: Mapping[str, Any] | None = None) -> list[str]:
    doc = manifest or load_field_manifest()
    return [str(item["field_id"]) for item in doc["fields"]]


def required_field_ids(manifest: Mapping[str, Any] | None = None) -> list[str]:
    doc = manifest or load_field_manifest()
    return [str(item["field_id"]) for item in doc["fields"] if item.get("required")]


def build_mireye_fetch_body(
    *,
    lat: float,
    lng: float,
    field_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    ids = list(field_ids) if field_ids is not None else manifest_field_ids()
    return {
        "lat": float(lat),
        "lng": float(lng),
        "fields": ids,
    }


def derive_confirmed_f06(
    geometry: Mapping[str, Any],
    *,
    geometry_hash: str,
    geometry_id: str | None = None,
    geometry_reference: str | None = None,
) -> dict[str, Any]:
    """Always-on F06 core derivation bound to the confirmed geometry hash."""
    factor = derive_f06_from_geometry(
        dict(geometry),
        geometry_hash=geometry_hash,
        geometry_id=geometry_id,
        geometry_reference=geometry_reference,
    )
    return {
        "factor_id": "F06_PARCEL_CONFIGURATION",
        "role": "ALWAYS_ON_CORE_DERIVATION",
        "spatial_semantics": "PARCEL",
        "geometry_hash": geometry_hash,
        "geometry_id": geometry_id,
        "geometry_reference": geometry_reference,
        "factor": factor,
        "summary": {
            "area_m2": factor.get("area_m2"),
            "perimeter_m": factor.get("perimeter_m"),
            "compactness": factor.get("compactness"),
            "polygon_part_count": factor.get("polygon_part_count"),
            "input_quality_state": factor.get("input_quality_state"),
            "geometry_validity": factor.get("geometry_validity"),
        },
    }


def _parcel_expected_ids(manifest: Mapping[str, Any]) -> set[str]:
    return {
        str(item["field_id"])
        for item in manifest["fields"]
        if item.get("expected_spatial_semantics") == "PARCEL"
    }


def field_values_from_fetch_response(
    raw: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    confirmed_geometry_hash: str,
    default_fetched_at: str | None = None,
) -> dict[str, Any]:
    """Map a Mireye /v1/fetch body into projector field_values."""
    fields_raw = raw.get("fields") if isinstance(raw.get("fields"), Mapping) else {}
    fetched_at = default_fetched_at or raw.get("fetched_at")
    parcel_ids = _parcel_expected_ids(manifest)
    out: dict[str, Any] = {}
    for field_id in manifest_field_ids(manifest):
        if field_id not in fields_raw:
            continue
        normalized = normalize_field(
            field_id, fields_raw[field_id], default_fetched_at=fetched_at
        )
        payload: dict[str, Any] = dict(normalized)
        if field_id in parcel_ids and not _is_empty(normalized.get("value")):
            # Parcel-metric fields from Mireye are bound to the confirmed hash.
            payload["spatial_semantics"] = "PARCEL"
            payload["geometry_hash"] = confirmed_geometry_hash
        out[field_id] = payload
    return out


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def fetch_mireye_environment_fields(
    *,
    lat: float,
    lng: float,
    confirmed_geometry_hash: str,
    request_fn: FetchRequestFn,
    manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Call /v1/fetch for the frozen cattle-environment manifest.

    Never substitutes fixture data on failure. Partial field maps are returned
    with unavailable_fields listed when the transport fails or fields are absent.
    """
    doc = manifest or load_field_manifest()
    field_ids = manifest_field_ids(doc)
    body = build_mireye_fetch_body(lat=lat, lng=lng, field_ids=field_ids)
    transport: dict[str, Any] = {
        "endpoint": ENDPOINT_FETCH,
        "ok": False,
        "error_class": None,
        "http_status": None,
        "requested_field_count": len(field_ids),
    }
    try:
        raw, meta = request_fn(endpoint=ENDPOINT_FETCH, body=body)
        safe_raw = sanitize_for_storage(raw) if isinstance(raw, Mapping) else {}
        assert_no_credentials(safe_raw, label="mireye_environmental_fetch")
        transport["ok"] = bool((meta or {}).get("ok", True))
        transport["http_status"] = (meta or {}).get("http_status")
        transport["error_class"] = (meta or {}).get("error_class")
        field_values = field_values_from_fetch_response(
            safe_raw if isinstance(safe_raw, Mapping) else {},
            manifest=doc,
            confirmed_geometry_hash=confirmed_geometry_hash,
            default_fetched_at=(
                safe_raw.get("fetched_at") if isinstance(safe_raw, Mapping) else None
            ),
        )
        present = set(field_values)
        unavailable = [fid for fid in field_ids if fid not in present]
        # If the whole call failed, mark every field unavailable (no fixture fill).
        if not transport["ok"] and not field_values:
            unavailable = list(field_ids)
        return {
            "ok": bool(transport["ok"] and field_values),
            "field_values": field_values,
            "unavailable_fields": unavailable,
            "transport": transport,
            "raw_fetched_at": (
                safe_raw.get("fetched_at") if isinstance(safe_raw, Mapping) else None
            ),
            "request_body": body,
        }
    except MireyeAdapterError as exc:
        error_class = str(exc).split(":", 1)[0] or type(exc).__name__
        transport["error_class"] = error_class
        return {
            "ok": False,
            "field_values": {},
            "unavailable_fields": list(field_ids),
            "transport": transport,
            "raw_fetched_at": None,
            "request_body": body,
            "error": error_class,
        }
    except Exception as exc:  # noqa: BLE001 — collection must degrade honestly
        transport["error_class"] = type(exc).__name__
        return {
            "ok": False,
            "field_values": {},
            "unavailable_fields": list(field_ids),
            "transport": transport,
            "raw_fetched_at": None,
            "request_body": body,
            "error": type(exc).__name__,
        }


def classify_environmental_profile_outcome(
    profile: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any] | None = None,
) -> str:
    required = set(required_field_ids(manifest))
    by_id = {
        str(obs.get("field_id")): obs
        for obs in (profile.get("observations") or [])
        if isinstance(obs, Mapping)
    }
    for field_id in required:
        obs = by_id.get(field_id) or {}
        if obs.get("status") not in {"RETRIEVED", "PARTIAL"}:
            return OUTCOME_ENVIRONMENTAL_PROFILE_PARTIAL
    retrieved = int((profile.get("coverage_summary") or {}).get("retrieved_field_count") or 0)
    if retrieved <= 0:
        return OUTCOME_ENVIRONMENTAL_PROFILE_PARTIAL
    return OUTCOME_ENVIRONMENTAL_PROFILE_COMPLETED


def run_mireye_first_collection(
    *,
    run_id: str,
    geometry: Mapping[str, Any],
    parcel_resolution_id: str,
    geometry_hash: str,
    lat: float,
    lng: float,
    request_fn: FetchRequestFn,
    geometry_id: str | None = None,
    geometry_reference: str | None = None,
    built_at: str | None = None,
) -> dict[str, Any]:
    """Execute F06 + Mireye fetch + Profile for one confirmed parcel."""
    manifest = load_field_manifest()
    f06 = derive_confirmed_f06(
        geometry,
        geometry_hash=geometry_hash,
        geometry_id=geometry_id,
        geometry_reference=geometry_reference,
    )
    fetch_result = fetch_mireye_environment_fields(
        lat=lat,
        lng=lng,
        confirmed_geometry_hash=geometry_hash,
        request_fn=request_fn,
        manifest=manifest,
    )
    profile = project_mireye_environmental_profile(
        run_id=run_id,
        parcel_ref={
            "parcel_resolution_id": parcel_resolution_id,
            "geometry_hash": geometry_hash,
            "confirmed": True,
        },
        field_values=fetch_result.get("field_values") or {},
        fetched_at=fetch_result.get("raw_fetched_at"),
        unavailable_fields=fetch_result.get("unavailable_fields") or [],
        built_at=built_at,
        manifest=manifest,
        validate=True,
    )
    env_outcome = classify_environmental_profile_outcome(profile, manifest=manifest)
    return {
        "f06": f06,
        "mireye_environmental_profile": profile,
        "environmental_profile_outcome": env_outcome,
        "fetch": {
            "ok": bool(fetch_result.get("ok")),
            "transport": fetch_result.get("transport"),
            "unavailable_field_count": len(fetch_result.get("unavailable_fields") or []),
            "error": fetch_result.get("error"),
            "requested_field_ids": list((fetch_result.get("request_body") or {}).get("fields") or []),
        },
        "agenda_ran_f01_f08": False,
        "collection_mode": COLLECTION_MODE_MIREYE_FIRST,
    }
