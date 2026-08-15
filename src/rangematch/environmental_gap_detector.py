"""Deterministic Environmental Gap Detector (Phase 3).

Consumes a Mireye Environmental Profile (+ optional F06 geometry hash) and emits
a schema-valid gap plan. The LLM never chooses tools. F06 is never planned here.
F07 is never triggered.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

from rangematch.mireye_environmental_profile import (
    BUYER_VISIBLE_STATUSES,
    SPATIAL_CONTEXT,
    SPATIAL_PARCEL,
    SPATIAL_POINT,
    STATUS_MISSING,
    STATUS_NOT_APPLICABLE,
    STATUS_REJECTED,
    STATUS_SOURCE_UNAVAILABLE,
    load_field_manifest,
)
from rangematch.unified_output import sha256_canonical

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "docs" / "schemas" / "environmental_gap_plan.schema.json"

SCHEMA_VERSION = "environmental_gap_plan@1.0.0"
DETECTOR_ID = "ENVIRONMENTAL_GAP_DETECTOR@1.0.0"

DOMAINS: tuple[str, ...] = (
    "TERRAIN",
    "FEED_VEGETATION",
    "WATER",
    "SOIL_ECOLOGY",
    "CLIMATE_HAZARD",
)

STATUS_SUFFICIENT = "SUFFICIENT_FROM_MIREYE"
STATUS_SUPPLEMENT = "MIREYE_CONTEXT_PLUS_SUPPLEMENT"
STATUS_UNAVAILABLE = "UNAVAILABLE"

TOOL_F01 = "F01_3DEP"
TOOL_F02 = "F02_RAP"
TOOL_F03 = "F03_NHD"
TOOL_F04 = "F04_SDA"
TOOL_F05 = "F05_NOAA"
TOOL_F08 = "F08_RAP_WOODY"
APPROVED_SUPPLEMENTS: tuple[str, ...] = (
    TOOL_F01,
    TOOL_F02,
    TOOL_F03,
    TOOL_F04,
    TOOL_F05,
    TOOL_F08,
)
EXCLUDED_TOOLS: tuple[str, ...] = ("F07_ROADS", "F06_PARCEL_CONFIGURATION", "F09")

# Material parcel-wide capabilities that Mireye point/context fields do not satisfy.
CAP_PARCEL_TERRAIN = "PARCEL_WIDE_TERRAIN_DEPTH"
CAP_PARCEL_HERBACEOUS = "PARCEL_WIDE_HERBACEOUS_PRODUCTION"
CAP_PARCEL_WOODY = "PARCEL_WIDE_WOODY_STRUCTURE"
CAP_PARCEL_HYDRO = "PARCEL_HYDROGRAPHY_INVENTORY"
CAP_PARCEL_SOIL = "PARCEL_SOIL_COMPOSITION"
CAP_PRECIP_NORMAL = "PRECIPITATION_NORMAL_SEASONALITY"

REASON_POINT_ONLY = "MIREYE_POINT_ONLY"
REASON_CONTEXT_ONLY = "MIREYE_CONTEXT_ONLY"
REASON_MIXED_POINT_CONTEXT = "MIREYE_POINT_AND_CONTEXT_ONLY"
REASON_HAS_PARCEL = "MIREYE_HAS_PARCEL_SEMANTICS"
REASON_MISSING_REQUIRED = "MIREYE_MISSING_REQUIRED"
REASON_PARTIAL = "MIREYE_PARTIAL"
REASON_SOURCE_UNAVAILABLE = "MIREYE_SOURCE_UNAVAILABLE"
REASON_REJECTED = "MIREYE_REJECTED_BY_SEMANTICS_GATE"
REASON_EMPTY_DOMAIN = "MIREYE_DOMAIN_EMPTY"
REASON_NOT_APPLICABLE = "MIREYE_NOT_APPLICABLE"
REASON_CATALOG_DRIFT = "CATALOG_DRIFT_FAIL_CLOSED"
REASON_MISSING_CAP_TERRAIN = "MISSING_PARCEL_WIDE_TERRAIN"
REASON_MISSING_CAP_HERB = "MISSING_PARCEL_HERBACEOUS_PRODUCTION"
REASON_MISSING_CAP_WOODY = "MISSING_PARCEL_WOODY_STRUCTURE"
REASON_MISSING_CAP_HYDRO = "MISSING_PARCEL_HYDROGRAPHY_INVENTORY"
REASON_MISSING_CAP_SOIL = "MISSING_PARCEL_SOIL_COMPOSITION"
REASON_MISSING_CAP_PRECIP = "MISSING_PRECIPITATION_NORMAL"
REASON_F06_PRESENT = "F06_GEOMETRY_AVAILABLE"
REASON_F07_EXCLUDED = "F07_EXCLUDED_APPENDIX_ONLY"


class EnvironmentalGapDetectorError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


@lru_cache(maxsize=1)
def load_gap_plan_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _obs_by_domain(profile: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {domain: [] for domain in DOMAINS}
    for obs in profile.get("observations") or []:
        if not isinstance(obs, Mapping):
            continue
        domain = str(obs.get("domain") or "")
        if domain in out:
            out[domain].append(dict(obs))
    return out


def _visible(obs: Mapping[str, Any]) -> bool:
    return str(obs.get("status") or "") in BUYER_VISIBLE_STATUSES


def _sorted_unique(values: Sequence[str]) -> list[str]:
    return sorted({str(v) for v in values if v})


def _domain_field_specs(domain: str) -> list[dict[str, Any]]:
    manifest = load_field_manifest()
    return [dict(row) for row in manifest["fields"] if row.get("domain") == domain]


def _evaluate_domain(
    domain: str,
    observations: Sequence[Mapping[str, Any]],
    *,
    catalog_drift_fail_closed: bool,
) -> dict[str, Any]:
    if catalog_drift_fail_closed:
        return {
            "domain": domain,
            "coverage_status": STATUS_UNAVAILABLE,
            "available_evidence_refs": [],
            "missing_capabilities": [],
            "reason_codes": [REASON_CATALOG_DRIFT],
            "supplemental_tool_ids": [],
        }

    specs = _domain_field_specs(domain)
    by_id = {str(obs.get("field_id")): obs for obs in observations}
    available_refs: list[str] = []
    reason_codes: list[str] = []
    visible_obs = [obs for obs in observations if _visible(obs)]
    for obs in visible_obs:
        ref = str(obs.get("observation_id") or obs.get("field_id") or "")
        if ref:
            available_refs.append(ref)

    spatials = {
        str(obs.get("spatial_semantics") or "")
        for obs in visible_obs
        if obs.get("spatial_semantics")
    }
    has_parcel = SPATIAL_PARCEL in spatials
    has_point = SPATIAL_POINT in spatials
    has_context = SPATIAL_CONTEXT in spatials

    required_ids = [str(row["field_id"]) for row in specs if row.get("required")]
    missing_required = []
    partial = False
    source_unavailable = False
    rejected = False
    not_applicable = False
    for field_id in required_ids:
        obs = by_id.get(field_id)
        if obs is None:
            missing_required.append(field_id)
            continue
        status = str(obs.get("status") or "")
        if status == STATUS_MISSING:
            missing_required.append(field_id)
        elif status == STATUS_SOURCE_UNAVAILABLE:
            source_unavailable = True
            missing_required.append(field_id)
        elif status == STATUS_REJECTED:
            rejected = True
        elif status == STATUS_NOT_APPLICABLE:
            not_applicable = True
        elif status == "PARTIAL":
            partial = True

    if missing_required:
        reason_codes.append(REASON_MISSING_REQUIRED)
    if partial:
        reason_codes.append(REASON_PARTIAL)
    if source_unavailable:
        reason_codes.append(REASON_SOURCE_UNAVAILABLE)
    if rejected:
        reason_codes.append(REASON_REJECTED)
    if not_applicable and not visible_obs:
        reason_codes.append(REASON_NOT_APPLICABLE)

    if not visible_obs:
        reason_codes.append(REASON_EMPTY_DOMAIN)
    elif has_parcel and not has_point and not has_context:
        reason_codes.append(REASON_HAS_PARCEL)
    elif has_point and has_context and not has_parcel:
        reason_codes.append(REASON_MIXED_POINT_CONTEXT)
    elif has_point and not has_parcel:
        reason_codes.append(REASON_POINT_ONLY)
    elif has_context and not has_parcel:
        reason_codes.append(REASON_CONTEXT_ONLY)
    elif has_parcel:
        reason_codes.append(REASON_HAS_PARCEL)

    missing_capabilities: list[str] = []
    tools: list[str] = []

    if domain == "TERRAIN":
        # Manifest terrain fields are POINT-only; parcel-wide depth needs F01.
        if not has_parcel:
            missing_capabilities.append(CAP_PARCEL_TERRAIN)
            tools.append(TOOL_F01)
            reason_codes.append(REASON_MISSING_CAP_TERRAIN)
    elif domain == "FEED_VEGETATION":
        if not has_parcel:
            missing_capabilities.append(CAP_PARCEL_HERBACEOUS)
            tools.append(TOOL_F02)
            reason_codes.append(REASON_MISSING_CAP_HERB)
            # Point canopy/LCMS is not parcel woody structure.
            if any(
                str(obs.get("field_id")) in {"tree_canopy_pct", "lcms_class"}
                for obs in visible_obs
            ) or not visible_obs:
                missing_capabilities.append(CAP_PARCEL_WOODY)
                tools.append(TOOL_F08)
                reason_codes.append(REASON_MISSING_CAP_WOODY)
    elif domain == "WATER":
        # Wetland parcel fraction is not a hydrography inventory.
        hydro_parcel = any(
            str(obs.get("field_id"))
            in {
                "parcel_hydrography_inventory",  # future
            }
            and _visible(obs)
            for obs in observations
        )
        if not hydro_parcel:
            missing_capabilities.append(CAP_PARCEL_HYDRO)
            tools.append(TOOL_F03)
            reason_codes.append(REASON_MISSING_CAP_HYDRO)
    elif domain == "SOIL_ECOLOGY":
        if not has_parcel:
            missing_capabilities.append(CAP_PARCEL_SOIL)
            tools.append(TOOL_F04)
            reason_codes.append(REASON_MISSING_CAP_SOIL)
    elif domain == "CLIMATE_HAZARD":
        # Cattle climate depth requires precipitation normal/seasonality (F05).
        # Current Mireye manifest has drought/temp/hazard context only.
        precip_present = any(
            str(obs.get("field_id"))
            in {
                "mean_annual_precipitation_mm",
                "precipitation_normal_mm",
            }
            and _visible(obs)
            for obs in observations
        )
        if not precip_present:
            missing_capabilities.append(CAP_PRECIP_NORMAL)
            tools.append(TOOL_F05)
            reason_codes.append(REASON_MISSING_CAP_PRECIP)

    # Coverage status
    if not_applicable and not visible_obs and not tools:
        coverage = STATUS_UNAVAILABLE
        tools = []
        missing_capabilities = []
    elif tools:
        coverage = STATUS_SUPPLEMENT
    elif visible_obs and not missing_capabilities:
        coverage = STATUS_SUFFICIENT
    elif not visible_obs and not tools:
        coverage = STATUS_UNAVAILABLE
    else:
        coverage = STATUS_SUPPLEMENT

    # Never emit F07.
    tools = [tool for tool in tools if tool in APPROVED_SUPPLEMENTS]

    return {
        "domain": domain,
        "coverage_status": coverage,
        "available_evidence_refs": _sorted_unique(available_refs),
        "missing_capabilities": _sorted_unique(missing_capabilities),
        "reason_codes": _sorted_unique(reason_codes),
        "supplemental_tool_ids": [tool for tool in APPROVED_SUPPLEMENTS if tool in tools],
    }


def detect_environmental_gaps(
    profile: Mapping[str, Any],
    *,
    f06_geometry_hash: str | None = None,
    catalog_drift_fail_closed: bool = False,
    built_at: str | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    """Build a deterministic environmental gap plan from a Mireye Profile."""
    if not isinstance(profile, Mapping):
        raise EnvironmentalGapDetectorError("invalid_profile", "profile must be an object")
    run_id = str(profile.get("run_id") or "").strip()
    profile_hash = str(profile.get("profile_hash") or "").strip()
    if not run_id or not profile_hash:
        raise EnvironmentalGapDetectorError(
            "invalid_profile",
            "run_id and profile_hash are required",
        )
    parcel_ref = profile.get("parcel_ref") if isinstance(profile.get("parcel_ref"), Mapping) else {}
    if parcel_ref.get("confirmed") is not True:
        raise EnvironmentalGapDetectorError(
            "parcel_not_confirmed",
            "Gap Detector requires a confirmed parcel profile",
        )

    by_domain = _obs_by_domain(profile)
    domain_decisions = [
        _evaluate_domain(
            domain,
            by_domain.get(domain) or [],
            catalog_drift_fail_closed=catalog_drift_fail_closed,
        )
        for domain in DOMAINS
    ]

    ordered_tools: list[str] = []
    for tool in APPROVED_SUPPLEMENTS:
        if any(tool in row["supplemental_tool_ids"] for row in domain_decisions):
            ordered_tools.append(tool)

    notes = [
        "LLM never chooses supplemental tools",
        "F06 is always-on core derivation and is not planned here",
        "F07 is excluded under HUMAN_ACCESS_INFRA_APPENDIX_ONLY",
    ]
    if f06_geometry_hash:
        notes.append(REASON_F06_PRESENT)
        notes.append(REASON_F07_EXCLUDED)

    plan: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "detector_id": DETECTOR_ID,
        "run_id": run_id,
        "profile_hash": profile_hash,
        "f06_geometry_hash": f06_geometry_hash,
        "catalog_drift_fail_closed": bool(catalog_drift_fail_closed),
        "domains": domain_decisions,
        "ordered_supplemental_tool_ids": ordered_tools,
        "excluded_tool_ids": list(EXCLUDED_TOOLS),
        "provenance": {
            "built_at": built_at or _utc_now(),
            "llm_tool_routing": False,
            "notes": notes,
        },
    }
    plan["plan_hash"] = compute_gap_plan_hash(plan)
    if validate:
        validate_environmental_gap_plan(plan)
    return plan


def compute_gap_plan_hash(plan: Mapping[str, Any]) -> str:
    body = {k: v for k, v in dict(plan).items() if k != "plan_hash"}
    # Provenance built_at is retained in the plan object but excluded from the
    # stability hash so identical evidence yields an identical plan_hash.
    prov = dict(body.get("provenance") or {})
    prov.pop("built_at", None)
    body["provenance"] = prov
    return sha256_canonical(body)


def validate_environmental_gap_plan(plan: Mapping[str, Any]) -> None:
    schema = load_gap_plan_schema()
    errors = sorted(
        Draft202012Validator(schema).iter_errors(dict(plan)),
        key=lambda err: list(err.path),
    )
    if errors:
        first = errors[0]
        path = ".".join(str(p) for p in first.path) or "<root>"
        raise EnvironmentalGapDetectorError(
            "schema_validation_failed",
            f"{path}: {first.message}",
        )
    if plan.get("provenance", {}).get("llm_tool_routing") is not False:
        raise EnvironmentalGapDetectorError(
            "llm_tool_routing_forbidden",
            "llm_tool_routing must be false",
        )
    excluded = set(plan.get("excluded_tool_ids") or [])
    for tool in plan.get("ordered_supplemental_tool_ids") or []:
        if tool in excluded or str(tool).startswith("F07"):
            raise EnvironmentalGapDetectorError(
                "excluded_tool_planned",
                f"excluded tool planned: {tool}",
            )
    for domain in plan.get("domains") or []:
        for tool in domain.get("supplemental_tool_ids") or []:
            if str(tool).startswith("F07") or tool == "F06_PARCEL_CONFIGURATION":
                raise EnvironmentalGapDetectorError(
                    "excluded_tool_planned",
                    f"domain {domain.get('domain')} planned excluded tool {tool}",
                )
            if domain.get("coverage_status") == STATUS_SUFFICIENT and tool:
                raise EnvironmentalGapDetectorError(
                    "sufficient_with_tools",
                    f"{domain.get('domain')} is sufficient but lists tools",
                )
            if domain.get("coverage_status") == STATUS_SUPPLEMENT and not domain.get(
                "reason_codes"
            ):
                raise EnvironmentalGapDetectorError(
                    "supplement_without_reason",
                    f"{domain.get('domain')} lists supplements without reason_codes",
                )
