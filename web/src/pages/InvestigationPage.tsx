import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  HOLD_COPY,
  INVESTIGATION_TERMINAL_STATUSES,
  api,
  operationLabel,
  type BuyerReport,
  type BuyerReportResponse,
  type DiligenceSearchResult,
  type Investigation,
  type ParcelResolution,
  type Report,
  type Trace,
} from "../api/client";
import { AppShell, Badge } from "../components/AppShell";
import { BuyerDashboard } from "../components/BuyerDashboard";
import { EvidenceDetails } from "../components/EvidenceDetails";
import { NarrativeBlock } from "../components/NarrativeBlock";
import { ProgressStages } from "../components/ProgressStages";
import { PublicResearchSection } from "../components/PublicResearchSection";
import { OperationEvidenceMatrix, ParcelFactsSummary } from "../components/ParcelDecisionBrief";
import { SectionPanel } from "../components/SectionPanel";

const SECTION_NAV = [
  { id: "executive", title: "Executive Summary" },
  { id: "unknowns", title: "Key Unknowns" },
  { id: "facts", title: "Parcel Facts" },
  { id: "ops", title: "Operation Comparison" },
  { id: "diligence", title: "Diligence Plan" },
  { id: "research", title: "Current Guidance" },
] as const;

const POLL_MS = 600;

function hasBuyerNarrative(buyer: BuyerReport | null | undefined) {
  return Boolean(
    buyer &&
      buyer.executive_summary &&
      buyer.property &&
      buyer.land_and_resources &&
      buyer.resilience_and_hazards &&
      buyer.operation_comparison &&
      buyer.key_unknowns &&
      buyer.diligence_plan,
  );
}

function readableDecision(label: string) {
  if (label === "HOLD") return "Evidence incomplete";
  if (label === "ADVANCE") return "Continue investigation";
  if (label === "REDIRECT") return "Consider another operation";
  if (label === "REJECT") return "Do not advance";
  return "Not evaluated";
}

export function InvestigationPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [buyerResp, setBuyerResp] = useState<BuyerReportResponse | null>(null);
  const [diligenceSearch, setDiligenceSearch] = useState<DiligenceSearchResult | null>(null);
  const [diligenceSearchStatus, setDiligenceSearchStatus] = useState<"IDLE" | "RUNNING" | "DONE">("IDLE");
  const [parcelResolution, setParcelResolution] = useState<ParcelResolution | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function loadTerminalExtras(inv: Investigation) {
      const params = new URLSearchParams(window.location.search);
      const providerParam = params.get("llm");
      const buyerProvider =
        providerParam === "openai" || providerParam === "OPENAI"
          ? "OPENAI"
          : providerParam === "fixture" || providerParam === "FIXTURE"
            ? "FIXTURE"
            : undefined;
      const hasUo = Boolean(inv.unified_output);
      const reportPromise = hasUo
        ? api.getReport(id).catch(() => null)
        : Promise.resolve(null);
      const parcelPromise = inv.parcel_resolution_id
        ? api.getParcelResolution(inv.parcel_resolution_id).catch(() => null)
        : Promise.resolve(null);

      // Parcel geometry and the deterministic report should not wait for the
      // slower LLM narrative. Reveal each trusted result as soon as it arrives.
      void reportPromise.then((rep) => {
        if (!cancelled) setReport(rep);
      });
      void parcelPromise.then((parcel) => {
        if (!cancelled) setParcelResolution(parcel);
      });

      const buyerPromise = hasUo
        ? api.generateBuyerReport(id, buyerProvider).catch((err: unknown) => {
              const message = err instanceof Error ? err.message : "buyer_report_failed";
              return {
                investigation_id: id,
                displayable: false,
                validation_status: "FAILED",
                buyer_report: null,
                validation_violations: [
                  { code: "CLIENT_FETCH_FAILED", message },
                ],
                report_provenance: {
                  provider_status: "FAILED_EXTERNAL",
                  displayable: false,
                },
              } satisfies BuyerReportResponse;
            })
        : Promise.resolve(null);
      setDiligenceSearchStatus("RUNNING");
      const searchPromise = hasUo
        ? api.runDiligenceSearch(id, buyerProvider).catch(() => null)
        : Promise.resolve(null);
      const [buyer, search] = await Promise.all([buyerPromise, searchPromise]);
      if (cancelled) return;
      setBuyerResp(buyer);
      setDiligenceSearch(search?.diligence_search || null);
      setDiligenceSearchStatus("DONE");
    }

    async function tick() {
      try {
        const inv = await api.getInvestigation(id);
        if (cancelled) return;
        setInvestigation(inv);
        const tr = await api.getTrace(id).catch(() => null);
        if (cancelled) return;
        setTrace(tr);
        setLoading(false);
        if (!INVESTIGATION_TERMINAL_STATUSES.has(inv.status)) {
          timer = setTimeout(() => {
            void tick();
          }, POLL_MS);
          return;
        }

        await loadTerminalExtras(inv);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "load_failed");
          setLoading(false);
        }
      }
    }

    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [id]);

  const replay = investigation?.replay_label === "REPLAY_DEMO_FIXTURE_NOT_LIVE";
  const mireyeBlocked = (investigation?.limitations || []).some((l) =>
    l.includes("BLOCKED_EXTERNAL"),
  );
  const uo = investigation?.unified_output as Record<string, unknown> | null | undefined;
  const mireyeContexts = (uo?.mireye_context as Record<string, unknown>[] | undefined) || [];
  const inProgress =
    investigation &&
    (investigation.status === "QUEUED" || investigation.status === "RUNNING" || diligenceSearchStatus === "RUNNING");
  const progressTrace: Trace | null = diligenceSearchStatus === "RUNNING"
    ? {
        ...(trace || { steps: [] }),
        steps: [
          ...(trace?.steps || []),
          { step_id: "diligence-search", tool_id: "diligence.web_search", action: "SEARCH", status: "RUNNING" },
        ],
      }
    : trace;

  const narrativeOk =
    buyerResp?.validation_status === "PASSED" &&
    buyerResp.displayable &&
    hasBuyerNarrative(buyerResp.buyer_report);
  const buyer = narrativeOk ? buyerResp!.buyer_report : null;
  const usingFallback = Boolean(!narrativeOk && report && investigation?.unified_output);

  const opsSection = report?.sections?.["Operation Comparison"];
  const opHighlights = ((opsSection?.highlights || []) as Record<string, unknown>[]).filter(
    (h) => typeof h.operation_id === "string" && h.operation_id,
  );
  const orderedOps = [...opHighlights].sort((a, b) => {
    const pa = typeof a.presentation_priority === "number" ? a.presentation_priority : 99;
    const pb = typeof b.presentation_priority === "number" ? b.presentation_priority : 99;
    return pa - pb;
  });
  const materialUnknownCount = buyer?.key_unknowns?.findings?.length ||
    report?.sections?.["Land & Resources"]?.unknowns?.length || 0;
  const completedFactorCount =
    uo?.factors && typeof uo.factors === "object"
      ? Object.keys(uo.factors as Record<string, unknown>).length
      : 0;

  const badges = (
    <>
      {replay && <Badge kind="replay">Demo result</Badge>}
      {mireyeBlocked && <Badge kind="blocked">Some sources unavailable</Badge>}
      {inProgress && <Badge kind="point">Analysis in progress</Badge>}
      <Link className="header-new-analysis" to="/">Analyze another property</Link>
    </>
  );

  if (loading && !investigation) {
    return (
      <AppShell badges={badges}>
        <div className="panel" role="status" data-testid="investigation-loading">
          Loading investigation…
        </div>
      </AppShell>
    );
  }

  if (error || !investigation) {
    return (
      <AppShell>
        <div className="error-banner" role="alert">
          {error || "investigation_not_found"}
        </div>
        <button className="btn btn-ghost" type="button" onClick={() => navigate("/")}>
          Back to intake
        </button>
      </AppShell>
    );
  }

  const blocked =
    investigation.status === "BLOCKED_EXTERNAL" ||
    investigation.status === "BLOCKED_INPUT";

  if (inProgress) {
    return (
      <AppShell badges={badges}>
        <div className="investigation-progress-shell" data-testid="investigation-progress">
          <header className="analysis-progress-hero">
            <div>
              <p className="analysis-eyebrow">One parcel · evidence-led analysis</p>
              <h1>Your land investigation is underway</h1>
              <p>
                RangeMatch is coordinating specialist agents across physical-world data,
                agricultural evidence, and the deterministic matching engine.
              </p>
            </div>
            <div className="analysis-run-meta">
              <span>{investigation.mode === "DISCOVERY" ? "General exploration" : operationLabel(investigation.intended_operation)}</span>
              <small>Run {investigation.investigation_id.slice(-8)}</small>
            </div>
          </header>

          <div className="analysis-progress-body">
            <ProgressStages trace={progressTrace} />
            <aside className="analysis-trust-panel" aria-label="Analysis safeguards">
              <p className="analysis-eyebrow">What stays true</p>
              <h2>Evidence before conclusion</h2>
              <div className="analysis-trust-card">
                <strong>One confirmed parcel</strong>
                <span>Every source remains bound to the same geometry.</span>
              </div>
              <div className="analysis-trust-card">
                <strong>Fixed agricultural rules</strong>
                <span>The LLM cannot change Factor science or Engine labels.</span>
              </div>
              <div className="analysis-trust-card">
                <strong>Unknown stays unknown</strong>
                <span>Missing or blocked evidence becomes diligence—not a guess.</span>
              </div>
              <p className="analysis-live-note">
                This page follows the real workflow. It may pause while external sources respond.
              </p>
            </aside>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell badges={badges}>
      {!blocked && investigation.unified_output && (
        <BuyerDashboard
          investigation={investigation}
          report={report}
          buyer={buyer}
          parcelResolution={parcelResolution}
        />
      )}
      <header className={`report-hero legacy-report-hero${blocked ? " is-blocked" : ""}`}>
        <div className="report-hero-copy">
          <p className="analysis-eyebrow">
            {blocked ? "Investigation blocked" : "RangeMatch land investigation"}
          </p>
          <h1>
            {blocked
              ? "We could not complete this investigation."
              : investigation.status === "FAILED"
                ? "This investigation needs to be restarted."
                : "The land remains worth investigating."}
          </h1>
          <p className="report-hero-lede">
            {blocked
              ? "The parcel or an essential external source could not be resolved. No substitute geometry was used."
              : "The reviewed evidence does not support a rejection, but material questions remain before a confident cattle or sheep decision."}
          </p>
          {!blocked && investigation.status !== "FAILED" && (
            <div className="report-hold-message" role="note">
              <span>Current decision</span>
              <strong>HOLD</strong>
              <p>{HOLD_COPY}</p>
            </div>
          )}
          <div className="report-hero-actions">
            {!blocked && investigation.unified_output && (
              <a className="btn btn-primary" href="#ops">Compare operations</a>
            )}
            <a className="btn report-ghost-button" href="#evidence-details">Review evidence</a>
            <Link className="btn report-ghost-button" to="/">New investigation</Link>
          </div>
        </div>
        <div className="report-run-card">
          <p>Investigation snapshot</p>
          <dl>
            <div><dt>Mode</dt><dd>{investigation.mode === "DISCOVERY" ? "General exploration" : operationLabel(investigation.intended_operation)}</dd></div>
            <div><dt>Reviewed</dt><dd>{completedFactorCount || 8} land Factors</dd></div>
            <div><dt>Open questions</dt><dd>{materialUnknownCount || "Material gaps remain"}</dd></div>
            <div><dt>Ranking</dt><dd>Not permitted</dd></div>
          </dl>
          <details>
            <summary>Run details</summary>
            <code>{investigation.investigation_id}</code>
            {replay && <p><Badge kind="replay">Replay demo fixture</Badge></p>}
          </details>
        </div>
      </header>

      {blocked && (
        <div className="panel">
          <div className="error-banner" role="status">
            No fabricated geometry or silent fixture substitution. Resolve live parcel input
            or run the explicit CPER demo fixture from intake.
          </div>
        </div>
      )}

      {!blocked && narrativeOk && buyer && (
        <div className="report-layout" data-testid="buyer-narrative">
          <aside className="report-sidebar">
            <p className="analysis-eyebrow">Your report</p>
            <nav className="report-section-nav" aria-label="Report sections">
              {SECTION_NAV.map((s, index) => (
                <a key={s.id} href={`#${s.id}`}><span>{String(index + 1).padStart(2, "0")}</span>{s.title}</a>
              ))}
            </nav>
            <div className="report-sidebar-note">
              <strong>How to read this</strong>
              <p>Start with the conclusion, then use unknowns and diligence actions to decide what to verify next.</p>
            </div>
          </aside>
          <main className="report-main">

          <NarrativeBlock
            id="executive"
            title="Executive Summary"
            section={buyer.executive_summary}
          />
          <NarrativeBlock
            id="unknowns"
            title="Key Unknowns"
            section={buyer.key_unknowns}
          />
          <ParcelFactsSummary investigation={investigation} />
          <OperationEvidenceMatrix investigation={investigation} report={report} />

          <NarrativeBlock
            id="diligence"
            title="Diligence Plan"
            section={buyer.diligence_plan}
          />

          <PublicResearchSection result={diligenceSearch} />

          {buyer.methodology_and_limitations && (
            <NarrativeBlock
              id="methodology"
              title="Methodology and limitations"
              section={buyer.methodology_and_limitations}
            />
          )}
          </main>
        </div>
      )}

      {!blocked && usingFallback && report && (
        <div className="panel" data-testid="deterministic-fallback">
          <nav className="section-nav" aria-label="Report sections">
            {SECTION_NAV.filter((s) => s.id !== "executive" && s.id !== "unknowns").map((s) => (
              <a key={s.id} href={`#${s.id}`}>
                {s.title}
              </a>
            ))}
          </nav>

          <section className="section-block" id="unknowns" aria-labelledby="unknowns-title">
            <h2 id="unknowns-title">Key Unknowns</h2>
            <ul className="unknown-list">
              {(
                report.sections["Land & Resources"]?.unknowns ||
                report.sections["Operation Comparison"]?.unknowns ||
                []
              )
                .slice(0, 8)
                .map((u) => (
                  <li key={u} className="highlight-item" style={{ background: "var(--verify-bg)" }}>
                    {u}
                  </li>
                ))}
            </ul>
          </section>

          <SectionPanel
            id="property"
            title="Property"
            body={report.sections.Property}
          >
            <p className="muted">
              Includes F06 configuration and F07 mapped-road physical context. Legal access
              remains diligence — not a Property conclusion.
            </p>
          </SectionPanel>

          <SectionPanel
            id="land"
            title="Land & Resources"
            body={report.sections["Land & Resources"]}
          />

          <SectionPanel
            id="hazards"
            title="Resilience & Hazards"
            body={report.sections["Resilience & Hazards"]}
          >
            {mireyeContexts.length > 0 && (
              <ul className="highlight-list" style={{ marginBottom: "0.75rem" }}>
                {mireyeContexts.map((m, i) => (
                  <li key={i} className="highlight-item">
                    {m.disposition === "BLOCKED_EXTERNAL"
                      ? "An additional location check was unavailable and remains follow-up work."
                      : "Additional location information was reviewed; confirm parcel-wide conditions during diligence."}
                  </li>
                ))}
              </ul>
            )}
          </SectionPanel>

          <PublicResearchSection result={diligenceSearch} />

          <section className="section-block" id="ops" aria-labelledby="ops-title">
            <h2 id="ops-title">Operation Comparison</h2>
            <p className="muted">
              {investigation.mode === "GOAL_DIRECTED"
                ? "Selected profile presented first. Peer profile still evaluated."
                : "Cow-Calf and Sheep as peers. No best-use claim."}{" "}
              Results remain preliminary until the listed field checks are completed.
            </p>
            <div className="op-grid">
              {orderedOps.map((op) => {
                const oid = String(op.operation_id || "");
                const isPrimary =
                  investigation.mode === "GOAL_DIRECTED" &&
                  oid === investigation.intended_operation;
                return (
                  <article
                    key={oid}
                    className={`op-card${isPrimary ? " primary" : ""}`}
                    aria-label={operationLabel(oid)}
                  >
                    <h3 style={{ margin: "0 0 0.35rem", fontFamily: "var(--font-display)" }}>
                      {operationLabel(oid)}
                      {isPrimary ? " · selected" : ""}
                    </h3>
                    <p style={{ margin: 0 }}>
                      Current status: <strong>{readableDecision(String(op.decision_label))}</strong>
                    </p>
                    {String(op.decision_label) === "HOLD" && (
                      <p className="hold-callout" style={{ marginTop: "0.55rem" }}>
                        {HOLD_COPY}
                      </p>
                    )}
                  </article>
                );
              })}
            </div>
          </section>

          <SectionPanel
            id="diligence"
            title="Diligence Plan"
            body={report.sections["Diligence Plan"]}
          />
        </div>
      )}

      {!blocked && (investigation.unified_output || (trace?.steps || []).length > 0) && (
        <div className="panel report-evidence-shell">
          <EvidenceDetails investigation={investigation} report={report} trace={trace} />
        </div>
      )}
    </AppShell>
  );
}
