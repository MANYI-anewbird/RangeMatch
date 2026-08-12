"""Request-time Advisor Agent: place → agenda → Packet → Brief. No LLM."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from rangematch.advisor_brief import generate_deterministic_brief
from rangematch.advisor_contract import (
    REPO_ROOT,
    land_fact_index,
    packet_hash,
    validate_packet,
    validate_three_page,
)
from rangematch.advisor_packet import (
    F03_INVENTORY_REF,
    F03_REMOTE_PILOT_REF,
    is_cper_engineering_fixture,
    project_cper_buyer_evidence_packet,
)
from rangematch.parcel_resolution import (
    FIXTURE_ROOT,
    compute_geometry_hash,
    find_fixture_scenario_id,
)
from rangematch.planner import build_investigation_plan
from rangematch.planner_executor import execute_plan
from rangematch.tool_runners import ExecutionFixtures
from rangematch.unified_output import validate_one_parcel_geometry

PROFILE_REF = "test-data/land-profiles/land_profile_cper_001.json"
CLAIMS_REF = "test-data/advisor/cper_listing_claims_fixture.json"
UNIFIED_OUTPUT_REF = "test-data/land-profiles/unified_output_cper_001.json"
CPER_DEMO_ADDRESS = "Central Plains Experimental Range Demo, Nunn, CO"
CPER_SCENARIO_ID = "cper_complete_demo"
MIREYE_CONTEXT_TYPES: tuple[str, ...] = (
    "PROPERTY_DILIGENCE_CONTEXT",
    "POINT_LAND_CONTEXT",
    "POINT_HAZARD_CONTEXT",
)
MIREYE_STEP_BY_CONTEXT = {
    "PROPERTY_DILIGENCE_CONTEXT": "S03_MIREYE_PROPERTY",
    "POINT_LAND_CONTEXT": "S04_MIREYE_POINT_LAND",
    "POINT_HAZARD_CONTEXT": "S05_MIREYE_POINT_HAZARD",
}

AGENT_STEPS: tuple[tuple[str, str], ...] = (
    ("ACCEPT_PLACE", "Accept place"),
    ("RESOLVE_PARCEL", "Resolve parcel"),
    ("CALL_MIREYE", "Call Mireye"),
    ("BUILD_AGENDA", "Build agenda"),
    ("RUN_AGENDA", "Run agenda"),
    ("COMPARE_CLAIMS", "Compare claims"),
    ("ORDER_ACTIONS", "Order actions"),
    ("VALIDATE_BRIEF", "Validate brief"),
)

_RUNS: dict[str, dict[str, Any]] = {}
_PACE_S = 0.22
_MIREYE_REQUEST_FN: Any = None
_MIREYE_LOOKUP_FN: Any = None


class AdvisorAgentStepError(RuntimeError):
    def __init__(self, step_id: str, message: str) -> None:
        super().__init__(message)
        self.step_id = step_id
        self.message = message


def _unit_test_mireye_request(*, endpoint: str, body: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    from rangematch.mireye_adapter import MireyeAdapterError

    raise MireyeAdapterError("TOKEN_MISSING:advisor_unit_test_hook")


def _unit_test_lookup(address: str, **kwargs: Any) -> Any:
    from rangematch.mireye_lookup_transport import LookupTransportResult

    return LookupTransportResult(
        ok=False,
        error_class="UNIT_TEST_HOOK",
        http_status=None,
        sanitized_response=None,
        response_hash=None,
        request_hash=None,
        attempts=0,
        retries=0,
        sleep_seconds=[],
        retrieved_at=_utc_now(),
        endpoint="/v1/lookup",
        kind="address",
        input_length=len(address or ""),
        input_fingerprint="advisor_unit_test_hook",
        limitations=["unit test hook; no HTTP"],
    )


def reset_advisor_runs_for_tests() -> None:
    _RUNS.clear()
    set_advisor_pace_for_tests(0.0)
    set_advisor_mireye_hooks_for_tests(
        request_fn=_unit_test_mireye_request,
        lookup_fn=_unit_test_lookup,
    )


def set_advisor_mireye_hooks_for_tests(
    *,
    request_fn: Any | None = None,
    lookup_fn: Any | None = None,
) -> None:
    """Tests only. Production uvicorn never calls this; live HTTP is the default."""
    global _MIREYE_REQUEST_FN, _MIREYE_LOOKUP_FN
    _MIREYE_REQUEST_FN = request_fn
    _MIREYE_LOOKUP_FN = lookup_fn


def set_advisor_pace_for_tests(seconds: float) -> None:
    global _PACE_S
    _PACE_S = max(0.0, float(seconds))


def get_advisor_run(run_id: str) -> dict[str, Any] | None:
    record = _RUNS.get(run_id)
    return None if record is None else _public_view(record)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(relative: str) -> Any:
    path = REPO_ROOT / relative
    if not path.is_file():
        raise FileNotFoundError(relative)
    return json.loads(path.read_text(encoding="utf-8"))


def _pace() -> None:
    if _PACE_S:
        time.sleep(_PACE_S)


def _empty_steps() -> list[dict[str, Any]]:
    return [
        {
            "step_id": step_id,
            "label": label,
            "status": "PENDING",
            "started_at": None,
            "completed_at": None,
        }
        for step_id, label in AGENT_STEPS
    ]


def _public_view(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": record["status"],
        "run_id": record["run_id"],
        "generated_at": record["generated_at"],
        "address": record.get("address"),
        "fixture_id": record.get("fixture_id"),
        "packet_hash": record.get("packet_hash"),
        "llm_used": False,
        "generator": "DETERMINISTIC_TEMPLATE",
        "failed_step": record.get("failed_step"),
        "error": record.get("error"),
        "steps": list(record.get("steps") or []),
        "agenda": list(record.get("agenda") or []),
        "packet": record.get("packet"),
        "brief": record.get("brief"),
        "parcel_geometry": record.get("parcel_geometry"),
        "limitations": list(record.get("limitations") or []),
        "mireye_live": record.get("mireye_live"),
        "buyer_explanation": record.get("buyer_explanation"),
    }


def _mark(steps: list[dict[str, Any]], step_id: str, status: str, *, now: str) -> None:
    for row in steps:
        if row["step_id"] != step_id:
            continue
        if status == "RUNNING" and not row.get("started_at"):
            row["started_at"] = now
        if status != "RUNNING":
            row["completed_at"] = now
        row["status"] = status
        return


def _run_step(
    record: dict[str, Any],
    step_id: str,
    work: Any,
    *,
    fail_step: str | None,
) -> Any:
    steps = record["steps"]
    started = _utc_now()
    _mark(steps, step_id, "RUNNING", now=started)
    record["status"] = "RUNNING"
    aliases = {fail_step} if fail_step else set()
    if fail_step == "GATHER_EVIDENCE":
        aliases.add("RUN_AGENDA")
    if fail_step in aliases and step_id in aliases:
        raise AdvisorAgentStepError(step_id, f"injected failure at {step_id}")
    try:
        result = work()
    except AdvisorAgentStepError:
        raise
    except Exception as exc:  # noqa: BLE001 — step boundary is the product error
        raise AdvisorAgentStepError(step_id, f"{type(exc).__name__}: {exc}") from exc
    _mark(steps, step_id, "SUCCEEDED", now=_utc_now())
    _pace()
    return result


def _resolve_requested_address(address: str | None, fixture_id: str | None) -> str:
    text = (address or "").strip()
    if text:
        return text
    if (fixture_id or "").strip() == "CPER":
        return CPER_DEMO_ADDRESS
    return ""


def _accept_place(address: str) -> str:
    if not address:
        raise AdvisorAgentStepError(
            "ACCEPT_PLACE",
            "Enter a place — address or the CPER demo location — before running the Agent.",
        )
    return address


def _resolve_parcel(address: str) -> dict[str, Any]:
    scenario_id = find_fixture_scenario_id(address)
    if not scenario_id:
        raise AdvisorAgentStepError(
            "RESOLVE_PARCEL",
            f"No parcel candidates matched “{address}”. Try the CPER demo address, "
            "or another listed demo place.",
        )
    path = FIXTURE_ROOT / f"{scenario_id}.json"
    scenario = json.loads(path.read_text(encoding="utf-8"))
    candidates = list(scenario.get("candidates") or [])
    if not candidates:
        raise AdvisorAgentStepError("RESOLVE_PARCEL", "Place matched, but no parcel candidate exists.")
    geometry = candidates[0].get("parcel_geometry")
    validate_one_parcel_geometry(geometry)
    return {
        "scenario_id": scenario_id,
        "label": candidates[0].get("label") or scenario_id,
        "geometry": geometry,
        "listing_claims": list(_load_json(CLAIMS_REF).get("listing_claims") or []),
    }


def _public_lookup_view(result: Any) -> dict[str, Any]:
    payload = result.to_public_dict() if hasattr(result, "to_public_dict") else dict(result)
    return {
        "ok": bool(payload.get("ok")),
        "error_class": payload.get("error_class"),
        "http_status": payload.get("http_status"),
        "endpoint": payload.get("endpoint") or "/v1/lookup",
        "kind": payload.get("kind") or "address",
        "attempts": payload.get("attempts"),
        "disposition": payload.get("disposition"),
        "limitations": list(payload.get("limitations") or []),
    }


def _context_row(status: str, error_class: str | None = None) -> dict[str, Any]:
    return {"status": status, "error_class": error_class}


def _mireye_limitation(live: dict[str, Any]) -> str:
    lookup = live.get("lookup") or {}
    lookup_bit = "ok" if lookup.get("ok") else (lookup.get("error_class") or "UNKNOWN")
    parts = []
    for context_type in MIREYE_CONTEXT_TYPES:
        row = (live.get("contexts") or {}).get(context_type) or {}
        parts.append(
            f"{context_type.split('_')[0]}={row.get('error_class') or row.get('status')}"
        )
    hook = "unit test hook; no HTTP" if live.get("mode") == "UNIT_TEST_HOOK" else "allow_network=true"
    return (
        f"Mireye live HTTP ({hook}). Failed contexts were not replaced with fixtures. "
        f"lookup={lookup_bit}; {'; '.join(parts)}. "
        "BLOCKED_EXTERNAL is the real transport/token/API result when present."
    )


def _paint_mireye_preview(record: dict[str, Any], live: dict[str, Any]) -> None:
    rows = []
    for context_type in MIREYE_CONTEXT_TYPES:
        sid = MIREYE_STEP_BY_CONTEXT[context_type]
        row = (live.get("contexts") or {}).get(context_type) or {}
        rows.append(
            {
                "step_id": sid,
                "label": sid.split("_", 1)[-1].replace("_", " ").title(),
                "tool_id": {
                    "PROPERTY_DILIGENCE_CONTEXT": "mireye.property_diligence",
                    "POINT_LAND_CONTEXT": "mireye.point_land",
                    "POINT_HAZARD_CONTEXT": "mireye.point_hazard",
                }[context_type],
                "status": row.get("status") or "PENDING",
            }
        )
    record["agenda"] = rows


def _call_live_mireye(record: dict[str, Any], address: str, geometry: dict[str, Any]) -> dict[str, Any]:
    from shapely.geometry import shape

    from rangematch.mireye_adapter import assert_no_credentials, collect_live_mireye_contexts
    from rangematch.mireye_lookup_transport import lookup_parcel_via_mireye

    feature = geometry["features"][0]
    centroid = shape(feature["geometry"]).centroid
    requested_point = {"lat": float(centroid.y), "lng": float(centroid.x)}
    geometry_hash = compute_geometry_hash(geometry)
    mode = "UNIT_TEST_HOOK" if _MIREYE_LOOKUP_FN is not None else "LIVE"
    lookup_fn = _MIREYE_LOOKUP_FN or lookup_parcel_via_mireye
    lookup_result = lookup_fn(address, kind="address", allow_network=True)
    lookup_view = _public_lookup_view(lookup_result)

    live: dict[str, Any] = {
        "mode": mode,
        "allow_network": True,
        "lookup": lookup_view,
        "requested_point": requested_point,
        "contexts": {
            context_type: _context_row("RUNNING") for context_type in MIREYE_CONTEXT_TYPES
        },
    }
    record["mireye_live"] = live
    _paint_mireye_preview(record, live)
    _pace()

    try:
        summary = collect_live_mireye_contexts(
            lat=requested_point["lat"],
            lng=requested_point["lng"],
            parcel_geometry_hash=geometry_hash,
            request_fn=_MIREYE_REQUEST_FN,
        )
    except Exception as exc:  # noqa: BLE001 — live gate records the real failure
        summary = {
            "contexts": {},
            "errors": {
                context_type: {
                    "error_class": type(exc).__name__,
                    "message": str(exc),
                }
                for context_type in MIREYE_CONTEXT_TYPES
            },
        }

    contexts_out: dict[str, Any] = {}
    for context_type in MIREYE_CONTEXT_TYPES:
        error = (summary.get("errors") or {}).get(context_type)
        if error:
            error_class = str(error.get("error_class") or error.get("message") or "UNKNOWN")
            status = (
                "BLOCKED_EXTERNAL"
                if "BLOCKED_EXTERNAL" in error_class or "TOKEN_MISSING" in error_class
                else "FAILED"
            )
            if "TOKEN_MISSING" in error_class:
                status = "BLOCKED_EXTERNAL"
            contexts_out[context_type] = _context_row(status, error_class)
        elif context_type in (summary.get("contexts") or {}):
            contexts_out[context_type] = _context_row("SUCCEEDED")
        else:
            contexts_out[context_type] = _context_row("BLOCKED_EXTERNAL", "CONTEXT_MISSING")

    live["contexts"] = contexts_out
    live["canonical_for_parcel_facts"] = False
    record["mireye_live"] = live
    record["_mireye_context_payloads"] = dict(summary.get("contexts") or {})
    record["limitations"] = [note for note in (record.get("limitations") or []) if note]
    record["limitations"].append(_mireye_limitation(live))
    _paint_mireye_preview(record, live)
    assert_no_credentials(live, label="advisor_mireye_live")
    return live


def _agenda_from_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for step in plan.get("steps") or []:
        sid = str(step.get("step_id") or "")
        tool_id = str(step.get("tool_id") or "")
        label = sid.split("_", 1)[-1].replace("_", " ").title() if sid else tool_id
        rows.append(
            {
                "step_id": sid,
                "label": label,
                "tool_id": tool_id,
                "status": "PENDING",
            }
        )
    return rows


def _build_agenda(record: dict[str, Any], resolved: dict[str, Any]) -> dict[str, Any]:
    if resolved["scenario_id"] != CPER_SCENARIO_ID:
        raise AdvisorAgentStepError(
            "BUILD_AGENDA",
            f"Resolved “{resolved['label']}”. This Challenge Demo only builds the full "
            "evidence agenda for the CPER engineering tract, not a nationwide listing.",
        )
    profile = _load_json(PROFILE_REF)
    plan = build_investigation_plan(
        mode="DISCOVERY",
        intended_operation=None,
        land_profile=profile,
        planned_actions=[],
        include_mireye_context=True,
        plan_id=f"advisor_cper_{uuid4().hex[:8]}",
    )
    agenda = _agenda_from_plan(plan)
    live = record.get("mireye_live") or {}
    live_contexts = live.get("contexts") or {}
    for row in agenda:
        for context_type, step_id in MIREYE_STEP_BY_CONTEXT.items():
            if row["step_id"] == step_id and context_type in live_contexts:
                row["status"] = live_contexts[context_type].get("status") or row["status"]
    return {"plan": plan, "profile": profile, "agenda": agenda}


def _run_agenda(
    record: dict[str, Any],
    built: dict[str, Any],
    geometry: dict[str, Any],
    live: dict[str, Any],
) -> dict[str, Any]:
    def on_progress(partial: dict[str, Any]) -> None:
        rows = []
        for step in partial.get("steps") or []:
            sid = str(step.get("step_id") or "")
            rows.append(
                {
                    "step_id": sid,
                    "label": sid.split("_", 1)[-1].replace("_", " ").title() if sid else "",
                    "tool_id": step.get("tool_id"),
                    "status": step.get("status") or "PENDING",
                }
            )
        record["agenda"] = rows
        _pace()

    context_payloads: dict[str, Any] = {}
    blocked: dict[str, bool] = {}
    live_rows = live.get("contexts") or {}
    live_bodies = record.get("_mireye_context_payloads") or {}
    for context_type in MIREYE_CONTEXT_TYPES:
        row = live_rows.get(context_type) or {}
        payload = live_bodies.get(context_type)
        succeeded = row.get("status") == "SUCCEEDED" and payload is not None
        blocked[context_type] = not succeeded
        if succeeded:
            context_payloads[context_type] = payload

    fixtures = ExecutionFixtures(
        land_profile=built["profile"],
        geometry=geometry,
        mireye_contexts=context_payloads,
        mireye_blocked_external=blocked,
    )
    execution = execute_plan(built["plan"], fixtures=fixtures, on_progress=on_progress)
    unified = (execution.get("_artifact_store") or {}).get("unified_output")
    if not isinstance(unified, dict):
        raise AdvisorAgentStepError("RUN_AGENDA", "Agenda finished without a Unified Output")
    if not is_cper_engineering_fixture(unified):
        raise AdvisorAgentStepError(
            "RUN_AGENDA",
            "Agenda output is not the CPER engineering fixture",
        )
    return {
        "unified_output": unified,
        "candidate_inventory": _load_json(F03_INVENTORY_REF),
        "remote_pilot": _load_json(F03_REMOTE_PILOT_REF),
    }


def _compare_claims(
    unified_output: dict[str, Any],
    listing_claims: list[dict[str, Any]],
    candidate_inventory: Any,
    remote_pilot: Any,
) -> dict[str, Any]:
    packet = project_cper_buyer_evidence_packet(
        unified_output,
        listing_claims=listing_claims,
        candidate_inventory=candidate_inventory,
        remote_pilot=remote_pilot,
        unified_output_ref=UNIFIED_OUTPUT_REF,
    )
    facts = land_fact_index(unified_output)
    violations = validate_packet(packet, land_facts=facts)
    if violations:
        codes = ", ".join(row["code"] for row in violations)
        raise AdvisorAgentStepError("COMPARE_CLAIMS", f"packet rejected: {codes}")
    return packet


def _order_actions(packet: dict[str, Any], unified_output: dict[str, Any]) -> dict[str, Any]:
    brief = generate_deterministic_brief(packet, unified_output=unified_output)
    if brief.get("validation_status") == "FAILED":
        codes = ", ".join(
            row.get("code") or "?" for row in (brief.get("validation_violations") or [])
        )
        raise AdvisorAgentStepError("ORDER_ACTIONS", f"brief packet validation failed: {codes}")
    return brief


def _validate_brief(
    brief: dict[str, Any],
    packet: dict[str, Any],
    unified_output: dict[str, Any],
) -> None:
    facts = land_fact_index(unified_output)
    violations = validate_three_page(brief, packet, land_facts=facts)
    if violations:
        codes = ", ".join(row["code"] for row in violations)
        raise AdvisorAgentStepError("VALIDATE_BRIEF", f"brief rejected: {codes}")
    if brief.get("report_provenance", {}).get("llm_used"):
        raise AdvisorAgentStepError("VALIDATE_BRIEF", "LLM overlay is not authorized for this Demo")


def enqueue_advisor_run(
    *,
    address: str | None = None,
    fixture_id: str | None = "CPER",
) -> dict[str, Any]:
    run_id = f"advisor_{uuid4().hex[:16]}"
    resolved_address = _resolve_requested_address(address, fixture_id)
    record: dict[str, Any] = {
        "status": "QUEUED",
        "run_id": run_id,
        "generated_at": _utc_now(),
        "address": resolved_address or address,
        "fixture_id": fixture_id,
        "steps": _empty_steps(),
        "agenda": [],
        "packet": None,
        "brief": None,
        "packet_hash": None,
        "parcel_geometry": None,
        "failed_step": None,
        "error": None,
        "llm_used": False,
        "limitations": [],
        "mireye_live": None,
        "buyer_explanation": None,
    }
    _RUNS[run_id] = record
    return _public_view(record)


def execute_advisor_run(run_id: str, *, fail_step: str | None = None) -> dict[str, Any]:
    record = _RUNS.get(run_id)
    if record is None:
        raise KeyError(run_id)
    record["status"] = "RUNNING"
    address = str(record.get("address") or "")
    try:
        accepted = _run_step(
            record, "ACCEPT_PLACE", lambda: _accept_place(address), fail_step=fail_step
        )
        resolved = _run_step(
            record, "RESOLVE_PARCEL", lambda: _resolve_parcel(accepted), fail_step=fail_step
        )
        live = _run_step(
            record,
            "CALL_MIREYE",
            lambda: _call_live_mireye(record, accepted, resolved["geometry"]),
            fail_step=fail_step,
        )
        built = _run_step(
            record, "BUILD_AGENDA", lambda: _build_agenda(record, resolved), fail_step=fail_step
        )
        record["agenda"] = list(built.get("agenda") or [])
        gathered = _run_step(
            record,
            "RUN_AGENDA",
            lambda: _run_agenda(record, built, resolved["geometry"], live),
            fail_step=fail_step,
        )
        packet = _run_step(
            record,
            "COMPARE_CLAIMS",
            lambda: _compare_claims(
                gathered["unified_output"],
                resolved["listing_claims"],
                gathered["candidate_inventory"],
                gathered["remote_pilot"],
            ),
            fail_step=fail_step,
        )
        brief = _run_step(
            record,
            "ORDER_ACTIONS",
            lambda: _order_actions(packet, gathered["unified_output"]),
            fail_step=fail_step,
        )
        _run_step(
            record,
            "VALIDATE_BRIEF",
            lambda: _validate_brief(brief, packet, gathered["unified_output"]),
            fail_step=fail_step,
        )
        record.update(
            {
                "status": "SUCCEEDED",
                "packet": packet,
                "brief": brief,
                "packet_hash": packet_hash(packet),
                "parcel_geometry": resolved["geometry"],
            }
        )
    except AdvisorAgentStepError as exc:
        _mark(record["steps"], exc.step_id, "FAILED", now=_utc_now())
        record.update(
            {
                "status": "FAILED",
                "failed_step": exc.step_id,
                "error": exc.message,
                "packet": None,
                "brief": None,
                "packet_hash": None,
                "parcel_geometry": None,
            }
        )
    return _public_view(record)


def run_cper_advisor_agent(
    *,
    address: str | None = None,
    fixture_id: str = "CPER",
    fail_step: str | None = None,
) -> dict[str, Any]:
    """Synchronous helper for tests. Demo HTTP path enqueues, then executes."""
    queued = enqueue_advisor_run(address=address, fixture_id=fixture_id)
    return execute_advisor_run(queued["run_id"], fail_step=fail_step)


def attach_advisor_buyer_explanation(
    run_id: str,
    *,
    provider_name: str = "FIXTURE",
) -> dict[str, Any]:
    """Optional LLM explanation. Live miss never becomes a silent fixture."""
    from rangematch.advisor_llm import generate_advisor_buyer_explanation

    record = _RUNS.get(run_id)
    if record is None:
        raise KeyError(run_id)
    if record.get("status") != "SUCCEEDED" or not record.get("packet"):
        raise AdvisorAgentStepError(
            "EXPLAIN",
            "Buyer explanation requires a succeeded Advisor run with a Packet",
        )
    record["buyer_explanation"] = generate_advisor_buyer_explanation(
        record["packet"],
        mireye_live=record.get("mireye_live"),
        provider_name=provider_name,
    )
    return _public_view(record)
