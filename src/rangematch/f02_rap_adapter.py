"""RAP v3 aggregate adapter shared by F02 herbaceous and F08 woody context."""

from __future__ import annotations

import hashlib
import json
import ssl
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from rangematch.f08_derivation import derive_f08_from_rap_bands

RAP_YEAR = 2025
RAP_ENDPOINTS = {
    "coverV3": "https://us-central1-rap-data-365417.cloudfunctions.net/coverV3",
    "productionV3": "https://us-central1-rap-data-365417.cloudfunctions.net/productionV3",
}
ADAPTER_ID = "USDA_ARS_RAP_V3_AGGREGATE_ADAPTER@0.1.0"
PostJson = Callable[[str, Mapping[str, Any], float], dict[str, Any]]


class F02RAPAdapterError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _post_json(url: str, payload: Mapping[str, Any], timeout: float) -> dict[str, Any]:
    if not url.startswith("https://"):
        raise F02RAPAdapterError("RAP_NON_HTTPS_URL_REJECTED")
    try:
        import certifi

        context = ssl.create_default_context(cafile=certifi.where())
    except Exception:  # pragma: no cover
        context = ssl.create_default_context()
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=context))
    request = Request(
        url,
        data=json.dumps(dict(payload)).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    with opener.open(request, timeout=timeout) as response:  # noqa: S310 - HTTPS enforced
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict):
        raise F02RAPAdapterError("RAP_RESPONSE_NOT_OBJECT")
    return result


def _table(feature: Mapping[str, Any], key: str) -> dict[str, Any]:
    table = (feature.get("properties") or {}).get(key)
    if isinstance(table, list) and len(table) >= 2 and isinstance(table[0], list):
        return {str(k): v for k, v in zip(table[0], table[1])}
    return {}


def _hash(payload: Mapping[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def collect_f02_f08_from_rap(
    *,
    geometry: Mapping[str, Any],
    geometry_id: str,
    geometry_hash: str,
    applicability_status: str | None = None,
    applicability_basis: list[str] | None = None,
    requested_area_m2: float | None = None,
    post_json: PostJson | None = None,
) -> dict[str, Any]:
    """Issue one coverV3 and one productionV3 request; F08 reuses coverV3."""
    post_json = post_json or _post_json
    request_feature = {
        "type": "Feature",
        "id": geometry_id,
        "properties": {"mask": True, "year": RAP_YEAR},
        "geometry": geometry["features"][0]["geometry"],
    }
    cover_response = post_json(RAP_ENDPOINTS["coverV3"], request_feature, 180)
    production_response = post_json(RAP_ENDPOINTS["productionV3"], request_feature, 180)
    cover, production = _table(cover_response, "cover"), _table(production_response, "production")
    if "PFG" not in cover:
        raise F02RAPAdapterError("RAP_COVER_MISSING_PFG")
    herb = production.get("HER")
    if not isinstance(herb, (int, float)):
        raise F02RAPAdapterError("RAP_PRODUCTION_MISSING_HER")
    if requested_area_m2 is None:
        from rangematch.f06_derivation import derive_f06_from_geometry

        geometry_measurement = derive_f06_from_geometry(
            geometry,
            geometry_hash=geometry_hash,
            geometry_id=geometry_id,
        )
        measured_area = geometry_measurement.get("area_m2")
        requested_area_m2 = float(measured_area) if measured_area is not None else None

    # A successful mask=true aggregate containing the required RAP bands proves
    # that the service found modeled in-domain pixels contributing to the result.
    # It does NOT prove full parcel coverage; that remains explicitly unquantified.
    if applicability_status is None:
        applicability_status = "IN_DOCUMENTED_PRODUCT_SCOPE"
        applicability_basis = list(applicability_basis or []) + [
            "RAP_MASK_TRUE_RETURNED_REQUIRED_COVER_AND_PRODUCTION_BANDS",
            "APPLICABILITY_SUPPORTED_BUT_PIXEL_AREA_COVERAGE_UNQUANTIFIED",
        ]
    fetched_at = _utc_now()
    cover_hash, production_hash = _hash(cover_response), _hash(production_response)
    applicability = {
        "domain_status": applicability_status,
        "review_status": "NEEDS_VERIFICATION" if applicability_status == "UNKNOWN" else "VERIFIED",
        "basis": list(applicability_basis or ["RAP_RANGELAND_DOMAIN_NOT_YET_VERIFIED_FOR_LIVE_PARCEL"]),
    }
    coverage = {
        "status": "COVERAGE_UNQUANTIFIED",
        "requested_area_m2": requested_area_m2,
        "eligible_area_m2": None,
        "masked_area_m2": None,
        "no_data_area_m2": None,
        "valid_area_m2": None,
        "valid_coverage_fraction": None,
        "adapter_status": "AGGREGATE_API_VERIFIED",
    }

    def fact(variable_id: str, value: float, unit: str, endpoint: str, artifact_hash: str, limitations: list[str]):
        return {
            "variable_id": variable_id,
            "observation": {
                "value_state": "KNOWN", "value": float(value), "unit": unit,
                "spatial_semantics": "parcel_mean", "temporal_semantics": f"annual_{RAP_YEAR}",
            },
            "source": {"provider": "USDA_ARS", "product": "RAP", "version": "v3", "data_kind": "MODELED", "adapter_id": ADAPTER_ID, "modeled": True},
            "applicability": dict(applicability),
            "coverage": dict(coverage),
            "quality": {"confidence_state": "LIMITED_BY_UNQUANTIFIED_COVERAGE", "modeled": True, "resolution": "30_meters_nominal", "api_contract_verified": True},
            "provenance": {
                "source_reference": f"RAP_{endpoint}", "canonical_source_id": "USDA_ARS_RAP_V3",
                "source_product_and_version": "RAP_v3", "fetched_at": fetched_at,
                "geometry_hash": geometry_hash, "response_or_artifact_hash": artifact_hash,
                "endpoint": endpoint, "request_parameters": {"mask": True, "year": RAP_YEAR},
                "derivation_spec_version": "F02_HERBACEOUS_DERIVATION_SPEC.yaml@0.1.0",
                "algorithm_version": ADAPTER_ID,
            },
            "limitations": limitations,
        }

    f02 = {
        "factor_id": "F02_HERBACEOUS_RESOURCE",
        "input_quality_state": (
            "RAP_OUTSIDE_OR_UNKNOWN_APPLICABILITY"
            if applicability_status == "UNKNOWN"
            else "COVERAGE_UNQUANTIFIED"
        ),
        "derivation_spec": "F02_HERBACEOUS_DERIVATION_SPEC.yaml@0.1.0",
        "algorithm_version": ADAPTER_ID,
        "ranking_effect": "NONE",
        "limitations": [
            "RAP aggregate coverage remains COVERAGE_UNQUANTIFIED.",
            "Modeled cover/production are not forage availability, palatability, nutritive value, carrying capacity, or stocking rate.",
        ],
        "unknowns": ["RAP valid pixel-area fraction is not quantified.", "Botanical composition, palatability, and nutritive value are not verified."],
        "land_facts": [
            fact("VAR_F02_PERENNIAL_HERB_COVER", cover["PFG"], "percent_cover", "coverV3", cover_hash, ["PFG combines perennial grasses and forbs."]),
            fact("VAR_F02_ANNUAL_HERB_PRODUCTION", herb, "pound_per_acre", "productionV3", production_hash, ["Modeled new growth is not standing biomass or available forage."]),
        ],
    }
    f08 = derive_f08_from_rap_bands(
        raw_shr_percent=cover.get("SHR"), raw_tre_percent=cover.get("TRE"),
        source_year=RAP_YEAR, mask=True, geometry_hash=geometry_hash,
        response_or_artifact_hash=cover_hash, applicability_status=applicability_status,
        coverage_status="COVERAGE_UNQUANTIFIED", coverage_record=coverage,
        applicability_record=applicability, fetched_at=fetched_at, geometry_id=geometry_id,
        artifact_path="memory://rap/coverV3", reused_existing_artifact=True,
        duplicate_coverV3_fetch=False,
    )
    return {
        "factors": {"F02_HERBACEOUS_RESOURCE": f02, "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE": f08},
        "cover_response_hash": cover_hash,
        "production_response_hash": production_hash,
        "cover_request_count": 1,
        "production_request_count": 1,
        "duplicate_coverV3_fetch": False,
    }
