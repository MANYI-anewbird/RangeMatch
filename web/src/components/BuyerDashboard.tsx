import {
  ArrowRight,
  CloudRain,
  Cow,
  Drop,
  Leaf,
  MapTrifold,
  Mountains,
  ShieldCheck,
  Tree,
} from "@phosphor-icons/react";
import type {
  BuyerReport,
  Investigation,
  ParcelResolution,
  Report,
} from "../api/client";
import { operationLabel } from "../api/client";
import { ParcelMap } from "./ParcelMap";

type Factor = Record<string, unknown>;
type LandFact = Record<string, unknown>;

function factorMap(investigation: Investigation): Record<string, Factor> {
  const value = (investigation.unified_output as Record<string, unknown> | null)?.factors;
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, Factor>)
    : {};
}

function fact(factors: Record<string, Factor>, factorId: string, variableId: string) {
  const facts = (factors[factorId]?.land_facts as LandFact[] | undefined) || [];
  return facts.find((item) => item.variable_id === variableId);
}

function numeric(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function fmt(value: number | null, digits = 0) {
  return value == null ? "Not available" : value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function evidenceConfidence(factors: Record<string, Factor>) {
  const values = Object.values(factors);
  if (!values.length) return { label: "Low", ratio: 0 };
  const score = values.reduce((sum, item) => {
    const signal = String(item.signal || "UNKNOWN");
    if (signal === "CONTEXT_DEPENDENT") return sum + 1;
    if (signal === "NEEDS_VERIFICATION") return sum + 0.55;
    return sum;
  }, 0);
  const ratio = score / 8;
  const hasMaterialGap = values.some((item) =>
    ["NEEDS_VERIFICATION", "UNKNOWN"].includes(String(item.signal || "UNKNOWN")),
  );
  const rawLabel = ratio >= 0.72 ? "High" : ratio >= 0.38 ? "Moderate" : "Low";
  // A mostly populated profile can still have material verification gaps.
  // Never label evidence High while any Factor remains unknown or needs verification.
  return { label: hasMaterialGap && rawLabel === "High" ? "Moderate" : rawLabel, ratio };
}

function diligenceLabel(value: unknown) {
  const text = String(value || "");
  const lower = text.toLowerCase();
  if (lower.includes("water") && (lower.includes("reliability") || lower.includes("source operation"))) {
    return "Verify water availability and reliability";
  }
  if (lower.includes("legal access") || lower.includes("mapped road")) {
    return "Confirm legal access and usable roads";
  }
  if (lower.includes("botanical") || lower.includes("rap eligible") || lower.includes("vegetation")) {
    return "Walk the property and verify forage conditions";
  }
  const firstClause = text.split(/[.;]/)[0]?.trim();
  return firstClause || "Review the remaining evidence gap";
}

function decisionCopy(label: string) {
  if (label === "HOLD") return "Evidence incomplete";
  if (label === "ADVANCE") return "Continue investigation";
  if (label === "REDIRECT") return "Consider another operation";
  if (label === "REJECT") return "Do not advance";
  return label || "Not evaluated";
}

export function BuyerDashboard({
  investigation,
  report,
  buyer,
  parcelResolution,
}: {
  investigation: Investigation;
  report: Report | null;
  buyer: BuyerReport | null;
  parcelResolution: ParcelResolution | null;
}) {
  const factors = factorMap(investigation);
  const confidence = evidenceConfidence(factors);
  const ops = ((report?.sections?.["Operation Comparison"]?.highlights || []) as Record<string, unknown>[])
    .filter((item) => item.operation_id);
  const decision = String(ops[0]?.decision_label || "HOLD");
  const areaM2 = numeric(fact(factors, "F06_PARCEL_CONFIGURATION", "VAR_F06_AREA_M2")?.value);
  const acres = areaM2 == null ? null : areaM2 / 4046.8564224;
  const precip = numeric(fact(factors, "F05_CLIMATE_DROUGHT_EXPOSURE", "VAR_F05_MEAN_ANNUAL_PRECIPITATION")?.value);
  const climateFactor = factors["F05_CLIMATE_DROUGHT_EXPOSURE"] || {};
  const climateExtras =
    (climateFactor.evaluation_extras as Record<string, unknown> | undefined) || {};
  const climateCoverage =
    (climateFactor.coverage as Record<string, unknown> | undefined) || {};
  const climatePeriod = String(climateExtras.normals_period || "Not specified");
  const climateCoverageLabel =
    String(climateCoverage.normalized_status || "") === "COMPLETE"
      ? "Complete parcel context"
      : "Coverage needs review";
  const herb = numeric(fact(factors, "F02_HERBACEOUS_RESOURCE", "VAR_F02_PERENNIAL_HERB_COVER")?.value);
  const production = numeric(fact(factors, "F02_HERBACEOUS_RESOURCE", "VAR_F02_ANNUAL_HERB_PRODUCTION")?.value);
  const waterCandidates = numeric(fact(factors, "F03_LIVESTOCK_WATER", "VAR_F03_MAPPED_WATER_CANDIDATE_COUNT")?.value);
  const verifiedWater = numeric(fact(factors, "F03_LIVESTOCK_WATER", "VAR_F03_FIELD_VERIFIED_LIVESTOCK_WATER_COUNT")?.value);
  const roadDistance = numeric(fact(factors, "F07_ROAD_AND_PHYSICAL_ACCESS", "VAR_F07_NEAREST_MAPPED_ROAD_DISTANCE_M")?.value);
  const shrub = numeric(fact(factors, "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE", "VAR_F08_SHRUB_COVER_FRACTION")?.value);
  const tree = numeric(fact(factors, "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE", "VAR_F08_TREE_COVER_FRACTION")?.value);
  const selectedId = parcelResolution?.selection?.selected_candidate_id || null;
  const confirmed = parcelResolution?.status === "PARCEL_CONFIRMED";
  const diligence = buyer?.diligence_plan?.findings || report?.sections?.["Diligence Plan"]?.diligence_actions || [];

  return (
    <section className="buyer-dashboard" data-testid="buyer-dashboard" aria-label="Buyer decision dashboard">
      <div className="dashboard-main-column">
        <div className="dashboard-map-shell">
          {parcelResolution?.candidates?.length ? (
            <ParcelMap
              candidates={parcelResolution.candidates}
              selectedCandidateId={selectedId}
              confirmed={confirmed}
              interactive={false}
              onSelectCandidate={() => undefined}
            />
          ) : (
            <div className="dashboard-map-empty"><MapTrifold size={34} /><span>Parcel map unavailable for this saved run</span></div>
          )}
          <div className="dashboard-parcel-callout">
            <span>Confirmed parcel</span>
            <strong>{acres == null ? "Area unavailable" : `${fmt(acres)} acres`}</strong>
            <small>Mapped boundary · confirm by survey before purchase</small>
          </div>
          <div className="dashboard-map-facts">
            <span><MapTrifold size={18} /> Nearest mapped road <strong>{roadDistance == null ? "Unknown" : `${fmt(roadDistance, 1)} m`}</strong></span>
            <span><Drop size={18} /> Mapped water candidates <strong>{fmt(waterCandidates)}</strong></span>
            <span><ShieldCheck size={18} /> Field-verified systems <strong>{fmt(verifiedWater)}</strong></span>
          </div>
        </div>

        <div className="dashboard-season-strip">
          <div className="dashboard-climate-total"><CloudRain size={28} /><strong>{precip == null ? "Not available" : `${fmt(precip)} mm/year`}</strong><span>Annual precipitation context</span></div>
          <div className="dashboard-climate-detail"><strong>{climatePeriod}</strong><span>Climate normal period</span></div>
          <div className="dashboard-climate-detail"><strong>{climateCoverageLabel}</strong><span>Data coverage</span></div>
          <div className="dashboard-climate-detail"><strong>Context only</strong><span>Not a livestock fit score</span></div>
        </div>

        <div className="dashboard-resource-row">
          <div className="dashboard-resource-block">
            <p>Vegetation summary <span>Modeled context</span></p>
            <div><Leaf size={26} /><strong>{herb == null ? "—" : `${fmt(herb, 1)}%`}</strong><small>Perennial herb cover</small></div>
            <div><Mountains size={26} /><strong>{production == null ? "—" : `${fmt(production)} lb/ac`}</strong><small>Modeled production</small></div>
            <div><Tree size={26} /><strong>{shrub == null ? "—" : `${fmt(shrub * 100, 1)}%`}</strong><small>Shrub cover</small></div>
            <div><Tree size={26} /><strong>{tree == null ? "—" : `${fmt(tree * 100, 1)}%`}</strong><small>Tree cover</small></div>
          </div>
          <div className="dashboard-resource-block water-block">
            <p>Water summary <span>Field verification required</span></p>
            <div><Drop size={28} weight="fill" /><strong>{fmt(waterCandidates)}</strong><small>Mapped candidates</small></div>
            <div><Drop size={28} /><strong>{fmt(verifiedWater)}</strong><small>Field-verified systems</small></div>
          </div>
        </div>
        <div className="dashboard-evidence-legend"><span>● Modeled or mapped facts</span><span>○ Verification gaps remain</span></div>
      </div>

      <aside className="dashboard-decision-column">
        <div className="dashboard-decision">
          <span>Current decision</span><h2>{decisionCopy(decision)}</h2><p>{decision === "HOLD" ? "The land did not fail; material evidence remains incomplete." : "Evidence supports the current Engine decision."}</p>
        </div>
        <div className="dashboard-fit-panel">
          <p>Operation fit <span>Engine-bound</span></p>
          {ops.slice(0, 2).map((op) => (
            <div className="dashboard-fit-row" key={String(op.operation_id)}>
              <div className="dashboard-animal-icon">
                {String(op.operation_id) === "SHEEP_GRAZING"
                  ? <span aria-hidden="true">S</span>
                  : <Cow size={28} weight="fill" />}
              </div>
              <div><strong>{operationLabel(String(op.operation_id))}</strong><h3>{decisionCopy(String(op.decision_label))}</h3><small>No directional fit score is approved yet.</small></div>
              <div className="dashboard-band" aria-label="Evidence incomplete"><i /><i /><i className="active" /><i /></div>
            </div>
          ))}
        </div>
        <div className="dashboard-confidence">
          <ShieldCheck size={34} /><div><span>Evidence confidence</span><h3>{confidence.label}</h3><p>{Math.round(confidence.ratio * 8)} of 8 land checks have usable information.</p></div>
        </div>
        <div className="dashboard-actions">
          <p>Top diligence actions</p>
          {diligence.slice(0, 3).map((item, index) => <a href="#diligence" key={index}><b>{index + 1}</b><span>{diligenceLabel(item)}</span><ArrowRight size={18} /></a>)}
        </div>
        <div className="dashboard-core-actions">
          <a className="primary" href="#executive">Read plain-language report <ArrowRight /></a>
          <a href="#ops">Compare operations <ArrowRight /></a>
          <a href="#evidence-details">Open evidence appendix <ArrowRight /></a>
        </div>
      </aside>
    </section>
  );
}
