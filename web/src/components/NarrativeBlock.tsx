import type { ReactNode } from "react";
import type { NarrativeSection } from "../api/client";

export function NarrativeBlock({
  id,
  title,
  section,
  badges,
  children,
}: {
  id: string;
  title: string;
  section?: NarrativeSection | null;
  badges?: ReactNode;
  children?: ReactNode;
}) {
  if (!section) return null;
  return (
    <section className={`section-block report-section report-section-${id}`} id={id} aria-labelledby={`${id}-title`}>
      <div className="report-section-heading">
        <div>
          <span className="report-section-index" aria-hidden="true">
            {id === "executive" ? "01" : id === "unknowns" ? "02" : id === "diligence" ? "05" : "07"}
          </span>
          <h2 id={`${id}-title`}>{title}</h2>
        </div>
        <div className="status-row">{badges}</div>
      </div>
      {section.summary && <p className="report-section-summary">{section.summary}</p>}
      {children}
      <ul className="highlight-list" aria-label={`${title} findings`}>
        {(section.findings || []).map((f, i) => (
          <li key={i} className="highlight-item report-finding">
            <span className="report-finding-marker" aria-hidden="true">{String(i + 1).padStart(2, "0")}</span>
            <span>{f}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
