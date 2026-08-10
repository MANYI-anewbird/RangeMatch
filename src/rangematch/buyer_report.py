"""Constrained LLM Buyer Report Generator.

Consumes validated Unified Output only. Output is not displayable until the
deterministic validator passes.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from rangematch.llm_provider import (
    BUYER_REPORT_PROMPT_VERSION,
    get_provider,
    utc_now_iso,
)
from rangematch.report_validator import (
    FACTOR_HUMAN,
    build_evidence_index,
    validate_buyer_report,
)

BUYER_REPORT_SCHEMA_VERSION = "RANGEMATCH_BUYER_REPORT@0.1.0"

BUYER_SYSTEM = """You are RangeMatch Buyer Report writer.
Return JSON only. Your output is a prose overlay, not the authoritative report.
Use this exact root shape:
{"sections":{"executive_summary":{"summary":"...","findings":["..."]},
"property":{"summary":"...","findings":["..."]},
"land_and_resources":{"summary":"...","findings":["..."]},
"resilience_and_hazards":{"summary":"...","findings":["..."]},
"operation_comparison":{"summary":"...","findings":["..."]},
"key_unknowns":{"summary":"...","findings":["..."]},
"diligence_plan":{"summary":"...","findings":["..."]},
"methodology_and_limitations":{"summary":"...","findings":["..."]}}}
Rules:
- Never change Engine decision_label, Factor signals, or ranking_permission.
- HOLD means incomplete evidence, not unsuitable land.
- Write for a non-technical ranch buyer at an eighth-grade reading level.
- Lead with the practical decision: continue diligence, pause, or do not advance.
- Explain what the evidence means for the buyer, not how the software is built.
- Never expose Factor IDs (F01-F08), variable IDs, enum names, ranking_permission,
  CONTEXT_DEPENDENT, NEEDS_VERIFICATION, Engine-bound, hashes, or adapter language.
- Use at most three short findings per section, except key_unknowns may use four.
- Prioritize exactly three diligence actions by decision value.
- Translate all internal states into ordinary language.
- Disclose Mireye BLOCKED_EXTERNAL plainly without dominating the report.
- Only Cow-Calf and Sheep are compared; never claim a globally best land use.
- Every numeric claim needs numeric_refs to land facts.
- Preserve material unknowns (F02 coverage, F03 water, F07 legal access, F08 woody).
- Do not invent URLs, sources, acreage, APN, carrying capacity, profitability,
  legal compliance, or permit certainty.
"""

NARRATIVE_SECTION_KEYS = (
    "executive_summary",
    "property",
    "land_and_resources",
    "resilience_and_hazards",
    "operation_comparison",
    "key_unknowns",
    "diligence_plan",
    "methodology_and_limitations",
)


def merge_live_prose_onto_grounded_report(
    grounded: dict[str, Any], raw: dict[str, Any]
) -> dict[str, Any]:
    """Accept only prose fields from live output; keep authority/evidence deterministic."""
    merged = deepcopy(grounded)
    sections = raw.get("sections") if isinstance(raw.get("sections"), dict) else raw
    if not isinstance(sections, dict):
        return merged
    for key in NARRATIVE_SECTION_KEYS:
        candidate = sections.get(key)
        target = merged.get(key)
        if not isinstance(candidate, dict) or not isinstance(target, dict):
            continue
        summary = candidate.get("summary")
        findings = candidate.get("findings")
        if isinstance(summary, str) and summary.strip():
            target["summary"] = summary.strip()
        if (
            isinstance(findings, list)
            and findings
            and all(isinstance(item, str) and item.strip() for item in findings)
        ):
            target["findings"] = [item.strip() for item in findings]
    return merged


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def compact_unified_for_llm(unified_output: dict[str, Any]) -> dict[str, Any]:
    """Strip heavy / sensitive fields before sending to an LLM."""
    factors_compact = {}
    for fid, factor in (unified_output.get("factors") or {}).items():
        facts = []
        for fact in (factor.get("land_facts") or [])[:12]:
            facts.append(
                {
                    "variable_id": fact.get("variable_id"),
                    "value": fact.get("value"),
                    "unit": fact.get("unit"),
                    "spatial_semantics": fact.get("spatial_semantics"),
                    "source_id": fact.get("source_id"),
                }
            )
        factors_compact[fid] = {
            "human_name": FACTOR_HUMAN.get(fid, fid),
            "signal": factor.get("signal"),
            "input_quality_state": factor.get("input_quality_state"),
            "ranking_effect": factor.get("ranking_effect"),
            "land_facts": facts,
            "limitations": (factor.get("limitations") or [])[:8],
        }
    mireye = []
    for m in unified_output.get("mireye_context") or []:
        mireye.append(
            {
                "context_type": m.get("context_type"),
                "disposition": m.get("disposition"),
                "partial_failures": [
                    {
                        "error_code": pf.get("error_code"),
                        "message": pf.get("message"),
                    }
                    for pf in (m.get("partial_failures") or [])[:3]
                    if isinstance(pf, dict)
                ],
                "limitations": (m.get("limitations") or [])[:4],
                "point_context": True,
            }
        )
    ops = {}
    for oid, op in (unified_output.get("operations") or {}).items():
        ops[oid] = {
            "decision_label": op.get("decision_label"),
            "ranking_permission": op.get("ranking_permission"),
            "limiting_signals": op.get("limiting_signals"),
            "supporting_signals": op.get("supporting_signals"),
            "presentation_priority": op.get("presentation_priority"),
            "confidence_limitation": op.get("confidence_limitation"),
        }
    parcel = unified_output.get("parcel") or {}
    return {
        "match_result_hash": unified_output.get("match_result_hash"),
        "mode": unified_output.get("mode"),
        "intended_operation": unified_output.get("intended_operation"),
        "planned_actions": unified_output.get("planned_actions") or [],
        "parcel": {
            "geometry_id": parcel.get("geometry_id"),
            "jurisdiction": parcel.get("jurisdiction"),
            "geometry_validity": parcel.get("geometry_validity"),
        },
        "factors": factors_compact,
        "operations": ops,
        "cross_profile_comparison": unified_output.get("cross_profile_comparison"),
        "unknowns": (unified_output.get("unknowns") or [])[:30],
        "diligence_actions": [
            (a if isinstance(a, str) else (a.get("action") or a.get("description") or str(a)))
            for a in (unified_output.get("diligence_actions") or [])[:20]
        ],
        "mireye_context": mireye,
        "evidence_index_keys": sorted(build_evidence_index(unified_output).keys())[:200],
    }


def _section(
    heading: str,
    summary: str,
    findings: list[str],
    evidence_refs: list[str] | None = None,
    limitation_refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "heading": heading,
        "summary": summary,
        "findings": findings,
        "evidence_refs": evidence_refs or [],
        "limitation_refs": limitation_refs or [],
    }


def build_fixture_buyer_report(
    unified_output: dict[str, Any],
    *,
    mode: str | None = None,
    intended_operation: str | None = None,
) -> dict[str, Any]:
    """Deterministic buyer-language report used by FIXTURE provider post-process."""
    mode_u = mode or unified_output.get("mode") or "DISCOVERY"
    intended = (
        intended_operation
        if intended_operation is not None
        else unified_output.get("intended_operation")
    )
    idx = build_evidence_index(unified_output)
    factors = unified_output.get("factors") or {}
    ops = unified_output.get("operations") or {}
    parcel = unified_output.get("parcel") or {}
    jur = parcel.get("jurisdiction") or {}
    ranking = bool(
        (unified_output.get("cross_profile_comparison") or {}).get("ranking_permitted")
    )
    mireye = unified_output.get("mireye_context") or []
    blocked = any(m.get("disposition") == "BLOCKED_EXTERNAL" for m in mireye)

    def eref(*keys: str) -> list[str]:
        return [k for k in keys if k in idx]

    hold_line = "HOLD means the evidence is incomplete; it does not mean the land is unsuitable."

    # Executive
    selected = intended if mode_u == "GOAL_DIRECTED" else None
    exec_findings = [
        "Neither cattle nor sheep has been ruled out by the reviewed evidence.",
        "The largest decision gaps are usable forage, reliable livestock water, and confirmed access.",
        hold_line,
    ]
    if selected:
        exec_findings.append(
            "Your selected operation is reviewed first, while the other supported operation "
            "is retained as a comparison."
        )
    else:
        exec_findings.append(
            "Cattle and sheep are reviewed as peers; no best-use choice can be supported yet."
        )
    if blocked:
        exec_findings.append(
            "One supplementary property-data service was unavailable. The report leaves that "
            "information unresolved instead of guessing."
        )

    # Land findings from signals
    land_findings = [
        "Parcel-wide terrain and soil information is available for preliminary screening.",
        "Modeled herbaceous and woody cover describes the land surface, but a field visit is still needed to confirm usable forage.",
        "Mapped water features are leads for investigation, not proof of a reliable livestock-water system.",
    ]

    # Elevation numeric example if present
    elev_ref = next(
        (
            k
            for k, v in idx.items()
            if v.get("variable_id") == "VAR_F01_ELEVATION_MEDIAN_M"
        ),
        None,
    )
    elev_claim = None
    if elev_ref:
        elev_val = idx[elev_ref]["value"]
        elev_claim = {
            "claim_id": "C_ELEV",
            "text": f"Median parcel elevation is approximately {float(elev_val):.0f} m.",
            "claim_type": "FACT",
            "evidence_refs": [elev_ref, "factor:F01_TOPOGRAPHY"],
            "numeric_refs": [elev_ref],
            "certainty": "KNOWN",
            "operation_scope": None,
        }

    op_findings = []
    claims = []
    for oid, op in ops.items():
        label = op.get("decision_label")
        human = "Cow-Calf" if "COW" in oid else "Sheep"
        op_findings.append(
            f"{human}: {label}. The reviewed evidence is not yet complete enough for a confident fit decision."
        )
        claims.append(
            {
                "claim_id": f"C_DEC_{oid}",
                "text": f"{human} decision_label is {label}.",
                "claim_type": "ENGINE_DECISION",
                "evidence_refs": [f"operation:{oid}"],
                "numeric_refs": [],
                "certainty": "KNOWN",
                "operation_scope": oid,
            }
        )
    op_findings.append(
        "The present evidence does not justify choosing cattle over sheep, or sheep over cattle."
    )

    # Unknowns
    unk_findings = [
        "Forage quantity and condition are still uncertain because modeled herbaceous coverage has not been fully checked against the parcel.",
        "A usable livestock-water system is not confirmed; seasonal reliability, capacity, quality, and animal access remain unknown.",
        "A mapped road does not prove legal access or a usable ranch entrance.",
        "Shrub and woody cover is mapped, but its browse value and effect on livestock movement are not confirmed.",
    ]

    diligence_findings = [
        "Inspect every mapped water candidate and confirm year-round reliability, capacity, quality, and livestock access.",
        "Walk representative areas of the parcel with a local range professional to confirm usable forage and woody vegetation.",
        "Review the deed, easements, gates, and road condition to confirm legal and practical access.",
    ]

    method_findings = [
        "The underlying land checks and operation decisions are fixed before this plain-language summary is written.",
        "Missing evidence remains missing; this report does not invent measurements or a fit score.",
    ]
    if blocked:
        method_findings.append(
            "An external service was unavailable, so its information remains an open follow-up item."
        )
    else:
        method_findings.append(
            "Parcel-wide measurements and mapped evidence are the primary basis for this screening."
        )

    evidence_references = []
    for ref_id, item in list(idx.items())[:80]:
        evidence_references.append(
            {
                "ref_id": ref_id,
                "kind": item["kind"],
                "label": item.get("label") or ref_id,
                "factor_id": item.get("factor_id"),
                "variable_id": item.get("variable_id"),
                "value": item.get("value"),
                "unit": item.get("unit"),
                "spatial_semantics": item.get("spatial_semantics"),
                "source_id": item.get("source_id"),
                "point_context": bool(item.get("point_context")),
            }
        )

    for i, u in enumerate((unified_output.get("unknowns") or [])[:12]):
        claims.append(
            {
                "claim_id": f"C_UNK_{i}",
                "text": str(u),
                "claim_type": "UNKNOWN",
                "evidence_refs": [f"unknown:{i}"] if f"unknown:{i}" in idx else [],
                "numeric_refs": [],
                "certainty": "UNKNOWN",
                "operation_scope": None,
            }
        )
    claims.append(
        {
            "claim_id": "C_HOLD_EXPLAIN",
            "text": hold_line,
            "claim_type": "CONTEXT",
            "evidence_refs": [],
            "numeric_refs": [],
            "certainty": "KNOWN",
            "operation_scope": "BOTH",
        }
    )
    if elev_claim:
        claims.insert(0, elev_claim)

    county = jur.get("county")
    state = jur.get("state")
    prop_findings = [
        f"Jurisdiction context: {county or 'unknown county'}, {state or 'unknown state'}."
        if county or state
        else "Jurisdiction identifiers are limited in the current profile.",
        "The parcel boundary was sufficient for the mapped analysis, but it is not a replacement for a survey.",
        "Nearby or intersecting mapped roads do not prove legal access or a usable entrance.",
    ]

    report = {
        "schema_version": BUYER_REPORT_SCHEMA_VERSION,
        "match_result_hash": unified_output.get("match_result_hash"),
        "mode": mode_u,
        "intended_operation": intended,
        "validation_status": "PENDING",
        "validation_violations": [],
        "executive_summary": _section(
            "Executive summary",
            "Continue investigating, but do not make a purchase or operating decision from this screening alone.",
            exec_findings,
            evidence_refs=eref("operation:COW_CALF_OPERATION", "operation:SHEEP_GRAZING"),
        ),
        "property": _section(
            "Property",
            "Parcel identity, configuration, and physical road context.",
            prop_findings,
            evidence_refs=eref("factor:F06_PARCEL_CONFIGURATION", "factor:F07_ROAD_AND_PHYSICAL_ACCESS"),
        ),
        "land_and_resources": _section(
            "Land and resources",
            "The mapped land evidence is useful for screening, but the two most important operating resources—usable forage and dependable water—still need verification.",
            land_findings,
            evidence_refs=eref(
                "factor:F01_TOPOGRAPHY",
                "factor:F02_HERBACEOUS_RESOURCE",
                "factor:F03_LIVESTOCK_WATER",
                "factor:F04_SOIL_WETNESS_ECOLOGICAL_SITE",
                "factor:F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE",
            ),
        ),
        "resilience_and_hazards": _section(
            "Resilience and hazards",
            "Long-term climate context is available, while seasonal conditions and parcel-wide hazards still require additional evidence.",
            [
                "Long-term precipitation context helps frame forage and water risk but does not determine livestock capacity.",
                "Seasonal rainfall patterns and drought history are not yet complete enough for an operating conclusion.",
                "Location-based hazard notes are screening leads and should be confirmed across the full parcel.",
            ]
            + (
                [
                    "A supplementary hazard lookup was unavailable and should not be treated as a cleared risk."
                ]
                if blocked
                else []
            ),
            evidence_refs=eref("factor:F05_CLIMATE_DROUGHT_EXPOSURE"),
        ),
        "operation_comparison": _section(
            "Operation comparison",
            "The evidence is incomplete: both supported operations remain possible, but neither has enough verified evidence for a confident recommendation.",
            op_findings,
            evidence_refs=eref("operation:COW_CALF_OPERATION", "operation:SHEEP_GRAZING"),
        ),
        "key_unknowns": _section(
            "Key unknowns",
            "These questions could materially change the purchase or operating decision.",
            unk_findings,
            evidence_refs=[k for k in idx if k.startswith("unknown:")][:12],
        ),
        "diligence_plan": _section(
            "Diligence plan",
            "Complete these three checks before relying on the operation comparison.",
            diligence_findings,
            evidence_refs=[k for k in idx if k.startswith("diligence:")][:12],
        ),
        "methodology_and_limitations": _section(
            "Methodology and limitations",
            "How RangeMatch keeps the summary tied to reviewed evidence.",
            method_findings,
        ),
        "evidence_references": evidence_references,
        "claim_ledger": claims,
        "report_provenance": {
            "provider": "FIXTURE",
            "model_id": "fixture",
            "prompt_version": BUYER_REPORT_PROMPT_VERSION,
            "generated_at": utc_now_iso(),
            "provider_status": "FIXTURE",
            "match_result_hash": unified_output.get("match_result_hash"),
            "displayable": False,
        },
    }
    return report


def generate_buyer_report(
    unified_output: dict[str, Any],
    *,
    mode: str | None = None,
    intended_operation: str | None = None,
    planned_actions: list[str] | None = None,
    provider_name: str | None = None,
) -> dict[str, Any]:
    if not unified_output or not unified_output.get("match_result_hash"):
        return {
            "schema_version": BUYER_REPORT_SCHEMA_VERSION,
            "match_result_hash": None,
            "mode": mode or "DISCOVERY",
            "intended_operation": intended_operation,
            "validation_status": "FAILED",
            "validation_violations": [
                {
                    "code": "MISSING_UNIFIED_OUTPUT",
                    "message": "validated Unified Output required",
                    "path": "unified_output",
                }
            ],
            "report_provenance": {
                "provider": provider_name or "UNKNOWN",
                "model_id": None,
                "prompt_version": BUYER_REPORT_PROMPT_VERSION,
                "generated_at": utc_now_iso(),
                "provider_status": "FAILED_EXTERNAL",
                "match_result_hash": None,
                "displayable": False,
            },
        }

    provider = get_provider(provider_name)
    compact = compact_unified_for_llm(unified_output)
    compact["requested_mode"] = mode or unified_output.get("mode")
    compact["requested_intended_operation"] = (
        intended_operation
        if intended_operation is not None
        else unified_output.get("intended_operation")
    )
    compact["approved_planned_actions"] = planned_actions or unified_output.get(
        "planned_actions"
    ) or []
    grounded_draft = build_fixture_buyer_report(
        unified_output,
        mode=compact["requested_mode"],
        intended_operation=compact["requested_intended_operation"],
    )
    compact["grounded_report_draft"] = {
        key: {
            "summary": grounded_draft[key]["summary"],
            "findings": grounded_draft[key]["findings"],
        }
        for key in NARRATIVE_SECTION_KEYS
    }

    fixture_key = "buyer_report_cper_template"
    completion = provider.complete_json(
        system=BUYER_SYSTEM,
        user=json.dumps(compact, ensure_ascii=False),
        prompt_version=BUYER_REPORT_PROMPT_VERSION,
        fixture_key=fixture_key if provider.name == "FIXTURE" else None,
    )

    if completion.content is None:
        return {
            "schema_version": BUYER_REPORT_SCHEMA_VERSION,
            "match_result_hash": unified_output.get("match_result_hash"),
            "mode": compact["requested_mode"],
            "intended_operation": compact["requested_intended_operation"],
            "validation_status": "FAILED",
            "validation_violations": [
                {
                    "code": completion.error_code or "LLM_FAILED",
                    "message": completion.error_message or "provider_failed",
                    "path": "report_provenance",
                }
            ],
            "executive_summary": _section("Executive summary", "", []),
            "property": _section("Property", "", []),
            "land_and_resources": _section("Land and resources", "", []),
            "resilience_and_hazards": _section("Resilience and hazards", "", []),
            "operation_comparison": _section("Operation comparison", "", []),
            "key_unknowns": _section("Key unknowns", "", []),
            "diligence_plan": _section("Diligence plan", "", []),
            "methodology_and_limitations": _section("Methodology and limitations", "", []),
            "evidence_references": [],
            "claim_ledger": [],
            "report_provenance": {
                "provider": completion.provider,
                "model_id": completion.model_id,
                "prompt_version": BUYER_REPORT_PROMPT_VERSION,
                "generated_at": completion.generated_at,
                "provider_status": completion.provider_status,
                "match_result_hash": unified_output.get("match_result_hash"),
                "displayable": False,
            },
        }

    # FIXTURE template marker → build grounded report from UO
    raw = completion.content
    if raw.get("_fixture_action") == "BUILD_FROM_UNIFIED_OUTPUT" or provider.name == "FIXTURE":
        report = build_fixture_buyer_report(
            unified_output,
            mode=compact["requested_mode"],
            intended_operation=compact["requested_intended_operation"],
        )
        report["report_provenance"] = {
            "provider": completion.provider,
            "model_id": completion.model_id,
            "prompt_version": BUYER_REPORT_PROMPT_VERSION,
            "generated_at": completion.generated_at,
            "provider_status": completion.provider_status,
            "match_result_hash": unified_output.get("match_result_hash"),
            "displayable": False,
        }
    else:
        report = merge_live_prose_onto_grounded_report(grounded_draft, raw)
        report["schema_version"] = BUYER_REPORT_SCHEMA_VERSION
        report["match_result_hash"] = unified_output.get("match_result_hash")
        report["mode"] = compact["requested_mode"]
        report["intended_operation"] = compact["requested_intended_operation"]
        report["report_provenance"] = {
            "provider": completion.provider,
            "model_id": completion.model_id,
            "prompt_version": BUYER_REPORT_PROMPT_VERSION,
            "generated_at": completion.generated_at,
            "provider_status": completion.provider_status,
            "match_result_hash": unified_output.get("match_result_hash"),
            "displayable": False,
        }

    return validate_buyer_report(report, unified_output=unified_output)
