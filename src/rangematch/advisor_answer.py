"""Slice 5: answer the current next_question and revise the conclusion.

Physical Packet is never mutated. Deal Context bumps version; revised conclusion
is stored beside the frozen initial conclusion.
"""

from __future__ import annotations

from typing import Any, Mapping

from rangematch.advisor_deal_context import OPERATION_TYPES
from rangematch.advisor_question import QUESTION_CATALOG


class AdvisorAnswerError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def normalize_answer_value(question_id: str, answer: Any) -> tuple[str, Any]:
    """Map a submitted answer onto the catalog field + typed value."""
    catalog = QUESTION_CATALOG.get(str(question_id or "").strip())
    if catalog is None:
        raise AdvisorAnswerError("ANSWER_QUESTION_UNKNOWN", f"unknown question_id={question_id}")
    field = str(catalog["allowed_field"])

    if field == "operation_type":
        raw = str(answer or "").strip().upper().replace("-", "_").replace(" ", "_")
        aliases = {
            "SEASONAL": "SEASONAL_GRAZING",
            "SEASONAL_GRAZING": "SEASONAL_GRAZING",
            "GRAZING": "SEASONAL_GRAZING",
            "YEAR_ROUND": "YEAR_ROUND_COW_CALF",
            "YEAR_ROUND_COW_CALF": "YEAR_ROUND_COW_CALF",
            "COW_CALF": "YEAR_ROUND_COW_CALF",
            "OTHER": "OTHER",
        }
        value = aliases.get(raw)
        if value is None or value not in OPERATION_TYPES or value == "UNKNOWN":
            raise AdvisorAnswerError(
                "ANSWER_OPERATION_TYPE_INVALID",
                "answer must be SEASONAL_GRAZING, YEAR_ROUND_COW_CALF, or OTHER",
            )
        return field, value

    if field in {"seller_water_claim", "access_documents_on_hand"}:
        if isinstance(answer, bool):
            return field, answer
        raw = str(answer or "").strip().upper()
        if raw in {"YES", "Y", "TRUE", "1"}:
            return field, True
        if raw in {"NO", "N", "FALSE", "0"}:
            return field, False
        raise AdvisorAnswerError(
            "ANSWER_BOOLEAN_INVALID",
            f"answer for {field} must be yes/no or boolean",
        )

    raise AdvisorAnswerError("ANSWER_FIELD_UNSUPPORTED", f"unsupported field={field}")


def require_question_binding(
    *,
    conclusion: Mapping[str, Any] | None,
    question_id: str,
    expected_context_version: int,
    expected_geometry_hash: str,
    deal_context: Mapping[str, Any],
    run_geometry_hash: str | None,
) -> dict[str, Any]:
    """Fail closed unless the answer targets the live conclusion + context + geometry."""
    if not isinstance(conclusion, Mapping):
        raise AdvisorAnswerError("ANSWER_CONCLUSION_MISSING", "no operating conclusion on run")
    live_qid = str((conclusion.get("next_question") or {}).get("question_id") or "")
    submitted = str(question_id or "").strip()
    if not submitted or submitted != live_qid:
        raise AdvisorAnswerError(
            "ANSWER_QUESTION_MISMATCH",
            f"expected question_id={live_qid}, got {submitted}",
        )
    concl_version = int(conclusion.get("deal_context_version") or 0)
    context_version = int(deal_context.get("context_version") or 0)
    if int(expected_context_version) != context_version:
        raise AdvisorAnswerError(
            "ANSWER_CONTEXT_VERSION_MISMATCH",
            f"expected_context_version={expected_context_version}, current={context_version}",
        )
    if concl_version != context_version:
        raise AdvisorAnswerError(
            "ANSWER_CONCLUSION_STALE",
            f"conclusion deal_context_version={concl_version} != context {context_version}",
        )
    geo = str(expected_geometry_hash or "").strip()
    ctx_geo = str(deal_context.get("geometry_hash") or "").strip()
    run_geo = str(run_geometry_hash or "").strip()
    if not geo or geo != ctx_geo or (run_geo and geo != run_geo):
        raise AdvisorAnswerError(
            "ANSWER_GEOMETRY_MISMATCH",
            "expected_geometry_hash does not match this run",
        )
    return dict(QUESTION_CATALOG[submitted])
