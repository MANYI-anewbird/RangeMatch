"""Request-time Advisor Agent: place → agenda → Packet → Brief. No LLM."""

from __future__ import annotations

import copy
import json
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from rangematch.advisor_brief import _mireye_provenance, generate_deterministic_brief
from rangematch.advisor_bundle import assemble_advisor_report_bundle
from rangematch.advisor_contract import (
    REPO_ROOT,
    land_fact_index,
    packet_hash,
    validate_packet,
    validate_three_page,
)
from rangematch.advisor_generic_collect import (
    assemble_generic_unified_output,
    collect_advisor_factors,
    inventory_from_collection,
    paint_generic_agenda,
    unit_test_factor_collect,
)
from rangematch.advisor_generic_packet import project_generic_buyer_evidence_packet
from rangematch.advisor_packet import (
    F03_INVENTORY_REF,
    F03_REMOTE_PILOT_REF,
    is_cper_engineering_fixture,
    project_cper_buyer_evidence_packet,
)
from rangematch.advisor_place import (
    ASK_FOR_MORE,
    prepare_advisor_place,
    set_advisor_place_normalize_for_tests,
)
from rangematch.coordinates import CoordinateValidationError
from rangematch.parcel_resolution import (
    FIXTURE_ROOT,
    compute_geometry_hash,
    is_parcel_quality_accuracy,
    normalize_address_text,
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
NAMBE_DEMO_ADDRESS = "4213 Nambe Road, Indian Hills, CO 80454"
DEMO_SCENARIO_NAMBE_CATTLE_V1 = "NAMBE_CATTLE_V1"
RUN_MODE_CUSTOM = "CUSTOM"
RUN_MODE_VERIFIED_DEMO = "VERIFIED_DEMO"
HIGH_CONFIDENCE_MIN = 0.8
OUTCOME_PARCEL_NEEDS_CONFIRMATION = "PARCEL_NEEDS_CONFIRMATION"
OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED = "EVIDENCE_INVESTIGATION_COMPLETED"
OUTCOME_EVIDENCE_INVESTIGATION_INCOMPLETE = "EVIDENCE_INVESTIGATION_INCOMPLETE"
OUTCOME_PARCEL_NOT_FOUND = "PARCEL_NOT_FOUND"
OUTCOME_PARCEL_SERVICE_UNAVAILABLE = "PARCEL_SERVICE_UNAVAILABLE"
OUTCOME_INVESTIGATION_COULD_NOT_COMPLETE = "INVESTIGATION_COULD_NOT_COMPLETE"
TRACK_CPER_COMPLETE = "CPER_COMPLETE"
TRACK_GENERIC = "GENERIC_CONFIRMED"
TRACK_NEEDS_CONFIRM = "NEEDS_CONFIRM"
TRACK_LIMITED = "LIMITED"
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

# Phase 2 collection gate — not the Demo/LLM path.
MIREYE_FIRST_AGENT_STEPS: tuple[tuple[str, str], ...] = (
    ("ACCEPT_PLACE", "Accept place"),
    ("RESOLVE_PARCEL", "Resolve parcel"),
    ("DERIVE_F06", "Derive F06 geometry"),
    ("FETCH_MIREYE_ENVIRONMENT", "Fetch Mireye environment"),
    ("BUILD_MIREYE_ENVIRONMENTAL_PROFILE", "Build Mireye environmental profile"),
    ("DETECT_ENVIRONMENTAL_GAPS", "Detect environmental gaps"),
    ("RUN_ENVIRONMENTAL_SUPPLEMENTS", "Run planned environmental supplements"),
    ("COLLECT_ADDITIONAL_PROPERTY_CONTEXT", "Collect optional property context"),
    ("MERGE_ENVIRONMENTAL_EVIDENCE", "Merge combined environmental evidence"),
    ("PROJECT_NATURAL_CATTLE_PROFILE", "Project natural cattle profile"),
    ("CREATE_DEAL_CONTEXT", "Create deal context"),
    ("GENERATE_NATURAL_FOUNDATION_INTERPRETATION", "Generate natural foundation interpretation"),
)

COLLECTION_MODE_LEGACY = "LEGACY"
COLLECTION_MODE_MIREYE_FIRST = "MIREYE_FIRST"

_RUNS: dict[str, dict[str, Any]] = {}
_PACE_S = 0.22
_MIREYE_REQUEST_FN: Any = None
_MIREYE_LOOKUP_FN: Any = None
_SUPPLEMENT_RUNNERS_FN: Any = None
_PROPERTY_CONTEXT_RUNNER_FN: Any = None

# Transport / auth / provider failures — never "address not found".
_LOOKUP_SERVICE_ERROR_CLASSES = frozenset(
    {
        "AUTH_FAILED",
        "FORBIDDEN",
        "TOKEN_MISSING",
        "BLOCKED_EXTERNAL",
        "NETWORK_NOT_AUTHORIZED",
        "TIMEOUT",
        "UPSTREAM_TIMEOUT",
        "RATE_LIMITED",
        "SERVER_ERROR",
        "TRANSPORT_ERROR",
        "MALFORMED_JSON",
        "RESPONSE_CONTRACT_CHANGED",
        "RETRY_EXHAUSTED",
        "HTTP_404",
        "HTTP_401",
        "HTTP_403",
        "HTTP_429",
        "HTTP_500",
        "HTTP_502",
        "HTTP_503",
        "HTTP_504",
        "LOOKUP_FAILED",
        "FORCED_FIRST",
    }
)


def nambe_demo_scenario_claims() -> list[dict[str, Any]]:
    """Versioned Demo scenario claims. Not seller statements from the parcel owner."""
    return [
        {
            "claim_id": "DEMO_CLAIM_WATER_001",
            "category": "LIVESTOCK_WATER",
            "text": "Excellent year-round water",
            "source_reference": "nambe_cattle_v1#demo_water",
            "claim_strength": "STRONG",
            "verification_status": "SELLER_CLAIMED",
            "provenance": "DEMO_SCENARIO_CLAIM",
        },
        {
            "claim_id": "DEMO_CLAIM_ACCESS_001",
            "category": "LEGAL_ACCESS",
            "text": "Easy county-road access",
            "source_reference": "nambe_cattle_v1#demo_access",
            "claim_strength": "STRONG",
            "verification_status": "SELLER_CLAIMED",
            "provenance": "DEMO_SCENARIO_CLAIM",
        },
        {
            "claim_id": "DEMO_CLAIM_FORAGE_001",
            "category": "FORAGE_OR_PRODUCTION",
            "text": "Productive pasture ready for cattle",
            "source_reference": "nambe_cattle_v1#demo_forage",
            "claim_strength": "STRONG",
            "verification_status": "SELLER_CLAIMED",
            "provenance": "DEMO_SCENARIO_CLAIM",
        },
    ]


def _lookup_service_unavailable(error_class: str | None) -> bool:
    text = str(error_class or "").strip().upper()
    if not text:
        return True
    if text in _LOOKUP_SERVICE_ERROR_CLASSES:
        return True
    if text.startswith("HTTP_") and text != "HTTP_200":
        return True
    if "BLOCKED_EXTERNAL" in text or "TIMEOUT" in text or "TLS" in text:
        return True
    return False


_FACTOR_COLLECT_FN: Any = None


class AdvisorAgentStepError(RuntimeError):
    def __init__(
        self,
        step_id: str,
        message: str,
        *,
        investigation_outcome: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.step_id = step_id
        self.message = message
        self.investigation_outcome = investigation_outcome
        self.details = dict(details or {})


def _unit_test_mireye_request(*, endpoint: str, body: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    from rangematch.mireye_adapter import MireyeAdapterError

    raise MireyeAdapterError("TOKEN_MISSING:advisor_unit_test_hook")


def _is_cper_demo_address(address: str) -> bool:
    return normalize_address_text(address).lower() == normalize_address_text(
        CPER_DEMO_ADDRESS
    ).lower()


def classify_advisor_place(place: str) -> dict[str, Any]:
    """Classify a Demo place as ADDRESS or COORDINATE. Coords must be US lat,lng."""
    from rangematch.advisor_place import classify_place_input

    return classify_place_input(place)


def _lookup_transport_result(
    *,
    ok: bool,
    address: str,
    error_class: str | None = None,
    http_status: int | None = None,
    sanitized_response: dict[str, Any] | None = None,
    disposition: str | None = None,
    limitations: list[str] | None = None,
    kind: str = "address",
) -> Any:
    from rangematch.mireye_lookup_transport import LookupTransportResult

    lookup_kind = kind if kind in {"address", "coord"} else "address"
    return LookupTransportResult(
        ok=ok,
        error_class=error_class,
        http_status=http_status,
        sanitized_response=sanitized_response,
        response_hash=None,
        request_hash=None,
        attempts=1 if ok or error_class else 0,
        retries=0,
        sleep_seconds=[],
        retrieved_at=_utc_now(),
        endpoint="/v1/lookup",
        kind=lookup_kind,
        input_length=len(address or ""),
        input_fingerprint="advisor_unit_test_hook",
        limitations=list(limitations or ["unit test hook; no HTTP"]),
        disposition=disposition
        or (str((sanitized_response or {}).get("disposition") or "") or None),
    )


def _cper_unit_test_lookup_response() -> dict[str, Any]:
    """Unique high-confidence location resolve; polygon comes from CPER engineering bind."""
    return {
        "disposition": "resolved",
        "confidence": 0.95,
        "normalized_address": CPER_DEMO_ADDRESS,
        "accuracy_type": "rooftop",
        "accuracy": 1.0,
        "match_type": "address",
        "fetched_at": "2026-08-08T16:00:00+00:00",
        "request_id": "advisor_unit_cper_lookup",
        "lat": 40.825,
        "lng": -104.7625,
        "resolved_location": {
            "lat": 40.825,
            "lng": -104.7625,
            "source": "geocode",
        },
        "parcel_unavailable": True,
        "parcel_unavailable_reason": "advisor_demo_location_resolve_only",
        "fields": {},
        "partial_failures": [],
    }


def _unit_test_lookup(address: str, **kwargs: Any) -> Any:
    """Default test hook: CPER demo → unique high-conf Mireye; anything else → fail closed."""
    if _is_cper_demo_address(address):
        return _lookup_transport_result(
            ok=True,
            address=address,
            sanitized_response=_cper_unit_test_lookup_response(),
            disposition="resolved",
        )
    return _lookup_transport_result(
        ok=False,
        address=address,
        error_class="UNIT_TEST_HOOK",
        limitations=["unit test hook; no HTTP; non-CPER address not simulated"],
    )


def reset_advisor_runs_for_tests() -> None:
    from rangematch.advisor_deal_context import reset_deal_contexts_for_tests
    from rangematch.parcel_resolution_store import reset_parcel_resolution_store_for_tests

    _RUNS.clear()
    reset_deal_contexts_for_tests()
    reset_parcel_resolution_store_for_tests()
    set_advisor_pace_for_tests(0.0)
    set_advisor_mireye_hooks_for_tests(
        request_fn=_unit_test_mireye_request,
        lookup_fn=_unit_test_lookup,
    )
    set_advisor_factor_collect_for_tests(unit_test_factor_collect)
    set_advisor_supplement_runners_for_tests(_unit_test_supplement_runners)
    set_advisor_property_context_runner_for_tests(lambda: {
        "factor_id": "F07_ROAD_AND_PHYSICAL_ACCESS",
        "canonical_source_id": "UNIT_TEST_TIGER",
        "land_facts": [{
            "variable_id": "VAR_F07_NEAREST_MAPPED_ROAD_DISTANCE_M",
            "value": 0.0,
            "unit": "m",
            "spatial_semantics": "CONTEXT",
            "source_id": "UNIT_TEST_TIGER",
        }],
    })
    set_advisor_place_normalize_for_tests(None)
    from rangematch.advisor_generic_collect import set_advisor_collect_timeouts_for_tests

    set_advisor_collect_timeouts_for_tests()


def _unit_test_supplement_runners(**_kwargs: Any) -> dict[str, Any]:
    from rangematch.environmental_supplement_runner import unit_test_supplement_runners

    return unit_test_supplement_runners()


def set_advisor_mireye_hooks_for_tests(
    *,
    request_fn: Any | None = None,
    lookup_fn: Any | None = None,
) -> None:
    """Tests only. Production uvicorn never calls this; live HTTP is the default."""
    global _MIREYE_REQUEST_FN, _MIREYE_LOOKUP_FN
    _MIREYE_REQUEST_FN = request_fn
    _MIREYE_LOOKUP_FN = lookup_fn


def set_advisor_factor_collect_for_tests(collect_fn: Any | None) -> None:
    """Tests only. None restores live F01–F08 adapters (not used by unit tests)."""
    global _FACTOR_COLLECT_FN
    _FACTOR_COLLECT_FN = collect_fn


def set_advisor_supplement_runners_for_tests(runners_fn: Any | None) -> None:
    """Tests only. None restores live plan-driven F01–F05/F08 adapters."""
    global _SUPPLEMENT_RUNNERS_FN
    _SUPPLEMENT_RUNNERS_FN = runners_fn


def set_advisor_property_context_runner_for_tests(runner_fn: Any | None) -> None:
    """Tests only. None restores the live fail-soft F07 Appendix collector."""
    global _PROPERTY_CONTEXT_RUNNER_FN
    _PROPERTY_CONTEXT_RUNNER_FN = runner_fn


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


def _empty_steps(
    *, collection_mode: str = COLLECTION_MODE_LEGACY
) -> list[dict[str, Any]]:
    steps = (
        MIREYE_FIRST_AGENT_STEPS
        if collection_mode == COLLECTION_MODE_MIREYE_FIRST
        else AGENT_STEPS
    )
    return [
        {
            "step_id": step_id,
            "label": label,
            "status": "PENDING",
            "started_at": None,
            "completed_at": None,
        }
        for step_id, label in steps
    ]


def _public_view(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": record["status"],
        "run_id": record["run_id"],
        "generated_at": record["generated_at"],
        "address": record.get("address"),
        "fixture_id": record.get("fixture_id"),
        "run_mode": record.get("run_mode") or RUN_MODE_CUSTOM,
        "demo_scenario_id": record.get("demo_scenario_id"),
        "packet_hash": record.get("packet_hash"),
        "llm_used": bool(
            ((record.get("buyer_explanation") or {}).get("provenance") or {}).get("llm_used")
        ),
        "generator": (
            "LLM_OVERLAY"
            if (record.get("buyer_explanation") or {}).get("source") == "LIVE_LLM"
            else (
                "FALLBACK_TEMPLATE"
                if (record.get("buyer_explanation") or {}).get("source")
                == "DETERMINISTIC_FALLBACK"
                else "DETERMINISTIC_TEMPLATE"
            )
        ),
        "failed_step": record.get("failed_step"),
        "error": record.get("error"),
        "investigation_outcome": record.get("investigation_outcome"),
        "environmental_profile_outcome": record.get("environmental_profile_outcome"),
        "collection_mode": record.get("collection_mode") or COLLECTION_MODE_LEGACY,
        "location_resolved": bool(record.get("location_resolved")),
        "parcel_geometry_confirmed": bool(record.get("parcel_geometry_confirmed")),
        "parcel_resolution_id": record.get("parcel_resolution_id"),
        "geometry_hash": record.get("geometry_hash"),
        "track": record.get("track"),
        "limited_investigation": record.get("limited_investigation"),
        "parcel_candidates": list(record.get("parcel_candidates") or []),
        "steps": list(record.get("steps") or []),
        "agenda": list(record.get("agenda") or []),
        "packet": record.get("packet"),
        "brief": record.get("brief"),
        "parcel_geometry": record.get("parcel_geometry"),
        "limitations": list(record.get("limitations") or []),
        "collecting_factor": record.get("collecting_factor"),
        "mireye_live": record.get("mireye_live"),
        "mireye_environmental_profile": record.get("mireye_environmental_profile"),
        "mireye_environmental_profile_hash": (
            (record.get("mireye_environmental_profile") or {}).get("profile_hash")
            if isinstance(record.get("mireye_environmental_profile"), dict)
            else None
        ),
        "environmental_gap_plan": record.get("environmental_gap_plan"),
        "supplement_execution": record.get("supplement_execution"),
        "additional_property_context_collection": record.get(
            "additional_property_context_collection"
        ),
        "combined_environmental_evidence_packet": record.get(
            "combined_environmental_evidence_packet"
        ),
        "natural_cattle_profile": record.get("natural_cattle_profile"),
        "natural_cattle_profile_hash": (
            (record.get("natural_cattle_profile") or {}).get("profile_hash")
            if isinstance(record.get("natural_cattle_profile"), dict)
            else None
        ),
        "natural_foundation_interpretation": record.get(
            "natural_foundation_interpretation"
        ),
        "f06_derivation": record.get("f06_derivation"),
        "buyer_explanation": record.get("buyer_explanation"),
        "operating_profile": record.get("operating_profile"),
        "operating_profile_hash": (record.get("operating_profile") or {}).get("profile_hash")
        if isinstance(record.get("operating_profile"), dict)
        else None,
        "place_normalization": record.get("place_normalization"),
        "deal_context": record.get("deal_context"),
        "operating_conclusion": record.get("operating_conclusion"),
        "initial_operating_conclusion": record.get("initial_operating_conclusion"),
        "revised_operating_conclusion": record.get("revised_operating_conclusion"),
        "conclusion_change": record.get("conclusion_change"),
        "chat_turns": list(record.get("chat_turns") or []),
        "chat_suggestions": record.get("chat_suggestions"),
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
    status = "SUCCEEDED"
    if isinstance(result, dict) and result.get("_step_status"):
        status = str(result["_step_status"])
    _mark(steps, step_id, status, now=_utc_now())
    _pace()
    return result


def _resolve_requested_address(address: str | None, fixture_id: str | None) -> str:
    text = (address or "").strip()
    if text:
        return text
    if (fixture_id or "").strip() == "CPER":
        return CPER_DEMO_ADDRESS
    return ""


def _accept_place(address: str, record: dict[str, Any] | None = None) -> str:
    if not address:
        raise AdvisorAgentStepError(
            "ACCEPT_PLACE",
            "Enter a U.S. street address or lat,lng coordinates before running the Agent.",
        )
    try:
        prepared = prepare_advisor_place(address)
    except CoordinateValidationError as exc:
        raise AdvisorAgentStepError(
            "ACCEPT_PLACE",
            f"Place input failed: {exc.message}",
            investigation_outcome=OUTCOME_INVESTIGATION_COULD_NOT_COMPLETE,
        ) from exc
    if record is not None:
        record["place_normalization"] = prepared.get("public")
        if prepared.get("lookup_input"):
            record["address"] = prepared["lookup_input"]
        note = (prepared.get("public") or {}).get("note")
        if note and note not in (record.get("limitations") or []):
            record.setdefault("limitations", []).append(note)
    if prepared.get("status") == "NEEDS_MORE":
        raise AdvisorAgentStepError(
            "ACCEPT_PLACE",
            str(prepared.get("message") or ASK_FOR_MORE),
            investigation_outcome=OUTCOME_INVESTIGATION_COULD_NOT_COMPLETE,
            details={
                "place_normalization": prepared.get("public"),
                "location_resolved": False,
                "parcel_geometry_confirmed": False,
            },
        )
    return str(prepared.get("lookup_input") or address)


def _invoke_mireye_lookup(address: str) -> Any:
    from rangematch.mireye_lookup_transport import lookup_parcel_via_mireye

    classified = classify_advisor_place(address)
    lookup_fn = _MIREYE_LOOKUP_FN or lookup_parcel_via_mireye
    return lookup_fn(
        classified["input"],
        kind=classified["kind"],
        allow_network=True,
    )


def _confidence_allows_continue(mapping: Any) -> bool:
    confidence = mapping.confidence
    if confidence is not None and float(confidence) < HIGH_CONFIDENCE_MIN:
        return False
    accuracy_type = mapping.accuracy_type
    if accuracy_type and not is_parcel_quality_accuracy(accuracy_type):
        return False
    return True


def _candidate_public_rows(mapping: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cand in list(mapping.candidates or [])[:3]:
        geometry = cand.get("parcel_geometry")
        geometry_hash = cand.get("geometry_hash")
        if not geometry_hash and geometry:
            try:
                geometry_hash = compute_geometry_hash(geometry)
            except Exception:  # noqa: BLE001 — public row stays honest
                geometry_hash = None
        rows.append(
            {
                "candidate_id": cand.get("candidate_id"),
                "label": cand.get("label"),
                "parcel_id": cand.get("parcel_id") or cand.get("external_parcel_id"),
                "has_geometry": bool(geometry),
                "geometry_hash": geometry_hash,
            }
        )
    if rows:
        return rows
    for hint in list(getattr(mapping, "location_hints", None) or [])[:3]:
        rows.append(
            {
                "candidate_id": hint.get("candidate_id"),
                "label": hint.get("label"),
                "parcel_id": None,
                "has_geometry": bool(hint.get("has_geometry")),
                "geometry_hash": hint.get("geometry_hash"),
                "lat": hint.get("lat"),
                "lng": hint.get("lng"),
            }
        )
    return rows


def _bind_cper_engineering_after_mireye(address: str) -> dict[str, Any]:
    """CPER full path only after Mireye unique high-confidence location resolve."""
    path = FIXTURE_ROOT / f"{CPER_SCENARIO_ID}.json"
    scenario = json.loads(path.read_text(encoding="utf-8"))
    candidates = list(scenario.get("candidates") or [])
    if not candidates:
        raise AdvisorAgentStepError(
            "RESOLVE_PARCEL",
            "CPER demo location resolved, but engineering geometry is missing.",
            investigation_outcome=OUTCOME_INVESTIGATION_COULD_NOT_COMPLETE,
        )
    geometry = candidates[0].get("parcel_geometry")
    validate_one_parcel_geometry(geometry)
    return {
        "scenario_id": CPER_SCENARIO_ID,
        "label": candidates[0].get("label") or CPER_SCENARIO_ID,
        "geometry": geometry,
        "listing_claims": list(_load_json(CLAIMS_REF).get("listing_claims") or []),
        "track": TRACK_CPER_COMPLETE,
        "location_resolved": True,
        "parcel_geometry_confirmed": True,
        "geometry_source": "CPER_ENGINEERING_FIXTURE",
        "limitations": [
            "Mireye resolved the demo location first; CPER engineering boundary was "
            "bound only for the Challenge Demo complete path — not as a nationwide "
            "parcel confirmation.",
        ],
    }


def _limited_investigation_payload(
    *,
    address: str,
    mapping: Any | None,
    lookup_view: dict[str, Any] | None,
    parcel_geometry_confirmed: bool = False,
    parcel_resolution_id: str | None = None,
    geometry_hash: str | None = None,
) -> dict[str, Any]:
    point = getattr(mapping, "geocode_point", None) if mapping is not None else None
    coords = None
    if isinstance(point, dict) and point.get("coordinates"):
        coords = {
            "lng": float(point["coordinates"][0]),
            "lat": float(point["coordinates"][1]),
        }
    if parcel_geometry_confirmed:
        message = (
            "Parcel boundary is confirmed. The Generic Evidence Packet projector is "
            "available, but this Advisor run has not yet executed F01–F08 for a "
            "nationwide Unified Output. CPER demo claims, objects, and policy were "
            "not applied."
        )
        next_step = (
            "Next milestone: run F01–F08 on the confirmed geometry, project a "
            "Generic Packet, then emit the three-page brief."
        )
    else:
        message = (
            "Location was recognized with a unique high-confidence Mireye candidate, "
            "but no confirmable parcel polygon is available yet. Boundary is not "
            "confirmed from lookup alone, and no general Packet exists."
        )
        next_step = (
            "Provide a clearer address, drop a pin, or obtain a parcel polygon "
            "before a full investigation can start."
        )
    return {
        "address": address,
        "normalized_address": getattr(mapping, "normalized_address", None) if mapping else address,
        "location_resolved": True,
        "parcel_geometry_confirmed": parcel_geometry_confirmed,
        "parcel_resolution_id": parcel_resolution_id,
        "geometry_hash": geometry_hash,
        "mireye_disposition": getattr(mapping, "disposition", None) if mapping else None,
        "accuracy_type": getattr(mapping, "accuracy_type", None) if mapping else None,
        "confidence": getattr(mapping, "confidence", None) if mapping else None,
        "geocode_point": coords,
        "candidate_count": len(list(getattr(mapping, "candidates", None) or []))
        if mapping
        else 0,
        "parcel_unavailable": getattr(mapping, "parcel_unavailable", None) if mapping else None,
        "parcel_unavailable_reason": getattr(mapping, "parcel_unavailable_reason", None)
        if mapping
        else None,
        "lookup": lookup_view,
        "cper_policy_blocked": True,
        "full_buyer_report": False,
        "message": message,
        "next_step": next_step,
    }


def _stage_confirmation_or_none(
    *,
    address: str,
    mapping: Any,
    lookup_view: dict[str, Any],
) -> tuple[str | None, list[dict[str, Any]]]:
    from rangematch.advisor_parcel_gate import (
        AdvisorParcelGateError,
        stage_mireye_mapping_for_confirmation,
    )

    if not list(mapping.candidates or []):
        return None, _candidate_public_rows(mapping)
    try:
        classified = classify_advisor_place(address)
        staged = stage_mireye_mapping_for_confirmation(
            address=address,
            mapping=mapping,
            lookup_view=lookup_view,
            input_kind=str(classified.get("input_kind") or "ADDRESS"),
            latitude=classified.get("latitude"),
            longitude=classified.get("longitude"),
        )
    except AdvisorParcelGateError:
        return None, _candidate_public_rows(mapping)
    rows = [
        {
            "candidate_id": c.get("candidate_id"),
            "label": c.get("label"),
            "parcel_id": (c.get("attributes") or {}).get("apn") or c.get("candidate_id"),
            "has_geometry": bool(c.get("parcel_geometry")),
            "geometry_hash": c.get("geometry_hash"),
        }
        for c in list(staged.get("candidates") or [])[:3]
        if c.get("validation_status") == "VALID"
    ]
    return str(staged["resolution_id"]), rows


def _needs_confirmation_result(
    address: str,
    *,
    message: str,
    mapping: Any,
    lookup_view: dict[str, Any],
    stage: bool,
) -> dict[str, Any]:
    """Return a confirm-gate result. Not a FAILED step."""
    raised = _needs_confirmation_error(
        address,
        message=message,
        mapping=mapping,
        lookup_view=lookup_view,
        stage=stage,
    )
    details = dict(raised.details or {})
    return {
        "track": TRACK_NEEDS_CONFIRM,
        "_step_status": "NEEDS_CONFIRMATION",
        "label": address,
        "location_resolved": bool(details.get("location_resolved")),
        "parcel_geometry_confirmed": False,
        "parcel_resolution_id": details.get("parcel_resolution_id"),
        "parcel_candidates": list(details.get("parcel_candidates") or []),
        "lookup_view": details.get("mireye_live_lookup"),
        "message": raised.message,
        "limitations": [
            "Mireye found a parcel candidate. Confirm the boundary before F01–F08.",
        ],
    }


def _needs_confirmation_error(
    address: str,
    *,
    message: str,
    mapping: Any,
    lookup_view: dict[str, Any],
    stage: bool,
) -> AdvisorAgentStepError:
    resolution_id = None
    rows = _candidate_public_rows(mapping)
    if stage:
        resolution_id, rows = _stage_confirmation_or_none(
            address=address, mapping=mapping, lookup_view=lookup_view
        )
    return AdvisorAgentStepError(
        "RESOLVE_PARCEL",
        message,
        investigation_outcome=OUTCOME_PARCEL_NEEDS_CONFIRMATION,
        details={
            "mireye_live_lookup": lookup_view,
            "parcel_candidates": rows,
            "normalized_address": mapping.normalized_address,
            "accuracy_type": mapping.accuracy_type,
            "confidence": mapping.confidence,
            "location_resolved": mapping.geocode_point is not None or bool(rows),
            "parcel_geometry_confirmed": False,
            "parcel_resolution_id": resolution_id,
        },
    )


def _resolve_confirmed_parcel(
    address: str, parcel_resolution_id: str
) -> dict[str, Any]:
    """Continue only from an existing PARCEL_CONFIRMED resolution record."""
    from rangematch.advisor_parcel_gate import (
        AdvisorParcelGateError,
        load_confirmed_binding,
    )

    try:
        binding = load_confirmed_binding(parcel_resolution_id)
    except AdvisorParcelGateError as exc:
        outcome = (
            OUTCOME_PARCEL_NEEDS_CONFIRMATION
            if exc.code == "PARCEL_NOT_CONFIRMED"
            else OUTCOME_INVESTIGATION_COULD_NOT_COMPLETE
        )
        raise AdvisorAgentStepError(
            "RESOLVE_PARCEL",
            exc.message,
            investigation_outcome=outcome,
            details={
                "location_resolved": False,
                "parcel_geometry_confirmed": False,
                "parcel_resolution_id": parcel_resolution_id,
            },
        ) from exc

    geometry = binding["parcel_geometry"]
    validate_one_parcel_geometry(geometry)
    limitations = [
        "Advisor continued from PARCEL_CONFIRMED parcel resolution.",
        f"geometry_hash={binding['geometry_hash']}",
        f"polygon_source={binding.get('polygon_source') or 'unknown'}",
        "USER_BOUNDARY_CONFIRMATION is required for full investigation "
        "(see docs/ADVISOR_PARCEL_CONFIRMATION_GATE.md).",
    ]

    if _is_cper_demo_address(address):
        bound = _bind_cper_engineering_after_mireye(address)
        bound["parcel_resolution_id"] = parcel_resolution_id
        bound["geometry_hash"] = binding["geometry_hash"]
        bound["limitations"] = limitations + list(bound.get("limitations") or [])
        return bound

    return {
        "scenario_id": None,
        "label": address,
        "geometry": geometry,
        "listing_claims": [],
        "track": TRACK_GENERIC,
        "location_resolved": True,
        "parcel_geometry_confirmed": True,
        "geometry_source": binding.get("polygon_source"),
        "parcel_resolution_id": parcel_resolution_id,
        "geometry_hash": binding["geometry_hash"],
        "geometry_id": binding.get("geometry_id")
        or binding.get("selected_candidate_id")
        or f"CONFIRMED_{binding['geometry_hash'][:16]}",
        "geometry_reference": binding.get("geometry_reference")
        or f"parcel_resolution:{parcel_resolution_id}",
        "limitations": limitations
        + [
            "Confirmed non-CPER parcel bound to this run; downstream collection "
            "follows the selected collection_mode. CPER claims, CPER F03 fixtures, "
            "and build_cper_demo_policy are not applied.",
        ],
    }


def _resolve_parcel(
    address: str, *, parcel_resolution_id: str | None = None
) -> dict[str, Any]:
    """Mireye-first entry. Full investigation requires PARCEL_CONFIRMED (except CPER demo)."""
    from rangematch.mireye_parcel_resolver import map_mireye_lookup_to_parcel

    if parcel_resolution_id:
        return _resolve_confirmed_parcel(address, parcel_resolution_id)

    lookup_result = _invoke_mireye_lookup(address)
    lookup_view = _public_lookup_view(lookup_result)

    if not getattr(lookup_result, "ok", False) or not getattr(
        lookup_result, "sanitized_response", None
    ):
        raise AdvisorAgentStepError(
            "RESOLVE_PARCEL",
            f"The parcel service could not complete this lookup for “{address}” "
            f"({lookup_view.get('error_class') or 'LOOKUP_FAILED'}; "
            f"http_status={lookup_view.get('http_status')}). "
            "RangeMatch did not substitute another property.",
            investigation_outcome=OUTCOME_PARCEL_SERVICE_UNAVAILABLE,
            details={
                "location_resolved": False,
                "parcel_geometry_confirmed": False,
                "mireye_live_lookup": lookup_view,
            },
        )

    try:
        mapping = map_mireye_lookup_to_parcel(lookup_result.sanitized_response)
    except Exception as exc:  # noqa: BLE001 — keep failure step honest
        raise AdvisorAgentStepError(
            "RESOLVE_PARCEL",
            f"The parcel service returned a response that could not be used: "
            f"{type(exc).__name__}: {exc}. RangeMatch did not substitute another property.",
            investigation_outcome=OUTCOME_PARCEL_SERVICE_UNAVAILABLE,
            details={
                "location_resolved": False,
                "parcel_geometry_confirmed": False,
                "mireye_live_lookup": lookup_view,
            },
        ) from exc

    terminal = mapping.terminal_status
    candidates = list(mapping.candidates or [])
    candidate_rows = _candidate_public_rows(mapping)
    base_details = {
        "mireye_live_lookup": lookup_view,
        "parcel_candidates": candidate_rows,
        "normalized_address": mapping.normalized_address,
        "accuracy_type": mapping.accuracy_type,
        "confidence": mapping.confidence,
    }

    if terminal == "NO_MATCH":
        reason = getattr(mapping, "no_match_reason", None) or "no_match"
        hint = getattr(mapping, "no_match_hint", None)
        message = (
            f"We found the general location inquiry completed, but no parcel boundary "
            f"precise enough for property-level analysis matched “{address}” "
            f"(reason={reason}). No report was generated."
        )
        if hint:
            message = f"{message} {hint}"
        raise AdvisorAgentStepError(
            "RESOLVE_PARCEL",
            message,
            investigation_outcome=OUTCOME_PARCEL_NOT_FOUND,
            details={**base_details, "location_resolved": False, "parcel_geometry_confirmed": False},
        )

    if terminal in {"AMBIGUOUS", "GEOCODE_QUALITY_INSUFFICIENT"} and not candidates:
        labels = [
            str(row.get("label") or "").strip()
            for row in candidate_rows
            if row.get("label")
        ]
        extra = f" Candidates: {'; '.join(labels)}." if labels else ""
        raise AdvisorAgentStepError(
            "RESOLVE_PARCEL",
            f"We found the general location, but not a parcel boundary precise enough "
            f"for a property-level analysis of “{address}” "
            f"(terminal={terminal}, disposition={mapping.disposition}).{extra} "
            "No report was generated.",
            investigation_outcome=OUTCOME_PARCEL_NOT_FOUND,
            details={
                **base_details,
                "location_resolved": bool(mapping.geocode_point or candidate_rows),
                "parcel_geometry_confirmed": False,
            },
        )

    if terminal in {"AMBIGUOUS", "GEOCODE_QUALITY_INSUFFICIENT"}:
        return _needs_confirmation_result(
            address,
            message=(
                f"Parcel needs confirmation for “{address}” "
                f"(disposition={mapping.disposition}, terminal={terminal})."
            ),
            mapping=mapping,
            lookup_view=lookup_view,
            stage=True,
        )

    if mapping.disposition == "clarify" or len(candidates) > 1:
        return _needs_confirmation_result(
            address,
            message=(
                f"Multiple parcel candidates for “{address}”; confirm exactly one "
                "boundary before continuing."
            ),
            mapping=mapping,
            lookup_view=lookup_view,
            stage=True,
        )

    unique_ok = (
        mapping.disposition == "resolved"
        and _confidence_allows_continue(mapping)
        and terminal in {None, "PARCEL_DATA_UNAVAILABLE"}
    )
    if not unique_ok:
        return _needs_confirmation_result(
            address,
            message=(
                f"Unique high-confidence parcel resolve unavailable for “{address}” "
                f"(disposition={mapping.disposition}, confidence={mapping.confidence}, "
                f"accuracy_type={mapping.accuracy_type}, terminal={terminal})."
            ),
            mapping=mapping,
            lookup_view=lookup_view,
            stage=bool(candidates),
        )

    limitations = [
        "Mireye /lookup resolved a unique high-confidence location candidate first.",
        "location_resolved=true does not mean parcel_geometry_confirmed.",
        "Full investigation requires PARCEL_CONFIRMED "
        "(docs/ADVISOR_PARCEL_CONFIRMATION_GATE.md).",
    ]

    if _is_cper_demo_address(address):
        bound = _bind_cper_engineering_after_mireye(address)
        bound["lookup_result"] = lookup_result
        bound["lookup_view"] = lookup_view
        bound["mapping"] = mapping
        bound["limitations"] = limitations + list(bound.get("limitations") or [])
        return bound

    # Unique + polygon candidate(s) → stage confirmation; do not enter full investigation.
    if candidates and terminal is None:
        return _needs_confirmation_result(
            address,
            message=(
                f"Mireye found a unique parcel candidate for “{address}”. "
                "Confirm the boundary before a full investigation can start."
            ),
            mapping=mapping,
            lookup_view=lookup_view,
            stage=True,
        )

    # Location-only (parcel fabric unavailable): limited, not confirmed.
    return {
        "scenario_id": None,
        "label": mapping.normalized_address or address,
        "geometry": None,
        "listing_claims": [],
        "track": TRACK_LIMITED,
        "location_resolved": True,
        "parcel_geometry_confirmed": False,
        "geometry_source": None,
        "lookup_result": lookup_result,
        "lookup_view": lookup_view,
        "mapping": mapping,
        "limitations": limitations
        + [
            "Non-CPER parcel: build_cper_demo_policy, CPER listing claims, and F03 "
            "objects are blocked.",
        ],
        "limited_investigation": _limited_investigation_payload(
            address=address, mapping=mapping, lookup_view=lookup_view
        ),
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


def _call_live_mireye(
    record: dict[str, Any],
    address: str,
    geometry: dict[str, Any],
    *,
    lookup_result: Any | None = None,
) -> dict[str, Any]:
    from shapely.geometry import shape

    from rangematch.mireye_adapter import assert_no_credentials, collect_live_mireye_contexts

    feature = geometry["features"][0]
    centroid = shape(feature["geometry"]).centroid
    requested_point = {"lat": float(centroid.y), "lng": float(centroid.x)}
    geometry_hash = compute_geometry_hash(geometry)
    mode = "UNIT_TEST_HOOK" if _MIREYE_LOOKUP_FN is not None else "LIVE"
    if lookup_result is None:
        lookup_result = _invoke_mireye_lookup(address)
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
                "factor_id": step.get("factor_id"),
                "status": "PENDING",
            }
        )
    return rows


def _build_generic_agenda(record: dict[str, Any], resolved: dict[str, Any]) -> dict[str, Any]:
    geometry_id = str(
        resolved.get("geometry_id")
        or resolved.get("parcel_resolution_id")
        or f"CONFIRMED_{resolved.get('geometry_hash') or 'unknown'}"
    )
    profile = {
        "land_profile_id": f"ADVISOR_GENERIC_{record['run_id']}",
        "geometry_id": geometry_id,
        "geometry_hash": resolved.get("geometry_hash"),
        "geometry_reference": resolved.get("geometry_reference")
        or f"parcel_resolution:{resolved.get('parcel_resolution_id')}",
        "factors": {},
    }
    plan = build_investigation_plan(
        mode="DISCOVERY",
        intended_operation=None,
        land_profile=profile,
        planned_actions=[],
        include_mireye_context=True,
        plan_id=f"advisor_generic_{record['run_id'][-8:]}",
    )
    agenda = _agenda_from_plan(plan)
    live = record.get("mireye_live") or {}
    live_contexts = live.get("contexts") or {}
    for row in agenda:
        for context_type, step_id in MIREYE_STEP_BY_CONTEXT.items():
            if row["step_id"] == step_id and context_type in live_contexts:
                row["status"] = live_contexts[context_type].get("status") or row["status"]
    return {
        "plan": plan,
        "profile": profile,
        "agenda": agenda,
        "generic": True,
        "geometry_id": geometry_id,
    }


def _build_agenda(record: dict[str, Any], resolved: dict[str, Any]) -> dict[str, Any]:
    if resolved.get("track") == TRACK_GENERIC:
        return _build_generic_agenda(record, resolved)
    if resolved.get("track") != TRACK_CPER_COMPLETE or resolved.get("scenario_id") != CPER_SCENARIO_ID:
        raise AdvisorAgentStepError(
            "BUILD_AGENDA",
            f"Resolved “{resolved.get('label')}”. Full agenda, CPER listing claims, "
            "F03 objects, and build_cper_demo_policy are blocked outside the CPER "
            "engineering complete path.",
            investigation_outcome=OUTCOME_EVIDENCE_INVESTIGATION_INCOMPLETE,
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


def _run_generic_agenda(
    record: dict[str, Any],
    built: dict[str, Any],
    geometry: dict[str, Any],
    live: dict[str, Any],
    resolved: dict[str, Any],
) -> dict[str, Any]:
    geometry_id = str(
        built.get("geometry_id")
        or resolved.get("geometry_id")
        or f"CONFIRMED_{resolved.get('geometry_hash')}"
    )
    geometry_hash = str(resolved.get("geometry_hash") or compute_geometry_hash(geometry))
    geometry_reference = str(
        resolved.get("geometry_reference")
        or f"parcel_resolution:{resolved.get('parcel_resolution_id')}"
    )
    live_bodies = record.get("_mireye_context_payloads") or {}
    live_rows = live.get("contexts") or {}
    record["agenda"] = paint_generic_agenda(
        built["plan"],
        collected={"computed_factors": {}, "factor_errors": {}},
        live_contexts=live_rows,
    )

    def on_progress(update: dict[str, Any]) -> None:
        factor_id = str(update.get("factor_id") or "")
        status = str(update.get("status") or "RUNNING")
        note = update.get("note")
        record["collecting_factor"] = factor_id if status == "RUNNING" else None
        for row in record.get("agenda") or []:
            if row.get("factor_id") == factor_id:
                row["status"] = status
        if note and note not in (record.get("limitations") or []):
            record.setdefault("limitations", []).append(note)

    try:
        collected = collect_advisor_factors(
            geometry=geometry,
            geometry_id=geometry_id,
            geometry_hash=geometry_hash,
            geometry_reference=geometry_reference,
            mireye_contexts=live_bodies,
            collect_fn=_FACTOR_COLLECT_FN,
            on_progress=on_progress,
        )
    except Exception as exc:  # noqa: BLE001 — collect must not abort Generic Packet
        collected = {
            "computed_factors": {},
            "factor_errors": {"COLLECT": f"{type(exc).__name__}:{exc}"},
            "f03_inventory": None,
            "f03_status": "NOT_PROVIDED",
            "f03_remote_pilot": None,
            "progress_notes": [
                f"Factor collect failed ({type(exc).__name__}); continuing with geometry-only evidence"
            ],
        }
    record["collecting_factor"] = None
    from rangematch.tool_runners import to_unified_mireye_item

    mireye_items = []
    for context_type in MIREYE_CONTEXT_TYPES:
        payload = live_bodies.get(context_type)
        if live_rows.get(context_type, {}).get("status") == "SUCCEEDED" and payload:
            item = dict(payload)
            item.setdefault("context_type", context_type)
            mireye_items.append(to_unified_mireye_item(item))

    try:
        unified = assemble_generic_unified_output(
            geometry=geometry,
            geometry_id=geometry_id,
            geometry_hash=geometry_hash,
            geometry_reference=geometry_reference,
            run_id=str(record["run_id"]),
            computed_factors=collected.get("computed_factors") or {},
            mireye_items=mireye_items,
            address=str(resolved.get("label") or record.get("address") or ""),
        )
    except Exception as exc:  # noqa: BLE001 — last-chance geometry-only envelope
        unified = assemble_generic_unified_output(
            geometry=geometry,
            geometry_id=geometry_id,
            geometry_hash=geometry_hash,
            geometry_reference=geometry_reference,
            run_id=str(record["run_id"]),
            computed_factors={},
            mireye_items=[],
            address=str(resolved.get("label") or record.get("address") or ""),
        )
        record.setdefault("limitations", []).append(
            f"Unified Output assembled without live factors ({type(exc).__name__})"
        )
    if is_cper_engineering_fixture(unified):
        raise AdvisorAgentStepError(
            "RUN_AGENDA",
            "Generic collect assembled a CPER engineering fixture; refused",
        )
    record["agenda"] = paint_generic_agenda(
        built["plan"],
        collected=collected,
        live_contexts=live_rows,
    )
    errors = collected.get("factor_errors") or {}
    for note in collected.get("progress_notes") or []:
        if note not in (record.get("limitations") or []):
            record.setdefault("limitations", []).append(note)
    if errors:
        note = "live_factor_failures:" + ",".join(sorted(errors))
        if note not in (record.get("limitations") or []):
            record.setdefault("limitations", []).append(note)
    inventory = inventory_from_collection(collected)
    return {
        "unified_output": unified,
        "candidate_inventory": inventory,
        "remote_pilot": collected.get("f03_remote_pilot"),
        "f03_status": collected.get("f03_status"),
        "f03_inventory_ref": (
            f"memory://advisor/{record['run_id']}/f03_inventory" if inventory else None
        ),
        "generic": True,
    }


def _run_agenda(
    record: dict[str, Any],
    built: dict[str, Any],
    geometry: dict[str, Any],
    live: dict[str, Any],
    resolved: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if built.get("generic") or (resolved or {}).get("track") == TRACK_GENERIC:
        return _run_generic_agenda(
            record, built, geometry, live, resolved or {}
        )

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
        "generic": False,
    }


def _compare_claims(
    unified_output: dict[str, Any],
    listing_claims: list[dict[str, Any]],
    candidate_inventory: Any,
    remote_pilot: Any,
    *,
    generic: bool = False,
    run_id: str | None = None,
    f03_status: str | None = None,
    f03_inventory_ref: str | None = None,
    mireye_live: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if generic:
        if is_cper_engineering_fixture(unified_output):
            raise AdvisorAgentStepError(
                "COMPARE_CLAIMS",
                "Generic track refused CPER engineering fixture",
            )
        packet = project_generic_buyer_evidence_packet(
            unified_output,
            listing_claims=listing_claims or [],
            confirmation_status="CONFIRMED",
            unified_output_ref=f"memory://advisor/{run_id}/unified_output",
            candidate_inventory=candidate_inventory,
            remote_pilot=remote_pilot,
            f03_status=f03_status,
            f03_inventory_ref=f03_inventory_ref,
            f03_remote_pilot_ref=None,
            mireye_context_refs=_mireye_provenance(mireye_live),
        )
    else:
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


def _order_actions(
    packet: dict[str, Any],
    unified_output: dict[str, Any],
    *,
    mireye_live: dict[str, Any] | None = None,
) -> dict[str, Any]:
    brief = generate_deterministic_brief(
        packet, unified_output=unified_output, mireye_live=mireye_live
    )
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
    parcel_resolution_id: str | None = None,
    run_mode: str | None = None,
    demo_scenario_id: str | None = None,
    collection_mode: str | None = None,
) -> dict[str, Any]:
    mode = (run_mode or RUN_MODE_CUSTOM).strip().upper()
    if mode not in {RUN_MODE_CUSTOM, RUN_MODE_VERIFIED_DEMO}:
        raise ValueError(f"unsupported_run_mode:{mode}")

    collect = (collection_mode or COLLECTION_MODE_LEGACY).strip().upper()
    if collect not in {COLLECTION_MODE_LEGACY, COLLECTION_MODE_MIREYE_FIRST}:
        raise ValueError(f"unsupported_collection_mode:{collect}")
    # Verified Demo stays on the complete Nambe/LEGACY path until later phases.
    if mode == RUN_MODE_VERIFIED_DEMO and collect != COLLECTION_MODE_LEGACY:
        raise ValueError("verified_demo_requires_legacy_collection_mode")

    scenario = (demo_scenario_id or "").strip().upper() or None
    listing_claims: list[dict[str, Any]] = []
    resolved_fixture = fixture_id

    if mode == RUN_MODE_VERIFIED_DEMO:
        if scenario and scenario != DEMO_SCENARIO_NAMBE_CATTLE_V1:
            raise ValueError(f"unsupported_demo_scenario_id:{scenario}")
        scenario = DEMO_SCENARIO_NAMBE_CATTLE_V1
        # Isolated Demo run: fixed Nambe address, scenario claims only, never CPER fixture.
        address = NAMBE_DEMO_ADDRESS
        resolved_fixture = None
        listing_claims = nambe_demo_scenario_claims()
    else:
        scenario = None

    run_id = f"advisor_{uuid4().hex[:16]}"
    resolved_address = _resolve_requested_address(address, resolved_fixture)
    record: dict[str, Any] = {
        "status": "QUEUED",
        "run_id": run_id,
        "generated_at": _utc_now(),
        "address": resolved_address or address,
        "fixture_id": resolved_fixture,
        "run_mode": mode,
        "demo_scenario_id": scenario,
        "collection_mode": collect,
        "listing_claims": listing_claims,
        "parcel_resolution_id": (parcel_resolution_id or "").strip() or None,
        "geometry_hash": None,
        "steps": _empty_steps(collection_mode=collect),
        "agenda": [],
        "packet": None,
        "brief": None,
        "packet_hash": None,
        "parcel_geometry": None,
        "failed_step": None,
        "error": None,
        "investigation_outcome": None,
        "environmental_profile_outcome": None,
        "location_resolved": False,
        "parcel_geometry_confirmed": False,
        "track": None,
        "limited_investigation": None,
        "parcel_candidates": [],
        "llm_used": False,
        "limitations": [],
        "mireye_live": None,
        "mireye_environmental_profile": None,
        "environmental_gap_plan": None,
        "supplement_execution": None,
        "additional_property_context_collection": None,
        "combined_environmental_evidence_packet": None,
        "natural_cattle_profile": None,
        "natural_foundation_interpretation": None,
        "f06_derivation": None,
        "collecting_factor": None,
        "buyer_explanation": None,
        "operating_profile": None,
        "place_normalization": None,
        "deal_context": None,
        "operating_conclusion": None,
        "initial_operating_conclusion": None,
        "revised_operating_conclusion": None,
        "conclusion_change": None,
        "chat_turns": [],
        "chat_suggestions": None,
    }
    if mode == RUN_MODE_VERIFIED_DEMO:
        record["limitations"].append(
            "Verified Demo Property: Nambe, Colorado. "
            "This report uses the Nambe parcel, not a previous custom location input. "
            "Demo scenario claims are labeled DEMO_SCENARIO_CLAIM."
        )
    if collect == COLLECTION_MODE_MIREYE_FIRST:
        record["limitations"].append(
            "collection_mode=MIREYE_FIRST: Profile → Gap Detector → planned "
            "F01–F05/F08 supplements → Combined Evidence Packet → Natural Cattle Profile "
            "→ Deal Context → natural-foundation interpretation (LLM or fallback). "
            "The validated interpretation feeds the two-page Foundation report. "
            "F07 runs only as a fail-soft Appendix context collector and cannot enter "
            "the Natural Cattle Profile, LLM workbench, or conclusion."
        )
    _RUNS[run_id] = record
    return _public_view(record)


def _skip_remaining_steps(record: dict[str, Any], *, after_step: str) -> None:
    seen = False
    now = _utc_now()
    for row in record["steps"]:
        if row["step_id"] == after_step:
            seen = True
            continue
        if not seen:
            continue
        if row["status"] == "PENDING":
            row["status"] = "SKIPPED"
            row["completed_at"] = now


def _apply_resolve_flags(record: dict[str, Any], resolved: dict[str, Any]) -> None:
    record["track"] = resolved.get("track")
    record["location_resolved"] = bool(resolved.get("location_resolved"))
    record["parcel_geometry_confirmed"] = bool(resolved.get("parcel_geometry_confirmed"))
    if resolved.get("parcel_resolution_id"):
        record["parcel_resolution_id"] = resolved.get("parcel_resolution_id")
    if resolved.get("geometry_hash"):
        record["geometry_hash"] = resolved.get("geometry_hash")
    if resolved.get("parcel_candidates") is not None:
        record["parcel_candidates"] = list(resolved.get("parcel_candidates") or [])
    elif resolved.get("mapping") is not None:
        record["parcel_candidates"] = _candidate_public_rows(resolved.get("mapping"))
    else:
        record["parcel_candidates"] = []
    for note in resolved.get("limitations") or []:
        if note not in (record.get("limitations") or []):
            record.setdefault("limitations", []).append(note)


def _centroid_lat_lng(geometry: dict[str, Any]) -> tuple[float, float]:
    from shapely.geometry import shape

    feature = geometry["features"][0]
    centroid = shape(feature["geometry"]).centroid
    return float(centroid.y), float(centroid.x)


def _mireye_first_request_fn(*, endpoint: str, body: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if _MIREYE_REQUEST_FN is not None:
        return _MIREYE_REQUEST_FN(endpoint=endpoint, body=body)
    from rangematch.mireye_adapter import live_mireye_request

    return live_mireye_request(endpoint=endpoint, body=body)


def _execute_mireye_first_path(
    record: dict[str, Any],
    resolved: dict[str, Any],
    *,
    fail_step: str | None,
) -> dict[str, Any]:
    """MIREYE_FIRST: natural evidence plus an isolated fail-soft F07 Appendix collect.

    No fixture substitution. F07 is never part of environmental gap filling or reasoning.
    """
    from rangematch.environmental_evidence_packet import (
        build_combined_environmental_evidence_packet,
    )
    from rangematch.environmental_gap_detector import detect_environmental_gaps
    from rangematch.environmental_supplement_runner import (
        execute_supplement_plan,
        planned_factor_jobs,
    )
    from rangematch.mireye_environmental_profile import (
        project_mireye_environmental_profile,
    )
    from rangematch.mireye_first_collection import (
        classify_environmental_profile_outcome,
        derive_confirmed_f06,
        fetch_mireye_environment_fields,
    )

    geometry = resolved["geometry"]
    geometry_hash = str(resolved.get("geometry_hash") or compute_geometry_hash(geometry))
    parcel_resolution_id = str(
        resolved.get("parcel_resolution_id") or record.get("parcel_resolution_id") or ""
    )
    if not parcel_resolution_id:
        raise AdvisorAgentStepError(
            "DERIVE_F06",
            "MIREYE_FIRST collection requires a confirmed parcel_resolution_id",
            investigation_outcome=OUTCOME_INVESTIGATION_COULD_NOT_COMPLETE,
        )

    lat, lng = _centroid_lat_lng(geometry)

    f06 = _run_step(
        record,
        "DERIVE_F06",
        lambda: derive_confirmed_f06(
            geometry,
            geometry_hash=geometry_hash,
            geometry_id=resolved.get("geometry_id"),
            geometry_reference=resolved.get("geometry_reference"),
        ),
        fail_step=fail_step,
    )

    fetch_result = _run_step(
        record,
        "FETCH_MIREYE_ENVIRONMENT",
        lambda: fetch_mireye_environment_fields(
            lat=lat,
            lng=lng,
            confirmed_geometry_hash=geometry_hash,
            request_fn=_mireye_first_request_fn,
        ),
        fail_step=fail_step,
    )

    profile = _run_step(
        record,
        "BUILD_MIREYE_ENVIRONMENTAL_PROFILE",
        lambda: project_mireye_environmental_profile(
            run_id=str(record["run_id"]),
            parcel_ref={
                "parcel_resolution_id": parcel_resolution_id,
                "geometry_hash": geometry_hash,
                "confirmed": True,
            },
            field_values=fetch_result.get("field_values") or {},
            fetched_at=fetch_result.get("raw_fetched_at"),
            unavailable_fields=fetch_result.get("unavailable_fields") or [],
            validate=True,
        ),
        fail_step=fail_step,
    )
    env_outcome = classify_environmental_profile_outcome(profile)

    gap_plan = _run_step(
        record,
        "DETECT_ENVIRONMENTAL_GAPS",
        lambda: detect_environmental_gaps(
            profile,
            f06_geometry_hash=geometry_hash,
            validate=True,
        ),
        fail_step=fail_step,
    )

    def _run_supplements() -> dict[str, Any]:
        planned = planned_factor_jobs(gap_plan)
        runners = None
        if _SUPPLEMENT_RUNNERS_FN is not None:
            runners = _SUPPLEMENT_RUNNERS_FN(
                geometry=geometry,
                geometry_id=str(resolved.get("geometry_id") or parcel_resolution_id),
                geometry_hash=geometry_hash,
                geometry_reference=resolved.get("geometry_reference"),
                planned_factor_ids=planned,
            )
        return execute_supplement_plan(
            gap_plan,
            geometry=geometry,
            geometry_id=str(resolved.get("geometry_id") or parcel_resolution_id),
            geometry_hash=geometry_hash,
            geometry_reference=resolved.get("geometry_reference"),
            runners=runners,
        )

    supplement_execution = _run_step(
        record,
        "RUN_ENVIRONMENTAL_SUPPLEMENTS",
        _run_supplements,
        fail_step=fail_step,
    )

    from rangematch.advisor_property_context_collector import (
        collect_additional_property_context,
    )

    property_context_collection = _run_step(
        record,
        "COLLECT_ADDITIONAL_PROPERTY_CONTEXT",
        lambda: collect_additional_property_context(
            geometry=geometry,
            geometry_id=str(resolved.get("geometry_id") or parcel_resolution_id),
            geometry_hash=geometry_hash,
            geometry_reference=str(resolved.get("geometry_reference") or f"geometry:{geometry_hash}"),
            runner=_PROPERTY_CONTEXT_RUNNER_FN,
        ),
        fail_step=fail_step,
    )

    combined_packet = _run_step(
        record,
        "MERGE_ENVIRONMENTAL_EVIDENCE",
        lambda: build_combined_environmental_evidence_packet(
            mireye_profile=profile,
            gap_plan=gap_plan,
            supplement_execution=supplement_execution,
            f06=f06,
        ),
        fail_step=fail_step,
    )

    from rangematch.natural_cattle_profile import project_natural_cattle_profile

    natural_profile = _run_step(
        record,
        "PROJECT_NATURAL_CATTLE_PROFILE",
        lambda: project_natural_cattle_profile(combined_packet, validate=True),
        fail_step=fail_step,
    )

    from rangematch.advisor_deal_context import create_deal_context
    from rangematch.advisor_natural_interpretation import (
        generate_natural_foundation_interpretation,
    )
    from rangematch.llm_provider import configured_provider_name

    deal_context = _run_step(
        record,
        "CREATE_DEAL_CONTEXT",
        lambda: create_deal_context(
            run_id=str(record["run_id"]),
            parcel_resolution_id=parcel_resolution_id,
            geometry_hash=geometry_hash,
            seller_claims=list(record.get("listing_claims") or []),
            run_mode=str(record.get("run_mode") or RUN_MODE_CUSTOM),
            demo_scenario_id=record.get("demo_scenario_id"),
        ),
        fail_step=fail_step,
    )

    interpretation = _run_step(
        record,
        "GENERATE_NATURAL_FOUNDATION_INTERPRETATION",
        lambda: generate_natural_foundation_interpretation(
            natural_cattle_profile=natural_profile,
            deal_context=deal_context,
            provider_name=configured_provider_name(),
            combined_environmental_evidence_packet=combined_packet,
        ),
        fail_step=fail_step,
    )

    record["f06_derivation"] = {
        "role": f06["role"],
        "spatial_semantics": f06["spatial_semantics"],
        "geometry_hash": f06["geometry_hash"],
        "summary": f06["summary"],
        "factor_id": f06["factor_id"],
    }
    record["_f06_factor"] = f06.get("factor")
    record["mireye_environmental_profile"] = profile
    record["environmental_profile_outcome"] = env_outcome
    record["environmental_gap_plan"] = gap_plan
    record["supplement_execution"] = {
        "plan_hash": supplement_execution.get("plan_hash"),
        "planned_tool_ids": list(supplement_execution.get("planned_tool_ids") or []),
        "attempted_tool_ids": list(supplement_execution.get("attempted_tool_ids") or []),
        "succeeded_tool_ids": list(supplement_execution.get("succeeded_tool_ids") or []),
        "failed_tool_ids": list(supplement_execution.get("failed_tool_ids") or []),
        "skipped_tool_ids": list(supplement_execution.get("skipped_tool_ids") or []),
        "capabilities_filled": list(
            supplement_execution.get("capabilities_filled") or []
        ),
        "capabilities_still_missing": list(
            supplement_execution.get("capabilities_still_missing") or []
        ),
        "attempts": list(supplement_execution.get("attempts") or []),
        "progress_notes": list(supplement_execution.get("progress_notes") or []),
        # Keep full factors for merge/debug; buyer LLM still not fed.
        "computed_factors": dict(supplement_execution.get("computed_factors") or {}),
        "factor_errors": dict(supplement_execution.get("factor_errors") or {}),
    }
    record["additional_property_context_collection"] = property_context_collection
    record["combined_environmental_evidence_packet"] = combined_packet
    record["natural_cattle_profile"] = natural_profile
    record["deal_context"] = deal_context
    record["natural_foundation_interpretation"] = interpretation
    # Compatibility alias for answer/chat surfaces that still read operating_conclusion.
    record["operating_conclusion"] = None
    record["mireye_live"] = {
        "mode": "UNIT_TEST_HOOK" if _MIREYE_REQUEST_FN is not None else "LIVE",
        "allow_network": _MIREYE_REQUEST_FN is None,
        "collection_mode": COLLECTION_MODE_MIREYE_FIRST,
        "environmental_fetch": {
            "ok": bool(fetch_result.get("ok")),
            "transport": fetch_result.get("transport"),
            "unavailable_field_count": len(fetch_result.get("unavailable_fields") or []),
            "error": fetch_result.get("error"),
            "requested_field_ids": list(
                (fetch_result.get("request_body") or {}).get("fields") or []
            ),
        },
        "canonical_for_parcel_facts": "per_field",
        "requested_point": {"lat": lat, "lng": lng},
        "supplement_plan_hash": gap_plan.get("plan_hash"),
        "supplements_succeeded": list(
            supplement_execution.get("succeeded_tool_ids") or []
        ),
        "supplements_failed": list(supplement_execution.get("failed_tool_ids") or []),
    }
    agenda = [
        {
            "step_id": "S_F06_ALWAYS_ON",
            "label": "F06 confirmed geometry",
            "tool_id": "rangematch.f06",
            "factor_id": "F06_PARCEL_CONFIGURATION",
            "status": "SUCCEEDED",
        },
        {
            "step_id": "S_MIREYE_ENVIRONMENT_FETCH",
            "label": "Mireye cattle-environment fetch",
            "tool_id": "mireye.fetch_environment",
            "factor_id": None,
            "status": "SUCCEEDED" if fetch_result.get("ok") else "PARTIAL",
        },
        {
            "step_id": "S_MIREYE_ENVIRONMENTAL_PROFILE",
            "label": "Mireye Environmental Profile",
            "tool_id": "rangematch.mireye_environmental_profile",
            "factor_id": None,
            "status": "SUCCEEDED",
        },
        {
            "step_id": "S_ENVIRONMENTAL_GAP_DETECTOR",
            "label": "Environmental Gap Detector",
            "tool_id": "rangematch.environmental_gap_detector",
            "factor_id": None,
            "status": "SUCCEEDED",
        },
    ]
    for tool_id in supplement_execution.get("planned_tool_ids") or []:
        if tool_id in (supplement_execution.get("succeeded_tool_ids") or []):
            status = "SUCCEEDED"
        elif tool_id in (supplement_execution.get("failed_tool_ids") or []):
            status = "PARTIAL"
        else:
            status = "SKIPPED"
        factor_id = {
            "F01_3DEP": "F01_TOPOGRAPHY",
            "F02_RAP": "F02_HERBACEOUS_RESOURCE",
            "F03_NHD": "F03_LIVESTOCK_WATER",
            "F04_SDA": "F04_SOIL_WETNESS_ECOLOGICAL_SITE",
            "F05_NOAA": "F05_CLIMATE_DROUGHT_EXPOSURE",
            "F08_RAP_WOODY": "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE",
        }.get(str(tool_id))
        agenda.append(
            {
                "step_id": f"S_SUPPLEMENT_{tool_id}",
                "label": f"Supplement {tool_id}",
                "tool_id": f"rangematch.supplement.{tool_id}",
                "factor_id": factor_id,
                "status": status,
            }
        )
    agenda.append(
        {
            "step_id": "S_COMBINED_ENVIRONMENTAL_EVIDENCE",
            "label": "Combined Environmental Evidence Packet",
            "tool_id": "rangematch.environmental_evidence_packet",
            "factor_id": None,
            "status": "SUCCEEDED",
        }
    )
    agenda.append(
        {
            "step_id": "S_NATURAL_CATTLE_PROFILE",
            "label": "Natural Cattle Profile",
            "tool_id": "rangematch.natural_cattle_profile",
            "factor_id": None,
            "status": "SUCCEEDED",
        }
    )
    agenda.append(
        {
            "step_id": "S_DEAL_CONTEXT",
            "label": "Deal Context",
            "tool_id": "rangematch.deal_context",
            "factor_id": None,
            "status": "SUCCEEDED",
        }
    )
    agenda.append(
        {
            "step_id": "S_NATURAL_FOUNDATION_INTERPRETATION",
            "label": "Natural foundation interpretation",
            "tool_id": "rangematch.natural_foundation_interpretation",
            "factor_id": None,
            "status": "SUCCEEDED",
        }
    )
    record["agenda"] = agenda
    # Evidence + Profile + interpretation complete; LEGACY buyer Packet/PDF remain off.
    record["investigation_outcome"] = OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED
    record["packet"] = None
    record["brief"] = None
    record["packet_hash"] = None
    record["operating_profile"] = None
    record["buyer_explanation"] = None
    record["parcel_geometry"] = geometry
    record["geometry_hash"] = geometry_hash
    record["status"] = "SUCCEEDED"
    record["error"] = None
    record["failed_step"] = None
    if not fetch_result.get("ok"):
        note = (
            "Mireye environmental fetch failed or returned no fields; "
            "Profile preserves SOURCE_UNAVAILABLE / MISSING honestly "
            f"(error={fetch_result.get('error') or (fetch_result.get('transport') or {}).get('error_class')}). "
            "No fixture substitution."
        )
        if note not in (record.get("limitations") or []):
            record.setdefault("limitations", []).append(note)
    failed_tools = list(supplement_execution.get("failed_tool_ids") or [])
    if failed_tools:
        note = (
            "Planned supplement adapter(s) failed and were retained as "
            f"SOURCE_UNAVAILABLE ({', '.join(failed_tools)}); no fixture substitution."
        )
        if note not in (record.get("limitations") or []):
            record.setdefault("limitations", []).append(note)
    return _public_view(record)


def execute_advisor_run(run_id: str, *, fail_step: str | None = None) -> dict[str, Any]:
    record = _RUNS.get(run_id)
    if record is None:
        raise KeyError(run_id)
    record["status"] = "RUNNING"
    address = str(record.get("address") or "")
    parcel_resolution_id = record.get("parcel_resolution_id")
    try:
        accepted = _run_step(
            record,
            "ACCEPT_PLACE",
            lambda: _accept_place(address, record),
            fail_step=fail_step,
        )
        resolved = _run_step(
            record,
            "RESOLVE_PARCEL",
            lambda: _resolve_parcel(
                accepted, parcel_resolution_id=parcel_resolution_id
            ),
            fail_step=fail_step,
        )
        _apply_resolve_flags(record, resolved)

        # Claim isolation: Verified Demo uses only labeled scenario claims.
        # Custom GENERIC never inherits Demo/CPER listing claims.
        if record.get("run_mode") == RUN_MODE_VERIFIED_DEMO:
            resolved["listing_claims"] = list(
                record.get("listing_claims") or nambe_demo_scenario_claims()
            )
        elif resolved.get("track") == TRACK_GENERIC:
            resolved["listing_claims"] = []

        if resolved.get("track") in {TRACK_LIMITED, TRACK_NEEDS_CONFIRM}:
            if resolved.get("track") == TRACK_NEEDS_CONFIRM and resolved.get("lookup_view"):
                record["mireye_live"] = {
                    "mode": "UNIT_TEST_HOOK" if _MIREYE_LOOKUP_FN is not None else "LIVE",
                    "allow_network": True,
                    "lookup": resolved.get("lookup_view"),
                    "contexts": {},
                    "canonical_for_parcel_facts": False,
                }
            record.update(
                {
                    "status": "SUCCEEDED",
                    "investigation_outcome": (
                        OUTCOME_PARCEL_NEEDS_CONFIRMATION
                        if resolved.get("track") == TRACK_NEEDS_CONFIRM
                        else OUTCOME_EVIDENCE_INVESTIGATION_INCOMPLETE
                    ),
                    "error": resolved.get("message"),
                    "failed_step": None,
                    "limited_investigation": resolved.get("limited_investigation"),
                    "packet": None,
                    "brief": None,
                    "packet_hash": None,
                    "parcel_geometry": resolved.get("geometry")
                    if resolved.get("parcel_geometry_confirmed")
                    else None,
                }
            )
            _skip_remaining_steps(record, after_step="RESOLVE_PARCEL")
            return _public_view(record)

        if record.get("collection_mode") == COLLECTION_MODE_MIREYE_FIRST:
            return _execute_mireye_first_path(
                record, resolved, fail_step=fail_step
            )

        live = _run_step(
            record,
            "CALL_MIREYE",
            lambda: _call_live_mireye(
                record,
                accepted,
                resolved["geometry"],
                lookup_result=resolved.get("lookup_result"),
            ),
            fail_step=fail_step,
        )
        built = _run_step(
            record, "BUILD_AGENDA", lambda: _build_agenda(record, resolved), fail_step=fail_step
        )
        record["agenda"] = list(built.get("agenda") or [])
        gathered = _run_step(
            record,
            "RUN_AGENDA",
            lambda: _run_agenda(
                record, built, resolved["geometry"], live, resolved
            ),
            fail_step=fail_step,
        )
        packet = _run_step(
            record,
            "COMPARE_CLAIMS",
            lambda: _compare_claims(
                gathered["unified_output"],
                resolved.get("listing_claims") or [],
                gathered.get("candidate_inventory"),
                gathered.get("remote_pilot"),
                generic=bool(gathered.get("generic")),
                run_id=record["run_id"],
                f03_status=gathered.get("f03_status"),
                f03_inventory_ref=gathered.get("f03_inventory_ref"),
                mireye_live=live,
            ),
            fail_step=fail_step,
        )
        brief = _run_step(
            record,
            "ORDER_ACTIONS",
            lambda: _order_actions(
                packet, gathered["unified_output"], mireye_live=live
            ),
            fail_step=fail_step,
        )
        _run_step(
            record,
            "VALIDATE_BRIEF",
            lambda: _validate_brief(brief, packet, gathered["unified_output"]),
            fail_step=fail_step,
        )
        profile = None
        if gathered.get("generic"):
            try:
                from rangematch.livestock_operating_profile import (
                    OperatingProfileError,
                    project_livestock_operating_profile,
                )

                profile = project_livestock_operating_profile(
                    packet, gathered["unified_output"], species_lens="CATTLE"
                )
            except OperatingProfileError as exc:
                record.setdefault("limitations", []).append(
                    f"Operating Profile limited: {exc.code}"
                )
        record.update(
            {
                # Keep the public run open until Deal Context, conclusion, chat
                # suggestions, and the optional explanation have all settled.
                # Publishing SUCCEEDED here let the UI stop polling before the
                # buyer-facing result existed.
                "status": "RUNNING",
                "investigation_outcome": OUTCOME_EVIDENCE_INVESTIGATION_COMPLETED,
                "packet": packet,
                "brief": brief,
                "packet_hash": packet_hash(packet),
                "parcel_geometry": resolved["geometry"],
                "operating_profile": profile,
                "_unified_output": gathered["unified_output"],
                "_candidate_inventory": gathered.get("candidate_inventory"),
            }
        )
        if profile is not None and record.get("geometry_hash"):
            try:
                from rangematch.advisor_deal_context import create_deal_context

                seller_claims = list(resolved.get("listing_claims") or [])
                if not seller_claims and isinstance(packet.get("listing_claims"), list):
                    seller_claims = list(packet.get("listing_claims") or [])
                record["deal_context"] = create_deal_context(
                    run_id=record["run_id"],
                    parcel_resolution_id=record.get("parcel_resolution_id"),
                    geometry_hash=str(record["geometry_hash"]),
                    seller_claims=seller_claims,
                    run_mode=str(record.get("run_mode") or RUN_MODE_CUSTOM),
                    demo_scenario_id=record.get("demo_scenario_id"),
                )
            except Exception as exc:  # noqa: BLE001 — context must not fail the run
                record.setdefault("limitations", []).append(
                    f"Deal Context unavailable: {getattr(exc, 'code', type(exc).__name__)}"
                )
        if record.get("deal_context") and profile is not None:
            try:
                from rangematch.advisor_conclusion import generate_operating_conclusion
                from rangematch.llm_provider import configured_provider_name

                record["operating_conclusion"] = generate_operating_conclusion(
                    run_id=record["run_id"],
                    packet=packet,
                    operating_profile=profile,
                    deal_context=record["deal_context"],
                    provider_name=configured_provider_name(),
                )
                record["initial_operating_conclusion"] = dict(record["operating_conclusion"])
                record["revised_operating_conclusion"] = None
                record["conclusion_change"] = None
                from rangematch.advisor_chat import suggested_chat_questions

                record["chat_suggestions"] = suggested_chat_questions()
            except Exception as exc:  # noqa: BLE001 — conclusion must not fail the run
                record.setdefault("limitations", []).append(
                    f"Operating Conclusion unavailable: {type(exc).__name__}"
                )
        if gathered.get("generic"):
            from rangematch.llm_provider import configured_provider_name

            try:
                attach_advisor_buyer_explanation(
                    run_id, provider_name=configured_provider_name()
                )
            except Exception as exc:  # noqa: BLE001 — explanation must not fail the run
                record.setdefault("limitations", []).append(
                    f"Buyer explanation unavailable: {type(exc).__name__}"
                )
        # This is the single success publication point for a completed
        # investigation. Everything the successful UI expects is final now.
        record["status"] = "SUCCEEDED"
    except AdvisorAgentStepError as exc:
        details = dict(exc.details or {})
        outcome = (
            exc.investigation_outcome
            or OUTCOME_INVESTIGATION_COULD_NOT_COMPLETE
        )
        waiting_for_confirm = outcome == OUTCOME_PARCEL_NEEDS_CONFIRMATION
        _mark(
            record["steps"],
            exc.step_id,
            "NEEDS_CONFIRMATION" if waiting_for_confirm else "FAILED",
            now=_utc_now(),
        )
        if waiting_for_confirm:
            _skip_remaining_steps(record, after_step=exc.step_id)
        if "location_resolved" in details:
            record["location_resolved"] = bool(details.get("location_resolved"))
        if "parcel_geometry_confirmed" in details:
            record["parcel_geometry_confirmed"] = bool(
                details.get("parcel_geometry_confirmed")
            )
        if details.get("parcel_resolution_id"):
            record["parcel_resolution_id"] = details.get("parcel_resolution_id")
        if details.get("parcel_candidates") is not None:
            record["parcel_candidates"] = list(details.get("parcel_candidates") or [])
        if details.get("mireye_live_lookup") is not None:
            record["mireye_live"] = {
                "mode": "UNIT_TEST_HOOK" if _MIREYE_LOOKUP_FN is not None else "LIVE",
                "allow_network": True,
                "lookup": details["mireye_live_lookup"],
                "contexts": {},
                "canonical_for_parcel_facts": False,
            }
        record.update(
            {
                "status": "SUCCEEDED" if waiting_for_confirm else "FAILED",
                "failed_step": None if waiting_for_confirm else exc.step_id,
                "error": exc.message,
                "investigation_outcome": outcome,
                "packet": None,
                "brief": None,
                "packet_hash": None,
                "parcel_geometry": None,
                "limited_investigation": None,
            }
        )
    return _public_view(record)


def run_cper_advisor_agent(
    *,
    address: str | None = None,
    fixture_id: str = "CPER",
    parcel_resolution_id: str | None = None,
    fail_step: str | None = None,
    run_mode: str | None = None,
    demo_scenario_id: str | None = None,
    collection_mode: str | None = None,
) -> dict[str, Any]:
    """Synchronous helper for tests. Demo HTTP path enqueues, then executes."""
    queued = enqueue_advisor_run(
        address=address,
        fixture_id=fixture_id,
        parcel_resolution_id=parcel_resolution_id,
        run_mode=run_mode,
        demo_scenario_id=demo_scenario_id,
        collection_mode=collection_mode,
    )
    return execute_advisor_run(queued["run_id"], fail_step=fail_step)


def attach_advisor_buyer_explanation(
    run_id: str,
    *,
    provider_name: str = "FIXTURE",
) -> dict[str, Any]:
    """Optional LLM explanation. Live miss never becomes a silent fixture."""
    from rangematch.advisor_insight import project_advisor_llm_workbench
    from rangematch.advisor_llm import generate_advisor_buyer_explanation

    record = _RUNS.get(run_id)
    if record is None:
        raise KeyError(run_id)
    # During execute_advisor_run this is the final internal enrichment step,
    # while the run deliberately remains RUNNING so clients keep polling.
    # External calls still reach this only after a completed public run.
    if record.get("status") not in {"RUNNING", "SUCCEEDED"} or not record.get("packet"):
        raise AdvisorAgentStepError(
            "EXPLAIN",
            "Buyer explanation requires a succeeded Advisor run with a Packet",
        )
    workbench = project_advisor_llm_workbench(
        record["packet"],
        mireye_live=record.get("mireye_live"),
        unified_output=record.get("_unified_output"),
        operating_profile=record.get("operating_profile"),
    )
    record["_llm_workbench"] = workbench
    report = generate_advisor_buyer_explanation(
        record["packet"],
        mireye_live=record.get("mireye_live"),
        unified_output=record.get("_unified_output"),
        operating_profile=record.get("operating_profile"),
        provider_name=provider_name,
    )
    record["_validated_insights"] = list(report.get("insights") or [])
    record["buyer_explanation"] = report
    return _public_view(record)


def get_advisor_operating_conclusion(run_id: str) -> dict[str, Any]:
    record = _RUNS.get(run_id)
    if record is None:
        raise KeyError(run_id)
    conclusion = record.get("operating_conclusion")
    if not isinstance(conclusion, dict):
        raise AdvisorAgentStepError(
            "CONCLUSION",
            "Operating Conclusion is not available for this run",
        )
    return dict(conclusion)


def submit_advisor_answer(
    run_id: str,
    *,
    question_id: str,
    answer: Any,
    expected_context_version: int,
    expected_geometry_hash: str,
    provider_name: str | None = None,
) -> dict[str, Any]:
    """Accept one catalog answer, bump Deal Context, and revise the conclusion."""
    from rangematch.advisor_answer import (
        AdvisorAnswerError,
        normalize_answer_value,
        require_question_binding,
    )
    from rangematch.advisor_conclusion import (
        build_what_changed,
        generate_operating_conclusion,
    )
    from rangematch.advisor_deal_context import DealContextError, update_deal_context
    from rangematch.llm_provider import configured_provider_name

    record = _RUNS.get(run_id)
    if record is None:
        raise KeyError(run_id)
    if record.get("status") != "SUCCEEDED":
        raise AdvisorAnswerError(
            "ANSWER_RUN_NOT_READY",
            "answers require a succeeded Advisor run",
        )

    # Mireye-first natural-foundation path: bind the answer to the validated
    # interpretation, bump the same Deal Context, and regenerate from the
    # unchanged Natural Cattle Profile. Legacy operating conclusions continue
    # through the existing branch below.
    if record.get("collection_mode") == COLLECTION_MODE_MIREYE_FIRST:
        from rangematch.advisor_natural_interpretation import (
            generate_natural_foundation_interpretation,
        )

        natural_profile = record.get("natural_cattle_profile")
        deal_context = record.get("deal_context")
        before = record.get("natural_foundation_interpretation")
        if not isinstance(natural_profile, dict) or not isinstance(deal_context, dict):
            raise AdvisorAnswerError(
                "ANSWER_RUN_INCOMPLETE",
                "Natural Cattle Profile and Deal Context are required before answering",
            )
        require_question_binding(
            conclusion=before if isinstance(before, dict) else None,
            question_id=question_id,
            expected_context_version=expected_context_version,
            expected_geometry_hash=expected_geometry_hash,
            deal_context=deal_context,
            run_geometry_hash=record.get("geometry_hash"),
        )
        field, value = normalize_answer_value(question_id, answer)
        profile_hash_before = natural_profile.get("profile_hash")
        try:
            updated_context = update_deal_context(
                run_id=run_id,
                expected_geometry_hash=expected_geometry_hash,
                expected_context_version=expected_context_version,
                append_answer={"field": field, "value": value},
                operation_type=value if field == "operation_type" else None,
            )
        except DealContextError as exc:
            raise AdvisorAnswerError(exc.code, exc.message) from exc
        if (record.get("natural_cattle_profile") or {}).get("profile_hash") != profile_hash_before:
            raise AdvisorAnswerError(
                "ANSWER_PROFILE_MUTATION_FORBIDDEN",
                "Natural Cattle Profile must not change when answering",
            )
        provider = provider_name or configured_provider_name()
        revised = generate_natural_foundation_interpretation(
            natural_cattle_profile=natural_profile,
            deal_context=updated_context,
            provider_name=provider,
            previous_interpretation=before if isinstance(before, dict) else None,
            combined_environmental_evidence_packet=record.get(
                "combined_environmental_evidence_packet"
            ),
        )
        if int(revised.get("deal_context_version") or 0) != int(
            updated_context.get("context_version") or 0
        ):
            raise AdvisorAnswerError(
                "ANSWER_REVISED_VERSION_MISMATCH",
                "revised interpretation must cite the bumped Deal Context version",
            )
        changed = any(
            revised.get(key) != (before or {}).get(key)
            for key in (
                "advisor_view",
                "integrated_natural_reading",
                "intended_use_interpretation",
                "refinement_request",
            )
        )
        record["deal_context"] = updated_context
        record["initial_natural_foundation_interpretation"] = copy.deepcopy(before)
        record["revised_natural_foundation_interpretation"] = revised
        record["natural_foundation_interpretation"] = revised
        record["conclusion_change"] = {
            "change_status": "CONCLUSION_CHANGED" if changed else "UNCHANGED_BUT_NARROWED",
            "summary": (
                "The natural-foundation interpretation was updated for the cattle use you supplied."
                if changed
                else "The overall view remains the same, but the intended-use interpretation is now narrower."
            ),
            "user_answer": {
                "question_id": str(question_id),
                "field": field,
                "value": value,
                "provenance": "USER_SUPPLIED_UNVERIFIED",
            },
            "before_interpretation_id": (before or {}).get("interpretation_id"),
            "after_interpretation_id": revised.get("interpretation_id"),
        }
        return _public_view(record)

    packet = record.get("packet")
    profile = record.get("operating_profile")
    deal_context = record.get("deal_context")
    if not isinstance(packet, dict) or not isinstance(deal_context, dict):
        raise AdvisorAnswerError(
            "ANSWER_RUN_INCOMPLETE",
            "packet and Deal Context are required before answering",
        )
    if profile is None:
        raise AdvisorAnswerError(
            "ANSWER_PROFILE_MISSING",
            "operating profile is required before answering",
        )

    before = record.get("operating_conclusion")
    require_question_binding(
        conclusion=before if isinstance(before, dict) else None,
        question_id=question_id,
        expected_context_version=expected_context_version,
        expected_geometry_hash=expected_geometry_hash,
        deal_context=deal_context,
        run_geometry_hash=record.get("geometry_hash"),
    )
    field, value = normalize_answer_value(question_id, answer)

    packet_hash_before = record.get("packet_hash")
    try:
        updated_context = update_deal_context(
            run_id=run_id,
            expected_geometry_hash=expected_geometry_hash,
            expected_context_version=expected_context_version,
            append_answer={"field": field, "value": value},
            operation_type=value if field == "operation_type" else None,
        )
    except DealContextError as exc:
        raise AdvisorAnswerError(exc.code, exc.message) from exc

    record["deal_context"] = updated_context
    if record.get("packet_hash") != packet_hash_before:
        raise AdvisorAnswerError(
            "ANSWER_PACKET_MUTATION_FORBIDDEN",
            "Physical Packet must not change when answering",
        )

    user_answer_public = {
        "question_id": str(question_id),
        "field": field,
        "value": value,
        "provenance": "USER_SUPPLIED_UNVERIFIED",
    }
    provider = provider_name or configured_provider_name()
    revised = generate_operating_conclusion(
        run_id=run_id,
        packet=packet,
        operating_profile=profile,
        deal_context=updated_context,
        provider_name=provider,
        previous_conclusion=before if isinstance(before, dict) else None,
    )
    if int(revised.get("deal_context_version") or 0) != int(
        updated_context.get("context_version") or 0
    ):
        # Fail closed on version drift between generator and context.
        raise AdvisorAnswerError(
            "ANSWER_REVISED_VERSION_MISMATCH",
            "revised conclusion must cite the bumped Deal Context version",
        )

    change = build_what_changed(
        before if isinstance(before, dict) else {},
        revised,
        user_answer=user_answer_public,
    )

    if not isinstance(record.get("initial_operating_conclusion"), dict) and isinstance(
        before, dict
    ):
        record["initial_operating_conclusion"] = dict(before)
    record["revised_operating_conclusion"] = revised
    record["operating_conclusion"] = revised
    record["conclusion_change"] = change

    try:
        from rangematch.advisor_deal_context import set_current_conclusion_id

        record["deal_context"] = set_current_conclusion_id(
            run_id=run_id,
            expected_geometry_hash=expected_geometry_hash,
            conclusion_id=revised.get("conclusion_id"),
        )
    except DealContextError:
        pass

    return _public_view(record)


def get_advisor_chat(run_id: str) -> dict[str, Any]:
    record = _RUNS.get(run_id)
    if record is None:
        raise KeyError(run_id)
    from rangematch.advisor_chat import suggested_chat_questions

    suggestions = record.get("chat_suggestions") or suggested_chat_questions()
    record["chat_suggestions"] = suggestions
    return {
        "run_id": run_id,
        "deal_context_version": (record.get("deal_context") or {}).get("context_version"),
        "suggested_questions": suggestions,
        "turns": list(record.get("chat_turns") or []),
    }


def post_advisor_chat(
    run_id: str,
    *,
    message: str,
    provider_name: str | None = None,
) -> dict[str, Any]:
    """Append one grounded chat turn. Read-only against Packet/Context/Conclusion."""
    from rangematch.advisor_chat import (
        AdvisorChatError,
        chat_view_from_natural_foundation,
        generate_chat_turn,
        suggested_chat_questions,
    )
    from rangematch.llm_provider import configured_provider_name

    record = _RUNS.get(run_id)
    if record is None:
        raise KeyError(run_id)
    if record.get("status") != "SUCCEEDED":
        raise AdvisorChatError("CHAT_RUN_NOT_READY", "chat requires a succeeded Advisor run")

    deal_context = record.get("deal_context")
    if not isinstance(deal_context, dict):
        raise AdvisorChatError("CHAT_RUN_INCOMPLETE", "Deal Context is required")

    mireye_first = record.get("collection_mode") == COLLECTION_MODE_MIREYE_FIRST or (
        not isinstance(record.get("packet"), dict)
        and isinstance(record.get("combined_environmental_evidence_packet"), dict)
    )

    if mireye_first:
        combined = record.get("combined_environmental_evidence_packet")
        natural_profile = record.get("natural_cattle_profile")
        interpretation = record.get("natural_foundation_interpretation")
        if not isinstance(combined, dict):
            raise AdvisorChatError(
                "CHAT_RUN_INCOMPLETE",
                "Combined Environmental Evidence Packet is required for MIREYE_FIRST chat",
            )
        if not isinstance(natural_profile, dict):
            raise AdvisorChatError(
                "CHAT_RUN_INCOMPLETE",
                "Natural Cattle Profile is required for MIREYE_FIRST chat",
            )
        if not isinstance(interpretation, dict):
            raise AdvisorChatError(
                "CHAT_RUN_INCOMPLETE",
                "Natural Foundation Interpretation is required for MIREYE_FIRST chat",
            )

        combined_before = copy.deepcopy(combined)
        profile_before = copy.deepcopy(natural_profile)
        interpretation_before = copy.deepcopy(interpretation)
        context_before = copy.deepcopy(deal_context)
        advisor_view = chat_view_from_natural_foundation(interpretation)

        from rangematch.advisor_insight import load_approved_knowledge_cards

        turn = generate_chat_turn(
            run_id=run_id,
            user_message=message,
            packet=combined,
            deal_context=deal_context,
            operating_conclusion=advisor_view,
            operating_profile=natural_profile,
            knowledge_cards=load_approved_knowledge_cards(workbench="natural_cattle"),
            provider_name=provider_name or configured_provider_name(),
        )

        if record.get("combined_environmental_evidence_packet") != combined_before:
            raise AdvisorChatError(
                "CHAT_PACKET_MUTATION_FORBIDDEN",
                "chat must not modify Combined Environmental Evidence Packet",
            )
        if record.get("natural_cattle_profile") != profile_before:
            raise AdvisorChatError(
                "CHAT_PROFILE_MUTATION_FORBIDDEN",
                "chat must not modify Natural Cattle Profile",
            )
        if record.get("natural_foundation_interpretation") != interpretation_before:
            raise AdvisorChatError(
                "CHAT_INTERPRETATION_MUTATION_FORBIDDEN",
                "chat must not modify Natural Foundation Interpretation",
            )
        if record.get("deal_context") != context_before:
            raise AdvisorChatError(
                "CHAT_CONTEXT_MUTATION_FORBIDDEN",
                "chat must not modify Deal Context",
            )
    else:
        packet = record.get("packet")
        conclusion = record.get("operating_conclusion")
        if not isinstance(packet, dict):
            raise AdvisorChatError("CHAT_RUN_INCOMPLETE", "packet and Deal Context are required")
        if not isinstance(conclusion, dict):
            raise AdvisorChatError(
                "CHAT_CONCLUSION_REQUIRED",
                "chat begins only after an Operating Conclusion exists",
            )

        packet_hash_before = record.get("packet_hash")
        context_before = copy.deepcopy(deal_context)
        conclusion_id_before = conclusion.get("conclusion_id")

        turn = generate_chat_turn(
            run_id=run_id,
            user_message=message,
            packet=packet,
            deal_context=deal_context,
            operating_conclusion=conclusion,
            operating_profile=record.get("operating_profile"),
            provider_name=provider_name or configured_provider_name(),
        )

        # Hard read-only gate: chat must not mutate evidence, context, or conclusion.
        if record.get("packet_hash") != packet_hash_before:
            raise AdvisorChatError(
                "CHAT_PACKET_MUTATION_FORBIDDEN",
                "chat must not modify Physical Evidence",
            )
        if record.get("deal_context") != context_before:
            raise AdvisorChatError(
                "CHAT_CONTEXT_MUTATION_FORBIDDEN",
                "chat must not modify Deal Context",
            )
        if (record.get("operating_conclusion") or {}).get("conclusion_id") != conclusion_id_before:
            raise AdvisorChatError(
                "CHAT_CONCLUSION_MUTATION_FORBIDDEN",
                "chat must not modify Operating Conclusion",
            )

    turns = list(record.get("chat_turns") or [])
    turns.append(turn)
    record["chat_turns"] = turns[-20:]
    if not record.get("chat_suggestions"):
        record["chat_suggestions"] = suggested_chat_questions()
    return {
        "run_id": run_id,
        "deal_context_version": deal_context.get("context_version"),
        "suggested_questions": record["chat_suggestions"],
        "turn": turn,
        "turns": list(record["chat_turns"]),
    }


def get_advisor_deal_context(run_id: str) -> dict[str, Any]:
    from rangematch.advisor_deal_context import DealContextError, get_deal_context_for_run

    record = _RUNS.get(run_id)
    if record is None:
        raise KeyError(run_id)
    context = record.get("deal_context") or get_deal_context_for_run(run_id)
    if context is None:
        raise DealContextError("DEAL_CONTEXT_NOT_FOUND", f"no Deal Context for run {run_id}")
    record["deal_context"] = context
    return context


def update_advisor_deal_context(
    run_id: str,
    *,
    expected_geometry_hash: str,
    expected_context_version: int | None = None,
    operation_type: str | None = None,
    diligence_stage: str | None = None,
    append_answer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from rangematch.advisor_deal_context import DealContextError, update_deal_context

    record = _RUNS.get(run_id)
    if record is None:
        raise KeyError(run_id)
    if record.get("status") != "SUCCEEDED":
        raise DealContextError(
            "DEAL_CONTEXT_RUN_NOT_READY",
            "Deal Context updates require a succeeded Advisor run",
        )
    updated = update_deal_context(
        run_id=run_id,
        expected_geometry_hash=expected_geometry_hash,
        expected_context_version=expected_context_version,
        operation_type=operation_type,
        diligence_stage=diligence_stage,
        append_answer=append_answer,
    )
    record["deal_context"] = updated
    return updated


def get_advisor_report_bundle(run_id: str) -> dict[str, Any] | None:
    record = _RUNS.get(run_id)
    if record is None:
        return None
    parcel = None
    resolution_id = record.get("parcel_resolution_id")
    if resolution_id:
        from rangematch.parcel_resolution_store import get_parcel_resolution_store

        parcel = get_parcel_resolution_store().get(str(resolution_id))
    return assemble_advisor_report_bundle(record, parcel_resolution=parcel)
