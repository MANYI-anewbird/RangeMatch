"""Mireye Field Catalog compatibility gate (public GET /v1/meta/fields).

Offline-first: evaluate a catalog body / fixture without network.
Live fetch is optional and gated — catalog failure is NEVER a parcel failure.

Contract: docs/MIREYE_LIVE_PARCEL_RESOLVER_CONTRACT.md §7
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from rangematch.mireye_adapter import (
    MireyeAdapterError,
    _bypass_env_proxy_flag,
    _env_base_url,
    assert_no_credentials,
    sanitize_for_storage,
)
from rangematch.mireye_transport import (
    classify_tls_failure,
    mireye_urlopen,
    probe_plaintext_http_on_443,
    redact_transport_message,
)

ENDPOINT_META_FIELDS = "/v1/meta/fields"
PINNED_CATALOG_VERSION = "0.14.0"
GATE_ID = "MIREYE_FIELD_CATALOG_COMPATIBILITY_GATE"
GATE_VERSION = "0.1.0"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE_PATH = REPO_ROOT / "mireye" / "fixtures" / "field_catalog_v0.14.0.json"

CatalogGateStatus = Literal[
    "COMPATIBLE",
    "NOT_MODIFIED",
    "INCOMPATIBLE",
    "FETCH_FAILED",
    "NOT_PROBED",
]


@dataclass(frozen=True)
class RequiredFieldSpec:
    name: str
    expected_type: str | None = None
    expected_unit: str | None = None


# Required point-context fields from docs/MIREYE_FIELD_USAGE_REGISTRY.yaml,
# pinned against catalog v0.14.0 units/types.
REQUIRED_FIELDS: tuple[RequiredFieldSpec, ...] = (
    RequiredFieldSpec("elevation", "float", "meters"),
    RequiredFieldSpec("slope_degrees", "float", "degrees"),
    RequiredFieldSpec("aspect_degrees", "float", "degrees"),
    RequiredFieldSpec("aspect_cardinal", "string", None),
    RequiredFieldSpec("lcms_class", "string", None),
    RequiredFieldSpec("land_use_class", "string", None),
    RequiredFieldSpec("intersects_nhd_area", "bool", None),
    RequiredFieldSpec("nearest_flowline_name", "string", None),
    RequiredFieldSpec("nearest_waterbody_name", "string", None),
    RequiredFieldSpec("nearest_groundwater_well_depth_to_water_m", "float", "meters"),
    RequiredFieldSpec("nearest_usgs_gage_name", "string", None),
    RequiredFieldSpec("nearest_usgs_gage_distance_m", "float", "meters"),
    RequiredFieldSpec(
        "nearest_usgs_gage_daily_discharge_cfs", "float", "cubic feet per second"
    ),
    RequiredFieldSpec("surface_water_permanence_pct", "float", "percent"),
    RequiredFieldSpec("soil_drainage_class", "string", None),
    RequiredFieldSpec("soil_hydrologic_group", "string", None),
    RequiredFieldSpec("soil_map_unit_name", "string", None),
    RequiredFieldSpec("soil_available_water_capacity", "float", "cm/cm"),
    RequiredFieldSpec("soil_ponding_frequency_class", "string", None),
    RequiredFieldSpec("soil_restrictive_layer_depth_cm", "float", "cm"),
    RequiredFieldSpec("soil_restrictive_layer_kind", "string", None),
    RequiredFieldSpec("drought_category", "string", None),
    RequiredFieldSpec("mean_annual_dry_bulb_temperature_degc", "float", "degC"),
    RequiredFieldSpec("days_above_32c_annual_count", "int", "days"),
    RequiredFieldSpec("tree_canopy_pct", "float", "percent"),
    RequiredFieldSpec("ndvi_current", "float", None),
)


@dataclass
class CatalogGateResult:
    gate_id: str = GATE_ID
    gate_version: str = GATE_VERSION
    status: CatalogGateStatus = "NOT_PROBED"
    compatible: bool = False
    pinned_catalog_version: str = PINNED_CATALOG_VERSION
    observed_catalog_version: str | None = None
    pinned_major: int | None = None
    observed_major: int | None = None
    etag: str | None = None
    previous_etag: str | None = None
    http_status: int | None = None
    field_count: int | None = None
    missing_fields: list[str] = field(default_factory=list)
    unit_mismatches: list[dict[str, Any]] = field(default_factory=list)
    type_mismatches: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    # Explicit separation from parcel resolution.
    affects_parcel_resolution: bool = False

    def to_public_dict(self) -> dict[str, Any]:
        return asdict(self)


class CatalogGateError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}:{message}")


def parse_major_version(version: str | None) -> int | None:
    if version is None or str(version).strip() == "":
        return None
    text = str(version).strip().lstrip("vV")
    head = text.split(".", 1)[0]
    if not head.isdigit():
        return None
    return int(head)


def load_catalog_fixture(path: Path | None = None) -> dict[str, Any]:
    target = path or DEFAULT_FIXTURE_PATH
    if not target.is_file():
        raise CatalogGateError(
            "CATALOG_FIXTURE_MISSING",
            f"field catalog fixture not found: {target}",
        )
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CatalogGateError("CATALOG_FIXTURE_INVALID", "catalog fixture must be object")
    assert_no_credentials(data, label=str(target))
    return data


def _index_fields(catalog: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    fields = catalog.get("fields")
    if not isinstance(fields, list):
        raise CatalogGateError("CATALOG_INVALID", "catalog.fields must be an array")
    out: dict[str, dict[str, Any]] = {}
    for item in fields:
        if not isinstance(item, Mapping):
            continue
        name = item.get("name")
        if isinstance(name, str) and name:
            out[name] = dict(item)
    return out


def _units_equal(expected: str | None, observed: Any) -> bool:
    if expected is None:
        return observed is None or observed == "" or observed == "null"
    if observed is None:
        return False
    return str(observed).strip() == str(expected).strip()


def evaluate_catalog_compatibility(
    catalog: Mapping[str, Any],
    *,
    etag: str | None = None,
    previous_etag: str | None = None,
    http_status: int | None = None,
    pinned_version: str = PINNED_CATALOG_VERSION,
    required_fields: Sequence[RequiredFieldSpec] = REQUIRED_FIELDS,
) -> CatalogGateResult:
    """Evaluate a catalog JSON body. Does not perform network I/O."""
    result = CatalogGateResult(
        pinned_catalog_version=pinned_version,
        pinned_major=parse_major_version(pinned_version),
        etag=etag,
        previous_etag=previous_etag,
        http_status=http_status,
        limitations=[
            "Catalog compatibility is independent of parcel resolution status.",
            "Catalog failure must not be rewritten as NO_MATCH / PARCEL_DATA_UNAVAILABLE.",
            f"Pinned baseline catalog version: {pinned_version}.",
        ],
        affects_parcel_resolution=False,
    )

    if http_status == 304:
        result.status = "NOT_MODIFIED"
        result.compatible = True
        result.observed_catalog_version = pinned_version
        result.observed_major = parse_major_version(pinned_version)
        result.limitations.append("HTTP 304 Not Modified — prior ETag still valid.")
        return result

    try:
        by_name = _index_fields(catalog)
    except CatalogGateError as exc:
        result.status = "INCOMPATIBLE"
        result.compatible = False
        result.errors.append({"code": exc.code, "message": exc.message})
        return result

    result.field_count = len(by_name)
    observed_version = catalog.get("version")
    result.observed_catalog_version = (
        str(observed_version) if observed_version is not None else None
    )
    result.observed_major = parse_major_version(result.observed_catalog_version)

    if result.pinned_major is not None and result.observed_major is not None:
        if result.observed_major != result.pinned_major:
            result.status = "INCOMPATIBLE"
            result.compatible = False
            result.errors.append(
                {
                    "code": "CATALOG_MAJOR_INCOMPATIBLE",
                    "message": (
                        f"catalog major {result.observed_major} != "
                        f"pinned major {result.pinned_major}; human review required"
                    ),
                }
            )
            return result

    if result.observed_catalog_version is None:
        result.errors.append(
            {
                "code": "CATALOG_VERSION_MISSING",
                "message": "catalog.version missing",
            }
        )

    missing: list[str] = []
    unit_mismatches: list[dict[str, Any]] = []
    type_mismatches: list[dict[str, Any]] = []
    for spec in required_fields:
        found = by_name.get(spec.name)
        if found is None:
            missing.append(spec.name)
            continue
        if spec.expected_type is not None:
            obs_type = found.get("type")
            if obs_type is not None and str(obs_type) != spec.expected_type:
                type_mismatches.append(
                    {
                        "field": spec.name,
                        "expected": spec.expected_type,
                        "observed": obs_type,
                    }
                )
        if not _units_equal(spec.expected_unit, found.get("unit")):
            unit_mismatches.append(
                {
                    "field": spec.name,
                    "expected": spec.expected_unit,
                    "observed": found.get("unit"),
                }
            )

    result.missing_fields = missing
    result.unit_mismatches = unit_mismatches
    result.type_mismatches = type_mismatches

    if missing:
        result.errors.append(
            {
                "code": "CATALOG_MISSING_FIELD",
                "message": "required fields missing: " + ", ".join(missing),
            }
        )
    if unit_mismatches:
        result.errors.append(
            {
                "code": "CATALOG_UNIT_MISMATCH",
                "message": f"{len(unit_mismatches)} required field unit mismatch(es)",
            }
        )
    if type_mismatches:
        result.errors.append(
            {
                "code": "CATALOG_TYPE_MISMATCH",
                "message": f"{len(type_mismatches)} required field type mismatch(es)",
            }
        )

    if result.errors:
        result.status = "INCOMPATIBLE"
        result.compatible = False
        return result

    result.status = "COMPATIBLE"
    result.compatible = True
    return result


def evaluate_fixture_catalog(
    path: Path | None = None,
    *,
    etag: str | None = "W/\"fixture-field-catalog-v0.14.0\"",
) -> CatalogGateResult:
    catalog = load_catalog_fixture(path)
    return evaluate_catalog_compatibility(catalog, etag=etag, http_status=200)


def fetch_mireye_field_catalog(
    *,
    etag: str | None = None,
    timeout_seconds: float = 30.0,
    allow_network: bool = False,
    bypass_env_proxy: bool | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """GET /v1/meta/fields (public, no auth).

    Returns (catalog_or_none, meta). Does not raise for HTTP/transport failures —
    callers map meta into CatalogGateResult. Never returns credentials.
    """
    meta: dict[str, Any] = {
        "endpoint": ENDPOINT_META_FIELDS,
        "authenticated": False,
        "http_status": None,
        "ok": False,
        "etag": None,
        "error": None,
        "error_class": None,
        "allow_network": allow_network,
    }
    if not allow_network:
        meta["error_class"] = "NETWORK_GATED"
        meta["error"] = "live catalog fetch disabled (allow_network=false)"
        return None, meta

    try:
        base = _env_base_url()
    except MireyeAdapterError as exc:
        meta["error_class"] = "CONFIG_ERROR"
        meta["error"] = str(exc)
        return None, meta

    if bypass_env_proxy is None:
        bypass_env_proxy = _bypass_env_proxy_flag()
    meta["api_base_url"] = base
    meta["bypass_env_proxy"] = bypass_env_proxy

    headers = {"Accept": "application/json"}
    if etag:
        headers["If-None-Match"] = etag
    req = urllib.request.Request(
        f"{base}{ENDPOINT_META_FIELDS}",
        method="GET",
        headers=headers,
    )
    try:
        with mireye_urlopen(
            req, timeout=timeout_seconds, bypass_env_proxy=bypass_env_proxy
        ) as resp:
            meta["http_status"] = getattr(resp, "status", None) or resp.getcode()
            meta["etag"] = resp.headers.get("ETag") or resp.headers.get("etag")
            if meta["http_status"] == 304:
                meta["ok"] = True
                return None, meta
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        meta["http_status"] = exc.code
        meta["etag"] = exc.headers.get("ETag") if exc.headers else None
        body_text = exc.read().decode("utf-8", errors="replace")
        meta["error"] = f"HTTPError:{exc.code}"
        meta["error_class"] = "HTTP_ERROR"
        if exc.code == 304:
            meta["ok"] = True
            meta["error"] = None
            meta["error_class"] = None
            return None, meta
        try:
            payload = json.loads(body_text)
        except json.JSONDecodeError:
            return None, meta
        # Unexpected error body — still sanitize for inspection
        safe = sanitize_for_storage(payload) if isinstance(payload, dict) else None
        assert_no_credentials(safe or {}, label="catalog_http_error")
        return safe if isinstance(safe, dict) else None, meta
    except Exception as exc:  # noqa: BLE001
        probe = probe_plaintext_http_on_443()
        error_class = classify_tls_failure(exc, plaintext_probe=probe)
        meta["error_class"] = error_class
        meta["error"] = redact_transport_message(
            f"{error_class}:{type(exc).__name__}", api_key=None
        )
        return None, meta

    if not isinstance(payload, dict):
        meta["error_class"] = "INVALID_RESPONSE"
        meta["error"] = "catalog response was not an object"
        return None, meta
    safe = sanitize_for_storage(payload)
    assert_no_credentials(safe, label="field_catalog")
    meta["ok"] = meta["http_status"] == 200
    return safe, meta


def run_catalog_gate(
    *,
    mode: Literal["FIXTURE", "LIVE"] = "FIXTURE",
    fixture_path: Path | None = None,
    etag: str | None = None,
    allow_network: bool | None = None,
) -> CatalogGateResult:
    """Run the gate in FIXTURE (default) or LIVE mode."""
    mode_u = mode.strip().upper()
    if mode_u == "FIXTURE":
        return evaluate_fixture_catalog(fixture_path)

    if allow_network is None:
        allow_network = os.environ.get("RANGEMATCH_MIREYE_CATALOG_LIVE", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    catalog, meta = fetch_mireye_field_catalog(
        etag=etag, allow_network=bool(allow_network)
    )
    if meta.get("http_status") == 304:
        return evaluate_catalog_compatibility(
            {},
            etag=meta.get("etag") or etag,
            previous_etag=etag,
            http_status=304,
        )
    if not meta.get("ok") or catalog is None:
        result = CatalogGateResult(
            status="FETCH_FAILED",
            compatible=False,
            etag=meta.get("etag"),
            previous_etag=etag,
            http_status=meta.get("http_status"),
            errors=[
                {
                    "code": str(meta.get("error_class") or "CATALOG_FETCH_FAILED"),
                    "message": str(meta.get("error") or "catalog fetch failed"),
                }
            ],
            limitations=[
                "Catalog fetch failed — independent of parcel resolution.",
                "Do not map this status to parcel NO_MATCH or silent FIXTURE success.",
            ],
            affects_parcel_resolution=False,
        )
        return result

    return evaluate_catalog_compatibility(
        catalog,
        etag=meta.get("etag"),
        previous_etag=etag,
        http_status=meta.get("http_status"),
    )


def mutate_catalog_missing_field(
    catalog: Mapping[str, Any], field_name: str
) -> dict[str, Any]:
    out = deepcopy(dict(catalog))
    fields = [f for f in (out.get("fields") or []) if f.get("name") != field_name]
    out["fields"] = fields
    return out


def mutate_catalog_unit(
    catalog: Mapping[str, Any], field_name: str, new_unit: str
) -> dict[str, Any]:
    out = deepcopy(dict(catalog))
    fields = []
    for f in out.get("fields") or []:
        item = dict(f)
        if item.get("name") == field_name:
            item["unit"] = new_unit
        fields.append(item)
    out["fields"] = fields
    return out


def mutate_catalog_major_version(
    catalog: Mapping[str, Any], new_version: str
) -> dict[str, Any]:
    out = deepcopy(dict(catalog))
    out["version"] = new_version
    return out
