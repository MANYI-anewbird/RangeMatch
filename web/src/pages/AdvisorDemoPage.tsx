import { useState } from "react";
import type { FeatureCollection } from "geojson";
import { AdvisorCopyButton } from "../components/advisor/AdvisorCopyButton";
import { AdvisorDemoMap } from "../components/advisor/AdvisorDemoMap";
import "../styles/advisor-demo.css";

type VisitPurpose =
  | "VISIT_PURPOSE_DEFINED"
  | "VISIT_DEPENDS_ON_DOCUMENT"
  | "NO_DEFINED_VISIT_PURPOSE_YET";

type Message = {
  message_id: string;
  audience: string;
  bound_action_id: string;
  bound_claim_id?: string | null;
  body: string;
};

type Candidate = {
  candidate_id: string;
  candidate_type: string;
  display_name?: string | null;
  geometry?: {
    kind?: string;
    bbox?: number[];
    field_navigation_precision?: string;
  };
  review_status?: string;
  evidence_state?: string;
};

type ClaimGap = {
  claim_id: string;
  claim: string;
  supported_portion?: string;
  unsupported_portion?: string[];
};

type AgentStep = {
  step_id: string;
  label: string;
  status: "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED";
};

type AgendaStep = {
  step_id: string;
  label: string;
  tool_id?: string | null;
  status: "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED" | string;
};

type MireyeLive = {
  mode?: string;
  allow_network?: boolean;
  lookup?: {
    ok?: boolean;
    error_class?: string | null;
    http_status?: number | null;
    endpoint?: string;
    disposition?: string | null;
  };
  requested_point?: { lat?: number; lng?: number };
  contexts?: Record<string, { status?: string; error_class?: string | null }>;
};

type AgentRun = {
  status: "QUEUED" | "SUCCEEDED" | "FAILED" | "RUNNING";
  run_id: string;
  generated_at: string;
  address?: string | null;
  fixture_id?: string | null;
  packet_hash: string | null;
  llm_used: boolean;
  failed_step: string | null;
  error: string | null;
  steps: AgentStep[];
  agenda?: AgendaStep[];
  limitations?: string[];
  mireye_live?: MireyeLive | null;
  buyer_explanation?: {
    source: string;
    validation_status: string;
    sections: {
      recommendation: string;
      why: string;
      listing_jumps: string;
      do_now: string;
      if_changes: string;
      professional_reminders: string;
    };
    provenance?: { provider_status?: string; provider?: string };
  } | null;
  packet: {
    parcel: { display_label?: string | null; parcel_id?: string };
    bottlenecks: Array<{ bottleneck_id: string; title: string }>;
    actions: Array<{ execution_order: number; why_now?: string }>;
    candidate_objects: Candidate[];
    listing_claims?: Array<{ claim_id: string; text: string }>;
    claim_evidence_gaps?: ClaimGap[];
  } | null;
  brief: {
    page_one_advisor: {
      how_the_tract_reads: string;
      listing_outruns_evidence: string[];
      do_today: string[];
      visit_purpose: VisitPurpose;
      visit_guidance: string;
      what_changes_next: string;
      what_not_to_recheck: string[];
    };
    page_two_actions: { messages: Message[] };
    page_three_kitchen: {
      observations: Array<Record<string, unknown>>;
      source_notes: Array<Record<string, unknown>>;
      coverage_and_limitations: Array<Record<string, unknown>>;
      engine_appendix: Record<string, unknown>;
      map_layers: Array<{
        layer_id: string;
        candidate_type?: string;
        display_name?: string | null;
        bbox?: number[];
      }>;
    };
  } | null;
  parcel_geometry: FeatureCollection | null;
};

const IDLE_STEPS: AgentStep[] = [
  { step_id: "ACCEPT_PLACE", label: "Accept place", status: "PENDING" },
  { step_id: "RESOLVE_PARCEL", label: "Resolve parcel", status: "PENDING" },
  { step_id: "CALL_MIREYE", label: "Call Mireye", status: "PENDING" },
  { step_id: "BUILD_AGENDA", label: "Build agenda", status: "PENDING" },
  { step_id: "RUN_AGENDA", label: "Run agenda", status: "PENDING" },
  { step_id: "COMPARE_CLAIMS", label: "Compare claims", status: "PENDING" },
  { step_id: "ORDER_ACTIONS", label: "Order actions", status: "PENDING" },
  { step_id: "VALIDATE_BRIEF", label: "Validate brief", status: "PENDING" },
];

const CPER_DEMO_ADDRESS = "Central Plains Experimental Range Demo, Nunn, CO";
const OTHER_DEMO_ADDRESS = "100 Demo Ranch Rd, Weld County, CO 80701";

const AUDIENCE_LABEL: Record<string, string> = {
  LISTING_BROKER: "Listing broker",
  TITLE_OR_COUNSEL: "Title / counsel",
  FIELD_VISITOR: "Field visitor",
  PARTNER: "Partner",
};

const AUDIENCE_JOB: Record<string, string> = {
  LISTING_BROKER: "Ask what “excellent water” actually is",
  TITLE_OR_COUNSEL: "Ask whether the road contact is a recorded entrance",
  FIELD_VISITOR: "If the visit happens, walk mapped water areas",
  PARTNER: "Tell the client the trip is not the first spend",
};

const VISIT_HEADLINE: Record<VisitPurpose, string> = {
  VISIT_PURPOSE_DEFINED: "The visit has a defined job",
  VISIT_DEPENDS_ON_DOCUMENT: "Do not send the client yet",
  NO_DEFINED_VISIT_PURPOSE_YET: "Do not visit yet",
};

const VISIT_STATUS: Record<VisitPurpose, string> = {
  VISIT_PURPOSE_DEFINED: "Visit has a defined purpose",
  VISIT_DEPENDS_ON_DOCUMENT: "Visit depends on access paper",
  NO_DEFINED_VISIT_PURPOSE_YET: "No defined visit purpose yet",
};

const CLAIM_PLAIN: Record<string, string> = {
  CLAIM_WATER_001: "The map has water leads. That is not a drinker.",
  CLAIM_ACCESS_001: "A road meets the boundary. That is not a recorded entrance.",
  CLAIM_FORAGE_001: "There is a growth snapshot. That is not a stocking plan.",
};

const KIND_LABEL: Record<string, string> = {
  WATERBODY: "Pond / waterbody",
  FLOWLINE: "Creek / channel",
};

function audienceRank(audience: string): number {
  if (audience === "TITLE_OR_COUNSEL") return 0;
  if (audience === "LISTING_BROKER") return 1;
  if (audience === "PARTNER") return 2;
  return 3;
}

function shortId(value: string | null | undefined): string {
  if (!value) return "—";
  return value.length > 16 ? `${value.slice(0, 12)}…` : value;
}

function prettyTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
}

function objectLabel(row: Candidate): string {
  return row.display_name || KIND_LABEL[row.candidate_type] || row.candidate_type;
}

async function readRun(response: Response): Promise<AgentRun & { detail?: string }> {
  return (await response.json()) as AgentRun & { detail?: string };
}

type ExplanationProvider = "OPENAI" | "FIXTURE";

export function AdvisorDemoPage() {
  const [address, setAddress] = useState(CPER_DEMO_ADDRESS);
  const [run, setRun] = useState<AgentRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [clientError, setClientError] = useState<string | null>(null);
  const [explainBusy, setExplainBusy] = useState(false);
  /** Explicit choice: LIVE LLM (OPENAI) or structured fixture. Default LIVE. */
  const [explanationProvider, setExplanationProvider] =
    useState<ExplanationProvider>("OPENAI");

  async function runAgent() {
    const place = address.trim();
    setBusy(true);
    setClientError(null);
    setRun(null);
    try {
      const response = await fetch("/v1/advisor/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ address: place }),
      });
      let body = await readRun(response);
      if (!response.ok) {
        setClientError(
          typeof body.detail === "string"
            ? body.detail
            : `Run failed (${response.status}). Start the API on port 8001.`,
        );
        return;
      }
      setRun(body);
      while (body.status === "QUEUED" || body.status === "RUNNING") {
        await new Promise((resolve) => window.setTimeout(resolve, 180));
        const poll = await fetch(`/v1/advisor/runs/${body.run_id}`, {
          headers: { Accept: "application/json" },
        });
        body = await readRun(poll);
        setRun(body);
        if (!poll.ok) {
          setClientError("The Agent run could not be read. Try again.");
          return;
        }
      }
    } catch {
      setClientError(
        "The Agent API did not respond. Start `uvicorn rangematch.api:app --port 8001`, then run again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function explainBuyer() {
    if (!run?.run_id) return;
    setExplainBusy(true);
    setClientError(null);
    try {
      const response = await fetch(`/v1/advisor/runs/${run.run_id}/buyer-explanation`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ provider: explanationProvider }),
      });
      const body = await readRun(response);
      if (!response.ok) {
        setClientError(
          typeof body.detail === "string"
            ? body.detail
            : "Buyer explanation failed. The deterministic brief stays on screen.",
        );
        return;
      }
      setRun(body);
    } catch {
      setClientError("Buyer explanation failed. The deterministic brief stays on screen.");
    } finally {
      setExplainBusy(false);
    }
  }

  const steps = run?.steps?.length
    ? run.steps
    : busy
      ? IDLE_STEPS.map((row, index) =>
          index === 0 ? { ...row, status: "RUNNING" as const } : row,
        )
      : IDLE_STEPS;
  const failed = Boolean(clientError || run?.status === "FAILED");
  const succeeded = run?.status === "SUCCEEDED" && run.brief && run.packet;

  return (
    <div className="advisor-demo">
      <header className="advisor-top">
        <div>
          <p className="advisor-kicker">Mireye Build Challenge · Advisor Demo</p>
          <h1>RangeMatch</h1>
          <p className="advisor-tag">
            Know what to verify before you visit or spend.
          </p>
          <p className="advisor-payer">
            Built for buyer-side ranch brokers and land advisors deciding what to
            verify before their client travels or spends.
          </p>
        </div>
        <div className="advisor-badges">
          <span className="advisor-badge">Deterministic agent</span>
          <span className="advisor-badge">
            {explanationProvider === "OPENAI"
              ? "Buyer explanation: LIVE LLM"
              : "Buyer explanation: structured fixture"}
          </span>
          <span className="advisor-badge advisor-badge-warn">
            CPER engineering test geometry — not a listing
          </span>
        </div>
      </header>

      <section className="advisor-mireye" aria-label="Mireye contribution">
        <p>
          <strong>Mireye</strong> is called live on this Demo:{" "}
          <code>POST /v1/lookup</code> on the typed place, then{" "}
          <code>/v1/lookup</code> + <code>/v1/fetch</code> at the parcel
          centroid. A green step means HTTP succeeded.{" "}
          <code>BLOCKED_EXTERNAL</code> or <code>FAILED</code> is the real
          transport, token, or API result — not a silent fixture success.
        </p>
        {run?.mireye_live ? <MireyeLivePanel live={run.mireye_live} /> : null}
      </section>

      <section className="advisor-run" aria-label="Run the agent">
        <div className="advisor-run-select">
          <h2>Enter a place, then run the Agent</h2>
          <label className="advisor-address-label" htmlFor="advisor-address">
            Place
          </label>
          <input
            id="advisor-address"
            className="advisor-address"
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            placeholder="Address or named ranch location"
            disabled={busy}
          />
          <div className="advisor-place-chips">
            <button
              type="button"
              className="advisor-chip"
              disabled={busy}
              onClick={() => setAddress(CPER_DEMO_ADDRESS)}
            >
              CPER demo, Nunn, CO
            </button>
            <button
              type="button"
              className="advisor-chip"
              disabled={busy}
              onClick={() => setAddress(OTHER_DEMO_ADDRESS)}
            >
              100 Demo Ranch Rd
            </button>
          </div>
          <p className="advisor-quiet">
            The Agent resolves the place, calls live Mireye, builds an agenda,
            then runs it. This Challenge Demo can complete a Decision Brief only
            for the CPER engineering tract. Other places can be entered; they
            fail closed instead of inventing a report.
          </p>
        </div>
        <div className="advisor-run-toolbar">
          <button
            type="button"
            className="advisor-run-button"
            onClick={() => void runAgent()}
            disabled={busy || !address.trim()}
          >
            {busy ? "Running investigation…" : succeeded ? "Run again" : "Run investigation"}
          </button>
          {succeeded && (
            <div className="advisor-explain-controls">
              <label className="advisor-address-label" htmlFor="advisor-explanation-provider">
                Buyer explanation provider
              </label>
              <select
                id="advisor-explanation-provider"
                className="advisor-address"
                value={explanationProvider}
                disabled={explainBusy}
                onChange={(event) =>
                  setExplanationProvider(event.target.value as ExplanationProvider)
                }
              >
                <option value="OPENAI">LIVE LLM (OpenAI)</option>
                <option value="FIXTURE">Structured fixture</option>
              </select>
              <button
                type="button"
                className="advisor-chip"
                disabled={explainBusy}
                onClick={() => void explainBuyer()}
              >
                {explainBusy
                  ? "Generating explanation…"
                  : explanationProvider === "OPENAI"
                    ? "Generate buyer explanation (LIVE LLM)"
                    : "Generate buyer explanation (fixture)"}
              </button>
              <p className="advisor-quiet">
                LIVE LLM calls{" "}
                <code>POST …/buyer-explanation</code> with{" "}
                <code>{`{"provider":"OPENAI"}`}</code>. If the key is missing or
                validation fails, the API returns a deterministic fallback — it
                does not silently swap the fixture.
              </p>
            </div>
          )}
          {run && (run.status === "SUCCEEDED" || run.status === "FAILED") && (
            <p className="advisor-run-meta">
              This run · <code>{run.run_id}</code> · {prettyTime(run.generated_at)}
              {run.packet_hash ? (
                <>
                  {" "}
                  · packet{" "}
                  <code title={run.packet_hash}>{shortId(run.packet_hash)}</code>
                </>
              ) : null}
            </p>
          )}
        </div>
        <ol className="advisor-steps">
          {steps.map((step) => (
            <li
              key={step.step_id}
              className={`advisor-step advisor-step-${step.status.toLowerCase()}`}
            >
              <span className="advisor-step-label">{step.label}</span>
              <span className="advisor-step-status">{step.status}</span>
            </li>
          ))}
        </ol>
        {(run?.agenda?.length || 0) > 0 && (
          <ol className="advisor-agenda" aria-label="Agenda system">
            {run?.agenda?.map((row) => (
              <li
                key={row.step_id}
                className={`advisor-agenda-item advisor-step-${String(row.status).toLowerCase()}`}
              >
                <span>{row.label}</span>
                <code>{row.tool_id}</code>
                <em>{row.status}</em>
              </li>
            ))}
          </ol>
        )}
        {failed && (
          <p className="advisor-run-error" role="alert">
            {clientError ||
              `${run?.failed_step || "Agent"} failed: ${run?.error || "unknown error"}. Previous output was cleared.`}
          </p>
        )}
        {(run?.limitations?.length || 0) > 0 && (
          <ul className="advisor-limitations">
            {run?.limitations?.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        )}
        {!busy && !run && !clientError && (
          <p className="advisor-quiet">
            No brief yet. Enter a place and click Run investigation. You should
            see the agenda move from pending to running to succeeded.
          </p>
        )}
      </section>

      {succeeded ? <AdvisorBriefResult run={run} /> : null}
    </div>
  );
}

function MireyeLivePanel({ live }: { live: MireyeLive }) {
  const lookup = live.lookup;
  const point = live.requested_point;
  const rows = Object.entries(live.contexts || {});
  return (
    <dl className="advisor-mireye-live">
      <div>
        <dt>Lookup</dt>
        <dd>
          {lookup?.ok ? "ok" : lookup?.error_class || "pending"}
          {lookup?.http_status != null ? ` · HTTP ${lookup.http_status}` : ""}
          {lookup?.disposition ? ` · ${lookup.disposition}` : ""}
        </dd>
      </div>
      {point?.lat != null && point?.lng != null ? (
        <div>
          <dt>Centroid</dt>
          <dd>
            {point.lat.toFixed(4)}, {point.lng.toFixed(4)}
          </dd>
        </div>
      ) : null}
      {rows.map(([name, row]) => (
        <div key={name}>
          <dt>{name.replaceAll("_", " ")}</dt>
          <dd>
            {row.status}
            {row.error_class ? ` · ${row.error_class}` : ""}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function AdvisorBriefResult({ run }: { run: AgentRun }) {
  const brief = run.brief;
  const packet = run.packet;
  if (!brief || !packet) return null;
  const pageOne = brief.page_one_advisor;
  const visitPurpose = pageOne.visit_purpose;
  const messages = [...brief.page_two_actions.messages].sort(
    (a, b) => audienceRank(a.audience) - audienceRank(b.audience),
  );
  const kitchen = brief.page_three_kitchen;
  const objects = packet.candidate_objects || [];
  const drawable = objects.filter(
    (row) => row.geometry?.field_navigation_precision === "AREA_ONLY",
  );
  const inventoryOnly = objects.filter(
    (row) => row.geometry?.field_navigation_precision === "NOT_NAVIGABLE",
  );
  const water = packet.bottlenecks.find(
    (row) => row.bottleneck_id === "BOTTLENECK_WATER_EVIDENCE",
  );
  const first = [...packet.actions].sort(
    (a, b) => a.execution_order - b.execution_order,
  )[0];
  const claims = (packet.claim_evidence_gaps || []).slice(0, 3);
  const claimRows =
    claims.length > 0
      ? claims.map((gap) => ({
          id: gap.claim_id,
          said: gap.claim,
          support: CLAIM_PLAIN[gap.claim_id] || pageOne.listing_outruns_evidence.find(
            (line) => line.toLowerCase().includes(gap.claim.split(" ")[0].toLowerCase()),
          ) || gap.supported_portion || "",
        }))
      : pageOne.listing_outruns_evidence.map((line, index) => ({
          id: `line-${index}`,
          said: line.split(" goes past ")[0]?.replace(/[“”]/g, "") || line,
          support: line,
        }));

  const explanation = run.buyer_explanation;

  return (
    <>
      {explanation?.sections ? (
        <section className="advisor-decision" aria-label="Buyer explanation">
          <p className="advisor-kicker">Buyer explanation</p>
          <h2>{explanation.sections.recommendation}</h2>
          <p className="advisor-decision-lead">{explanation.sections.why}</p>
          <p>{explanation.sections.listing_jumps}</p>
          <p>{explanation.sections.if_changes}</p>
          <p className="advisor-quiet">{explanation.sections.professional_reminders}</p>
          <p className="advisor-quiet">
            Source {explanation.source}
            {explanation.provenance?.provider_status
              ? ` · ${explanation.provenance.provider_status}`
              : ""}
          </p>
        </section>
      ) : null}
      <section className="advisor-decision" aria-label="Decision">
        <p className="advisor-kicker">Decision</p>
        <h2>{VISIT_HEADLINE[visitPurpose]}</h2>
        <p className="advisor-decision-lead">
          Get the access paper first. Water is the larger evidence gap, but the
          paper is cheaper than a trip.
        </p>
        <dl className="advisor-decision-facts">
          <div>
            <dt>Largest gap</dt>
            <dd>{water?.title || "Livestock-water use still lacks operating evidence"}</dd>
          </div>
          <div>
            <dt>First action</dt>
            <dd>{first?.why_now || "Request access documents before travel."}</dd>
          </div>
        </dl>
      </section>

      <section className="advisor-reason" aria-label="Reason">
        <h2>What RangeMatch noticed</h2>
        <div className="advisor-claim-grid">
          {claimRows.map((row) => (
            <article key={row.id} className="advisor-claim">
              <p className="advisor-claim-said">
                <span>Listing said</span>
                {row.said}
              </p>
              <p className="advisor-claim-support">
                <span>Evidence shows</span>
                {row.support}
              </p>
            </article>
          ))}
        </div>
        <details className="advisor-tract-note">
          <summary>Full tract reading</summary>
          <p>{pageOne.how_the_tract_reads}</p>
        </details>
      </section>

      <section className="advisor-actions" aria-label="Act">
        <h2>What you can do now</h2>
        <ol className="advisor-today">
          {pageOne.do_today.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ol>
        <div className="advisor-action-grid">
          {messages.map((row) => (
            <article key={row.message_id} className="advisor-action-card">
              <header>
                <div>
                  <h3>{AUDIENCE_LABEL[row.audience] || row.audience}</h3>
                  <p className="advisor-quiet">{AUDIENCE_JOB[row.audience]}</p>
                </div>
                <AdvisorCopyButton
                  label={`Copy for ${AUDIENCE_LABEL[row.audience] || row.audience}`}
                  text={row.body}
                />
              </header>
              <p>{row.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="advisor-follow" aria-label="Visit and next">
        <article className={`advisor-visit advisor-visit-${visitPurpose}`}>
          <h2>Visit purpose</h2>
          <p className="advisor-visit-state">{VISIT_STATUS[visitPurpose]}</p>
          <p>{pageOne.visit_guidance}</p>
        </article>
        <article>
          <h2>What changes next</h2>
          <p>{pageOne.what_changes_next}</p>
          <p className="advisor-quiet">{pageOne.what_not_to_recheck[0]}</p>
        </article>
      </section>

      <details className="advisor-kitchen">
        <summary>
          Evidence kitchen · {drawable.length} can be reviewed on the map ·{" "}
          {inventoryOnly.length} catalog-only
        </summary>
        <div className="advisor-kitchen-body">
          <section>
            <h3>Parcel</h3>
            <p>{packet.parcel.display_label}</p>
            <p className="advisor-quiet">
              Confirmed engineering test geometry. Not a purchasable listing.
            </p>
            {run.parcel_geometry ? (
              <AdvisorDemoMap parcel={run.parcel_geometry} layers={kitchen.map_layers} />
            ) : null}
          </section>
          <section>
            <h3>Review on the map ({drawable.length})</h3>
            <ul>
              {drawable.map((row) => (
                <li key={row.candidate_id}>
                  {objectLabel(row)} · review as an area, not a pin
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h3>Catalog only ({inventoryOnly.length})</h3>
            <p className="advisor-quiet">
              These identities exist in the source catalog, but they cannot be
              drawn or used as navigation points.
            </p>
            <ul>
              {inventoryOnly.map((row) => (
                <li key={row.candidate_id}>{objectLabel(row)} · catalog only</li>
              ))}
            </ul>
          </section>
          <section>
            <h3>What the public data already measured</h3>
            <ul>
              {kitchen.observations.map((row) => (
                <li key={String(row.observation_id)}>
                  {String(row.label)}
                  {row.display_value || row.value != null
                    ? ` · ${String(row.display_value || row.value)}`
                    : ""}
                  {row.unit ? ` ${String(row.unit)}` : ""}
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h3>Limits</h3>
            <ul>
              {kitchen.coverage_and_limitations
                .filter((row) => Array.isArray(row.limitations) && (row.limitations as string[]).length)
                .slice(0, 6)
                .map((row, index) => (
                  <li key={`${row.land_fact_ref}-${index}`}>
                    {(row.limitations as string[])[0]}
                  </li>
                ))}
            </ul>
          </section>
          <section>
            <h3>Engine appendix</h3>
            <p className="advisor-quiet">
              Engine decision labels stay confined to this appendix. They are not
              a buy/no-buy verdict and do not appear on the buyer pages.
            </p>
          </section>
        </div>
      </details>
    </>
  );
}
