"""Mireye /v1/lookup → Parcel Resolution mapping (offline-capable).

Maps official lookup dispositions to RangeMatch parcel-resolution states.
Does not auto-confirm parcels. Does not make network calls — callers inject
raw lookup JSON (fixtures) or a future gated HTTP client.

Contract: docs/MIREYE_LIVE_PARCEL_RESOLVER_CONTRACT.md
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from rangematch.parcel_resolution import (
    ADAPTER_LIVE,
    PARCEL_QUALITY_ACCURACY_TYPES,
    ParcelResolutionError,
    is_parcel_quality_accuracy,
    normalize_address_text,
    validate_parcel_boundary_geometry,
)

ADAPTER_ID = ADAPTER_LIVE
ADAPTER_VERSION = "0.2.0-mireye-lookup"
PROVIDER_NAME = "Mireye"
PROVENANCE_SOURCE = "REGRID via Mireye"

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "test-data" / "mireye-parcel-lookup"

# Owner / PII keys — strip until Regrid licensing confirms display is allowed.
_OWNER_KEYS = frozenset(
    {"owner", "owner_name", "ownername", "owners", "owner_names", "grantee"}
)


@dataclass
class MireyeLookupMapping:
    """Deterministic mapping result from one /v1/lookup payload."""

    disposition: str | None
    terminal_status: str | None
    """If set before candidates are considered, start_parcel_resolution should stop."""

    normalized_address: str | None
    geocode_status: str
    geocode_point: dict[str, Any] | None
    accuracy: float | None = None
    accuracy_type: str | None = None
    match_type: str | None = None
    confidence: float | None = None
    request_id: str = "mireye:lookup"
    retrieved_at: str | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    parcel_unavailable: bool | None = None
    parcel_unavailable_reason: str | None = None
    limitations: list[str] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    raw_disposition: str | None = None
    location_hints: list[dict[str, Any]] = field(default_factory=list)
    no_match_reason: str | None = None
    no_match_hint: str | None = None


def load_mireye_parcel_lookup_scenario(scenario_id: str) -> dict[str, Any]:
    path = FIXTURE_ROOT / f"{scenario_id}.json"
    if not path.is_file():
        raise ParcelResolutionError(
            "MIREYE_LOOKUP_FIXTURE_MISSING",
            f"mireye parcel-lookup fixture not found: {scenario_id}",
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ParcelResolutionError(
            "MIREYE_LOOKUP_FIXTURE_INVALID",
            f"fixture must be an object: {scenario_id}",
        )
    return data


def _accuracy_from_match_method(match_method: Any) -> str | None:
    """Latest /v1/lookup often sends match_method instead of accuracy_type."""
    text = str(match_method or "").strip().lower()
    if not text:
        return None
    if "nearest_rooftop" in text:
        return "nearest_rooftop_match"
    if "rooftop" in text:
        return "rooftop"
    if "range_interpolation" in text:
        return "range_interpolation"
    return None


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _redact_owner_fields(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if str(k).lower() in _OWNER_KEYS:
                out[k] = None
            else:
                out[k] = _redact_owner_fields(v)
        return out
    if isinstance(obj, list):
        return [_redact_owner_fields(x) for x in obj]
    return obj


def _wkt_to_geojson(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw.upper().startswith(("POLYGON", "MULTIPOLYGON")):
        return None
    try:
        from shapely import from_wkt
        from shapely.geometry import mapping
    except ImportError:
        return None
    try:
        mapped = mapping(from_wkt(raw))
    except Exception:  # noqa: BLE001 — WKT is optional live-contract sugar
        return None
    if isinstance(mapped, Mapping):
        return dict(mapped)
    return None


def _geometry_to_feature_collection(geom: Any) -> dict[str, Any] | None:
    if isinstance(geom, str):
        wkt = _wkt_to_geojson(geom)
        if wkt is not None:
            geom = wkt
        else:
            try:
                geom = json.loads(geom)
            except json.JSONDecodeError:
                return None
    if not isinstance(geom, Mapping):
        return None
    gtype = geom.get("type")
    if gtype == "FeatureCollection":
        return deepcopy(dict(geom))
    if gtype == "Feature":
        return {"type": "FeatureCollection", "features": [deepcopy(dict(geom))]}
    if gtype in {"Polygon", "MultiPolygon"}:
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": deepcopy(dict(geom)),
                }
            ],
        }
    return None


def _extract_geocode_fields(raw: Mapping[str, Any]) -> dict[str, Any]:
    geocode = raw.get("geocode") if isinstance(raw.get("geocode"), Mapping) else {}
    accuracy_type = (
        raw.get("accuracy_type")
        or geocode.get("accuracy_type")
        or raw.get("geocode_accuracy_type")
        or _accuracy_from_match_method(raw.get("match_method") or geocode.get("match_method"))
    )
    accuracy = _as_float(
        raw.get("accuracy") if raw.get("accuracy") is not None else geocode.get("accuracy")
    )
    match_type = raw.get("match_type") or geocode.get("match_type")
    point = None
    resolved = raw.get("resolved_location")
    if isinstance(resolved, Mapping) and resolved.get("lat") is not None and resolved.get("lng") is not None:
        point = {
            "type": "Point",
            "coordinates": [float(resolved["lng"]), float(resolved["lat"])],
        }
    elif raw.get("lat") is not None and raw.get("lng") is not None:
        point = {
            "type": "Point",
            "coordinates": [float(raw["lng"]), float(raw["lat"])],
        }
    elif isinstance(geocode.get("point"), Mapping):
        point = deepcopy(dict(geocode["point"]))
    return {
        "accuracy": accuracy,
        "accuracy_type": str(accuracy_type).strip() if accuracy_type else None,
        "match_type": str(match_type).strip() if match_type else None,
        "point": point,
    }


def _parcel_block(raw: Mapping[str, Any]) -> Mapping[str, Any] | None:
    parcel = raw.get("parcel")
    if isinstance(parcel, Mapping):
        return parcel
    return None


def _candidate_from_parcel_block(
    parcel: Mapping[str, Any],
    *,
    index: int,
    retrieved_at: str | None,
    request_id: str,
    label_fallback: str,
) -> dict[str, Any] | None:
    geom_raw = (
        parcel.get("geometry")
        or parcel.get("parcel_geometry")
        or parcel.get("boundary")
        or parcel.get("geometry_wkt")
    )
    fc = _geometry_to_feature_collection(geom_raw)
    if fc is None:
        return None
    parcel = _redact_owner_fields(parcel)
    candidate_id = str(
        parcel.get("parcel_id")
        or parcel.get("id")
        or parcel.get("apn")
        or f"mireye_cand_{index}"
    )
    label = str(
        parcel.get("label")
        or parcel.get("address")
        or parcel.get("apn")
        or label_fallback
    )
    attrs = {
        "apn": parcel.get("apn"),
        "owner": None,  # redacted pending license
        "zoning": parcel.get("zoning"),
        "jurisdiction": parcel.get("jurisdiction") or parcel.get("county"),
        "parcel_unavailable": False,
    }
    return {
        "candidate_id": candidate_id,
        "label": label,
        "parcel_geometry": fc,
        "source_crs": str(parcel.get("crs") or parcel.get("source_crs") or "EPSG:4326"),
        "normalized_crs": "EPSG:4326",
        "confidence": _as_float(parcel.get("confidence")),
        "provenance": {
            "source": PROVENANCE_SOURCE,
            "provider": PROVIDER_NAME,
            "request_id": request_id,
            "reference_id": str(parcel.get("parcel_id") or candidate_id),
            "retrieved_at": retrieved_at,
        },
        "limitations": [
            "Parcel geometry sourced via Mireye /v1/lookup (Regrid).",
            "Owner names are redacted pending licensing confirmation.",
            "APN/zoning/legal access/purchasability are unverified soft labels.",
            "Geometry requires explicit user boundary confirmation.",
        ],
        "attributes": attrs,
        "validation_status": "PENDING",
        "validation_errors": [],
        "geometry_hash": None,
    }


def _location_hints_from_clarify(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    for item in list(raw.get("candidates") or [])[:3]:
        if not isinstance(item, Mapping):
            continue
        lat = _as_float(item.get("lat"))
        lng = _as_float(item.get("lng"))
        has_geom = bool(
            item.get("geometry")
            or item.get("parcel_geometry")
            or item.get("boundary")
            or (isinstance(item.get("parcel"), Mapping) and item["parcel"].get("geometry"))
        )
        hints.append(
            {
                "label": item.get("resolved_address")
                or item.get("normalized_address")
                or item.get("label")
                or item.get("address"),
                "lat": lat,
                "lng": lng,
                "confidence": _as_float(item.get("confidence")),
                "has_geometry": has_geom,
                "candidate_id": None,
                "geometry_hash": None,
            }
        )
    return hints


def _candidates_from_clarify(
    raw: Mapping[str, Any], *, request_id: str, retrieved_at: str | None
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, item in enumerate(raw.get("candidates") or []):
        if not isinstance(item, Mapping):
            continue
        parcel_like: dict[str, Any] | None = None
        if item.get("geometry") or item.get("parcel_geometry") or item.get("boundary"):
            parcel_like = dict(item)
        elif isinstance(item.get("parcel"), Mapping):
            parcel_like = dict(item["parcel"])
            if item.get("label"):
                parcel_like.setdefault("label", item["label"])
        if parcel_like is None:
            # Point-only clarify hits are not parcel boundaries.
            continue
        cand = _candidate_from_parcel_block(
            parcel_like,
            index=i,
            retrieved_at=retrieved_at,
            request_id=request_id,
            label_fallback=str(item.get("label") or f"Candidate {i + 1}"),
        )
        if cand is not None:
            out.append(cand)
    return out


def map_mireye_lookup_to_parcel(raw_lookup: Mapping[str, Any]) -> MireyeLookupMapping:
    """Map a sanitized Mireye /v1/lookup JSON body to parcel-resolution inputs."""
    if not isinstance(raw_lookup, Mapping) or not raw_lookup:
        raise ParcelResolutionError("INVALID_LOOKUP", "empty or invalid lookup payload")

    raw = _redact_owner_fields(dict(raw_lookup))
    disposition_raw = raw.get("disposition")
    disposition = str(disposition_raw).strip().lower() if disposition_raw is not None else None
    retrieved_at = raw.get("fetched_at") or raw.get("retrieved_at")
    request_id = str(raw.get("request_id") or raw.get("id") or "mireye:lookup")
    normalized = (
        raw.get("normalized_address")
        or raw.get("resolved_address")
        or raw.get("address")
    )
    if normalized is not None:
        normalized = str(normalized)

    geo = _extract_geocode_fields(raw)
    confidence = _as_float(raw.get("confidence"))
    parcel_unavailable = raw.get("parcel_unavailable")
    if parcel_unavailable is None:
        parcel = _parcel_block(raw)
        if isinstance(parcel, Mapping) and parcel.get("parcel_unavailable") is not None:
            parcel_unavailable = parcel.get("parcel_unavailable")
    parcel_unavailable = (
        bool(parcel_unavailable) if parcel_unavailable is not None else None
    )
    parcel_unavailable_reason = raw.get("parcel_unavailable_reason")
    if parcel_unavailable_reason is None:
        parcel = _parcel_block(raw)
        if isinstance(parcel, Mapping):
            parcel_unavailable_reason = parcel.get("parcel_unavailable_reason")
    if parcel_unavailable_reason is not None:
        parcel_unavailable_reason = str(parcel_unavailable_reason)

    limitations = [
        "Property addresses sent for live resolution may be logged and retained "
        "by the geospatial provider for reliability and audit purposes.",
        "Geocode point is not a parcel boundary.",
        f"Mireye lookup disposition={disposition or 'unknown'}.",
    ]
    errors: list[dict[str, str]] = []

    # Geocode quality gate (when accuracy_type is present).
    accuracy_type = geo["accuracy_type"]
    if accuracy_type and not is_parcel_quality_accuracy(accuracy_type):
        return MireyeLookupMapping(
            disposition=disposition,
            raw_disposition=str(disposition_raw) if disposition_raw is not None else None,
            terminal_status="GEOCODE_QUALITY_INSUFFICIENT",
            normalized_address=normalized,
            geocode_status="GEOCODE_QUALITY_INSUFFICIENT",
            geocode_point=geo["point"],
            accuracy=geo["accuracy"],
            accuracy_type=accuracy_type,
            match_type=geo["match_type"],
            confidence=confidence,
            request_id=request_id,
            retrieved_at=str(retrieved_at) if retrieved_at else None,
            parcel_unavailable=parcel_unavailable,
            parcel_unavailable_reason=parcel_unavailable_reason,
            limitations=limitations
            + [
                f"Geocode accuracy_type={accuracy_type} is not parcel-quality "
                f"(required: {sorted(PARCEL_QUALITY_ACCURACY_TYPES)}).",
                "Refine the address or supply a parcel polygon.",
            ],
            errors=[
                {
                    "code": "GEOCODE_QUALITY_INSUFFICIENT",
                    "message": f"accuracy_type={accuracy_type} is not parcel-quality",
                }
            ],
        )

    if disposition in {None, ""}:
        raise ParcelResolutionError("lookup_missing_disposition", "disposition required")

    if disposition == "no_match":
        reason = str(raw.get("reason") or "no_match")
        hint = raw.get("hint")
        hint_text = str(hint).strip() if hint else None
        return MireyeLookupMapping(
            disposition=disposition,
            raw_disposition=str(disposition_raw),
            terminal_status="NO_MATCH",
            normalized_address=normalized,
            geocode_status="NO_MATCH" if geo["point"] is None else "OK",
            geocode_point=geo["point"],
            accuracy=geo["accuracy"],
            accuracy_type=accuracy_type,
            match_type=geo["match_type"],
            confidence=confidence,
            request_id=request_id,
            retrieved_at=str(retrieved_at) if retrieved_at else None,
            parcel_unavailable=parcel_unavailable,
            parcel_unavailable_reason=parcel_unavailable_reason,
            limitations=limitations
            + [f"Mireye no_match reason={reason}."]
            + ([f"Mireye hint: {hint_text}"] if hint_text else []),
            errors=[{"code": "NO_MATCH", "message": reason}],
            no_match_reason=reason,
            no_match_hint=hint_text,
        )

    if disposition == "clarify":
        candidates = _candidates_from_clarify(
            raw, request_id=request_id, retrieved_at=str(retrieved_at) if retrieved_at else None
        )
        location_hints = _location_hints_from_clarify(raw)
        if not candidates:
            # Clarify without parcel polygons — cannot auto-pick points as boundaries.
            return MireyeLookupMapping(
                disposition=disposition,
                raw_disposition=str(disposition_raw),
                terminal_status="AMBIGUOUS",
                normalized_address=normalized,
                geocode_status="AMBIGUOUS",
                geocode_point=geo["point"],
                accuracy=geo["accuracy"],
                accuracy_type=accuracy_type,
                match_type=geo["match_type"],
                confidence=confidence,
                request_id=request_id,
                retrieved_at=str(retrieved_at) if retrieved_at else None,
                location_hints=location_hints,
                limitations=limitations
                + [
                    "clarify returned candidates without parcel polygons; "
                    "points are not boundaries.",
                ],
                errors=[
                    {
                        "code": "AMBIGUOUS",
                        "message": "clarify candidates lack parcel geometry",
                    }
                ],
            )
        return MireyeLookupMapping(
            disposition=disposition,
            raw_disposition=str(disposition_raw),
            terminal_status=None,
            normalized_address=normalized,
            geocode_status="OK",
            geocode_point=geo["point"],
            accuracy=geo["accuracy"],
            accuracy_type=accuracy_type or "rooftop",
            match_type=geo["match_type"],
            confidence=confidence,
            request_id=request_id,
            retrieved_at=str(retrieved_at) if retrieved_at else None,
            candidates=candidates[:3],
            location_hints=location_hints,
            limitations=limitations
            + ["Multiple Mireye clarify candidates — user must select exactly one."],
            errors=errors,
        )

    if disposition != "resolved":
        return MireyeLookupMapping(
            disposition=disposition,
            raw_disposition=str(disposition_raw),
            terminal_status="AMBIGUOUS",
            normalized_address=normalized,
            geocode_status="AMBIGUOUS",
            geocode_point=geo["point"],
            accuracy=geo["accuracy"],
            accuracy_type=accuracy_type,
            match_type=geo["match_type"],
            confidence=confidence,
            request_id=request_id,
            retrieved_at=str(retrieved_at) if retrieved_at else None,
            limitations=limitations + [f"Unsupported disposition: {disposition}."],
            errors=[
                {
                    "code": "AMBIGUOUS",
                    "message": f"unsupported disposition: {disposition}",
                }
            ],
        )

    # disposition == resolved
    if parcel_unavailable is True:
        reason = parcel_unavailable_reason or "parcel_unavailable"
        return MireyeLookupMapping(
            disposition=disposition,
            raw_disposition=str(disposition_raw),
            terminal_status="PARCEL_DATA_UNAVAILABLE",
            normalized_address=normalized,
            geocode_status="OK",
            geocode_point=geo["point"],
            accuracy=geo["accuracy"],
            accuracy_type=accuracy_type or "rooftop",
            match_type=geo["match_type"],
            confidence=confidence,
            request_id=request_id,
            retrieved_at=str(retrieved_at) if retrieved_at else None,
            parcel_unavailable=True,
            parcel_unavailable_reason=reason,
            limitations=limitations
            + [
                "Address resolved but parcel geometry unavailable.",
                f"parcel_unavailable_reason={reason}.",
                "CPER/demo fixtures were not substituted.",
            ],
            errors=[
                {
                    "code": "PARCEL_DATA_UNAVAILABLE",
                    "message": reason,
                }
            ],
        )

    parcel = _parcel_block(raw) or {}
    cand = _candidate_from_parcel_block(
        parcel,
        index=0,
        retrieved_at=str(retrieved_at) if retrieved_at else None,
        request_id=request_id,
        label_fallback=normalized or "Resolved parcel",
    )
    if cand is None:
        # resolved but no geometry object
        return MireyeLookupMapping(
            disposition=disposition,
            raw_disposition=str(disposition_raw),
            terminal_status="PARCEL_DATA_UNAVAILABLE",
            normalized_address=normalized,
            geocode_status="OK",
            geocode_point=geo["point"],
            accuracy=geo["accuracy"],
            accuracy_type=accuracy_type or "rooftop",
            match_type=geo["match_type"],
            confidence=confidence,
            request_id=request_id,
            retrieved_at=str(retrieved_at) if retrieved_at else None,
            parcel_unavailable=True,
            parcel_unavailable_reason=parcel_unavailable_reason or "missing_parcel_geometry",
            limitations=limitations
            + [
                "resolved disposition without usable parcel.geometry.",
                "CPER/demo fixtures were not substituted.",
            ],
            errors=[
                {
                    "code": "PARCEL_DATA_UNAVAILABLE",
                    "message": "missing_parcel_geometry",
                }
            ],
        )

    # Soft-validate geometry early (hard validation still in resolver.validate_candidate).
    errs = validate_parcel_boundary_geometry(
        cand["parcel_geometry"], source_crs=str(cand.get("source_crs") or "")
    )
    if errs:
        cand["validation_status"] = "INVALID"
        cand["validation_errors"] = list(errs)

    return MireyeLookupMapping(
        disposition=disposition,
        raw_disposition=str(disposition_raw),
        terminal_status=None,
        normalized_address=normalized,
        geocode_status="OK",
        geocode_point=geo["point"],
        accuracy=geo["accuracy"],
        accuracy_type=accuracy_type or "rooftop",
        match_type=geo["match_type"],
        confidence=confidence,
        request_id=request_id,
        retrieved_at=str(retrieved_at) if retrieved_at else None,
        candidates=[cand],
        parcel_unavailable=False,
        parcel_unavailable_reason=None,
        limitations=limitations
        + [
            "Mireye resolved + parcel geometry present; user must confirm boundary.",
            f"provenance.source={PROVENANCE_SOURCE}.",
        ],
        errors=errors,
    )


def find_mireye_lookup_scenario_id(raw_address: str) -> str | None:
    needle = normalize_address_text(raw_address).lower()
    if not FIXTURE_ROOT.is_dir():
        return None
    matches: list[str] = []
    for path in sorted(FIXTURE_ROOT.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        expected = data.get("raw_address") or data.get("normalized_address")
        if not expected:
            continue
        if normalize_address_text(str(expected)).lower() == needle:
            matches.append(str(data.get("scenario_id") or path.stem))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ParcelResolutionError(
            "MIREYE_LOOKUP_FIXTURE_AMBIGUOUS",
            f"address matches multiple mireye lookup fixtures: {matches}",
        )
    return None
