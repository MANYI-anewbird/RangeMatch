"""Fixture-backed Planner Executor — runs an approved DAG without live network."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from uuid import uuid4

from rangematch.planner import PLANNER_VERSION, plan_sha256
from rangematch.tool_registry import (
    CANONICAL_FACTOR_REPORT_ORDER,
    UNAUTHORIZED_TOOL_IDS,
    assert_no_unauthorized_tools,
)
from rangematch.tool_runners import (
    RUNNER_VERSION,
    ExecutionFixtures,
    RunnerContext,
    RunnerError,
    resolve_runner,
)
from rangematch.unified_output import sha256_canonical

EXECUTOR_VERSION = "RANGEMATCH_PLANNER_EXECUTOR@0.1.0"

STEP_PENDING = "PENDING"
STEP_RUNNING = "RUNNING"
STEP_SUCCEEDED = "SUCCEEDED"
STEP_PARTIAL = "PARTIAL"
STEP_FAILED = "FAILED"
STEP_BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
STEP_BLOCKED_DEPENDENCY = "BLOCKED_DEPENDENCY"
STEP_SKIPPED_REUSE = "SKIPPED_REUSE"

TERMINAL_OK = frozenset(
    {STEP_SUCCEEDED, STEP_PARTIAL, STEP_SKIPPED_REUSE, STEP_BLOCKED_EXTERNAL}
)
TERMINAL_ALL = frozenset(
    {
        STEP_SUCCEEDED,
        STEP_PARTIAL,
        STEP_FAILED,
        STEP_BLOCKED_EXTERNAL,
        STEP_BLOCKED_DEPENDENCY,
        STEP_SKIPPED_REUSE,
    }
)

_SECRET_RE = re.compile(
    r"(?i)(authorization|api[_-]?key|bearer\s+[a-z0-9._\-]+|password|client_secret)"
)


class ExecutorError(ValueError):
    """Plan validation or execution policy error."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assert_no_credentials(payload: Any, *, label: str) -> None:
    text = json.dumps(payload, ensure_ascii=False) if not isinstance(payload, str) else payload
    if _SECRET_RE.search(text):
        raise ExecutorError(f"credentials_detected_in_{label}")


def validate_plan(plan: Mapping[str, Any]) -> None:
    if plan.get("planner_version") != PLANNER_VERSION:
        raise ExecutorError(
            f"planner_version_mismatch:expected={PLANNER_VERSION};got={plan.get('planner_version')}"
        )
    if plan.get("live_network_authorized") is True:
        raise ExecutorError("live_network_not_authorized_for_fixture_executor")
    steps = plan.get("steps") or []
    tool_ids = [s.get("tool_id") for s in steps]
    assert_no_unauthorized_tools([t for t in tool_ids if t])
    for tid in tool_ids:
        if tid in UNAUTHORIZED_TOOL_IDS or str(tid).startswith("F09"):
            raise ExecutorError(f"unauthorized_tool:{tid}")
    # plan_sha256 is written after hashing; re-hash must exclude the field itself.
    body = {k: v for k, v in plan.items() if k != "plan_sha256"}
    expected = plan_sha256(body)
    got = plan.get("plan_sha256")
    if got != expected:
        raise ExecutorError("plan_sha256_mismatch")
    if plan.get("execution_model") != "DEPENDENCY_DAG":
        raise ExecutorError("execution_model_must_be_DEPENDENCY_DAG")


def topological_step_order(steps: Sequence[Mapping[str, Any]]) -> list[str]:
    """Deterministic Kahn topo-sort; ties broken by step_id."""
    by_id = {s["step_id"]: s for s in steps}
    indeg = {sid: 0 for sid in by_id}
    children: dict[str, list[str]] = {sid: [] for sid in by_id}
    for step in steps:
        sid = step["step_id"]
        for dep in step.get("dependency_step_ids") or []:
            if dep not in by_id:
                raise ExecutorError(f"missing_dependency_step:{dep}_for_{sid}")
            indeg[sid] += 1
            children[dep].append(sid)
    ready = sorted([sid for sid, d in indeg.items() if d == 0])
    order: list[str] = []
    while ready:
        sid = ready.pop(0)
        order.append(sid)
        for child in sorted(children[sid]):
            indeg[child] -= 1
            if indeg[child] == 0:
                ready.append(child)
                ready.sort()
    if len(order) != len(by_id):
        raise ExecutorError("cyclic_or_incomplete_dependency_dag")
    return order


def _step_nonvolatile(step_record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        k: v
        for k, v in step_record.items()
        if k not in {"started_at", "completed_at"}
    }


def nonvolatile_step_hash(step_record: Mapping[str, Any]) -> str:
    return sha256_canonical(_step_nonvolatile(step_record))


def deterministic_execution_hash(execution: Mapping[str, Any]) -> str:
    payload = {
        "executor_version": execution.get("executor_version"),
        "plan_id": execution.get("plan_id"),
        "plan_sha256": execution.get("plan_sha256"),
        "execution_status": execution.get("execution_status"),
        "steps": [
            _step_nonvolatile(s)
            for s in sorted(execution.get("steps") or [], key=lambda x: x["step_id"])
        ],
        "failures": execution.get("failures") or [],
        "land_profile_ref": execution.get("land_profile_ref"),
        "match_result_ref": execution.get("match_result_ref"),
        "unified_output_ref": execution.get("unified_output_ref"),
        "artifact_keys": sorted((execution.get("artifacts") or {}).keys()),
        "rap_fetch_count": (execution.get("artifacts") or {}).get("_meta", {}).get(
            "rap_fetch_count"
        ),
    }
    return sha256_canonical(payload)


def _is_mireye_tool(tool_id: str) -> bool:
    return tool_id.startswith("mireye.")


def _factor_id_of(step: Mapping[str, Any]) -> str | None:
    return step.get("factor_id")


def dependency_blocks_child(
    *,
    parent: Mapping[str, Any],
    parent_status: str,
    child: Mapping[str, Any],
) -> bool:
    """Return True if parent terminal status hard-blocks child execution."""
    if parent_status in {STEP_SUCCEEDED, STEP_PARTIAL, STEP_SKIPPED_REUSE}:
        return False
    if parent_status == STEP_BLOCKED_EXTERNAL:
        # Mireye external blocks never hard-block canonical factor paths.
        return False
    if parent_status not in {STEP_FAILED, STEP_BLOCKED_DEPENDENCY}:
        return False

    parent_tool = parent.get("tool_id") or ""
    child_tool = child.get("tool_id") or ""
    parent_factor = _factor_id_of(parent)
    child_factor = _factor_id_of(child)

    # Geometry / one-parcel gate blocks parcel workflow.
    if parent_tool in {"geometry.validate_one_parcel", "geometry.resolve"}:
        return True

    # F06 gate blocks peers / F08 / assemble chain that depends on it.
    if parent_factor == "F06_PARCEL_CONFIGURATION":
        return child_tool != "mireye.property_diligence"  # mireye already parallel; deps are geo only

    # F02 failure blocks F08 only.
    if parent_factor == "F02_HERBACEOUS_RESOURCE":
        return child_factor == "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"

    # Assemble may proceed with missing/failed peers (no invented facts).
    if child_tool == "profile.assemble":
        return False

    # Evaluate/project/explain require assemble success-ish.
    if child_tool in {
        "engine.evaluate",
        "output.project_unified",
        "explanation.bind_and_product",
        "diligence.dynamic_from_planned_actions",
    }:
        if parent_tool == "profile.assemble":
            return parent_status in {STEP_FAILED, STEP_BLOCKED_DEPENDENCY}
        if parent_tool == "engine.evaluate":
            return parent_status in {STEP_FAILED, STEP_BLOCKED_DEPENDENCY}
        if parent_tool == "output.project_unified":
            return parent_status in {STEP_FAILED, STEP_BLOCKED_DEPENDENCY}
        return False

    # Peer failures do not block other peers.
    if parent.get("parallel_group") == "peer_factors_after_f06" and child.get(
        "parallel_group"
    ) == "peer_factors_after_f06":
        return False

    # Default: failed hard dep blocks.
    return True


def _geometry_failed(step_records: Mapping[str, Any], steps_by_id: Mapping[str, Any]) -> bool:
    for sid, rec in step_records.items():
        tool = (steps_by_id.get(sid) or {}).get("tool_id")
        if tool in {"geometry.validate_one_parcel", "geometry.resolve"}:
            if rec.get("status") in {STEP_FAILED, STEP_BLOCKED_DEPENDENCY}:
                return True
    return False


def execute_plan(
    plan: Mapping[str, Any],
    *,
    fixtures: ExecutionFixtures,
    execution_id: str | None = None,
    on_progress: Any | None = None,
) -> dict[str, Any]:
    """Execute a validated plan with fixture-backed runners. No live network.

    Optional ``on_progress`` receives a partial execution snapshot after each
    step status change (for async investigation job polling). It must not alter
    Factor/Engine/Unified Output science.
    """
    plan = deepcopy(dict(plan))
    validate_plan(plan)

    steps = list(plan.get("steps") or [])
    steps_by_id = {s["step_id"]: s for s in steps}
    order = topological_step_order(steps)

    started_at = _utc_now()
    execution_id = execution_id or f"exec_{uuid4().hex[:16]}"
    artifacts: dict[str, Any] = {
        "_meta": {
            "network_authorized": False,
            "rap_fetch_count": 0,
            "executor_version": EXECUTOR_VERSION,
            "runner_version": RUNNER_VERSION,
        }
    }
    step_records: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []

    for step in steps:
        step_records[step["step_id"]] = {
            "step_id": step["step_id"],
            "tool_id": step["tool_id"],
            "action": step.get("action"),
            "dependency_step_ids": list(step.get("dependency_step_ids") or []),
            "runner_id": None,
            "runner_version": None,
            "status": STEP_PENDING,
            "input_refs": list(step.get("input_refs") or []),
            "output_refs": [],
            "reused_artifact_refs": [],
            "failure": None,
            "started_at": None,
            "completed_at": None,
            "parallel_group": step.get("parallel_group"),
            "factor_id": step.get("factor_id"),
            "report_order_index": step.get("report_order_index"),
            "nonvolatile_step_hash": None,
        }

    def _emit_progress(*, execution_status: str = "RUNNING") -> None:
        if on_progress is None:
            return
        on_progress(
            {
                "execution_id": execution_id,
                "plan_sha256": plan.get("plan_sha256"),
                "execution_status": execution_status,
                "step_order_executed": [
                    sid
                    for sid in order
                    if step_records[sid]["status"]
                    not in {STEP_PENDING, STEP_RUNNING}
                ],
                "canonical_factor_report_order": list(CANONICAL_FACTOR_REPORT_ORDER),
                "steps": [step_records[sid] for sid in order],
                "failures": list(failures),
                "artifacts": {},
                "constraints": {
                    "live_network": False,
                    "live_mireye_attempted": False,
                    "f09_authorized": False,
                    "batch_authorized": False,
                    "icp_authorized": False,
                },
            }
        )

    runner_ctx = RunnerContext(
        plan=plan, fixtures=fixtures, artifacts=artifacts, step_records=step_records
    )
    _emit_progress(execution_status="RUNNING")

    for step_id in order:
        step = steps_by_id[step_id]
        record = step_records[step_id]

        # Forced status injection for tests (failure scenarios).
        forced = fixtures.force_step_status.get(step_id)
        if forced:
            record["status"] = forced
            record["started_at"] = _utc_now()
            record["completed_at"] = _utc_now()
            record["failure"] = {
                "error_code": "FORCED_STATUS",
                "message": f"forced:{forced}",
                "retryable": False,
            }
            if forced in {STEP_FAILED, STEP_BLOCKED_DEPENDENCY, STEP_BLOCKED_EXTERNAL}:
                failures.append(
                    {"step_id": step_id, "tool_id": step["tool_id"], "status": forced}
                )
            record["nonvolatile_step_hash"] = nonvolatile_step_hash(record)
            _emit_progress()
            continue

        # Dependency gate
        blocked_by: list[str] = []
        for dep in step.get("dependency_step_ids") or []:
            dep_status = step_records[dep]["status"]
            if dep_status not in TERMINAL_ALL:
                raise ExecutorError(f"dependency_not_terminal:{dep}_for_{step_id}")
            if dependency_blocks_child(
                parent=steps_by_id[dep],
                parent_status=dep_status,
                child=step,
            ):
                blocked_by.append(dep)

        if blocked_by:
            record["status"] = STEP_BLOCKED_DEPENDENCY
            record["started_at"] = _utc_now()
            record["completed_at"] = _utc_now()
            record["failure"] = {
                "error_code": "BLOCKED_DEPENDENCY",
                "message": f"blocked_by:{blocked_by}",
                "retryable": False,
                "blocked_by": blocked_by,
            }
            failures.append(
                {
                    "step_id": step_id,
                    "tool_id": step["tool_id"],
                    "status": STEP_BLOCKED_DEPENDENCY,
                    "blocked_by": blocked_by,
                }
            )
            record["nonvolatile_step_hash"] = nonvolatile_step_hash(record)
            _emit_progress()
            continue

        # If geometry already failed, skip evaluate chain even if assemble soft-deps allow —
        # harden: when geometry failed, block assemble/evaluate/project/explain.
        if _geometry_failed(step_records, steps_by_id) and step["tool_id"] in {
            "profile.assemble",
            "engine.evaluate",
            "output.project_unified",
            "explanation.bind_and_product",
            "factor.f06_parcel_configuration",
            "adapter.usgs_3dep",
            "adapter.rap_cover_production",
            "adapter.nhd_water_candidates",
            "adapter.usda_sda",
            "adapter.noaa_ncei_precip",
            "adapter.tiger_roads",
            "factor.f08_woody_reuse_rap",
        }:
            record["status"] = STEP_BLOCKED_DEPENDENCY
            record["started_at"] = _utc_now()
            record["completed_at"] = _utc_now()
            record["failure"] = {
                "error_code": "GEOMETRY_FAILURE_BLOCKS_PARCEL_WORKFLOW",
                "message": "geometry_failure_blocks_parcel_workflow",
                "retryable": False,
            }
            failures.append(
                {
                    "step_id": step_id,
                    "tool_id": step["tool_id"],
                    "status": STEP_BLOCKED_DEPENDENCY,
                }
            )
            record["nonvolatile_step_hash"] = nonvolatile_step_hash(record)
            _emit_progress()
            continue

        runner_meta = resolve_runner(step["tool_id"])
        record["runner_id"] = runner_meta["runner_id"]
        record["runner_version"] = runner_meta["runner_version"]
        record["status"] = STEP_RUNNING
        record["started_at"] = _utc_now()
        _emit_progress()

        try:
            result = runner_meta["run"](dict(step), runner_ctx)
            status = result.get("status") or STEP_SUCCEEDED
            if status not in TERMINAL_ALL:
                raise RunnerError(f"invalid_runner_status:{status}")
            record["status"] = status
            record["output_refs"] = list(result.get("output_refs") or [])
            record["reused_artifact_refs"] = list(result.get("reused_artifact_refs") or [])
            record["failure"] = result.get("failure")
            if result.get("notes"):
                record["notes"] = dict(result["notes"])
            if status in {STEP_FAILED, STEP_BLOCKED_EXTERNAL, STEP_BLOCKED_DEPENDENCY}:
                failures.append(
                    {
                        "step_id": step_id,
                        "tool_id": step["tool_id"],
                        "status": status,
                        "failure": record["failure"],
                    }
                )
        except RunnerError as exc:
            record["status"] = exc.status if exc.status in TERMINAL_ALL else STEP_FAILED
            record["failure"] = {
                "error_code": type(exc).__name__,
                "message": str(exc),
                "retryable": False,
                "details": exc.details,
            }
            failures.append(
                {
                    "step_id": step_id,
                    "tool_id": step["tool_id"],
                    "status": record["status"],
                    "failure": record["failure"],
                }
            )
        except Exception as exc:  # noqa: BLE001
            record["status"] = STEP_FAILED
            record["failure"] = {
                "error_code": type(exc).__name__,
                "message": str(exc)[:300],
                "retryable": False,
            }
            failures.append(
                {
                    "step_id": step_id,
                    "tool_id": step["tool_id"],
                    "status": STEP_FAILED,
                    "failure": record["failure"],
                }
            )
        finally:
            record["completed_at"] = _utc_now()
            artifacts["_meta"]["rap_fetch_count"] = fixtures.rap_fetch_count
            record["nonvolatile_step_hash"] = nonvolatile_step_hash(record)
            _emit_progress()

    completed_at = _utc_now()

    # Execution status rollup
    statuses = {r["status"] for r in step_records.values()}
    if STEP_FAILED in statuses or STEP_BLOCKED_DEPENDENCY in statuses:
        if _geometry_failed(step_records, steps_by_id):
            execution_status = "FAILED"
        elif any(
            r["status"] == STEP_FAILED and not _is_mireye_tool(r["tool_id"])
            for r in step_records.values()
        ):
            execution_status = "PARTIAL"
        else:
            execution_status = "PARTIAL"
    elif STEP_BLOCKED_EXTERNAL in statuses or STEP_PARTIAL in statuses:
        execution_status = "PARTIAL"
    else:
        execution_status = "SUCCEEDED"

    # If evaluate never produced a match result due to geometry failure, keep refs null.
    land_profile_ref = "land_profile" if "land_profile" in artifacts else None
    match_result_ref = "match_result" if "match_result" in artifacts else None
    unified_output_ref = "unified_output" if "unified_output" in artifacts else None

    # Public artifacts view (exclude huge optional dumps unless present).
    public_artifacts = {
        k: ("<in_memory>" if not k.startswith("_") else v)
        for k, v in artifacts.items()
    }
    # Keep compact metadata and mireye stubs / refs only in summary form.
    public_artifacts["_meta"] = dict(artifacts.get("_meta") or {})
    for key, value in artifacts.items():
        if key.startswith("mireye:"):
            public_artifacts[key] = {
                "context_type": (value or {}).get("context_type"),
                "disposition": (value or {}).get("disposition"),
                "partial_failure_count": len((value or {}).get("partial_failures") or []),
                "limitations": (value or {}).get("limitations"),
            }

    ordered_steps = [step_records[sid] for sid in order]
    # Canonical report order check metadata
    factor_report_order = [
        s["factor_id"]
        for s in sorted(
            [r for r in ordered_steps if r.get("factor_id") and r.get("report_order_index") is not None],
            key=lambda r: r["report_order_index"],
        )
    ]

    execution = {
        "execution_id": execution_id,
        "plan_id": plan.get("plan_id"),
        "plan_sha256": plan.get("plan_sha256"),
        "executor_version": EXECUTOR_VERSION,
        "planner_version": plan.get("planner_version"),
        "runner_bundle_version": RUNNER_VERSION,
        "mode": plan.get("mode"),
        "intended_operation": plan.get("intended_operation"),
        "started_at": started_at,
        "completed_at": completed_at,
        "steps": ordered_steps,
        "step_order_executed": order,
        "canonical_factor_report_order": list(CANONICAL_FACTOR_REPORT_ORDER),
        "factor_steps_by_report_order": factor_report_order,
        "artifacts": public_artifacts,
        "failures": failures,
        "land_profile_ref": land_profile_ref,
        "match_result_ref": match_result_ref,
        "unified_output_ref": unified_output_ref,
        "execution_status": execution_status,
        "presentation": plan.get("presentation"),
        "constraints": {
            "live_network": False,
            "live_mireye_attempted": False,
            "f09_authorized": False,
            "batch_authorized": False,
            "icp_authorized": False,
        },
    }
    execution["deterministic_execution_hash"] = deterministic_execution_hash(execution)
    _assert_no_credentials(execution, label="execution_record")
    # Attach full in-memory artifacts for callers that need them (not written by default).
    execution["_artifact_store"] = artifacts
    return execution


def write_execution_record(path: str, execution: Mapping[str, Any]) -> None:
    """Persist execution record without in-memory artifact store or credentials."""
    payload = {k: v for k, v in execution.items() if k != "_artifact_store"}
    _assert_no_credentials(payload, label=str(path))
    from pathlib import Path

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
