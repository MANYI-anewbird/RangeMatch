"""Minimal local product surface for the demo Factor closure."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .engine import evaluate_land_profile
from .explanation import FACTOR_LABELS, explain_match_result


SECTION_ORDER = (
    "Parcel Summary",
    "Factor Evidence",
    "Operation Comparison",
    "Unknowns",
    "Diligence Actions",
    "Source Trace",
)

SIGNAL_PLAIN_LANGUAGE = {
    "CONTEXT_DEPENDENT": "Context only — not a positive suitability score",
    "NEEDS_VERIFICATION": "Needs verification — evidence is incomplete or unconfirmed",
    "UNKNOWN": "Unknown — required evidence is missing",
    "HOLD": "Hold screening — not a finding that the land is unsuitable",
}


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _signal_class(signal: str | None) -> str:
    mapping = {
        "CONTEXT_DEPENDENT": "signal-context",
        "NEEDS_VERIFICATION": "signal-verify",
        "UNKNOWN": "signal-unknown",
        "HOLD": "signal-hold",
    }
    return mapping.get(signal or "", "signal-default")


def _factor_coverage(factor: dict[str, Any]) -> str:
    if "parcel_coverage" in factor:
        coverage = factor["parcel_coverage"]
        return (
            f"{coverage.get('status')} "
            f"(fraction={coverage.get('coverage_fraction')})"
        )
    if "coverage" in factor:
        return str(factor["coverage"].get("status"))
    land_facts = factor.get("land_facts") or []
    if land_facts:
        statuses = sorted(
            {
                str((fact.get("coverage") or {}).get("status"))
                for fact in land_facts
            }
        )
        return ", ".join(statuses)
    return str(factor.get("input_quality_state") or "UNKNOWN")


def _unique_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _collect_factor_limitations(factor: dict[str, Any]) -> list[str]:
    items: list[str] = []
    items.extend(factor.get("limitations") or [])
    for fact in factor.get("land_facts") or []:
        items.extend(fact.get("limitations") or [])
    coverage = _factor_coverage(factor)
    if "COVERAGE_UNQUANTIFIED" in coverage:
        items.append(
            "Parcel eligible, masked, no-data, and valid areas are not quantified."
        )
    return _unique_preserve(items)


def _collect_factor_unknowns(
    factor_id: str,
    factor: dict[str, Any],
    global_unknowns: list[str],
) -> list[str]:
    items: list[str] = []
    items.extend(factor.get("unknowns") or [])
    prefix = factor_id.split("_", 1)[0]
    for unknown in global_unknowns:
        text = str(unknown)
        lowered = text.lower()
        if (
            text.startswith(f"{factor_id} ")
            or text.startswith(f"{prefix} ")
            or factor_id.lower() in lowered
        ):
            items.append(text)
            continue
        # Pull clearly Factor-owned verification unknowns into F02 rows.
        if factor_id == "F02_HERBACEOUS_RESOURCE" and any(
            token in lowered
            for token in (
                "botanical composition",
                "palatability",
                "nutritive value",
            )
        ):
            items.append(text)

    coverage = _factor_coverage(factor)
    joined = " ".join(items).lower()
    if "COVERAGE_UNQUANTIFIED" in coverage and "eligible, masked" not in joined:
        items.append(
            f"{prefix} eligible, masked, no-data, and valid parcel areas are not quantified."
        )

    # Collapse near-duplicate coverage unknowns that differ only by Factor id form.
    collapsed: list[str] = []
    seen_coverage = False
    for item in _unique_preserve(items):
        lowered = item.lower()
        if "eligible, masked" in lowered and "valid parcel areas" in lowered:
            if seen_coverage:
                continue
            seen_coverage = True
            collapsed.append(
                f"{prefix} eligible, masked, no-data, and valid parcel areas are not quantified."
            )
            continue
        collapsed.append(item)
    return collapsed


def _source_lines(profile: dict[str, Any]) -> list[str]:
    lines = []
    factors = profile.get("factors") or {}
    for factor_id, factor in factors.items():
        if factor.get("derivation_spec"):
            lines.append(f"{factor_id}: derivation {factor['derivation_spec']}")
        if factor.get("evidence_contract"):
            lines.append(f"{factor_id}: evidence_contract {factor['evidence_contract']}")
        if factor.get("result_reference"):
            lines.append(f"{factor_id}: result {factor['result_reference']}")
        if factor.get("remote_collection_reference"):
            lines.append(
                f"{factor_id}: remote_collection {factor['remote_collection_reference']}"
            )
        if factor.get("five_parcel_remote_collection_reference"):
            lines.append(
                f"{factor_id}: five_parcel_remote_collection "
                f"{factor['five_parcel_remote_collection_reference']}"
            )
        for ref in factor.get("source_fixture_references") or []:
            lines.append(f"{factor_id}: fixture {ref}")
        for fact in factor.get("land_facts") or []:
            provenance = fact.get("provenance") or {}
            lines.append(
                f"{factor_id}/{fact.get('variable_id')}: "
                f"{provenance.get('source_reference')} @ {provenance.get('fetched_at')}"
            )
        provenance = factor.get("provenance") or {}
        if provenance:
            lines.append(
                f"{factor_id}: {provenance.get('source_reference')} "
                f"hash={provenance.get('response_or_artifact_hash')}"
            )
        synthetic = (factor.get("remote_evidence_summary") or {}).get(
            "synthetic_field_evidence_demo"
        )
        if isinstance(synthetic, dict) and synthetic.get("reference"):
            lines.append(
                f"{factor_id}: synthetic_field_evidence_demo "
                f"{synthetic['reference']} (TEST_ONLY; not live CPER evidence)"
            )
    return lines


def _f03_evidence_summary_lines(source_factor: dict[str, Any]) -> list[str]:
    summary = source_factor.get("remote_evidence_summary") or {}
    if not summary:
        return []
    lines = [
        f"total mapped candidates: {summary.get('total_mapped_candidates')}",
        (
            "deterministically sampled for remote review: "
            f"{summary.get('deterministically_sampled_for_remote_review')}"
        ),
        f"remotely supported: {summary.get('remotely_supported')}",
        f"sampled but still mapped: {summary.get('sampled_but_still_mapped')}",
        f"field verified: {summary.get('field_verified')}",
        f"sample coverage limitation: {summary.get('sample_coverage_limitation')}",
        f"Factor state: {summary.get('factor_state') or source_factor.get('input_quality_state')}",
        f"signal: {summary.get('signal') or 'NEEDS_VERIFICATION'}",
        f"ranking_effect: {summary.get('ranking_effect') or 'NONE'}",
    ]
    lines.extend(source_factor.get("demo_statements") or [])
    return lines


def build_demo_closure_payload(
    land_profile: dict[str, Any],
    match_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the demo closure payload from profile and MatchResult."""
    result = match_result or evaluate_land_profile(land_profile)
    explanation = explain_match_result(result, land_profile)
    factors = land_profile.get("factors") or {}
    first_operation = next(iter((result.get("operation_results") or {}).values()), {})
    factor_evaluations = first_operation.get("factor_evaluations") or {}

    global_unknowns = list(result.get("unknowns") or [])
    factor_evidence = []
    for factor_id, evaluation in factor_evaluations.items():
        source_factor = factors.get(factor_id) or {}
        signal = evaluation.get("signal")
        row = {
            "factor_id": factor_id,
            "label": FACTOR_LABELS.get(factor_id, factor_id),
            "signal": signal,
            "signal_plain_language": SIGNAL_PLAIN_LANGUAGE.get(signal, signal),
            "ranking_effect": evaluation.get("ranking_effect"),
            "explanation_code": evaluation.get("explanation_code"),
            "input_quality_state": evaluation.get("input_quality_state")
            or source_factor.get("input_quality_state"),
            "coverage": _factor_coverage(source_factor),
            "limitations": _collect_factor_limitations(source_factor),
            "unknowns": _collect_factor_unknowns(
                factor_id, source_factor, global_unknowns
            ),
        }
        if factor_id == "F03_LIVESTOCK_WATER":
            row["evidence_summary"] = _f03_evidence_summary_lines(source_factor)
            row["remote_evidence_summary"] = source_factor.get("remote_evidence_summary")
            row["field_verified_count"] = source_factor.get("field_verified_count", 0)
            row["mapped_candidate_count"] = source_factor.get("mapped_candidate_count")
        factor_evidence.append(row)

    return {
        "demo_closure_version": "0.1.0",
        "sections": list(SECTION_ORDER),
        "parcel_summary": {
            "land_profile_id": land_profile.get("land_profile_id"),
            "version": land_profile.get("version"),
            "geometry_id": land_profile.get("geometry_id"),
            "geometry_reference": land_profile.get("geometry_reference"),
            "geometry_hash": land_profile.get("geometry_hash"),
            "supported_use": land_profile.get("supported_use"),
            "geometry_role": "ENGINEERING_TEST_GEOMETRY",
            "purchasable_parcel": False,
            "input_sha256": result.get("input_sha256"),
            "engine_version": result.get("engine_version"),
        },
        "factor_evidence": factor_evidence,
        "operation_comparison": explanation["operation_summaries"],
        "cross_profile_comparison": result.get("cross_profile_comparison"),
        "unknowns": result.get("unknowns") or [],
        "diligence_actions": result.get("diligence_actions") or [],
        "source_trace": _source_lines(land_profile),
        "explanation": explanation,
        "match_result": result,
    }


def render_demo_html(payload: dict[str, Any]) -> str:
    """Render a minimal local HTML product surface."""
    parcel = payload["parcel_summary"]
    rows = []
    for factor in payload["factor_evidence"]:
        limitations = "".join(f"<li>{_esc(item)}</li>" for item in factor["limitations"])
        unknowns = "".join(f"<li>{_esc(item)}</li>" for item in factor["unknowns"])
        evidence_summary = ""
        if factor.get("evidence_summary"):
            summary_items = "".join(
                f"<li>{_esc(item)}</li>" for item in factor["evidence_summary"]
            )
            evidence_summary = (
                f"<div class='evidence-summary'><strong>Evidence summary</strong>"
                f"<ul>{summary_items}</ul></div>"
            )
        rows.append(
            f"""
            <tr>
              <td>
                <strong>{_esc(factor['label'])}</strong><br />
                <code>{_esc(factor['factor_id'])}</code>
                {evidence_summary}
              </td>
              <td>
                <span class="pill {_signal_class(factor['signal'])}">{_esc(factor['signal'])}</span>
                <div class="plain">{_esc(factor['signal_plain_language'])}</div>
              </td>
              <td>{_esc(factor['ranking_effect'])}</td>
              <td>{_esc(factor['coverage'])}</td>
              <td><ul>{limitations or '<li>No additional Factor-specific limitations recorded</li>'}</ul></td>
              <td><ul>{unknowns or '<li>No additional Factor-specific unknowns recorded</li>'}</ul></td>
            </tr>
            """
        )

    operations = []
    for operation in payload["operation_comparison"]:
        factor_bits = "".join(
            f"<li>{_esc(item['label'])}: "
            f"<span class='pill {_signal_class(item['signal'])}'>{_esc(item['signal'])}</span>"
            f" / ranking={_esc(item['ranking_effect'])}</li>"
            for item in operation["factors"]
        )
        operations.append(
            f"""
            <article class="operation">
              <h3>{_esc(operation['label'])}</h3>
              <p><span class="pill {_signal_class(operation['decision_label'])}">{_esc(operation['decision_label'])}</span></p>
              <p>{_esc(operation['decision_reason'])}</p>
              <ul>{factor_bits}</ul>
            </article>
            """
        )

    unknowns = "".join(f"<li>{_esc(item)}</li>" for item in payload["unknowns"])
    diligence = "".join(f"<li>{_esc(item)}</li>" for item in payload["diligence_actions"])
    sources = "".join(f"<li><code>{_esc(item)}</code></li>" for item in payload["source_trace"])
    narrative = "".join(
        f"<li>{_esc(item)}</li>"
        for item in payload["explanation"]["narrative_constraints"]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RangeMatch Demo Closure — {_esc(parcel['land_profile_id'])}</title>
  <style>
    :root {{
      --ink: #1d2a24;
      --muted: #5c6b63;
      --paper: #f3efe6;
      --panel: #fffdf8;
      --line: #c9c1b3;
      --context: #5f5a52;
      --verify: #8a5a17;
      --unknown: #5a5a5a;
      --hold: #6b3f2a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", Palatino, serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(47,93,80,0.08), transparent 40%),
        linear-gradient(180deg, #e7e0d2 0%, var(--paper) 35%, #efe9dc 100%);
    }}
    main {{
      width: min(1100px, calc(100% - 2rem));
      margin: 1.5rem auto 3rem;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      padding-bottom: 1rem;
      margin-bottom: 1.5rem;
    }}
    h1, h2, h3 {{
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      letter-spacing: 0.01em;
      margin: 0 0 0.6rem;
    }}
    h1 {{ font-size: 1.8rem; }}
    h2 {{
      font-size: 1.1rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-top: 2rem;
    }}
    p, li, td, th {{ font-size: 0.98rem; line-height: 1.45; }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      padding: 1rem 1.1rem;
      margin-top: 0.75rem;
    }}
    .meta {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 0.75rem;
    }}
    .meta div {{
      border-top: 1px solid var(--line);
      padding-top: 0.45rem;
    }}
    .meta span {{
      display: block;
      color: var(--muted);
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.9rem;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      padding: 0.65rem 0.4rem;
    }}
    th {{
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
    }}
    ul {{ margin: 0.2rem 0 0.2rem 1.1rem; padding: 0; }}
    .pill {{
      display: inline-block;
      padding: 0.15rem 0.45rem;
      border: 1px solid currentColor;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-size: 0.75rem;
      letter-spacing: 0.04em;
    }}
    .signal-context {{ color: var(--context); }}
    .signal-verify {{ color: var(--verify); }}
    .signal-unknown {{ color: var(--unknown); }}
    .signal-hold {{ color: var(--hold); }}
    .operations {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 0.9rem;
    }}
    .disclaimer {{
      margin-top: 1rem;
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .callout {{
      background: #fff7e8;
      border: 1px solid #d2b48c;
      padding: 0.85rem 1rem;
      margin: 0.9rem 0 0;
    }}
    .plain {{
      margin-top: 0.35rem;
      color: var(--muted);
      font-size: 0.86rem;
    }}
    .evidence-summary {{
      margin-top: 0.55rem;
      padding: 0.45rem 0.55rem;
      background: #f7f2e8;
      border: 1px solid var(--line);
      font-size: 0.84rem;
    }}
    .evidence-summary ul {{
      margin: 0.35rem 0 0;
      padding-left: 1.1rem;
    }}
    code {{
      font-family: "SFMono-Regular", Menlo, Consolas, monospace;
      font-size: 0.82rem;
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>RangeMatch</h1>
      <p>Five-Factor demo closure — preliminary screening, deterministic evaluation only.</p>
      <div class="callout">
        <strong>HOLD does not mean the land is unsuitable.</strong>
        It means the current reviewed evidence is incomplete for an ADVANCE, REDIRECT, or REJECT decision.
        <br /><br />
        <strong>CONTEXT_DEPENDENT is not a positive score.</strong>
        It means the Factor provides reviewed context and still depends on other conditions.
        <br /><br />
        This geometry is an <strong>engineering test polygon</strong>, not a real purchasable ranch parcel.
      </div>
      <p class="disclaimer">{_esc(payload['explanation']['disclaimer'])}</p>
    </header>

    <section>
      <h2>Parcel Summary</h2>
      <div class="panel meta">
        <div><span>Profile</span>{_esc(parcel['land_profile_id'])}</div>
        <div><span>Geometry</span>{_esc(parcel['geometry_id'])}</div>
        <div><span>Geometry role</span>{_esc(parcel['geometry_role'])}</div>
        <div><span>Purchasable parcel</span>{_esc(parcel['purchasable_parcel'])}</div>
        <div><span>Supported use</span>{_esc(parcel['supported_use'])}</div>
        <div><span>Engine</span>{_esc(parcel['engine_version'])}</div>
        <div><span>Input hash</span><code>{_esc(parcel['input_sha256'])}</code></div>
        <div><span>Geometry file</span><code>{_esc(parcel['geometry_reference'])}</code></div>
      </div>
    </section>

    <section>
      <h2>Factor Evidence</h2>
      <div class="panel" style="overflow-x:auto;">
        <p class="plain">Signals describe evidence quality and reviewed context. They are not carrying capacity or profitability.</p>
        <table>
          <thead>
            <tr>
              <th>Factor</th>
              <th>Signal</th>
              <th>Ranking effect</th>
              <th>Coverage</th>
              <th>Limitations</th>
              <th>Unknowns</th>
            </tr>
          </thead>
          <tbody>
            {''.join(rows)}
          </tbody>
        </table>
      </div>
    </section>

    <section>
      <h2>Operation Comparison</h2>
      <div class="panel">
        <p><strong>Peer evaluation:</strong> Cow-Calf and Sheep are shown side by side. Neither is primary.</p>
        <p>Ranking permitted:
          <strong>{_esc(payload['cross_profile_comparison'].get('ranking_permitted'))}</strong>
          — {_esc(payload['cross_profile_comparison'].get('reason'))}
        </p>
        <div class="operations">{''.join(operations)}</div>
      </div>
    </section>

    <section id="unknowns">
      <h2>Unknowns</h2>
      <div class="panel">
        <p class="plain">These items remain unresolved and should guide field or records diligence.</p>
        <ul>{unknowns or '<li>None recorded</li>'}</ul>
      </div>
    </section>

    <section>
      <h2>Diligence Actions</h2>
      <div class="panel"><ul>{diligence or '<li>None recorded</li>'}</ul></div>
    </section>

    <section>
      <h2>Source Trace</h2>
      <div class="panel"><ul>{sources or '<li>None recorded</li>'}</ul></div>
    </section>

    <section>
      <h2>Constrained Explanation</h2>
      <div class="panel">
        <p>Bound to MatchResult <code>{_esc(payload['explanation']['bound_to_input_sha256'])}</code>.
        LLM override permitted: <strong>false</strong>.</p>
        <ul>{narrative}</ul>
      </div>
    </section>
  </main>
</body>
</html>
"""


def write_demo_closure(
    profile_path: str | Path,
    *,
    html_output: str | Path | None = None,
    json_output: str | Path | None = None,
) -> dict[str, Any]:
    """Evaluate a profile and write the demo closure artifacts."""
    profile_path = Path(profile_path)
    profile = json.loads(profile_path.read_text())
    match_result = evaluate_land_profile(profile)
    payload = build_demo_closure_payload(profile, match_result)

    if json_output is None:
        json_output = profile_path.with_name(profile_path.stem + "_demo_closure.json")
    if html_output is None:
        html_output = profile_path.with_name(profile_path.stem + "_demo_closure.html")

    Path(json_output).write_text(json.dumps(payload, indent=2) + "\n")
    Path(html_output).write_text(render_demo_html(payload))
    return payload
