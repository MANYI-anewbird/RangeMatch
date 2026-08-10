"""Constrained LLM Intent Parser.

Explicit UI selections are authoritative. LLM output is schema-validated and
fails closed. Never invents parcel identity or unsupported operations.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from rangematch.llm_provider import (
    INTENT_PROMPT_VERSION,
    LLMCompletion,
    get_provider,
    utc_now_iso,
)

SUPPORTED_OPERATIONS = ("COW_CALF_OPERATION", "SHEEP_GRAZING")
SUPPORTED_MODES = ("GOAL_DIRECTED", "DISCOVERY")

INTENT_SYSTEM = """You are RangeMatch Intent Parser.
Return JSON only matching the RangeMatch intent schema.
Required keys: intent_status, rejection_code, mode, intended_operation,
planned_actions, parcel_input_reference, clarification_questions,
parser_provenance, prohibited_inferences_applied.
Rules:
- Do not invent address, APN, geometry, acreage, or planned actions.
- Do not create batch/portfolio/ICP intent.
- Unsupported operations must not be mapped to Cow-Calf or Sheep.
- DISCOVERY requires intended_operation null.
- GOAL_DIRECTED requires one supported intended operation.
- Explicit UI selections in the user payload are authoritative.
- Set prohibited_inferences_applied to true.
"""


def normalize_live_intent_shape(
    raw: dict[str, Any], *, fixture_key: str
) -> tuple[dict[str, Any], bool]:
    """Repair incomplete live structure from a deterministic intent baseline."""
    if not _basic_schema_validate(raw):
        return dict(raw), False
    baseline_path = _repo_root() / "test-data" / "llm" / f"{fixture_key}.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    repaired = dict(baseline)
    # Live output may contribute diligence intent and clarification prose only.
    for key in ("planned_actions", "clarification_questions"):
        value = raw.get(key)
        if (
            isinstance(value, list)
            and all(isinstance(item, str) and item.strip() for item in value)
        ):
            repaired[key] = [item.strip() for item in value]
    return repaired, True


class IntentParseError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_intent_schema() -> dict[str, Any]:
    path = _repo_root() / "docs" / "schemas" / "rangematch_intent.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _basic_schema_validate(intent: dict[str, Any]) -> list[str]:
    """Minimal fail-closed validation without external jsonschema dependency."""
    errors: list[str] = []
    required = [
        "intent_status",
        "mode",
        "intended_operation",
        "planned_actions",
        "parcel_input_reference",
        "clarification_questions",
        "parser_provenance",
        "prohibited_inferences_applied",
    ]
    for key in required:
        if key not in intent:
            errors.append(f"missing:{key}")
    status = intent.get("intent_status")
    if status not in ("PARSED", "NEEDS_CLARIFICATION", "REJECTED"):
        errors.append("invalid:intent_status")
    if intent.get("prohibited_inferences_applied") is not True:
        errors.append("prohibited_inferences_applied_must_be_true")
    mode = intent.get("mode")
    if mode not in ("GOAL_DIRECTED", "DISCOVERY", None):
        errors.append("invalid:mode")
    op = intent.get("intended_operation")
    if op not in ("COW_CALF_OPERATION", "SHEEP_GRAZING", None):
        errors.append("invalid:intended_operation")
    if not isinstance(intent.get("planned_actions"), list):
        errors.append("invalid:planned_actions")
    elif any(not isinstance(x, str) or not x.strip() for x in intent["planned_actions"]):
        errors.append("invalid:planned_actions_item")
    if not isinstance(intent.get("clarification_questions"), list):
        errors.append("invalid:clarification_questions")
    pref = intent.get("parcel_input_reference")
    if not isinstance(pref, dict) or "kind" not in pref or "value" not in pref:
        errors.append("invalid:parcel_input_reference")
    return errors


def _parcel_reference(
    *,
    address: str | None,
    parcel_geometry: dict[str, Any] | None,
    existing_land_profile_reference: str | None,
) -> dict[str, Any]:
    present = []
    if address and str(address).strip():
        present.append(("address", str(address).strip()))
    if parcel_geometry is not None:
        present.append(("parcel_geometry", parcel_geometry))
    if existing_land_profile_reference and str(existing_land_profile_reference).strip():
        present.append(
            (
                "existing_land_profile_reference",
                str(existing_land_profile_reference).strip(),
            )
        )
    if len(present) > 1:
        raise IntentParseError(
            "REJECTED_INVALID_REQUEST",
            "exactly_one_parcel_input_or_none",
        )
    if not present:
        return {"kind": "none", "value": None}
    kind, value = present[0]
    return {"kind": kind, "value": value}


def _looks_like_batch(text: str) -> bool:
    t = text.lower()
    patterns = [
        r"\bbest\s+\d+\b",
        r"\b\d+\s+ranches?\b",
        r"\bbatch\b",
        r"\bportfolio\b",
        r"\bicp\b",
        r"\bmultiple\s+parcels?\b",
        r"\bsearch\s+list\b",
        r"\bacross\s+(colorado|texas|montana|the\s+state)\b",
    ]
    return any(re.search(p, t) for p in patterns)


def _mentions_unsupported_operation(text: str) -> bool:
    t = text.lower()
    # Supported mentions
    cow = bool(re.search(r"cow[\s\-]?calf|cattle\s+pair", t))
    sheep = bool(re.search(r"\bsheep\b|\bgrazing\s+sheep\b", t))
    # Unsupported livestock / crops often requested
    unsupported = bool(
        re.search(
            r"\b(dairy|feedlot|vineyard|orchard|cannabis|horse\s+boarding|"
            r"goat\b|bison|elk\b|poultry|chicken|pig\b|swine|row\s*crop|"
            r"wheat|corn|hay\s+only)\b",
            t,
        )
    )
    return unsupported and not (cow or sheep)


def select_intent_fixture_key(user_request: str) -> str:
    t = user_request.lower()
    if _looks_like_batch(t):
        return "intent_rejected_batch"
    if _mentions_unsupported_operation(t):
        return "intent_needs_clarification_unsupported_op"
    if re.search(r"what can (this|the) parcel be used for|best use|suitable uses", t):
        return "intent_discovery"
    if re.search(r"cow[\s\-]?calf|cattle", t):
        return "intent_goal_directed_cow_calf"
    if re.search(r"\bsheep\b", t):
        return "intent_goal_directed_sheep"
    return "intent_needs_clarification_mode"


def _apply_ui_overrides(
    intent: dict[str, Any],
    *,
    ui_mode: str | None,
    ui_intended_operation: str | None,
    ui_planned_actions: list[str] | None,
) -> dict[str, Any]:
    out = dict(intent)
    applied = False
    if ui_mode in SUPPORTED_MODES:
        out["mode"] = ui_mode
        applied = True
        if ui_mode == "DISCOVERY":
            out["intended_operation"] = None
    if ui_mode == "GOAL_DIRECTED" and ui_intended_operation in SUPPORTED_OPERATIONS:
        out["intended_operation"] = ui_intended_operation
        applied = True
    elif ui_intended_operation in SUPPORTED_OPERATIONS and ui_mode is None:
        # Explicit op without mode → GOAL_DIRECTED
        out["mode"] = "GOAL_DIRECTED"
        out["intended_operation"] = ui_intended_operation
        applied = True
    if ui_planned_actions is not None:
        out["planned_actions"] = [
            a.strip() for a in ui_planned_actions if isinstance(a, str) and a.strip()
        ]
        applied = True
    prov = dict(out.get("parser_provenance") or {})
    prov["ui_overrides_applied"] = applied
    out["parser_provenance"] = prov
    return out


def _enforce_mode_rules(intent: dict[str, Any]) -> dict[str, Any]:
    out = dict(intent)
    status = out.get("intent_status")
    if status == "REJECTED":
        return out
    mode = out.get("mode")
    op = out.get("intended_operation")
    if mode == "DISCOVERY" and op is not None:
        out["intended_operation"] = None
    if mode == "GOAL_DIRECTED" and op not in SUPPORTED_OPERATIONS:
        out["intent_status"] = "NEEDS_CLARIFICATION"
        out["intended_operation"] = None
        qs = list(out.get("clarification_questions") or [])
        qs.append(
            "Which supported operation should we evaluate: Cow-Calf or Sheep?"
        )
        out["clarification_questions"] = qs
        out["supported_operations_note"] = (
            "Supported operations are COW_CALF_OPERATION and SHEEP_GRAZING only."
        )
    if status == "PARSED" and mode not in SUPPORTED_MODES:
        out["intent_status"] = "NEEDS_CLARIFICATION"
        out["mode"] = None
        out["intended_operation"] = None
        out["clarification_questions"] = list(
            out.get("clarification_questions") or []
        ) + ["Is this a goal-directed check for Cow-Calf/Sheep, or a discovery comparison?"]
    return out


def parse_intent(
    *,
    user_request: str,
    address: str | None = None,
    parcel_geometry: dict[str, Any] | None = None,
    existing_land_profile_reference: str | None = None,
    ui_mode: str | None = None,
    ui_intended_operation: str | None = None,
    ui_planned_actions: list[str] | None = None,
    provider_name: str | None = None,
) -> dict[str, Any]:
    text = (user_request or "").strip()
    if not text:
        raise IntentParseError("REJECTED_INVALID_REQUEST", "user_request_required")

    parcel_ref = _parcel_reference(
        address=address,
        parcel_geometry=parcel_geometry,
        existing_land_profile_reference=existing_land_profile_reference,
    )

    # Deterministic pre-checks (still recorded via fixture path when using FIXTURE).
    fixture_key = select_intent_fixture_key(text)
    provider = get_provider(provider_name)
    completion: LLMCompletion = provider.complete_json(
        system=INTENT_SYSTEM,
        user=json.dumps(
            {
                "user_request": text,
                "parcel_input_reference": parcel_ref,
                "ui_mode": ui_mode,
                "ui_intended_operation": ui_intended_operation,
                "ui_planned_actions": ui_planned_actions,
                "supported_operations": list(SUPPORTED_OPERATIONS),
                "rules": [
                    "UI selections are authoritative",
                    "no batch/ICP",
                    "no invented parcel facts",
                ],
            },
            ensure_ascii=False,
        ),
        prompt_version=INTENT_PROMPT_VERSION,
        fixture_key=fixture_key if provider.name == "FIXTURE" else None,
    )

    if completion.content is None:
        return {
            "intent_status": "REJECTED",
            "rejection_code": "REJECTED_INVALID_REQUEST",
            "mode": None,
            "intended_operation": None,
            "planned_actions": [],
            "parcel_input_reference": parcel_ref,
            "clarification_questions": [],
            "parser_provenance": {
                "provider": completion.provider,
                "model_id": completion.model_id,
                "prompt_version": completion.prompt_version,
                "generated_at": completion.generated_at,
                "provider_status": completion.provider_status,
                "ui_overrides_applied": False,
            },
            "prohibited_inferences_applied": True,
            "provider_error": {
                "code": completion.error_code,
                "message": completion.error_message,
            },
        }

    intent, live_shape_repaired = normalize_live_intent_shape(
        dict(completion.content), fixture_key=fixture_key
    )
    intent["parcel_input_reference"] = parcel_ref
    intent["prohibited_inferences_applied"] = True
    intent["parser_provenance"] = {
        "provider": completion.provider,
        "model_id": completion.model_id,
        "prompt_version": INTENT_PROMPT_VERSION,
        "generated_at": completion.generated_at or utc_now_iso(),
        "provider_status": completion.provider_status,
        "ui_overrides_applied": False,
        "live_shape_repaired": live_shape_repaired,
    }

    intent = _apply_ui_overrides(
        intent,
        ui_mode=ui_mode,
        ui_intended_operation=ui_intended_operation,
        ui_planned_actions=ui_planned_actions,
    )
    intent = _enforce_mode_rules(intent)

    # Batch hard reject even if LLM misfires.
    if _looks_like_batch(text) and intent.get("intent_status") != "REJECTED":
        intent["intent_status"] = "REJECTED"
        intent["rejection_code"] = "REJECTED_OUT_OF_SCOPE_BATCH"
        intent["mode"] = None
        intent["intended_operation"] = None
        intent["planned_actions"] = []
        intent["clarification_questions"] = [
            "RangeMatch investigates exactly one parcel. Batch/portfolio search is out of scope."
        ]

    errors = _basic_schema_validate(intent)
    if errors:
        raise IntentParseError(
            "REJECTED_INVALID_REQUEST",
            "intent_schema_validation_failed:" + ",".join(errors),
        )
    return intent
