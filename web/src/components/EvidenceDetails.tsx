import type { Investigation, Report, Trace } from "../api/client";

const CHECK_ORDER = [
  "F01_TOPOGRAPHY",
  "F02_HERBACEOUS_RESOURCE",
  "F03_LIVESTOCK_WATER",
  "F04_SOIL_WETNESS_ECOLOGICAL_SITE",
  "F05_CLIMATE_DROUGHT_EXPOSURE",
  "F06_PARCEL_CONFIGURATION",
  "F07_ROAD_AND_PHYSICAL_ACCESS",
  "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE",
] as const;

const CHECK_LABELS: Record<string, string> = {
  F01_TOPOGRAPHY: "Terrain and slope",
  F02_HERBACEOUS_RESOURCE: "Grass and forage",
  F03_LIVESTOCK_WATER: "Livestock water",
  F04_SOIL_WETNESS_ECOLOGICAL_SITE: "Soil and wetness",
  F05_CLIMATE_DROUGHT_EXPOSURE: "Climate and drought",
  F06_PARCEL_CONFIGURATION: "Parcel size and shape",
  F07_ROAD_AND_PHYSICAL_ACCESS: "Road proximity",
  F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE: "Trees and shrubs",
};

function readableStatus(signal: unknown) {
  if (signal === "CONTEXT_DEPENDENT") return "Information available";
  if (signal === "NEEDS_VERIFICATION") return "Needs field verification";
  return "Not enough information";
}

function sourceNames(factor: Record<string, unknown>) {
  const facts = Array.isArray(factor.land_facts)
    ? (factor.land_facts as Record<string, unknown>[])
    : [];
  const names = facts.flatMap((item) => {
    const values = [item.source_id, item.source, item.provider, item.dataset];
    return values.filter((value): value is string => typeof value === "string" && Boolean(value));
  });
  return [...new Set(names)].slice(0, 3);
}

export function EvidenceDetails({
  investigation,
}: {
  investigation: Investigation;
  report: Report | null;
  trace: Trace | null;
}) {
  const output = (investigation.unified_output || {}) as Record<string, unknown>;
  const factors = (output.factors || {}) as Record<string, Record<string, unknown>>;

  return (
    <details className="details evidence-details" id="evidence-details">
      <summary>Data sources and methodology</summary>
      <p className="muted" style={{ marginTop: "0.65rem" }}>
        Optional appendix showing which land checks had usable information and which still need
        on-the-ground confirmation.
      </p>
      <ul className="buyer-source-list" aria-label="Land checks and data sources">
        {CHECK_ORDER.map((id) => {
          const factor = factors[id] || {};
          const sources = sourceNames(factor);
          return (
            <li key={id}>
              <strong>{CHECK_LABELS[id]}</strong>
              <span>{readableStatus(factor.signal)}</span>
              {sources.length > 0 && <small>Sources: {sources.join(", ")}</small>}
            </li>
          );
        })}
      </ul>
    </details>
  );
}
