"""Unified Mireye Context Adapter — normalize raw Mireye responses.

Produces PROPERTY_DILIGENCE_CONTEXT, POINT_LAND_CONTEXT, and
POINT_HAZARD_CONTEXT envelopes. Does not write Factor Land Facts or
change MatchResult signals.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

from rangematch.unified_output import canonical_json_bytes, sha256_canonical
from rangematch.mireye_transport import (
    DEFAULT_BYPASS_ENV_PROXY,
    OFFICIAL_MIREYE_HTTPS_ORIGIN,
    classify_tls_failure,
    diagnose_mireye_transport,
    mireye_urlopen,
    probe_plaintext_http_on_443,
    redact_transport_message,
    report_proxy_environment,
    validate_mireye_base_url,
)

ADAPTER_ID = "MIREYE_UNIFIED_CONTEXT_ADAPTER"
ADAPTER_VERSION = "0.1.0"

CONTEXT_PROPERTY = "PROPERTY_DILIGENCE_CONTEXT"
CONTEXT_LAND = "POINT_LAND_CONTEXT"
CONTEXT_HAZARD = "POINT_HAZARD_CONTEXT"
SUPPORTED_CONTEXT_TYPES = frozenset({CONTEXT_PROPERTY, CONTEXT_LAND, CONTEXT_HAZARD})

ENDPOINT_LOOKUP = "/v1/lookup"
ENDPOINT_FETCH = "/v1/fetch"

POINT_ROLES = frozenset(
    {"PARCEL_CENTROID_QA", "USER_SUPPLIED_POINT", "ADDRESS_RESOLVED_POINT"}
)

PERMITTED_USES = (
    "POINT_QA",
    "FAST_CONTEXT",
    "CANDIDATE_DISCOVERY",
    "DILIGENCE_TRIGGER",
    "JURISDICTION_CONTEXT",
)

DEFAULT_LIMITATIONS = (
    "canonical_for_parcel_facts=false",
    "point_or_diligence_context_only",
    "do_not_average_with_parcel_land_facts",
    "do_not_promote_to_factor_land_facts",
    "legal_title_not_verified",
    "zoning_legality_not_confirmed",
)

# Reviewed field→factor refs (mirrors docs/MIREYE_FIELD_USAGE_REGISTRY.yaml).
FACTOR_FIELD_USAGE: dict[str, tuple[tuple[str, str], ...]] = {
    "slope_degrees": (("F01_TOPOGRAPHY", "POINT_QA"),),
    "elevation": (("F01_TOPOGRAPHY", "POINT_QA"),),
    "aspect_degrees": (("F01_TOPOGRAPHY", "POINT_QA"),),
    "aspect_cardinal": (("F01_TOPOGRAPHY", "POINT_QA"),),
    "lcms_class": (
        ("F02_HERBACEOUS_RESOURCE", "FAST_CONTEXT"),
        ("F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE", "POINT_QA"),
    ),
    "land_use_class": (("F02_HERBACEOUS_RESOURCE", "FAST_CONTEXT"),),
    "intersects_nhd_area": (("F03_LIVESTOCK_WATER", "CANDIDATE_DISCOVERY"),),
    "nearest_flowline_name": (("F03_LIVESTOCK_WATER", "CANDIDATE_DISCOVERY"),),
    "nearest_waterbody_name": (("F03_LIVESTOCK_WATER", "CANDIDATE_DISCOVERY"),),
    "nearest_groundwater_well_depth_to_water_m": (
        ("F03_LIVESTOCK_WATER", "CANDIDATE_DISCOVERY"),
    ),
    "nearest_usgs_gage_name": (("F03_LIVESTOCK_WATER", "CANDIDATE_DISCOVERY"),),
    "nearest_usgs_gage_distance_m": (("F03_LIVESTOCK_WATER", "CANDIDATE_DISCOVERY"),),
    "nearest_usgs_gage_daily_discharge_cfs": (
        ("F03_LIVESTOCK_WATER", "CANDIDATE_DISCOVERY"),
    ),
    "surface_water_permanence_pct": (("F03_LIVESTOCK_WATER", "CANDIDATE_DISCOVERY"),),
    "soil_drainage_class": (("F04_SOIL_WETNESS_ECOLOGICAL_SITE", "POINT_QA"),),
    "soil_hydrologic_group": (("F04_SOIL_WETNESS_ECOLOGICAL_SITE", "POINT_QA"),),
    "soil_map_unit_name": (("F04_SOIL_WETNESS_ECOLOGICAL_SITE", "POINT_QA"),),
    "soil_available_water_capacity": (("F04_SOIL_WETNESS_ECOLOGICAL_SITE", "POINT_QA"),),
    "soil_ponding_frequency_class": (("F04_SOIL_WETNESS_ECOLOGICAL_SITE", "POINT_QA"),),
    "soil_restrictive_layer_depth_cm": (
        ("F04_SOIL_WETNESS_ECOLOGICAL_SITE", "POINT_QA"),
    ),
    "soil_restrictive_layer_kind": (("F04_SOIL_WETNESS_ECOLOGICAL_SITE", "POINT_QA"),),
    "drought_category": (("F05_CLIMATE_DROUGHT_EXPOSURE", "POINT_QA"),),
    "mean_annual_dry_bulb_temperature_degc": (
        ("F05_CLIMATE_DROUGHT_EXPOSURE", "POINT_QA"),
    ),
    "days_above_32c_annual_count": (("F05_CLIMATE_DROUGHT_EXPOSURE", "FAST_CONTEXT"),),
    "tree_canopy_pct": (("F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE", "POINT_QA"),),
}

LAND_ADDITIONAL_FIELDS = ("lcms_class", "land_use_class")
HAZARD_ADDITIONAL_FIELDS = ("tree_canopy_pct", "ndvi_current")
FEMA_RELATED_FIELDS = frozenset(
    {
        "flood_zone",
        "within_floodplain_polygon",
        "fema_flood_zone",
        "nfhl_flood_zone",
    }
)

_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|authorization|password|client_secret|access_token|refresh_token)",
    re.IGNORECASE,
)
# Match credential-shaped values only — not adapter context_id prefixes (mireye_<hash>).
_SECRET_VALUE_RE = re.compile(
    r"(?i)(\bbearer\s+[a-z0-9._\-]{8,}\b|\bsk-[a-z0-9]{16,}\b|"
    r"\bmireye_(?:live|secret|key|tok)_[a-z0-9_\-]{8,}\b|"
    r"https?://[^/\s]+:[^/@\s]+@)"
)


class MireyeAdapterError(ValueError):
    """Fail-closed adapter error."""


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sanitize_for_storage(value: Any) -> Any:
    """Remove credential-like keys/values from structures destined for disk/logs."""
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_s = str(key)
            if _SECRET_KEY_RE.search(key_s):
                continue
            out[key_s] = sanitize_for_storage(item)
        return out
    if isinstance(value, list):
        return [sanitize_for_storage(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_for_storage(item) for item in value]
    if isinstance(value, str):
        return _SECRET_VALUE_RE.sub("[REDACTED]", value)
    return value


def assert_no_credentials(payload: Any, *, label: str = "payload") -> None:
    """Fail if credential-shaped keys/values appear in stored artifacts."""
    if isinstance(payload, Mapping):
        for key in payload:
            if _SECRET_KEY_RE.search(str(key)):
                raise MireyeAdapterError(f"credentials_detected_in_{label}")
        text = json.dumps(payload, ensure_ascii=False)
    else:
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    # Key-like JSON properties with non-empty secret values.
    if re.search(
        r'(?i)"(api[_-]?key|authorization|password|client_secret|access_token|refresh_token)"\s*:\s*"[^"]+"',
        text,
    ):
        raise MireyeAdapterError(f"credentials_detected_in_{label}")
    if _SECRET_VALUE_RE.search(text):
        raise MireyeAdapterError(f"credentials_detected_in_{label}")


def context_spec(context_type: str) -> dict[str, Any]:
    if context_type == CONTEXT_PROPERTY:
        return {
            "endpoint": ENDPOINT_LOOKUP,
            "preset": None,
            "explicitly_requested_fields": [],
        }
    if context_type == CONTEXT_LAND:
        return {
            "endpoint": ENDPOINT_FETCH,
            "preset": "terrain",
            "explicitly_requested_fields": list(LAND_ADDITIONAL_FIELDS),
        }
    if context_type == CONTEXT_HAZARD:
        return {
            "endpoint": ENDPOINT_FETCH,
            "preset": "flood_risk",
            "explicitly_requested_fields": list(HAZARD_ADDITIONAL_FIELDS),
        }
    raise MireyeAdapterError(f"unsupported_context_type:{context_type}")


def build_request_record(
    *,
    context_type: str,
    requested_location: Mapping[str, Any],
    endpoint: str | None = None,
    preset: str | None = None,
    explicitly_requested_fields: Sequence[str] | None = None,
) -> dict[str, Any]:
    spec = context_spec(context_type)
    record = {
        "endpoint": endpoint if endpoint is not None else spec["endpoint"],
        "preset": preset if preset is not None else spec["preset"],
        "explicitly_requested_fields": list(
            explicitly_requested_fields
            if explicitly_requested_fields is not None
            else spec["explicitly_requested_fields"]
        ),
        "requested_location": sanitize_for_storage(dict(requested_location)),
    }
    record["request_hash"] = sha256_canonical(record)
    return record


def _normalize_disposition(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip().upper().replace("-", "_")
    aliases = {
        "RESOLVED": "RESOLVED",
        "CLARIFY": "CLARIFY",
        "NO_MATCH": "NO_MATCH",
        "NOMATCH": "NO_MATCH",
    }
    if text not in aliases:
        raise MireyeAdapterError(f"invalid_lookup_disposition:{raw}")
    return aliases[text]


def _field_blob_hash(field_id: str, raw_field: Any) -> str:
    return sha256_canonical({"field_id": field_id, "raw": sanitize_for_storage(raw_field)})


def normalize_field(field_id: str, raw_field: Any, *, default_fetched_at: str | None) -> dict[str, Any]:
    """Preserve Mireye values as-is; do not reinterpret units or convert nulls."""
    if raw_field is None:
        raw_obj: dict[str, Any] = {"value": None}
    elif isinstance(raw_field, Mapping):
        raw_obj = dict(raw_field)
    else:
        # Scalar returned without envelope — wrap without converting.
        raw_obj = {"value": raw_field}

    return {
        "field_id": field_id,
        "value": raw_obj.get("value", None),
        "unit": raw_obj.get("unit", None),
        "source": raw_obj.get("source", None),
        "source_url": raw_obj.get("source_url", None),
        "confidence": raw_obj.get("confidence", None),
        "dataset_vintage": raw_obj.get("dataset_vintage", None),
        "fetched_at": raw_obj.get("fetched_at", default_fetched_at),
        "ttl_seconds": raw_obj.get("ttl_seconds", None),
        "notes": raw_obj.get("notes", None),
        "raw_field_hash": _field_blob_hash(field_id, raw_obj),
    }


def _failure_hash(payload: Mapping[str, Any]) -> str:
    return sha256_canonical(sanitize_for_storage(dict(payload)))


def normalize_partial_failure(raw: Any, *, fallback_field_id: str | None = None) -> dict[str, Any]:
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raw = {"message": str(raw)}
    field_id = raw.get("field_id") or raw.get("field") or fallback_field_id
    source = raw.get("source")
    error_code = raw.get("error_code") or raw.get("code") or raw.get("status")
    message = raw.get("message") or raw.get("error") or raw.get("detail")
    retryable = bool(raw.get("retryable", False))
    body = {
        "field_id": field_id,
        "source": source,
        "error_code": error_code,
        "message": message,
        "retryable": retryable,
        "normalized_effect": "UNKNOWN",
        "raw_failure_hash": _failure_hash(
            {
                "field_id": field_id,
                "source": source,
                "error_code": error_code,
                "message": message,
                "retryable": retryable,
                "raw": dict(raw),
            }
        ),
    }
    return body


def _collect_field_status_failures(
    fields_raw: Mapping[str, Any],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for field_id, raw_field in fields_raw.items():
        if not isinstance(raw_field, Mapping):
            continue
        status = str(raw_field.get("status") or "").lower()
        if status in {"", "ok", "absent"}:
            # Preserve null/"absent" as field values; FEMA null+error handled below.
            if field_id in FEMA_RELATED_FIELDS and raw_field.get("value") is None:
                if status in {"error", "failed", "timeout", "unavailable"} or raw_field.get(
                    "error"
                ):
                    failures.append(
                        normalize_partial_failure(
                            {
                                "field_id": field_id,
                                "source": raw_field.get("source"),
                                "error_code": raw_field.get("error_code")
                                or raw_field.get("status")
                                or "FEMA_NULL_OR_PARTIAL",
                                "message": raw_field.get("message")
                                or raw_field.get("error")
                                or "FEMA-related field null/partial",
                                "retryable": bool(raw_field.get("retryable", True)),
                            },
                            fallback_field_id=field_id,
                        )
                    )
            continue
        if status in {"error", "failed", "timeout", "unavailable", "partial"}:
            failures.append(
                normalize_partial_failure(
                    {
                        "field_id": field_id,
                        "source": raw_field.get("source"),
                        "error_code": raw_field.get("error_code") or status.upper(),
                        "message": raw_field.get("message")
                        or raw_field.get("error")
                        or f"field status={status}",
                        "retryable": bool(raw_field.get("retryable", status == "timeout")),
                    },
                    fallback_field_id=field_id,
                )
            )
        elif field_id in FEMA_RELATED_FIELDS and raw_field.get("value") is None:
            failures.append(
                normalize_partial_failure(
                    {
                        "field_id": field_id,
                        "source": raw_field.get("source"),
                        "error_code": raw_field.get("error_code") or "FEMA_NULL_OR_PARTIAL",
                        "message": raw_field.get("message")
                        or "FEMA-related field returned null",
                        "retryable": bool(raw_field.get("retryable", True)),
                    },
                    fallback_field_id=field_id,
                )
            )
    return failures


def build_factor_usage_refs(context_id: str, fields: Mapping[str, Any]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for field_id in sorted(fields):
        for factor_id, use in FACTOR_FIELD_USAGE.get(field_id, ()):
            refs.append(
                {
                    "factor_id": factor_id,
                    "field_id": field_id,
                    "use": use,
                    "context_id": context_id,
                }
            )
    return refs


def _resolve_location(
    *,
    raw: Mapping[str, Any],
    requested_location: Mapping[str, Any],
    point_role: str,
    parcel_geometry_hash: str | None,
) -> dict[str, Any]:
    resolved = raw.get("resolved_location") if isinstance(raw.get("resolved_location"), Mapping) else {}
    lat = raw.get("lat")
    lng = raw.get("lng")
    if lat is None and isinstance(resolved, Mapping):
        lat = resolved.get("lat")
    if lng is None and isinstance(resolved, Mapping):
        lng = resolved.get("lng")
    if lat is None:
        lat = requested_location.get("lat")
    if lng is None:
        lng = requested_location.get("lng")
    return {
        "lat": lat,
        "lng": lng,
        "spatial_semantics": "POINT",
        "point_role": point_role,
        "parcel_geometry_hash": parcel_geometry_hash,
    }


def _lookup_resolution(raw: Mapping[str, Any]) -> dict[str, Any]:
    disposition = _normalize_disposition(raw.get("disposition"))
    if disposition is None:
        raise MireyeAdapterError("lookup_missing_disposition")
    resolution = {
        "disposition": disposition,
        "parcel_grade": raw.get("parcel_grade"),
        "confidence": raw.get("confidence"),
        "normalized_address": raw.get("normalized_address") or raw.get("address"),
        "precision_note": raw.get("precision_note"),
        "reason": raw.get("reason"),
        "parcel_unavailable": raw.get("parcel_unavailable"),
        "parcel_unavailable_reason": raw.get("parcel_unavailable_reason"),
        "legal_title_verified": False,
        "zoning_legality_confirmed": False,
    }
    if isinstance(raw.get("resolved_location"), Mapping):
        resolution["resolved_location"] = sanitize_for_storage(dict(raw["resolved_location"]))
    elif raw.get("lat") is not None and raw.get("lng") is not None:
        resolution["resolved_location"] = {
            "lat": raw.get("lat"),
            "lng": raw.get("lng"),
            "source": raw.get("resolved_source"),
        }
    return resolution


def _lookup_parcel_candidate(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    parcel = raw.get("parcel") or raw.get("parcel_candidate")
    if parcel is None:
        # Flatten common top-level parcel keys when present.
        candidate_keys = (
            "parcel_id",
            "apn",
            "jurisdiction",
            "county",
            "state",
            "zoning",
            "land_use",
            "land_use_class",
            "owner_name",
        )
        flat = {k: raw[k] for k in candidate_keys if k in raw}
        if not flat:
            return None
        parcel = flat
    if not isinstance(parcel, Mapping):
        raise MireyeAdapterError("invalid_parcel_candidate")
    out = sanitize_for_storage(dict(parcel))
    # Lookup may return jurisdiction beside the nested parcel object. Preserve
    # these non-owner context fields so downstream reports can scope public
    # diligence research without sending a street address.
    for key in ("jurisdiction", "county", "county_fips", "state", "state_fips"):
        if out.get(key) is None and raw.get(key) is not None:
            out[key] = sanitize_for_storage(raw.get(key))
    out["legal_title_verified"] = False
    out["zoning_legality_confirmed"] = False
    return out


def _response_status(
    *,
    context_type: str,
    raw: Mapping[str, Any],
    fields: Mapping[str, Any],
    partial_failures: Sequence[Mapping[str, Any]],
    resolution: Mapping[str, Any] | None,
) -> dict[str, Any]:
    fetched_at = raw.get("fetched_at")
    if context_type == CONTEXT_PROPERTY and resolution is not None:
        disposition = resolution.get("disposition")
        if disposition == "NO_MATCH":
            status = "FAILED" if not fields else "PARTIAL"
        elif disposition == "CLARIFY":
            status = "PARTIAL"
        elif partial_failures:
            status = "PARTIAL"
        else:
            status = "COMPLETE"
    else:
        if raw.get("error") and not fields and not partial_failures:
            status = "FAILED"
        elif partial_failures:
            status = "PARTIAL"
        elif not fields:
            status = "FAILED"
        else:
            status = "COMPLETE"
    return {"status": status, "fetched_at": fetched_at}


def normalize_mireye_context(
    *,
    context_type: str,
    raw_response: Mapping[str, Any] | None,
    requested_location: Mapping[str, Any],
    point_role: str = "PARCEL_CENTROID_QA",
    parcel_geometry_hash: str | None = None,
    endpoint: str | None = None,
    preset: str | None = None,
    explicitly_requested_fields: Sequence[str] | None = None,
    api_base_url: str | None = None,
    api_or_catalog_version: str | None = None,
    raw_artifact_reference: str | None = None,
    fail_closed: bool = True,
) -> dict[str, Any]:
    """Normalize one sanitized raw Mireye response into a unified context envelope."""
    if context_type not in SUPPORTED_CONTEXT_TYPES:
        raise MireyeAdapterError(f"unsupported_context_type:{context_type}")
    if point_role not in POINT_ROLES:
        raise MireyeAdapterError(f"invalid_point_role:{point_role}")
    if raw_response is None or not isinstance(raw_response, Mapping):
        raise MireyeAdapterError("invalid_raw_response")
    if fail_closed and not raw_response:
        raise MireyeAdapterError("empty_raw_response")

    raw = sanitize_for_storage(dict(raw_response))
    assert_no_credentials(raw, label="raw_response")

    if context_type == CONTEXT_PROPERTY:
        if "disposition" not in raw:
            raise MireyeAdapterError("lookup_missing_disposition")
    else:
        if "fields" not in raw or not isinstance(raw.get("fields"), Mapping):
            raise MireyeAdapterError("fetch_missing_fields_object")

    request = build_request_record(
        context_type=context_type,
        requested_location=requested_location,
        endpoint=endpoint,
        preset=preset,
        explicitly_requested_fields=explicitly_requested_fields,
    )

    fields_raw = raw.get("fields") if isinstance(raw.get("fields"), Mapping) else {}
    default_fetched_at = raw.get("fetched_at")
    fields: dict[str, Any] = {}
    for field_id in sorted(fields_raw):
        fields[field_id] = normalize_field(
            field_id, fields_raw[field_id], default_fetched_at=default_fetched_at
        )

    partial_failures: list[dict[str, Any]] = []
    for item in raw.get("partial_failures") or []:
        partial_failures.append(normalize_partial_failure(item))
    partial_failures.extend(_collect_field_status_failures(fields_raw))

    # Deduplicate by raw_failure_hash while preserving order.
    seen_hashes: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in partial_failures:
        h = item["raw_failure_hash"]
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        deduped.append(item)
    partial_failures = deduped

    resolution = None
    parcel_candidate = None
    if context_type == CONTEXT_PROPERTY:
        resolution = _lookup_resolution(raw)
        parcel_candidate = _lookup_parcel_candidate(raw)

    location = _resolve_location(
        raw=raw,
        requested_location=requested_location,
        point_role=point_role,
        parcel_geometry_hash=parcel_geometry_hash,
    )

    response_status = _response_status(
        context_type=context_type,
        raw=raw,
        fields=fields,
        partial_failures=partial_failures,
        resolution=resolution,
    )

    raw_response_hash = sha256_canonical(raw)
    context_id = "mireye_" + sha256_canonical(
        {
            "adapter_id": ADAPTER_ID,
            "adapter_version": ADAPTER_VERSION,
            "context_type": context_type,
            "request_hash": request["request_hash"],
            "raw_response_hash": raw_response_hash,
        }
    )[:24]

    safe_base = None
    if api_base_url:
        # Strip any embedded credentials from URL userinfo.
        safe_base = re.sub(r"://[^/@]+@", "://", str(api_base_url)).rstrip("/")

    envelope: dict[str, Any] = {
        "context_id": context_id,
        "context_type": context_type,
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "request": request,
        "response_status": response_status,
        "location": location,
        "authority": {
            "canonical_for_parcel_facts": False,
            "permitted_uses": list(PERMITTED_USES),
        },
        "fields": fields,
        "partial_failures": partial_failures,
        "provenance": {
            "raw_response_hash": raw_response_hash,
            "request_hash": request["request_hash"],
            "raw_artifact_reference": raw_artifact_reference,
            "api_base_url": safe_base,
            "api_or_catalog_version": api_or_catalog_version,
            "adapter_version": ADAPTER_VERSION,
        },
        "factor_usage_refs": [],
        "limitations": list(DEFAULT_LIMITATIONS),
    }
    if resolution is not None:
        envelope["resolution"] = resolution
    if parcel_candidate is not None:
        envelope["parcel_candidate"] = parcel_candidate

    envelope["factor_usage_refs"] = build_factor_usage_refs(context_id, fields)
    assert_no_credentials(envelope, label="normalized_context")
    return envelope


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = sanitize_for_storage(payload)
    assert_no_credentials(safe, label=str(path))
    path.write_text(
        json.dumps(safe, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _repo_relative_posix(path: str | Path) -> str:
    path = Path(path).resolve()
    repo = Path(__file__).resolve().parents[2]
    try:
        return path.relative_to(repo).as_posix()
    except ValueError:
        return path.as_posix()


def normalize_from_fixture(
    *,
    context_type: str,
    raw_path: str | Path,
    requested_location: Mapping[str, Any] | None = None,
    point_role: str = "PARCEL_CENTROID_QA",
    parcel_geometry_hash: str | None = None,
    api_base_url: str | None = None,
    api_or_catalog_version: str | None = "0.14.0",
) -> dict[str, Any]:
    raw = load_json(raw_path)
    if not isinstance(raw, Mapping):
        raise MireyeAdapterError("fixture_not_object")
    loc = dict(requested_location or {})
    if "lat" not in loc and "lat" in raw:
        loc["lat"] = raw["lat"]
    if "lng" not in loc and "lng" in raw:
        loc["lng"] = raw["lng"]
    return normalize_mireye_context(
        context_type=context_type,
        raw_response=raw,
        requested_location=loc,
        point_role=point_role,
        parcel_geometry_hash=parcel_geometry_hash,
        api_base_url=api_base_url,
        api_or_catalog_version=api_or_catalog_version,
        raw_artifact_reference=_repo_relative_posix(raw_path),
    )


def lookup_supports_coordinate_input() -> bool:
    """OpenAPI ResolveRequest accepts kind=coord and input 'lat,lng'."""
    return True


def _env_base_url() -> str:
    raw = (os.environ.get("MIREYE_API_BASE_URL") or OFFICIAL_MIREYE_HTTPS_ORIGIN).rstrip("/")
    validation = validate_mireye_base_url(raw)
    if not validation["ok"]:
        # Fail closed on misconfigured base URL rather than silently hitting the wrong host.
        raise MireyeAdapterError(
            "invalid_MIREYE_API_BASE_URL:"
            f"expected={OFFICIAL_MIREYE_HTTPS_ORIGIN};"
            f"scheme={validation.get('scheme')};host={validation.get('hostname')}"
        )
    return raw


def resolve_mireye_api_token() -> str | None:
    """Return Mireye Bearer token from env.

    Canonical: ``MIREYE_API_TOKEN`` (Mireye docs).
    Legacy alias: ``MIREYE_API_KEY`` (existing RangeMatch .env files).
    Never log the returned value.
    """
    for name in ("MIREYE_API_TOKEN", "MIREYE_API_KEY"):
        raw = os.environ.get(name)
        if raw and raw.strip():
            return raw.strip()
    return None


def _env_api_key() -> str | None:
    return resolve_mireye_api_token()


def _bypass_env_proxy_flag() -> bool:
    raw = os.environ.get("MIREYE_TRANSPORT_BYPASS_ENV_PROXY")
    if raw is None or raw.strip() == "":
        return DEFAULT_BYPASS_ENV_PROXY
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def live_mireye_request(
    *,
    endpoint: str,
    body: Mapping[str, Any],
    timeout_seconds: float = 60.0,
    bypass_env_proxy: bool | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """POST to Mireye. Returns (sanitized_json, meta). Never returns the API key."""
    base = _env_base_url()
    key = _env_api_key()
    if not key:
        raise MireyeAdapterError("MIREYE_API_TOKEN_missing")
    if bypass_env_proxy is None:
        bypass_env_proxy = _bypass_env_proxy_flag()
    url = f"{base}{endpoint}"
    data = json.dumps(dict(body)).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {key}",
        },
    )
    meta: dict[str, Any] = {
        "endpoint": endpoint,
        "api_base_url": base,
        "http_status": None,
        "ok": False,
        "error": None,
        "error_class": None,
        "bypass_env_proxy": bypass_env_proxy,
    }
    try:
        with mireye_urlopen(
            req, timeout=timeout_seconds, bypass_env_proxy=bypass_env_proxy
        ) as resp:
            meta["http_status"] = getattr(resp, "status", None) or resp.getcode()
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        meta["http_status"] = exc.code
        body_text = exc.read().decode("utf-8", errors="replace")
        meta["error"] = f"HTTPError:{exc.code}"
        meta["error_class"] = "HTTP_ERROR"
        try:
            payload = json.loads(body_text)
        except json.JSONDecodeError:
            payload = {"error": "http_error", "message": body_text[:500]}
    except Exception as exc:  # noqa: BLE001 — live gate must record transport failures
        probe = probe_plaintext_http_on_443()
        error_class = classify_tls_failure(exc, plaintext_probe=probe)
        meta["error_class"] = error_class
        meta["error"] = redact_transport_message(
            f"{error_class}:{type(exc).__name__}", api_key=key
        )
        meta["plaintext_http_probe"] = {
            "looks_like_http": probe.get("looks_like_http"),
            "safebrowse_redirect": probe.get("safebrowse_redirect"),
            "status_line": probe.get("status_line"),
        }
        raise MireyeAdapterError(meta["error"]) from exc

    safe = sanitize_for_storage(payload)
    assert_no_credentials(safe, label="live_response")
    meta["ok"] = meta["http_status"] == 200
    return safe if isinstance(safe, dict) else {"value": safe}, meta


def collect_live_mireye_contexts(
    *,
    lat: float,
    lng: float,
    parcel_geometry_hash: str,
    request_fn: Any | None = None,
) -> dict[str, Any]:
    """Collect the three non-canonical Mireye contexts for one confirmed parcel.

    Each context fails independently. Returned contexts are normalized envelopes
    and remain point/diligence context only; errors are safe public metadata.
    """
    request_fn = request_fn or live_mireye_request
    requested = {"lat": float(lat), "lng": float(lng), "kind": "coord"}
    specs = (
        (
            CONTEXT_PROPERTY,
            ENDPOINT_LOOKUP,
            {"input": f"{lat},{lng}", "kind": "coord", "include_parcel": True},
            None,
            (),
        ),
        (
            CONTEXT_LAND,
            ENDPOINT_FETCH,
            {"lat": lat, "lng": lng, "preset": "terrain", "fields": list(LAND_ADDITIONAL_FIELDS)},
            "terrain",
            LAND_ADDITIONAL_FIELDS,
        ),
        (
            CONTEXT_HAZARD,
            ENDPOINT_FETCH,
            {"lat": lat, "lng": lng, "preset": "flood_risk", "fields": list(HAZARD_ADDITIONAL_FIELDS)},
            "flood_risk",
            HAZARD_ADDITIONAL_FIELDS,
        ),
    )
    contexts: dict[str, Any] = {}
    errors: dict[str, Any] = {}
    transport_meta: dict[str, Any] = {}
    for context_type, endpoint, body, preset, requested_fields in specs:
        try:
            raw, meta = request_fn(endpoint=endpoint, body=body)
            transport_meta[context_type] = sanitize_for_storage(meta)
            contexts[context_type] = normalize_mireye_context(
                context_type=context_type,
                raw_response=raw,
                requested_location=requested,
                point_role="PARCEL_CENTROID_QA",
                parcel_geometry_hash=parcel_geometry_hash,
                endpoint=endpoint,
                preset=preset,
                explicitly_requested_fields=requested_fields,
                api_base_url=_env_base_url(),
                api_or_catalog_version="0.14.0",
                raw_artifact_reference=f"memory://mireye-live/{context_type.lower()}",
            )
        except MireyeAdapterError as exc:
            errors[context_type] = {
                "error_class": str(exc).split(":", 1)[0],
                "message": str(exc),
                "normalized_effect": "UNKNOWN",
            }
    result = {
        "contexts": contexts,
        "errors": errors,
        "transport_meta": transport_meta,
        "requested_point": {"lat": float(lat), "lng": float(lng)},
        "canonical_for_parcel_facts": False,
    }
    assert_no_credentials(result, label="live_context_collection")
    return result


def write_transport_diagnosis(out_path: str | Path) -> dict[str, Any]:
    """Write sanitized transport diagnosis JSON (no credentials)."""
    report = diagnose_mireye_transport(base_url=os.environ.get("MIREYE_API_BASE_URL"))
    # Never include key material; key_present bool only.
    report["proxy_environment"] = report_proxy_environment()
    write_json(out_path, report)
    return report


def run_cper_live_gate(
    *,
    out_dir: str | Path,
    lat: float = 40.825,
    lng: float = -104.7625,
    parcel_geometry_hash: str | None = None,
) -> dict[str, Any]:
    """One controlled live gate for CPER centroid contexts.

    Transport/TLS failures are recorded per context and do not invent data.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {
        "gate_id": "MIREYE_ADAPTER_CPER_LIVE_GATE",
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "location": {"lat": lat, "lng": lng},
        "contexts": {},
        "credential_safety": "PASS_PENDING_ASSERT",
        "factor_writes": False,
        "match_result_changed": False,
        "transport_blocked": False,
    }
    requested = {"lat": lat, "lng": lng, "kind": "coord"}

    def _attempt_fetch(context_type: str, body: Mapping[str, Any], raw_name: str, norm_name: str) -> None:
        try:
            raw, meta = live_mireye_request(endpoint=ENDPOINT_FETCH, body=body)
        except MireyeAdapterError as exc:
            results["transport_blocked"] = True
            err = str(exc)
            results["contexts"][context_type] = {
                "endpoint_status": {
                    "ok": False,
                    "error": err,
                    "endpoint": ENDPOINT_FETCH,
                    "error_class": err.split(":", 1)[0],
                },
                "adapter_status": "FAILED",
                "gate_status": "BLOCKED_EXTERNAL"
                if err.startswith("BLOCKED_EXTERNAL")
                else "FAILED",
                "note": "live_transport_or_tls_failure",
            }
            return
        raw_path = out / raw_name
        write_json(raw_path, raw)
        ctx = normalize_mireye_context(
            context_type=context_type,
            raw_response=raw,
            requested_location=requested,
            point_role="PARCEL_CENTROID_QA",
            parcel_geometry_hash=parcel_geometry_hash,
            api_base_url=_env_base_url(),
            api_or_catalog_version="0.14.0",
            raw_artifact_reference=_repo_relative_posix(raw_path),
        )
        norm_path = out / norm_name
        write_json(norm_path, ctx)
        results["contexts"][context_type] = {
            "endpoint_status": meta,
            "adapter_status": ctx["response_status"]["status"],
            "raw_artifact": _repo_relative_posix(raw_path),
            "normalized_artifact": _repo_relative_posix(norm_path),
            "context_id": ctx["context_id"],
            "partial_failure_count": len(ctx["partial_failures"]),
        }

    _attempt_fetch(
        CONTEXT_LAND,
        {"lat": lat, "lng": lng, "preset": "terrain", "fields": list(LAND_ADDITIONAL_FIELDS)},
        "raw_point_land_cper.json",
        "normalized_point_land_cper.json",
    )
    _attempt_fetch(
        CONTEXT_HAZARD,
        {
            "lat": lat,
            "lng": lng,
            "preset": "flood_risk",
            "fields": list(HAZARD_ADDITIONAL_FIELDS),
        },
        "raw_point_hazard_cper.json",
        "normalized_point_hazard_cper.json",
    )

    if lookup_supports_coordinate_input():
        lookup_body = {"input": f"{lat},{lng}", "kind": "coord", "include_parcel": True}
        try:
            lookup_raw, lookup_meta = live_mireye_request(
                endpoint=ENDPOINT_LOOKUP, body=lookup_body
            )
            lookup_raw_path = out / "raw_property_diligence_cper.json"
            write_json(lookup_raw_path, lookup_raw)
            lookup_ctx = normalize_mireye_context(
                context_type=CONTEXT_PROPERTY,
                raw_response=lookup_raw,
                requested_location=requested,
                point_role="PARCEL_CENTROID_QA",
                parcel_geometry_hash=parcel_geometry_hash,
                api_base_url=_env_base_url(),
                api_or_catalog_version="0.14.0",
                raw_artifact_reference=_repo_relative_posix(lookup_raw_path),
            )
            lookup_norm_path = out / "normalized_property_diligence_cper.json"
            write_json(lookup_norm_path, lookup_ctx)
            results["contexts"][CONTEXT_PROPERTY] = {
                "endpoint_status": lookup_meta,
                "adapter_status": lookup_ctx["response_status"]["status"],
                "raw_artifact": _repo_relative_posix(lookup_raw_path),
                "normalized_artifact": _repo_relative_posix(lookup_norm_path),
                "context_id": lookup_ctx["context_id"],
                "partial_failure_count": len(lookup_ctx["partial_failures"]),
                "disposition": lookup_ctx.get("resolution", {}).get("disposition"),
            }
        except MireyeAdapterError as exc:
            results["transport_blocked"] = True
            err = str(exc)
            results["contexts"][CONTEXT_PROPERTY] = {
                "endpoint_status": {
                    "ok": False,
                    "error": err,
                    "endpoint": ENDPOINT_LOOKUP,
                    "error_class": err.split(":", 1)[0],
                },
                "adapter_status": "FAILED",
                "gate_status": "BLOCKED_EXTERNAL"
                if err.startswith("BLOCKED_EXTERNAL")
                else "FAILED",
                "note": "live_transport_or_tls_failure",
            }
    else:
        results["contexts"][CONTEXT_PROPERTY] = {
            "adapter_status": "NOT_TESTED_MISSING_APPROVED_INPUT",
            "note": "lookup_coordinate_input_not_supported_by_contract",
        }

    for path in out.glob("*.json"):
        assert_no_credentials(path.read_text(encoding="utf-8"), label=str(path))
    results["credential_safety"] = "PASS"
    summary_path = out / "live_gate_summary.json"
    write_json(summary_path, results)
    results["summary_artifact"] = _repo_relative_posix(summary_path)
    return results
