"""Phase 7: Natural Cattle Foundation two-page PDF.

Page 1 renders validated Phase 6 interpretation fields verbatim.
Page 2 renders Combined Packet buyer-visible evidence + optional property context.
No second LLM pass. No re-summarization of the judgment.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Mapping

from rangematch.advisor_property_context_appendix import (
    MAXIMUM_ROWS,
    PAGE1_APPENDIX_POINTER,
    project_additional_property_context,
)
from rangematch.environmental_evidence_packet import buyer_visible_observations
from rangematch.natural_cattle_profile import BUYER_LABELS

REPORT_SCHEMA = "RANGEMATCH_NATURAL_CATTLE_FOUNDATION_REPORT@1.0.0"

STATUS_LABELS = {
    "PROMISING_NATURAL_FOUNDATION": "Promising natural foundation",
    "CONDITIONAL_NATURAL_FOUNDATION": "Conditional natural foundation",
    "ENVIRONMENTALLY_CONSTRAINED": "Environmentally constrained",
    "INSUFFICIENT_ENVIRONMENTAL_EVIDENCE": "Environmental picture is not yet sufficient",
}

OPERATION_LABELS = {
    "SEASONAL_GRAZING": "seasonal grazing",
    "YEAR_ROUND_COW_CALF": "year-round cow-calf",
    "OTHER": "other cattle use",
    "UNKNOWN": "cattle use not yet specified",
}

SPATIAL_LABELS = {
    "PARCEL": "Parcel-wide",
    "POINT": "Point sample",
    "CONTEXT": "Nearby / context",
}

PROVIDER_LABELS = {
    "MIREYE": "Mireye",
    "RANGEMATCH_SUPPLEMENT": "RangeMatch supplement",
    "RANGEMATCH_CORE": "Confirmed geometry",
}

# The appendix is not an arbitrary first-N dump. These buyer-relevant fields
# are displayed first so the evidence used by Page 1 remains visible on Page 2.
APPENDIX_PRIORITY_TERMS = (
    "area",
    "acre",
    "slope median",
    "slope",
    "elevation",
    "land use",
    "ndvi",
    "production",
    "tree canopy",
    "precip",
    "drought",
    "temperature",
    "wetland acres",
    "wetland fraction",
    "surface water permanence",
    "soil drainage",
    "soil depth",
    "hydrologic group",
    "soil map unit",
)

INTERNAL_LEAK = re.compile(
    r"\b(?:OBS_|BOTTLENECK_|CLAIM_|ACTION_|FACTOR_|F0[1-8]_|"
    r"ADAPTER_|HTTP_|coverage_status|"
    r"packet_hash|profile_hash|concl_|deal_|nfi_)",
    re.I,
)


class NaturalFoundationReportError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _plain(text: Any) -> str:
    raw = str(text or "")
    return (
        raw.replace("—", "-")
        .replace("–", "-")
        .replace("…", "...")
        .replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("•", "-")
    )


def _clip(text: str, limit: int) -> str:
    text = _plain(text).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _clip_complete_sentences(text: Any, limit: int) -> str:
    """Fit advisor prose without leaving an abrupt half-sentence in the PDF."""
    clean = re.sub(r"\s+", " ", _plain(text)).strip()
    if len(clean) <= limit:
        return clean
    sentences = [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+", clean)
        if part.strip()
    ]
    kept: list[str] = []
    for sentence in sentences:
        candidate = " ".join(kept + [sentence]).strip()
        if len(candidate) > limit:
            break
        kept.append(sentence)
    if kept:
        return " ".join(kept)
    # A provider may return one very long sentence. Preserve its meaning at a
    # word boundary rather than failing the entire download.
    clipped = clean[: max(0, limit - 1)].rsplit(" ", 1)[0].rstrip(" ,;:")
    return clipped + "." if clipped else ""


def run_has_natural_foundation_report(run: Mapping[str, Any]) -> bool:
    interpretation = run.get("natural_foundation_interpretation")
    packet = run.get("combined_environmental_evidence_packet")
    return isinstance(interpretation, Mapping) and isinstance(packet, Mapping)


def _format_value(obs: Mapping[str, Any]) -> str:
    value = obs.get("value")
    unit = obs.get("unit")
    if value is None:
        return ""
    if isinstance(value, float):
        text = f"{value:.4g}"
    elif isinstance(value, bool):
        text = "Yes" if value else "No"
    else:
        text = str(value)
    if unit:
        return f"{text} {unit}".strip()
    return text


def _evidence_label(obs: Mapping[str, Any]) -> str:
    field = str(obs.get("field_id") or obs.get("observation_id") or "Evidence")
    # Buyer label: strip technical prefixes without inventing meaning.
    cleaned = field
    for prefix in ("VAR_F01_", "VAR_F02_", "VAR_F03_", "VAR_F04_", "VAR_F05_", "VAR_F06_", "VAR_F08_", "SUPPLEMENT_", "CORE_"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break
    return cleaned.replace("_", " ").strip().title() or "Evidence"


def _appendix_priority(row: Mapping[str, Any], original_index: int) -> tuple[int, int, int]:
    """Rank cited/buyer-critical evidence without changing any evidence value."""
    label = str(row.get("evidence") or "").lower()
    domain = str(row.get("domain") or "")
    term_rank = next(
        (index for index, term in enumerate(APPENDIX_PRIORITY_TERMS) if term in label),
        len(APPENDIX_PRIORITY_TERMS),
    )
    domain_rank = {
        "Terrain": 0,
        "Forage": 1,
        "Water": 2,
        "Climate": 3,
        "Soil": 4,
    }.get(domain, 5)
    return (term_rank, domain_rank, original_index)


def project_natural_cattle_foundation_report(run: Mapping[str, Any]) -> dict[str, Any]:
    """Project a two-page report view from validated interpretation + Combined Packet."""
    interpretation = run.get("natural_foundation_interpretation")
    if not isinstance(interpretation, Mapping):
        raise NaturalFoundationReportError(
            "INTERPRETATION_REQUIRED",
            "natural_foundation_interpretation is required",
        )
    if interpretation.get("validation_status") != "PASSED":
        raise NaturalFoundationReportError(
            "INTERPRETATION_NOT_VALIDATED",
            "interpretation validation_status must be PASSED",
        )
    packet = run.get("combined_environmental_evidence_packet")
    if not isinstance(packet, Mapping):
        raise NaturalFoundationReportError(
            "COMBINED_PACKET_REQUIRED",
            "combined_environmental_evidence_packet is required",
        )
    profile = run.get("natural_cattle_profile")
    if not isinstance(profile, Mapping):
        raise NaturalFoundationReportError(
            "PROFILE_REQUIRED",
            "natural_cattle_profile is required",
        )
    if interpretation.get("natural_cattle_profile_hash") != profile.get("profile_hash"):
        raise NaturalFoundationReportError(
            "PROFILE_HASH_MISMATCH",
            "interpretation hash must match natural_cattle_profile.profile_hash",
        )

    deal = run.get("deal_context") if isinstance(run.get("deal_context"), Mapping) else {}
    status = str(interpretation.get("status") or "")
    status_label = STATUS_LABELS.get(status, status.replace("_", " ").title())
    op = str(deal.get("operation_type") or "UNKNOWN").upper()
    op_label = OPERATION_LABELS.get(op, op.replace("_", " ").lower())
    controlling = interpretation.get("controlling_factor") or {}
    ctrl_domain = controlling.get("domain")
    ctrl_label = BUYER_LABELS.get(str(ctrl_domain), "unresolved factor") if ctrl_domain else "unresolved"

    visible = buyer_visible_observations(packet)
    env_rows: list[dict[str, str]] = []
    provider_counts: dict[str, int] = {}
    spatial_counts: dict[str, int] = {}
    for obs in visible:
        provider = str(obs.get("provider") or "UNKNOWN")
        spatial = str(obs.get("spatial_semantics") or "PARCEL").upper()
        provider_counts[provider] = provider_counts.get(provider, 0) + 1
        spatial_counts[spatial] = spatial_counts.get(spatial, 0) + 1
        domain = str(obs.get("domain") or "")
        env_rows.append(
            {
                "domain": BUYER_LABELS.get(domain, domain.replace("_", " ").title()),
                "evidence": _clip(_evidence_label(obs), 42),
                "result": _clip(_format_value(obs), 36),
                "spatial": SPATIAL_LABELS.get(spatial, spatial.title()),
                "provider": PROVIDER_LABELS.get(provider, provider.replace("_", " ").title()),
                "source": _clip(
                    str(obs.get("source_name") or obs.get("dataset_vintage") or "—"),
                    28,
                ),
                "status": str(obs.get("status") or "RETRIEVED"),
            }
        )

    # Preserve all retrieved rows in provenance, but make the fixed 22-row page
    # budget useful: area/slope, vegetation, climate, water, and soil evidence
    # cited by the advisor view should not disappear behind provider ordering.
    env_rows = [
        row
        for _, row in sorted(
            enumerate(env_rows),
            key=lambda item: _appendix_priority(item[1], item[0]),
        )
    ]

    # Property context is isolated from the environmental packet and primary reasoning.
    legacy_packet = run.get("packet") if isinstance(run.get("packet"), Mapping) else {"observations": []}
    # Also scan combined packet for appendix-only markers (usually empty).
    synth_obs = []
    for key in ("mireye_observations", "core_observations", "supplement_observations"):
        for obs in packet.get(key) or []:
            if isinstance(obs, Mapping):
                synth_obs.append(dict(obs))
    isolated_context = run.get("additional_property_context_collection")
    if isinstance(isolated_context, Mapping):
        for obs in isolated_context.get("observations") or []:
            if isinstance(obs, Mapping):
                synth_obs.append(dict(obs))
    property_context = project_additional_property_context(
        {"observations": list(legacy_packet.get("observations") or []) + synth_obs}
    )
    if not property_context.get("enabled"):
        property_context = None
    elif len(property_context.get("rows") or []) > MAXIMUM_ROWS:
        raise NaturalFoundationReportError(
            "PROPERTY_CONTEXT_TOO_MANY",
            f"property context exceeds {MAXIMUM_ROWS} rows",
        )

    page1_pointer = PAGE1_APPENDIX_POINTER if property_context else None

    view = {
        "schema_version": REPORT_SCHEMA,
        "title": "Natural Cattle Foundation",
        "address": str(run.get("address") or ""),
        "status_line": f"Current view: {status_label} for {op_label}",
        "page1": {
            "land_character": _plain(interpretation.get("land_character")),
            "advisor_judgment": _plain(interpretation.get("advisor_judgment")),
            "operating_possibilities": [
                _plain(x) for x in (interpretation.get("operating_possibilities") or []) if str(x).strip()
            ],
            "conditional_scenarios": [
                _plain(x) for x in (interpretation.get("conditional_scenarios") or []) if str(x).strip()
            ],
            "advisor_view": _plain(interpretation.get("advisor_view")),
            "integrated_natural_reading": _plain(
                interpretation.get("integrated_natural_reading")
            ),
            "intended_use_interpretation": _plain(
                interpretation.get("intended_use_interpretation")
            ),
            "what_would_change_the_view": [
                _plain(x) for x in (interpretation.get("what_would_change_the_view") or []) if str(x).strip()
            ],
            "refinement_request": _plain(interpretation.get("refinement_request")),
            "controlling_factor_label": ctrl_label,
            "scope_footer": (
                "This is a preliminary cattle-land interpretation based on a confirmed parcel, "
                "sourced environmental evidence, reviewed cattle-land knowledge, and the buyer "
                "information currently available. It is not a stocking-rate, water-right, "
                "appraisal, insurance, legal-access, or purchase opinion."
            ),
            "appendix_pointer": page1_pointer,
        },
        "page2": {
            "environmental_evidence": env_rows,
            "provenance": {
                "retrieved_row_count": len(env_rows),
                "provider_counts": provider_counts,
                "spatial_counts": spatial_counts,
                "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            },
            "related_property_context": property_context,
        },
        "provenance": {
            "run_id": run.get("run_id"),
            "interpretation_id": interpretation.get("interpretation_id"),
            "interpretation_source": interpretation.get("source"),
            "natural_cattle_profile_hash": profile.get("profile_hash"),
            "packet_hash": packet.get("packet_hash"),
            "deal_context_version": deal.get("context_version"),
            "collection_mode": run.get("collection_mode"),
        },
    }
    violations = validate_natural_cattle_foundation_report(view)
    if violations:
        raise NaturalFoundationReportError(
            violations[0]["code"], violations[0]["message"]
        )
    return view


def validate_natural_cattle_foundation_report(
    view: Mapping[str, Any],
) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    page1 = view.get("page1") or {}
    prose = " ".join(
        [
            str(page1.get("advisor_view") or ""),
            str(page1.get("land_character") or ""),
            str(page1.get("advisor_judgment") or ""),
            " ".join(page1.get("operating_possibilities") or []),
            " ".join(page1.get("conditional_scenarios") or []),
            str(page1.get("integrated_natural_reading") or ""),
            str(page1.get("intended_use_interpretation") or ""),
            str(page1.get("refinement_request") or ""),
            " ".join(page1.get("what_would_change_the_view") or []),
        ]
    )
    hit = INTERNAL_LEAK.search(prose)
    if hit:
        violations.append(
            {"code": "PAGE1_INTERNAL_LEAK", "message": f"Page 1 leaks {hit.group(0)}"}
        )
    if "{" in prose or "}" in prose:
        violations.append(
            {
                "code": "PAGE1_STRUCTURED_LITERAL_LEAK",
                "message": "Page 1 contains an unrendered object literal",
            }
        )
    for key in (
        "land_character",
        "advisor_judgment",
        "intended_use_interpretation",
        "refinement_request",
    ):
        if not str(page1.get(key) or "").strip():
            violations.append(
                {"code": "PAGE1_FIELD_MISSING", "message": f"missing {key}"}
            )
    if not (page1.get("what_would_change_the_view") or []):
        violations.append(
            {"code": "PAGE1_FIELD_MISSING", "message": "missing what_would_change_the_view"}
        )

    page2 = view.get("page2") or {}
    for row in page2.get("environmental_evidence") or []:
        if not str(row.get("result") or "").strip():
            violations.append(
                {"code": "EMPTY_EVIDENCE_ROW", "message": "empty environmental result"}
            )
        if str(row.get("status") or "") not in {"RETRIEVED", "PARTIAL"}:
            violations.append(
                {"code": "NON_RETRIEVED_EVIDENCE_ROW", "message": str(row.get("status"))}
            )
    ctx = page2.get("related_property_context")
    if isinstance(ctx, Mapping) and ctx.get("enabled") and len(ctx.get("rows") or []) > MAXIMUM_ROWS:
        violations.append(
            {"code": "PROPERTY_CONTEXT_TOO_MANY", "message": "too many context rows"}
        )
    return violations


def render_natural_cattle_foundation_pdf(view: Mapping[str, Any]) -> bytes:
    """Render a readable advisor narrative followed by a new-page appendix."""
    try:
        from fpdf import FPDF
    except ModuleNotFoundError as exc:
        raise RuntimeError("DEPENDENCY_MISSING:fpdf2") from exc

    violations = validate_natural_cattle_foundation_report(view)
    if violations:
        raise NaturalFoundationReportError(
            violations[0]["code"], violations[0]["message"]
        )

    pdf = FPDF(format="Letter", unit="mm")
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(14, 12, 14)
    ink = (25, 37, 29)
    forest = (24, 74, 48)
    gray = (96, 109, 100)
    line = (207, 217, 208)
    pale = (232, 239, 231)
    page_bottom = 272.0

    def new_page_writer(*, allow_page_break: bool = False, continuation_title: str = ""):
        state = {"y": 12.0}

        def start_continuation_page() -> None:
            pdf.add_page()
            state["y"] = 12.0
            pdf.set_fill_color(*forest)
            pdf.rect(0, 0, 216, 3, style="F")
            if continuation_title:
                pdf.set_xy(14, state["y"])
                pdf.set_font("Helvetica", "B", 9.5)
                pdf.set_text_color(*forest)
                pdf.cell(182, 4.4, continuation_title, align="C")
                state["y"] = 20.0

        def write(
            text: Any,
            *,
            size: float = 9,
            style: str = "",
            leading: float = 4.2,
            color: tuple[int, int, int] = ink,
            width: float = 182.0,
            align: str = "L",
        ) -> None:
            pdf.set_font("Helvetica", style, size)
            pdf.set_text_color(*color)
            measured_height = float(
                pdf.multi_cell(
                    width,
                    leading,
                    _plain(text),
                    border=0,
                    align=align,
                    dry_run=True,
                    output="HEIGHT",
                )
            )
            if state["y"] + measured_height > page_bottom:
                if not allow_page_break:
                    raise NaturalFoundationReportError(
                        "FOUNDATION_PAGE_OVERFLOW",
                        f"content overflow at y={state['y'] + measured_height:.1f}mm",
                    )
                start_continuation_page()
                pdf.set_font("Helvetica", style, size)
                pdf.set_text_color(*color)
            pdf.set_xy(14, state["y"])
            pdf.multi_cell(width, leading, _plain(text), border=0, align=align)
            state["y"] = pdf.get_y() + 0.5
            if state["y"] > page_bottom:
                raise NaturalFoundationReportError(
                    "FOUNDATION_PAGE_OVERFLOW",
                    f"content overflow at y={state['y']:.1f}mm",
                )

        def gap(amount: float = 2.8) -> None:
            state["y"] += amount
            if state["y"] > page_bottom:
                if not allow_page_break:
                    raise NaturalFoundationReportError(
                        "FOUNDATION_PAGE_OVERFLOW",
                        f"content overflow at y={state['y']:.1f}mm",
                    )
                start_continuation_page()

        def rule() -> None:
            pdf.set_draw_color(*line)
            pdf.line(14, state["y"], 196, state["y"])
            state["y"] += 2.0

        return write, gap, rule, state

    def fit_cell_text(value: Any, width: float) -> str:
        """Ellipsize table text to the rendered cell width; never overlap columns."""
        text = _plain(value).strip()
        available = max(1.0, width - 1.2)
        if pdf.get_string_width(text) <= available:
            return text
        suffix = "..."
        while text and pdf.get_string_width(text + suffix) > available:
            text = text[:-1]
        return (text.rstrip() + suffix) if text else suffix

    # --- Page 1 ---
    pdf.add_page()
    write, gap, rule, state = new_page_writer(
        allow_page_break=True,
        continuation_title="Natural Cattle Foundation - continued",
    )
    page1 = view.get("page1") or {}
    pdf.set_fill_color(*forest)
    pdf.rect(0, 0, 216, 3, style="F")
    write("RANGEMATCH", size=10, style="B", color=forest, leading=4.4, align="C")
    write(str(view.get("title") or "Natural Cattle Foundation"), size=23, style="B", leading=9.2, align="C")
    write(str(view.get("address") or ""), size=11.5, color=gray, leading=5.0, align="C")
    write(str(view.get("status_line") or ""), size=10, color=gray, leading=4.4, align="C")
    gap(1.0)
    rule()

    write("Advisor's judgment", size=14.2, style="B", color=forest, leading=6.0)
    write(
        str(page1.get("advisor_judgment") or ""),
        size=10.8,
        leading=4.8,
    )
    gap()

    write("How this land naturally reads", size=14.2, style="B", color=forest, leading=6.0)
    write(
        str(page1.get("land_character") or ""),
        size=10.8,
        leading=4.8,
    )
    gap()

    write("What this may support", size=14.2, style="B", color=forest, leading=6.0)
    for item in (page1.get("operating_possibilities") or [])[:3]:
        write(
            f"- {str(item)}",
            size=10.6,
            leading=4.7,
        )
    gap()

    write("What your intended cattle use changes", size=14.2, style="B", color=forest, leading=6.0)
    write(
        str(page1.get("intended_use_interpretation") or ""),
        size=10.8,
        leading=4.8,
    )
    gap()

    write("What would change my view", size=14.2, style="B", color=forest, leading=6.0)
    for item in (page1.get("conditional_scenarios") or [])[:2]:
        write(
            f"- {str(item)}",
            size=10.6,
            leading=4.7,
        )
    gap()

    write("To refine this assessment", size=14.2, style="B", color=forest, leading=6.0)
    write(
        str(page1.get("refinement_request") or ""),
        size=10.8,
        leading=4.8,
    )
    gap(2.2)

    write(_clip(str(page1.get("scope_footer") or ""), 420), size=8.7, color=gray, leading=3.9)
    if page1.get("appendix_pointer"):
        write(str(page1.get("appendix_pointer")), size=8.0, color=gray, leading=3.5)

    # --- Appendix: always starts on a fresh page after the full narrative. ---
    pdf.add_page()
    write, gap, rule, state = new_page_writer()
    page2 = view.get("page2") or {}
    pdf.set_fill_color(*forest)
    pdf.rect(0, 0, 216, 3, style="F")
    write("RANGEMATCH", size=10, style="B", color=forest, leading=4.4, align="C")
    write("Appendix", size=22, style="B", leading=8.8, align="C")
    write("Evidence retrieved for this confirmed parcel", size=11, color=gray, leading=4.8, align="C")
    gap(1.5)

    write("Environmental Evidence Retrieved", size=12, style="B", color=forest, leading=5.2)
    provenance = page2.get("provenance") or {}
    rows = list(page2.get("environmental_evidence") or [])
    max_rows = 22
    displayed_rows = min(len(rows), max_rows)
    write(
        f"Retrieved rows: {provenance.get('retrieved_row_count', 0)}; "
        f"displaying {displayed_rows} (this run only; empty and failed rows omitted).",
        size=8.4,
        color=gray,
        leading=3.7,
    )
    gap(1.2)

    # Compact table header
    headers = ["Domain", "Evidence", "Result", "Spatial", "Provider", "Source"]
    col_w = [22, 40, 34, 28, 30, 28]
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_text_color(*gray)
    x = 14.0
    for header, width in zip(headers, col_w):
        pdf.set_xy(x, state["y"])
        pdf.cell(width, 4.0, header, border=0)
        x += width
    state["y"] += 4.2
    rule()

    # Fit in remaining page budget; prefer earlier rows, never invent.
    for row in rows[:max_rows]:
        pdf.set_font("Helvetica", "", 7.2)
        pdf.set_text_color(*ink)
        x = 14.0
        values = [
            str(row.get("domain") or ""),
            str(row.get("evidence") or ""),
            str(row.get("result") or ""),
            str(row.get("spatial") or ""),
            str(row.get("provider") or ""),
            str(row.get("source") or ""),
        ]
        for value, width in zip(values, col_w):
            pdf.set_xy(x, state["y"])
            pdf.cell(width, 3.8, fit_cell_text(value, width), border=0)
            x += width
        state["y"] += 3.9
        if state["y"] > page_bottom - 40:
            break
    if len(rows) > max_rows:
        write(
            f"Showing {max_rows} of {len(rows)} retrieved rows for page fit.",
            size=7.8,
            color=gray,
            leading=3.4,
        )
    gap(3.0)

    ctx = page2.get("related_property_context")
    if isinstance(ctx, Mapping) and ctx.get("enabled") and len(ctx.get("rows") or []) > 0:
        write("Related Property Context", size=12, style="B", color=forest, leading=5.2)
        write(
            "Physical map context only. Does not establish legal or usable access.",
            size=8.2,
            color=gray,
            leading=3.6,
        )
        gap(1.0)
        for row in (ctx.get("rows") or [])[:MAXIMUM_ROWS]:
            if not isinstance(row, Mapping):
                continue
            topic = str(row.get("topic") or "Mapped context")
            can_say = str(row.get("what_we_can_say") or "")
            does_not = str(row.get("what_it_does_not_establish") or "")
            write(f"- {topic}: {can_say}", size=9.0, leading=3.9)
            if does_not:
                write(f"  {does_not}", size=8.0, color=gray, leading=3.5)
    # Empty context: section omitted entirely.

    # Provenance footer (hashes only here)
    gap(2.0)
    rule()
    prov = view.get("provenance") or {}
    write(
        f"Interpretation source: {prov.get('interpretation_source') or 'n/a'}  |  "
        f"Profile hash: {str(prov.get('natural_cattle_profile_hash') or '')[:16]}...  |  "
        f"Packet hash: {str(prov.get('packet_hash') or '')[:16]}...",
        size=7.2,
        color=gray,
        leading=3.3,
    )

    buffer = BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()
