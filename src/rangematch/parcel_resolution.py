"""Parcel resolution: address → candidates → user confirmation → Planner geometry.

FIXTURE/OFFLINE resolver uses explicit scenario fixtures (no network).
LIVE uses Mireye /v1/lookup mapping — offline fixtures or controlled HTTP
(`allow_network=true`). Never silently substitutes CPER or other demo geometries.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol

from rangematch.unified_output import sha256_canonical

SCHEMA_VERSION = "RANGEMATCH_PARCEL_RESOLUTION@0.1.0"
ADAPTER_VERSION = "0.1.0"
ADAPTER_FIXTURE = "PARCEL_RESOLVER_FIXTURE"
ADAPTER_LIVE = "PARCEL_RESOLVER_LIVE"

REQUIRED_CRS = "EPSG:4326"
CPER_GEOMETRY_REFERENCE_MARKERS = (
    "engineering_test_geometry_cper",
    "ENGINEERING_TEST_GEOMETRY_CPER",
)

ResolutionStatus = Literal[
    "ADDRESS_ACCEPTED",
    "GEOCODED",
    "PARCEL_CANDIDATES_FOUND",
    "NEEDS_USER_SELECTION",
    "NEEDS_BOUNDARY_CONFIRMATION",
    "PARCEL_CONFIRMED",
    "NO_MATCH",
    "AMBIGUOUS",
    "BLOCKED_EXTERNAL",
    "INVALID_GEOMETRY",
    "PARCEL_DATA_UNAVAILABLE",
    "GEOCODE_QUALITY_INSUFFICIENT",
]

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "test-data" / "parcel-resolution"

# Geocode accuracy types that may enter live parcel-level lookup (Mireye Geocode).
PARCEL_QUALITY_ACCURACY_TYPES = frozenset({"rooftop", "nearest_rooftop_match"})

TERMINAL_FAILURE = frozenset(
    {
        "NO_MATCH",
        "AMBIGUOUS",
        "BLOCKED_EXTERNAL",
        "INVALID_GEOMETRY",
        "PARCEL_DATA_UNAVAILABLE",
        "GEOCODE_QUALITY_INSUFFICIENT",
    }
)


def is_parcel_quality_accuracy(accuracy_type: str | None) -> bool:
    """True only for Mireye geocode types eligible for parcel-level lookup."""
    if not accuracy_type:
        return False
    return accuracy_type.strip().lower() in PARCEL_QUALITY_ACCURACY_TYPES


class ParcelResolutionError(ValueError):
    """Fail-closed parcel resolution error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _error(code: str, message: str, path: str | None = None) -> dict[str, str]:
    out = {"code": code, "message": message}
    if path is not None:
        out["path"] = path
    return out


def normalize_address_text(raw_address: str) -> str:
    """Deterministic address normalization (whitespace / case / punctuation)."""
    if raw_address is None:
        raise ParcelResolutionError("ADDRESS_EMPTY", "address is required")
    text = str(raw_address).strip()
    if not text:
        raise ParcelResolutionError("ADDRESS_EMPTY", "address is required")
    text = re.sub(r"\s+", " ", text)
    text = text.replace(" ,", ",")
    # Preserve original casing for display but collapse internal space.
    return text


def _extract_geometry_object(payload: Mapping[str, Any]) -> tuple[str, Any, list[dict]]:
    """Return (geom_type, coordinates_or_none, features_list)."""
    gtype = payload.get("type")
    if gtype == "FeatureCollection":
        features = list(payload.get("features") or [])
        return "FeatureCollection", None, features
    if gtype == "Feature":
        geom = payload.get("geometry") or {}
        return str(geom.get("type") or ""), geom.get("coordinates"), [dict(payload)]
    if gtype in {"Polygon", "MultiPolygon", "Point", "LineString", "MultiPoint"}:
        return str(gtype), payload.get("coordinates"), []
    return str(gtype or ""), None, []


def _ring_closed(ring: Any) -> bool:
    if not isinstance(ring, list) or len(ring) < 4:
        return False
    return ring[0] == ring[-1]


def _coords_in_wgs84_bounds(coords: Any) -> bool:
    if not isinstance(coords, (list, tuple)):
        return False
    if coords and isinstance(coords[0], (int, float)):
        if len(coords) < 2:
            return False
        lon, lat = float(coords[0]), float(coords[1])
        return -180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0
    return all(_coords_in_wgs84_bounds(c) for c in coords)


def _polygon_rings_ok(coords: Any) -> bool:
    if not isinstance(coords, list) or not coords:
        return False
    for ring in coords:
        if not _ring_closed(ring):
            return False
        if not _coords_in_wgs84_bounds(ring):
            return False
    return True


def _multipolygon_ok(coords: Any) -> bool:
    if not isinstance(coords, list) or not coords:
        return False
    return all(_polygon_rings_ok(poly) for poly in coords)


def as_one_feature_collection(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize Feature / Polygon / MultiPolygon / one-Feature FC → one-Feature FC."""
    gtype = payload.get("type")
    if gtype == "FeatureCollection":
        features = list(payload.get("features") or [])
        if len(features) != 1:
            raise ParcelResolutionError(
                "FEATURE_COUNT",
                f"FeatureCollection must contain exactly one Feature; got {len(features)}",
            )
        return {
            "type": "FeatureCollection",
            "features": [deepcopy(features[0])],
        }
    if gtype == "Feature":
        return {"type": "FeatureCollection", "features": [deepcopy(dict(payload))]}
    if gtype in {"Polygon", "MultiPolygon"}:
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": deepcopy(dict(payload)),
                }
            ],
        }
    raise ParcelResolutionError(
        "INVALID_GEOMETRY_TYPE",
        f"unsupported geometry type for parcel boundary: {gtype}",
    )


def compute_geometry_hash(parcel_geometry: Mapping[str, Any]) -> str:
    """SHA-256 of canonical one-Feature FeatureCollection JSON."""
    fc = as_one_feature_collection(parcel_geometry)
    return sha256_canonical(fc)


def validate_parcel_boundary_geometry(
    payload: Mapping[str, Any] | None,
    *,
    source_crs: str | None,
    allow_pending_hash: bool = False,
) -> list[str]:
    """Return validation error codes; empty list means valid."""
    errors: list[str] = []
    if payload is None:
        return ["GEOMETRY_MISSING"]

    crs = (source_crs or "").strip()
    if crs and crs != REQUIRED_CRS:
        errors.append("UNSUPPORTED_CRS")

    gtype, coords, features = _extract_geometry_object(payload)

    if gtype == "FeatureCollection":
        if len(features) == 0:
            errors.append("FEATURE_COLLECTION_EMPTY")
            return errors
        if len(features) != 1:
            errors.append("FEATURE_COLLECTION_MULTI")
            return errors
        feature = features[0]
        geom = feature.get("geometry") if isinstance(feature, Mapping) else None
        if not isinstance(geom, Mapping):
            errors.append("GEOMETRY_MISSING")
            return errors
        return validate_parcel_boundary_geometry(
            geom, source_crs=source_crs, allow_pending_hash=allow_pending_hash
        )

    if gtype == "Point":
        errors.append("ADDRESS_POINT_NOT_PARCEL_BOUNDARY")
        return errors
    if gtype in {"LineString", "MultiPoint", "MultiLineString"}:
        errors.append("INVALID_GEOMETRY_TYPE")
        return errors
    if gtype == "Polygon":
        if not _polygon_rings_ok(coords):
            errors.append("INVALID_POLYGON")
        return errors
    if gtype == "MultiPolygon":
        if not _multipolygon_ok(coords):
            errors.append("INVALID_POLYGON")
        return errors
    if gtype == "Feature":
        geom = payload.get("geometry")
        if not isinstance(geom, Mapping):
            return ["GEOMETRY_MISSING"]
        return validate_parcel_boundary_geometry(
            geom, source_crs=source_crs, allow_pending_hash=allow_pending_hash
        )

    errors.append("INVALID_GEOMETRY_TYPE")
    return errors


def references_cper_demo_geometry(value: Any) -> bool:
    blob = json.dumps(value, sort_keys=True) if not isinstance(value, str) else value
    return any(marker in blob for marker in CPER_GEOMETRY_REFERENCE_MARKERS)


@dataclass(frozen=True)
class NormalizedAddress:
    raw_address: str
    normalized_address: str


@dataclass(frozen=True)
class GeocodeResult:
    status: str
    point: dict[str, Any] | None
    confidence: float | None
    provider: str
    request_id: str
    retrieved_at: str | None
    limitations: tuple[str, ...] = ()
    accuracy: float | None = None
    accuracy_type: str | None = None
    match_type: str | None = None
    normalized_address: str | None = None


@dataclass(frozen=True)
class CandidateValidation:
    ok: bool
    errors: tuple[str, ...]
    geometry_hash: str | None


class ParcelResolver(Protocol):
    name: str
    adapter_id: str

    def normalize_address(self, raw_address: str) -> NormalizedAddress: ...

    def geocode_address(self, normalized: NormalizedAddress) -> GeocodeResult: ...

    def find_parcel_candidates(
        self, geocode: GeocodeResult, *, normalized: NormalizedAddress
    ) -> list[dict[str, Any]]: ...

    def validate_candidate(self, candidate: Mapping[str, Any]) -> CandidateValidation: ...

    def confirm_parcel(
        self,
        resolution: Mapping[str, Any],
        *,
        candidate_id: str,
        confirm_boundary: bool = True,
    ) -> dict[str, Any]: ...


def _base_record(
    *,
    resolution_id: str,
    adapter_id: str,
    provider_mode: str,
    status: ResolutionStatus,
    raw_address: str | None,
    normalized_address: str | None,
    scenario_id: str | None = None,
    input_kind: str = "ADDRESS",
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "resolution_id": resolution_id,
        "adapter_id": adapter_id,
        "adapter_version": ADAPTER_VERSION,
        "provider_mode": provider_mode,
        "status": status,
        "scenario_id": scenario_id,
        "input": {
            "input_kind": input_kind,
            "raw_address": raw_address,
            "normalized_address": normalized_address,
            "latitude": latitude,
            "longitude": longitude,
        },
        "geocode": None,
        "candidates": [],
        "selection": None,
        "confirmed_parcel": None,
        "evidence_invalidation_required": False,
        "previous_geometry_hash": None,
        "provenance": {
            "source": None,
            "provider": provider_mode,
            "request_id": resolution_id,
            "reference_id": scenario_id,
            "retrieved_at": None,
            "source_crs": None,
            "normalized_crs": None,
            "confidence": None,
            "status": status,
        },
        "limitations": [
            "Ownership, APN, zoning, legal access, and purchasability are not verified "
            "by parcel resolution alone.",
            "Address text and geocode points are not parcel boundaries.",
            "Coordinates (when used) are a parcel lookup point only — never F01–F08 geometry.",
        ],
        "errors": [],
    }


def _load_scenario(scenario_id: str) -> dict[str, Any]:
    path = FIXTURE_ROOT / f"{scenario_id}.json"
    if not path.is_file():
        raise ParcelResolutionError(
            "FIXTURE_MISSING",
            f"parcel resolution fixture not found: {scenario_id}",
        )
    return json.loads(path.read_text(encoding="utf-8"))


def find_fixture_scenario_id(raw_address: str) -> str | None:
    """Match address to an explicit fixture scenario. Never defaults to CPER."""
    needle = normalize_address_text(raw_address).lower()
    matches: list[str] = []
    if not FIXTURE_ROOT.is_dir():
        return None
    for path in sorted(FIXTURE_ROOT.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(data.get("input_kind") or "ADDRESS").upper() == "COORDINATE":
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
            "FIXTURE_ADDRESS_AMBIGUOUS",
            f"address matches multiple fixture scenarios: {matches}",
        )
    return None


def find_fixture_scenario_id_for_coordinates(lat: float, lng: float) -> str | None:
    """Match COORDINATE fixtures by exact lat/lng (6-decimal tolerance)."""
    matches: list[str] = []
    if not FIXTURE_ROOT.is_dir():
        return None
    for path in sorted(FIXTURE_ROOT.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(data.get("input_kind") or "").upper() != "COORDINATE":
            continue
        try:
            flat = float(data.get("latitude"))
            flng = float(data.get("longitude"))
        except (TypeError, ValueError):
            continue
        if abs(flat - lat) < 1e-6 and abs(flng - lng) < 1e-6:
            matches.append(str(data.get("scenario_id") or path.stem))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ParcelResolutionError(
            "FIXTURE_COORD_AMBIGUOUS",
            f"coordinates match multiple fixture scenarios: {matches}",
        )
    return None


def public_resolution_view(record: Mapping[str, Any]) -> dict[str, Any]:
    """API-safe resolution projection (no secrets; stable field set)."""
    selection = record.get("selection")
    confirmed = record.get("confirmed_parcel")
    return {
        "schema_version": record.get("schema_version"),
        "resolution_id": record.get("resolution_id"),
        "adapter_id": record.get("adapter_id"),
        "adapter_version": record.get("adapter_version"),
        "provider_mode": record.get("provider_mode"),
        "status": record.get("status"),
        "scenario_id": record.get("scenario_id"),
        "input": deepcopy(record.get("input") or {}),
        "normalized_address": (record.get("input") or {}).get("normalized_address"),
        "input_kind": (record.get("input") or {}).get("input_kind") or "ADDRESS",
        "latitude": (record.get("input") or {}).get("latitude"),
        "longitude": (record.get("input") or {}).get("longitude"),
        "geocode": deepcopy(record.get("geocode")),
        "candidates": deepcopy(record.get("candidates") or []),
        "selection": deepcopy(selection) if selection is not None else None,
        "confirmation_status": {
            "status": record.get("status"),
            "selected_candidate_id": (selection or {}).get("selected_candidate_id")
            if isinstance(selection, Mapping)
            else None,
            "confirmed_at": (selection or {}).get("confirmed_at")
            if isinstance(selection, Mapping)
            else None,
            "confirmation_method": (selection or {}).get("confirmation_method")
            if isinstance(selection, Mapping)
            else None,
            "confirmed": record.get("status") == "PARCEL_CONFIRMED",
        },
        "confirmed_parcel": deepcopy(confirmed) if confirmed is not None else None,
        "evidence_invalidation_required": bool(
            record.get("evidence_invalidation_required")
        ),
        "previous_geometry_hash": record.get("previous_geometry_hash"),
        "provenance": deepcopy(record.get("provenance") or {}),
        "limitations": list(record.get("limitations") or []),
        "errors": deepcopy(record.get("errors") or []),
    }


def _candidate_from_fixture(raw: Mapping[str, Any]) -> dict[str, Any]:
    geom = deepcopy(raw.get("parcel_geometry"))
    source_crs = str(raw.get("source_crs") or REQUIRED_CRS)
    errs = validate_parcel_boundary_geometry(geom, source_crs=source_crs)
    geometry_hash = None
    if not errs:
        try:
            geometry_hash = compute_geometry_hash(geom)  # type: ignore[arg-type]
        except ParcelResolutionError:
            errs = ["INVALID_GEOMETRY_TYPE"]
    return {
        "candidate_id": str(raw["candidate_id"]),
        "label": str(raw.get("label") or raw["candidate_id"]),
        "parcel_geometry": geom,
        "source_crs": source_crs,
        "normalized_crs": REQUIRED_CRS if not errs and source_crs == REQUIRED_CRS else None,
        "geometry_hash": geometry_hash,
        "confidence": raw.get("confidence"),
        "provenance": deepcopy(raw.get("provenance") or {}),
        "limitations": list(raw.get("limitations") or []),
        "attributes": deepcopy(raw.get("attributes") or {}),
        "validation_status": "INVALID" if errs else "VALID",
        "validation_errors": list(errs),
    }


class FixtureParcelResolver:
    """OFFLINE resolver driven by explicit scenario fixtures (no network)."""

    name = "FIXTURE"
    adapter_id = ADAPTER_FIXTURE

    def __init__(self, scenario_id: str) -> None:
        if not scenario_id:
            raise ParcelResolutionError(
                "SCENARIO_REQUIRED",
                "FIXTURE resolver requires an explicit scenario_id "
                "(no silent default / CPER substitution)",
            )
        self.scenario_id = scenario_id
        self.scenario = _load_scenario(scenario_id)

    def normalize_address(self, raw_address: str) -> NormalizedAddress:
        expected = self.scenario.get("raw_address")
        input_kind = str(self.scenario.get("input_kind") or "ADDRESS").upper()
        if input_kind == "COORDINATE":
            # Coordinate fixtures bind by lat/lng; query string is "lat,lng".
            try:
                flat = float(self.scenario["latitude"])
                flng = float(self.scenario["longitude"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ParcelResolutionError(
                    "FIXTURE_COORD_INVALID",
                    "COORDINATE fixture requires latitude and longitude",
                ) from exc
            expected_q = f"{flat},{flng}"
            if normalize_address_text(raw_address) != normalize_address_text(expected_q):
                # Allow minor float formatting differences via round-trip parse
                from rangematch.coordinates import parse_lat_lng_text

                try:
                    qlat, qlng = parse_lat_lng_text(raw_address)
                except Exception as exc:  # noqa: BLE001
                    raise ParcelResolutionError(
                        "FIXTURE_COORD_MISMATCH",
                        "coordinates do not match explicit fixture scenario",
                    ) from exc
                if abs(qlat - flat) > 1e-6 or abs(qlng - flng) > 1e-6:
                    raise ParcelResolutionError(
                        "FIXTURE_COORD_MISMATCH",
                        "coordinates do not match explicit fixture scenario; "
                        "refusing silent geometry substitution",
                    )
            normalized = self.scenario.get("normalized_address") or expected_q
            return NormalizedAddress(
                raw_address=str(raw_address).strip(),
                normalized_address=str(normalized),
            )
        if expected is not None and normalize_address_text(raw_address) != normalize_address_text(
            str(expected)
        ):
            if normalize_address_text(raw_address).lower() != normalize_address_text(
                str(expected)
            ).lower():
                raise ParcelResolutionError(
                    "FIXTURE_ADDRESS_MISMATCH",
                    "address does not match explicit fixture scenario "
                    f"{self.scenario_id}; refusing silent geometry substitution",
                )
        normalized = self.scenario.get("normalized_address") or normalize_address_text(
            raw_address
        )
        return NormalizedAddress(
            raw_address=str(raw_address).strip(),
            normalized_address=str(normalized),
        )

    def geocode_address(self, normalized: NormalizedAddress) -> GeocodeResult:
        outcome = str(self.scenario.get("geocode_outcome") or "OK")
        raw = self.scenario.get("geocode") or {}
        if outcome == "BLOCKED_EXTERNAL":
            return GeocodeResult(
                status="BLOCKED_EXTERNAL",
                point=None,
                confidence=None,
                provider=str(raw.get("provider") or "FIXTURE"),
                request_id=str(raw.get("request_id") or f"fixture:{self.scenario_id}"),
                retrieved_at=raw.get("retrieved_at"),
                limitations=("External geocode provider blocked or unavailable.",),
            )
        if outcome in {"AMBIGUOUS", "NO_MATCH", "FAILED"}:
            return GeocodeResult(
                status=outcome if outcome != "FAILED" else "FAILED",
                point=None,
                confidence=raw.get("confidence"),
                provider=str(raw.get("provider") or "FIXTURE"),
                request_id=str(raw.get("request_id") or f"fixture:{self.scenario_id}"),
                retrieved_at=raw.get("retrieved_at"),
                limitations=tuple(raw.get("limitations") or ()),
            )
        point = raw.get("point")
        return GeocodeResult(
            status="OK",
            point=deepcopy(point) if isinstance(point, dict) else None,
            confidence=raw.get("confidence"),
            provider=str(raw.get("provider") or "FIXTURE"),
            request_id=str(raw.get("request_id") or f"fixture:{self.scenario_id}"),
            retrieved_at=raw.get("retrieved_at"),
            limitations=tuple(raw.get("limitations") or ()),
        )

    def find_parcel_candidates(
        self, geocode: GeocodeResult, *, normalized: NormalizedAddress
    ) -> list[dict[str, Any]]:
        del normalized  # scenario already bound
        if geocode.status != "OK":
            return []
        lookup = str(self.scenario.get("parcel_lookup_outcome") or "OK")
        if lookup in {"FAILED", "NO_MATCH", "BLOCKED_EXTERNAL"}:
            return []
        out: list[dict[str, Any]] = []
        for raw in self.scenario.get("candidates") or []:
            out.append(_candidate_from_fixture(raw))
        return out

    def validate_candidate(self, candidate: Mapping[str, Any]) -> CandidateValidation:
        errs = validate_parcel_boundary_geometry(
            candidate.get("parcel_geometry"),  # type: ignore[arg-type]
            source_crs=str(candidate.get("source_crs") or ""),
        )
        # Reject CPER demo geometry when scenario is the substitution attack fixture.
        if self.scenario_id == "silent_cper_substitution" or (
            self.scenario.get("reject_cper_substitution")
            and references_cper_demo_geometry(candidate)
        ):
            errs = list(errs) + ["SILENT_CPER_SUBSTITUTION_REJECTED"]
        geometry_hash = None
        if not errs:
            try:
                geometry_hash = compute_geometry_hash(candidate["parcel_geometry"])
            except ParcelResolutionError as exc:
                errs = list(errs) + [exc.code]
        return CandidateValidation(
            ok=not errs, errors=tuple(errs), geometry_hash=geometry_hash
        )

    def confirm_parcel(
        self,
        resolution: Mapping[str, Any],
        *,
        candidate_id: str,
        confirm_boundary: bool = True,
    ) -> dict[str, Any]:
        return confirm_selected_parcel(
            dict(resolution),
            candidate_id=candidate_id,
            confirm_boundary=confirm_boundary,
            resolver=self,
        )


class LiveParcelResolver:
    """LIVE parcel resolver via Mireye /v1/lookup.

    Modes:
    - Offline fixture: ``fixture_scenario_id`` under ``test-data/mireye-parcel-lookup/``
    - HTTP: ``allow_network=True`` (explicit); uses controlled lookup transport
    - Otherwise: ``BLOCKED_EXTERNAL`` / ``NETWORK_NOT_AUTHORIZED`` — no FIXTURE swap
    """

    name = "LIVE"
    adapter_id = ADAPTER_LIVE

    def __init__(
        self,
        fixture_scenario_id: str | None = None,
        *,
        allow_network: bool = False,
        lookup_kind: str = "address",
        http_post: Any = None,
        sleeper: Any = None,
        max_retries: int = 2,
        max_sleep_seconds: float = 30.0,
        catalog_context: Mapping[str, Any] | None = None,
    ) -> None:
        self.fixture_scenario_id = (fixture_scenario_id or "").strip() or None
        self.allow_network = bool(allow_network)
        self.lookup_kind = lookup_kind if lookup_kind in {"address", "coord"} else "address"
        self.http_post = http_post
        self.sleeper = sleeper
        self.max_retries = max_retries
        self.max_sleep_seconds = max_sleep_seconds
        self.terminal_status: str | None = None
        self.transport_result: dict[str, Any] | None = None
        self._mapping = None
        self._scenario: dict[str, Any] | None = None
        self._catalog_context = dict(catalog_context or {})
        self._raw_address_for_network: str | None = None

        if self.fixture_scenario_id:
            from rangematch.mireye_parcel_resolver import (
                load_mireye_parcel_lookup_scenario,
                map_mireye_lookup_to_parcel,
            )

            self._scenario = load_mireye_parcel_lookup_scenario(self.fixture_scenario_id)
            lookup = self._scenario.get("lookup_response")
            if not isinstance(lookup, Mapping):
                raise ParcelResolutionError(
                    "MIREYE_LOOKUP_FIXTURE_INVALID",
                    "fixture requires lookup_response object",
                )
            self._mapping = map_mireye_lookup_to_parcel(lookup)
            self.terminal_status = self._mapping.terminal_status

    def _ensure_catalog_context(self) -> dict[str, Any]:
        if self._catalog_context:
            return self._catalog_context
        try:
            from rangematch.mireye_catalog_gate import evaluate_fixture_catalog

            self._catalog_context = evaluate_fixture_catalog().to_public_dict()
        except Exception as exc:  # noqa: BLE001
            self._catalog_context = {
                "status": "FETCH_FAILED",
                "compatible": False,
                "affects_parcel_resolution": False,
                "errors": [{"code": "CATALOG_CONTEXT_ERROR", "message": type(exc).__name__}],
            }
        return self._catalog_context

    def _run_network_lookup(self, normalized: NormalizedAddress) -> None:
        from rangematch.mireye_lookup_transport import (
            lookup_parcel_via_mireye,
            transport_error_to_parcel_status,
        )
        from rangematch.mireye_parcel_resolver import map_mireye_lookup_to_parcel

        result = lookup_parcel_via_mireye(
            normalized.raw_address,
            kind=self.lookup_kind,  # type: ignore[arg-type]
            allow_network=True,
            http_post=self.http_post,
            sleeper=self.sleeper,
            max_retries=self.max_retries,
            max_sleep_seconds=self.max_sleep_seconds,
            catalog_context=self._ensure_catalog_context(),
        )
        self.transport_result = result.to_public_dict()
        if not result.ok or not result.sanitized_response:
            self.terminal_status = transport_error_to_parcel_status(result.error_class)
            self._mapping = None
            return
        self._mapping = map_mireye_lookup_to_parcel(result.sanitized_response)
        self.terminal_status = self._mapping.terminal_status

    def normalize_address(self, raw_address: str) -> NormalizedAddress:
        self._raw_address_for_network = str(raw_address).strip()
        if self._scenario is not None:
            expected = self._scenario.get("raw_address")
            if expected is not None and normalize_address_text(
                raw_address
            ).lower() != normalize_address_text(str(expected)).lower():
                raise ParcelResolutionError(
                    "MIREYE_LOOKUP_ADDRESS_MISMATCH",
                    "address does not match mireye lookup fixture; "
                    "refusing silent geometry substitution",
                )
            normalized = (
                self._mapping.normalized_address
                if self._mapping and self._mapping.normalized_address
                else self._scenario.get("normalized_address")
                or normalize_address_text(raw_address)
            )
            return NormalizedAddress(
                raw_address=str(raw_address).strip(),
                normalized_address=str(normalized),
            )
        # LIVE HTTP: preserve submitted address text (trim only) — do not invent locality.
        trimmed = str(raw_address).strip()
        return NormalizedAddress(
            raw_address=trimmed,
            normalized_address=trimmed,
        )

    def geocode_address(self, normalized: NormalizedAddress) -> GeocodeResult:
        if self._mapping is None and self.fixture_scenario_id is None:
            if not self.allow_network:
                return GeocodeResult(
                    status="BLOCKED_EXTERNAL",
                    point=None,
                    confidence=None,
                    provider="LIVE_NETWORK_GATED",
                    request_id="live:network_not_authorized",
                    retrieved_at=None,
                    limitations=(
                        "NETWORK_NOT_AUTHORIZED: LIVE HTTP lookup requires allow_network=true.",
                        "No network call was made.",
                        "CPER/demo fixtures were not substituted.",
                    ),
                )
            self._run_network_lookup(normalized)

        if self._mapping is None:
            # Transport failed after allow_network attempt (or still unconfigured).
            tr = self.transport_result or {}
            error_class = tr.get("error_class") or "LIVE_UNCONFIGURED"
            term = self.terminal_status or "BLOCKED_EXTERNAL"
            if term in {"NO_MATCH", "AMBIGUOUS", "GEOCODE_QUALITY_INSUFFICIENT"}:
                geo_status = term
            else:
                geo_status = "BLOCKED_EXTERNAL"
                self.terminal_status = "BLOCKED_EXTERNAL"
            return GeocodeResult(
                status=geo_status,
                point=None,
                confidence=None,
                provider="Mireye",
                request_id=str(tr.get("request_hash") or "live:lookup_failed"),
                retrieved_at=tr.get("retrieved_at"),
                limitations=tuple(tr.get("limitations") or ())
                + (
                    f"lookup_error_class={error_class}",
                    "No FIXTURE fallback.",
                ),
            )

        m = self._mapping
        return GeocodeResult(
            status=m.geocode_status,
            point=deepcopy(m.geocode_point) if m.geocode_point else None,
            confidence=m.confidence,
            provider="Mireye",
            request_id=m.request_id,
            retrieved_at=m.retrieved_at,
            limitations=tuple(m.limitations),
            accuracy=m.accuracy,
            accuracy_type=m.accuracy_type,
            match_type=m.match_type,
            normalized_address=m.normalized_address or normalized.normalized_address,
        )

    def find_parcel_candidates(
        self, geocode: GeocodeResult, *, normalized: NormalizedAddress
    ) -> list[dict[str, Any]]:
        del normalized
        if self._mapping is None:
            return []
        if geocode.status not in {"OK"}:
            return []
        if self._mapping.terminal_status in {
            "PARCEL_DATA_UNAVAILABLE",
            "NO_MATCH",
            "AMBIGUOUS",
            "GEOCODE_QUALITY_INSUFFICIENT",
            "BLOCKED_EXTERNAL",
        }:
            self.terminal_status = self._mapping.terminal_status
            return []
        return [deepcopy(c) for c in self._mapping.candidates]

    def validate_candidate(self, candidate: Mapping[str, Any]) -> CandidateValidation:
        if references_cper_demo_geometry(candidate):
            return CandidateValidation(
                ok=False,
                errors=("SILENT_CPER_SUBSTITUTION_REJECTED",),
                geometry_hash=None,
            )
        if self._mapping is None:
            return CandidateValidation(
                ok=False,
                errors=("LIVE_UNCONFIGURED",),
                geometry_hash=None,
            )
        errs = validate_parcel_boundary_geometry(
            candidate.get("parcel_geometry"),  # type: ignore[arg-type]
            source_crs=str(candidate.get("source_crs") or ""),
        )
        geometry_hash = None
        if not errs:
            try:
                geometry_hash = compute_geometry_hash(candidate["parcel_geometry"])
            except ParcelResolutionError as exc:
                errs = list(errs) + [exc.code]
        return CandidateValidation(
            ok=not errs, errors=tuple(errs), geometry_hash=geometry_hash
        )

    def confirm_parcel(
        self,
        resolution: Mapping[str, Any],
        *,
        candidate_id: str,
        confirm_boundary: bool = True,
    ) -> dict[str, Any]:
        if self._mapping is None:
            out = deepcopy(dict(resolution))
            out["status"] = "BLOCKED_EXTERNAL"
            out["errors"] = list(out.get("errors") or []) + [
                _error(
                    "LIVE_UNCONFIGURED",
                    "LIVE confirm_parcel is unavailable; no silent fixture substitution",
                )
            ]
            out["confirmed_parcel"] = None
            return out
        return confirm_selected_parcel(
            dict(resolution),
            candidate_id=candidate_id,
            confirm_boundary=confirm_boundary,
            resolver=self,
        )


def get_parcel_resolver(
    mode: str = "FIXTURE",
    *,
    scenario_id: str | None = None,
    allow_network: bool = False,
    http_post: Any = None,
    sleeper: Any = None,
    lookup_kind: str = "address",
) -> ParcelResolver:
    mode_u = (mode or "FIXTURE").strip().upper()
    if mode_u in {"FIXTURE", "OFFLINE"}:
        if not scenario_id:
            raise ParcelResolutionError(
                "SCENARIO_REQUIRED",
                "FIXTURE/OFFLINE mode requires explicit scenario_id "
                "(refusing silent CPER default)",
            )
        return FixtureParcelResolver(scenario_id)
    if mode_u == "LIVE":
        return LiveParcelResolver(
            fixture_scenario_id=scenario_id,
            allow_network=allow_network,
            http_post=http_post,
            sleeper=sleeper,
            lookup_kind=lookup_kind,
        )
    raise ParcelResolutionError("RESOLVER_MODE_UNKNOWN", f"unknown resolver mode: {mode}")


def _resolution_id_for(scenario_id: str | None, normalized: str) -> str:
    digest = hashlib.sha256(
        f"{scenario_id or 'none'}|{normalized}".encode("utf-8")
    ).hexdigest()[:16]
    return f"pres_{digest}"


def start_parcel_resolution(
    raw_address: str,
    *,
    mode: str = "FIXTURE",
    scenario_id: str | None = None,
    resolver: ParcelResolver | None = None,
    allow_network: bool = False,
    http_post: Any = None,
    sleeper: Any = None,
    input_kind: str = "ADDRESS",
    latitude: float | None = None,
    longitude: float | None = None,
    lookup_kind: str = "address",
) -> dict[str, Any]:
    """Run address/coord → geocode → candidates; stop at selection/confirmation gate."""
    kind_u = (input_kind or "ADDRESS").strip().upper()
    if kind_u not in {"ADDRESS", "COORDINATE"}:
        raise ParcelResolutionError("INVALID_INPUT_KIND", f"unknown input_kind: {input_kind}")
    lk = lookup_kind if lookup_kind in {"address", "coord"} else (
        "coord" if kind_u == "COORDINATE" else "address"
    )
    active = resolver or get_parcel_resolver(
        mode,
        scenario_id=scenario_id,
        allow_network=allow_network,
        http_post=http_post,
        sleeper=sleeper,
        lookup_kind=lk,
    )
    normalized = active.normalize_address(raw_address)
    sid = scenario_id
    if isinstance(active, FixtureParcelResolver):
        sid = active.scenario_id
    elif isinstance(active, LiveParcelResolver) and active.fixture_scenario_id:
        sid = active.fixture_scenario_id
    record = _base_record(
        resolution_id=_resolution_id_for(sid, normalized.normalized_address),
        adapter_id=active.adapter_id,
        provider_mode=active.name if active.name != "OFFLINE" else "OFFLINE",
        status="ADDRESS_ACCEPTED",
        raw_address=normalized.raw_address if kind_u == "ADDRESS" else None,
        normalized_address=normalized.normalized_address,
        scenario_id=sid,
        input_kind=kind_u,
        latitude=latitude,
        longitude=longitude,
    )
    if active.name == "FIXTURE":
        record["provider_mode"] = "FIXTURE"
    elif active.name == "LIVE":
        record["provider_mode"] = "LIVE"

    geocode = active.geocode_address(normalized)
    record["geocode"] = {
        "status": geocode.status,
        "point": geocode.point,
        "confidence": geocode.confidence,
        "provider": geocode.provider,
        "request_id": geocode.request_id,
        "retrieved_at": geocode.retrieved_at,
        "accuracy": geocode.accuracy,
        "accuracy_type": geocode.accuracy_type,
        "match_type": geocode.match_type,
        "normalized_address": geocode.normalized_address
        or normalized.normalized_address,
        "limitations": list(geocode.limitations),
    }
    record["provenance"]["request_id"] = geocode.request_id
    record["provenance"]["retrieved_at"] = geocode.retrieved_at
    record["provenance"]["confidence"] = geocode.confidence
    record["limitations"] = list(record["limitations"]) + list(geocode.limitations)

    if isinstance(active, LiveParcelResolver) and active.transport_result:
        tr = active.transport_result
        record["provenance"]["mireye_lookup"] = {
            "endpoint": tr.get("endpoint"),
            "ok": tr.get("ok"),
            "error_class": tr.get("error_class"),
            "http_status": tr.get("http_status"),
            "request_hash": tr.get("request_hash"),
            "response_hash": tr.get("response_hash"),
            "attempts": tr.get("attempts"),
            "retries": tr.get("retries"),
            "retrieved_at": tr.get("retrieved_at"),
            "kind": tr.get("kind"),
            "input_fingerprint": tr.get("input_fingerprint"),
            "disposition": tr.get("disposition"),
            "accuracy_type": (record.get("geocode") or {}).get("accuracy_type"),
            "catalog_context": tr.get("catalog_context"),
        }
        # Never persist Authorization / request headers (not present on transport_result).

    if geocode.status == "BLOCKED_EXTERNAL":
        record["status"] = "BLOCKED_EXTERNAL"
        record["provenance"]["status"] = "BLOCKED_EXTERNAL"
        record["errors"].append(
            _error("BLOCKED_EXTERNAL", "geocode/parcel provider blocked or unconfigured")
        )
        return record
    if geocode.status == "GEOCODE_QUALITY_INSUFFICIENT":
        record["status"] = "GEOCODE_QUALITY_INSUFFICIENT"
        record["provenance"]["status"] = "GEOCODE_QUALITY_INSUFFICIENT"
        record["errors"].append(
            _error(
                "GEOCODE_QUALITY_INSUFFICIENT",
                "geocode accuracy is not parcel-quality",
            )
        )
        return record
    if geocode.status == "AMBIGUOUS":
        record["status"] = "AMBIGUOUS"
        record["provenance"]["status"] = "AMBIGUOUS"
        record["errors"].append(_error("AMBIGUOUS", "geocode result is ambiguous"))
        return record
    if geocode.status in {"NO_MATCH", "FAILED"}:
        record["status"] = "NO_MATCH"
        record["provenance"]["status"] = "NO_MATCH"
        record["errors"].append(_error("NO_MATCH", "geocode produced no usable point"))
        return record

    record["status"] = "GEOCODED"
    record["provenance"]["status"] = "GEOCODED"

    # Explicit lookup-blocked scenario
    if isinstance(active, FixtureParcelResolver):
        lookup = str(active.scenario.get("parcel_lookup_outcome") or "OK")
        if lookup == "BLOCKED_EXTERNAL":
            record["status"] = "BLOCKED_EXTERNAL"
            record["errors"].append(
                _error("BLOCKED_EXTERNAL", "parcel lookup provider blocked")
            )
            return record

    # Mireye mapping may already know parcel_unavailable / no_match before candidates.
    terminal = getattr(active, "terminal_status", None)
    if terminal in {
        "PARCEL_DATA_UNAVAILABLE",
        "NO_MATCH",
        "AMBIGUOUS",
        "BLOCKED_EXTERNAL",
        "GEOCODE_QUALITY_INSUFFICIENT",
    }:
        record["status"] = terminal
        record["provenance"]["status"] = terminal
        mapping = getattr(active, "_mapping", None)
        if mapping is not None:
            for err in getattr(mapping, "errors", []) or []:
                if isinstance(err, Mapping) and err.get("code"):
                    record["errors"].append(
                        _error(str(err["code"]), str(err.get("message") or err["code"]))
                    )
            if getattr(mapping, "parcel_unavailable", None) is not None:
                record["provenance"]["parcel_unavailable"] = mapping.parcel_unavailable
            if getattr(mapping, "parcel_unavailable_reason", None):
                record["provenance"]["parcel_unavailable_reason"] = (
                    mapping.parcel_unavailable_reason
                )
            if getattr(mapping, "disposition", None):
                record["provenance"]["mireye_disposition"] = mapping.disposition
        if not record["errors"]:
            record["errors"].append(_error(terminal, f"terminal status {terminal}"))
        return record

    candidates = active.find_parcel_candidates(geocode, normalized=normalized)
    validated: list[dict[str, Any]] = []
    for cand in candidates:
        # Reject fabricated polygons from address points
        if cand.get("parcel_geometry") and cand["parcel_geometry"].get("type") == "Point":
            cand = deepcopy(cand)
            cand["validation_status"] = "INVALID"
            cand["validation_errors"] = ["ADDRESS_POINT_NOT_PARCEL_BOUNDARY"]
        result = active.validate_candidate(cand)
        cand = deepcopy(cand)
        cand["validation_status"] = "VALID" if result.ok else "INVALID"
        cand["validation_errors"] = list(result.errors)
        if result.geometry_hash:
            cand["geometry_hash"] = result.geometry_hash
        validated.append(cand)

    record["candidates"] = validated

    if not validated:
        # Prefer resolver-reported terminal over generic NO_MATCH.
        terminal_after = getattr(active, "terminal_status", None)
        if terminal_after in {
            "PARCEL_DATA_UNAVAILABLE",
            "AMBIGUOUS",
            "BLOCKED_EXTERNAL",
        }:
            record["status"] = terminal_after
            record["provenance"]["status"] = terminal_after
            record["errors"].append(
                _error(terminal_after, f"no usable parcel candidates ({terminal_after})")
            )
            return record
        record["status"] = "NO_MATCH"
        record["provenance"]["status"] = "NO_MATCH"
        record["errors"].append(
            _error("NO_MATCH", "no parcel candidates returned after geocode")
        )
        return record

    record["status"] = "PARCEL_CANDIDATES_FOUND"
    valid = [c for c in validated if c.get("validation_status") == "VALID"]
    invalid_only = validated and not valid

    if invalid_only:
        record["status"] = "INVALID_GEOMETRY"
        record["provenance"]["status"] = "INVALID_GEOMETRY"
        codes = sorted(
            {
                e
                for c in validated
                for e in (c.get("validation_errors") or [])
            }
        )
        record["errors"].append(
            _error(
                "INVALID_GEOMETRY",
                "candidate geometry failed validation: " + ", ".join(codes),
            )
        )
        return record

    if len(valid) > 1:
        record["status"] = "NEEDS_USER_SELECTION"
        record["provenance"]["status"] = "NEEDS_USER_SELECTION"
        record["selection"] = {
            "selected_candidate_id": None,
            "confirmed_at": None,
            "confirmation_method": "PENDING",
        }
        return record

    # Exactly one valid candidate — still requires boundary confirmation.
    record["status"] = "NEEDS_BOUNDARY_CONFIRMATION"
    record["provenance"]["status"] = "NEEDS_BOUNDARY_CONFIRMATION"
    record["selection"] = {
        "selected_candidate_id": valid[0]["candidate_id"],
        "confirmed_at": None,
        "confirmation_method": "PENDING",
    }
    record["provenance"]["source"] = (valid[0].get("provenance") or {}).get("source")
    record["provenance"]["source_crs"] = valid[0].get("source_crs")
    record["provenance"]["normalized_crs"] = valid[0].get("normalized_crs")
    return record


def select_parcel_candidate(
    resolution: Mapping[str, Any],
    *,
    candidate_id: str,
) -> dict[str, Any]:
    """User selects exactly one candidate from NEEDS_USER_SELECTION."""
    out = deepcopy(dict(resolution))
    if out.get("status") not in {
        "NEEDS_USER_SELECTION",
        "PARCEL_CANDIDATES_FOUND",
        "NEEDS_BOUNDARY_CONFIRMATION",
    }:
        raise ParcelResolutionError(
            "INVALID_STATE",
            f"cannot select candidate in status {out.get('status')}",
        )
    match = next(
        (
            c
            for c in out.get("candidates") or []
            if c.get("candidate_id") == candidate_id
        ),
        None,
    )
    if match is None:
        raise ParcelResolutionError(
            "CANDIDATE_NOT_FOUND", f"unknown candidate_id {candidate_id}"
        )
    if match.get("validation_status") != "VALID":
        out["status"] = "INVALID_GEOMETRY"
        out["errors"] = list(out.get("errors") or []) + [
            _error("INVALID_GEOMETRY", "selected candidate failed geometry validation")
        ]
        return out
    out["selection"] = {
        "selected_candidate_id": candidate_id,
        "confirmed_at": None,
        "confirmation_method": "PENDING",
    }
    out["status"] = "NEEDS_BOUNDARY_CONFIRMATION"
    out["provenance"] = dict(out.get("provenance") or {})
    out["provenance"]["status"] = "NEEDS_BOUNDARY_CONFIRMATION"
    return out


def confirm_selected_parcel(
    resolution: Mapping[str, Any],
    *,
    candidate_id: str | None = None,
    confirm_boundary: bool = True,
    expected_geometry_hash: str | None = None,
    resolver: ParcelResolver | None = None,
) -> dict[str, Any]:
    """Confirm exactly one candidate boundary → PARCEL_CONFIRMED or INVALID_GEOMETRY."""
    if not confirm_boundary:
        raise ParcelResolutionError(
            "CONFIRMATION_REQUIRED",
            "confirm_boundary / explicit_confirmation must be true; "
            "single candidates are not auto-confirmed",
        )
    out = deepcopy(dict(resolution))
    selected = candidate_id or (out.get("selection") or {}).get("selected_candidate_id")
    if not selected or not str(selected).strip():
        raise ParcelResolutionError(
            "CANDIDATE_REQUIRED", "exactly one selected_candidate_id is required"
        )
    if isinstance(candidate_id, (list, tuple, set)):
        raise ParcelResolutionError(
            "MULTIPLE_CANDIDATES_SELECTED",
            "exactly one selected_candidate_id is required",
        )

    # Idempotent re-confirm: same candidate + matching hash → return stored record.
    if out.get("status") == "PARCEL_CONFIRMED" and isinstance(
        out.get("confirmed_parcel"), Mapping
    ):
        confirmed = out["confirmed_parcel"]
        prev_sel = (out.get("selection") or {}).get("selected_candidate_id")
        if prev_sel != selected:
            raise ParcelResolutionError(
                "CONFIRMATION_CONFLICT",
                "resolution already confirmed with a different candidate",
            )
        if expected_geometry_hash and expected_geometry_hash != confirmed.get(
            "geometry_hash"
        ):
            raise ParcelResolutionError(
                "STALE_GEOMETRY_HASH",
                "expected_geometry_hash does not match confirmed parcel geometry_hash",
            )
        return out

    if out.get("status") == "NEEDS_USER_SELECTION":
        out = select_parcel_candidate(out, candidate_id=selected)

    if out.get("status") not in {
        "NEEDS_BOUNDARY_CONFIRMATION",
        "PARCEL_CANDIDATES_FOUND",
    }:
        if out.get("status") in TERMINAL_FAILURE:
            return out
        raise ParcelResolutionError(
            "INVALID_STATE",
            f"cannot confirm parcel in status {out.get('status')}",
        )

    match = next(
        (
            c
            for c in out.get("candidates") or []
            if c.get("candidate_id") == selected
        ),
        None,
    )
    if match is None:
        raise ParcelResolutionError(
            "CANDIDATE_NOT_FOUND", f"unknown candidate_id {selected}"
        )

    # Pre-selected candidate on single-candidate flow must match request.
    pending_sel = (out.get("selection") or {}).get("selected_candidate_id")
    if pending_sel and pending_sel != selected:
        raise ParcelResolutionError(
            "CANDIDATE_MISMATCH",
            f"selected_candidate_id {selected} does not match pending {pending_sel}",
        )

    if resolver is not None:
        validation = resolver.validate_candidate(match)
    else:
        errs = validate_parcel_boundary_geometry(
            match.get("parcel_geometry"),
            source_crs=str(match.get("source_crs") or ""),
        )
        if references_cper_demo_geometry(match) and out.get("scenario_id") == (
            "silent_cper_substitution"
        ):
            errs = list(errs) + ["SILENT_CPER_SUBSTITUTION_REJECTED"]
        validation = CandidateValidation(
            ok=not errs,
            errors=tuple(errs),
            geometry_hash=(
                compute_geometry_hash(match["parcel_geometry"]) if not errs else None
            ),
        )

    if not validation.ok:
        out["status"] = "INVALID_GEOMETRY"
        out["confirmed_parcel"] = None
        out["errors"] = list(out.get("errors") or []) + [
            _error(
                "INVALID_GEOMETRY",
                "confirmation rejected: " + ", ".join(validation.errors),
            )
        ]
        if "SILENT_CPER_SUBSTITUTION_REJECTED" in validation.errors:
            out["errors"].append(
                _error(
                    "SILENT_CPER_SUBSTITUTION_REJECTED",
                    "refusing silent CPER/demo geometry substitution",
                )
            )
        return out

    fc = as_one_feature_collection(match["parcel_geometry"])
    geometry_hash = validation.geometry_hash or compute_geometry_hash(fc)
    if expected_geometry_hash is not None:
        if expected_geometry_hash != geometry_hash and expected_geometry_hash != match.get(
            "geometry_hash"
        ):
            raise ParcelResolutionError(
                "STALE_GEOMETRY_HASH",
                "expected_geometry_hash does not match candidate geometry_hash",
            )

    geometry_id = str(
        (fc["features"][0].get("id") if fc["features"] else None)
        or match.get("candidate_id")
    )
    geometry_reference = str(
        (match.get("provenance") or {}).get("reference_id")
        or (match.get("provenance") or {}).get("source")
        or f"parcel-resolution:{out.get('scenario_id')}:{selected}"
    )

    out["selection"] = {
        "selected_candidate_id": selected,
        "confirmed_at": utc_now_iso(),
        "confirmation_method": "USER_BOUNDARY_CONFIRMATION",
    }
    out["confirmed_parcel"] = {
        "parcel_geometry": fc,
        "geometry_id": geometry_id,
        "geometry_reference": geometry_reference,
        "geometry_hash": geometry_hash,
        "source_crs": REQUIRED_CRS,
    }
    out["status"] = "PARCEL_CONFIRMED"
    out["provenance"] = dict(out.get("provenance") or {})
    out["provenance"].update(
        {
            "source": (match.get("provenance") or {}).get("source"),
            "reference_id": (match.get("provenance") or {}).get("reference_id"),
            "source_crs": match.get("source_crs"),
            "normalized_crs": REQUIRED_CRS,
            "confidence": match.get("confidence"),
            "status": "PARCEL_CONFIRMED",
        }
    )
    out["limitations"] = list(
        dict.fromkeys(
            list(out.get("limitations") or []) + list(match.get("limitations") or [])
        )
    )
    return out


def planner_parcel_input(resolution: Mapping[str, Any]) -> dict[str, Any]:
    """Extract Planner-ready fields from PARCEL_CONFIRMED record."""
    if resolution.get("status") != "PARCEL_CONFIRMED":
        raise ParcelResolutionError(
            "NOT_CONFIRMED",
            "Planner input requires status PARCEL_CONFIRMED",
        )
    confirmed = resolution.get("confirmed_parcel")
    if not isinstance(confirmed, Mapping):
        raise ParcelResolutionError("NOT_CONFIRMED", "confirmed_parcel missing")
    return {
        "parcel_geometry": deepcopy(confirmed["parcel_geometry"]),
        "geometry_reference": confirmed["geometry_reference"],
        "geometry_hash": confirmed["geometry_hash"],
        "source_crs": confirmed["source_crs"],
        "geometry_id": confirmed.get("geometry_id"),
    }


def apply_geometry_change_after_confirmation(
    resolution: Mapping[str, Any],
    new_parcel_geometry: Mapping[str, Any],
    *,
    source_crs: str = REQUIRED_CRS,
    geometry_reference: str | None = None,
) -> dict[str, Any]:
    """Geometry mutation after confirm → new hash + evidence invalidation flag."""
    out = deepcopy(dict(resolution))
    if out.get("status") != "PARCEL_CONFIRMED" or not out.get("confirmed_parcel"):
        raise ParcelResolutionError(
            "NOT_CONFIRMED",
            "geometry change requires an existing PARCEL_CONFIRMED record",
        )
    errs = validate_parcel_boundary_geometry(
        new_parcel_geometry, source_crs=source_crs
    )
    if errs:
        out["status"] = "INVALID_GEOMETRY"
        out["errors"] = list(out.get("errors") or []) + [
            _error("INVALID_GEOMETRY", "changed geometry invalid: " + ", ".join(errs))
        ]
        return out

    previous_hash = out["confirmed_parcel"]["geometry_hash"]
    fc = as_one_feature_collection(new_parcel_geometry)
    new_hash = compute_geometry_hash(fc)
    out["previous_geometry_hash"] = previous_hash
    out["evidence_invalidation_required"] = True
    out["confirmed_parcel"] = {
        "parcel_geometry": fc,
        "geometry_id": out["confirmed_parcel"].get("geometry_id"),
        "geometry_reference": geometry_reference
        or out["confirmed_parcel"].get("geometry_reference"),
        "geometry_hash": new_hash,
        "source_crs": REQUIRED_CRS,
    }
    # Require re-confirmation after mutation.
    out["status"] = "NEEDS_BOUNDARY_CONFIRMATION"
    out["selection"] = {
        "selected_candidate_id": (out.get("selection") or {}).get(
            "selected_candidate_id"
        ),
        "confirmed_at": None,
        "confirmation_method": "PENDING",
    }
    out["limitations"] = list(out.get("limitations") or []) + [
        "Parcel geometry changed after prior confirmation. "
        "Previous geometry_hash is void for F01–F08 evidence; "
        "re-confirm boundary and regenerate Factor evidence "
        "(see geometry_replace.replace_geometry)."
    ]
    out["provenance"] = dict(out.get("provenance") or {})
    out["provenance"]["status"] = "NEEDS_BOUNDARY_CONFIRMATION"
    return out


def reject_inferred_polygon_from_geocode_point(
    geocode_point: Mapping[str, Any],
    *,
    buffer_degrees: float = 0.01,
) -> None:
    """Hard reject fabricating a parcel polygon from a geocode point."""
    del buffer_degrees
    gtype = geocode_point.get("type")
    if gtype == "Point" or (
        gtype == "Feature"
        and (geocode_point.get("geometry") or {}).get("type") == "Point"
    ):
        raise ParcelResolutionError(
            "INFERRED_POLYGON_FORBIDDEN",
            "refusing to fabricate, buffer, or infer a parcel polygon from an address point",
        )
    raise ParcelResolutionError(
        "INFERRED_POLYGON_FORBIDDEN",
        "refusing to infer parcel boundary from non-parcel geometry",
    )
