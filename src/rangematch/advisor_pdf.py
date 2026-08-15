"""Validated Buyer Brief → PDF view model → three-page renderer."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Mapping

from rangematch.advisor_report import validate_buyer_copy_quality

PDF_VIEW_SCHEMA = "RANGEMATCH_ADVISOR_PDF_VIEW@0.1.0"


def _plain(text: Any) -> str:
    raw = str(text or "")
    return (
        raw.replace("—", "-")
        .replace("–", "-")
        .replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("•", "-")
    )


def _has_listing(packet: Mapping[str, Any] | None) -> bool:
    if not packet:
        return False
    return bool(packet.get("listing_claims") or packet.get("claim_evidence_gaps"))


def _mireye_anchor(run: Mapping[str, Any]) -> str:
    address = str(run.get("address") or "This address")
    live = run.get("mireye_live") or {}
    lookup_ok = bool((live.get("lookup") or {}).get("ok"))
    contexts = live.get("contexts") or {}
    confirmed = bool(run.get("parcel_geometry_confirmed"))
    if lookup_ok and confirmed:
        return (
            f"Mireye recognized {address}. You confirmed one outline. "
            "Federal evidence on this brief is clipped to that polygon. "
            "Mireye property, land, and hazard rows are context only - "
            "not parcel-wide proof."
        )
    if lookup_ok and not confirmed:
        return (
            f"Mireye recognized {address}, but the outline is not confirmed. "
            "Full investigation waits on that confirmation."
        )
    if contexts:
        return (
            "Mireye context was requested for this run. It is not a substitute "
            "for polygon-based canonical evidence."
        )
    return (
        "This brief does not treat Mireye as a land-fact source. "
        "Parcel facts come from the confirmed outline and federal adapters."
    )


def _mireye_page_three(run: Mapping[str, Any]) -> list[dict[str, Any]]:
    live = run.get("mireye_live") or {}
    rows: list[dict[str, Any]] = []
    lookup = live.get("lookup") or {}
    if lookup:
        rows.append(
            {
                "label": "Location recognition",
                "role": "PARCEL_ENTRY",
                "status": "ok" if lookup.get("ok") else str(lookup.get("error_class") or "unavailable"),
                "canonical_for_parcel_facts": False,
            }
        )
    labels = {
        "PROPERTY_DILIGENCE_CONTEXT": "Property context",
        "POINT_LAND_CONTEXT": "Land context at centroid",
        "POINT_HAZARD_CONTEXT": "Hazard context at centroid",
    }
    for key, label in labels.items():
        row = (live.get("contexts") or {}).get(key) or {}
        if not row and not lookup:
            continue
        rows.append(
            {
                "label": label,
                "role": "CONTEXT_ONLY",
                "status": str(row.get("status") or "NOT_REQUESTED"),
                "canonical_for_parcel_facts": False,
            }
        )
    return rows


def _normalize_mireye_rows(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Accept both Brief provenance rows and PDF-native rows."""
    labels = {
        "MIREYE_LOOKUP": "Location recognition",
        "MIREYE_PROPERTY_DILIGENCE_CONTEXT": "Property context",
        "MIREYE_POINT_LAND_CONTEXT": "Land context at centroid",
        "MIREYE_POINT_HAZARD_CONTEXT": "Hazard context at centroid",
    }
    normalized = []
    for row in rows:
        source_id = str(row.get("source_id") or "")
        label = row.get("label") or labels.get(source_id) or source_id or "Mireye context"
        if row.get("status") is not None:
            status = str(row.get("status"))
        elif row.get("ok") is True:
            status = "SUCCEEDED"
        elif row.get("ok") is False:
            status = "UNAVAILABLE"
        else:
            status = "NOT_RECORDED"
        normalized.append(
            {
                "source_id": source_id,
                "label": str(label),
                "role": str(row.get("role") or "CONTEXT_ONLY"),
                "status": status,
                "spatial_meaning": str(row.get("spatial_meaning") or "context"),
                "canonical_for_parcel_facts": False,
            }
        )
    return normalized


def project_buyer_brief_pdf_model(run: Mapping[str, Any]) -> dict[str, Any]:
    """Build a print model from a validated run. Does not invent facts."""
    brief = run.get("brief") or {}
    packet = run.get("packet") or {}
    explanation = run.get("buyer_explanation") or {}
    page_one = brief.get("page_one_advisor") or {}
    page_two = brief.get("page_two_actions") or {}
    kitchen = brief.get("page_three_kitchen") or {}
    ranch = explanation.get("ranch_narrative") if isinstance(explanation.get("ranch_narrative"), Mapping) else None
    expl_ok = (
        explanation.get("validation_status") == "PASSED"
        and bool(explanation)
        and not validate_buyer_copy_quality(explanation)
        and (
            explanation.get("source") == "LIVE_LLM"
            or ranch is not None
        )
    )
    sections = explanation.get("sections") or {}
    narrative = explanation.get("narrative") if expl_ok else None
    has_listing = _has_listing(packet)
    headline = (
        (ranch or {}).get("operating_thesis")
        or sections.get("recommendation")
        if expl_ok
        else (page_two.get("headline") or page_one.get("how_the_tract_reads") or "")
    )
    lead = (
        (ranch or {}).get("ranch_reading")
        or sections.get("why")
        if expl_ok
        else page_one.get("how_the_tract_reads")
    )
    evidence_block = (
        (ranch or {}).get("how_livestock_would_use_it")
        or sections.get("listing_jumps")
        if expl_ok
        else (
            " ".join(page_one.get("listing_outruns_evidence") or [])
            if has_listing
            else (
                "No listing packet was supplied. Read what public evidence supports, "
                "and treat entrance and operating water as document questions."
            )
        )
    )
    return {
        "schema_version": PDF_VIEW_SCHEMA,
        "run_id": run.get("run_id"),
        "address": run.get("address"),
        "packet_hash": run.get("packet_hash") or brief.get("packet_hash"),
        "brief_validation_status": brief.get("validation_status"),
        "prose_source": (
            explanation.get("source")
            if expl_ok
            else "DETERMINISTIC_BRIEF"
        ),
        "narrative": narrative if isinstance(narrative, Mapping) else None,
        "ranch_narrative": ranch if isinstance(ranch, Mapping) else None,
        "page_one": {
            "headline": headline,
            "lead": lead,
            "mireye_anchor": _mireye_anchor(run),
            "evidence_block": evidence_block,
            "do_today": list(page_one.get("do_today") or []),
            "visit_guidance": page_one.get("visit_guidance"),
            "what_changes_next": page_one.get("what_changes_next"),
            "signals": list(kitchen.get("observations") or [])[:6],
        },
        "page_two": {
            "mode": page_two.get("page_mode")
            or ("LISTING_CLAIMS" if has_listing else "PUBLIC_EVIDENCE"),
            "headline": page_two.get("headline")
            or (
                "What the listing language actually has behind it"
                if has_listing
                else "What public evidence supports - and what still requires transaction documents"
            ),
            "messages": list(page_two.get("messages") or []),
        },
        "page_three": {
            "parcel_summary": kitchen.get("parcel_summary") or packet.get("parcel") or {},
            "observations": list(kitchen.get("observations") or []),
            "source_notes": list(kitchen.get("source_notes") or []),
            "mireye_provenance": _normalize_mireye_rows(
                list(kitchen.get("mireye_provenance") or _mireye_page_three(run))
            ),
            "coverage": list(kitchen.get("coverage_and_limitations") or [])[:8],
            "validation": kitchen.get("validation_record") or {},
        },
    }


def render_three_page_pdf(view: Mapping[str, Any]) -> bytes:
    """Render a polished, fixed three-page buyer brief. Requires fpdf2."""
    try:
        from fpdf import FPDF
    except ModuleNotFoundError as exc:
        raise RuntimeError("DEPENDENCY_MISSING:fpdf2") from exc

    pdf = FPDF(format="Letter", unit="mm")
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(14, 12, 14)
    ink = (25, 37, 29)
    forest = (24, 74, 48)
    moss = (87, 113, 94)
    cream = (247, 245, 239)
    pale = (232, 239, 231)
    warm = (250, 238, 217)
    rose = (247, 233, 229)
    line = (207, 217, 208)
    gray = (96, 109, 100)
    white = (255, 255, 255)

    def color(rgb: tuple[int, int, int]) -> None:
        pdf.set_text_color(*rgb)

    def fill(rgb: tuple[int, int, int]) -> None:
        pdf.set_fill_color(*rgb)

    def stroke(rgb: tuple[int, int, int]) -> None:
        pdf.set_draw_color(*rgb)

    def write_at(x: float, y: float, w: float, text: Any, *, size: float = 9,
                 style: str = "", leading: float = 4.4,
                 text_color: tuple[int, int, int] = ink) -> None:
        pdf.set_xy(x, y)
        pdf.set_font("Helvetica", style, size)
        color(text_color)
        pdf.multi_cell(w, leading, _plain(text), border=0, align="L")

    def card(x: float, y: float, w: float, h: float,
             bg: tuple[int, int, int] = white,
             border: tuple[int, int, int] = line, radius: float = 3) -> None:
        fill(bg)
        stroke(border)
        pdf.rect(x, y, w, h, style="DF")

    def footer(page: int) -> None:
        stroke(line)
        pdf.line(14, 264, 202, 264)
        write_at(14, 266, 130, "Buyer-side pre-visit diligence | Evidence-constrained",
                 size=6.8, leading=3.2, text_color=gray)
        write_at(183, 266, 19, f"{page} / 3", size=6.8, leading=3.2, text_color=gray)

    def page_header(page: int, right: str, title: str, subtitle: str = "") -> None:
        fill(forest)
        pdf.rect(0, 0, 216, 3, style="F")
        write_at(14, 13, 60, "RANGEMATCH", size=8, style="B", text_color=forest)
        write_at(137, 13, 65, right.upper(), size=7.3, text_color=gray)
        title_size = 17 if len(title) > 55 else 21
        title_leading = 7.4 if len(title) > 55 else 8.8
        write_at(14, 22, 188, title, size=title_size, style="B", leading=title_leading)
        if subtitle:
            write_at(14, 41, 188, subtitle, size=8.6, leading=4.1, text_color=gray)
        footer(page)

    def observation_map() -> dict[str, Mapping[str, Any]]:
        return {
            str(row.get("observation_id") or ""): row
            for row in (page_three.get("observations") or [])
        }

    def fmt_signal(row: Mapping[str, Any] | None) -> tuple[str, str]:
        if not row:
            return ("Unavailable", "source unavailable")
        value = row.get("display_value") if row.get("display_value") is not None else row.get("value")
        unit = str(row.get("unit") or "")
        try:
            number = float(value)
            if unit == "m2":
                return (f"{number / 4046.8564224:.1f} acres", "mapped outline")
            if unit == "mm/year":
                return (f"{number / 25.4:.1f} in", "annual precipitation")
            if unit == "degree":
                return (f"{number:.1f} deg", "median slope")
            if unit == "pound_per_acre":
                return (f"{number:,.0f} lb/ac", "modeled snapshot")
            if unit == "m":
                return (f"{number:.0f} m", "mapped road distance")
            if unit == "count":
                return (f"{number:.0f}", "mapped water leads")
        except (TypeError, ValueError):
            pass
        return (_plain(value), _plain(unit or row.get("evidence_state") or "evidence"))

    page_one = view.get("page_one") or {}
    page_two = view.get("page_two") or {}
    page_three = view.get("page_three") or {}
    narrative = view.get("narrative") or {}

    observations = observation_map()

    ranch_story = view.get("ranch_narrative") or {}
    # Page 1: one thesis and one continuous advisor memo.
    pdf.add_page()
    page_header(
        1,
        "Cattle operating brief" if ranch_story else "Pre-visit advisor brief",
        "How This Ranch Reads" if ranch_story else "What should happen before the trip?",
        "A preliminary cattle operating picture, not a stocking or purchase opinion."
        if ranch_story
        else "",
    )
    card(14, 49, 188, 58, bg=ink, border=ink, radius=4)
    write_at(19, 55, 55, "ADVISOR RECOMMENDATION", size=7.2, style="B", text_color=(184, 211, 194))
    write_at(19, 63, 178, ranch_story.get("operating_thesis") or narrative.get("thesis") or page_one.get("headline") or "Buyer brief", size=15.5,
             style="B", leading=7.4, text_color=white)
    card(14, 114, 188, 93, bg=white)
    write_at(19, 120, 75, "THE ADVISOR'S READING", size=8, style="B", text_color=forest)
    client_summary = ranch_story.get("ranch_reading") or narrative.get("client_summary") or ""
    if client_summary:
        memo = client_summary
    else:
        memo = page_one.get("lead") or ""
    write_at(19, 131, 178, memo, size=9.2, leading=4.7)
    write_at(19, 193, 178, page_one.get("mireye_anchor") or "", size=7.4,
             leading=3.7, text_color=moss)

    card(14, 214, 188, 42, bg=warm, border=warm)
    write_at(19, 219, 65, "VISIT PURPOSE", size=7.3, style="B", text_color=(175, 103, 20))
    write_at(19, 227, 178, page_one.get("visit_guidance") or "", size=9.1,
             leading=4.5)
    write_at(19, 247, 178, page_one.get("what_changes_next") or "", size=7.2,
             leading=3.5, text_color=gray)

    # Page 2: buyer-facing advice. The evidence chain stays in the validated
    # report bundle as an audit trace; clients should not be asked to read it.
    pdf.add_page()
    page_header(
        2,
        "How cattle would use it" if ranch_story else "The advisor's call",
        "How Cattle Would Use It" if ranch_story else "Do the cheap work before the expensive trip",
        "Feed context, water investigation, and movement context — not unknown cards."
        if ranch_story
        else "",
    )
    pivot = narrative.get("action_pivot") or {}
    conditional = narrative.get("conditional_path") or {}
    advice_actions = list(page_one.get("do_today") or [])
    card(14, 49, 188, 44, bg=ink, border=ink, radius=4)
    write_at(19, 55, 62, "MY READ", size=7.2, style="B", text_color=(184, 211, 194))
    write_at(19, 64, 178, ranch_story.get("how_livestock_would_use_it") or narrative.get("client_summary") or page_one.get("lead") or "",
             size=11.2, style="B", leading=5.5, text_color=white)

    card(14, 102, 188, 41, bg=white)
    write_at(19, 108, 70, "START AT THE DESK", size=7.6, style="B", text_color=forest)
    first_desk_action = (
        (advice_actions[0] + " Do this before booking travel; the response gives the visit a defined job.")
        if advice_actions
        else "Request the entrance record before committing to travel; the response gives the visit a defined job."
    )
    write_at(19, 117, 178, first_desk_action,
             size=9.4, leading=4.7)

    card(14, 151, 188, 46, bg=warm, border=warm)
    write_at(19, 157, 85, "THEN GIVE THE TRIP ONE JOB", size=7.6, style="B", text_color=(175, 103, 20))
    write_at(19, 166, 178, conditional.get("if_favorable") or page_one.get("visit_guidance") or "",
             size=9.4, leading=4.7)

    card(14, 205, 188, 42, bg=pale, border=pale)
    write_at(19, 211, 85, "DO NOT SPEND TWICE", size=7.6, style="B", text_color=forest)
    write_at(19, 220, 178, "Hold additional forage interpretation until the entrance file and water-focused visit show which analysis is worth buying next.",
             size=8.8, leading=4.4)
    write_at(19, 238, 178, "The public layers have already done their job: they set the order. The next useful evidence comes from the file, then the ground.",
             size=7.4, leading=3.7, text_color=gray)

    # Page 3: how the story changes next.
    pdf.add_page()
    page_header(
        3,
        "Before you spend more" if ranch_story else "What happens next",
        "Before You Spend More" if ranch_story else "Let the first result change the story",
    )
    pivot = narrative.get("action_pivot") or {}
    conditional = narrative.get("conditional_path") or {}
    actions = list(page_one.get("do_today") or [])[:2]
    for index in range(2):
        yy = 53 + index * 38
        bg = pale if index == 0 else warm
        accent = forest if index == 0 else (180, 112, 26)
        card(14, yy, 188, 32, bg=white)
        fill(accent)
        pdf.ellipse(19, yy + 7, 13, 13, style="F")
        write_at(23.5, yy + 10, 5, str(index + 1), size=9, style="B", text_color=white)
        action_text = (pivot.get("first_action_reason") if index == 0 else None) or (actions[index] if index < len(actions) else (
            "If access documentation holds, schedule a water-focused field review."
        ))
        write_at(37, yy + 6, 158, action_text, size=10.5, style="B", leading=5)
        if index == 0:
            note = "This can be requested before travel and determines whether the visit has a defined job."
        else:
            note = "Visible conditions on one date still do not establish year-round reliability, quality, capacity, or rights."
        write_at(37, yy + 20, 158, note, size=7.5, leading=3.6, text_color=gray)

    messages = list(page_two.get("messages") or [])
    chosen = []
    for audience in ("TITLE_OR_COUNSEL", "LISTING_BROKER", "PARTNER"):
        row = next((item for item in messages if item.get("audience") == audience), None)
        if row and row not in chosen:
            chosen.append(row)
        if len(chosen) == 2:
            break
    for row in messages:
        if len(chosen) >= 2:
            break
        if row not in chosen:
            chosen.append(row)
    card(14, 130, 188, 42, bg=warm, border=warm)
    write_at(19, 136, 55, "IF THE FILES HOLD", size=7.1, style="B", text_color=(175, 103, 20))
    write_at(19, 144, 82, conditional.get("if_favorable") or page_one.get("what_changes_next") or "", size=7.8, leading=3.8)
    write_at(107, 136, 55, "IF THEY DO NOT", size=7.1, style="B", text_color=(156, 75, 60))
    write_at(107, 144, 89, conditional.get("if_unfavorable") or "Pause travel and route the question to title.", size=7.8, leading=3.8)
    write_at(14, 178, 80, "COPY-READY REQUESTS", size=8, style="B", text_color=forest)
    for index, row in enumerate(chosen[:2]):
        x = 14 + index * 95
        card(x, 186, 91, 35, bg=white)
        write_at(x + 5, 191, 81, str(row.get("audience") or "MESSAGE").replace("_", " / "),
                 size=7, style="B", text_color=forest)
        write_at(x + 5, 199, 81, row.get("body") or "", size=6.8, leading=3.3)

    card(14, 226, 188, 29, bg=(241, 244, 240))
    write_at(19, 231, 82, "SOURCES + PROVENANCE", size=7.0, style="B", text_color=forest)
    parcel = page_three.get("parcel_summary") or {}
    write_at(19, 238, 84,
             f"Confirmed investigation object\nParcel {parcel.get('parcel_id') or 'not recorded'}\nGeometry {str(parcel.get('geometry_hash') or '')[:12]}...",
             size=7.3, leading=3.7, text_color=gray)
    mireye_rows = list(page_three.get("mireye_provenance") or [])
    mireye_lines = [f"{row.get('label')}: {row.get('status')} ({row.get('role')})" for row in mireye_rows]
    write_at(105, 231, 91, "MIREYE ROLE", size=7.0, style="B", text_color=forest)
    write_at(105, 238, 91, "\n".join(mireye_lines[:2]), size=6.4, leading=3.1, text_color=gray)
    validation = page_three.get("validation") or {}
    write_at(19, 252, 178,
             f"Validator {view.get('brief_validation_status')} | Prose {view.get('prose_source')} | Packet {str(validation.get('packet_hash') or view.get('packet_hash') or '')[:16]}... | Mireye context is not canonical for parcel facts.",
             size=6.7, leading=3.2, text_color=gray)

    buffer = BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()
