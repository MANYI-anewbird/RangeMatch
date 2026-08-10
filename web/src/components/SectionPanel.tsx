import type { ReactNode } from "react";
import type { SectionBody } from "../api/client";
import { signalTone } from "../api/client";

const FACTOR_LABELS: Record<string, string> = {
  F01_TOPOGRAPHY: "Terrain and slope",
  F02_HERBACEOUS_RESOURCE: "Grass and forage",
  F03_LIVESTOCK_WATER: "Livestock water",
  F04_SOIL_WETNESS_ECOLOGICAL_SITE: "Soil and wetness",
  F05_CLIMATE_DROUGHT_EXPOSURE: "Climate and drought",
  F06_PARCEL_CONFIGURATION: "Parcel size and shape",
  F07_ROAD_AND_PHYSICAL_ACCESS: "Road proximity",
  F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE: "Trees and shrubs",
};

function signalLabel(signal: string) {
  if (signal === "CONTEXT_DEPENDENT") return "Information available";
  if (signal === "NEEDS_VERIFICATION") return "Needs verification";
  return "Not enough information";
}

function highlightTitle(h: Record<string, unknown>): string {
  if (typeof h.operation_id === "string") return String(h.operation_id);
  if (typeof h.f07_projection === "string") return `F07 · ${h.f07_projection}`;
  if (typeof h.factor_id === "string")
    return FACTOR_LABELS[h.factor_id] || h.factor_id;
  if (typeof h.canonical_factor_id === "string")
    return FACTOR_LABELS[h.canonical_factor_id] || h.canonical_factor_id;
  return "Finding";
}

export function SectionPanel({
  id,
  title,
  body,
  badges,
  children,
}: {
  id: string;
  title: string;
  body?: SectionBody;
  badges?: ReactNode;
  children?: ReactNode;
}) {
  const highlights = body?.highlights || [];
  const unknowns = body?.unknowns || [];
  const limitations = body?.limitations || [];
  const factors = body?.factor_ids || [];

  return (
    <section className="section-block" id={id} aria-labelledby={`${id}-title`}>
      <div className="status-row" style={{ marginBottom: "0.35rem" }}>
        <h2 id={`${id}-title`}>{title}</h2>
        {badges}
      </div>
      {factors.length > 0 && (
        <p className="muted" style={{ marginTop: 0 }}>
          Land checks: {factors.map((f) => FACTOR_LABELS[f] || f).join(" · ")}
        </p>
      )}
      {children}
      <ul className="highlight-list" aria-label={`${title} highlights`}>
        {highlights.map((h, idx) => {
          const signal = typeof h.signal === "string" ? h.signal : undefined;
          return (
            <li key={idx} className="highlight-item">
              {signal && (
                <span className={`signal-chip ${signalTone(signal)}`}>{signalLabel(signal)}</span>
              )}
              <strong>{highlightTitle(h)}</strong>
              {typeof h.decision_label === "string" && (
                <span> · Decision: {h.decision_label}</span>
              )}
              <details className="details" style={{ marginTop: "0.45rem" }}>
                <summary>Source details</summary>
                <dl className="evidence-dl">
                  {(
                    [
                      ["value", h.value ?? h.observed_value ?? h.summary],
                      ["unit", h.unit],
                      ["source", h.source ?? h.source_id ?? h.dataset],
                      ["vintage", h.vintage ?? h.as_of ?? h.observation_year],
                      ["coverage", h.coverage ?? h.coverage_status ?? h.input_quality_state],
                      ["limitations", h.limitation ?? h.limitations],
                    ] as [string, unknown][]
                  ).map(([label, val]) =>
                    val === undefined || val === null || val === "" ? null : (
                      <div key={label} className="evidence-row">
                        <dt>{label}</dt>
                        <dd>{Array.isArray(val) ? val.join("; ") : String(val)}</dd>
                      </div>
                    ),
                  )}
                </dl>
                {!h.value &&
                  !h.observed_value &&
                  !h.summary &&
                  !h.source &&
                  !h.source_id &&
                  !h.vintage &&
                  !h.coverage &&
                  !h.input_quality_state && (
                    <p className="muted" style={{ fontSize: "0.86rem", margin: "0.35rem 0 0" }}>
                      No additional field provenance projected in this report highlight.
                    </p>
                  )}
              </details>
            </li>
          );
        })}
      </ul>
      {unknowns.length > 0 && (
        <>
          <h3 style={{ fontSize: "1rem", margin: "0.9rem 0 0.35rem" }}>Unknowns</h3>
          <ul className="unknown-list">
            {unknowns.map((u) => (
              <li key={u} className="highlight-item" style={{ background: "var(--verify-bg)" }}>
                {u}
              </li>
            ))}
          </ul>
        </>
      )}
      <details className="details">
        <summary>Sources and limitations</summary>
        <ul className="unknown-list" style={{ marginTop: "0.5rem" }}>
          {limitations.map((l) => (
            <li key={l} className="muted" style={{ fontSize: "0.88rem" }}>
              {l}
            </li>
          ))}
        </ul>
        {Array.isArray(body?.diligence_actions) && body.diligence_actions.length > 0 && (
          <ol className="unknown-list" style={{ marginTop: "0.65rem" }}>
            {body.diligence_actions.slice(0, 12).map((action, i) => {
              const a = action as Record<string, unknown>;
              const text =
                typeof a === "string"
                  ? a
                  : String(
                      a.action ||
                        a.description ||
                        a.title ||
                        a.diligence_action ||
                        JSON.stringify(a),
                    );
              const link =
                typeof a.source_url === "string"
                  ? a.source_url
                  : typeof a.url === "string"
                    ? a.url
                    : null;
              return (
                <li key={i} className="highlight-item" style={{ fontSize: "0.9rem" }}>
                  {text}
                  {link && (
                    <>
                      {" "}
                      <a href={link} target="_blank" rel="noreferrer">
                        source
                      </a>
                    </>
                  )}
                </li>
              );
            })}
          </ol>
        )}
      </details>
    </section>
  );
}

export { FACTOR_LABELS };
