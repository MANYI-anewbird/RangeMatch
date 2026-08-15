"""Additional Property Context appendix — HUMAN_ACCESS_INFRA_APPENDIX_ONLY.

Projects isolated non-natural observations into a buyer appendix block.
Collection is performed by the fail-soft Appendix collector, never by this projector,
and the result must not enter primary reasoning.
Contract: docs/NATURAL_CATTLE_FOUNDATION_REPORT_TEMPLATE.md §B
         docs/RANGEMATCH_PRODUCT_AND_AGENT_CODE_FLOW.md Rule HUMAN_ACCESS_INFRA_APPENDIX_ONLY
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

HUMAN_ACCESS_INFRA_APPENDIX_ONLY = True
MAXIMUM_ROWS = 4
PAGE1_APPENDIX_POINTER = (
    "Additional mapped property context is summarized in the Appendix "
    "and does not affect the natural-foundation judgment above."
)

# Explicit APPENDIX_ONLY observation ids already present on the LEGACY packet.
APPENDIX_ONLY_OBSERVATION_IDS = frozenset({"OBS_ROAD"})
APPENDIX_ONLY_VARIABLE_PREFIXES = ("VAR_F07_",)

PROHIBITED_CONTEXT_CLAIM = re.compile(
    r"(?i)\b("
    r"legal\s+access|"
    r"easy\s+access|"
    r"has\s+access|"
    r"access\s+is\s+present|"
    r"recorded\s+access|"
    r"title\s+(?:documents?|clearance|opinion)|"
    r"request\s+title|"
    r"easement\s+(?:confirmed|proven)|"
    r"suitable\s+for\s+cattle|"
    r"buy\s*/\s*no-?buy|"
    r"purchase\s+(?:opinion|recommendation)|"
    r"controlling\s+factor|"
    r"next\s+action|"
    r"document\s+review"
    r")\b"
)


class PropertyContextAppendixError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def is_appendix_only_observation(observation: Mapping[str, Any]) -> bool:
    oid = str(observation.get("observation_id") or "")
    if oid in APPENDIX_ONLY_OBSERVATION_IDS:
        return True
    variable = str(
        observation.get("variable_id")
        or observation.get("land_fact_ref")
        or ""
    )
    return any(variable.startswith(prefix) for prefix in APPENDIX_ONLY_VARIABLE_PREFIXES)


def _observation_value(observation: Mapping[str, Any]) -> Any:
    value = observation.get("display_value")
    if value in (None, ""):
        value = observation.get("value")
    return value


def _is_displayable(observation: Mapping[str, Any]) -> bool:
    state = str(observation.get("evidence_state") or "").upper()
    if state in {
        "SOURCE_UNAVAILABLE",
        "FAILED",
        "NOT_AVAILABLE",
        "REJECTED",
        "MISSING",
        "REJECTED_BY_SEMANTICS_GATE",
    }:
        return False
    value = _observation_value(observation)
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def _format_distance_m(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number) < 1e-9:
        return "0 m"
    if number >= 1000:
        return f"{number / 1000:.2f} km".rstrip("0").rstrip(".")
    text = f"{number:.1f}".rstrip("0").rstrip(".")
    return f"{text} m"


def _project_road_row(observation: Mapping[str, Any]) -> dict[str, str]:
    value = _observation_value(observation)
    try:
        distance = float(value)
    except (TypeError, ValueError):
        distance = None
    if distance is not None and abs(distance) < 1e-9:
        can_say = "A mapped road reaches the parcel boundary."
        how = "The parcel is physically adjacent to the mapped road network."
    elif distance is not None:
        can_say = (
            f"The nearest mapped road is about {_format_distance_m(distance)} "
            "from the parcel boundary."
        )
        how = (
            "The parcel is near the mapped road network, but adjacency is not the same "
            "as a usable entrance."
        )
    else:
        can_say = "Mapped road context is present for this parcel."
        how = "Treat this as physical-map context only."
    return {
        "topic": "Mapped road context",
        "what_we_can_say": can_say,
        "how_to_read_it": how,
        "what_it_does_not_establish": (
            "This does not establish a legal entrance, usable road condition, "
            "or recorded access."
        ),
        "observation_id": str(observation.get("observation_id") or "OBS_ROAD"),
        "classification": "APPENDIX_ONLY",
    }


def project_additional_property_context(
    packet: Mapping[str, Any] | None,
    *,
    max_rows: int = MAXIMUM_ROWS,
) -> dict[str, Any]:
    """Build the optional Additional Property Context block from existing packet rows.

    Never triggers collection itself. Returns ``{"enabled": False}`` when empty.
    """
    if not HUMAN_ACCESS_INFRA_APPENDIX_ONLY:
        raise PropertyContextAppendixError(
            "APPENDIX_CONTRACT_DISABLED",
            "HUMAN_ACCESS_INFRA_APPENDIX_ONLY must remain true",
        )
    observations = []
    if isinstance(packet, Mapping):
        raw = packet.get("observations")
        if isinstance(raw, list):
            observations = [row for row in raw if isinstance(row, Mapping)]

    rows: list[dict[str, str]] = []
    for observation in observations:
        if not is_appendix_only_observation(observation):
            continue
        if not _is_displayable(observation):
            continue
        oid = str(observation.get("observation_id") or "")
        if oid == "OBS_ROAD" or str(observation.get("land_fact_ref") or "").startswith(
            "VAR_F07_"
        ):
            rows.append(_project_road_row(observation))
        else:
            # Future APPENDIX_ONLY ids must be explicitly mapped; do not invent prose.
            continue
        if len(rows) >= max_rows:
            break

    if not rows:
        return {
            "enabled": False,
            "title": "Additional Property Context",
            "rows": [],
            "contract": {
                "HUMAN_ACCESS_INFRA_APPENDIX_ONLY": True,
                "maximum_rows": max_rows,
                "may_trigger_F07": True,
                "collection_role": "APPENDIX_CONTEXT_COLLECTOR",
                "collection_is_fail_soft": True,
                "may_change_conclusion": False,
            },
        }

    validate_additional_property_context_rows(rows, max_rows=max_rows)
    return {
        "enabled": True,
        "title": "Additional Property Context",
        "rows": rows,
        "contract": {
            "HUMAN_ACCESS_INFRA_APPENDIX_ONLY": True,
            "maximum_rows": max_rows,
            "may_trigger_F07": True,
            "collection_role": "APPENDIX_CONTEXT_COLLECTOR",
            "collection_is_fail_soft": True,
            "may_change_conclusion": False,
            "enters_natural_cattle_profile": False,
            "enters_primary_llm_workbench": False,
            "may_be_controlling_factor": False,
            "may_generate_question_or_next_action": False,
        },
        "page1_pointer": PAGE1_APPENDIX_POINTER,
    }


def validate_additional_property_context_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    max_rows: int = MAXIMUM_ROWS,
) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    if len(rows) > max_rows:
        violations.append(
            {
                "code": "PROPERTY_CONTEXT_ROW_LIMIT",
                "message": f"Additional Property Context exceeds {max_rows} rows",
            }
        )
    required = (
        "topic",
        "what_we_can_say",
        "how_to_read_it",
        "what_it_does_not_establish",
    )
    for index, row in enumerate(rows):
        for key in required:
            if not str(row.get(key) or "").strip():
                violations.append(
                    {
                        "code": "PROPERTY_CONTEXT_MISSING_FIELD",
                        "message": f"row {index} missing {key}",
                    }
                )
        blob = " ".join(str(row.get(key) or "") for key in required)
        hit = PROHIBITED_CONTEXT_CLAIM.search(blob)
        if hit:
            # Allow the phrase inside the explicit non-conclusion column only when
            # framed as "does not establish … legal entrance / recorded access".
            non_conclusion = str(row.get("what_it_does_not_establish") or "")
            claim_cols = " ".join(
                [
                    str(row.get("topic") or ""),
                    str(row.get("what_we_can_say") or ""),
                    str(row.get("how_to_read_it") or ""),
                ]
            )
            bad = PROHIBITED_CONTEXT_CLAIM.search(claim_cols)
            if bad:
                violations.append(
                    {
                        "code": "PROPERTY_CONTEXT_PROHIBITED_CLAIM",
                        "message": bad.group(0),
                    }
                )
            elif "does not establish" not in non_conclusion.lower():
                violations.append(
                    {
                        "code": "PROPERTY_CONTEXT_PROHIBITED_CLAIM",
                        "message": hit.group(0),
                    }
                )
    return violations


def validate_property_context_against_primary(
    *,
    property_context: Mapping[str, Any] | None,
    primary_prose: str,
) -> list[dict[str, str]]:
    """Ensure appendix context did not leak into primary narrative control language."""
    violations: list[dict[str, str]] = []
    ctx = property_context if isinstance(property_context, Mapping) else {}
    enabled = bool(ctx.get("enabled"))
    if enabled:
        pointer = str(ctx.get("page1_pointer") or "")
        if pointer and pointer not in primary_prose and PAGE1_APPENDIX_POINTER not in primary_prose:
            # Pointer is optional on Page 1 footer; absence is allowed. Presence of
            # interpretive road/access language in primary prose is not.
            pass
    # Primary prose must not treat access/infra as the controlling story.
    if re.search(
        r"(?i)\b(controlling\s+(?:issue|factor|constraint)\s+is\s+(?:legal\s+)?access|"
        r"request\s+title\s+documents?\s+before|"
        r"legal\s+entrance\s+is\s+(?:proven|confirmed))\b",
        primary_prose or "",
    ):
        violations.append(
            {
                "code": "PROPERTY_CONTEXT_PRIMARY_LEAK",
                "message": "access/infrastructure language controls primary narrative",
            }
        )
    row_violations = validate_additional_property_context_rows(
        list(ctx.get("rows") or []) if enabled else []
    )
    violations.extend(row_violations)
    contract = ctx.get("contract") if isinstance(ctx.get("contract"), Mapping) else {}
    if enabled:
        if contract.get("may_trigger_F07") is not True or contract.get(
            "collection_role"
        ) != "APPENDIX_CONTEXT_COLLECTOR":
            violations.append(
                {
                    "code": "PROPERTY_CONTEXT_F07_CONTRACT",
                    "message": "F07 must be isolated to APPENDIX_CONTEXT_COLLECTOR",
                }
            )
        if contract.get("collection_is_fail_soft") is not True:
            violations.append(
                {
                    "code": "PROPERTY_CONTEXT_F07_CONTRACT",
                    "message": "Appendix F07 collection must be fail-soft",
                }
            )
        if contract.get("may_change_conclusion") is not False:
            violations.append(
                {
                    "code": "PROPERTY_CONTEXT_CONCLUSION_CONTRACT",
                    "message": "may_change_conclusion must be false",
                }
            )
    return violations
