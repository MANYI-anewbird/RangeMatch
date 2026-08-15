"""Phase 4: execute Gap Detector supplement plan and merge evidence.

Runs only adapters listed on the EnvironmentalGapPlan. Never calls F07.
Never substitutes fixtures. Failures become SOURCE_UNAVAILABLE observations.
"""

from __future__ import annotations

import time
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, wait
from typing import Any, Callable, Mapping, Sequence

from rangematch.advisor_generic_collect import (
    ADAPTER_TIMEOUT_REASON,
    ADAPTER_TIMEOUT_S,
    BUDGET_EXHAUSTED_REASON,
    TOTAL_BUDGET_S,
    _apply_adapter_payload,
    _default_live_runners,
    _dependency_reason,
    _is_missing_dependency,
)
from rangematch.environmental_gap_detector import (
    APPROVED_SUPPLEMENTS,
    CAP_PARCEL_HERBACEOUS,
    CAP_PARCEL_HYDRO,
    CAP_PARCEL_SOIL,
    CAP_PARCEL_TERRAIN,
    CAP_PARCEL_WOODY,
    CAP_PRECIP_NORMAL,
    TOOL_F01,
    TOOL_F02,
    TOOL_F03,
    TOOL_F04,
    TOOL_F05,
    TOOL_F08,
)
from rangematch.mireye_first_collection import derive_confirmed_f06
from rangematch.unified_output import (
    _project_scalar_measurements_as_facts,
    sha256_canonical,
)

PROVIDER_SUPPLEMENT = "RANGEMATCH_SUPPLEMENT"
PROVIDER_CORE = "RANGEMATCH_CORE"
PROVIDER_MIREYE = "MIREYE"

TOOL_TO_FACTOR: dict[str, str] = {
    TOOL_F01: "F01_TOPOGRAPHY",
    TOOL_F02: "F02_HERBACEOUS_RESOURCE",
    TOOL_F03: "F03_LIVESTOCK_WATER",
    TOOL_F04: "F04_SOIL_WETNESS_ECOLOGICAL_SITE",
    TOOL_F05: "F05_CLIMATE_DROUGHT_EXPOSURE",
    TOOL_F08: "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE",
}

FACTOR_TO_TOOL: dict[str, str] = {v: k for k, v in TOOL_TO_FACTOR.items()}

TOOL_CAPABILITY: dict[str, str] = {
    TOOL_F01: CAP_PARCEL_TERRAIN,
    TOOL_F02: CAP_PARCEL_HERBACEOUS,
    TOOL_F03: CAP_PARCEL_HYDRO,
    TOOL_F04: CAP_PARCEL_SOIL,
    TOOL_F05: CAP_PRECIP_NORMAL,
    TOOL_F08: CAP_PARCEL_WOODY,
}

VARIABLE_DOMAIN: dict[str, str] = {
    "VAR_F01_ELEVATION_MEDIAN_M": "TERRAIN",
    "VAR_F01_SLOPE_MEDIAN_DEGREES": "TERRAIN",
    "VAR_F02_ANNUAL_HERB_PRODUCTION": "FEED_VEGETATION",
    "VAR_F02_PERENNIAL_HERB_COVER": "FEED_VEGETATION",
    "VAR_F03_MAPPED_WATER_CANDIDATE_COUNT": "WATER",
    "VAR_F03_FIELD_VERIFIED_LIVESTOCK_WATER_COUNT": "WATER",
    "VAR_F03_EUCLIDEAN_DISTANCE_TO_MAPPED_CANDIDATE_MEDIAN_M": "WATER",
    "VAR_F04_SDA_VALID_COVERAGE_FRACTION": "SOIL_ECOLOGY",
    "VAR_F04_KNOWN_COMPONENT_SHARE": "SOIL_ECOLOGY",
    "VAR_F05_MEAN_ANNUAL_PRECIPITATION": "CLIMATE_HAZARD",
    "VAR_F05_MEAN_ANNUAL_PRECIP_MM": "CLIMATE_HAZARD",
    "VAR_F08_SHRUB_COVER_FRACTION": "FEED_VEGETATION",
    "VAR_F08_TREE_COVER_FRACTION": "FEED_VEGETATION",
    "VAR_F08_COMBINED_MODELED_WOODY_COVER_FRACTION": "FEED_VEGETATION",
}


class EnvironmentalSupplementError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def unit_test_supplement_runners(
    planned_factor_ids: Sequence[str] | None = None,
) -> dict[str, Callable[[], Any]]:
    """Honest stub payloads for MIREYE_FIRST unit tests — never CPER fixtures."""

    def f01() -> dict[str, Any]:
        return {
            "factor_id": "F01_TOPOGRAPHY",
            "canonical_source_id": "UNIT_TEST_3DEP",
            "summary": {"elevation_median_m": 1700.0, "slope_median_degrees": 4.0},
            "land_facts": [
                {
                    "variable_id": "VAR_F01_ELEVATION_MEDIAN_M",
                    "value": 1700.0,
                    "unit": "m",
                    "spatial_semantics": "parcel_aggregate",
                    "source_id": "UNIT_TEST_3DEP",
                }
            ],
        }

    def f02() -> dict[str, Any]:
        return {
            "factors": {
                "F02_HERBACEOUS_RESOURCE": {
                    "factor_id": "F02_HERBACEOUS_RESOURCE",
                    "canonical_source_id": "UNIT_TEST_RAP",
                    "land_facts": [
                        {
                            "variable_id": "VAR_F02_ANNUAL_HERB_PRODUCTION",
                            "value": 500.0,
                            "unit": "pound_per_acre",
                            "spatial_semantics": "parcel_aggregate",
                            "source_id": "UNIT_TEST_RAP",
                        }
                    ],
                },
                "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE": {
                    "factor_id": "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE",
                    "canonical_source_id": "UNIT_TEST_RAP",
                    "land_facts": [
                        {
                            "variable_id": "VAR_F08_SHRUB_COVER_FRACTION",
                            "value": 0.1,
                            "unit": "fraction",
                            "spatial_semantics": "parcel_aggregate",
                            "source_id": "UNIT_TEST_RAP",
                        }
                    ],
                },
            }
        }

    def f03() -> dict[str, Any]:
        return {
            "factor_id": "F03_LIVESTOCK_WATER",
            "canonical_source_id": "UNIT_TEST_NHD",
            "mapped_candidate_count": 1,
            "land_facts": [
                {
                    "variable_id": "VAR_F03_MAPPED_WATER_CANDIDATE_COUNT",
                    "value": 1,
                    "unit": "count",
                    "spatial_semantics": "parcel_aggregate",
                    "source_id": "UNIT_TEST_NHD",
                }
            ],
        }

    def f04() -> dict[str, Any]:
        return {
            "factor_id": "F04_SOIL_WETNESS_ECOLOGICAL_SITE",
            "canonical_source_id": "UNIT_TEST_SDA",
            "land_facts": [
                {
                    "variable_id": "VAR_F04_SDA_VALID_COVERAGE_FRACTION",
                    "value": 0.8,
                    "unit": "fraction",
                    "spatial_semantics": "parcel_aggregate",
                    "source_id": "UNIT_TEST_SDA",
                }
            ],
        }

    def f05() -> dict[str, Any]:
        return {
            "factor_id": "F05_CLIMATE_DROUGHT_EXPOSURE",
            "canonical_source_id": "UNIT_TEST_NOAA",
            "land_facts": [
                {
                    "variable_id": "VAR_F05_MEAN_ANNUAL_PRECIPITATION",
                    "value": 350.0,
                    "unit": "mm/year",
                    "spatial_semantics": "parcel_aggregate",
                    "source_id": "UNIT_TEST_NOAA",
                }
            ],
        }

    catalog = {
        "F01_TOPOGRAPHY": f01,
        "F02_HERBACEOUS_RESOURCE": f02,
        "F03_LIVESTOCK_WATER": f03,
        "F04_SOIL_WETNESS_ECOLOGICAL_SITE": f04,
        "F05_CLIMATE_DROUGHT_EXPOSURE": f05,
    }
    if planned_factor_ids is None:
        return dict(catalog)
    return {fid: catalog[fid] for fid in planned_factor_ids if fid in catalog}


def _normalize_spatial(raw: Any) -> str:
    text = str(raw or "PARCEL").upper()
    if text in {"PARCEL", "PARCEL_AGGREGATE", "PARCEL_MEAN", "PARCEL_DISTRIBUTION"}:
        return "PARCEL"
    if text in {"POINT", "POINT_SAMPLE"}:
        return "POINT"
    if text in {"CONTEXT", "NEAREST_FEATURE", "JURISDICTION"}:
        return "CONTEXT"
    return "PARCEL"


def _domain_for_variable(variable_id: str) -> str | None:
    if variable_id in VARIABLE_DOMAIN:
        return VARIABLE_DOMAIN[variable_id]
    if variable_id.startswith("VAR_F01_"):
        return "TERRAIN"
    if variable_id.startswith("VAR_F02_") or variable_id.startswith("VAR_F08_"):
        return "FEED_VEGETATION"
    if variable_id.startswith("VAR_F03_"):
        return "WATER"
    if variable_id.startswith("VAR_F04_"):
        return "SOIL_ECOLOGY"
    if variable_id.startswith("VAR_F05_"):
        return "CLIMATE_HAZARD"
    return None


def planned_factor_jobs(plan: Mapping[str, Any]) -> list[str]:
    """Return live factor runner keys for the plan (F02 implies shared RAP for F08)."""
    raw_tools = [str(tool) for tool in (plan.get("ordered_supplemental_tool_ids") or [])]
    if any(tool.startswith("F07") for tool in raw_tools):
        raise EnvironmentalSupplementError(
            "f07_forbidden",
            "F07 cannot be executed on the natural-environment supplement path",
        )
    tools = [tool for tool in raw_tools if tool in APPROVED_SUPPLEMENTS]
    jobs: list[str] = []
    for tool in tools:
        if tool == TOOL_F08 and TOOL_F02 in tools:
            # F08 is produced by the shared F02 RAP collect.
            continue
        factor_id = TOOL_TO_FACTOR[tool]
        if factor_id not in jobs:
            jobs.append(factor_id)
    return jobs


def _build_runners(
    *,
    geometry: Mapping[str, Any],
    geometry_id: str,
    geometry_hash: str,
    geometry_reference: str,
    planned_factor_ids: Sequence[str],
    runners: Mapping[str, Callable[[], Any]] | None,
) -> dict[str, Callable[[], Any]]:
    if runners is not None:
        selected = {fid: runners[fid] for fid in planned_factor_ids if fid in runners}
        missing = [fid for fid in planned_factor_ids if fid not in selected]
        if missing:
            raise EnvironmentalSupplementError(
                "runner_missing",
                f"test/live runners missing for {missing}",
            )
        if "F07_ROAD_AND_PHYSICAL_ACCESS" in selected:
            raise EnvironmentalSupplementError(
                "f07_forbidden",
                "F07 runner cannot be attached to supplement execution",
            )
        return selected

    live = _default_live_runners(
        geometry=geometry,
        geometry_id=geometry_id,
        geometry_hash=geometry_hash,
        geometry_reference=geometry_reference,
        mireye_contexts={},
    )
    # Never expose F07 on this path.
    live.pop("F07_ROAD_AND_PHYSICAL_ACCESS", None)
    return {fid: live[fid] for fid in planned_factor_ids if fid in live}


def execute_supplement_plan(
    plan: Mapping[str, Any],
    *,
    geometry: Mapping[str, Any],
    geometry_id: str,
    geometry_hash: str,
    geometry_reference: str | None = None,
    runners: Mapping[str, Callable[[], Any]] | None = None,
    adapter_timeout_s: float | None = None,
    total_budget_s: float | None = None,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Execute only planned supplements. Fresh result every call (no cross-run cache)."""
    planned_tools = [
        str(tool)
        for tool in (plan.get("ordered_supplemental_tool_ids") or [])
        if tool in APPROVED_SUPPLEMENTS
    ]
    planned_factors = planned_factor_jobs(plan)
    timeout_s = ADAPTER_TIMEOUT_S if adapter_timeout_s is None else float(adapter_timeout_s)
    budget_s = TOTAL_BUDGET_S if total_budget_s is None else float(total_budget_s)
    geom_ref = geometry_reference or f"geometry:{geometry_hash}"

    computed: dict[str, Any] = {}
    errors: dict[str, str] = {}
    attempts: list[dict[str, Any]] = []
    notes: list[str] = []
    deadline = time.monotonic() + max(0.0, budget_s)

    if not planned_factors:
        return {
            "run_id": plan.get("run_id"),
            "plan_hash": plan.get("plan_hash"),
            "planned_tool_ids": planned_tools,
            "attempted_tool_ids": [],
            "succeeded_tool_ids": [],
            "failed_tool_ids": [],
            "skipped_tool_ids": [],
            "computed_factors": {},
            "factor_errors": {},
            "attempts": [],
            "progress_notes": ["no supplements planned"],
            "capabilities_filled": [],
            "capabilities_still_missing": _still_missing(plan, filled=[]),
        }

    selected = _build_runners(
        geometry=geometry,
        geometry_id=geometry_id,
        geometry_hash=geometry_hash,
        geometry_reference=geom_ref,
        planned_factor_ids=planned_factors,
        runners=runners,
    )

    def emit(factor_id: str, status: str, note: str | None = None) -> None:
        if on_progress:
            on_progress({"factor_id": factor_id, "status": status, "note": note})

    def remaining() -> float:
        return max(0.0, deadline - time.monotonic())

    submitted: dict[Any, str] = {}
    pool = ThreadPoolExecutor(max_workers=max(1, min(6, len(selected) or 1)))
    try:
        for factor_id, runner in selected.items():
            if remaining() <= 0:
                errors[factor_id] = BUDGET_EXHAUSTED_REASON
                notes.append(f"{factor_id} skipped — budget exhausted")
                attempts.append(
                    {
                        "tool_id": FACTOR_TO_TOOL.get(factor_id, factor_id),
                        "factor_id": factor_id,
                        "status": "SKIPPED",
                        "error": BUDGET_EXHAUSTED_REASON,
                        "duration_ms": 0,
                    }
                )
                emit(factor_id, "PARTIAL", notes[-1])
                continue
            emit(factor_id, "RUNNING")
            submitted[pool.submit(_timed_call, runner)] = factor_id
        wait_s = min(timeout_s, remaining()) if submitted else 0.0
        done: set[Any] = set()
        not_done: set[Any] = set(submitted)
        if submitted:
            finished, pending = wait(
                list(submitted), timeout=wait_s, return_when=ALL_COMPLETED
            )
            done = set(finished)
            not_done = set(pending)
        for fut in done:
            factor_id = submitted[fut]
            started = time.monotonic()
            try:
                payload, duration_ms = fut.result(timeout=0)
                _apply_adapter_payload(
                    factor_id, payload, computed=computed, errors=errors
                )
                # Shared RAP: F02 payload may include F08.
                if factor_id == "F02_HERBACEOUS_RESOURCE" and isinstance(payload, Mapping):
                    factors = payload.get("factors") or {}
                    if "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE" in factors:
                        computed["F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"] = factors[
                            "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"
                        ]
                attempts.append(
                    {
                        "tool_id": FACTOR_TO_TOOL.get(factor_id, factor_id),
                        "factor_id": factor_id,
                        "status": "SUCCEEDED",
                        "error": None,
                        "duration_ms": duration_ms,
                    }
                )
                emit(factor_id, "SUCCEEDED")
            except Exception as exc:  # noqa: BLE001 — isolate adapter failure
                reason = (
                    _dependency_reason(exc)
                    if _is_missing_dependency(exc)
                    else (str(exc) or type(exc).__name__)
                )
                errors[factor_id] = reason
                attempts.append(
                    {
                        "tool_id": FACTOR_TO_TOOL.get(factor_id, factor_id),
                        "factor_id": factor_id,
                        "status": "FAILED",
                        "error": reason,
                        "duration_ms": int((time.monotonic() - started) * 1000),
                    }
                )
                emit(factor_id, "PARTIAL")
                if factor_id == "F02_HERBACEOUS_RESOURCE" and TOOL_F08 in planned_tools:
                    errors.setdefault(
                        "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE",
                        "BLOCKED_BY_F02_SHARED_RAP_ARTIFACT",
                    )
        for fut in not_done:
            factor_id = submitted[fut]
            reason = (
                BUDGET_EXHAUSTED_REASON if remaining() <= 0 else ADAPTER_TIMEOUT_REASON
            )
            errors[factor_id] = reason
            notes.append(f"{factor_id} timed out — continuing")
            attempts.append(
                {
                    "tool_id": FACTOR_TO_TOOL.get(factor_id, factor_id),
                    "factor_id": factor_id,
                    "status": "FAILED",
                    "error": reason,
                    "duration_ms": int(timeout_s * 1000),
                }
            )
            emit(factor_id, "PARTIAL", notes[-1])
            if factor_id == "F02_HERBACEOUS_RESOURCE" and TOOL_F08 in planned_tools:
                errors.setdefault(
                    "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE",
                    reason,
                )
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    succeeded_tools: list[str] = []
    failed_tools: list[str] = []
    for tool in planned_tools:
        factor_id = TOOL_TO_FACTOR[tool]
        if factor_id in computed and factor_id not in errors:
            succeeded_tools.append(tool)
        elif tool == TOOL_F08 and "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE" in computed:
            succeeded_tools.append(tool)
        else:
            failed_tools.append(tool)

    filled = [TOOL_CAPABILITY[tool] for tool in succeeded_tools if tool in TOOL_CAPABILITY]
    return {
        "run_id": plan.get("run_id"),
        "plan_hash": plan.get("plan_hash"),
        "planned_tool_ids": planned_tools,
        "attempted_tool_ids": [
            FACTOR_TO_TOOL.get(fid, fid) for fid in planned_factors if fid in selected
        ],
        "succeeded_tool_ids": succeeded_tools,
        "failed_tool_ids": failed_tools,
        "skipped_tool_ids": [
            FACTOR_TO_TOOL.get(fid, fid)
            for fid, err in errors.items()
            if err == BUDGET_EXHAUSTED_REASON and fid in planned_factors
        ],
        "computed_factors": computed,
        "factor_errors": errors,
        "attempts": attempts,
        "progress_notes": notes,
        "capabilities_filled": sorted(set(filled)),
        "capabilities_still_missing": _still_missing(plan, filled=filled),
    }


def _timed_call(runner: Callable[[], Any]) -> tuple[Any, int]:
    started = time.monotonic()
    payload = runner()
    return payload, int((time.monotonic() - started) * 1000)


def _still_missing(plan: Mapping[str, Any], *, filled: Sequence[str]) -> list[str]:
    filled_set = set(filled)
    missing: list[str] = []
    for domain in plan.get("domains") or []:
        for cap in domain.get("missing_capabilities") or []:
            if cap not in filled_set:
                missing.append(str(cap))
    return sorted(set(missing))


def factor_payloads_to_observations(
    computed_factors: Mapping[str, Any],
    *,
    geometry_hash: str,
    factor_errors: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Project successful factor payloads into supplement observations."""
    observations: list[dict[str, Any]] = []
    errors = dict(factor_errors or {})
    for factor_id, payload in sorted(computed_factors.items()):
        if not isinstance(payload, Mapping):
            continue
        if factor_id in errors:
            continue
        tool_id = FACTOR_TO_TOOL.get(factor_id, factor_id)
        facts = list(payload.get("land_facts") or [])
        if not facts:
            facts = _project_scalar_measurements_as_facts(
                factor_id, payload, geometry_hash
            )
        for fact in facts:
            if not isinstance(fact, Mapping):
                continue
            variable_id = str(fact.get("variable_id") or "")
            domain = _domain_for_variable(variable_id)
            if domain is None:
                continue
            value = fact.get("value")
            if value is None:
                continue
            observations.append(
                {
                    "observation_id": f"SUPPLEMENT_{variable_id}",
                    "field_id": variable_id,
                    "domain": domain,
                    "value": value,
                    "unit": fact.get("unit"),
                    "provider": PROVIDER_SUPPLEMENT,
                    "source_name": fact.get("source_id")
                    or payload.get("canonical_source_id")
                    or tool_id,
                    "source_url": None,
                    "dataset_vintage": fact.get("source_version"),
                    "fetched_at": None,
                    "confidence": fact.get("confidence_or_quality_status"),
                    "status": "RETRIEVED",
                    "spatial_semantics": _normalize_spatial(
                        fact.get("spatial_semantics") or "PARCEL"
                    ),
                    "temporal_semantics": fact.get("temporal_semantics"),
                    "canonical_for_parcel_facts": _normalize_spatial(
                        fact.get("spatial_semantics") or "PARCEL"
                    )
                    == "PARCEL",
                    "geometry_hash_ref": fact.get("geometry_hash") or geometry_hash,
                    "supplement_tool_id": tool_id,
                    "factor_id": factor_id,
                    "notes": "RANGEMATCH_SUPPLEMENT",
                }
            )
    # Explicit SOURCE_UNAVAILABLE rows for failed planned factors (honest, no fixtures).
    for factor_id, reason in sorted(errors.items()):
        tool_id = FACTOR_TO_TOOL.get(factor_id, factor_id)
        observations.append(
            {
                "observation_id": f"SUPPLEMENT_FAILURE_{factor_id}",
                "field_id": factor_id,
                "domain": _domain_for_failed_factor(factor_id),
                "value": None,
                "unit": None,
                "provider": PROVIDER_SUPPLEMENT,
                "source_name": tool_id,
                "source_url": None,
                "dataset_vintage": None,
                "fetched_at": None,
                "confidence": None,
                "status": "SOURCE_UNAVAILABLE",
                "spatial_semantics": "PARCEL",
                "temporal_semantics": None,
                "canonical_for_parcel_facts": False,
                "geometry_hash_ref": geometry_hash,
                "supplement_tool_id": tool_id,
                "factor_id": factor_id,
                "rejection_reason": reason,
                "notes": "adapter failure retained honestly; no fixture substitution",
            }
        )
    return observations


def _domain_for_failed_factor(factor_id: str) -> str:
    tool = FACTOR_TO_TOOL.get(factor_id, "")
    if tool == TOOL_F01:
        return "TERRAIN"
    if tool in {TOOL_F02, TOOL_F08}:
        return "FEED_VEGETATION"
    if tool == TOOL_F03:
        return "WATER"
    if tool == TOOL_F04:
        return "SOIL_ECOLOGY"
    if tool == TOOL_F05:
        return "CLIMATE_HAZARD"
    return "TERRAIN"


def build_combined_environmental_evidence_packet(
    *,
    mireye_profile: Mapping[str, Any],
    gap_plan: Mapping[str, Any],
    supplement_execution: Mapping[str, Any],
    f06: Mapping[str, Any] | None = None,
    geometry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge Mireye + F06 + supplements without semantic overwrite."""
    geometry_hash = str(
        (mireye_profile.get("parcel_ref") or {}).get("geometry_hash") or ""
    )
    mireye_obs = [
        dict(obs)
        for obs in (mireye_profile.get("observations") or [])
        if isinstance(obs, Mapping)
    ]
    for obs in mireye_obs:
        obs.setdefault("provider", PROVIDER_MIREYE)

    if f06 is None and geometry is not None and geometry_hash:
        f06 = derive_confirmed_f06(
            geometry,
            geometry_hash=geometry_hash,
            geometry_id=(mireye_profile.get("parcel_ref") or {}).get(
                "parcel_resolution_id"
            ),
        )

    f06_obs: list[dict[str, Any]] = []
    if isinstance(f06, Mapping):
        factor = f06.get("factor") if isinstance(f06.get("factor"), Mapping) else f06
        summary = f06.get("summary") if isinstance(f06.get("summary"), Mapping) else {}
        area = summary.get("area_m2")
        if area is None and isinstance(factor, Mapping):
            area = factor.get("area_m2")
        if area is not None:
            f06_obs.append(
                {
                    "observation_id": "CORE_F06_AREA_M2",
                    "field_id": "VAR_F06_AREA_M2",
                    "domain": "TERRAIN",
                    "value": area,
                    "unit": "m2",
                    "provider": PROVIDER_CORE,
                    "source_name": "CONFIRMED_GEOMETRY",
                    "source_url": None,
                    "dataset_vintage": None,
                    "fetched_at": None,
                    "confidence": None,
                    "status": "RETRIEVED",
                    "spatial_semantics": "PARCEL",
                    "temporal_semantics": None,
                    "canonical_for_parcel_facts": True,
                    "geometry_hash_ref": geometry_hash,
                    "notes": "ALWAYS_ON_CORE_DERIVATION",
                }
            )

    supplement_obs = factor_payloads_to_observations(
        supplement_execution.get("computed_factors") or {},
        geometry_hash=geometry_hash,
        factor_errors=supplement_execution.get("factor_errors") or {},
    )

    conflicts = _detect_conflicts(mireye_obs, supplement_obs)
    packet = {
        "schema_version": "combined_environmental_evidence_packet@1.0.0",
        "run_id": mireye_profile.get("run_id") or gap_plan.get("run_id"),
        "profile_hash": mireye_profile.get("profile_hash"),
        "plan_hash": gap_plan.get("plan_hash"),
        "parcel_ref": mireye_profile.get("parcel_ref"),
        "mireye_observations": mireye_obs,
        "core_observations": f06_obs,
        "supplement_observations": supplement_obs,
        "conflicts": conflicts,
        "gap_plan": {
            "plan_hash": gap_plan.get("plan_hash"),
            "ordered_supplemental_tool_ids": list(
                gap_plan.get("ordered_supplemental_tool_ids") or []
            ),
            "domains": list(gap_plan.get("domains") or []),
        },
        "execution": {
            "planned_tool_ids": list(supplement_execution.get("planned_tool_ids") or []),
            "attempted_tool_ids": list(
                supplement_execution.get("attempted_tool_ids") or []
            ),
            "succeeded_tool_ids": list(
                supplement_execution.get("succeeded_tool_ids") or []
            ),
            "failed_tool_ids": list(supplement_execution.get("failed_tool_ids") or []),
            "skipped_tool_ids": list(supplement_execution.get("skipped_tool_ids") or []),
            "capabilities_filled": list(
                supplement_execution.get("capabilities_filled") or []
            ),
            "capabilities_still_missing": list(
                supplement_execution.get("capabilities_still_missing") or []
            ),
            "attempts": list(supplement_execution.get("attempts") or []),
            "f06_counted_as_supplement": False,
        },
        "provenance": {
            "providers": [PROVIDER_MIREYE, PROVIDER_CORE, PROVIDER_SUPPLEMENT],
            "merge_rules": [
                "never_average_or_overwrite_different_spatial_semantics",
                "preserve_values_that_answer_different_spatial_questions",
                "expose_conflicts_llm_cannot_resolve",
                "no_fixture_substitution_on_adapter_failure",
            ],
        },
    }
    packet["packet_hash"] = sha256_canonical(
        {k: v for k, v in packet.items() if k != "packet_hash"}
    )
    return packet


def _detect_conflicts(
    mireye_obs: Sequence[Mapping[str, Any]],
    supplement_obs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Surface co-existing Mireye vs supplement evidence; never overwrite."""
    conflicts: list[dict[str, Any]] = []
    # Pair by coarse domain when both sides have retrieved values with different semantics.
    mireye_by_domain: dict[str, list[Mapping[str, Any]]] = {}
    for obs in mireye_obs:
        if obs.get("status") not in {"RETRIEVED", "PARTIAL"}:
            continue
        mireye_by_domain.setdefault(str(obs.get("domain")), []).append(obs)
    for obs in supplement_obs:
        if obs.get("status") != "RETRIEVED":
            continue
        domain = str(obs.get("domain"))
        for prior in mireye_by_domain.get(domain) or []:
            if prior.get("spatial_semantics") == obs.get("spatial_semantics"):
                # Same semantics + same domain: record as co-existing sources, not merge.
                if prior.get("field_id") == obs.get("field_id"):
                    conflicts.append(
                        {
                            "domain": domain,
                            "kind": "SAME_FIELD_MULTI_PROVIDER",
                            "mireye_ref": prior.get("observation_id"),
                            "supplement_ref": obs.get("observation_id"),
                            "mireye_spatial_semantics": prior.get("spatial_semantics"),
                            "supplement_spatial_semantics": obs.get("spatial_semantics"),
                            "resolution": "KEEP_BOTH_DO_NOT_AVERAGE",
                        }
                    )
            else:
                conflicts.append(
                    {
                        "domain": domain,
                        # A POINT sample and a PARCEL statistic describe
                        # different spatial supports. Their numeric difference
                        # is expected and must not be treated as a land defect
                        # or a source contradiction.
                        "kind": "SPATIAL_SCALE_DIFFERENCE",
                        "mireye_ref": prior.get("observation_id"),
                        "supplement_ref": obs.get("observation_id"),
                        "mireye_spatial_semantics": prior.get("spatial_semantics"),
                        "supplement_spatial_semantics": obs.get("spatial_semantics"),
                        "resolution": "KEEP_BOTH_INTERPRET_AT_ORIGINAL_SCALE",
                        "affects_domain_confidence": False,
                    }
                )
                break
    return conflicts
