import { useEffect, useRef, useState, type ReactNode } from "react";
import type { FeatureCollection } from "geojson";
import { AdvisorCopyButton } from "../components/advisor/AdvisorCopyButton";
import { AdvisorDemoMap } from "../components/advisor/AdvisorDemoMap";
import {
  NAMBE_DEMO_SCENARIO_ID,
  NAMBE_VERIFIED_DEMO_ADDRESS,
} from "../data/demoPlaces";
import "../styles/advisor-demo.css";

/** Bold every visible "Mireye" mention in user-facing copy. */
function withMireyeBold(text: string): ReactNode {
  const parts = String(text).split(/(Mireye)/g);
  if (parts.length === 1) return text;
  return parts.map((part, index) =>
    part === "Mireye" ? (
      <strong key={`mireye-${index}`} className="advisor-mireye-word">
        Mireye
      </strong>
    ) : (
      part
    ),
  );
}

type VisitPurpose =
  | "VISIT_PURPOSE_DEFINED"
  | "VISIT_DEPENDS_ON_DOCUMENT"
  | "NO_DEFINED_VISIT_PURPOSE_YET";

type InvestigationOutcome =
  | "PARCEL_NEEDS_CONFIRMATION"
  | "EVIDENCE_INVESTIGATION_COMPLETED"
  | "EVIDENCE_INVESTIGATION_INCOMPLETE"
  | "PARCEL_NOT_FOUND"
  | "PARCEL_SERVICE_UNAVAILABLE"
  | "INVESTIGATION_COULD_NOT_COMPLETE";

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
  status: "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED" | "SKIPPED" | string;
};

type AgendaStep = {
  step_id: string;
  label: string;
  tool_id?: string | null;
  status: "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED" | "SKIPPED" | string;
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
    limitations?: string[];
  };
  requested_point?: { lat?: number; lng?: number };
  contexts?: Record<string, { status?: string; error_class?: string | null }>;
};

type LimitedInvestigation = {
  address?: string;
  normalized_address?: string | null;
  location_resolved?: boolean;
  parcel_geometry_confirmed?: boolean;
  mireye_disposition?: string | null;
  accuracy_type?: string | null;
  confidence?: number | null;
  geocode_point?: { lat: number; lng: number } | null;
  candidate_count?: number;
  parcel_unavailable?: boolean | null;
  parcel_unavailable_reason?: string | null;
  cper_policy_blocked?: boolean;
  full_buyer_report?: boolean;
  message?: string;
  next_step?: string;
};

type ParcelCandidateRow = {
  candidate_id?: string | null;
  label?: string | null;
  parcel_id?: string | null;
  has_geometry?: boolean;
  geometry_hash?: string | null;
};

type AgentRun = {
  status: "QUEUED" | "SUCCEEDED" | "FAILED" | "RUNNING";
  collecting_factor?: string | null;
  run_id: string;
  generated_at: string;
  address?: string | null;
  fixture_id?: string | null;
  run_mode?: "CUSTOM" | "VERIFIED_DEMO" | string | null;
  demo_scenario_id?: string | null;
  packet_hash: string | null;
  llm_used: boolean;
  failed_step: string | null;
  error: string | null;
  investigation_outcome?: InvestigationOutcome | null;
  location_resolved?: boolean;
  parcel_geometry_confirmed?: boolean;
  parcel_resolution_id?: string | null;
  geometry_hash?: string | null;
  limited_investigation?: LimitedInvestigation | null;
  parcel_candidates?: ParcelCandidateRow[];
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
    ranch_narrative?: {
      operating_thesis?: string;
      ranch_reading?: string;
      how_livestock_would_use_it?: string;
      client_summary?: string;
      attention_pivot?: {
        largest_operating_theme?: string;
        why_theme_and_action_differ?: string;
      };
      conditional_path?: {
        if_access_holds?: string;
        if_access_fails?: string;
      };
    };
    provenance?: {
      provider_status?: string;
      provider?: string;
      error_code?: string;
      retry_count?: number;
    };
  } | null;
  operating_profile_hash?: string | null;
  deal_context?: {
    context_version?: number;
    operation_type?: string;
    geometry_hash?: string;
  } | null;
  collection_mode?: "LEGACY" | "MIREYE_FIRST" | string | null;
  natural_cattle_profile?: {
    profile_hash?: string;
    overall_natural_foundation?: {
      status?: string;
      controlling_factor?: {
        domain?: string | null;
        reason?: string;
        resolved?: boolean;
      };
    };
  } | null;
  natural_foundation_interpretation?: {
    land_character?: string;
    advisor_judgment?: string;
    operating_possibilities?: string[];
    conditional_scenarios?: string[];
    interpretation_id?: string;
    status?: string;
    advisor_view?: string;
    integrated_natural_reading?: string;
    intended_use_interpretation?: string;
    what_would_change_the_view?: string[];
    refinement_request?: string;
    optional_copy_ready_request?: string | null;
    cited_profile_refs?: string[];
    knowledge_refs?: string[];
    source?: string;
    validation_status?: string;
    natural_cattle_profile_hash?: string;
    deal_context_version?: number;
    controlling_factor?: {
      domain?: string | null;
      reason?: string;
      resolved?: boolean;
    };
    next_question?: {
      question_id?: string;
      prompt?: string;
      allowed_field?: string;
      what_would_change_view_ref?: string;
    };
  } | null;
  operating_conclusion?: {
    conclusion_id?: string;
    status?: string;
    headline?: string;
    summary?: string;
    primary_constraint?: string;
    confidence?: string;
    next_action?: string;
    next_spend_class?: string;
    what_would_change_view?: string[];
    evidence_refs?: string[];
    knowledge_refs?: string[];
    deal_context_version?: number;
    source?: string;
    validation_status?: string;
    next_question?: {
      question_id?: string;
      prompt?: string;
      allowed_field?: string;
      what_would_change_view_ref?: string;
    };
  } | null;
  initial_operating_conclusion?: AgentRun["operating_conclusion"];
  revised_operating_conclusion?: AgentRun["operating_conclusion"];
  conclusion_change?: {
    change_status?: string;
    summary?: string;
    fields_changed?: Array<{ field: string; before?: unknown; after?: unknown }>;
    user_answer?: {
      question_id?: string;
      field?: string;
      value?: unknown;
      provenance?: string;
    };
    before_deal_context_version?: number;
    after_deal_context_version?: number;
  } | null;
  chat_turns?: Array<{
    turn_id?: string;
    intent?: string;
    user_message?: string;
    judgment?: string;
    answer?: string;
    suggested_follow_up?: string;
    source?: string;
  }>;
  chat_suggestions?: Array<{ intent?: string; prompt?: string }>;
  place_normalization?: {
    raw_input?: string | null;
    lookup_input?: string | null;
    input_type?: string | null;
    llm_used?: boolean;
    status?: string | null;
    note?: string | null;
  } | null;
  packet: {
    parcel: {
      display_label?: string | null;
      parcel_id?: string;
      is_engineering_test_geometry?: boolean;
      confirmation_status?: string;
    };
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
    page_two_actions: {
      page_mode?: "LISTING_CLAIMS" | "PUBLIC_EVIDENCE";
      headline?: string;
      messages: Message[];
    };
    page_three_kitchen: {
      observations: Array<Record<string, unknown>>;
      source_notes: Array<Record<string, unknown>>;
      mireye_provenance?: Array<Record<string, unknown>>;
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
  { step_id: "DERIVE_F06", label: "Derive geometry", status: "PENDING" },
  { step_id: "FETCH_MIREYE_ENVIRONMENT", label: "Fetch Mireye", status: "PENDING" },
  { step_id: "BUILD_MIREYE_ENVIRONMENTAL_PROFILE", label: "Build Mireye profile", status: "PENDING" },
  { step_id: "DETECT_ENVIRONMENTAL_GAPS", label: "Detect gaps", status: "PENDING" },
  { step_id: "RUN_ENVIRONMENTAL_SUPPLEMENTS", label: "Run supplements", status: "PENDING" },
  { step_id: "MERGE_ENVIRONMENTAL_EVIDENCE", label: "Merge evidence", status: "PENDING" },
  { step_id: "PROJECT_NATURAL_CATTLE_PROFILE", label: "Cattle profile", status: "PENDING" },
  { step_id: "CREATE_DEAL_CONTEXT", label: "Deal context", status: "PENDING" },
  {
    step_id: "GENERATE_NATURAL_FOUNDATION_INTERPRETATION",
    label: "Advisor reasoning",
    status: "PENDING",
  },
];

const ADVISOR_MODES: Array<{
  id: string;
  label: string;
  detail: string;
  available: boolean;
}> = [
  {
    id: "cattle",
    label: "Cattle",
    detail: "Beef & cow-calf — available now",
    available: true,
  },
  {
    id: "sheep",
    label: "Sheep",
    detail: "Future mode",
    available: false,
  },
  {
    id: "goats",
    label: "Goats",
    detail: "Future mode",
    available: false,
  },
  {
    id: "hogs",
    label: "Hogs & pigs",
    detail: "Future mode",
    available: false,
  },
  {
    id: "poultry",
    label: "Poultry",
    detail: "Chicken & turkey — future mode",
    available: false,
  },
  {
    id: "horses",
    label: "Horses",
    detail: "Future mode",
    available: false,
  },
  {
    id: "fish",
    label: "Fish & aquaculture",
    detail: "Future mode",
    available: false,
  },
  {
    id: "bison",
    label: "Bison",
    detail: "Future mode",
    available: false,
  },
];

const ASSESSMENT_STAGES: Array<{
  id: string;
  title: string;
  detail: string;
  icon: string;
  stepIds: string[];
}> = [
  {
    id: "confirm_property",
    title: "Confirming the Property",
    detail: "Locating and confirming the parcel boundary",
    icon: "/assets/sprites/agent-parcel.png",
    stepIds: ["ACCEPT_PLACE", "RESOLVE_PARCEL", "DERIVE_F06"],
  },
  {
    id: "read_land",
    title: "Reading the Land",
    detail: "Collecting terrain, vegetation, water, climate, and soil evidence",
    icon: "/assets/sprites/agent-mireye.svg",
    stepIds: [
      "CALL_MIREYE",
      "FETCH_MIREYE_ENVIRONMENT",
      "BUILD_MIREYE_ENVIRONMENTAL_PROFILE",
    ],
  },
  {
    id: "fill_gaps",
    title: "Filling Evidence Gaps",
    detail: "Retrieving additional parcel-specific environmental data",
    icon: "/assets/sprites/agent-gap.svg",
    stepIds: [
      "DETECT_ENVIRONMENTAL_GAPS",
      "BUILD_AGENDA",
      "RUN_ENVIRONMENTAL_SUPPLEMENTS",
      "RUN_AGENDA",
      "COLLECT_ADDITIONAL_PROPERTY_CONTEXT",
    ],
  },
  {
    id: "cattle_profile",
    title: "Building the Cattle Profile",
    detail: "Connecting the land’s natural conditions to cattle use",
    icon: "/assets/sprites/agent-cattle.png",
    stepIds: [
      "MERGE_ENVIRONMENTAL_EVIDENCE",
      "COMPARE_CLAIMS",
      "PROJECT_NATURAL_CATTLE_PROFILE",
    ],
  },
  {
    id: "understand_plan",
    title: "Understanding Your Plan",
    detail: "Applying the buyer’s intended operation and priorities",
    icon: "/assets/sprites/agent-buyer.png",
    stepIds: ["CREATE_DEAL_CONTEXT"],
  },
  {
    id: "advisor_view",
    title: "Preparing the Advisor View",
    detail: "Producing the conclusion, refinement question, and report",
    icon: "/assets/sprites/agent-reasoning.svg",
    stepIds: [
      "GENERATE_NATURAL_FOUNDATION_INTERPRETATION",
      "ORDER_ACTIONS",
      "VALIDATE_BRIEF",
    ],
  },
];

type AgentProgressRow = AgentStep & {
  icon: string;
  shortLabel: string;
  detail: string;
  statusLabel: string;
  stageIndex: number;
};

function stageStatusLabel(
  status: string,
  options: { limited: boolean; showWaiting: boolean },
): string {
  if (status === "SUCCEEDED") {
    return options.limited ? "Completed with limited evidence" : "Completed";
  }
  if (status === "RUNNING") return "In progress";
  if (status === "FAILED" || status === "TIMED_OUT") return "Failed";
  if (status === "NEEDS_CONFIRMATION") return "Waiting";
  if (status === "SKIPPED") return "Completed with limited evidence";
  if (status === "PENDING" && options.showWaiting) return "Waiting";
  return "";
}

function agentProgress(steps: AgentStep[]): AgentProgressRow[] {
  const rank: Record<string, number> = {
    FAILED: 6,
    TIMED_OUT: 5,
    NEEDS_CONFIRMATION: 4,
    RUNNING: 3,
    PENDING: 2,
    SUCCEEDED: 1,
    SKIPPED: 0,
  };

  const rows = ASSESSMENT_STAGES.map((stage, stageIndex) => {
    const members = steps.filter((step) => stage.stepIds.includes(step.step_id));
    let status = "PENDING";
    let limited = false;
    if (members.length > 0) {
      const allDone = members.every(
        (step) => step.status === "SUCCEEDED" || step.status === "SKIPPED",
      );
      if (allDone) {
        const anySucceeded = members.some((step) => step.status === "SUCCEEDED");
        const anySkipped = members.some((step) => step.status === "SKIPPED");
        status = anySucceeded ? "SUCCEEDED" : "SKIPPED";
        limited = anySucceeded && anySkipped;
      } else {
        status = members.reduce(
          (selected, step) =>
            (rank[step.status] ?? 2) > (rank[selected] ?? 2) ? step.status : selected,
          "PENDING",
        );
      }
    } else {
      // Presentation only: unused optional work skips when a later stage has started.
      const laterStarted = ASSESSMENT_STAGES.slice(stageIndex + 1).some((later) =>
        steps.some(
          (step) =>
            later.stepIds.includes(step.step_id) &&
            step.status !== "PENDING" &&
            step.status !== "SKIPPED",
        ),
      );
      if (laterStarted) {
        status = "SKIPPED";
        limited = true;
      }
    }
    return {
      step_id: stage.id,
      label: stage.title,
      shortLabel: stage.title,
      detail: stage.detail,
      icon: stage.icon,
      status,
      stageIndex,
      limited,
    };
  });

  const firstWaitingIndex = rows.findIndex(
    (row) =>
      row.status === "PENDING" ||
      row.status === "NEEDS_CONFIRMATION" ||
      row.status === "RUNNING",
  );

  return rows.map((row) => {
    const showWaiting =
      row.status === "NEEDS_CONFIRMATION" ||
      (row.status === "PENDING" && row.stageIndex === firstWaitingIndex);
    return {
      step_id: row.step_id,
      label: row.label,
      shortLabel: row.shortLabel,
      detail: row.detail,
      icon: row.icon,
      status: row.status,
      stageIndex: row.stageIndex,
      statusLabel: stageStatusLabel(row.status, {
        limited: row.limited,
        showWaiting,
      }),
    };
  });
}

function agentProgressPercent(rows: AgentProgressRow[]): number {
  if (rows.length === 0) return 0;
  const done = rows.filter(
    (row) => row.status === "SUCCEEDED" || row.status === "SKIPPED",
  ).length;
  const running = rows.some((row) => row.status === "RUNNING") ? 0.45 : 0;
  return Math.min(100, Math.round(((done + running) / rows.length) * 100));
}

const AUDIENCE_LABEL: Record<string, string> = {
  LISTING_BROKER: "Listing broker",
  TITLE_OR_COUNSEL: "Title / counsel",
  FIELD_VISITOR: "Field visitor",
  PARTNER: "Partner",
};

const VISIT_HEADLINE: Record<VisitPurpose, string> = {
  VISIT_PURPOSE_DEFINED: "The visit has a defined job",
  VISIT_DEPENDS_ON_DOCUMENT: "Do not send the client yet",
  NO_DEFINED_VISIT_PURPOSE_YET: "Do not visit yet",
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

function resolveInvestigationOutcome(run: AgentRun | null): InvestigationOutcome | null {
  if (!run || run.status === "QUEUED" || run.status === "RUNNING") return null;
  if (run.investigation_outcome) return run.investigation_outcome;
  if (run.status === "SUCCEEDED" && run.brief && run.packet) {
    return "EVIDENCE_INVESTIGATION_COMPLETED";
  }
  if (run.status === "SUCCEEDED" && run.limited_investigation) {
    return "EVIDENCE_INVESTIGATION_INCOMPLETE";
  }
  if (run.status === "FAILED") return "INVESTIGATION_COULD_NOT_COMPLETE";
  return null;
}

function focusPlaceInput() {
  const input = document.getElementById("advisor-place-input");
  if (input instanceof HTMLInputElement) {
    input.focus();
    input.select();
    input.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

function humanOutcomeCopy(run: AgentRun, outcome: InvestigationOutcome) {
  const lookup = run.mireye_live?.lookup;
  const errorClass = lookup?.error_class || "";
  const failedStep = run.failed_step || "";

  if (outcome === "PARCEL_NEEDS_CONFIRMATION") {
    return {
      title: "Confirm the parcel to analyze",
      reached: "Mireye returned one or more parcel outlines for this place.",
      why: "A recognized location is not yet a confirmed parcel. Confirm the boundary RangeMatch should investigate.",
      next: "Select the outline you want, then confirm it.",
      report: "No cattle operating Snapshot yet — confirmation comes first.",
      cta: "Confirm parcel",
    };
  }
  if (outcome === "EVIDENCE_INVESTIGATION_COMPLETED") {
    return {
      title: "Cattle operating view ready",
      reached: "The confirmed parcel investigation finished.",
      why: "Physical evidence, Deal Context, and an Operating Conclusion are ready for this run.",
      next: "Read the natural cattle foundation, answer the Agent question, then download the two-page report.",
      report: "A two-page Natural Cattle Foundation report is available.",
      cta: "Read natural foundation view",
    };
  }
  if (outcome === "EVIDENCE_INVESTIGATION_INCOMPLETE") {
    return {
      title: "Location recognized — limited investigation only",
      reached: "RangeMatch identified a location, but not a full parcel investigation.",
      why:
        run.limited_investigation?.message ||
        "The parcel boundary is not confirmed for a full cattle operating reading.",
      next:
        run.limited_investigation?.next_step ||
        "Review the resolved location or try another place.",
      report: "No cattle operating Snapshot was generated.",
      cta: "Review resolved location",
    };
  }
  if (outcome === "PARCEL_NOT_FOUND") {
    return {
      title: "We could not confirm a parcel",
      reached: "The parcel lookup finished without a confirmable boundary.",
      why: "This is not a network failure — no parcel-quality polygon was returned for this place.",
      next: "Try a full street address or coordinates, or run the verified Nambe demo as a separate investigation.",
      report: "No property-level Snapshot was generated. Another property was not substituted.",
      cta: "Edit location",
    };
  }
  if (outcome === "PARCEL_SERVICE_UNAVAILABLE") {
    return {
      title: "The parcel service could not complete this lookup",
      reached: "RangeMatch could not reach a trustworthy parcel result from the external service.",
      why: "Network, TLS, authentication, timeout, or provider failure blocked the lookup. This is not the same as “no parcel matched.”",
      next: "Retry on a clean network, edit the location, or explicitly run the verified Nambe demo.",
      report: "No property-level Snapshot was generated. RangeMatch did not substitute another property.",
      cta: "Retry",
    };
  }

  let why = "A required investigation step could not finish.";
  if (errorClass.includes("TIMEOUT") || /timeout/i.test(run.error || "")) {
    why = "A later investigation stage timed out after parcel entry.";
  } else if (failedStep) {
    why = `The investigation stopped at ${failedStep.replaceAll("_", " ").toLowerCase()}.`;
  }

  return {
    title: "Investigation could not complete",
    reached: failedStep
      ? `The run stopped at ${failedStep.replaceAll("_", " ")}.`
      : "The run stopped before a parcel investigation could finish.",
    why,
    next: "Edit the place input and try again, or use the verified Nambe demo.",
    report: "No cattle operating Snapshot was generated.",
    cta: "Edit input and retry",
  };
}

export function AdvisorDemoPage() {
  const [address, setAddress] = useState("");
  const [run, setRun] = useState<AgentRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [clientError, setClientError] = useState<string | null>(null);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string>("");
  const [confirmDismissed, setConfirmDismissed] = useState(false);
  const [resultsDismissed, setResultsDismissed] = useState(false);
  const [reportChatOpen, setReportChatOpen] = useState(false);
  const [modeMenuOpen, setModeMenuOpen] = useState(false);
  const [activeModeId, setActiveModeId] = useState("cattle");
  const modeMenuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!modeMenuOpen) return;
    function onPointerDown(event: MouseEvent) {
      if (!modeMenuRef.current?.contains(event.target as Node)) {
        setModeMenuOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setModeMenuOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [modeMenuOpen]);

  useEffect(() => {
    setConfirmDismissed(false);
  }, [run?.run_id, run?.investigation_outcome]);

  useEffect(() => {
    const rows = run?.parcel_candidates || [];
    const confirmable = rows.filter(
      (row) => row.candidate_id && row.geometry_hash && row.has_geometry !== false,
    );
    if (confirmable.length === 1 && confirmable[0].candidate_id) {
      setSelectedCandidateId(confirmable[0].candidate_id);
      return;
    }
    setSelectedCandidateId((current) =>
      rows.some((row) => row.candidate_id === current) ? current : "",
    );
  }, [run?.run_id]);

  async function pollRun(started: AgentRun): Promise<AgentRun | null> {
    let body = started;
    const began = Date.now();
    setRun(body);
    while (
      body.status === "QUEUED" ||
      body.status === "RUNNING" ||
      (body.investigation_outcome === "EVIDENCE_INVESTIGATION_COMPLETED" &&
        !body.operating_conclusion &&
        !body.natural_foundation_interpretation)
    ) {
      const elapsed = Date.now() - began;
      if (elapsed > 125_000) {
        setClientError(
          "The evidence run finished, but the advisor conclusion is still being prepared. Retry shortly.",
        );
        return body;
      }
      const interval = elapsed > 90_000 ? 2000 : 180;
      await new Promise((resolve) => window.setTimeout(resolve, interval));
      const poll = await fetch(`/v1/advisor/runs/${body.run_id}`, {
        headers: { Accept: "application/json" },
      });
      body = await readRun(poll);
      setRun(body);
      if (!poll.ok) {
        setClientError("The Agent run could not be read. Try again.");
        return null;
      }
    }
    return body;
  }

  async function startAdvisorRun(payload: {
    address?: string;
    parcel_resolution_id?: string;
    run_mode?: "CUSTOM" | "VERIFIED_DEMO";
    demo_scenario_id?: string;
    collection_mode?: "LEGACY" | "MIREYE_FIRST";
  }): Promise<void> {
    const response = await fetch("/v1/advisor/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await readRun(response);
    if (!response.ok) {
      setClientError(
        typeof body.detail === "string"
          ? body.detail
          : `Run failed (${response.status}). Start the API on port 8001.`,
      );
      return;
    }
    await pollRun(body);
  }

  async function runAgent() {
    const place = address.trim();
    if (!place) {
      setClientError("Enter a U.S. address or coordinates first.");
      return;
    }
    setBusy(true);
    setClientError(null);
    setRun(null);
    setConfirmDismissed(false);
    setResultsDismissed(false);
    setReportChatOpen(false);
    try {
      await startAdvisorRun({
        address: place,
        run_mode: "CUSTOM",
        collection_mode: "MIREYE_FIRST",
      });
    } catch {
      setClientError(
        "The Agent API did not respond. Start `uvicorn rangematch.api:app --port 8001`, then run again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function runVerifiedNambeDemo() {
    setBusy(true);
    setClientError(null);
    setRun(null);
    setConfirmDismissed(false);
    setResultsDismissed(false);
    setReportChatOpen(false);
    setAddress(NAMBE_VERIFIED_DEMO_ADDRESS);
    try {
      // Explicit Nambe opt-in still uses the live custom Mireye-first path;
      // it never substitutes a fixture or inherits the previous run.
      await startAdvisorRun({
        address: NAMBE_VERIFIED_DEMO_ADDRESS,
        run_mode: "CUSTOM",
        collection_mode: "MIREYE_FIRST",
      });
    } catch {
      setClientError(
        "The Agent API did not respond. Start `uvicorn rangematch.api:app --port 8001`, then run again.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function confirmSelectedParcel() {
    const resolutionId = run?.parcel_resolution_id;
    const selected = (run?.parcel_candidates || []).find(
      (row) => row.candidate_id === selectedCandidateId,
    );
    if (!resolutionId || !selected?.candidate_id || !selected.geometry_hash) {
      setClientError(
        "This candidate cannot be confirmed yet — candidate id or geometry hash is missing.",
      );
      return;
    }
    setBusy(true);
    setClientError(null);
    setResultsDismissed(false);
    setReportChatOpen(false);
    try {
      const confirmResponse = await fetch(
        `/v1/parcel-resolutions/${encodeURIComponent(resolutionId)}/confirm`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({
            selected_candidate_id: selected.candidate_id,
            expected_geometry_hash: selected.geometry_hash,
            explicit_confirmation: true,
          }),
        },
      );
      const confirmBody = (await confirmResponse.json()) as {
        detail?: string | { code?: string };
        status?: string;
      };
      if (!confirmResponse.ok) {
        const detail =
          typeof confirmBody.detail === "string"
            ? confirmBody.detail
            : confirmBody.detail?.code || `Confirm failed (${confirmResponse.status}).`;
        setClientError(detail);
        return;
      }
      await startAdvisorRun({
        address: (address.trim() || run?.address || "").trim() || undefined,
        parcel_resolution_id: resolutionId,
        run_mode:
          run?.run_mode === "VERIFIED_DEMO" ? "VERIFIED_DEMO" : "CUSTOM",
        demo_scenario_id:
          run?.run_mode === "VERIFIED_DEMO"
            ? run.demo_scenario_id || NAMBE_DEMO_SCENARIO_ID
            : undefined,
        collection_mode:
          run?.collection_mode === "MIREYE_FIRST" ? "MIREYE_FIRST" : "LEGACY",
      });
    } catch {
      setClientError(
        "Parcel confirm did not reach the API. Start uvicorn on port 8001, then try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  const steps = run?.steps?.length
    ? run.steps
    : busy
      ? IDLE_STEPS.map((row, index) =>
          index === 0 ? { ...row, status: "RUNNING" as const } : row,
        )
      : IDLE_STEPS;
  const progressRows = agentProgress(steps);
  const progressPercent = agentProgressPercent(progressRows);
  const activeAgent =
    progressRows.find((row) => row.status === "RUNNING") ||
    [...progressRows].reverse().find((row) => row.status === "SUCCEEDED") ||
    progressRows[0];
  const recentActivity = progressRows
    .filter((row) => row.status === "SUCCEEDED" || row.status === "RUNNING")
    .slice(0, 5);
  const outcome = resolveInvestigationOutcome(run);
  const completed =
    outcome === "EVIDENCE_INVESTIGATION_COMPLETED" &&
    Boolean(run?.operating_conclusion || run?.natural_foundation_interpretation);
  const terminal = Boolean(outcome) || Boolean(clientError);
  const showProgress = busy || (Boolean(run) && !completed && !terminal);
  const snapshotLocation =
    run?.address ||
    run?.limited_investigation?.normalized_address ||
    (address.trim() ? address.trim() : "Enter a property to begin");
  const runCta = busy ? "Running analysis…" : terminal ? "Run again" : "Run analysis";

  const showConfirmModal =
    Boolean(run) &&
    outcome === "PARCEL_NEEDS_CONFIRMATION" &&
    !completed &&
    !confirmDismissed;

  const hasResultsContent =
    Boolean(run) &&
    (completed ||
      (Boolean(outcome) && outcome !== "PARCEL_NEEDS_CONFIRMATION"));

  const showResultsModal = hasResultsContent && !resultsDismissed;

  useEffect(() => {
    if (!showConfirmModal && !showResultsModal) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [showConfirmModal, showResultsModal]);

  function openResultsModal() {
    if (!hasResultsContent) return;
    setResultsDismissed(false);
  }

  function handleOutcomeAction(next: InvestigationOutcome) {
    if (next === "PARCEL_NEEDS_CONFIRMATION") {
      void confirmSelectedParcel();
      return;
    }
    if (
      next === "PARCEL_NOT_FOUND" ||
      next === "PARCEL_SERVICE_UNAVAILABLE" ||
      next === "INVESTIGATION_COULD_NOT_COMPLETE"
    ) {
      focusPlaceInput();
      return;
    }
    if (next === "EVIDENCE_INVESTIGATION_COMPLETED") {
      openResultsModal();
      return;
    }
    openResultsModal();
  }

  return (
    <div className="advisor-demo">
      <section className="advisor-landing-shell">
        <header className="advisor-site-header advisor-page-width">
          <a className="advisor-brand" href="#advisor-home" aria-label="RangeMatch home">
            <img
              className="advisor-brand-logo"
              src="/assets/rangematch-logo-brand.png"
              alt="RangeMatch — AI advisor for ranch buyers"
            />
          </a>
          <nav className="advisor-primary-navigation" aria-label="Primary navigation">
            <div
              className={`advisor-nav-mode${modeMenuOpen ? " is-open" : ""}`}
              ref={modeMenuRef}
            >
              <button
                type="button"
                className="advisor-nav-trigger"
                aria-expanded={modeMenuOpen}
                aria-haspopup="listbox"
                aria-controls="advisor-mode-menu"
                onClick={() => setModeMenuOpen((open) => !open)}
              >
                <img src="/assets/sprites/nav-hq-properties.png" alt="" aria-hidden="true" />
                Mode
                <span className="advisor-nav-caret" aria-hidden="true">
                  ▾
                </span>
              </button>
              {modeMenuOpen ? (
                <div
                  className="advisor-mode-menu"
                  id="advisor-mode-menu"
                  role="listbox"
                  aria-label="Operating modes"
                >
                  <p className="advisor-mode-menu-note">
                    Cattle is live today. Other U.S. livestock modes are planned next.
                  </p>
                  {ADVISOR_MODES.map((mode) => {
                    const selected = activeModeId === mode.id;
                    return (
                      <button
                        key={mode.id}
                        type="button"
                        role="option"
                        aria-selected={selected}
                        className={`advisor-mode-option${selected ? " is-selected" : ""}${
                          mode.available ? "" : " is-future"
                        }`}
                        onClick={() => {
                          if (mode.available) {
                            setActiveModeId(mode.id);
                            setModeMenuOpen(false);
                          }
                        }}
                        disabled={!mode.available}
                      >
                        <span className="advisor-mode-option-label">{mode.label}</span>
                        <span className="advisor-mode-option-detail">{mode.detail}</span>
                      </button>
                    );
                  })}
                </div>
              ) : null}
            </div>
            <a
              href="#advisor-results"
              onClick={(event) => {
                if (!hasResultsContent) return;
                event.preventDefault();
                openResultsModal();
              }}
            >
              <img src="/assets/sprites/nav-hq-reports.png" alt="" aria-hidden="true" />
              Reports
            </a>
            <a href="#advisor-agentic-system">
              <img src="/assets/sprites/nav-hq-saved.png" alt="" aria-hidden="true" />
              Agentic System
            </a>
          </nav>
          <div className="advisor-header-utils">
            <button type="button" className="advisor-util-btn" aria-label="Help">
              <img src="/assets/sprites/nav-hq-help.png" alt="" />
            </button>
            <button type="button" className="advisor-util-btn advisor-util-bell" aria-label="Notifications">
              <img src="/assets/sprites/nav-hq-bell.png" alt="" />
              <span className="advisor-util-badge">3</span>
            </button>
            <div className="advisor-profile-pill" aria-label="Demo profile">
              <img src="/assets/sprites/nav-hq-profile.png" alt="" aria-hidden="true" />
              <span>JD Ranch Co.</span>
              <span className="advisor-profile-caret" aria-hidden="true">▾</span>
            </div>
          </div>
        </header>

        <section className="advisor-hero advisor-page-width" id="advisor-home">
          <div className="advisor-hero-copy">
            <h1>Let’s understand this ranch.</h1>
            <p className="advisor-hero-description">
              Enter a U.S. address and our agent team will analyze the property to
              give you a grounded cattle-operating assessment.
            </p>
            <div className="advisor-address-row">
              <label className="advisor-address-field" htmlFor="advisor-place-input">
                <span className="advisor-pin" aria-hidden="true">
                  <img src="/assets/sprites/icon-map.png" alt="" />
                </span>
                <input
                  id="advisor-place-input"
                  className="advisor-address"
                  value={address}
                  onChange={(event) => setAddress(event.target.value)}
                  placeholder="Enter a U.S. address or coordinates"
                  aria-label="Enter a U.S. address or coordinates"
                  disabled={busy}
                />
              </label>
              <button
                type="button"
                className="advisor-run-button"
                onClick={() => void runAgent()}
                disabled={busy || !address.trim()}
              >
                {runCta}
                <span aria-hidden="true">→</span>
              </button>
            </div>
            <p className="advisor-quiet advisor-demo-link">
              <img
                className="advisor-shield"
                src="/assets/sprites/icon-leaf-circle.png"
                alt=""
                aria-hidden="true"
              />
              <span>
                We’ll use <strong className="advisor-mireye-word">Mireye</strong> to
                identify and confirm the parcel, then run our multi-agent analysis.
                Don’t have a property ready?{" "}
                <button
                  type="button"
                  className="advisor-text-button"
                  disabled={busy}
                  onClick={() => void runVerifiedNambeDemo()}
                >
                  Try the verified Nambe example
                </button>
              </span>
            </p>
          </div>

          <div className="advisor-hero-art" aria-hidden="true">
            <img src="/assets/sprites/hero-scene.png" alt="" />
          </div>

          <aside className="advisor-deliverables" id="what-you-get">
            <h2>
              <img src="/assets/sprites/get-star.svg" alt="" aria-hidden="true" />
              What you’ll get
            </h2>
            <ul>
              <li>
                <img src="/assets/sprites/get-overview.svg" alt="" aria-hidden="true" />
                <div>
                  <strong>Property overview</strong>
                  <small>How the ranch reads for cattle today</small>
                </div>
              </li>
              <li>
                <img src="/assets/sprites/get-constraint.svg" alt="" aria-hidden="true" />
                <div>
                  <strong>Operating constraint</strong>
                  <small>The single biggest factor to manage</small>
                </div>
              </li>
              <li>
                <img src="/assets/sprites/get-questions.svg" alt="" aria-hidden="true" />
                <div>
                  <strong>Targeted questions</strong>
                  <small>What could change the conclusion</small>
                </div>
              </li>
              <li>
                <img src="/assets/sprites/get-action.svg" alt="" aria-hidden="true" />
                <div>
                  <strong>Next diligence action</strong>
                  <small>The highest-value next step</small>
                </div>
              </li>
              <li>
                <img src="/assets/sprites/get-report.svg" alt="" aria-hidden="true" />
                <div>
                  <strong>Downloadable report</strong>
                  <small>With evidence appendix</small>
                </div>
              </li>
            </ul>
          </aside>
        </section>

        <header
          className="advisor-assessment-head advisor-page-width"
          id="advisor-agentic-system"
        >
          <h2 className="advisor-agent-team-title">Your Domain Agentic System</h2>
        </header>

        <section
          className="advisor-run advisor-run-landing advisor-page-width"
          aria-label="Run the agent"
        >
          <div className="advisor-run-main">
            <div className="advisor-run-select">
              {run?.run_mode === "VERIFIED_DEMO" ||
              (run?.collection_mode === "MIREYE_FIRST" &&
                run?.address === NAMBE_VERIFIED_DEMO_ADDRESS) ? (
                <p className="advisor-demo-banner" role="status">
                  <strong>Verified Demo Property: Nambe, Colorado</strong>
                  <br />
                  This reading uses the Nambe parcel, not your previous location input.
                </p>
              ) : null}

              <section
                className="advisor-agent-team"
                aria-label="Assessment progress"
              >
                <p className="advisor-assessment-lede">
                  RangeMatch combines{" "}
                  <strong className="advisor-mireye-word">Mireye</strong>
                  ’s parcel-specific physical-world data with rangeland environmental
                  sources, reviewed cattle-land knowledge, and the buyer’s intended
                  operation.
                </p>
                <ol className="advisor-agent-rail" aria-label="Assessment progress">
                  {progressRows.map((step) => (
                    <li
                      key={step.step_id}
                      className={`advisor-agent-node advisor-step-${step.status.toLowerCase()}`}
                    >
                      <div className="advisor-agent-icon-wrap">
                        <img src={step.icon} alt="" aria-hidden="true" />
                        {step.status === "SUCCEEDED" || step.status === "SKIPPED" ? (
                          <img
                            className="advisor-agent-badge"
                            src="/assets/sprites/status-check.png"
                            alt=""
                            aria-hidden="true"
                          />
                        ) : null}
                      </div>
                      <span className="advisor-step-label">{step.shortLabel}</span>
                      <span className="advisor-step-detail">{step.detail}</span>
                      {step.statusLabel ? (
                        <span className="advisor-step-status">{step.statusLabel}</span>
                      ) : (
                        <span className="advisor-step-status advisor-step-status-empty" aria-hidden="true">
                          &nbsp;
                        </span>
                      )}
                    </li>
                  ))}
                </ol>
              </section>

              <div className="advisor-status-grid">
                <article className="advisor-status-card advisor-status-active">
                  <h3>
                    <img
                      src={activeAgent?.icon || "/assets/sprites/agent-mireye.svg"}
                      alt=""
                      aria-hidden="true"
                    />
                    {showProgress || busy
                      ? activeAgent?.status === "RUNNING"
                        ? `In progress: ${activeAgent.label}`
                        : activeAgent?.status === "NEEDS_CONFIRMATION"
                          ? `Waiting: ${activeAgent.label}`
                          : `${activeAgent?.label || "Domain Agentic System"} ready`
                      : "Ready when you are"}
                  </h3>
                  <p>
                    {busy
                      ? activeAgent?.detail ||
                        "Collecting parcel-specific data on terrain, vegetation, precipitation, water, soils, and more."
                      : completed
                        ? "Your natural cattle foundation view is ready."
                        : "Start an analysis to follow each stage of your Domain Agentic System."}
                  </p>
                  <div className="advisor-progress-track" aria-hidden={!showProgress && !busy}>
                    <div
                      className="advisor-progress-fill"
                      style={{ width: `${showProgress || busy ? progressPercent : 0}%` }}
                    />
                    <img
                      className="advisor-progress-tuft"
                      src="/assets/sprites/icon-grass.png"
                      alt=""
                    />
                  </div>
                  <p className="advisor-progress-pct">
                    {showProgress || busy ? `${progressPercent}%` : "0%"}
                  </p>
                  {busy && run && (run.status === "QUEUED" || run.status === "RUNNING") ? (
                    <p className="advisor-quiet" data-testid="adapter-wait">
                      Building the natural cattle foundation…
                    </p>
                  ) : null}
                </article>

                <article className="advisor-status-card advisor-status-activity">
                  <h3>
                    <img src="/assets/sprites/status-clock.png" alt="" aria-hidden="true" />
                    Recent activity
                  </h3>
                  {!busy && !run && !clientError ? (
                    <p className="advisor-quiet advisor-empty-note">
                      No investigation yet. You will either confirm a parcel, see an honest
                      lookup failure, or receive a natural cattle foundation view.
                    </p>
                  ) : (
                    <ul className="advisor-activity-list">
                      {(recentActivity.length ? recentActivity : progressRows.slice(0, 3)).map(
                        (row) => (
                          <li key={row.step_id}>
                            <span className="advisor-activity-dot" aria-hidden="true" />
                            <div>
                              <strong>
                                {row.status === "RUNNING"
                                  ? `${row.label} · In progress`
                                  : row.statusLabel
                                    ? `${row.label} · ${row.statusLabel}`
                                    : row.label}
                              </strong>
                              <time>
                                {run?.generated_at
                                  ? new Date(run.generated_at).toLocaleTimeString("en-US", {
                                      hour: "numeric",
                                      minute: "2-digit",
                                    })
                                  : "—"}
                              </time>
                            </div>
                          </li>
                        ),
                      )}
                    </ul>
                  )}
                  <a
                    className="advisor-activity-link"
                    href="#advisor-results"
                    onClick={(event) => {
                      if (!hasResultsContent) return;
                      event.preventDefault();
                      openResultsModal();
                    }}
                  >
                    View all activity →
                  </a>
                </article>

                <article className="advisor-status-card advisor-status-snapshot">
                  <h3>
                    <img src="/assets/sprites/icon-fence.png" alt="" aria-hidden="true" />
                    Property snapshot
                  </h3>
                  <dl>
                    <div>
                      <dt>Location</dt>
                      <dd>{snapshotLocation}</dd>
                    </div>
                    <div>
                      <dt>Parcel</dt>
                      <dd>
                        {run?.parcel_geometry_confirmed
                          ? "Boundary confirmed"
                          : run?.location_resolved
                            ? "Location recognized"
                            : "Awaiting analysis"}
                      </dd>
                    </div>
                    <div>
                      <dt>Mode</dt>
                      <dd>
                        {run?.collection_mode === "MIREYE_FIRST"
                          ? withMireyeBold("Mireye-first")
                          : run
                            ? "Legacy / standard"
                            : "—"}
                      </dd>
                    </div>
                    <div>
                      <dt>Run</dt>
                      <dd>
                        {run?.run_id ? (
                          <code>{shortId(run.run_id)}</code>
                        ) : (
                          "Not started"
                        )}
                      </dd>
                    </div>
                  </dl>
                </article>
              </div>

              {clientError ? <p className="advisor-run-error" role="alert">{clientError}</p> : null}
            </div>
          </div>
        </section>

        <footer className="advisor-landing-footer advisor-page-width">
          <p>
            <img src="/assets/sprites/icon-leaf-circle.png" alt="" aria-hidden="true" />
            Analysis is parcel-grounded and evidence-backed. It is not a title opinion, survey,
            or substitute for on-site diligence.
          </p>
          <a href="#what-you-get">
            Learn more about our approach →
            <img src="/assets/sprites/icon-grass.png" alt="" aria-hidden="true" />
          </a>
        </footer>

        {showConfirmModal && run ? (
          <ParcelConfirmModal
            run={run}
            selectedCandidateId={selectedCandidateId}
            confirmBusy={busy}
            onSelectCandidate={setSelectedCandidateId}
            onConfirm={() => handleOutcomeAction("PARCEL_NEEDS_CONFIRMATION")}
            onDismiss={() => {
              setConfirmDismissed(true);
              focusPlaceInput();
            }}
          />
        ) : null}
      </section>

      {showResultsModal && run ? (
        <div
          className="advisor-confirm-overlay advisor-report-overlay"
          role="presentation"
          onClick={(event) => {
            if (event.target === event.currentTarget) setResultsDismissed(true);
          }}
        >
          <main
            className="advisor-report-modal"
            id="advisor-results"
            role="dialog"
            aria-modal="true"
            aria-label={completed ? "Advisor report" : "Investigation outcome"}
          >
            <div className="advisor-report-toolbar">
              {completed ? (
                <>
                  <a
                    className="advisor-report-download"
                    href={`/v1/advisor/runs/${run.run_id}/cattle-operating-snapshot.pdf`}
                  >
                    Download report
                  </a>
                  <button
                    type="button"
                    className="advisor-report-chat-start"
                    onClick={() => {
                      setReportChatOpen(true);
                      window.setTimeout(() => {
                        const node = document.getElementById("advisor-report-chat");
                        node?.scrollIntoView?.({ behavior: "smooth", block: "start" });
                      }, 40);
                    }}
                  >
                    Start to chat
                  </button>
                </>
              ) : null}
              <button
                type="button"
                className="advisor-confirm-close"
                aria-label="Close report"
                onClick={() => setResultsDismissed(true)}
              >
                <img src="/assets/sprites/confirm-close.png" alt="" />
              </button>
            </div>

            {outcome && !completed ? (
              <InvestigationOutcomePanel
                run={run}
                outcome={outcome}
                selectedCandidateId={selectedCandidateId}
                confirmBusy={busy}
                onSelectCandidate={setSelectedCandidateId}
                onAction={() => handleOutcomeAction(outcome)}
                onRetry={() => void runAgent()}
                onVerifiedDemo={() => void runVerifiedNambeDemo()}
              />
            ) : null}

            {outcome === "EVIDENCE_INVESTIGATION_INCOMPLETE" ? (
              <LimitedLocationPanel run={run} />
            ) : null}

            {completed ? (
              <AdvisorBriefResult
                run={run}
                onRunUpdate={setRun}
                chatOpen={reportChatOpen}
                onOpenChat={() => setReportChatOpen(true)}
              />
            ) : null}
          </main>
        </div>
      ) : null}
    </div>
  );
}

function ParcelConfirmModal({
  run,
  selectedCandidateId,
  confirmBusy,
  onSelectCandidate,
  onConfirm,
  onDismiss,
}: {
  run: AgentRun;
  selectedCandidateId: string;
  confirmBusy: boolean;
  onSelectCandidate: (candidateId: string) => void;
  onConfirm: () => void;
  onDismiss: () => void;
}) {
  const copy = humanOutcomeCopy(run, "PARCEL_NEEDS_CONFIRMATION");
  const locationResolved = Boolean(run.location_resolved);
  const parcelConfirmed = Boolean(run.parcel_geometry_confirmed);
  const candidates = run.parcel_candidates || [];
  const selected = candidates.find((row) => row.candidate_id === selectedCandidateId);
  const canConfirm =
    Boolean(run.parcel_resolution_id) &&
    Boolean(selected?.candidate_id) &&
    Boolean(selected?.geometry_hash);
  const lookup = run.mireye_live?.lookup;

  return (
    <div
      className="advisor-confirm-overlay"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget && !confirmBusy) onDismiss();
      }}
    >
      <section
        className="advisor-confirm-modal advisor-outcome advisor-outcome-confirm"
        role="dialog"
        aria-modal="true"
        aria-labelledby="advisor-confirm-title"
        data-testid="investigation-outcome"
        data-outcome="PARCEL_NEEDS_CONFIRMATION"
      >
        <button
          type="button"
          className="advisor-confirm-close"
          aria-label="Close"
          disabled={confirmBusy}
          onClick={onDismiss}
        >
          <img src="/assets/sprites/confirm-close.png" alt="" />
        </button>

        <img
          className="advisor-confirm-deco advisor-confirm-deco-farm"
          src="/assets/sprites/confirm-farm.png"
          alt=""
          aria-hidden="true"
        />
        <img
          className="advisor-confirm-deco advisor-confirm-deco-cow"
          src="/assets/sprites/confirm-peek-cow.png"
          alt=""
          aria-hidden="true"
        />

        <header className="advisor-confirm-head">
          <h2 id="advisor-confirm-title">
            {withMireyeBold(copy.title)}
            <img src="/assets/sprites/confirm-leaf.png" alt="" aria-hidden="true" />
          </h2>
          <p className="advisor-decision-lead">{withMireyeBold(copy.why)}</p>
        </header>

        <p className="advisor-confirm-banner" role="status">
          <img src="/assets/sprites/confirm-shield.png" alt="" aria-hidden="true" />
          <span>{withMireyeBold(copy.report)}</span>
        </p>

        <dl className="advisor-confirm-flags" aria-label="Location and parcel flags">
          <div className="advisor-confirm-flag">
            <dt>
              <img src="/assets/sprites/confirm-pin.png" alt="" aria-hidden="true" />
              Location
            </dt>
            <dd>
              {locationResolved ? "Location recognized" : "Location not resolved"}
              {!parcelConfirmed ? (
                <span className="advisor-quiet">
                  {" "}
                  · not the same as a confirmed parcel
                </span>
              ) : null}
            </dd>
          </div>
          <div className="advisor-confirm-flag">
            <dt>
              <img src="/assets/sprites/confirm-bounds-icon.png" alt="" aria-hidden="true" />
              Parcel boundary
            </dt>
            <dd>
              {parcelConfirmed
                ? "Parcel boundary confirmed for this investigation"
                : "Parcel boundary not confirmed"}
            </dd>
          </div>
        </dl>

        {candidates.length > 0 ? (
          <fieldset
            className="advisor-outcome-candidates advisor-confirm-candidates"
            disabled={confirmBusy}
          >
            <legend>Parcel candidates</legend>
            {candidates.map((row, index) => {
              const id = row.candidate_id || `cand-${index}`;
              const confirmable = Boolean(row.candidate_id && row.geometry_hash);
              const checked = selectedCandidateId === row.candidate_id;
              return (
                <label
                  key={id}
                  className={`advisor-candidate-choice${checked ? " is-selected" : ""}`}
                >
                  <input
                    type="radio"
                    name="advisor-parcel-candidate"
                    value={row.candidate_id || ""}
                    checked={checked}
                    disabled={!confirmable}
                    onChange={() => {
                      if (row.candidate_id) onSelectCandidate(row.candidate_id);
                    }}
                  />
                  <span className="advisor-candidate-copy">
                    {row.label || row.parcel_id || `Candidate ${index + 1}`}
                    {row.has_geometry ? " · has geometry" : " · no geometry yet"}
                    {row.geometry_hash ? (
                      <>
                        {" "}
                        · hash <code>{row.geometry_hash.slice(0, 8)}</code>
                      </>
                    ) : (
                      " · missing geometry hash"
                    )}
                  </span>
                  <img
                    className="advisor-candidate-thumb"
                    src="/assets/sprites/confirm-map-thumb.png"
                    alt=""
                    aria-hidden="true"
                  />
                </label>
              );
            })}
          </fieldset>
        ) : null}

        {run.parcel_resolution_id ? (
          <p className="advisor-quiet advisor-confirm-techline">
            Staged resolution <code>{run.parcel_resolution_id}</code>. Confirm
            posts{" "}
            <code>selected_candidate_id</code>,{" "}
            <code>expected_geometry_hash</code>, and{" "}
            <code>explicit_confirmation=true</code>, then re-runs Advisor with
            that <code>parcel_resolution_id</code>.
          </p>
        ) : null}

        <div className="advisor-confirm-actions">
          <button
            type="button"
            className="advisor-run-button advisor-confirm-primary"
            onClick={onConfirm}
            disabled={confirmBusy || !canConfirm}
          >
            <img src="/assets/sprites/status-check.png" alt="" aria-hidden="true" />
            {confirmBusy ? "Confirming parcel…" : copy.cta}
          </button>
          <button
            type="button"
            className="advisor-confirm-cancel"
            onClick={onDismiss}
            disabled={confirmBusy}
          >
            Cancel
          </button>
        </div>

        <details className="advisor-tech-details">
          <summary>Technical details</summary>
          <dl>
            <div>
              <dt>investigation_outcome</dt>
              <dd>
                <code>PARCEL_NEEDS_CONFIRMATION</code>
              </dd>
            </div>
            <div>
              <dt>run_mode</dt>
              <dd>
                <code>{run.run_mode || "CUSTOM"}</code>
              </dd>
            </div>
            {lookup ? (
              <>
                <div>
                  <dt>lookup.error_class</dt>
                  <dd>
                    <code>{lookup.error_class || "—"}</code>
                  </dd>
                </div>
                <div>
                  <dt>lookup.http_status</dt>
                  <dd>
                    <code>
                      {lookup.http_status == null ? "—" : String(lookup.http_status)}
                    </code>
                  </dd>
                </div>
              </>
            ) : null}
            <div>
              <dt>location_resolved</dt>
              <dd>
                <code>{String(locationResolved)}</code>
              </dd>
            </div>
            <div>
              <dt>parcel_geometry_confirmed</dt>
              <dd>
                <code>{String(parcelConfirmed)}</code>
              </dd>
            </div>
            {run.parcel_resolution_id ? (
              <div>
                <dt>parcel_resolution_id</dt>
                <dd>
                  <code>{run.parcel_resolution_id}</code>
                </dd>
              </div>
            ) : null}
          </dl>
        </details>
      </section>
    </div>
  );
}

function InvestigationOutcomePanel({
  run,
  outcome,
  selectedCandidateId,
  confirmBusy,
  onSelectCandidate,
  onAction,
  onRetry,
  onVerifiedDemo,
}: {
  run: AgentRun;
  outcome: InvestigationOutcome;
  selectedCandidateId: string;
  confirmBusy: boolean;
  onSelectCandidate: (candidateId: string) => void;
  onAction: () => void;
  onRetry: () => void;
  onVerifiedDemo: () => void;
}) {
  const copy = humanOutcomeCopy(run, outcome);
  const locationResolved = Boolean(run.location_resolved);
  const parcelConfirmed = Boolean(run.parcel_geometry_confirmed);
  const candidates = run.parcel_candidates || [];
  const selected = candidates.find((row) => row.candidate_id === selectedCandidateId);
  const canConfirm =
    outcome === "PARCEL_NEEDS_CONFIRMATION" &&
    Boolean(run.parcel_resolution_id) &&
    Boolean(selected?.candidate_id) &&
    Boolean(selected?.geometry_hash);
  const showEntryFailureActions =
    outcome === "PARCEL_NOT_FOUND" ||
    outcome === "PARCEL_SERVICE_UNAVAILABLE" ||
    outcome === "INVESTIGATION_COULD_NOT_COMPLETE";
  const tone =
    outcome === "EVIDENCE_INVESTIGATION_COMPLETED"
      ? "complete"
      : outcome === "EVIDENCE_INVESTIGATION_INCOMPLETE"
        ? "limited"
        : outcome === "PARCEL_NEEDS_CONFIRMATION"
          ? "confirm"
          : "failed";
  const lookup = run.mireye_live?.lookup;
  return (
    <section
      className={`advisor-outcome advisor-outcome-${tone}`}
      aria-label="Investigation outcome"
      data-testid="investigation-outcome"
      data-outcome={outcome}
    >
      <h2>{withMireyeBold(copy.title)}</h2>
      <p className="advisor-decision-lead">{withMireyeBold(copy.why)}</p>
      <p>{withMireyeBold(copy.next)}</p>
      <p className="advisor-quiet">{withMireyeBold(copy.report)}</p>

      {outcome !== "EVIDENCE_INVESTIGATION_COMPLETED" ? (
        <dl className="advisor-resolve-flags" aria-label="Location and parcel flags">
          <div>
            <dt>Location</dt>
            <dd>
              {locationResolved ? "Location recognized" : "Location not resolved"}
              {!parcelConfirmed ? (
                <span className="advisor-quiet">
                  {" "}
                  · not the same as a confirmed parcel
                </span>
              ) : null}
            </dd>
          </div>
          <div>
            <dt>Parcel boundary</dt>
            <dd>
              {parcelConfirmed
                ? "Parcel boundary confirmed for this investigation"
                : "Parcel boundary not confirmed"}
            </dd>
          </div>
        </dl>
      ) : null}

      {candidates.length > 0 ? (
        <fieldset className="advisor-outcome-candidates" disabled={confirmBusy}>
          <legend>Parcel candidates</legend>
          {candidates.map((row, index) => {
            const id = row.candidate_id || `cand-${index}`;
            const confirmable = Boolean(row.candidate_id && row.geometry_hash);
            return (
              <label key={id} className="advisor-candidate-choice">
                <input
                  type="radio"
                  name="advisor-parcel-candidate"
                  value={row.candidate_id || ""}
                  checked={selectedCandidateId === row.candidate_id}
                  disabled={!confirmable}
                  onChange={() => {
                    if (row.candidate_id) onSelectCandidate(row.candidate_id);
                  }}
                />
                <span>
                  {row.label || row.parcel_id || `Candidate ${index + 1}`}
                  {row.has_geometry ? " · has geometry" : " · no geometry yet"}
                  {row.geometry_hash ? (
                    <>
                      {" "}
                      · hash <code>{row.geometry_hash.slice(0, 8)}</code>
                    </>
                  ) : (
                    " · missing geometry hash"
                  )}
                </span>
              </label>
            );
          })}
        </fieldset>
      ) : null}

      {outcome === "PARCEL_NEEDS_CONFIRMATION" && run.parcel_resolution_id ? (
        <p className="advisor-quiet">
          Staged resolution <code>{run.parcel_resolution_id}</code>. Confirm
          posts{" "}
          <code>selected_candidate_id</code>,{" "}
          <code>expected_geometry_hash</code>, and{" "}
          <code>explicit_confirmation=true</code>, then re-runs Advisor with
          that <code>parcel_resolution_id</code>.
        </p>
      ) : null}

      {showEntryFailureActions ? (
        <div className="advisor-outcome-actions">
          <button
            type="button"
            className="advisor-run-button"
            onClick={onAction}
            disabled={confirmBusy}
          >
            Edit location
          </button>
          {outcome === "PARCEL_SERVICE_UNAVAILABLE" ? (
            <button
              type="button"
              className="advisor-chip"
              onClick={onRetry}
              disabled={confirmBusy || !String(run.address || "").trim()}
            >
              Retry
            </button>
          ) : null}
          <button
            type="button"
            className="advisor-chip"
            onClick={onVerifiedDemo}
            disabled={confirmBusy}
          >
            Try verified Nambe demo
          </button>
        </div>
      ) : (
        <button
          type="button"
          className="advisor-run-button"
          onClick={onAction}
          disabled={
            confirmBusy || (outcome === "PARCEL_NEEDS_CONFIRMATION" && !canConfirm)
          }
        >
          {confirmBusy && outcome === "PARCEL_NEEDS_CONFIRMATION"
            ? "Confirming parcel…"
            : copy.cta}
        </button>
      )}

      <details className="advisor-tech-details">
        <summary>Technical details</summary>
        <dl>
          <div>
            <dt>investigation_outcome</dt>
            <dd>
              <code>{outcome}</code>
            </dd>
          </div>
          <div>
            <dt>run_mode</dt>
            <dd>
              <code>{run.run_mode || "CUSTOM"}</code>
            </dd>
          </div>
          {lookup ? (
            <>
              <div>
                <dt>lookup.error_class</dt>
                <dd>
                  <code>{lookup.error_class || "—"}</code>
                </dd>
              </div>
              <div>
                <dt>lookup.http_status</dt>
                <dd>
                  <code>
                    {lookup.http_status == null ? "—" : String(lookup.http_status)}
                  </code>
                </dd>
              </div>
            </>
          ) : null}
          <div>
            <dt>location_resolved</dt>
            <dd>
              <code>{String(locationResolved)}</code>
            </dd>
          </div>
          <div>
            <dt>parcel_geometry_confirmed</dt>
            <dd>
              <code>{String(parcelConfirmed)}</code>
            </dd>
          </div>
          {run.parcel_resolution_id ? (
            <div>
              <dt>parcel_resolution_id</dt>
              <dd>
                <code>{run.parcel_resolution_id}</code>
              </dd>
            </div>
          ) : null}
          {run.geometry_hash ? (
            <div>
              <dt>geometry_hash</dt>
              <dd>
                <code>{run.geometry_hash}</code>
              </dd>
            </div>
          ) : null}
          {run.failed_step ? (
            <div>
              <dt>failed_step</dt>
              <dd>
                <code>{run.failed_step}</code>
              </dd>
            </div>
          ) : null}
          {run.error ? (
            <div>
              <dt>error</dt>
              <dd>{run.error}</dd>
            </div>
          ) : null}
          {run.mireye_live?.lookup ? (
            <div>
              <dt>{withMireyeBold("Mireye lookup")}</dt>
              <dd>
                ok=<code>{String(Boolean(run.mireye_live.lookup.ok))}</code>
                {run.mireye_live.lookup.error_class
                  ? ` · error_class=${run.mireye_live.lookup.error_class}`
                  : ""}
                {run.mireye_live.lookup.http_status != null
                  ? ` · http_status=${run.mireye_live.lookup.http_status}`
                  : ""}
                {run.mireye_live.lookup.disposition
                  ? ` · disposition=${run.mireye_live.lookup.disposition}`
                  : ""}
              </dd>
            </div>
          ) : null}
          {(run.limitations?.length || 0) > 0 ? (
            <div>
              <dt>limitations</dt>
              <dd>
                <ul>
                  {run.limitations?.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              </dd>
            </div>
          ) : null}
        </dl>
      </details>
    </section>
  );
}

function LimitedLocationPanel({ run }: { run: AgentRun }) {
  const limited = run.limited_investigation;
  const point = limited?.geocode_point;
  return (
    <section
      id="advisor-limited-location"
      className="advisor-limited"
      aria-label="Resolved location"
      data-testid="limited-location"
    >
      <p className="advisor-kicker">Limited investigation</p>
      <h2>Resolved location</h2>
      <p>
        {limited?.normalized_address || run.address || "Recognized location"}
      </p>
      <p className="advisor-quiet">
        Location recognized does not mean the parcel boundary is confirmed. No
        cattle operating Snapshot is offered for this place yet.
      </p>
      <dl className="advisor-outcome-facts">
        {point ? (
          <div>
            <dt>Approximate point</dt>
            <dd>
              {point.lat.toFixed(5)}, {point.lng.toFixed(5)}
            </dd>
          </div>
        ) : null}
        <div>
          <dt>{withMireyeBold("Mireye disposition")}</dt>
          <dd>{limited?.mireye_disposition || "—"}</dd>
        </div>
        <div>
          <dt>Confidence / accuracy</dt>
          <dd>
            {limited?.confidence != null ? limited.confidence : "—"}
            {limited?.accuracy_type ? ` · ${limited.accuracy_type}` : ""}
          </dd>
        </div>
        <div>
          <dt>Demo policy</dt>
          <dd>
            {limited?.cper_policy_blocked
              ? "CPER listing claims, F03 objects, and demo policy are blocked"
              : "—"}
          </dd>
        </div>
      </dl>
    </section>
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

function formatAnswerValue(value: unknown): string {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (value == null) return "—";
  const key = String(value).toUpperCase();
  if (key === "SEASONAL_GRAZING") return "Seasonal grazing";
  if (key === "YEAR_ROUND_COW_CALF") return "Year-round cow-calf";
  return String(value).replaceAll("_", " ");
}

function AdvisorBriefResult({
  run,
  onRunUpdate,
  chatOpen = false,
  onOpenChat,
}: {
  run: AgentRun;
  onRunUpdate?: (next: AgentRun) => void;
  chatOpen?: boolean;
  onOpenChat?: () => void;
}) {
  const brief = run.brief;
  const packet = run.packet;
  const [answerBusy, setAnswerBusy] = useState(false);
  const [answerError, setAnswerError] = useState<string | null>(null);
  const [chatBusy, setChatBusy] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [chatDraft, setChatDraft] = useState("");
  const [chatTurns, setChatTurns] = useState(run.chat_turns || []);
  const [chatSuggestions, setChatSuggestions] = useState(
    run.chat_suggestions || [
      { intent: "WATER", prompt: "What do we know about livestock water?" },
      { intent: "FEED", prompt: "What does the vegetation evidence actually tell me?" },
      { intent: "MOVEMENT", prompt: "How could cattle move across this parcel?" },
      { intent: "NEXT_ACTION", prompt: "What should I request next?" },
    ],
  );

  useEffect(() => {
    setChatTurns(run.chat_turns || []);
    if (run.chat_suggestions?.length) {
      setChatSuggestions(run.chat_suggestions);
    }
  }, [run.run_id, run.chat_turns, run.chat_suggestions]);

  useEffect(() => {
    if (!chatOpen) return;
    const node = document.getElementById("advisor-report-chat");
    node?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  }, [chatOpen]);

  const conclusion = run.operating_conclusion;
  const interpretation = run.natural_foundation_interpretation;
  const initial = run.initial_operating_conclusion;
  const change = run.conclusion_change;
  if (!conclusion?.headline && !interpretation?.advisor_view && !(brief && packet)) {
    return null;
  }

  const canChat = Boolean(interpretation?.advisor_view || conclusion?.headline);

  const pageOne = brief?.page_one_advisor;
  const messages = brief
    ? [...brief.page_two_actions.messages].sort(
        (a, b) => audienceRank(a.audience) - audienceRank(b.audience),
      )
    : [];
  const kitchen = brief?.page_three_kitchen;
  const objects = packet?.candidate_objects || [];
  const drawable = objects.filter(
    (row) => row.geometry?.field_navigation_precision === "AREA_ONLY",
  );
  const inventoryOnly = objects.filter(
    (row) => row.geometry?.field_navigation_precision === "NOT_NAVIGABLE",
  );
  const water = packet?.bottlenecks?.find(
    (row) => row.bottleneck_id === "BOTTLENECK_WATER_EVIDENCE",
  );
  const first = packet
    ? [...packet.actions].sort((a, b) => a.execution_order - b.execution_order)[0]
    : undefined;
  const explanation = run.buyer_explanation;
  const activeQuestion = interpretation?.next_question || conclusion?.next_question;
  const canAnswer =
    Boolean(activeQuestion?.question_id) &&
    Boolean(run.geometry_hash) &&
    typeof (
      interpretation?.deal_context_version ??
      conclusion?.deal_context_version ??
      run.deal_context?.context_version
    ) === "number" &&
    !change;

  async function submitAnswer(answer: string | boolean) {
    if (!activeQuestion?.question_id || !run.geometry_hash) return;
    const version =
      interpretation?.deal_context_version ??
      conclusion?.deal_context_version ??
      run.deal_context?.context_version ??
      1;
    setAnswerBusy(true);
    setAnswerError(null);
    try {
      const response = await fetch(`/v1/advisor/runs/${run.run_id}/answers`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          question_id: activeQuestion.question_id,
          answer,
          expected_context_version: version,
          expected_geometry_hash: run.geometry_hash,
        }),
      });
      const body = (await response.json()) as AgentRun & { detail?: string };
      if (!response.ok) {
        setAnswerError(String(body.detail || `answer_failed_${response.status}`));
        return;
      }
      onRunUpdate?.(body);
    } catch (error) {
      setAnswerError(error instanceof Error ? error.message : "answer_failed");
    } finally {
      setAnswerBusy(false);
    }
  }

  async function submitChat(message: string) {
    const text = message.trim();
    if (!text) return;
    setChatBusy(true);
    setChatError(null);
    try {
      const response = await fetch(`/v1/advisor/runs/${run.run_id}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const body = (await response.json()) as {
        detail?: string;
        turns?: AgentRun["chat_turns"];
        suggested_questions?: AgentRun["chat_suggestions"];
        turn?: NonNullable<AgentRun["chat_turns"]>[number];
      };
      if (!response.ok) {
        setChatError(String(body.detail || `chat_failed_${response.status}`));
        return;
      }
      setChatTurns(body.turns || []);
      if (body.suggested_questions?.length) {
        setChatSuggestions(body.suggested_questions);
      }
      setChatDraft("");
      onRunUpdate?.({
        ...run,
        chat_turns: body.turns || run.chat_turns,
        chat_suggestions: body.suggested_questions || run.chat_suggestions,
      });
    } catch (error) {
      setChatError(error instanceof Error ? error.message : "chat_failed");
    } finally {
      setChatBusy(false);
    }
  }

  const questionField = activeQuestion?.allowed_field;
  const whyLines = [
    water?.title,
    first?.why_now,
    pageOne?.how_the_tract_reads,
  ].filter(Boolean) as string[];

  return (
    <div id="advisor-brief-result" className="advisor-product">
      {interpretation?.advisor_view ? (
        <section className="advisor-decision" aria-label="Natural cattle foundation view">
          <p className="advisor-kicker">Natural cattle foundation</p>
          <h2>
            {withMireyeBold(
              interpretation.advisor_judgment || interpretation.advisor_view || "",
            )}
          </h2>
          <p className="advisor-decision-lead">
            {withMireyeBold(
              interpretation.land_character ||
                interpretation.integrated_natural_reading ||
                "",
            )}
          </p>
          {(interpretation.operating_possibilities || []).length > 0 ? (
            <div className="advisor-possibilities">
              <h3>What this may support</h3>
              <ul className="advisor-why-list">
                {(interpretation.operating_possibilities || []).slice(0, 3).map((line) => (
                  <li key={line.slice(0, 48)}>{withMireyeBold(line)}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <dl className="advisor-decision-facts">
            <div>
              <dt>What your plan changes</dt>
              <dd>{withMireyeBold(interpretation.intended_use_interpretation || "")}</dd>
            </div>
            <div>
              <dt>Controlling factor</dt>
              <dd>
                {withMireyeBold(
                  (interpretation.controlling_factor?.domain || "unresolved").replaceAll(
                    "_",
                    " ",
                  ),
                )}
              </dd>
            </div>
            <div>
              <dt>To refine this assessment</dt>
              <dd>{withMireyeBold(interpretation.refinement_request || "")}</dd>
            </div>
          </dl>
          {(interpretation.conditional_scenarios || interpretation.what_would_change_the_view || []).length > 0 ? (
            <ul className="advisor-why-list">
              {(interpretation.conditional_scenarios || interpretation.what_would_change_the_view || []).slice(0, 3).map((line) => (
                <li key={line.slice(0, 48)}>{withMireyeBold(line)}</li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : conclusion?.headline ? (
        <section className="advisor-decision" aria-label="Current cattle operating view">
          <p className="advisor-kicker">Current cattle operating view</p>
          <h2>{withMireyeBold(conclusion.headline || "")}</h2>
          <p className="advisor-decision-lead">{withMireyeBold(conclusion.summary || "")}</p>
          <dl className="advisor-decision-facts">
            <div>
              <dt>Primary constraint</dt>
              <dd>{withMireyeBold(conclusion.primary_constraint || "")}</dd>
            </div>
            <div>
              <dt>Recommended next spend</dt>
              <dd>{conclusion.next_spend_class || "—"}</dd>
            </div>
            <div>
              <dt>Next move</dt>
              <dd>{withMireyeBold(conclusion.next_action || "")}</dd>
            </div>
          </dl>
        </section>
      ) : null}

      {!interpretation?.advisor_view && whyLines.length > 0 && conclusion?.headline ? (
        <section className="advisor-reason" aria-label="Why this reading">
          <h2>Why this reading</h2>
          <ul className="advisor-why-list">
            {whyLines.slice(0, 3).map((line) => (
              <li key={line.slice(0, 48)}>{withMireyeBold(line)}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {canAnswer && activeQuestion?.prompt ? (
        <section
          className="advisor-decision advisor-conclusion-question"
          role="group"
          aria-label="Agent question"
        >
          <p className="advisor-kicker">One question that could change this view</p>
          <p className="advisor-conclusion-question-prompt">
            {withMireyeBold(activeQuestion.prompt)}
          </p>
          <div className="advisor-answer-actions">
            {questionField === "operation_type" ? (
              <>
                <button
                  type="button"
                  className="advisor-chip"
                  disabled={answerBusy}
                  onClick={() => void submitAnswer("SEASONAL_GRAZING")}
                >
                  Seasonal grazing
                </button>
                <button
                  type="button"
                  className="advisor-chip"
                  disabled={answerBusy}
                  onClick={() => void submitAnswer("YEAR_ROUND_COW_CALF")}
                >
                  Year-round cow-calf
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  className="advisor-chip"
                  disabled={answerBusy}
                  onClick={() => void submitAnswer(true)}
                >
                  Yes
                </button>
                <button
                  type="button"
                  className="advisor-chip"
                  disabled={answerBusy}
                  onClick={() => void submitAnswer(false)}
                >
                  No
                </button>
              </>
            )}
          </div>
          {answerError ? (
            <p className="advisor-copy-failed" role="alert">
              {answerError}
            </p>
          ) : null}
        </section>
      ) : null}

      {change ? (
        <section className="advisor-decision advisor-conclusion-loop" aria-label="Conclusion update">
          <p className="advisor-kicker">What changed after your answer</p>
          <dl className="advisor-decision-facts">
            <div>
              <dt>Your answer</dt>
              <dd>{formatAnswerValue(change.user_answer?.value)}</dd>
            </div>
            <div>
              <dt>What changed</dt>
              <dd>{withMireyeBold(change.summary || "")}</dd>
            </div>
            <div>
              <dt>Current view</dt>
              <dd>{(change.change_status || "").replaceAll("_", " ")}</dd>
            </div>
          </dl>
          {conclusion?.headline ? (
            <div className="advisor-change-now">
              <p className="advisor-kicker">Updated operating view</p>
              <h3>{conclusion.headline}</h3>
              <p>{conclusion.primary_constraint}</p>
            </div>
          ) : null}
          {initial?.headline && initial.headline !== conclusion?.headline ? (
            <p className="advisor-quiet">Earlier view: {initial.headline}</p>
          ) : null}
        </section>
      ) : null}

      {canChat ? (
        <section
          id="advisor-report-chat"
          className="advisor-decision advisor-chat"
          aria-label="Grounded chat about this report"
        >
          {!chatOpen ? (
            <>
              <p className="advisor-kicker">After this report</p>
              <h2>Continue with a grounded chat</h2>
              <p className="advisor-decision-lead">
                Chat uses this parcel’s analyzed evidence plus reviewed cattle-land
                knowledge. It is available only after analysis completes.
              </p>
              <button
                type="button"
                className="advisor-report-chat-start advisor-report-chat-start-inline"
                onClick={() => onOpenChat?.()}
              >
                Start to chat
              </button>
            </>
          ) : (
            <>
              <p className="advisor-kicker">Property chat</p>
              <h2>Ask about this analyzed parcel</h2>
              <p className="advisor-quiet advisor-chat-scope">
                Answers stay grounded in this run’s evidence and approved cattle knowledge —
                not a general ChatGPT.
              </p>
              <div className="advisor-chat-suggestions" role="group" aria-label="Suggested questions">
                {chatSuggestions.map((row) => (
                  <button
                    key={`${row.intent}-${row.prompt}`}
                    type="button"
                    className="advisor-chip"
                    disabled={chatBusy}
                    onClick={() => void submitChat(row.prompt || "")}
                  >
                    {row.prompt}
                  </button>
                ))}
              </div>
              <form
                className="advisor-chat-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  void submitChat(chatDraft);
                }}
              >
                <label className="advisor-address-label" htmlFor="advisor-chat-input">
                  Your question
                </label>
                <input
                  id="advisor-chat-input"
                  className="advisor-address"
                  value={chatDraft}
                  disabled={chatBusy}
                  onChange={(event) => setChatDraft(event.target.value)}
                  placeholder="Ask about water, vegetation, movement, or next request"
                />
                <button
                  type="submit"
                  className="advisor-chip"
                  disabled={chatBusy || !chatDraft.trim()}
                >
                  {chatBusy ? "Answering…" : "Ask"}
                </button>
              </form>
              {chatError ? (
                <p className="advisor-copy-failed" role="alert">
                  {chatError}
                </p>
              ) : null}
              {chatTurns.length > 0 ? (
                <ol className="advisor-chat-turns">
                  {chatTurns.map((turn) => (
                    <li key={turn.turn_id || turn.user_message}>
                      <p className="advisor-quiet">You</p>
                      <p className="advisor-chat-user">
                        {withMireyeBold(turn.user_message || "")}
                      </p>
                      <p className="advisor-chat-judgment">
                        {withMireyeBold(turn.judgment || "")}
                      </p>
                      <p>{withMireyeBold(turn.answer || "")}</p>
                    </li>
                  ))}
                </ol>
              ) : null}
            </>
          )}
        </section>
      ) : null}

      <div className="advisor-product-actions">
        <details className="advisor-tech-details advisor-kitchen">
          <summary>View technical evidence</summary>
          <div className="advisor-kitchen-body">
            <p className="advisor-quiet">
              Run <code>{run.run_id}</code>
              {run.packet_hash ? (
                <>
                  {" "}
                  · packet <code title={run.packet_hash}>{shortId(run.packet_hash)}</code>
                </>
              ) : null}
              {prettyTime(run.generated_at) ? ` · ${prettyTime(run.generated_at)}` : ""}
            </p>
            {run.mireye_live ? <MireyeLivePanel live={run.mireye_live} /> : null}
            {(run.steps || []).length > 0 ? (
              <section>
                <h3>Run trace</h3>
                <ol className="advisor-steps">
                  {run.steps.map((step) => (
                    <li
                      key={step.step_id}
                      className={`advisor-step advisor-step-${step.status.toLowerCase()}`}
                    >
                      <span className="advisor-step-label">{withMireyeBold(step.label)}</span>
                      <span className="advisor-step-status">{step.status}</span>
                    </li>
                  ))}
                </ol>
              </section>
            ) : null}
            {(run.agenda || []).length > 0 ? (
              <section>
                <h3>Agenda</h3>
                <ol className="advisor-agenda" aria-label="Agenda system">
                  {run.agenda?.map((row) => (
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
              </section>
            ) : null}
            {explanation?.ranch_narrative ? (
              <section>
                <h3>Legacy ranch narrative</h3>
                <p>{explanation.ranch_narrative.operating_thesis}</p>
                <p className="advisor-quiet">{explanation.ranch_narrative.client_summary}</p>
              </section>
            ) : explanation?.sections ? (
              <section>
                <h3>Legacy buyer explanation</h3>
                {explanation.source === "DETERMINISTIC_FALLBACK" ? (
                  <p role="status">
                    Evidence investigation completed. Live language overlay unavailable;
                    deterministic brief shown. No fixture was substituted.
                  </p>
                ) : null}
                <p>{explanation.sections.recommendation}</p>
                <p className="advisor-quiet">
                  Source {explanation.source}
                  {explanation.provenance?.provider_status
                    ? ` · ${explanation.provenance.provider_status}`
                    : ""}
                  {typeof explanation.provenance?.retry_count === "number"
                    ? ` · retries ${explanation.provenance.retry_count}`
                    : ""}
                </p>
              </section>
            ) : null}
            {pageOne ? (
              <section>
                <h3>Legacy decision brief</h3>
                <p>{VISIT_HEADLINE[pageOne.visit_purpose]}</p>
                <p className="advisor-quiet">{pageOne.how_the_tract_reads}</p>
                <ol>
                  {pageOne.do_today.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ol>
              </section>
            ) : null}
            {messages.length > 0 ? (
              <section>
                <h3>Partner and outreach copy</h3>
                {messages.map((row) => (
                  <article key={row.message_id} className="advisor-action-card">
                    <header>
                      <h4>{AUDIENCE_LABEL[row.audience] || row.audience}</h4>
                      <AdvisorCopyButton
                        label={`Copy for ${AUDIENCE_LABEL[row.audience] || row.audience}`}
                        text={row.body}
                      />
                    </header>
                    <p>{row.body}</p>
                  </article>
                ))}
              </section>
            ) : null}
            {packet && kitchen ? (
              <>
                <section>
                  <h3>Parcel</h3>
                  <p>{packet.parcel.display_label}</p>
                  {run.parcel_geometry ? (
                    <AdvisorDemoMap parcel={run.parcel_geometry} layers={kitchen.map_layers} />
                  ) : null}
                </section>
                <section>
                  <h3>Review on the map ({drawable.length})</h3>
                  <ul>
                    {drawable.map((row) => (
                      <li key={row.candidate_id}>{objectLabel(row)}</li>
                    ))}
                  </ul>
                </section>
                <section>
                  <h3>Catalog only ({inventoryOnly.length})</h3>
                  <ul>
                    {inventoryOnly.map((row) => (
                      <li key={row.candidate_id}>{objectLabel(row)}</li>
                    ))}
                  </ul>
                </section>
                <section>
                  <h3>Measured observations</h3>
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
                  <h3>Engine appendix</h3>
                  <p className="advisor-quiet">
                    Engine decision labels stay confined here. They are not a
                    buy/no-buy verdict.
                  </p>
                </section>
              </>
            ) : null}
            <p className="advisor-quiet">
              Legacy{" "}
              <a href={`/v1/advisor/runs/${run.run_id}/buyer-brief.pdf`}>three-page brief PDF</a>{" "}
              remains available for compatibility.
            </p>
          </div>
        </details>
      </div>
    </div>
  );
}
