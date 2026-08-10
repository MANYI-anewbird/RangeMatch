import type { Investigation, Report } from "../api/client";
import { operationLabel } from "../api/client";

type Obj = Record<string, unknown>;

function factorsOf(investigation: Investigation) {
  return (((investigation.unified_output || {}) as Obj).factors || {}) as Record<string, Obj>;
}

function fact(factors: Record<string, Obj>, factorId: string, variableId: string) {
  const facts = (factors[factorId]?.land_facts || []) as Obj[];
  return facts.find((item) => item.variable_id === variableId);
}

function numberValue(item: Obj | undefined) {
  return typeof item?.value === "number" && Number.isFinite(item.value) ? item.value : null;
}

function display(value: number | null, unit: string, digits = 1) {
  return value == null ? "Not collected" : `${value.toLocaleString(undefined, { maximumFractionDigits: digits })}${unit}`;
}

function evidenceStatus(item: Obj | undefined, fallback = "Available") {
  if (!item) return "Missing";
  const coverage = item.coverage as Obj | undefined;
  const status = String(coverage?.normalized_status || coverage?.status || "");
  if (status.includes("UNQUANTIFIED") || status.includes("PARTIAL")) return "Modeled · verify coverage";
  return fallback;
}

export function ParcelFactsSummary({ investigation }: { investigation: Investigation }) {
  const f = factorsOf(investigation);
  const area = numberValue(fact(f, "F06_PARCEL_CONFIGURATION", "VAR_F06_AREA_M2"));
  const slope = numberValue(fact(f, "F01_TOPOGRAPHY", "VAR_F01_SLOPE_MEDIAN_DEGREES"));
  const elevation = numberValue(fact(f, "F01_TOPOGRAPHY", "VAR_F01_ELEVATION_MEDIAN_M"));
  const precip = numberValue(fact(f, "F05_CLIMATE_DROUGHT_EXPOSURE", "VAR_F05_MEAN_ANNUAL_PRECIPITATION"));
  const herbFact = fact(f, "F02_HERBACEOUS_RESOURCE", "VAR_F02_PERENNIAL_HERB_COVER");
  const herb = numberValue(herbFact);
  const production = numberValue(fact(f, "F02_HERBACEOUS_RESOURCE", "VAR_F02_ANNUAL_HERB_PRODUCTION"));
  const water = numberValue(fact(f, "F03_LIVESTOCK_WATER", "VAR_F03_MAPPED_WATER_CANDIDATE_COUNT"));
  const verified = numberValue(fact(f, "F03_LIVESTOCK_WATER", "VAR_F03_FIELD_VERIFIED_LIVESTOCK_WATER_COUNT"));
  const road = numberValue(fact(f, "F07_ROAD_AND_PHYSICAL_ACCESS", "VAR_F07_NEAREST_MAPPED_ROAD_DISTANCE_M"));
  const woody = numberValue(fact(f, "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE", "VAR_F08_COMBINED_MODELED_WOODY_COVER_FRACTION"));

  const rows = [
    ["Parcel area", display(area == null ? null : area / 4046.8564224, " acres", 0), "Scale context only", "Confirmed geometry"],
    ["Terrain", `${display(slope, "° median slope")} · ${display(elevation, " m elevation", 0)}`, "Physical grazing-distribution context", "Parcel-derived"],
    ["Annual precipitation", display(precip, " mm/year", 0), "Long-term climate context; not carrying capacity", "NOAA climate normal"],
    ["Perennial herb cover", display(herb, "%"), "Modeled cover; not automatically edible forage", evidenceStatus(herbFact, "Modeled")],
    ["Herb production", display(production, " lb/ac", 0), "Modeled production; field condition still matters", "Modeled"],
    ["Woody cover", display(woody == null ? null : woody * 100, "%"), "Shrub + tree structure; not browse quality", "Modeled"],
    ["Livestock water", `${display(water, " mapped candidates", 0)} · ${display(verified, " field-verified", 0)}`, "Candidates are leads, not usable systems", verified === 0 ? "Critical verification gap" : "Partly verified"],
    ["Mapped road", display(road, " m", 1), "Physical proximity; not legal access", "Mapped context"],
  ];

  return (
    <section className="section-block report-section parcel-facts-section" id="facts" aria-labelledby="facts-title">
      <div className="report-section-heading"><div><span className="report-section-index">03</span><h2 id="facts-title">What we found on this parcel</h2></div></div>
      <p className="report-section-summary">Measured and modeled facts are shown separately from field-verification gaps.</p>
      <div className="parcel-facts-table" role="table" aria-label="Parcel facts">
        {rows.map(([label, value, meaning, status]) => (
          <div className="parcel-fact-row" role="row" key={label}>
            <strong role="cell">{label}</strong><span role="cell" className="parcel-fact-value">{value}</span><span role="cell">{meaning}</span><span role="cell" className="parcel-fact-status">{status}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

export function OperationEvidenceMatrix({ investigation, report }: { investigation: Investigation; report: Report | null }) {
  const f = factorsOf(investigation);
  const ops = ((report?.sections?.["Operation Comparison"]?.highlights || []) as Obj[]).filter((item) => item.operation_id);
  const sharedKnown = [
    f.F01_TOPOGRAPHY ? "Parcel terrain context is available" : null,
    f.F05_CLIMATE_DROUGHT_EXPOSURE ? "Long-term climate context is available" : null,
    f.F06_PARCEL_CONFIGURATION ? "Parcel size and shape are measured" : null,
  ].filter(Boolean) as string[];
  const sharedUnknown = [
    "Usable forage and botanical condition need field confirmation",
    "No dependable livestock-water system is field verified",
    "Legal access and a usable ranch entrance are not confirmed",
  ];
  return (
    <section className="section-block report-section operation-matrix-section" id="ops" aria-labelledby="ops-title">
      <div className="report-section-heading"><div><span className="report-section-index">04</span><h2 id="ops-title">Cow-Calf vs. Sheep</h2></div></div>
      <div className="operation-honesty-note">The current approved evidence cannot distinguish between the two operations. No winner or fit score is claimed.</div>
      <div className="operation-matrix">
        {ops.slice(0, 2).map((op) => (
          <article key={String(op.operation_id)}>
            <h3>{operationLabel(String(op.operation_id))}{investigation.mode === "GOAL_DIRECTED" && op.operation_id === investigation.intended_operation ? " · selected" : ""}</h3>
            <span className="operation-public-status">More evidence needed</span>
            <h4>Known context</h4><ul>{sharedKnown.map((x) => <li key={x}>{x}</li>)}</ul>
            <h4>Decision-changing unknowns</h4><ul>{sharedUnknown.map((x) => <li key={x}>{x}</li>)}</ul>
          </article>
        ))}
      </div>
      {investigation.mode === "GOAL_DIRECTED" && <p className="muted">Selected profile presented first; the peer operation is still evaluated against the same evidence.</p>}
    </section>
  );
}
