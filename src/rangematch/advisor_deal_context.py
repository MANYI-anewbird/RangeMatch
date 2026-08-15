"""Minimal Deal Context state for Advisor runs (Slice 3).

Physical Packet + Operating Profile create the context. Mutations bump
context_version. No LLM conclusion rewrite in this slice.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from jsonschema import Draft202012Validator

from rangematch.advisor_schema import _load_schema

SCHEMA_VERSION = "RANGEMATCH_ADVISOR_DEAL_CONTEXT@0.1.0"
PROVENANCE_USER = "USER_SUPPLIED_UNVERIFIED"
PROVENANCE_DEMO = "DEMO_SCENARIO_CLAIM"
PROVENANCE_PACKET = "PACKET_LISTING_CLAIM"

OPERATION_TYPES = frozenset(
    {"UNKNOWN", "SEASONAL_GRAZING", "YEAR_ROUND_COW_CALF", "OTHER"}
)
DILIGENCE_STAGES = frozenset(
    {"SCREENING", "PRE_VISIT", "FIELD_PLANNED", "TITLE_REVIEW"}
)

_BY_RUN: dict[str, dict[str, Any]] = {}
_BY_ID: dict[str, dict[str, Any]] = {}


class DealContextError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def reset_deal_contexts_for_tests() -> None:
    _BY_RUN.clear()
    _BY_ID.clear()


def _validate(context: dict[str, Any]) -> None:
    schema = _load_schema("advisor_deal_context.schema.json")
    errors = sorted(
        Draft202012Validator(schema).iter_errors(context),
        key=lambda err: list(err.absolute_path),
    )
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.absolute_path) or "$"
        raise DealContextError(
            "DEAL_CONTEXT_SCHEMA_INVALID",
            f"{path}: {first.message}",
        )


def _snapshot(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "context_version": int(context["context_version"]),
        "operation_type": context["operation_type"],
        "diligence_stage": context["diligence_stage"],
        "seller_claims": copy.deepcopy(context.get("seller_claims") or []),
        "user_answers": copy.deepcopy(context.get("user_answers") or []),
        "current_conclusion_id": context.get("current_conclusion_id"),
        "recorded_at": _utc_now(),
    }


def _public(context: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(context)


def normalize_seller_claims(
    claims: list[dict[str, Any]] | None,
    *,
    default_provenance: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for index, row in enumerate(claims or []):
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or row.get("claim") or "").strip()
        claim_id = str(row.get("claim_id") or f"CLAIM_{index + 1}").strip()
        if not text or not claim_id:
            continue
        provenance = str(row.get("provenance") or default_provenance).strip()
        out.append(
            {
                "claim_id": claim_id,
                "category": row.get("category"),
                "text": text,
                "source_reference": row.get("source_reference"),
                "claim_strength": row.get("claim_strength"),
                "verification_status": row.get("verification_status"),
                "provenance": provenance,
            }
        )
    return out


def create_deal_context(
    *,
    run_id: str,
    parcel_resolution_id: str | None,
    geometry_hash: str,
    seller_claims: list[dict[str, Any]] | None = None,
    run_mode: str = "CUSTOM",
    demo_scenario_id: str | None = None,
) -> dict[str, Any]:
    """Create version 1 Deal Context bound to one run + geometry."""
    run_key = str(run_id or "").strip()
    geo = str(geometry_hash or "").strip()
    if not run_key:
        raise DealContextError("DEAL_CONTEXT_RUN_REQUIRED", "run_id is required")
    if len(geo) != 64:
        raise DealContextError(
            "DEAL_CONTEXT_GEOMETRY_REQUIRED",
            "geometry_hash must be a 64-character confirmed parcel hash",
        )
    if run_key in _BY_RUN:
        raise DealContextError(
            "DEAL_CONTEXT_EXISTS",
            f"Deal Context already exists for run {run_key}",
        )

    mode = str(run_mode or "CUSTOM").strip().upper()
    if mode not in {"CUSTOM", "VERIFIED_DEMO"}:
        raise DealContextError("DEAL_CONTEXT_RUN_MODE_INVALID", mode)

    default_prov = PROVENANCE_DEMO if mode == "VERIFIED_DEMO" else PROVENANCE_PACKET
    now = _utc_now()
    context = {
        "schema_version": SCHEMA_VERSION,
        "deal_context_id": f"deal_{uuid4().hex[:16]}",
        "run_id": run_key,
        "parcel_resolution_id": (parcel_resolution_id or None),
        "geometry_hash": geo,
        "species": "CATTLE",
        "operation_type": "UNKNOWN",
        "diligence_stage": "SCREENING",
        "seller_claims": normalize_seller_claims(
            seller_claims, default_provenance=default_prov
        ),
        "user_answers": [],
        "current_conclusion_id": None,
        "context_version": 1,
        "created_at": now,
        "updated_at": now,
        "run_mode": mode,
        "demo_scenario_id": demo_scenario_id if mode == "VERIFIED_DEMO" else None,
        "version_history": [],
    }
    _validate(context)
    _BY_RUN[run_key] = context
    _BY_ID[context["deal_context_id"]] = context
    return _public(context)


def get_deal_context_for_run(run_id: str) -> dict[str, Any] | None:
    row = _BY_RUN.get(str(run_id or "").strip())
    return _public(row) if row else None


def get_deal_context(deal_context_id: str) -> dict[str, Any] | None:
    row = _BY_ID.get(str(deal_context_id or "").strip())
    return _public(row) if row else None


def _require_bound_context(
    *,
    run_id: str,
    expected_geometry_hash: str,
    expected_context_version: int | None = None,
) -> dict[str, Any]:
    run_key = str(run_id or "").strip()
    geo = str(expected_geometry_hash or "").strip()
    context = _BY_RUN.get(run_key)
    if context is None:
        raise DealContextError("DEAL_CONTEXT_NOT_FOUND", f"no Deal Context for run {run_key}")
    if context["run_id"] != run_key:
        raise DealContextError("DEAL_CONTEXT_RUN_MISMATCH", "run_id does not match context")
    if context["geometry_hash"] != geo:
        raise DealContextError(
            "DEAL_CONTEXT_GEOMETRY_MISMATCH",
            "geometry_hash does not match this run's Deal Context",
        )
    if expected_context_version is not None and int(expected_context_version) != int(
        context["context_version"]
    ):
        raise DealContextError(
            "DEAL_CONTEXT_VERSION_MISMATCH",
            f"expected context_version={expected_context_version}, "
            f"current={context['context_version']}",
        )
    return context


def _bump(context: dict[str, Any]) -> None:
    context.setdefault("version_history", []).append(_snapshot(context))
    context["context_version"] = int(context["context_version"]) + 1
    context["updated_at"] = _utc_now()


def set_current_conclusion_id(
    *,
    run_id: str,
    expected_geometry_hash: str,
    conclusion_id: str | None,
) -> dict[str, Any]:
    """Point Deal Context at the latest conclusion without bumping context_version."""
    context = _require_bound_context(
        run_id=run_id,
        expected_geometry_hash=expected_geometry_hash,
        expected_context_version=None,
    )
    context["current_conclusion_id"] = conclusion_id
    context["updated_at"] = _utc_now()
    _validate(context)
    return _public(context)


def update_deal_context(
    *,
    run_id: str,
    expected_geometry_hash: str,
    expected_context_version: int | None = None,
    operation_type: str | None = None,
    diligence_stage: str | None = None,
    append_answer: dict[str, Any] | None = None,
    current_conclusion_id: str | None = None,
    set_conclusion_id: bool = False,
) -> dict[str, Any]:
    """Mutate Deal Context. Always increments context_version. Never crosses runs."""
    context = _require_bound_context(
        run_id=run_id,
        expected_geometry_hash=expected_geometry_hash,
        expected_context_version=expected_context_version,
    )

    if operation_type is None and diligence_stage is None and append_answer is None and not set_conclusion_id:
        raise DealContextError("DEAL_CONTEXT_NO_MUTATION", "no fields to update")

    if operation_type is not None:
        value = str(operation_type).strip().upper()
        if value not in OPERATION_TYPES:
            raise DealContextError("DEAL_CONTEXT_OPERATION_TYPE_INVALID", value)
    if diligence_stage is not None:
        stage = str(diligence_stage).strip().upper()
        if stage not in DILIGENCE_STAGES:
            raise DealContextError("DEAL_CONTEXT_DILIGENCE_STAGE_INVALID", stage)

    answer_row: dict[str, Any] | None = None
    if append_answer is not None:
        if not isinstance(append_answer, dict):
            raise DealContextError("DEAL_CONTEXT_ANSWER_INVALID", "append_answer must be object")
        field = str(append_answer.get("field") or "").strip()
        if not field:
            raise DealContextError("DEAL_CONTEXT_ANSWER_FIELD_REQUIRED", "field is required")
        answer_row = {
            "answer_id": str(append_answer.get("answer_id") or f"ans_{uuid4().hex[:12]}"),
            "field": field,
            "value": append_answer.get("value"),
            "provenance": PROVENANCE_USER,
            "answered_at": _utc_now(),
        }

    _bump(context)

    if operation_type is not None:
        context["operation_type"] = str(operation_type).strip().upper()
    if diligence_stage is not None:
        context["diligence_stage"] = str(diligence_stage).strip().upper()
    if answer_row is not None:
        context["user_answers"] = list(context.get("user_answers") or []) + [answer_row]
        # Convenience: answering operation_type also sets the typed field.
        if answer_row["field"] == "operation_type" and operation_type is None:
            value = str(answer_row.get("value") or "").strip().upper()
            if value in OPERATION_TYPES:
                context["operation_type"] = value
        if answer_row["field"] == "diligence_stage" and diligence_stage is None:
            value = str(answer_row.get("value") or "").strip().upper()
            if value in DILIGENCE_STAGES:
                context["diligence_stage"] = value
    if set_conclusion_id:
        context["current_conclusion_id"] = current_conclusion_id

    _validate(context)
    return _public(context)
