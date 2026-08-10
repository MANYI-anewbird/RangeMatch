"""Bounded async investigation job runner.

POST /v1/investigations enqueues a QUEUED record; this module claims the job
once (QUEUED → RUNNING) and runs the existing Planner/Executor without changing
Factor science, Engine rules, Unified Output projection, or Report Validator.

Test hooks can hold jobs so QUEUED/RUNNING mid-states are observable.
"""

from __future__ import annotations

import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from rangematch.investigation_store import get_investigation_store
from rangematch.planner_executor import execute_plan
from rangematch.tool_runners import ExecutionFixtures

REPO_ROOT = Path(__file__).resolve().parents[2]
APPROVED_DATA_ROOT = (REPO_ROOT / "test-data").resolve()
APPROVED_CPER_PROFILE = (
    APPROVED_DATA_ROOT / "land-profiles" / "land_profile_cper_001.json"
).resolve()
APPROVED_CPER_GEOMETRY = (
    APPROVED_DATA_ROOT / "engineering_test_geometry_cper_001.geojson"
).resolve()

_HOLD_JOBS = False
_HELD_JOBS: list[Callable[[], None]] = []


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def set_hold_investigation_jobs_for_tests(hold: bool) -> None:
    global _HOLD_JOBS
    _HOLD_JOBS = hold
    if not hold:
        flush_held_investigation_jobs_for_tests()


def flush_held_investigation_jobs_for_tests() -> None:
    while _HELD_JOBS:
        job = _HELD_JOBS.pop(0)
        job()


def reset_investigation_job_hooks_for_tests() -> None:
    global _HOLD_JOBS
    _HOLD_JOBS = False
    _HELD_JOBS.clear()


def schedule_investigation_job(
    run: Callable[[], None],
    *,
    background_tasks: Any | None = None,
) -> None:
    """Schedule job on FastAPI BackgroundTasks, or hold for tests."""
    if _HOLD_JOBS:
        _HELD_JOBS.append(run)
        return
    if background_tasks is not None:
        background_tasks.add_task(run)
        return
    run()


def pending_trace_from_plan(plan: dict[str, Any] | None) -> dict[str, Any]:
    steps = []
    for step in (plan or {}).get("steps") or []:
        steps.append(
            {
                "step_id": step.get("step_id"),
                "tool_id": step.get("tool_id"),
                "action": step.get("action"),
                "status": "PENDING",
                "dependency_step_ids": list(step.get("dependency_step_ids") or []),
                "runner_id": None,
                "reused_artifact_refs": [],
                "output_refs": [],
                "failure": None,
                "parallel_group": step.get("parallel_group"),
                "factor_id": step.get("factor_id"),
            }
        )
    return {
        "execution_id": None,
        "execution_status": "QUEUED",
        "plan_sha256": (plan or {}).get("plan_sha256"),
        "deterministic_execution_hash": None,
        "step_order_executed": [],
        "canonical_factor_report_order": (plan or {}).get("canonical_factor_report_order"),
        "steps": steps,
        "failures": [],
        "artifact_refs": [],
        "constraints": (plan or {}).get("constraints"),
    }


def build_trace_from_execution(execution: dict[str, Any]) -> dict[str, Any]:
    steps = []
    for step in execution.get("steps") or []:
        steps.append(
            {
                "step_id": step.get("step_id"),
                "tool_id": step.get("tool_id"),
                "action": step.get("action"),
                "status": step.get("status"),
                "dependency_step_ids": step.get("dependency_step_ids"),
                "runner_id": step.get("runner_id"),
                "reused_artifact_refs": step.get("reused_artifact_refs"),
                "output_refs": step.get("output_refs"),
                "failure": step.get("failure"),
                "parallel_group": step.get("parallel_group"),
                "factor_id": step.get("factor_id"),
            }
        )
    return {
        "execution_id": execution.get("execution_id"),
        "execution_status": execution.get("execution_status") or "RUNNING",
        "plan_sha256": execution.get("plan_sha256"),
        "deterministic_execution_hash": execution.get("deterministic_execution_hash"),
        "step_order_executed": execution.get("step_order_executed"),
        "canonical_factor_report_order": execution.get("canonical_factor_report_order"),
        "steps": steps,
        "failures": execution.get("failures") or [],
        "artifact_refs": sorted(
            k for k in (execution.get("artifacts") or {}) if not str(k).startswith("_")
        ),
        "constraints": execution.get("constraints"),
    }


class _LiveCollectionProgress:
    """Expose the real pre-executor network collection through the public trace.

    Live adapters must collect their parcel artifacts before the deterministic
    runners can consume them. Without this bridge the UI sees every planner step
    as PENDING during the slowest part of a run, then jumps straight to terminal.
    """

    def __init__(
        self,
        plan: dict[str, Any],
        emit: Callable[[dict[str, Any]], None],
    ) -> None:
        self.plan = plan
        self.emit = emit
        self.steps: list[dict[str, Any]] = []
        for step in plan.get("steps") or []:
            self.steps.append(
                {
                    "step_id": step.get("step_id"),
                    "tool_id": step.get("tool_id"),
                    "action": step.get("action"),
                    "status": "PENDING",
                    "dependency_step_ids": list(step.get("dependency_step_ids") or []),
                    "runner_id": None,
                    "reused_artifact_refs": [],
                    "output_refs": [],
                    "failure": None,
                    "parallel_group": step.get("parallel_group"),
                    "factor_id": step.get("factor_id"),
                }
            )
        self.by_tool = {str(step["tool_id"]): step for step in self.steps}

    def _snapshot(self) -> dict[str, Any]:
        completed = [
            str(step["step_id"])
            for step in self.steps
            if step["status"] not in {"PENDING", "RUNNING"}
        ]
        failures = [
            {
                "step_id": step["step_id"],
                "tool_id": step["tool_id"],
                "status": step["status"],
                "failure": step["failure"],
            }
            for step in self.steps
            if step["failure"] is not None
        ]
        return {
            "execution_id": None,
            "plan_sha256": self.plan.get("plan_sha256"),
            "execution_status": "RUNNING",
            "step_order_executed": completed,
            "canonical_factor_report_order": self.plan.get(
                "canonical_factor_report_order"
            ),
            "steps": deepcopy(self.steps),
            "failures": failures,
            "artifacts": {},
            "constraints": self.plan.get("constraints"),
        }

    def set(self, tool_id: str, status: str, *, error: str | None = None) -> None:
        step = self.by_tool.get(tool_id)
        if step is None:
            return
        step["status"] = status
        step["failure"] = (
            {
                "error_code": "LIVE_COLLECTION_FAILED",
                "message": error or "live_collection_failed",
                "retryable": False,
            }
            if error
            else None
        )
        self.emit(self._snapshot())


def _map_exec_status(exec_status: str | None) -> str:
    if exec_status == "SUCCEEDED":
        return "COMPLETED"
    if exec_status == "PARTIAL":
        return "PARTIAL"
    return "FAILED"


def run_investigation_job(investigation_id: str) -> None:
    """Claim and execute one investigation. No-ops if already claimed/terminal."""
    store = get_investigation_store()
    if not store.try_claim(investigation_id):
        return

    current = store.get(investigation_id) or {}
    prior_trace = dict(current.get("trace") or {})
    prior_trace["execution_status"] = "RUNNING"
    store.update(
        investigation_id,
        {"started_at": _utc_now(), "trace": prior_trace},
    )
    record = store.get(investigation_id) or {}
    job = record.get("_job") or {}
    kind = job.get("kind")

    def on_progress(partial: dict[str, Any]) -> None:
        store.update(
            investigation_id,
            {
                "status": "RUNNING",
                "trace": build_trace_from_execution(partial),
            },
        )

    try:
        if kind in {"DEMO_FIXTURE", "EXISTING_LAND_PROFILE"}:
            _run_land_profile_job(investigation_id, record, job, on_progress)
        elif kind == "PARCEL_RESOLUTION":
            _run_parcel_resolution_job(investigation_id, record, job, on_progress)
        else:
            store.update(
                investigation_id,
                {
                    "status": "FAILED",
                    "completed_at": _utc_now(),
                    "limitations": list(record.get("limitations") or [])
                    + [f"unknown_job_kind:{kind}"],
                },
            )
    except Exception as exc:  # noqa: BLE001
        store.update(
            investigation_id,
            {
                "status": "FAILED",
                "completed_at": _utc_now(),
                "unified_output": None,
                "limitations": list(record.get("limitations") or [])
                + [f"investigation_job_failed:{type(exc).__name__}"],
                "trace": {
                    **((store.get(investigation_id) or {}).get("trace") or {}),
                    "execution_status": "FAILED",
                    "failures": [
                        {
                            "error_code": type(exc).__name__,
                            "message": str(exc)[:300],
                        }
                    ],
                },
            },
        )


def _finalize_execution(
    investigation_id: str,
    *,
    plan: dict[str, Any],
    execution: dict[str, Any],
    extra_limitations: list[str],
    presentation: Any,
    extra_fields: dict[str, Any] | None = None,
) -> None:
    store = get_investigation_store()
    art_store = execution.get("_artifact_store") or {}
    unified = art_store.get("unified_output")
    status = _map_exec_status(execution.get("execution_status"))
    patch: dict[str, Any] = {
        "status": status,
        "completed_at": _utc_now(),
        "plan_ref": plan.get("plan_id"),
        "plan_sha256": plan.get("plan_sha256"),
        "execution_ref": execution.get("execution_id"),
        "deterministic_execution_hash": execution.get("deterministic_execution_hash"),
        "unified_output_ref": (
            f"memory://{investigation_id}/unified_output" if unified else None
        ),
        "unified_output": unified,
        "trace": build_trace_from_execution(execution),
        "limitations": extra_limitations,
        "presentation": presentation,
    }
    if extra_fields:
        patch.update(extra_fields)
    store.update(investigation_id, patch)


def _run_land_profile_job(
    investigation_id: str,
    record: dict[str, Any],
    job: dict[str, Any],
    on_progress: Callable[[dict[str, Any]], None],
) -> None:
    from rangematch.api import _load_json, _mireye_fixture_bundle

    plan = job["plan"]
    profile_path = Path(job["profile_path"])
    land_profile = job.get("land_profile")
    mireye_blocked = bool(job.get("mireye_blocked"))
    fixtures = ExecutionFixtures(
        land_profile=land_profile,
        geometry=_load_json(APPROVED_CPER_GEOMETRY)
        if profile_path.resolve() == APPROVED_CPER_PROFILE
        else None,
        mireye_contexts=_mireye_fixture_bundle(blocked_external=mireye_blocked),
        mireye_blocked_external=mireye_blocked,
    )
    execution = execute_plan(plan, fixtures=fixtures, on_progress=on_progress)
    limitations = list(record.get("limitations") or [])
    replay_label = record.get("replay_label")
    if replay_label and replay_label not in limitations:
        limitations = [replay_label, *limitations]
    if mireye_blocked:
        note = (
            "Mireye context BLOCKED_EXTERNAL (documented SafeBrowse middlebox); "
            "canonical fixture Factor paths were not blocked."
        )
        if note not in limitations:
            limitations.append(note)
    uo_limits = list(
        ((execution.get("_artifact_store") or {}).get("unified_output") or {}).get(
            "limitations"
        )
        or []
    )
    for item in uo_limits:
        if item not in limitations:
            limitations.append(item)
    _finalize_execution(
        investigation_id,
        plan=plan,
        execution=execution,
        extra_limitations=limitations,
        presentation=execution.get("presentation") or plan.get("presentation"),
    )


def _run_parcel_resolution_job(
    investigation_id: str,
    record: dict[str, Any],
    job: dict[str, Any],
    on_progress: Callable[[dict[str, Any]], None],
) -> None:
    from rangematch.api import _mireye_fixture_bundle

    plan = job["plan"]
    binding = job["binding"]
    parcel_geometry = binding["parcel_geometry"]
    mireye_mode = job.get("mireye_mode") or "BLOCKED_EXTERNAL"
    collection_progress = _LiveCollectionProgress(plan, on_progress)
    collection_progress.set("geometry.validate_one_parcel", "RUNNING")
    collection_progress.set("geometry.validate_one_parcel", "SUCCEEDED")
    collection_progress.set("geometry.resolve", "RUNNING")
    collection_progress.set("geometry.resolve", "SUCCEEDED")

    mireye_contexts: dict[str, Any] = {}
    computed_factors: dict[str, Any] = {}
    live_factor_errors: dict[str, str] = {}
    rap_acquisition_summary: dict[str, Any] | None = None
    mireye_blocked: bool | dict[str, bool] = mireye_mode == "BLOCKED_EXTERNAL"
    live_mireye_summary: dict[str, Any] | None = None

    if mireye_mode == "FIXTURE":
        mireye_contexts = _mireye_fixture_bundle(blocked_external=False)
        if job.get("approved_demo_profile"):
            import json
            from rangematch.parcel_resolution import compute_geometry_hash

            profile = json.loads(APPROVED_CPER_PROFILE.read_text(encoding="utf-8"))
            approved_geometry = json.loads(
                APPROVED_CPER_GEOMETRY.read_text(encoding="utf-8")
            )
            if binding["geometry_hash"] != compute_geometry_hash(approved_geometry):
                raise ValueError("APPROVED_DEMO_GEOMETRY_HASH_MISMATCH")
            computed_factors = deepcopy(dict(profile.get("factors") or {}))
            for factor in computed_factors.values():
                if isinstance(factor, dict) and factor.get("geometry_hash"):
                    factor["source_profile_geometry_hash"] = factor["geometry_hash"]
                    factor["geometry_hash"] = binding["geometry_hash"]
            for tool_id in (
                "adapter.usgs_3dep",
                "adapter.rap_cover_production",
                "adapter.nhd_water_candidates",
                "adapter.usda_sda",
                "adapter.noaa_ncei_precip",
                "adapter.tiger_roads",
            ):
                collection_progress.set(tool_id, "RUNNING")
                collection_progress.set(tool_id, "SUCCEEDED")
    elif mireye_mode == "LIVE":
        from shapely.geometry import shape

        from rangematch.mireye_adapter import collect_live_mireye_contexts

        feature = parcel_geometry["features"][0]
        centroid = shape(feature["geometry"]).centroid
        mireye_tools = (
            "mireye.property_diligence",
            "mireye.point_land",
            "mireye.point_hazard",
        )
        for tool_id in mireye_tools:
            collection_progress.set(tool_id, "RUNNING")
        try:
            live_mireye_summary = collect_live_mireye_contexts(
                lat=float(centroid.y),
                lng=float(centroid.x),
                parcel_geometry_hash=binding["geometry_hash"],
            )
        except Exception as exc:  # noqa: BLE001
            for tool_id in mireye_tools:
                collection_progress.set(tool_id, "BLOCKED_EXTERNAL", error=type(exc).__name__)
            raise
        mireye_contexts = dict(live_mireye_summary["contexts"])
        mireye_blocked = {
            context_type: context_type in live_mireye_summary["errors"]
            for context_type in (
                "PROPERTY_DILIGENCE_CONTEXT",
                "POINT_LAND_CONTEXT",
                "POINT_HAZARD_CONTEXT",
            )
        }
        context_tool = {
            "PROPERTY_DILIGENCE_CONTEXT": "mireye.property_diligence",
            "POINT_LAND_CONTEXT": "mireye.point_land",
            "POINT_HAZARD_CONTEXT": "mireye.point_hazard",
        }
        for context_type, tool_id in context_tool.items():
            error = live_mireye_summary["errors"].get(context_type)
            collection_progress.set(
                tool_id,
                "BLOCKED_EXTERNAL" if error else "SUCCEEDED",
                error=str(error) if error else None,
            )
        from rangematch.f01_3dep_adapter import F01AdapterError, collect_f01_from_usgs_3dep

        collection_progress.set("adapter.usgs_3dep", "RUNNING")
        try:
            computed_factors["F01_TOPOGRAPHY"] = collect_f01_from_usgs_3dep(
                geometry=parcel_geometry,
                geometry_id=str(binding["geometry_id"]),
                geometry_hash=str(binding["geometry_hash"]),
            )
            collection_progress.set("adapter.usgs_3dep", "SUCCEEDED")
        except Exception as exc:  # noqa: BLE001
            live_factor_errors["F01_TOPOGRAPHY"] = (
                str(exc) if isinstance(exc, F01AdapterError) else type(exc).__name__
            )
            collection_progress.set(
                "adapter.usgs_3dep", "PARTIAL", error=live_factor_errors["F01_TOPOGRAPHY"]
            )
        from rangematch.f02_rap_adapter import (
            F02RAPAdapterError,
            collect_f02_f08_from_rap,
        )

        collection_progress.set("adapter.rap_cover_production", "RUNNING")
        try:
            rap_result = collect_f02_f08_from_rap(
                geometry=parcel_geometry,
                geometry_id=str(binding["geometry_id"]),
                geometry_hash=str(binding["geometry_hash"]),
            )
            computed_factors.update(rap_result["factors"])
            rap_acquisition_summary = {
                "cover_request_count": rap_result["cover_request_count"],
                "production_request_count": rap_result["production_request_count"],
                "duplicate_coverV3_fetch": rap_result["duplicate_coverV3_fetch"],
                "cover_response_hash": rap_result["cover_response_hash"],
                "f08_reuses_f02_cover_artifact": True,
            }
            collection_progress.set("adapter.rap_cover_production", "SUCCEEDED")
        except Exception as exc:  # noqa: BLE001
            reason = (
                str(exc) if isinstance(exc, F02RAPAdapterError) else type(exc).__name__
            )
            live_factor_errors["F02_HERBACEOUS_RESOURCE"] = reason
            live_factor_errors["F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"] = (
                "BLOCKED_BY_F02_SHARED_RAP_ARTIFACT"
            )
            collection_progress.set(
                "adapter.rap_cover_production", "PARTIAL", error=reason
            )
        from rangematch.f03_nhd_adapter import F03NHDAdapterError, collect_f03_from_usgs_nhd

        collection_progress.set("adapter.nhd_water_candidates", "RUNNING")
        try:
            computed_factors["F03_LIVESTOCK_WATER"] = collect_f03_from_usgs_nhd(
                geometry=parcel_geometry,
                geometry_id=str(binding["geometry_id"]),
                geometry_hash=str(binding["geometry_hash"]),
            )
            collection_progress.set("adapter.nhd_water_candidates", "SUCCEEDED")
        except Exception as exc:  # noqa: BLE001
            live_factor_errors["F03_LIVESTOCK_WATER"] = (
                str(exc) if isinstance(exc, F03NHDAdapterError) else type(exc).__name__
            )
            collection_progress.set(
                "adapter.nhd_water_candidates",
                "PARTIAL",
                error=live_factor_errors["F03_LIVESTOCK_WATER"],
            )
        from rangematch.f04_sda_adapter import F04SDAAdapterError, collect_f04_from_usda_sda

        collection_progress.set("adapter.usda_sda", "RUNNING")
        try:
            computed_factors["F04_SOIL_WETNESS_ECOLOGICAL_SITE"] = (
                collect_f04_from_usda_sda(
                    geometry=parcel_geometry,
                    geometry_id=str(binding["geometry_id"]),
                    geometry_hash=str(binding["geometry_hash"]),
                    mireye_context=mireye_contexts.get("POINT_LAND_CONTEXT"),
                )
            )
            collection_progress.set("adapter.usda_sda", "SUCCEEDED")
        except Exception as exc:  # noqa: BLE001
            live_factor_errors["F04_SOIL_WETNESS_ECOLOGICAL_SITE"] = (
                str(exc) if isinstance(exc, F04SDAAdapterError) else type(exc).__name__
            )
            collection_progress.set(
                "adapter.usda_sda",
                "PARTIAL",
                error=live_factor_errors["F04_SOIL_WETNESS_ECOLOGICAL_SITE"],
            )
        from rangematch.f05_noaa_adapter import (
            F05NOAAAdapterError,
            collect_f05_from_noaa_normals,
        )

        collection_progress.set("adapter.noaa_ncei_precip", "RUNNING")
        try:
            computed_factors["F05_CLIMATE_DROUGHT_EXPOSURE"] = (
                collect_f05_from_noaa_normals(
                    geometry=parcel_geometry,
                    geometry_id=str(binding["geometry_id"]),
                    geometry_hash=str(binding["geometry_hash"]),
                    mireye_context=mireye_contexts.get("POINT_LAND_CONTEXT"),
                )
            )
            collection_progress.set("adapter.noaa_ncei_precip", "SUCCEEDED")
        except Exception as exc:  # noqa: BLE001
            live_factor_errors["F05_CLIMATE_DROUGHT_EXPOSURE"] = (
                str(exc) if isinstance(exc, F05NOAAAdapterError) else type(exc).__name__
            )
            collection_progress.set(
                "adapter.noaa_ncei_precip",
                "PARTIAL",
                error=live_factor_errors["F05_CLIMATE_DROUGHT_EXPOSURE"],
            )
        from rangematch.f07_tiger_adapter import derive_f07_via_tiger_adapter

        collection_progress.set("adapter.tiger_roads", "RUNNING")
        try:
            tiger_cache_dir = Path(
                os.environ.get(
                    "RANGEMATCH_TIGER_CACHE_DIR",
                    "/tmp/rangematch/tiger2025_cache",
                )
            )
            f07 = derive_f07_via_tiger_adapter(
                parcel_geometry,
                cache_dir=tiger_cache_dir,
                geometry_id=str(binding["geometry_id"]),
                geometry_hash=str(binding["geometry_hash"]),
                geometry_reference=str(binding["geometry_reference"]),
            )
            f07.pop("_collection", None)
            computed_factors["F07_ROAD_AND_PHYSICAL_ACCESS"] = f07
            collection_progress.set("adapter.tiger_roads", "SUCCEEDED")
        except Exception as exc:  # noqa: BLE001
            live_factor_errors["F07_ROAD_AND_PHYSICAL_ACCESS"] = type(exc).__name__
            collection_progress.set(
                "adapter.tiger_roads",
                "PARTIAL",
                error=live_factor_errors["F07_ROAD_AND_PHYSICAL_ACCESS"],
            )

    fixtures = ExecutionFixtures(
        geometry=parcel_geometry,
        mireye_contexts=mireye_contexts,
        mireye_blocked_external=mireye_blocked,
        computed_factors=computed_factors,
    )
    execution = execute_plan(plan, fixtures=fixtures, on_progress=on_progress)
    art_store = execution.get("_artifact_store") or {}
    unified = art_store.get("unified_output")

    limitations = list((unified or {}).get("limitations") or [])
    limitations = [
        "execution_source:PARCEL_RESOLUTION",
        "geometry_bound_from_confirmed_parcel_resolution",
        f"geometry_hash:{binding['geometry_hash']}",
        "f01_f08_confirmed_parcel_collection_attempted",
        (
            "approved_geometry_matched_cper_demo_replay"
            if job.get("approved_demo_profile")
            else "no_automatic_cper_fixture_substitution"
        ),
        *limitations,
    ]
    if mireye_mode == "LIVE" and live_mireye_summary is not None:
        limitations.insert(3, "live_mireye_contexts_noncanonical_for_parcel_facts")
        if live_mireye_summary["errors"]:
            limitations.insert(
                4,
                "mireye_live_partial_failures:"
                + ",".join(sorted(live_mireye_summary["errors"])),
            )
        if live_factor_errors:
            limitations.insert(
                5,
                "live_factor_failures:" + ",".join(sorted(live_factor_errors)),
            )
    elif bool(mireye_blocked):
        note = (
            "Mireye context BLOCKED_EXTERNAL for this run; canonical fixture "
            "Factor paths were not used for this resolution geometry."
        )
        if note not in limitations:
            limitations.append(note)

    extra = {
        "mireye_live_summary": (
            {
                "canonical_for_parcel_facts": False,
                "requested_point": live_mireye_summary["requested_point"],
                "context_status": {
                    context_type: context.get("response_status", {}).get(
                        "status", "UNKNOWN"
                    )
                    for context_type, context in live_mireye_summary["contexts"].items()
                },
                "failed_contexts": sorted(live_mireye_summary["errors"]),
            }
            if live_mireye_summary is not None
            else None
        ),
        "live_factor_summary": (
            {
                "computed_factors": sorted(computed_factors),
                "failed_factors": dict(live_factor_errors),
                "rules_changed": False,
                "ranking_effect": "NONE",
                "rap_acquisition": rap_acquisition_summary,
            }
            if mireye_mode == "LIVE"
            else (
                {
                    "computed_factors": sorted(computed_factors),
                    "failed_factors": {},
                    "rules_changed": False,
                    "ranking_effect": "NONE",
                    "demo_fixture": True,
                    "geometry_hash_matched": True,
                }
                if job.get("approved_demo_profile")
                else None
            )
        ),
    }
    _finalize_execution(
        investigation_id,
        plan=plan,
        execution=execution,
        extra_limitations=limitations,
        presentation=execution.get("presentation") or plan.get("presentation"),
        extra_fields=extra,
    )
