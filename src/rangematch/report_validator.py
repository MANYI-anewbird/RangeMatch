"""Deterministic Buyer Report validator.

Reports are not displayable until validation_status == PASSED.

Trusted evidence IDs come only from Unified Output. Report-supplied
evidence_references never expand the trusted set.
"""

from __future__ import annotations

import math
import re
from typing import Any

FACTOR_HUMAN = {
    "F01_TOPOGRAPHY": "topography",
    "F02_HERBACEOUS_RESOURCE": "herbaceous forage",
    "F03_LIVESTOCK_WATER": "livestock water",
    "F04_SOIL_WETNESS_ECOLOGICAL_SITE": "soil / ecological site",
    "F05_CLIMATE_DROUGHT_EXPOSURE": "climate / drought exposure",
    "F06_PARCEL_CONFIGURATION": "parcel configuration",
    "F07_ROAD_AND_PHYSICAL_ACCESS": "road / physical access",
    "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE": "woody / shrub structure",
}

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

PROHIBITED_PATTERNS = [
    (
        r"\bcarrying\s+capacity\s+(is|of|equals|=|:|at\s+least|about)\b",
        "PROHIBITED_CARRYING_CAPACITY",
    ),
    (r"\bAUM\b", "PROHIBITED_CARRYING_CAPACITY"),
    (r"\bprofitab", "PROHIBITED_PROFITABILITY"),
    (r"\bROI\b", "PROHIBITED_PROFITABILITY"),
    (r"\blegally\s+compliant\b", "PROHIBITED_LEGAL_COMPLIANCE"),
    (r"\bpermit\s+not\s+required\b", "PROHIBITED_PERMIT_CERTAINTY"),
    (r"\bno\s+permit\s+(is\s+)?needed\b", "PROHIBITED_PERMIT_CERTAINTY"),
    (r"\bwater\s+rights?\s+(are|is)\s+(secure|certain|confirmed)\b", "PROHIBITED_WATER_RIGHTS"),
    (r"\bbest\s+(land\s+)?use\b", "PROHIBITED_BEST_USE"),
    (
        r"\bsuitability\s+score\s+(is|of|equals|=|:|\d)",
        "PROHIBITED_SUITABILITY_SCORE",
    ),
    (r"\brank(?:ed|ing)\s+(#|number|as)\s*1\b", "PROHIBITED_RANKING"),
    (
        r"\bHOLD\b(?![^.!?\n]*(?:\bincomplete\s+evidence\b|\bevidence\s+is\s+incomplete\b))[^.!?\n]{0,80}\b(?:is\s+unsuitable|unsuitable\s+for|not\s+suitable)\b",
        "PROHIBITED_HOLD_AS_UNSUITABLE",
    ),
]

MATERIAL_UNKNOWN_HINTS = {
    "F02": [r"F02", r"herbaceous", r"forage", r"coverage", r"eligible"],
    "F03": [r"F03", r"water", r"livestock\s+water"],
    "F07": [r"F07", r"legal\s+access", r"entrance", r"landlocked"],
    "F08": [r"F08", r"woody", r"shrub", r"browse"],
}

# Digits must not be glued to alphanumerics (avoids F02 → 2, EPSG4326 false splits).
_NUMERIC_RE = re.compile(r"(?<![A-Za-z0-9_/])(-?\d+(?:\.\d+)?)(?![A-Za-z0-9_])")


def build_evidence_index(unified_output: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Compact evidence index for grounding (no secrets / cache paths)."""
    index: dict[str, dict[str, Any]] = {}
    for fid, factor in (unified_output.get("factors") or {}).items():
        index[f"factor:{fid}"] = {
            "ref_id": f"factor:{fid}",
            "kind": "FACTOR",
            "label": FACTOR_HUMAN.get(fid, fid),
            "factor_id": fid,
            "signal": factor.get("signal"),
            "input_quality_state": factor.get("input_quality_state"),
            "point_context": False,
        }
        for i, fact in enumerate(factor.get("land_facts") or []):
            vid = fact.get("variable_id") or f"fact_{i}"
            ref = f"land_fact:{fid}:{vid}"
            index[ref] = {
                "ref_id": ref,
                "kind": "LAND_FACT",
                "label": vid,
                "factor_id": fid,
                "variable_id": vid,
                "value": fact.get("value"),
                "unit": fact.get("unit"),
                "spatial_semantics": fact.get("spatial_semantics"),
                "source_id": fact.get("source_id"),
                "point_context": str(fact.get("spatial_semantics") or "").startswith(
                    "point"
                ),
            }
    for oid, op in (unified_output.get("operations") or {}).items():
        index[f"operation:{oid}"] = {
            "ref_id": f"operation:{oid}",
            "kind": "OPERATION",
            "label": oid,
            "decision_label": op.get("decision_label"),
            "ranking_permission": op.get("ranking_permission"),
            "point_context": False,
        }
    for i, unk in enumerate(unified_output.get("unknowns") or []):
        index[f"unknown:{i}"] = {
            "ref_id": f"unknown:{i}",
            "kind": "UNKNOWN",
            "label": str(unk)[:200],
            "point_context": False,
        }
    for i, lim in enumerate(
        (unified_output.get("constraints") or {}).get("limitations")
        or unified_output.get("limitations")
        or []
    ):
        index[f"limitation:{i}"] = {
            "ref_id": f"limitation:{i}",
            "kind": "LIMITATION",
            "label": str(lim)[:200],
            "point_context": False,
        }
    for i, m in enumerate(unified_output.get("mireye_context") or []):
        index[f"mireye:{i}"] = {
            "ref_id": f"mireye:{i}",
            "kind": "MIREYE_CONTEXT",
            "label": str(m.get("context_type")),
            "disposition": m.get("disposition"),
            "point_context": True,
        }
    for i, act in enumerate(unified_output.get("diligence_actions") or []):
        index[f"diligence:{i}"] = {
            "ref_id": f"diligence:{i}",
            "kind": "DILIGENCE",
            "label": str(act)[:200]
            if not isinstance(act, dict)
            else str(act.get("action") or act.get("description") or act)[:200],
            "point_context": False,
        }
    return index


def _collect_report_text(report: dict[str, Any]) -> str:
    chunks: list[str] = []
    for key in NARRATIVE_SECTION_KEYS:
        sec = report.get(key) or {}
        chunks.append(str(sec.get("summary") or ""))
        chunks.extend(str(x) for x in (sec.get("findings") or []))
    for claim in report.get("claim_ledger") or []:
        chunks.append(str(claim.get("text") or ""))
    return "\n".join(chunks)


def _numeric_tokens(text: str) -> list[float]:
    vals: list[float] = []
    for m in _NUMERIC_RE.finditer(text or ""):
        try:
            vals.append(float(m.group(1)))
        except ValueError:
            continue
    return vals


def _close(a: float, b: float, *, rel: float = 0.02, abs_tol: float = 0.05) -> bool:
    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_tol)


def _is_exempt_number(n: float) -> bool:
    if n.is_integer() and 1900 <= n <= 2100:
        return True
    if n in (0.0, 1.0, 2.0):
        return True
    return False


def _number_matches_land_fact(
    n: float,
    item: dict[str, Any],
    *,
    formatting_tolerance: float,
) -> bool:
    """Approved display conversions: identity/rounding; fraction→percent."""
    if item.get("kind") != "LAND_FACT":
        return False
    val = item.get("value")
    if not isinstance(val, (int, float)):
        return False
    fv = float(val)
    if _close(n, fv, rel=formatting_tolerance):
        return True
    unit = str(item.get("unit") or "").lower()
    # Contract-approved: fraction / unitless 0–1 → percent display.
    if unit in ("fraction", "frac", "1", "ratio", "") or (0.0 <= fv <= 1.0):
        if 0.0 <= fv <= 1.0 and _close(n, fv * 100.0, rel=formatting_tolerance):
            return True
    return False


def _iter_buyer_visible_text_units(
    report: dict[str, Any],
) -> list[tuple[str, str, list[str], str | None]]:
    """Yield (path, text, numeric_refs, claim_type)."""
    units: list[tuple[str, str, list[str], str | None]] = []
    for key in NARRATIVE_SECTION_KEYS:
        sec = report.get(key) or {}
        summary = str(sec.get("summary") or "")
        if summary.strip():
            units.append((f"{key}.summary", summary, [], None))
        for i, finding in enumerate(sec.get("findings") or []):
            units.append((f"{key}.findings[{i}]", str(finding), [], None))
    for claim in report.get("claim_ledger") or []:
        units.append(
            (
                f"claim_ledger.{claim.get('claim_id')}",
                str(claim.get("text") or ""),
                [str(x) for x in (claim.get("numeric_refs") or [])],
                str(claim.get("claim_type") or "") or None,
            )
        )
    return units


def validate_buyer_report(
    report: dict[str, Any],
    *,
    unified_output: dict[str, Any],
    formatting_tolerance: float = 0.02,
) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    evidence_index = build_evidence_index(unified_output)
    # Trusted IDs: Unified Output only. Never trust report.evidence_references.
    trusted_refs = set(evidence_index.keys())

    for er in report.get("evidence_references") or []:
        rid = er.get("ref_id") if isinstance(er, dict) else None
        if rid and rid not in trusted_refs:
            violations.append(
                {
                    "code": "FABRICATED_EVIDENCE_REF",
                    "message": (
                        f"evidence_references declares untrusted id {rid}; "
                        "trusted IDs come only from Unified Output"
                    ),
                    "path": "evidence_references",
                }
            )

    # --- Authority ---
    uo_hash = unified_output.get("match_result_hash")
    if report.get("match_result_hash") != uo_hash:
        violations.append(
            {
                "code": "AUTHORITY_HASH_MISMATCH",
                "message": "report match_result_hash must equal Unified Output",
                "path": "match_result_hash",
            }
        )

    ops = unified_output.get("operations") or {}
    ranking = bool(
        (unified_output.get("cross_profile_comparison") or {}).get("ranking_permitted")
    )
    for oid, op in ops.items():
        expected = op.get("decision_label")
        for claim in report.get("claim_ledger") or []:
            if claim.get("claim_type") != "ENGINE_DECISION":
                continue
            scope = claim.get("operation_scope")
            if scope not in (oid, "BOTH", None):
                continue
            text = str(claim.get("text") or "")
            if expected and expected not in text and claim.get("operation_scope") == oid:
                violations.append(
                    {
                        "code": "AUTHORITY_DECISION_MISMATCH",
                        "message": f"{oid} decision must remain {expected}",
                        "path": f"claim_ledger.{claim.get('claim_id')}",
                    }
                )

    text_all = _collect_report_text(report)
    if not ranking and re.search(
        r"\branking_permitted\s*[:=]\s*true\b|\branked\s+above\b|\bbetter\s+than\b.{0,40}\brank",
        text_all,
        flags=re.I,
    ):
        violations.append(
            {
                "code": "AUTHORITY_RANKING_MISMATCH",
                "message": "ranking_permitted is false; report must not claim ranking",
                "path": "operation_comparison",
            }
        )

    factors = unified_output.get("factors") or {}
    for claim in report.get("claim_ledger") or []:
        if claim.get("claim_type") != "FACT":
            continue
        for ref in claim.get("evidence_refs") or []:
            if not str(ref).startswith("factor:"):
                continue
            fid = str(ref).split(":", 1)[1]
            if fid in factors:
                sig = factors[fid].get("signal")
                if sig and re.search(
                    r"\b(ADVANCE|REJECT)\b", str(claim.get("text") or "")
                ):
                    violations.append(
                        {
                            "code": "AUTHORITY_FACTOR_SIGNAL",
                            "message": f"factor claim must not invent pass/fail beyond signal {sig}",
                            "path": f"claim_ledger.{claim.get('claim_id')}",
                        }
                    )

    op_section = " ".join(
        [
            str((report.get("operation_comparison") or {}).get("summary") or ""),
            *[
                str(x)
                for x in ((report.get("operation_comparison") or {}).get("findings") or [])
            ],
        ]
    )
    for oid, op in ops.items():
        label = op.get("decision_label")
        if label and label not in op_section and label not in text_all:
            violations.append(
                {
                    "code": "AUTHORITY_DECISION_MISSING",
                    "message": f"decision_label {label} for {oid} missing from report",
                    "path": "operation_comparison",
                }
            )

    # --- Evidence grounding (UO-trusted IDs only) ---
    def _check_refs(refs: list[Any], *, path: str) -> None:
        for ref in refs:
            if ref not in trusted_refs:
                violations.append(
                    {
                        "code": "EVIDENCE_REF_UNRESOLVED",
                        "message": f"unresolved evidence_ref {ref}",
                        "path": path,
                    }
                )

    for key in NARRATIVE_SECTION_KEYS:
        sec = report.get(key) or {}
        _check_refs(sec.get("evidence_refs") or [], path=f"{key}.evidence_refs")
        _check_refs(sec.get("limitation_refs") or [], path=f"{key}.limitation_refs")

    for claim in report.get("claim_ledger") or []:
        _check_refs(
            claim.get("evidence_refs") or [],
            path=f"claim_ledger.{claim.get('claim_id')}.evidence_refs",
        )

    if re.search(r"https?://", text_all):
        allowed_urls = set()
        for item in evidence_index.values():
            for v in item.values():
                if isinstance(v, str) and v.startswith("http"):
                    allowed_urls.add(v)
        for m in re.finditer(r"https?://[^\s)\"']+", text_all):
            if m.group(0) not in allowed_urls:
                violations.append(
                    {
                        "code": "FABRICATED_URL",
                        "message": "report must not invent source URLs",
                        "path": "claim_ledger",
                    }
                )
                break

    # --- Numeric grounding across all buyer-visible text ---
    uo_unknown_texts = {str(u) for u in (unified_output.get("unknowns") or [])}

    for path, text, numeric_refs, claim_type in _iter_buyer_visible_text_units(report):
        if claim_type == "UNKNOWN":
            continue
        if text in uo_unknown_texts:
            # Verbatim Engine unknown may contain digits; do not require LLM numeric_refs.
            continue

        nums = [n for n in _numeric_tokens(text) if not _is_exempt_number(n)]
        if not nums:
            continue

        if not numeric_refs:
            violations.append(
                {
                    "code": "NUMERIC_UNGROUNDED",
                    "message": "buyer-visible numeric claim requires numeric_refs to a Land Fact",
                    "path": path,
                }
            )
            continue

        for nref in numeric_refs:
            if nref not in trusted_refs:
                violations.append(
                    {
                        "code": "NUMERIC_REF_UNRESOLVED",
                        "message": f"unresolved numeric_ref {nref}",
                        "path": path,
                    }
                )
                continue
            if (evidence_index.get(nref) or {}).get("kind") != "LAND_FACT":
                violations.append(
                    {
                        "code": "NUMERIC_REF_NOT_LAND_FACT",
                        "message": f"numeric_ref {nref} must resolve to a canonical Land Fact",
                        "path": path,
                    }
                )

        land_refs = [
            r
            for r in numeric_refs
            if (evidence_index.get(r) or {}).get("kind") == "LAND_FACT"
        ]
        if not land_refs:
            continue

        for n in nums:
            ok = any(
                _number_matches_land_fact(
                    n,
                    evidence_index[r],
                    formatting_tolerance=formatting_tolerance,
                )
                for r in land_refs
                if r in evidence_index
            )
            if not ok:
                violations.append(
                    {
                        "code": "NUMERIC_VALUE_MISMATCH",
                        "message": (
                            f"numeric value {n} does not match referenced Land Fact "
                            "value/unit (or approved fraction→percent conversion)"
                        ),
                        "path": path,
                    }
                )

    # --- Unknown preservation ---
    unknowns_text = " ".join(
        [
            str((report.get("key_unknowns") or {}).get("summary") or ""),
            *[
                str(x)
                for x in ((report.get("key_unknowns") or {}).get("findings") or [])
            ],
        ]
    )
    uo_unknowns = " ".join(str(u) for u in (unified_output.get("unknowns") or []))
    for key, patterns in MATERIAL_UNKNOWN_HINTS.items():
        present_in_uo = any(
            re.search(p, uo_unknowns, flags=re.I) for p in patterns
        ) or any(
            key in fid
            for fid, fac in factors.items()
            if fac.get("signal") in ("NEEDS_VERIFICATION", "UNKNOWN") and key in fid
        )
        if not present_in_uo:
            continue
        if not any(re.search(p, unknowns_text, flags=re.I) for p in patterns):
            violations.append(
                {
                    "code": "UNKNOWN_OMITTED",
                    "message": f"material unknown related to {key} omitted",
                    "path": "key_unknowns",
                }
            )

    mireye = unified_output.get("mireye_context") or []
    blocked = any(m.get("disposition") == "BLOCKED_EXTERNAL" for m in mireye)
    if blocked and not re.search(
        r"BLOCKED_EXTERNAL|external\s+(service|data)\s+(was\s+)?(?:blocked|unavailable)|"
        r"third-party\s+property\s+context\s+(?:was\s+)?unavailable",
        text_all,
        flags=re.I,
    ):
        violations.append(
            {
                "code": "MIREYE_BLOCKED_OMITTED",
                "message": "BLOCKED_EXTERNAL Mireye state must be disclosed in plain language",
                "path": "methodology_and_limitations",
            }
        )
    if blocked and re.search(
        r"\bMireye\b.{0,40}\b(succeeded|complete|live\s+success)\b",
        text_all,
        flags=re.I,
    ):
        violations.append(
            {
                "code": "MIREYE_FALSE_SUCCESS",
                "message": "must not claim live Mireye success when BLOCKED_EXTERNAL",
                "path": "methodology_and_limitations",
            }
        )

    # --- Prohibited claims (skip verbatim Engine UNKNOWN rows) ---
    scan_chunks: list[str] = []
    for key in NARRATIVE_SECTION_KEYS:
        sec = report.get(key) or {}
        scan_chunks.append(str(sec.get("summary") or ""))
        scan_chunks.extend(str(x) for x in (sec.get("findings") or []))
    for claim in report.get("claim_ledger") or []:
        if claim.get("claim_type") == "UNKNOWN":
            continue
        scan_chunks.append(str(claim.get("text") or ""))
    prohibited_scan = "\n".join(scan_chunks)

    for pattern, code in PROHIBITED_PATTERNS:
        if re.search(pattern, prohibited_scan, flags=re.I):
            violations.append(
                {
                    "code": code,
                    "message": f"prohibited claim matched /{pattern}/",
                    "path": "claim_ledger",
                }
            )

    if any(op.get("decision_label") == "HOLD" for op in ops.values()):
        if not re.search(
            r"incomplete\s+evidence|evidence\s+is\s+incomplete|not\s+that\s+the\s+land\s+is\s+unsuitable",
            text_all,
            flags=re.I,
        ):
            violations.append(
                {
                    "code": "HOLD_EXPLANATION_MISSING",
                    "message": "HOLD must be explained as incomplete evidence, not unsuitable land",
                    "path": "operation_comparison",
                }
            )

    for key in (
        *NARRATIVE_SECTION_KEYS,
        "evidence_references",
        "claim_ledger",
        "report_provenance",
    ):
        if key not in report:
            violations.append(
                {
                    "code": "SECTION_MISSING",
                    "message": f"missing section {key}",
                    "path": key,
                }
            )

    status = "PASSED" if not violations else "FAILED"
    out = dict(report)
    out["validation_status"] = status
    out["validation_violations"] = violations
    prov = dict(out.get("report_provenance") or {})
    prov["displayable"] = status == "PASSED"
    prov["match_result_hash"] = uo_hash
    out["report_provenance"] = prov
    return out
