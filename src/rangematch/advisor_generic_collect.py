"""Collect F01–F08 for a confirmed non-CPER parcel and assemble Unified Output.

Production uses live adapters (honest PARTIAL/FAILED). Tests inject a collect
hook so advisor unit tests never open USGS/RAP/NHD/TIGER sockets.
Contract: docs/ADVISOR_GENERIC_EVIDENCE_PACKET.md
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, wait
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping

from rangematch.advisor_packet import F03_AVAILABLE, F03_FAILED, F03_NOT_PROVIDED
from rangematch.engine import evaluate_land_profile
from rangematch.f06_derivation import derive_f06_from_geometry
from rangematch.unified_output import project_unified_output

ADAPTER_TIMEOUT_S = 18.0
TOTAL_BUDGET_S = 75.0
ProgressFn = Callable[[dict[str, Any]], None]

LIVE_FACTOR_IDS: tuple[str, ...] = (
    "F01_TOPOGRAPHY",
    "F02_HERBACEOUS_RESOURCE",
    "F03_LIVESTOCK_WATER",
    "F04_SOIL_WETNESS_ECOLOGICAL_SITE",
    "F05_CLIMATE_DROUGHT_EXPOSURE",
    "F07_ROAD_AND_PHYSICAL_ACCESS",
    "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE",
)

UNIT_TEST_HOOK_REASON = "UNIT_TEST_HOOK_NO_LIVE_ADAPTER"
ADAPTER_TIMEOUT_REASON = "ADAPTER_TIMEOUT"
BUDGET_EXHAUSTED_REASON = "BUDGET_EXHAUSTED"
DEPENDENCY_MISSING_REASON = "DEPENDENCY_MISSING"

_FACTOR_LABEL = {
    "F01_TOPOGRAPHY": "F01",
    "F02_HERBACEOUS_RESOURCE": "F02",
    "F03_LIVESTOCK_WATER": "F03",
    "F04_SOIL_WETNESS_ECOLOGICAL_SITE": "F04",
    "F05_CLIMATE_DROUGHT_EXPOSURE": "F05",
    "F07_ROAD_AND_PHYSICAL_ACCESS": "F07",
    "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE": "F08",
}


def _label(factor_id: str) -> str:
    return _FACTOR_LABEL.get(factor_id, factor_id)


def _timeout_note(factor_id: str, reason: str) -> str:
    short = _label(factor_id)
    if reason == BUDGET_EXHAUSTED_REASON:
        return f"{short} skipped — investigation time budget exhausted"
    if reason.startswith(DEPENDENCY_MISSING_REASON):
        missing = reason.split(":", 1)[-1] if ":" in reason else "optional package"
        return f"{short} unavailable — missing dependency {missing}"
    return f"{short} timed out — continuing with remaining evidence"


def _dependency_reason(exc: BaseException) -> str:
    name = getattr(exc, "name", None) or str(exc).split(" ")[-1].strip("'\"") or "unknown"
    return f"{DEPENDENCY_MISSING_REASON}:{name}"


def _is_missing_dependency(exc: BaseException) -> bool:
    return isinstance(exc, ModuleNotFoundError) or (
        isinstance(exc, ImportError) and "No module named" in str(exc)
    )


def set_advisor_collect_timeouts_for_tests(
    *,
    adapter_timeout_s: float | None = None,
    total_budget_s: float | None = None,
) -> None:
    """Tests only. None restores production defaults."""
    global ADAPTER_TIMEOUT_S, TOTAL_BUDGET_S
    ADAPTER_TIMEOUT_S = 18.0 if adapter_timeout_s is None else float(adapter_timeout_s)
    TOTAL_BUDGET_S = 75.0 if total_budget_s is None else float(total_budget_s)


def unit_test_factor_collect(**_kwargs: Any) -> dict[str, Any]:
    """Default advisor test hook: no invented numbers, no live HTTP."""
    return {
        "computed_factors": {},
        "factor_errors": {fid: UNIT_TEST_HOOK_REASON for fid in LIVE_FACTOR_IDS},
        "f03_inventory": None,
        "f03_status": F03_NOT_PROVIDED,
        "f03_remote_pilot": None,
    }


def _default_live_runners(
    *,
    geometry: Mapping[str, Any],
    geometry_id: str,
    geometry_hash: str,
    geometry_reference: str,
    mireye_contexts: Mapping[str, Any],
) -> dict[str, Callable[[], Any]]:
    """Import adapters inside each runner so a missing package cannot kill collect."""

    def f01() -> dict[str, Any]:
        from rangematch.f01_3dep_adapter import collect_f01_from_usgs_3dep

        return collect_f01_from_usgs_3dep(
            geometry=geometry,
            geometry_id=geometry_id,
            geometry_hash=geometry_hash,
        )

    def f02() -> dict[str, Any]:
        from rangematch.f02_rap_adapter import collect_f02_f08_from_rap

        return collect_f02_f08_from_rap(
            geometry=geometry,
            geometry_id=geometry_id,
            geometry_hash=geometry_hash,
        )

    def f03() -> dict[str, Any]:
        from rangematch.f03_nhd_adapter import collect_f03_from_usgs_nhd

        return collect_f03_from_usgs_nhd(
            geometry=geometry,
            geometry_id=geometry_id,
            geometry_hash=geometry_hash,
        )

    def f04() -> dict[str, Any]:
        from rangematch.f04_sda_adapter import collect_f04_from_usda_sda

        return collect_f04_from_usda_sda(
            geometry=geometry,
            geometry_id=geometry_id,
            geometry_hash=geometry_hash,
            mireye_context=mireye_contexts.get("POINT_LAND_CONTEXT"),
        )

    def f05() -> dict[str, Any]:
        from rangematch.f05_noaa_adapter import collect_f05_from_noaa_normals

        return collect_f05_from_noaa_normals(
            geometry=geometry,
            geometry_id=geometry_id,
            geometry_hash=geometry_hash,
            mireye_context=mireye_contexts.get("POINT_LAND_CONTEXT"),
        )

    def f07() -> dict[str, Any]:
        from rangematch.f07_tiger_adapter import derive_f07_via_tiger_adapter

        tiger_cache_dir = Path(
            os.environ.get(
                "RANGEMATCH_TIGER_CACHE_DIR",
                "/tmp/rangematch/tiger2025_cache",
            )
        )
        factor = derive_f07_via_tiger_adapter(
            geometry,
            cache_dir=tiger_cache_dir,
            geometry_id=geometry_id,
            geometry_hash=geometry_hash,
            geometry_reference=geometry_reference,
        )
        factor.pop("_collection", None)
        return factor

    return {
        "F01_TOPOGRAPHY": f01,
        "F02_HERBACEOUS_RESOURCE": f02,
        "F03_LIVESTOCK_WATER": f03,
        "F04_SOIL_WETNESS_ECOLOGICAL_SITE": f04,
        "F05_CLIMATE_DROUGHT_EXPOSURE": f05,
        "F07_ROAD_AND_PHYSICAL_ACCESS": f07,
    }


def _apply_adapter_payload(
    factor_id: str,
    payload: Any,
    *,
    computed: dict[str, Any],
    errors: dict[str, str],
) -> Any:
    if factor_id == "F02_HERBACEOUS_RESOURCE" and isinstance(payload, Mapping):
        computed.update(dict(payload.get("factors") or {}))
        return payload.get("candidate_inventory")
    if factor_id == "F03_LIVESTOCK_WATER" and isinstance(payload, Mapping):
        computed[factor_id] = payload
        return payload.get("candidate_inventory")
    if isinstance(payload, Mapping):
        computed[factor_id] = dict(payload)
    else:
        errors[factor_id] = "ADAPTER_EMPTY_RESULT"
    return None


def collect_live_advisor_factors(
    *,
    geometry: Mapping[str, Any],
    geometry_id: str,
    geometry_hash: str,
    geometry_reference: str,
    mireye_contexts: Mapping[str, Any] | None = None,
    adapter_timeout_s: float | None = None,
    total_budget_s: float | None = None,
    on_progress: ProgressFn | None = None,
    runners: Mapping[str, Callable[[], Any]] | None = None,
) -> dict[str, Any]:
    """Call F01–F08 adapters with per-adapter and total-run budgets.

    Timeouts become SOURCE_UNAVAILABLE later — never invent numbers or swap CPER.
    """
    timeout_s = ADAPTER_TIMEOUT_S if adapter_timeout_s is None else float(adapter_timeout_s)
    budget_s = TOTAL_BUDGET_S if total_budget_s is None else float(total_budget_s)
    computed: dict[str, Any] = {}
    errors: dict[str, str] = {}
    notes: list[str] = []
    contexts = dict(mireye_contexts or {})
    f03_inventory = None
    f03_status = F03_NOT_PROVIDED
    deadline = time.monotonic() + max(0.0, budget_s)
    try:
        jobs = dict(
            runners
            or _default_live_runners(
                geometry=geometry,
                geometry_id=geometry_id,
                geometry_hash=geometry_hash,
                geometry_reference=geometry_reference,
                mireye_contexts=contexts,
            )
        )
    except Exception as exc:  # noqa: BLE001 — runner construction must not kill the run
        reason = (
            _dependency_reason(exc)
            if _is_missing_dependency(exc)
            else f"{type(exc).__name__}:{exc}"
        )
        notes = [_timeout_note(fid, reason) for fid in LIVE_FACTOR_IDS]
        return {
            "computed_factors": {},
            "factor_errors": {fid: reason for fid in LIVE_FACTOR_IDS},
            "f03_inventory": None,
            "f03_status": F03_NOT_PROVIDED,
            "f03_remote_pilot": None,
            "progress_notes": notes,
        }

    def emit(factor_id: str, status: str, note: str | None = None) -> None:
        if on_progress is None:
            return
        on_progress({"factor_id": factor_id, "status": status, "note": note})

    def remaining() -> float:
        return max(0.0, deadline - time.monotonic())

    submitted: dict[Any, str] = {}
    worker_count = max(1, min(6, len(jobs) or 1))
    pool = ThreadPoolExecutor(max_workers=worker_count)
    try:
        for factor_id, runner in jobs.items():
            extras = (
                ["F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"]
                if factor_id == "F02_HERBACEOUS_RESOURCE"
                else []
            )
            if remaining() <= 0:
                errors[factor_id] = BUDGET_EXHAUSTED_REASON
                notes.append(_timeout_note(factor_id, BUDGET_EXHAUSTED_REASON))
                emit(factor_id, "PARTIAL", notes[-1])
                for extra in extras:
                    errors[extra] = BUDGET_EXHAUSTED_REASON
                continue
            emit(factor_id, "RUNNING")
            submitted[pool.submit(runner)] = factor_id
        wait_s = min(timeout_s, remaining()) if submitted else 0.0
        done: set[Any] = set()
        not_done: set[Any] = set(submitted)
        if submitted:
            finished, pending = wait(
                list(submitted),
                timeout=wait_s,
                return_when=ALL_COMPLETED,
            )
            done = set(finished)
            not_done = set(pending)
        for fut in done:
            factor_id = submitted[fut]
            extras = (
                ["F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"]
                if factor_id == "F02_HERBACEOUS_RESOURCE"
                else []
            )
            try:
                payload = fut.result(timeout=0)
                inventory = _apply_adapter_payload(
                    factor_id, payload, computed=computed, errors=errors
                )
                if factor_id == "F03_LIVESTOCK_WATER":
                    f03_inventory = inventory
                    f03_status = F03_AVAILABLE
                emit(factor_id, "SUCCEEDED")
            except Exception as exc:  # noqa: BLE001 — keep the real adapter class
                reason = (
                    _dependency_reason(exc)
                    if _is_missing_dependency(exc)
                    else (str(exc) or type(exc).__name__)
                )
                errors[factor_id] = reason
                if _is_missing_dependency(exc):
                    notes.append(_timeout_note(factor_id, reason))
                    emit(factor_id, "PARTIAL", notes[-1])
                else:
                    emit(factor_id, "PARTIAL")
                if factor_id == "F03_LIVESTOCK_WATER":
                    f03_status = F03_FAILED
                for extra in extras:
                    errors.setdefault(
                        extra,
                        reason
                        if _is_missing_dependency(exc)
                        else "BLOCKED_BY_F02_SHARED_RAP_ARTIFACT",
                    )
        for fut in not_done:
            factor_id = submitted[fut]
            extras = (
                ["F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"]
                if factor_id == "F02_HERBACEOUS_RESOURCE"
                else []
            )
            reason = (
                BUDGET_EXHAUSTED_REASON
                if remaining() <= 0
                else ADAPTER_TIMEOUT_REASON
            )
            errors[factor_id] = reason
            notes.append(_timeout_note(factor_id, reason))
            if factor_id == "F03_LIVESTOCK_WATER":
                f03_status = F03_FAILED
            for extra in extras:
                errors.setdefault(extra, reason)
            emit(factor_id, "PARTIAL", notes[-1])
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    if "F03_LIVESTOCK_WATER" not in computed and "F03_LIVESTOCK_WATER" not in errors:
        f03_status = F03_NOT_PROVIDED

    return {
        "computed_factors": computed,
        "factor_errors": errors,
        "f03_inventory": f03_inventory,
        "f03_status": f03_status,
        "f03_remote_pilot": None,
        "progress_notes": notes,
    }


def collect_advisor_factors(
    *,
    geometry: Mapping[str, Any],
    geometry_id: str,
    geometry_hash: str,
    geometry_reference: str,
    mireye_contexts: Mapping[str, Any] | None = None,
    collect_fn: Any | None = None,
    adapter_timeout_s: float | None = None,
    total_budget_s: float | None = None,
    on_progress: ProgressFn | None = None,
    runners: Mapping[str, Callable[[], Any]] | None = None,
) -> dict[str, Any]:
    """Hook when provided; otherwise live adapters. F06 is always derived locally."""
    if collect_fn is not None:
        try:
            collected = dict(
                collect_fn(
                    geometry=geometry,
                    geometry_id=geometry_id,
                    geometry_hash=geometry_hash,
                    geometry_reference=geometry_reference,
                    mireye_contexts=mireye_contexts,
                )
                or {}
            )
        except Exception as exc:  # noqa: BLE001 — hook/import failure must not kill RUN_AGENDA
            reason = (
                _dependency_reason(exc)
                if _is_missing_dependency(exc)
                else f"{type(exc).__name__}:{exc}"
            )
            collected = {
                "computed_factors": {},
                "factor_errors": {fid: reason for fid in LIVE_FACTOR_IDS},
                "f03_inventory": None,
                "f03_status": F03_NOT_PROVIDED,
                "f03_remote_pilot": None,
                "progress_notes": [_timeout_note(fid, reason) for fid in LIVE_FACTOR_IDS],
            }
        collected.setdefault("computed_factors", {})
        collected.setdefault("factor_errors", {})
        collected.setdefault("f03_inventory", None)
        collected.setdefault("f03_status", F03_NOT_PROVIDED)
        collected.setdefault("f03_remote_pilot", None)
        collected.setdefault("progress_notes", [])
        return collected
    return collect_live_advisor_factors(
        geometry=geometry,
        geometry_id=geometry_id,
        geometry_hash=geometry_hash,
        geometry_reference=geometry_reference,
        mireye_contexts=mireye_contexts,
        adapter_timeout_s=adapter_timeout_s,
        total_budget_s=total_budget_s,
        on_progress=on_progress,
        runners=runners,
    )


def assemble_generic_unified_output(
    *,
    geometry: Mapping[str, Any],
    geometry_id: str,
    geometry_hash: str,
    geometry_reference: str,
    run_id: str,
    computed_factors: Mapping[str, Any],
    mireye_items: list[Mapping[str, Any]] | None = None,
    address: str | None = None,
) -> dict[str, Any]:
    """Project a non-CPER Unified Output. Missing factors stay missing."""
    factors = deepcopy(dict(computed_factors or {}))
    if "F06_PARCEL_CONFIGURATION" not in factors:
        factors["F06_PARCEL_CONFIGURATION"] = derive_f06_from_geometry(
            geometry,
            geometry_hash=geometry_hash,
            geometry_reference=geometry_reference,
            geometry_id=geometry_id,
            source_crs="EPSG:4326",
        )
    profile = {
        "land_profile_id": f"ADVISOR_GENERIC_{run_id}",
        "version": "0.2.1",
        "geometry_id": geometry_id,
        "geometry_reference": geometry_reference,
        "geometry_hash": geometry_hash,
        "address": address,
        "supported_use": "BUYER_DILIGENCE",
        "factors": factors,
    }
    match = evaluate_land_profile(deepcopy(profile))
    return project_unified_output(
        profile,
        match,
        mode="DISCOVERY",
        intended_operation=None,
        planned_actions=[],
        run_id=run_id,
        geometry=geometry,
        mireye_context=list(mireye_items or []),
    )


def inventory_from_collection(collected: Mapping[str, Any]) -> Any:
    inventory = collected.get("f03_inventory")
    if inventory is None:
        f03 = (collected.get("computed_factors") or {}).get("F03_LIVESTOCK_WATER") or {}
        inventory = f03.get("candidate_inventory")
    if inventory is None:
        return None
    if isinstance(inventory, Mapping) and "candidate_inventory" in inventory:
        return inventory
    return {"candidate_inventory": list(inventory)}


def paint_generic_agenda(
    plan: Mapping[str, Any],
    *,
    collected: Mapping[str, Any],
    live_contexts: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Mark plan steps from live/hook results. Do not paint failed adapters SUCCEEDED."""
    errors = dict(collected.get("factor_errors") or {})
    computed = dict(collected.get("computed_factors") or {})
    live = dict(live_contexts or {})
    rows: list[dict[str, Any]] = []
    for step in plan.get("steps") or []:
        sid = str(step.get("step_id") or "")
        tool_id = str(step.get("tool_id") or "")
        factor_id = step.get("factor_id")
        status = "PENDING"
        if sid == "S03_MIREYE_PROPERTY":
            status = str(
                (live.get("PROPERTY_DILIGENCE_CONTEXT") or {}).get("status") or "PENDING"
            )
        elif sid == "S04_MIREYE_POINT_LAND":
            status = str(
                (live.get("POINT_LAND_CONTEXT") or {}).get("status") or "PENDING"
            )
        elif sid == "S05_MIREYE_POINT_HAZARD":
            status = str(
                (live.get("POINT_HAZARD_CONTEXT") or {}).get("status") or "PENDING"
            )
        elif factor_id == "F06_PARCEL_CONFIGURATION":
            status = "SUCCEEDED"
        elif factor_id:
            if factor_id in computed and factor_id not in errors:
                status = "SUCCEEDED"
            elif factor_id in errors:
                reason = str(errors[factor_id])
                status = (
                    "TIMED_OUT"
                    if reason in {ADAPTER_TIMEOUT_REASON, BUDGET_EXHAUSTED_REASON}
                    else "PARTIAL"
                )
            else:
                status = "PARTIAL"
        elif tool_id.startswith("profile.") or tool_id.startswith("engine."):
            status = "SUCCEEDED"
        else:
            status = "SUCCEEDED"
        rows.append(
            {
                "step_id": sid,
                "label": sid.split("_", 1)[-1].replace("_", " ").title() if sid else tool_id,
                "tool_id": tool_id,
                "factor_id": factor_id,
                "status": status,
            }
        )
    return rows
