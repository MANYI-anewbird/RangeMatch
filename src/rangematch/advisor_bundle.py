"""Persist one Advisor run as a competition/report evidence bundle.

In-memory runs disappear on restart. The bundle is the durable artifact.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

BUNDLE_SCHEMA = "RANGEMATCH_ADVISOR_REPORT_BUNDLE@0.1.0"
SECRET_KEYS = frozenset(
    {
        "authorization",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "token",
        "cookie",
        "set-cookie",
        "x-api-key",
    }
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in SECRET_KEYS:
                out[str(key)] = "[REDACTED]"
            else:
                out[str(key)] = _redact(item)
        return out
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def assemble_advisor_report_bundle(
    record: Mapping[str, Any],
    *,
    parcel_resolution: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a durable bundle from the in-memory run record."""
    packet = record.get("packet") or {}
    brief = record.get("brief")
    explanation = record.get("buyer_explanation")
    mireye_live = record.get("mireye_live") or {}
    payloads = _redact(record.get("_mireye_context_payloads") or {})
    unified = record.get("_unified_output")
    workbench = record.get("_llm_workbench")
    insights = record.get("_validated_insights")
    if insights is None and isinstance(explanation, Mapping):
        insights = explanation.get("insights")
    missing = []
    if unified is None:
        missing.append("unified_output_body")
    if not payloads:
        missing.append("mireye_context_payloads")
    if insights is None:
        missing.append("validated_insight_records")
    selection = (parcel_resolution or {}).get("selection") or {}
    confirmed = (parcel_resolution or {}).get("confirmed_parcel") or {}
    return {
        "schema_version": BUNDLE_SCHEMA,
        "captured_at": _utc_now(),
        "completeness": "COMPLETE" if not missing else "PARTIAL",
        "missing_from_record": missing,
        "user_input": (parcel_resolution or {}).get("input")
        or {"raw_address": record.get("address")},
        "parcel_resolution": _redact(
            {
                "resolution_id": (parcel_resolution or {}).get("resolution_id")
                or record.get("parcel_resolution_id"),
                "status": (parcel_resolution or {}).get("status"),
                "candidates": (parcel_resolution or {}).get("candidates")
                or record.get("parcel_candidates"),
                "selection": selection,
                "confirmed_parcel": {
                    "geometry_id": confirmed.get("geometry_id"),
                    "geometry_reference": confirmed.get("geometry_reference"),
                    "geometry_hash": confirmed.get("geometry_hash")
                    or record.get("geometry_hash"),
                    "source_crs": confirmed.get("source_crs"),
                    "parcel_geometry": confirmed.get("parcel_geometry")
                    or record.get("parcel_geometry"),
                },
                "provenance": (parcel_resolution or {}).get("provenance"),
                "limitations": (parcel_resolution or {}).get("limitations"),
            }
        ),
        "advisor_run": {
            "run_id": record.get("run_id"),
            "address": record.get("address"),
            "status": record.get("status"),
            "investigation_outcome": record.get("investigation_outcome"),
            "track": record.get("track"),
            "generated_at": record.get("generated_at"),
            "geometry_hash": record.get("geometry_hash"),
            "parcel_geometry_confirmed": bool(record.get("parcel_geometry_confirmed")),
            "location_resolved": bool(record.get("location_resolved")),
            "steps": list(record.get("steps") or []),
            "agenda": list(record.get("agenda") or []),
            "limitations": list(record.get("limitations") or []),
            "packet_hash": record.get("packet_hash"),
        },
        "mireye_lookup": _redact(mireye_live.get("lookup")),
        "mireye_contexts_status": mireye_live.get("contexts"),
        "mireye_context_payloads": payloads,
        "mireye_live": _redact(
            {key: value for key, value in mireye_live.items() if key != "lookup"}
            | {"lookup": mireye_live.get("lookup")}
        )
        if mireye_live
        else None,
        "confirmed_geometry": record.get("parcel_geometry")
        or confirmed.get("parcel_geometry"),
        "unified_output": unified,
        "operating_profile": record.get("operating_profile"),
        "generic_evidence_packet": packet,
        "candidate_objects": packet.get("candidate_objects") if packet else None,
        "action_policy": packet.get("action_policy") if packet else None,
        "llm_workbench": workbench,
        "validated_insights": insights,
        "deterministic_brief": brief,
        "buyer_report": explanation,
        "provenance": {
            "brief_validation_status": (brief or {}).get("validation_status"),
            "buyer_report_source": (explanation or {}).get("source")
            if isinstance(explanation, Mapping)
            else None,
            "buyer_report_validation_status": (explanation or {}).get("validation_status")
            if isinstance(explanation, Mapping)
            else None,
            "buyer_report_provenance": (explanation or {}).get("provenance")
            if isinstance(explanation, Mapping)
            else None,
            "policy_scope": (packet.get("technical_references") or {}).get("policy_scope")
            if packet
            else None,
            "is_engineering_test_geometry": (packet.get("parcel") or {}).get(
                "is_engineering_test_geometry"
            )
            if packet
            else None,
            "confirmation_method": selection.get("confirmation_method"),
            "llm_used": bool(
                ((explanation or {}).get("provenance") or {}).get("llm_used")
            )
            if isinstance(explanation, Mapping)
            else False,
        },
    }
