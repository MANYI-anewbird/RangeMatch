"""RangeMatch one-parcel investigation API.

Canonical Factor collection remains fixture-backed in this prototype. A
confirmed parcel may explicitly request live, non-canonical Mireye contexts.
In-memory stores are cleared on process restart.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from rangematch.advisor_agent import (
    AdvisorAgentStepError,
    attach_advisor_buyer_explanation,
    enqueue_advisor_run,
    execute_advisor_run,
    get_advisor_run,
    reset_advisor_runs_for_tests,
)
from rangematch.buyer_report import generate_buyer_report
from rangematch.intent_parser import IntentParseError, parse_intent
from rangematch.investigation_job import (
    pending_trace_from_plan,
    reset_investigation_job_hooks_for_tests,
    run_investigation_job,
    schedule_investigation_job,
)
from rangematch.investigation_store import (
    get_investigation_store,
    public_investigation_view,
    reset_investigation_store_for_tests,
)
from rangematch.llm_provider import configured_provider_name, provider_health_summary
from rangematch.parcel_resolution import (
    FixtureParcelResolver,
    ParcelResolutionError,
    compute_geometry_hash,
    confirm_selected_parcel,
    find_fixture_scenario_id,
    find_fixture_scenario_id_for_coordinates,
    planner_parcel_input,
    public_resolution_view,
    references_cper_demo_geometry,
    start_parcel_resolution,
)
from rangematch.parcel_resolution_store import (
    get_parcel_resolution_store,
    reset_parcel_resolution_store_for_tests,
)
from rangematch.planner import PLANNER_VERSION, PlannerError, build_investigation_plan
from rangematch.planner_executor import EXECUTOR_VERSION, execute_plan
from rangematch.tool_runners import ExecutionFixtures, MIREYE_BLOCKED_EXTERNAL_CLASS
from rangematch.unified_output import (
    validate_one_parcel_geometry,
    validate_run_mode,
)

API_VERSION = "RANGEMATCH_ONE_PARCEL_API@0.1.0"
SCHEMA_VERSION = "RANGEMATCH_UNIFIED_OUTPUT@0.1.0"
REPLAY_LABEL = "REPLAY_DEMO_FIXTURE_NOT_LIVE"

REPO_ROOT = Path(__file__).resolve().parents[2]
APPROVED_DATA_ROOT = (REPO_ROOT / "test-data").resolve()
APPROVED_CPER_PROFILE = (
    APPROVED_DATA_ROOT / "land-profiles" / "land_profile_cper_001.json"
).resolve()
APPROVED_CPER_GEOMETRY = (
    APPROVED_DATA_ROOT / "engineering_test_geometry_cper_001.geojson"
).resolve()
MIREYE_NORMALIZED = (APPROVED_DATA_ROOT / "mireye-normalized" / "normalized").resolve()

MAX_GEOMETRY_BYTES = 1_000_000  # 1 MiB prototype limit

_SECRET_RE = re.compile(
    r"(?i)(authorization|api[_-]?key|bearer\s+[a-z0-9._\-]+|password|client_secret)"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assert_no_secrets(payload: Any, *, where: str) -> None:
    """Reject credential-bearing structures without flagging policy prose.

    The previous whole-payload keyword regex treated the safe limitation
    ``Authorization is never stored`` as a leak and blocked every successful
    live lookup response. Reuse the adapter's value-aware scanner instead.
    """
    from rangematch.mireye_adapter import MireyeAdapterError, assert_no_credentials

    try:
        assert_no_credentials(payload, label=where)
    except MireyeAdapterError:
        raise HTTPException(status_code=500, detail=f"secret_leak_prevented:{where}")


def _live_mireye_availability() -> str:
    """Do not probe network from health; report configuration readiness only."""
    from rangematch.mireye_adapter import resolve_mireye_api_token

    if not resolve_mireye_api_token():
        return "NOT_CONFIGURED"
    return "CONFIGURED_LIVE_GATE_REQUIRED"


def _safe_resolve_land_profile(ref: str) -> Path:
    raw = (ref or "").strip()
    if not raw or "\x00" in raw:
        raise HTTPException(status_code=400, detail="invalid_land_profile_reference")
    candidate = Path(raw)
    if candidate.is_absolute():
        path = candidate.resolve()
    else:
        path = (REPO_ROOT / candidate).resolve()
    try:
        path.relative_to(APPROVED_DATA_ROOT)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="land_profile_path_outside_approved_root"
        ) from exc
    if ".." in Path(raw).parts:
        raise HTTPException(status_code=400, detail="path_traversal_rejected")
    if not path.is_file():
        raise HTTPException(status_code=400, detail="land_profile_not_found")
    if path.suffix.lower() != ".json":
        raise HTTPException(status_code=400, detail="land_profile_must_be_json")
    return path


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _mireye_fixture_bundle(*, blocked_external: bool) -> dict[str, Any]:
    if blocked_external:
        return {}
    return {
        "PROPERTY_DILIGENCE_CONTEXT": _load_json(
            MIREYE_NORMALIZED / "lookup_resolved.normalized.json"
        ),
        "POINT_LAND_CONTEXT": _load_json(
            MIREYE_NORMALIZED / "point_land_complete.normalized.json"
        ),
        "POINT_HAZARD_CONTEXT": _load_json(
            MIREYE_NORMALIZED / "point_hazard_complete.normalized.json"
        ),
    }


class InvestigationCreateRequest(BaseModel):
    address: str | None = None
    parcel_geometry: dict[str, Any] | None = None
    existing_land_profile_reference: str | None = None
    parcel_resolution_id: str | None = None
    mode: Literal["GOAL_DIRECTED", "DISCOVERY"]
    intended_operation: Literal["COW_CALF_OPERATION", "SHEEP_GRAZING"] | None = None
    planned_actions: list[str] = Field(default_factory=list)
    execution_source: Literal[
        "EXISTING_LAND_PROFILE", "DEMO_FIXTURE", "PARCEL_RESOLUTION"
    ]
    mireye_mode: Literal["FIXTURE", "BLOCKED_EXTERNAL", "LIVE"] = "BLOCKED_EXTERNAL"
    allow_network: bool = False

    @model_validator(mode="after")
    def _exactly_one_parcel_input(self) -> InvestigationCreateRequest:
        present = [
            name
            for name, value in (
                ("address", self.address and str(self.address).strip()),
                ("parcel_geometry", self.parcel_geometry is not None),
                (
                    "existing_land_profile_reference",
                    self.existing_land_profile_reference
                    and str(self.existing_land_profile_reference).strip(),
                ),
                (
                    "parcel_resolution_id",
                    self.parcel_resolution_id
                    and str(self.parcel_resolution_id).strip(),
                ),
            )
            if value
        ]
        if len(present) != 1:
            raise ValueError(
                "exactly_one_of_address_parcel_geometry_existing_land_profile_reference_parcel_resolution_id_required"
            )
        if self.parcel_resolution_id and self.execution_source != "PARCEL_RESOLUTION":
            raise ValueError(
                "parcel_resolution_id_requires_execution_source_PARCEL_RESOLUTION"
            )
        if (
            self.execution_source == "PARCEL_RESOLUTION"
            and not self.parcel_resolution_id
        ):
            raise ValueError("PARCEL_RESOLUTION_requires_parcel_resolution_id")
        try:
            validate_run_mode(self.mode, self.intended_operation)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(str(exc)) from exc
        if self.planned_actions is None:
            self.planned_actions = []
        if self.mireye_mode == "LIVE":
            if self.allow_network is not True:
                raise ValueError("LIVE_mireye_mode_requires_allow_network_true")
            if self.execution_source != "PARCEL_RESOLUTION":
                raise ValueError("LIVE_mireye_mode_requires_confirmed_PARCEL_RESOLUTION")
        if self.parcel_geometry is not None:
            blob = json.dumps(self.parcel_geometry, separators=(",", ":"))
            if len(blob.encode("utf-8")) > MAX_GEOMETRY_BYTES:
                raise ValueError("parcel_geometry_exceeds_size_limit")
            try:
                validate_one_parcel_geometry(self.parcel_geometry)
            except Exception as exc:  # noqa: BLE001
                raise ValueError(str(exc)) from exc
        return self


class ParcelResolutionCreateRequest(BaseModel):
    """Competition Demo: ADDRESS or COORDINATE → same confirmation flow."""

    input_kind: Literal["ADDRESS", "COORDINATE"] = "ADDRESS"
    address: str | None = Field(default=None, max_length=256)
    latitude: float | None = None
    longitude: float | None = None
    resolver_mode: Literal["FIXTURE", "LIVE"]
    fixture_scenario_id: str | None = None
    allow_network: bool = False

    @model_validator(mode="after")
    def _require_kind_inputs(self) -> ParcelResolutionCreateRequest:
        kind = self.input_kind
        if kind == "ADDRESS":
            if not (self.address and str(self.address).strip()):
                raise ValueError("address_required_for_ADDRESS_input")
            if self.latitude is not None or self.longitude is not None:
                raise ValueError("latitude_longitude_not_allowed_with_ADDRESS_input")
        elif kind == "COORDINATE":
            if self.latitude is None or self.longitude is None:
                raise ValueError("latitude_and_longitude_required_for_COORDINATE_input")
            if self.address and str(self.address).strip():
                raise ValueError("address_not_allowed_with_COORDINATE_input")
        return self


class ParcelResolutionConfirmRequest(BaseModel):
    selected_candidate_id: str = Field(min_length=1)
    expected_geometry_hash: str = Field(min_length=64, max_length=64)
    explicit_confirmation: bool

    @model_validator(mode="after")
    def _require_explicit_true(self) -> ParcelResolutionConfirmRequest:
        if self.explicit_confirmation is not True:
            raise ValueError("explicit_confirmation_must_be_true")
        if not re.fullmatch(r"[a-f0-9]{64}", self.expected_geometry_hash):
            raise ValueError("expected_geometry_hash_must_be_sha256_hex")
        return self


class HealthResponse(BaseModel):
    status: str
    api_version: str
    schema_version: str
    planner_version: str
    executor_version: str
    live_mireye_availability: str
    storage: str
    live_network_authorized: bool = False
    llm: dict[str, Any] = Field(default_factory=dict)
    parcel_resolver_live: str = "NOT_CONFIGURED"
    mireye_catalog_gate: dict[str, Any] = Field(default_factory=dict)


class IntentParseRequest(BaseModel):
    user_request: str
    address: str | None = None
    parcel_geometry: dict[str, Any] | None = None
    existing_land_profile_reference: str | None = None
    ui_mode: Literal["GOAL_DIRECTED", "DISCOVERY"] | None = None
    ui_intended_operation: Literal["COW_CALF_OPERATION", "SHEEP_GRAZING"] | None = None
    ui_planned_actions: list[str] | None = None
    provider: Literal["FIXTURE", "OPENAI"] | None = None

    @model_validator(mode="after")
    def _at_most_one_parcel_input(self) -> IntentParseRequest:
        present = [
            name
            for name, value in (
                ("address", self.address and str(self.address).strip()),
                ("parcel_geometry", self.parcel_geometry is not None),
                (
                    "existing_land_profile_reference",
                    self.existing_land_profile_reference
                    and str(self.existing_land_profile_reference).strip(),
                ),
            )
            if value
        ]
        if len(present) > 1:
            raise ValueError(
                "at_most_one_of_address_parcel_geometry_existing_land_profile_reference"
            )
        return self


class BuyerReportGenerateRequest(BaseModel):
    provider: Literal["FIXTURE", "OPENAI"] | None = None


class AdvisorRunRequest(BaseModel):
    address: str | None = None
    fixture_id: str | None = None


class AdvisorExplanationRequest(BaseModel):
    provider: Literal["FIXTURE", "OPENAI"] = "FIXTURE"


class DiligenceSearchRequest(BaseModel):
    provider: Literal["FIXTURE", "OPENAI"] | None = None
    topics: list[
        Literal[
            "REGULATION_AND_PERMITS",
            "LOCAL_AG_GUIDANCE",
            "CURRENT_DROUGHT",
            "PUBLIC_LAND_CONSTRAINTS",
        ]
    ] = Field(default_factory=list)


app = FastAPI(
    title="RangeMatch One-Parcel API",
    version="0.1.0",
    description=(
        "Fixture-backed / existing-Land-Profile investigation API with parcel "
        "resolution. Not live collection. In-memory stores clear on restart."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "http://127.0.0.1:5273",
        "http://localhost:5273",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:8001",
        "http://localhost:8001",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)


@app.exception_handler(Exception)
async def _sanitize_errors(request: Request, exc: Exception):  # noqa: ARG001
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return JSONResponse(status_code=500, content={"detail": "internal_error"})


@app.post("/v1/advisor/runs")
def create_advisor_run(
    body: AdvisorRunRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Queue one Advisor run: place → agenda → Packet → Brief."""
    queued = enqueue_advisor_run(
        address=body.address,
        fixture_id=body.fixture_id,
    )
    run_id = queued["run_id"]
    schedule_investigation_job(
        lambda: execute_advisor_run(run_id),
        background_tasks=background_tasks,
    )
    _assert_no_secrets(queued, where="advisor_run")
    return queued


@app.get("/v1/advisor/runs/{run_id}")
def get_advisor_run_endpoint(run_id: str) -> dict[str, Any]:
    record = get_advisor_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="advisor_run_not_found")
    _assert_no_secrets(record, where="advisor_run_get")
    return record


@app.post("/v1/advisor/runs/{run_id}/buyer-explanation")
def create_advisor_buyer_explanation(
    run_id: str,
    body: AdvisorExplanationRequest | None = None,
) -> dict[str, Any]:
    """Optional structured LLM explanation. Live failure does not swap a fixture."""
    req = body or AdvisorExplanationRequest()
    try:
        view = attach_advisor_buyer_explanation(run_id, provider_name=req.provider)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="advisor_run_not_found") from exc
    except AdvisorAgentStepError as exc:
        raise HTTPException(status_code=409, detail=exc.message) from exc
    _assert_no_secrets(view, where="advisor_buyer_explanation")
    return view


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    from rangematch.mireye_catalog_gate import evaluate_fixture_catalog

    llm = provider_health_summary()
    try:
        catalog_gate = evaluate_fixture_catalog().to_public_dict()
    except Exception as exc:  # noqa: BLE001 — health must stay up
        catalog_gate = {
            "status": "FETCH_FAILED",
            "compatible": False,
            "affects_parcel_resolution": False,
            "errors": [{"code": "CATALOG_GATE_HEALTH_ERROR", "message": type(exc).__name__}],
        }
    body = HealthResponse(
        status="ok",
        api_version=API_VERSION,
        schema_version=SCHEMA_VERSION,
        planner_version=PLANNER_VERSION,
        executor_version=EXECUTOR_VERSION,
        live_mireye_availability=_live_mireye_availability(),
        storage="in_memory_ephemeral",
        live_network_authorized=False,
        llm=llm,
        parcel_resolver_live="NOT_CONFIGURED",
        mireye_catalog_gate=catalog_gate,
    )
    _assert_no_secrets(body.model_dump(), where="health")
    return body


class CatalogGateRequest(BaseModel):
    mode: Literal["FIXTURE", "LIVE"] = "FIXTURE"
    etag: str | None = None
    allow_network: bool = False


@app.post("/v1/mireye/catalog-gate")
def mireye_catalog_gate(body: CatalogGateRequest | None = None) -> dict[str, Any]:
    """Run Field Catalog compatibility gate.

    Default FIXTURE (offline). LIVE requires allow_network=true and does not
    affect parcel resolution status.
    """
    from rangematch.mireye_catalog_gate import run_catalog_gate

    req = body or CatalogGateRequest()
    result = run_catalog_gate(
        mode=req.mode,
        etag=req.etag,
        allow_network=req.allow_network if req.mode == "LIVE" else False,
    )
    view = result.to_public_dict()
    _assert_no_secrets(view, where="mireye_catalog_gate")
    return view


class LookupLiveGateRequest(BaseModel):
    address: str = Field(min_length=1, max_length=256)
    allow_network: bool = False
    kind: Literal["address", "coord"] = "address"


@app.post("/v1/mireye/lookup-live-gate")
def mireye_lookup_live_gate(body: LookupLiveGateRequest) -> dict[str, Any]:
    """Controlled single-address /v1/lookup live gate.

    Does not claim success when network is blocked. Never calls /v1/fetch.
    Requires explicit allow_network=true for HTTP; otherwise NETWORK_NOT_AUTHORIZED.
    """
    from rangematch.mireye_catalog_gate import evaluate_fixture_catalog
    from rangematch.parcel_resolution import LiveParcelResolver, start_parcel_resolution

    try:
        catalog_ctx = evaluate_fixture_catalog().to_public_dict()
    except Exception as exc:  # noqa: BLE001
        catalog_ctx = {
            "status": "FETCH_FAILED",
            "compatible": False,
            "affects_parcel_resolution": False,
            "errors": [{"code": "CATALOG_CONTEXT_ERROR", "message": type(exc).__name__}],
        }

    resolver = LiveParcelResolver(
        allow_network=bool(body.allow_network),
        lookup_kind=body.kind,
        catalog_context=catalog_ctx,
        max_sleep_seconds=5.0,
    )
    record = start_parcel_resolution(
        body.address,
        mode="LIVE",
        resolver=resolver,
        allow_network=bool(body.allow_network),
    )
    store = get_parcel_resolution_store()
    store.put(record)
    resolution = public_resolution_view(record)
    transport = resolver.transport_result or {
        "ok": False,
        "error_class": "NETWORK_NOT_AUTHORIZED"
        if not body.allow_network
        else (record.get("provenance") or {}).get("mireye_lookup", {}).get("error_class"),
        "http_status": None,
        "catalog_context": catalog_ctx,
        "limitations": list(record.get("limitations") or []),
        "endpoint": "/v1/lookup",
    }

    success_statuses = {
        "NEEDS_BOUNDARY_CONFIRMATION",
        "NEEDS_USER_SELECTION",
        "PARCEL_DATA_UNAVAILABLE",
        "NO_MATCH",
        "AMBIGUOUS",
        "GEOCODE_QUALITY_INSUFFICIENT",
        "PARCEL_CONFIRMED",
    }
    transport_ok = bool(transport.get("ok"))
    view = {
        "gate": "MIREYE_LOOKUP_LIVE_GATE",
        "allow_network": bool(body.allow_network),
        "transport": transport,
        "parcel_resolution": resolution,
        "live_success_claimed": bool(
            body.allow_network
            and transport_ok
            and resolution.get("status") in success_statuses
        ),
        "notes": [
            "Does not claim live success when transport is BLOCKED_EXTERNAL.",
            "Catalog context is separate from parcel status.",
            "/v1/fetch Land/Hazard is out of scope for this gate.",
        ],
    }
    _assert_no_secrets(view, where="mireye_lookup_live_gate")
    return view


@app.post("/v1/intent/parse")
def intent_parse(body: IntentParseRequest) -> dict[str, Any]:
    try:
        intent = parse_intent(
            user_request=body.user_request,
            address=body.address,
            parcel_geometry=body.parcel_geometry,
            existing_land_profile_reference=body.existing_land_profile_reference,
            ui_mode=body.ui_mode,
            ui_intended_operation=body.ui_intended_operation,
            ui_planned_actions=body.ui_planned_actions,
            provider_name=body.provider,
        )
    except IntentParseError as exc:
        raise HTTPException(status_code=400, detail=f"{exc.code}:{exc.message}") from exc
    _assert_no_secrets(intent, where="intent_parse")
    return intent


@app.post("/v1/parcel-resolutions")
def create_parcel_resolution(body: ParcelResolutionCreateRequest) -> dict[str, Any]:
    from rangematch.coordinates import (
        CoordinateValidationError,
        format_coord_input,
        validate_us_query_point,
    )

    store = get_parcel_resolution_store()
    try:
        if body.input_kind == "COORDINATE":
            assert body.latitude is not None and body.longitude is not None
            validated = validate_us_query_point(float(body.latitude), float(body.longitude))
            query = format_coord_input(validated["latitude"], validated["longitude"])
            lookup_kind = "coord"
            latitude = validated["latitude"]
            longitude = validated["longitude"]
            address_for_resolver = query
        else:
            address_for_resolver = str(body.address or "").strip()
            if not address_for_resolver:
                raise HTTPException(status_code=400, detail="address_required")
            lookup_kind = "address"
            latitude = None
            longitude = None
            query = address_for_resolver

        if body.resolver_mode == "LIVE":
            live_scenario = (body.fixture_scenario_id or "").strip() or None
            record = start_parcel_resolution(
                address_for_resolver,
                mode="LIVE",
                scenario_id=live_scenario,
                allow_network=bool(body.allow_network) and not live_scenario,
                input_kind=body.input_kind,
                latitude=latitude,
                longitude=longitude,
                lookup_kind=lookup_kind,
            )
        else:
            scenario_id = (body.fixture_scenario_id or "").strip() or None
            if not scenario_id:
                if body.input_kind == "COORDINATE":
                    scenario_id = find_fixture_scenario_id_for_coordinates(
                        float(latitude), float(longitude)
                    )
                else:
                    scenario_id = find_fixture_scenario_id(query)
            if not scenario_id:
                raise HTTPException(
                    status_code=400,
                    detail="fixture_scenario_not_found_for_input",
                )
            record = start_parcel_resolution(
                address_for_resolver,
                mode="FIXTURE",
                scenario_id=scenario_id,
                input_kind=body.input_kind,
                latitude=latitude,
                longitude=longitude,
                lookup_kind=lookup_kind,
            )
    except CoordinateValidationError as exc:
        raise HTTPException(status_code=400, detail=f"{exc.code}:{exc.message}") from exc
    except ParcelResolutionError as exc:
        raise HTTPException(status_code=400, detail=f"{exc.code}:{exc.message}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    store.put(record)
    view = public_resolution_view(record)
    _assert_no_secrets(view, where="parcel_resolution_create")
    return view


@app.get("/v1/parcel-resolutions/{resolution_id}")
def get_parcel_resolution(resolution_id: str) -> dict[str, Any]:
    record = get_parcel_resolution_store().get(resolution_id)
    if record is None:
        raise HTTPException(status_code=404, detail="parcel_resolution_not_found")
    view = public_resolution_view(record)
    _assert_no_secrets(view, where="parcel_resolution_get")
    return view


@app.post("/v1/parcel-resolutions/{resolution_id}/confirm")
def confirm_parcel_resolution(
    resolution_id: str, body: ParcelResolutionConfirmRequest
) -> dict[str, Any]:
    store = get_parcel_resolution_store()
    record = store.get(resolution_id)
    if record is None:
        raise HTTPException(status_code=404, detail="parcel_resolution_not_found")

    resolver = None
    if record.get("provider_mode") in {"FIXTURE", "OFFLINE"} and record.get("scenario_id"):
        try:
            resolver = FixtureParcelResolver(str(record["scenario_id"]))
        except ParcelResolutionError:
            resolver = None

    try:
        confirmed = confirm_selected_parcel(
            record,
            candidate_id=body.selected_candidate_id,
            confirm_boundary=True,
            expected_geometry_hash=body.expected_geometry_hash,
            resolver=resolver,
        )
    except ParcelResolutionError as exc:
        status = 400
        if exc.code in {
            "STALE_GEOMETRY_HASH",
            "CONFIRMATION_CONFLICT",
            "CANDIDATE_MISMATCH",
            "INVALID_STATE",
        }:
            status = 409
        if exc.code == "CANDIDATE_NOT_FOUND":
            status = 404
        raise HTTPException(status_code=status, detail=f"{exc.code}:{exc.message}") from exc

    if confirmed.get("status") != "PARCEL_CONFIRMED":
        store.put(confirmed)
        view = public_resolution_view(confirmed)
        _assert_no_secrets(view, where="parcel_resolution_confirm_failed")
        raise HTTPException(
            status_code=409,
            detail={
                "code": confirmed.get("status"),
                "errors": confirmed.get("errors") or [],
                "resolution": view,
            },
        )

    binding = planner_parcel_input(confirmed)
    if (
        references_cper_demo_geometry(binding)
        and confirmed.get("scenario_id") == "silent_cper_substitution"
    ):
        raise HTTPException(status_code=409, detail="SILENT_CPER_SUBSTITUTION_REJECTED")

    store.put(confirmed)
    view = public_resolution_view(confirmed)
    view["planner_binding"] = binding
    _assert_no_secrets(view, where="parcel_resolution_confirm")
    return view


@app.post("/v1/investigations/{investigation_id}/buyer-report")
def post_buyer_report(
    investigation_id: str,
    body: BuyerReportGenerateRequest | None = None,
) -> dict[str, Any]:
    record = _get_record(investigation_id)
    if record.get("status") in {"QUEUED", "RUNNING"}:
        raise HTTPException(
            status_code=409,
            detail=f"investigation_not_terminal:{record.get('status')}",
        )
    unified = record.get("unified_output")
    if not isinstance(unified, dict):
        raise HTTPException(
            status_code=409,
            detail="unified_output_unavailable_for_investigation",
        )
    provider = body.provider if body is not None else None
    report = generate_buyer_report(
        unified,
        mode=record.get("mode"),
        intended_operation=record.get("intended_operation"),
        planned_actions=list(unified.get("planned_actions") or []),
        provider_name=provider,
    )
    get_investigation_store().update(investigation_id, {"llm_buyer_report": report})
    payload = {
        "investigation_id": investigation_id,
        "displayable": bool((report.get("report_provenance") or {}).get("displayable")),
        "validation_status": report.get("validation_status"),
        "buyer_report": report if report.get("validation_status") == "PASSED" else None,
        "validation_violations": report.get("validation_violations") or [],
        "report_provenance": report.get("report_provenance"),
    }
    _assert_no_secrets(payload, where="buyer_report_post")
    return payload


@app.get("/v1/investigations/{investigation_id}/buyer-report")
def get_buyer_report(investigation_id: str) -> dict[str, Any]:
    record = _get_record(investigation_id)
    report = record.get("llm_buyer_report")
    if not isinstance(report, dict):
        raise HTTPException(status_code=404, detail="buyer_report_not_generated")
    payload = {
        "investigation_id": investigation_id,
        "displayable": bool((report.get("report_provenance") or {}).get("displayable")),
        "validation_status": report.get("validation_status"),
        "buyer_report": report if report.get("validation_status") == "PASSED" else None,
        "validation_violations": report.get("validation_violations") or [],
        "report_provenance": report.get("report_provenance"),
    }
    _assert_no_secrets(payload, where="buyer_report_get")
    return payload


@app.post("/v1/investigations/{investigation_id}/diligence-search")
def post_diligence_search(
    investigation_id: str,
    body: DiligenceSearchRequest,
) -> dict[str, Any]:
    from rangematch.diligence_search import run_diligence_search

    record = _get_record(investigation_id)
    if record.get("status") in {"QUEUED", "RUNNING"}:
        raise HTTPException(
            status_code=409,
            detail=f"investigation_not_terminal:{record.get('status')}",
        )
    unified = record.get("unified_output")
    if not isinstance(unified, dict):
        raise HTTPException(
            status_code=409,
            detail="unified_output_unavailable_for_diligence_search",
        )
    parcel = unified.get("parcel") or {}
    search_jurisdiction = dict(parcel.get("jurisdiction") or {})
    if not (search_jurisdiction.get("county") or search_jurisdiction.get("state")):
        resolution_id = record.get("parcel_resolution_id")
        resolution = get_parcel_resolution_store().get(str(resolution_id)) if resolution_id else None
        if isinstance(resolution, dict):
            selected_id = ((resolution.get("selection") or {}).get("selected_candidate_id"))
            selected = next(
                (c for c in (resolution.get("candidates") or []) if c.get("candidate_id") == selected_id),
                None,
            )
            jurisdiction_value = ((selected or {}).get("attributes") or {}).get("jurisdiction")
            if isinstance(jurisdiction_value, dict):
                search_jurisdiction.update({k: jurisdiction_value.get(k) for k in ("county", "state") if jurisdiction_value.get(k)})
            elif jurisdiction_value:
                search_jurisdiction["county"] = str(jurisdiction_value)
    result = run_diligence_search(
        jurisdiction=search_jurisdiction,
        topics=list(body.topics) or None,
        provider=body.provider or configured_provider_name(),
    )
    get_investigation_store().update(
        investigation_id, {"diligence_search": result}
    )
    payload = {"investigation_id": investigation_id, "diligence_search": result}
    _assert_no_secrets(payload, where="diligence_search_post")
    return payload


@app.get("/v1/investigations/{investigation_id}/diligence-search")
def get_diligence_search(investigation_id: str) -> dict[str, Any]:
    record = _get_record(investigation_id)
    result = record.get("diligence_search")
    if not isinstance(result, dict):
        raise HTTPException(status_code=404, detail="diligence_search_not_run")
    payload = {"investigation_id": investigation_id, "diligence_search": result}
    _assert_no_secrets(payload, where="diligence_search_get")
    return payload


def _blocked_response(
    *,
    status: str,
    mode: str,
    intended_operation: str | None,
    execution_source: str,
    limitations: list[str],
    replay_label: str | None = None,
) -> dict[str, Any]:
    investigation_id = f"inv_{uuid4().hex[:16]}"
    record = {
        "investigation_id": investigation_id,
        "status": status,
        "mode": mode,
        "intended_operation": intended_operation,
        "execution_source": execution_source,
        "replay_label": replay_label,
        "plan_ref": None,
        "plan_sha256": None,
        "execution_ref": None,
        "deterministic_execution_hash": None,
        "unified_output_ref": None,
        "unified_output": None,
        "trace": {
            "steps": [],
            "failures": [],
            "note": "no_execution_trace_for_blocked_investigation",
            "status": status,
            "limitations": limitations,
        },
        "limitations": limitations,
        "created_at": _utc_now(),
        "completed_at": _utc_now(),
        "execution_claimed": False,
    }
    get_investigation_store().put(record)
    _assert_no_secrets(record, where="blocked_create")
    return public_investigation_view(record)


def _enqueue_from_confirmed_resolution(
    body: InvestigationCreateRequest,
    *,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    rid = str(body.parcel_resolution_id or "").strip()
    resolution = get_parcel_resolution_store().get(rid)
    if resolution is None:
        raise HTTPException(status_code=404, detail="parcel_resolution_not_found")
    if resolution.get("status") != "PARCEL_CONFIRMED":
        raise HTTPException(
            status_code=409,
            detail=f"parcel_resolution_not_confirmed:{resolution.get('status')}",
        )
    try:
        binding = planner_parcel_input(resolution)
    except ParcelResolutionError as exc:
        raise HTTPException(
            status_code=409, detail=f"{exc.code}:{exc.message}"
        ) from exc

    if (
        references_cper_demo_geometry(binding)
        and resolution.get("scenario_id") == "silent_cper_substitution"
    ):
        raise HTTPException(status_code=409, detail="SILENT_CPER_SUBSTITUTION_REJECTED")

    parcel_geometry = binding["parcel_geometry"]
    try:
        validate_one_parcel_geometry(parcel_geometry)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=409, detail=f"invalid_confirmed_geometry:{exc}"
        ) from exc

    approved_demo_profile = False
    if resolution.get("scenario_id") == "cper_complete_demo":
        try:
            approved_geometry = _load_json(APPROVED_CPER_GEOMETRY)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=500, detail="approved_demo_geometry_unavailable"
            ) from exc
        if binding["geometry_hash"] != compute_geometry_hash(approved_geometry):
            raise HTTPException(
                status_code=409, detail="APPROVED_DEMO_GEOMETRY_HASH_MISMATCH"
            )
        approved_demo_profile = True

    try:
        stable_plan_id = (
            f"api_{body.mode}_{body.intended_operation or 'DISCOVERY'}_"
            f"PARCEL_RESOLUTION_{rid}_mireye_{body.mireye_mode}"
        )
        plan = build_investigation_plan(
            mode=body.mode,
            intended_operation=body.intended_operation,
            parcel_geometry=parcel_geometry,
            planned_actions=body.planned_actions,
            plan_id=stable_plan_id,
            include_mireye_context=True,
        )
    except PlannerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    investigation_id = f"inv_{uuid4().hex[:16]}"
    record = {
        "investigation_id": investigation_id,
        "status": "QUEUED",
        "mode": body.mode,
        "intended_operation": body.intended_operation,
        "execution_source": "PARCEL_RESOLUTION",
        "replay_label": None,
        "parcel_resolution_id": rid,
        "geometry_hash": binding["geometry_hash"],
        "geometry_reference": binding["geometry_reference"],
        "source_crs": binding["source_crs"],
        "plan_ref": plan.get("plan_id"),
        "plan_sha256": plan.get("plan_sha256"),
        "execution_ref": None,
        "deterministic_execution_hash": None,
        "unified_output_ref": None,
        "unified_output": None,
        "trace": pending_trace_from_plan(plan),
        "limitations": [
            "execution_source:PARCEL_RESOLUTION",
            "geometry_bound_from_confirmed_parcel_resolution",
            f"geometry_hash:{binding['geometry_hash']}",
            "investigation_job_queued",
            "no_automatic_cper_fixture_substitution",
        ],
        "created_at": _utc_now(),
        "started_at": None,
        "completed_at": None,
        "land_profile_reference": None,
        "presentation": plan.get("presentation"),
        "mireye_live_summary": None,
        "live_factor_summary": None,
        "execution_claimed": False,
        "_job": {
            "kind": "PARCEL_RESOLUTION",
            "plan": plan,
            "binding": binding,
            "mireye_mode": body.mireye_mode,
            "approved_demo_profile": approved_demo_profile,
        },
    }
    get_investigation_store().put(record)
    schedule_investigation_job(
        lambda: run_investigation_job(investigation_id),
        background_tasks=background_tasks,
    )
    view = public_investigation_view(record)
    _assert_no_secrets(view, where="enqueue_from_resolution")
    return view


@app.post("/v1/investigations")
def create_investigation(
    body: InvestigationCreateRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    if body.parcel_resolution_id and str(body.parcel_resolution_id).strip():
        return _enqueue_from_confirmed_resolution(
            body, background_tasks=background_tasks
        )

    if body.address and str(body.address).strip():
        return _blocked_response(
            status="BLOCKED_EXTERNAL",
            mode=body.mode,
            intended_operation=body.intended_operation,
            execution_source=body.execution_source,
            limitations=[
                "address_input_requires_parcel_resolution",
                "use_POST_/v1/parcel-resolutions_then_confirm",
                "live_resolution_unavailable_without_configured_provider",
                "no_fabricated_geometry",
                "no_automatic_fixture_substitution",
                f"mireye_transport:{MIREYE_BLOCKED_EXTERNAL_CLASS}",
            ],
        )

    if body.parcel_geometry is not None and body.execution_source != "DEMO_FIXTURE":
        return _blocked_response(
            status="BLOCKED_INPUT",
            mode=body.mode,
            intended_operation=body.intended_operation,
            execution_source=body.execution_source,
            limitations=[
                "parcel_geometry_without_existing_land_profile_not_collected_live",
                "use_EXISTING_LAND_PROFILE_or_explicit_DEMO_FIXTURE",
                "no_live_data_collection_in_this_slice",
            ],
        )

    replay_label = None
    profile_path: Path | None = None
    land_profile: dict[str, Any] | None = None

    if body.execution_source == "DEMO_FIXTURE":
        replay_label = REPLAY_LABEL
        if body.existing_land_profile_reference:
            profile_path = _safe_resolve_land_profile(body.existing_land_profile_reference)
            if profile_path != APPROVED_CPER_PROFILE:
                raise HTTPException(
                    status_code=400,
                    detail="demo_fixture_only_cper_land_profile_cper_001_allowed",
                )
        elif body.parcel_geometry is not None:
            raise HTTPException(
                status_code=400,
                detail="demo_fixture_requires_existing_land_profile_reference_to_cper",
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="demo_fixture_requires_existing_land_profile_reference_to_cper",
            )
        land_profile = _load_json(profile_path)
    elif body.execution_source == "PARCEL_RESOLUTION":
        raise HTTPException(
            status_code=400,
            detail="PARCEL_RESOLUTION_requires_parcel_resolution_id",
        )
    else:
        if not body.existing_land_profile_reference:
            raise HTTPException(
                status_code=400,
                detail="existing_land_profile_reference_required",
            )
        profile_path = _safe_resolve_land_profile(body.existing_land_profile_reference)
        land_profile = _load_json(profile_path)

    try:
        stable_plan_id = (
            f"api_{body.mode}_{body.intended_operation or 'DISCOVERY'}_"
            f"{body.execution_source}_{profile_path.name}_"
            f"mireye_{body.mireye_mode}"
        )
        plan = build_investigation_plan(
            mode=body.mode,
            intended_operation=body.intended_operation,
            land_profile=land_profile,
            planned_actions=body.planned_actions,
            plan_id=stable_plan_id,
            include_mireye_context=True,
        )
    except PlannerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    mireye_blocked = body.mireye_mode == "BLOCKED_EXTERNAL"
    investigation_id = f"inv_{uuid4().hex[:16]}"
    record = {
        "investigation_id": investigation_id,
        "status": "QUEUED",
        "mode": body.mode,
        "intended_operation": body.intended_operation,
        "execution_source": body.execution_source,
        "replay_label": replay_label,
        "plan_ref": plan.get("plan_id"),
        "plan_sha256": plan.get("plan_sha256"),
        "execution_ref": None,
        "deterministic_execution_hash": None,
        "unified_output_ref": None,
        "unified_output": None,
        "trace": pending_trace_from_plan(plan),
        "limitations": ["investigation_job_queued"]
        + ([replay_label] if replay_label else []),
        "created_at": _utc_now(),
        "started_at": None,
        "completed_at": None,
        "land_profile_reference": str(profile_path.relative_to(REPO_ROOT))
        if profile_path
        else None,
        "presentation": plan.get("presentation"),
        "execution_claimed": False,
        "_job": {
            "kind": body.execution_source,
            "plan": plan,
            "profile_path": str(profile_path),
            "land_profile": land_profile,
            "mireye_blocked": mireye_blocked,
        },
    }
    get_investigation_store().put(record)
    schedule_investigation_job(
        lambda: run_investigation_job(investigation_id),
        background_tasks=background_tasks,
    )
    view = public_investigation_view(record)
    _assert_no_secrets(view, where="enqueue_create")
    return view


def _get_record(investigation_id: str) -> dict[str, Any]:
    record = get_investigation_store().get(investigation_id)
    if not record:
        raise HTTPException(status_code=404, detail="investigation_not_found")
    return record


@app.get("/v1/investigations/{investigation_id}")
def get_investigation(investigation_id: str) -> dict[str, Any]:
    record = _get_record(investigation_id)
    out = public_investigation_view(record)
    _assert_no_secrets(out.get("limitations") or [], where="get_limitations")
    return out


@app.get("/v1/investigations/{investigation_id}/trace")
def get_trace(investigation_id: str) -> dict[str, Any]:
    record = _get_record(investigation_id)
    trace = record.get("trace") or {
        "steps": [],
        "failures": [],
        "note": "no_execution_trace_for_blocked_investigation",
        "status": record.get("status"),
        "limitations": record.get("limitations") or [],
    }
    _assert_no_secrets(trace, where="trace")
    return trace


@app.get("/v1/investigations/{investigation_id}/report")
def get_report(investigation_id: str) -> dict[str, Any]:
    record = _get_record(investigation_id)
    if record.get("status") in {"QUEUED", "RUNNING"}:
        raise HTTPException(
            status_code=409,
            detail=f"investigation_not_terminal:{record.get('status')}",
        )
    unified = record.get("unified_output")
    if not isinstance(unified, dict):
        raise HTTPException(
            status_code=409,
            detail="unified_output_unavailable_for_investigation",
        )
    buyer = unified.get("buyer_report") or {}
    required = [
        "Property",
        "Land & Resources",
        "Resilience & Hazards",
        "Operation Comparison",
        "Diligence Plan",
    ]
    report = {section: buyer.get(section) for section in required}
    payload = {
        "investigation_id": investigation_id,
        "source": "unified_output.buyer_report",
        "replay_label": record.get("replay_label"),
        "mode": record.get("mode"),
        "intended_operation": record.get("intended_operation"),
        "match_result_hash": unified.get("match_result_hash"),
        "explanation_binding_hash": unified.get("explanation_binding_hash"),
        "sections": report,
        "limitations": record.get("limitations") or [],
    }
    _assert_no_secrets(payload, where="report")
    return payload


def reset_store_for_tests() -> None:
    """Test helper — clears ephemeral investigations and parcel resolutions."""
    reset_investigation_store_for_tests()
    reset_investigation_job_hooks_for_tests()
    reset_parcel_resolution_store_for_tests()
    reset_advisor_runs_for_tests()


# Explicitly no list/batch route is registered.
