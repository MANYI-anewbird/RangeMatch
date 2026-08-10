"""Deterministic investigation Planner (dependency DAG, plan-only).

Builds tool plans for one parcel. Does not execute live network calls,
modify Factor science, or override the deterministic engine.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from rangematch.tool_registry import (
    CANONICAL_FACTOR_REPORT_ORDER,
    PEER_FACTORS_AFTER_F06,
    PLANNER_VERSION,
    assert_no_unauthorized_tools,
    get_tool,
)

__all__ = [
    "PLANNER_VERSION",
    "PlannerError",
    "build_investigation_plan",
    "plan_sha256",
    "get_step",
    "factor_steps_in_report_order",
    "assert_plans_equal",
]
from rangematch.unified_output import (
    SUPPORTED_OPERATIONS,
    UnifiedOutputError,
    validate_one_parcel_geometry,
    validate_run_mode,
)

PEER_TOOL_BY_FACTOR = {
    "F01_TOPOGRAPHY": "adapter.usgs_3dep",
    "F02_HERBACEOUS_RESOURCE": "adapter.rap_cover_production",
    "F03_LIVESTOCK_WATER": "adapter.nhd_water_candidates",
    "F04_SOIL_WETNESS_ECOLOGICAL_SITE": "adapter.usda_sda",
    "F05_CLIMATE_DROUGHT_EXPOSURE": "adapter.noaa_ncei_precip",
    "F07_ROAD_AND_PHYSICAL_ACCESS": "adapter.tiger_roads",
}


class PlannerError(UnifiedOutputError):
    """Invalid planner input or unauthorized routing."""


def _canonical_plan_bytes(plan: Mapping[str, Any]) -> bytes:
    # Exclude volatile created_at from determinism hash of the plan body used for equality tests.
    payload = {k: v for k, v in plan.items() if k != "created_at"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def plan_sha256(plan: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_plan_bytes(plan)).hexdigest()


def _count_inputs(
    *,
    address: str | None,
    parcel_geometry: Mapping[str, Any] | None,
    land_profile: Mapping[str, Any] | None,
) -> int:
    return sum(
        [
            bool(address and str(address).strip()),
            parcel_geometry is not None,
            land_profile is not None,
        ]
    )


def _step(
    step_id: str,
    tool_id: str,
    *,
    purpose: str | None = None,
    input_refs: list[str] | None = None,
    dependency_step_ids: list[str] | None = None,
    action: str,
    expected_output_type: str | None = None,
    failure_behavior: str | None = None,
    prohibited_promotions: list[str] | None = None,
    factor_id: str | None = None,
    parallel_group: str | None = None,
    report_order_index: int | None = None,
    notes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = get_tool(tool_id)
    return {
        "step_id": step_id,
        "tool_id": tool_id,
        "purpose": purpose or meta["purpose"],
        "input_refs": list(input_refs or []),
        "dependency_step_ids": list(dependency_step_ids or []),
        "action": action,
        "expected_output_type": expected_output_type or meta["expected_output_type"],
        "canonical_authority": meta["canonical_authority"],
        "failure_behavior": failure_behavior or meta["failure_behavior"],
        "prohibited_promotions": list(
            prohibited_promotions
            if prohibited_promotions is not None
            else meta["prohibited_promotions"]
        ),
        "factor_id": factor_id or meta.get("factor_id"),
        "parallel_group": parallel_group,
        "report_order_index": report_order_index,
        "endpoint": meta.get("endpoint"),
        "notes": notes or {},
    }


def _profile_has_factor_evidence(land_profile: Mapping[str, Any], factor_id: str) -> bool:
    factor = (land_profile.get("factors") or {}).get(factor_id) or {}
    if not factor:
        return False
    if factor.get("geometry_replacement_status") == "EVIDENCE_INVALIDATED":
        return False
    state = factor.get("input_quality_state")
    if state in {"MISSING", "EVIDENCE_INVALIDATED"}:
        return False
    if state not in {None, ""}:
        return True
    # Some frozen Factors (e.g. F02) omit top-level input_quality_state but carry Land Facts.
    if factor.get("land_facts"):
        return True
    if factor.get("summary") or factor.get("result_reference"):
        return True
    if factor.get("shrub_cover_fraction") is not None or factor.get("area_m2") is not None:
        return True
    return False


def _profile_has_f02_cover_artifact(land_profile: Mapping[str, Any]) -> bool:
    f02 = (land_profile.get("factors") or {}).get("F02_HERBACEOUS_RESOURCE") or {}
    for fact in f02.get("land_facts") or []:
        prov = (fact or {}).get("provenance") or {}
        if prov.get("endpoint") == "coverV3" or prov.get("source_reference") == "RAP_coverV3":
            if prov.get("response_or_artifact_hash"):
                return True
        if fact.get("variable_id") == "VAR_F02_PERENNIAL_HERB_COVER":
            if (fact.get("provenance") or {}).get("response_or_artifact_hash"):
                return True
    return bool((f02.get("provenance") or {}).get("response_or_artifact_hash"))


def build_investigation_plan(
    *,
    mode: str,
    intended_operation: str | None = None,
    address: str | None = None,
    parcel_geometry: Mapping[str, Any] | None = None,
    land_profile: Mapping[str, Any] | None = None,
    planned_actions: Sequence[str] | None = None,
    plan_id: str | None = None,
    include_mireye_context: bool = True,
    hazard_partial_failures: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic investigation DAG. Plan-only; no network I/O."""
    try:
        validate_run_mode(mode, intended_operation)
    except UnifiedOutputError as exc:
        raise PlannerError(str(exc)) from exc

    n_inputs = _count_inputs(
        address=address, parcel_geometry=parcel_geometry, land_profile=land_profile
    )
    if n_inputs != 1:
        raise PlannerError(
            "exactly one of address, parcel_geometry, or land_profile is required"
        )

    if parcel_geometry is not None:
        try:
            validate_one_parcel_geometry(parcel_geometry)
        except UnifiedOutputError as exc:
            raise PlannerError(str(exc)) from exc

    if land_profile is not None:
        # Existing profiles are single-parcel bindings; multi-geometry lists rejected.
        if isinstance(land_profile.get("geometries"), list) and len(land_profile["geometries"]) > 1:
            raise PlannerError("one_parcel_only: land_profile contains multiple geometries")

    planned_actions = list(planned_actions or [])
    steps: list[dict[str, Any]] = []
    entry = (
        "address"
        if address
        else "parcel_geometry"
        if parcel_geometry is not None
        else "land_profile"
    )
    prefer_reuse = entry == "land_profile"

    # --- Stage 1: geometry resolve/validate ---
    steps.append(
        _step(
            "S01_VALIDATE_ONE_PARCEL",
            "geometry.validate_one_parcel",
            action="COMPUTE",
            input_refs=[entry],
            dependency_step_ids=[],
            notes={"entry": entry},
        )
    )
    geo_action = "REUSE" if prefer_reuse else "FETCH" if address else "COMPUTE"
    steps.append(
        _step(
            "S02_RESOLVE_GEOMETRY",
            "geometry.resolve",
            action=geo_action,
            input_refs=[entry, "S01_VALIDATE_ONE_PARCEL"],
            dependency_step_ids=["S01_VALIDATE_ONE_PARCEL"],
            notes={
                "binds": [
                    "geometry_id",
                    "geometry_hash",
                    "geometry_reference",
                    "source_crs",
                ]
            },
        )
    )
    geo_step = "S02_RESOLVE_GEOMETRY"

    # --- Stage 2: Mireye context after location available ---
    mireye_deps = [geo_step]
    mireye_steps: list[str] = []
    if include_mireye_context:
        # Address entry may need property diligence to obtain parcel candidate context.
        steps.append(
            _step(
                "S03_MIREYE_PROPERTY",
                "mireye.property_diligence",
                action="REUSE" if prefer_reuse else "FETCH",
                input_refs=[geo_step, entry],
                dependency_step_ids=mireye_deps,
                parallel_group="mireye_context",
                notes={
                    "context_type": "PROPERTY_DILIGENCE_CONTEXT",
                    "non_canonical": True,
                },
            )
        )
        steps.append(
            _step(
                "S04_MIREYE_POINT_LAND",
                "mireye.point_land",
                action="REUSE" if prefer_reuse else "FETCH",
                input_refs=[geo_step],
                dependency_step_ids=mireye_deps,
                parallel_group="mireye_context",
                notes={
                    "context_type": "POINT_LAND_CONTEXT",
                    "non_canonical": True,
                },
            )
        )
        hazard_notes: dict[str, Any] = {
            "context_type": "POINT_HAZARD_CONTEXT",
            "non_canonical": True,
            "preserve_partial_failures": True,
        }
        if hazard_partial_failures is not None:
            hazard_notes["partial_failures"] = list(hazard_partial_failures)
        else:
            hazard_notes["partial_failures"] = []
        steps.append(
            _step(
                "S05_MIREYE_POINT_HAZARD",
                "mireye.point_hazard",
                action="REUSE" if prefer_reuse else "FETCH",
                input_refs=[geo_step],
                dependency_step_ids=mireye_deps,
                parallel_group="mireye_context",
                notes=hazard_notes,
            )
        )
        mireye_steps = [
            "S03_MIREYE_PROPERTY",
            "S04_MIREYE_POINT_LAND",
            "S05_MIREYE_POINT_HAZARD",
        ]

    # --- Stage 3: F06 after geometry ---
    f06_action = (
        "REUSE"
        if prefer_reuse
        and land_profile is not None
        and _profile_has_factor_evidence(land_profile, "F06_PARCEL_CONFIGURATION")
        else "COMPUTE"
    )
    steps.append(
        _step(
            "S06_F06_PARCEL_CONFIGURATION",
            "factor.f06_parcel_configuration",
            action=f06_action,
            input_refs=[geo_step],
            dependency_step_ids=[geo_step],
            factor_id="F06_PARCEL_CONFIGURATION",
            report_order_index=CANONICAL_FACTOR_REPORT_ORDER.index(
                "F06_PARCEL_CONFIGURATION"
            ),
            notes={"gate": "geometry_validity_hash_area_crs"},
        )
    )
    f06_step = "S06_F06_PARCEL_CONFIGURATION"

    # --- Stage 4: peer factors after F06 ---
    peer_step_ids: dict[str, str] = {}
    for factor_id in PEER_FACTORS_AFTER_F06:
        tool_id = PEER_TOOL_BY_FACTOR[factor_id]
        step_id = f"S07_PEER_{factor_id}"
        action = (
            "REUSE"
            if prefer_reuse
            and land_profile is not None
            and _profile_has_factor_evidence(land_profile, factor_id)
            else "FETCH"
        )
        # F01 may be COMPUTE from local DEM artifact patterns; keep FETCH as adapter plan.
        if factor_id == "F01_TOPOGRAPHY" and action != "REUSE":
            action = "FETCH"
        steps.append(
            _step(
                step_id,
                tool_id,
                action=action,
                input_refs=[f06_step, geo_step],
                dependency_step_ids=[f06_step],
                factor_id=factor_id,
                parallel_group="peer_factors_after_f06",
                report_order_index=CANONICAL_FACTOR_REPORT_ORDER.index(factor_id),
            )
        )
        peer_step_ids[factor_id] = step_id

    f02_step = peer_step_ids["F02_HERBACEOUS_RESOURCE"]

    # --- Stage 5: F08 depends on F02-compatible artifact; REUSE only ---
    f08_action = "REUSE"
    f08_notes = {
        "requires_compatible_f02_coverV3": True,
        "compatibility_fields": [
            "geometry_hash",
            "source_year",
            "mask",
            "applicability",
            "coverage",
            "artifact_hash",
        ],
        "duplicate_rap_fetch": False,
        "action_forced": "REUSE",
    }
    if prefer_reuse and land_profile is not None:
        f08_notes["existing_profile_f02_artifact"] = _profile_has_f02_cover_artifact(
            land_profile
        )
    steps.append(
        _step(
            "S08_F08_WOODY_REUSE",
            "factor.f08_woody_reuse_rap",
            action=f08_action,
            input_refs=[f02_step, f06_step, geo_step],
            dependency_step_ids=[f02_step],
            factor_id="F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE",
            report_order_index=CANONICAL_FACTOR_REPORT_ORDER.index(
                "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"
            ),
            notes=f08_notes,
            prohibited_promotions=list(
                get_tool("factor.f08_woody_reuse_rap")["prohibited_promotions"]
            )
            + ["duplicate RAP coverV3 FETCH"],
        )
    )
    f08_step = "S08_F08_WOODY_REUSE"

    # Factor completion dependencies for assembly: all factor steps
    factor_completion_steps = [f06_step, *peer_step_ids.values(), f08_step]

    # --- Stage 6: assemble in report order ---
    steps.append(
        _step(
            "S09_ASSEMBLE_LAND_PROFILE",
            "profile.assemble",
            action="COMPUTE",
            input_refs=factor_completion_steps + mireye_steps,
            dependency_step_ids=factor_completion_steps,
            notes={
                "report_order": list(CANONICAL_FACTOR_REPORT_ORDER),
                "execution_order_independent": True,
            },
        )
    )
    assemble_step = "S09_ASSEMBLE_LAND_PROFILE"

    # --- Stage 7: evaluate ---
    steps.append(
        _step(
            "S10_EVALUATE_ENGINE",
            "engine.evaluate",
            action="EVALUATE",
            input_refs=[assemble_step],
            dependency_step_ids=[assemble_step],
            notes={
                "operations": list(SUPPORTED_OPERATIONS),
                "mode": mode,
                "intended_operation": intended_operation,
                "presentation_only_priority": mode == "GOAL_DIRECTED",
                "planner_cannot_modify_decisions": True,
            },
        )
    )
    evaluate_step = "S10_EVALUATE_ENGINE"

    # --- Stage 8: project unified output ---
    steps.append(
        _step(
            "S11_PROJECT_UNIFIED_OUTPUT",
            "output.project_unified",
            action="PROJECT",
            input_refs=[assemble_step, evaluate_step],
            dependency_step_ids=[evaluate_step],
            notes={
                "contract_version": "RANGEMATCH_UNIFIED_OUTPUT@0.1.0",
                "planned_actions_passthrough": planned_actions,
                "planned_actions_mutate_factors": False,
            },
        )
    )
    project_step = "S11_PROJECT_UNIFIED_OUTPUT"

    # Optional dynamic diligence from planned_actions.
    # Side branch only: must not alter Factor DAG or terminal assemble→evaluate→project→explain deps.
    if planned_actions:
        steps.append(
            _step(
                "S12_DYNAMIC_DILIGENCE",
                "diligence.dynamic_from_planned_actions",
                action="COMPUTE",
                input_refs=[project_step],
                dependency_step_ids=[project_step],
                notes={
                    "planned_actions": planned_actions,
                    "does_not_modify_factor_dag": True,
                    "non_canonical": True,
                    "side_branch": True,
                },
            )
        )

    # --- Stage 9: explain + product ---
    steps.append(
        _step(
            "S13_EXPLAIN_AND_PRODUCT",
            "explanation.bind_and_product",
            action="EXPLAIN",
            input_refs=[project_step, evaluate_step],
            dependency_step_ids=[project_step],
            notes={
                "bind_to": "match_result_hash",
                "buyer_sections": [
                    "Property",
                    "Land & Resources",
                    "Resilience & Hazards",
                    "Operation Comparison",
                    "Diligence Plan",
                ],
                "discovery_qualification": mode == "DISCOVERY",
            },
        )
    )

    tool_ids = [s["tool_id"] for s in steps]
    assert_no_unauthorized_tools(tool_ids)

    presentation = {
        "mode": mode,
        "intended_operation": intended_operation,
        "operation_presentation_order": (
            [intended_operation]
            + [op for op in SUPPORTED_OPERATIONS if op != intended_operation]
            if mode == "GOAL_DIRECTED" and intended_operation
            else list(SUPPORTED_OPERATIONS)
        ),
        "scientific_priority_change": False,
        "rule_or_threshold_change": False,
        "discovery_limited_to_supported_profiles": mode == "DISCOVERY",
    }

    plan: dict[str, Any] = {
        "planner_version": PLANNER_VERSION,
        "plan_id": plan_id
        or f"plan_{mode}_{intended_operation or 'DISCOVERY'}_{entry}",
        "mode": mode,
        "intended_operation": intended_operation,
        "planned_actions": planned_actions,
        "entry": entry,
        "live_network_authorized": False,
        "constraints": {
            "parcels_per_run": 1,
            "f09_authorized": False,
            "batch_workflow_authorized": False,
            "icp_authorized": False,
            "duplicate_rap_fetch_for_f08": False,
            "planner_modifies_engine_decisions": False,
            "mireye_canonical_for_factors": False,
            "planned_actions_mutate_factor_dag": False,
        },
        "canonical_factor_report_order": list(CANONICAL_FACTOR_REPORT_ORDER),
        "execution_model": "DEPENDENCY_DAG",
        "peer_factors_after_f06": list(PEER_FACTORS_AFTER_F06),
        "presentation": presentation,
        "stages": [
            "resolve_geometry",
            "mireye_context",
            "f06_geometry_compute",
            "peer_factor_adapters",
            "f08_artifact_reuse",
            "assemble_land_profile",
            "evaluate_engine",
            "project_unified_output",
            "explain_and_product",
        ],
        "steps": steps,
        "terminal_sequence": [
            "S09_ASSEMBLE_LAND_PROFILE",
            "S10_EVALUATE_ENGINE",
            "S11_PROJECT_UNIFIED_OUTPUT",
            "S13_EXPLAIN_AND_PRODUCT",
        ],
        "dag": _build_dag_index(steps),
    }
    plan["plan_sha256"] = plan_sha256(plan)
    return plan


def _build_dag_index(steps: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_id = {s["step_id"]: dict(s) for s in steps}
    dependents: dict[str, list[str]] = {sid: [] for sid in by_id}
    for step in steps:
        for dep in step["dependency_step_ids"]:
            dependents.setdefault(dep, []).append(step["step_id"])
    return {
        "nodes": list(by_id.keys()),
        "edges": [
            {"from": dep, "to": step["step_id"]}
            for step in steps
            for dep in step["dependency_step_ids"]
        ],
        "dependents": dependents,
        "parallel_groups": {
            "mireye_context": [
                s["step_id"] for s in steps if s.get("parallel_group") == "mireye_context"
            ],
            "peer_factors_after_f06": [
                s["step_id"]
                for s in steps
                if s.get("parallel_group") == "peer_factors_after_f06"
            ],
        },
    }


def get_step(plan: Mapping[str, Any], step_id: str) -> dict[str, Any]:
    for step in plan.get("steps") or []:
        if step.get("step_id") == step_id:
            return dict(step)
    raise KeyError(step_id)


def factor_steps_in_report_order(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    factor_steps = [
        s for s in plan.get("steps") or [] if s.get("factor_id") in CANONICAL_FACTOR_REPORT_ORDER
    ]
    return sorted(
        factor_steps,
        key=lambda s: CANONICAL_FACTOR_REPORT_ORDER.index(s["factor_id"]),
    )


def assert_plans_equal(a: Mapping[str, Any], b: Mapping[str, Any]) -> None:
    if plan_sha256(a) != plan_sha256(b):
        raise AssertionError("plans are not deterministically identical")
