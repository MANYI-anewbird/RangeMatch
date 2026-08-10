"""Fixture-backed tool runners for Planner Executor v0.1.

No live network. Runners load approved fixtures / in-memory bindings only.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping, MutableMapping

from rangematch.engine import evaluate_land_profile
from rangematch.explanation import explain_match_result
from rangematch.f06_derivation import derive_f06_from_geometry, evaluate_f06_signal
from rangematch.tool_registry import (
    CANONICAL_FACTOR_REPORT_ORDER,
    UNAUTHORIZED_TOOL_IDS,
    get_tool,
)
from rangematch.unified_output import (
    assert_explanation_binding,
    hash_match_result,
    project_unified_output,
    sha256_canonical,
    validate_one_parcel_geometry,
)

RUNNER_VERSION = "RANGEMATCH_TOOL_RUNNERS@0.1.0"

# Stable blocked-external classification from transport diagnosis (do not re-probe).
MIREYE_BLOCKED_EXTERNAL_CLASS = "MIREYE_CONTEXT_UNAVAILABLE_FOR_THIS_RUN"


class RunnerError(RuntimeError):
    """Fixture runner failure."""

    def __init__(self, message: str, *, status: str = "FAILED", details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.status = status
        self.details = dict(details or {})


class NetworkForbiddenError(RunnerError):
    def __init__(self, message: str = "network_calls_forbidden_in_fixture_executor"):
        super().__init__(message, status="FAILED")


def _forbid_network() -> None:
    """Guard used by runners; tests may patch urllib to assert no calls."""
    # Intentionally no-op body: presence documents policy. Call sites must not urllib.
    return None


def _load_json(path: str | Path | None) -> Any:
    if path is None:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _factor_from_profile(profile: Mapping[str, Any] | None, factor_id: str) -> dict[str, Any] | None:
    if not profile:
        return None
    factor = (profile.get("factors") or {}).get(factor_id)
    return deepcopy(factor) if isinstance(factor, Mapping) else None


def _f02_cover_artifact_ref(f02: Mapping[str, Any] | None) -> str | None:
    if not f02:
        return None
    for fact in f02.get("land_facts") or []:
        prov = (fact or {}).get("provenance") or {}
        if prov.get("endpoint") == "coverV3" or prov.get("source_reference") == "RAP_coverV3":
            h = prov.get("response_or_artifact_hash")
            if h:
                return str(h)
        if fact.get("variable_id") == "VAR_F02_PERENNIAL_HERB_COVER":
            h = (fact.get("provenance") or {}).get("response_or_artifact_hash")
            if h:
                return str(h)
    h = (f02.get("provenance") or {}).get("response_or_artifact_hash")
    return str(h) if h else None


def to_unified_mireye_item(context: Mapping[str, Any]) -> dict[str, Any]:
    """Project adapter/normalized or blocked stub into unified_output mireye_context item."""
    ctx = dict(context)
    context_type = ctx.get("context_type")
    request = ctx.get("request") or {}
    location = ctx.get("location") or {}
    response_status = ctx.get("response_status") or {}
    resolution = ctx.get("resolution") or {}
    disposition = (
        resolution.get("disposition")
        or ctx.get("disposition")
        or response_status.get("status")
        or "UNKNOWN"
    )
    endpoint_or_preset = (
        ctx.get("endpoint_or_preset")
        or request.get("preset")
        or request.get("endpoint")
    )
    fields = ctx.get("fields") or {}
    # Normalized fields are objects; unified item accepts mapping — keep as-is.
    item = {
        "context_type": context_type,
        "endpoint_or_preset": endpoint_or_preset,
        "requested_point": {
            "lat": location.get("lat"),
            "lng": location.get("lng"),
        }
        if location
        else ctx.get("requested_point"),
        "disposition": disposition,
        "parcel_grade": resolution.get("parcel_grade") or ctx.get("parcel_grade"),
        "fields": fields,
        "confidence": resolution.get("confidence") or ctx.get("confidence"),
        "fetched_at": response_status.get("fetched_at") or ctx.get("fetched_at"),
        "partial_failures": list(ctx.get("partial_failures") or []),
        "source_urls": list(ctx.get("source_urls") or []),
        "dataset_vintage": ctx.get("dataset_vintage"),
    }
    if ctx.get("limitations"):
        item["limitations"] = list(ctx["limitations"])
    if ctx.get("authority"):
        item["authority"] = dict(ctx["authority"])
    if ctx.get("context_id"):
        item["context_id"] = ctx["context_id"]
    return item


def blocked_external_mireye_context(
    *,
    context_type: str,
    endpoint_or_preset: str | None,
    requested_point: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Visible BLOCKED_EXTERNAL stub — never an empty successful context."""
    return {
        "context_type": context_type,
        "context_id": f"blocked_{context_type.lower()}",
        "endpoint_or_preset": endpoint_or_preset,
        "requested_point": dict(requested_point or {}),
        "disposition": "BLOCKED_EXTERNAL",
        "fields": {},
        "fetched_at": None,
        "partial_failures": [
            {
                "field_id": None,
                "source": "MIREYE_TRANSPORT",
                "error_code": MIREYE_BLOCKED_EXTERNAL_CLASS,
                "message": "Mireye context was unavailable for this investigation run",
                "retryable": False,
                "normalized_effect": "UNKNOWN",
            }
        ],
        "limitations": [
            "BLOCKED_EXTERNAL: Mireye context unavailable or live HTTP not authorized for this run",
            "canonical_for_parcel_facts=false",
            "diligence_note: inspect the context failure and retry when available; do not treat absence as empty success",
        ],
        "authority": {
            "canonical_for_parcel_facts": False,
            "permitted_uses": [
                "POINT_QA",
                "FAST_CONTEXT",
                "CANDIDATE_DISCOVERY",
                "DILIGENCE_TRIGGER",
                "JURISDICTION_CONTEXT",
            ],
        },
        "response_status": {"status": "FAILED", "fetched_at": None},
    }


class ExecutionFixtures:
    """In-memory / path fixtures for one executor run."""

    def __init__(
        self,
        *,
        land_profile: Mapping[str, Any] | None = None,
        land_profile_path: str | Path | None = None,
        geometry: Mapping[str, Any] | None = None,
        geometry_path: str | Path | None = None,
        mireye_contexts: Mapping[str, Any] | None = None,
        mireye_blocked_external: bool | Mapping[str, bool] = False,
        computed_factors: Mapping[str, Any] | None = None,
        force_step_status: Mapping[str, str] | None = None,
        force_missing_factors: set[str] | None = None,
    ) -> None:
        self.land_profile = (
            deepcopy(dict(land_profile))
            if land_profile is not None
            else _load_json(land_profile_path)
        )
        self.geometry = (
            deepcopy(dict(geometry))
            if geometry is not None
            else _load_json(geometry_path)
        )
        self.mireye_contexts = dict(mireye_contexts or {})
        self.computed_factors = deepcopy(dict(computed_factors or {}))
        if isinstance(mireye_blocked_external, bool):
            self.mireye_blocked_external = {
                "PROPERTY_DILIGENCE_CONTEXT": mireye_blocked_external,
                "POINT_LAND_CONTEXT": mireye_blocked_external,
                "POINT_HAZARD_CONTEXT": mireye_blocked_external,
            }
        else:
            self.mireye_blocked_external = dict(mireye_blocked_external)
        self.force_step_status = dict(force_step_status or {})
        self.force_missing_factors = set(force_missing_factors or set())
        self.rap_fetch_count = 0

    def mireye_is_blocked(self, context_type: str) -> bool:
        return bool(self.mireye_blocked_external.get(context_type))


RunnerFn = Callable[[dict[str, Any], "RunnerContext"], dict[str, Any]]


class RunnerContext:
    def __init__(
        self,
        *,
        plan: Mapping[str, Any],
        fixtures: ExecutionFixtures,
        artifacts: MutableMapping[str, Any],
        step_records: Mapping[str, Any],
    ) -> None:
        self.plan = plan
        self.fixtures = fixtures
        self.artifacts = artifacts
        self.step_records = step_records


def _runner_result(
    *,
    status: str,
    outputs: Mapping[str, Any] | None = None,
    output_refs: list[str] | None = None,
    reused_artifact_refs: list[str] | None = None,
    failure: Mapping[str, Any] | None = None,
    notes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "outputs": dict(outputs or {}),
        "output_refs": list(output_refs or []),
        "reused_artifact_refs": list(reused_artifact_refs or []),
        "failure": dict(failure) if failure else None,
        "notes": dict(notes or {}),
    }


def run_geometry_validate(step: dict[str, Any], ctx: RunnerContext) -> dict[str, Any]:
    _forbid_network()
    geom = ctx.fixtures.geometry
    if geom is None and ctx.fixtures.land_profile is not None:
        # Land-profile entry: geometry already bound in profile; validate presence.
        if ctx.fixtures.land_profile.get("geometry_hash") or ctx.fixtures.land_profile.get(
            "geometry_id"
        ):
            return _runner_result(
                status="SUCCEEDED",
                outputs={"one_parcel": True, "source": "land_profile"},
                output_refs=["geometry_validation"],
            )
    try:
        validate_one_parcel_geometry(geom)
    except Exception as exc:  # noqa: BLE001
        raise RunnerError(f"one_parcel_validation_failed:{exc}", status="FAILED") from exc
    if geom is None:
        raise RunnerError("geometry_missing", status="FAILED")
    return _runner_result(
        status="SUCCEEDED",
        outputs={"one_parcel": True, "geometry": geom},
        output_refs=["geometry_validation"],
    )


def run_geometry_resolve(step: dict[str, Any], ctx: RunnerContext) -> dict[str, Any]:
    _forbid_network()
    profile = ctx.fixtures.land_profile
    geom = ctx.fixtures.geometry
    if profile is not None:
        binding = {
            "geometry_id": profile.get("geometry_id"),
            "geometry_hash": profile.get("geometry_hash"),
            "geometry_reference": profile.get("geometry_reference"),
            "source_crs": profile.get("source_crs") or profile.get("crs"),
            "source": "land_profile_reuse",
        }
        if not binding["geometry_hash"] and not binding["geometry_id"]:
            raise RunnerError("land_profile_missing_geometry_binding", status="FAILED")
        ctx.artifacts["geometry_binding"] = binding
        if geom is not None:
            ctx.artifacts["geometry"] = deepcopy(geom)
        return _runner_result(
            status="SUCCEEDED",
            outputs={"binding": binding},
            output_refs=["geometry_binding"],
            reused_artifact_refs=["land_profile"],
        )
    if geom is None:
        raise RunnerError("geometry_resolve_missing_input", status="FAILED")
    validate_one_parcel_geometry(geom)
    digest = sha256_canonical(geom)
    binding = {
        "geometry_id": f"geom_{digest[:12]}",
        "geometry_hash": digest,
        "geometry_reference": "fixture_geometry",
        "source_crs": "EPSG:4326",
        "source": "parcel_geometry_fixture",
    }
    ctx.artifacts["geometry_binding"] = binding
    ctx.artifacts["geometry"] = deepcopy(geom)
    return _runner_result(
        status="SUCCEEDED",
        outputs={"binding": binding, "geometry": geom},
        output_refs=["geometry_binding", "geometry"],
    )


def _run_mireye(
    step: dict[str, Any],
    ctx: RunnerContext,
    *,
    context_type: str,
    endpoint_or_preset: str | None,
) -> dict[str, Any]:
    _forbid_network()
    point = None
    binding = ctx.artifacts.get("geometry_binding") or {}
    profile = ctx.fixtures.land_profile or {}
    # Prefer explicit fixture point if present in normalized contexts later.
    if ctx.fixtures.mireye_is_blocked(context_type):
        stub = blocked_external_mireye_context(
            context_type=context_type,
            endpoint_or_preset=endpoint_or_preset,
            requested_point=point or {"geometry_hash": binding.get("geometry_hash")},
        )
        key = f"mireye:{context_type}"
        ctx.artifacts[key] = stub
        return _runner_result(
            status="BLOCKED_EXTERNAL",
            outputs={"context": stub},
            output_refs=[key],
            failure={
                "error_code": MIREYE_BLOCKED_EXTERNAL_CLASS,
                "message": stub["partial_failures"][0]["message"],
                "retryable": False,
            },
            notes={"diligence_note": stub["limitations"][-1]},
        )

    raw = ctx.fixtures.mireye_contexts.get(context_type)
    if raw is None:
        # Soft empty is not allowed as success — treat as FAILED closed.
        raise RunnerError(
            f"mireye_fixture_missing:{context_type}",
            status="FAILED",
            details={"hint": "provide fixture or set mireye_blocked_external"},
        )
    ctx_obj = deepcopy(raw)
    # Ensure authority cannot become parcel-canonical.
    authority = ctx_obj.setdefault("authority", {})
    authority["canonical_for_parcel_facts"] = False
    item = to_unified_mireye_item(ctx_obj)
    key = f"mireye:{context_type}"
    ctx.artifacts[key] = item
    failures = item.get("partial_failures") or []
    status = "PARTIAL" if failures else "SUCCEEDED"
    # Disposition CLARIFY / NO_MATCH → PARTIAL/FAILED visibility
    disp = str(item.get("disposition") or "").upper()
    if disp in {"NO_MATCH", "FAILED", "BLOCKED_EXTERNAL"}:
        status = "FAILED" if disp == "NO_MATCH" else (
            "BLOCKED_EXTERNAL" if disp == "BLOCKED_EXTERNAL" else status
        )
        if disp == "CLARIFY":
            status = "PARTIAL"
    if disp == "CLARIFY":
        status = "PARTIAL"
    return _runner_result(
        status=status,
        outputs={"context": item},
        output_refs=[key],
        reused_artifact_refs=[f"mireye_fixture:{context_type}"],
    )


def run_mireye_property(step: dict[str, Any], ctx: RunnerContext) -> dict[str, Any]:
    return _run_mireye(
        step, ctx, context_type="PROPERTY_DILIGENCE_CONTEXT", endpoint_or_preset="/v1/lookup"
    )


def run_mireye_point_land(step: dict[str, Any], ctx: RunnerContext) -> dict[str, Any]:
    return _run_mireye(
        step, ctx, context_type="POINT_LAND_CONTEXT", endpoint_or_preset="terrain"
    )


def run_mireye_point_hazard(step: dict[str, Any], ctx: RunnerContext) -> dict[str, Any]:
    return _run_mireye(
        step, ctx, context_type="POINT_HAZARD_CONTEXT", endpoint_or_preset="flood_risk"
    )


def _run_factor_reuse(
    step: dict[str, Any],
    ctx: RunnerContext,
    *,
    factor_id: str,
    rap_fetch: bool = False,
) -> dict[str, Any]:
    _forbid_network()
    if factor_id in ctx.fixtures.force_missing_factors:
        raise RunnerError(f"factor_fixture_forced_missing:{factor_id}", status="FAILED")
    profile = ctx.fixtures.land_profile
    factor = deepcopy(ctx.fixtures.computed_factors.get(factor_id))
    computed = factor is not None
    if factor is None:
        factor = _factor_from_profile(profile, factor_id)
    if factor is None:
        raise RunnerError(f"factor_fixture_missing:{factor_id}", status="FAILED")
    if rap_fetch:
        # Fixture-backed F02 still counts as the sole RAP artifact producer for this run.
        ctx.fixtures.rap_fetch_count += 1
        art = _f02_cover_artifact_ref(factor)
        if art:
            ctx.artifacts["f02_coverV3_artifact_hash"] = art
            ctx.artifacts["f02_factor"] = factor
    key = f"factor:{factor_id}"
    ctx.artifacts[key] = factor
    reused = (
        [f"computed_factor:{factor_id}"]
        if computed
        else (["land_profile"] if step.get("action") == "REUSE" else ["land_profile_fixture"])
    )
    if rap_fetch and ctx.artifacts.get("f02_coverV3_artifact_hash"):
        reused.append(f"rap_coverV3:{ctx.artifacts['f02_coverV3_artifact_hash']}")
    return _runner_result(
        status="SUCCEEDED",
        outputs={"factor_id": factor_id, "factor": factor},
        output_refs=[key],
        reused_artifact_refs=reused,
        notes={"fixture_backed": not computed, "computed_factor": computed, "rap_fetch": rap_fetch},
    )


def run_f06(step: dict[str, Any], ctx: RunnerContext) -> dict[str, Any]:
    factor_id = "F06_PARCEL_CONFIGURATION"
    if step.get("action") == "REUSE":
        return _run_factor_reuse(step, ctx, factor_id=factor_id)

    geometry = ctx.artifacts.get("geometry") or ctx.fixtures.geometry
    binding = ctx.artifacts.get("geometry_binding") or {}
    if geometry is None:
        raise RunnerError("f06_compute_geometry_missing", status="FAILED")
    factor = derive_f06_from_geometry(
        geometry,
        geometry_hash=binding.get("geometry_hash"),
        geometry_reference=binding.get("geometry_reference") or "CONFIRMED_PARCEL_GEOMETRY",
        geometry_id=binding.get("geometry_id"),
        source_crs=binding.get("source_crs") or "EPSG:4326",
        derived_at=ctx.plan.get("created_at"),
    )
    signal = evaluate_f06_signal(factor)
    key = f"factor:{factor_id}"
    ctx.artifacts[key] = factor
    context_complete = signal["signal"] == "CONTEXT_DEPENDENT"
    return _runner_result(
        status="SUCCEEDED" if context_complete else "PARTIAL",
        outputs={"factor_id": factor_id, "factor": factor, "signal": signal},
        output_refs=[key],
        notes={
            "fixture_backed": False,
            "deterministic_geometry_compute": True,
            "ranking_effect": "NONE",
        },
    )


def run_f01(step: dict[str, Any], ctx: RunnerContext) -> dict[str, Any]:
    return _run_factor_reuse(step, ctx, factor_id="F01_TOPOGRAPHY")


def run_f02(step: dict[str, Any], ctx: RunnerContext) -> dict[str, Any]:
    return _run_factor_reuse(
        step, ctx, factor_id="F02_HERBACEOUS_RESOURCE", rap_fetch=True
    )


def run_f03(step: dict[str, Any], ctx: RunnerContext) -> dict[str, Any]:
    return _run_factor_reuse(step, ctx, factor_id="F03_LIVESTOCK_WATER")


def run_f04(step: dict[str, Any], ctx: RunnerContext) -> dict[str, Any]:
    return _run_factor_reuse(step, ctx, factor_id="F04_SOIL_WETNESS_ECOLOGICAL_SITE")


def run_f05(step: dict[str, Any], ctx: RunnerContext) -> dict[str, Any]:
    return _run_factor_reuse(step, ctx, factor_id="F05_CLIMATE_DROUGHT_EXPOSURE")


def run_f07(step: dict[str, Any], ctx: RunnerContext) -> dict[str, Any]:
    return _run_factor_reuse(step, ctx, factor_id="F07_ROAD_AND_PHYSICAL_ACCESS")


def run_f08_reuse(step: dict[str, Any], ctx: RunnerContext) -> dict[str, Any]:
    _forbid_network()
    if step.get("action") != "REUSE":
        raise RunnerError("f08_action_must_be_REUSE", status="FAILED")
    # Never increment rap_fetch_count here.
    f02 = ctx.artifacts.get("factor:F02_HERBACEOUS_RESOURCE") or ctx.artifacts.get("f02_factor")
    art = ctx.artifacts.get("f02_coverV3_artifact_hash") or _f02_cover_artifact_ref(f02)
    if not art:
        raise RunnerError(
            "f08_missing_compatible_f02_coverV3_artifact",
            status="FAILED",
            details={"duplicate_rap_fetch": False},
        )
    factor = deepcopy(
        ctx.fixtures.computed_factors.get(
            "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"
        )
    )
    computed = factor is not None
    if factor is None:
        factor = _factor_from_profile(
            ctx.fixtures.land_profile, "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"
        )
    if factor is None:
        raise RunnerError("f08_fixture_missing", status="FAILED")
    key = "factor:F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"
    ctx.artifacts[key] = factor
    return _runner_result(
        status="SUCCEEDED",
        outputs={"factor_id": "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE", "factor": factor},
        output_refs=[key],
        reused_artifact_refs=[f"rap_coverV3:{art}", "factor:F02_HERBACEOUS_RESOURCE"],
        notes={
            "duplicate_rap_fetch": False,
            "reused_f02_artifact": True,
            "computed_factor": computed,
        },
    )


def run_assemble(step: dict[str, Any], ctx: RunnerContext) -> dict[str, Any]:
    _forbid_network()
    base = deepcopy(ctx.fixtures.land_profile) if ctx.fixtures.land_profile else {
        "land_profile_id": "assembled_fixture",
        "factors": {},
    }
    factors: dict[str, Any] = {}
    missing: list[str] = []
    for factor_id in CANONICAL_FACTOR_REPORT_ORDER:
        key = f"factor:{factor_id}"
        if key in ctx.artifacts:
            factors[factor_id] = deepcopy(ctx.artifacts[key])
        elif factor_id not in ctx.fixtures.force_missing_factors:
            # Do not invent — leave absent and record.
            missing.append(factor_id)
        else:
            missing.append(factor_id)
    base["factors"] = factors
    # Preserve geometry binding if present.
    binding = ctx.artifacts.get("geometry_binding") or {}
    for field in ("geometry_id", "geometry_hash", "geometry_reference"):
        if binding.get(field) and not base.get(field):
            base[field] = binding[field]
    ctx.artifacts["land_profile"] = base
    status = "PARTIAL" if missing else "SUCCEEDED"
    return _runner_result(
        status=status,
        outputs={
            "land_profile": base,
            "report_order": list(CANONICAL_FACTOR_REPORT_ORDER),
            "missing_factors": missing,
        },
        output_refs=["land_profile"],
        notes={"invented_land_facts": False, "missing_factors": missing},
    )


def run_evaluate(step: dict[str, Any], ctx: RunnerContext) -> dict[str, Any]:
    _forbid_network()
    profile = ctx.artifacts.get("land_profile")
    if not isinstance(profile, Mapping):
        raise RunnerError("evaluate_missing_land_profile", status="FAILED")
    match_result = evaluate_land_profile(deepcopy(dict(profile)))
    ctx.artifacts["match_result"] = match_result
    return _runner_result(
        status="SUCCEEDED",
        outputs={"match_result": match_result},
        output_refs=["match_result"],
        notes={"engine_authoritative": True},
    )


def run_project(step: dict[str, Any], ctx: RunnerContext) -> dict[str, Any]:
    _forbid_network()
    profile = ctx.artifacts.get("land_profile")
    match_result = ctx.artifacts.get("match_result")
    if not isinstance(profile, Mapping) or not isinstance(match_result, Mapping):
        raise RunnerError("project_missing_profile_or_match_result", status="FAILED")
    mireye_items = []
    for ctype in (
        "PROPERTY_DILIGENCE_CONTEXT",
        "POINT_LAND_CONTEXT",
        "POINT_HAZARD_CONTEXT",
    ):
        key = f"mireye:{ctype}"
        if key in ctx.artifacts:
            mireye_items.append(to_unified_mireye_item(ctx.artifacts[key]))
    envelope = project_unified_output(
        profile,
        match_result,
        mode=ctx.plan.get("mode") or "DISCOVERY",
        intended_operation=ctx.plan.get("intended_operation"),
        planned_actions=ctx.plan.get("planned_actions") or [],
        run_id=ctx.plan.get("plan_id"),
        mireye_context=mireye_items,
        geometry=ctx.artifacts.get("geometry") or ctx.fixtures.geometry,
    )
    # Attach diligence note when any Mireye context is blocked external.
    if any(
        (m.get("disposition") == "BLOCKED_EXTERNAL")
        or any(
            (pf or {}).get("error_code") == MIREYE_BLOCKED_EXTERNAL_CLASS
            for pf in (m.get("partial_failures") or [])
        )
        for m in mireye_items
    ):
        limitations = list(envelope.get("limitations") or [])
        note = (
            "Mireye context BLOCKED_EXTERNAL (documented SafeBrowse middlebox); "
            "canonical F01–F08 fixture paths were not blocked by this failure."
        )
        if note not in limitations:
            limitations.append(note)
        envelope["limitations"] = limitations
    ctx.artifacts["unified_output"] = envelope
    return _runner_result(
        status="SUCCEEDED",
        outputs={"unified_output": envelope},
        output_refs=["unified_output"],
    )


def run_explanation(step: dict[str, Any], ctx: RunnerContext) -> dict[str, Any]:
    _forbid_network()
    profile = ctx.artifacts.get("land_profile")
    match_result = ctx.artifacts.get("match_result")
    envelope = ctx.artifacts.get("unified_output")
    if not isinstance(match_result, Mapping) or not isinstance(envelope, Mapping):
        raise RunnerError("explanation_missing_inputs", status="FAILED")
    explanation = explain_match_result(dict(match_result), dict(profile or {}))
    assert_explanation_binding(explanation, envelope)
    if explanation.get("bound_to_match_result_hash") != envelope.get("match_result_hash"):
        raise RunnerError("explanation_binding_mismatch", status="FAILED")
    if explanation.get("may_alter_decision_labels") is not False:
        raise RunnerError("explanation_must_not_alter_labels", status="FAILED")
    # Attach explanation into envelope copy without changing match hashes.
    env2 = deepcopy(envelope)
    env2["explanation"] = explanation
    ctx.artifacts["unified_output"] = env2
    ctx.artifacts["explanation"] = explanation
    return _runner_result(
        status="SUCCEEDED",
        outputs={"explanation": explanation},
        output_refs=["explanation", "unified_output"],
        notes={"bound_to_match_result_hash": explanation.get("bound_to_match_result_hash")},
    )


def run_dynamic_diligence(step: dict[str, Any], ctx: RunnerContext) -> dict[str, Any]:
    _forbid_network()
    actions = list(ctx.plan.get("planned_actions") or [])
    findings = [
        {
            "finding_id": f"planned_action_{idx}",
            "finding_type": "REGULATORY",
            "trigger": action,
            "jurisdiction": "UNKNOWN",
            "official_sources": [],
            "accessed_at": "fixture",
            "currency_status": "UNKNOWN",
            "applicability_status": "UNKNOWN",
            "limitations": ["non_canonical_diligence_only"],
            "professional_verification_required": True,
            "disposition": "PROFESSIONAL_CONFIRMATION_REQUIRED",
            "related_planned_actions": [action],
        }
        for idx, action in enumerate(actions)
    ]
    ctx.artifacts["dynamic_diligence_findings"] = findings
    return _runner_result(
        status="SUCCEEDED",
        outputs={"findings": findings},
        output_refs=["dynamic_diligence_findings"],
    )


TOOL_RUNNERS: dict[str, dict[str, Any]] = {
    "geometry.validate_one_parcel": {
        "runner_id": "fixture.geometry_validate",
        "runner_version": RUNNER_VERSION,
        "run": run_geometry_validate,
    },
    "geometry.resolve": {
        "runner_id": "fixture.geometry_resolve",
        "runner_version": RUNNER_VERSION,
        "run": run_geometry_resolve,
    },
    "mireye.property_diligence": {
        "runner_id": "fixture.mireye_property",
        "runner_version": RUNNER_VERSION,
        "run": run_mireye_property,
    },
    "mireye.point_land": {
        "runner_id": "fixture.mireye_point_land",
        "runner_version": RUNNER_VERSION,
        "run": run_mireye_point_land,
    },
    "mireye.point_hazard": {
        "runner_id": "fixture.mireye_point_hazard",
        "runner_version": RUNNER_VERSION,
        "run": run_mireye_point_hazard,
    },
    "factor.f06_parcel_configuration": {
        "runner_id": "deterministic.factor_f06_geometry_or_reuse",
        "runner_version": RUNNER_VERSION,
        "run": run_f06,
    },
    "adapter.usgs_3dep": {
        "runner_id": "fixture.factor_f01",
        "runner_version": RUNNER_VERSION,
        "run": run_f01,
    },
    "adapter.rap_cover_production": {
        "runner_id": "fixture.factor_f02_rap",
        "runner_version": RUNNER_VERSION,
        "run": run_f02,
    },
    "adapter.nhd_water_candidates": {
        "runner_id": "fixture.factor_f03",
        "runner_version": RUNNER_VERSION,
        "run": run_f03,
    },
    "adapter.usda_sda": {
        "runner_id": "fixture.factor_f04",
        "runner_version": RUNNER_VERSION,
        "run": run_f04,
    },
    "adapter.noaa_ncei_precip": {
        "runner_id": "fixture.factor_f05",
        "runner_version": RUNNER_VERSION,
        "run": run_f05,
    },
    "adapter.tiger_roads": {
        "runner_id": "fixture.factor_f07",
        "runner_version": RUNNER_VERSION,
        "run": run_f07,
    },
    "factor.f08_woody_reuse_rap": {
        "runner_id": "fixture.factor_f08_reuse",
        "runner_version": RUNNER_VERSION,
        "run": run_f08_reuse,
    },
    "profile.assemble": {
        "runner_id": "fixture.assemble_land_profile",
        "runner_version": RUNNER_VERSION,
        "run": run_assemble,
    },
    "engine.evaluate": {
        "runner_id": "fixture.engine_evaluate",
        "runner_version": RUNNER_VERSION,
        "run": run_evaluate,
    },
    "output.project_unified": {
        "runner_id": "fixture.project_unified",
        "runner_version": RUNNER_VERSION,
        "run": run_project,
    },
    "explanation.bind_and_product": {
        "runner_id": "fixture.explanation_bind",
        "runner_version": RUNNER_VERSION,
        "run": run_explanation,
    },
    "diligence.dynamic_from_planned_actions": {
        "runner_id": "fixture.dynamic_diligence",
        "runner_version": RUNNER_VERSION,
        "run": run_dynamic_diligence,
    },
}


def resolve_runner(tool_id: str) -> dict[str, Any]:
    if tool_id in UNAUTHORIZED_TOOL_IDS or tool_id.startswith("F09"):
        raise PermissionError(f"unauthorized tool: {tool_id}")
    get_tool(tool_id)  # registry gate
    if tool_id not in TOOL_RUNNERS:
        raise KeyError(f"no_fixture_runner_for_tool:{tool_id}")
    return dict(TOOL_RUNNERS[tool_id])
