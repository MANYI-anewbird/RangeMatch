export type Mode = "GOAL_DIRECTED" | "DISCOVERY";
export type IntendedOperation = "COW_CALF_OPERATION" | "SHEEP_GRAZING" | null;
export type ExecutionSource =
  | "EXISTING_LAND_PROFILE"
  | "DEMO_FIXTURE"
  | "PARCEL_RESOLUTION";
export type MireyeMode = "FIXTURE" | "LIVE" | "BLOCKED_EXTERNAL";
export type ResolverMode = "FIXTURE" | "LIVE";

export type AnalysisChoice = "GENERAL" | "CATTLE" | "SHEEP";

export function analysisChoiceToApi(choice: AnalysisChoice): {
  mode: Mode;
  intended_operation: IntendedOperation;
} {
  if (choice === "GENERAL") return { mode: "DISCOVERY", intended_operation: null };
  if (choice === "CATTLE")
    return { mode: "GOAL_DIRECTED", intended_operation: "COW_CALF_OPERATION" };
  return { mode: "GOAL_DIRECTED", intended_operation: "SHEEP_GRAZING" };
}

export type InvestigationCreateRequest = {
  address?: string | null;
  parcel_geometry?: Record<string, unknown> | null;
  existing_land_profile_reference?: string | null;
  parcel_resolution_id?: string | null;
  mode: Mode;
  intended_operation?: IntendedOperation;
  planned_actions?: string[];
  execution_source: ExecutionSource;
  mireye_mode?: MireyeMode;
  allow_network?: boolean;
};

export type InvestigationStatus =
  | "QUEUED"
  | "RUNNING"
  | "COMPLETED"
  | "PARTIAL"
  | "FAILED"
  | "BLOCKED_EXTERNAL"
  | "BLOCKED_INPUT";

export const INVESTIGATION_TERMINAL_STATUSES = new Set<string>([
  "COMPLETED",
  "PARTIAL",
  "FAILED",
  "BLOCKED_EXTERNAL",
  "BLOCKED_INPUT",
]);

export type Investigation = {
  investigation_id: string;
  status: InvestigationStatus | string;
  mode: Mode;
  intended_operation: IntendedOperation;
  execution_source: ExecutionSource;
  replay_label?: string | null;
  plan_ref?: string | null;
  plan_sha256?: string | null;
  execution_ref?: string | null;
  deterministic_execution_hash?: string | null;
  unified_output_ref?: string | null;
  unified_output?: Record<string, unknown> | null;
  limitations?: string[];
  created_at?: string;
  started_at?: string | null;
  completed_at?: string | null;
  parcel_resolution_id?: string | null;
  geometry_hash?: string | null;
  geometry_reference?: string | null;
  source_crs?: string | null;
  presentation?: {
    operation_presentation_order?: string[];
    scientific_priority_change?: boolean;
  };
};

export type TraceStep = {
  step_id: string;
  tool_id: string;
  action?: string;
  status: string;
  failure?: Record<string, unknown> | null;
  reused_artifact_refs?: string[];
  factor_id?: string | null;
  parallel_group?: string | null;
};

export type Trace = {
  execution_id?: string;
  execution_status?: string;
  steps: TraceStep[];
  failures?: unknown[];
  deterministic_execution_hash?: string;
};

export type Report = {
  investigation_id: string;
  source: string;
  replay_label?: string | null;
  mode?: Mode;
  intended_operation?: IntendedOperation;
  match_result_hash?: string;
  explanation_binding_hash?: string;
  sections: Record<string, SectionBody | undefined>;
  limitations?: string[];
};

export type NarrativeSection = {
  heading: string;
  summary: string;
  findings: string[];
  evidence_refs?: string[];
  limitation_refs?: string[];
};

export type BuyerReport = {
  schema_version?: string;
  match_result_hash?: string;
  mode?: Mode;
  intended_operation?: IntendedOperation | null;
  validation_status?: string;
  executive_summary?: NarrativeSection;
  property?: NarrativeSection;
  land_and_resources?: NarrativeSection;
  resilience_and_hazards?: NarrativeSection;
  operation_comparison?: NarrativeSection;
  key_unknowns?: NarrativeSection;
  diligence_plan?: NarrativeSection;
  methodology_and_limitations?: NarrativeSection;
  evidence_references?: Record<string, unknown>[];
  claim_ledger?: Record<string, unknown>[];
  report_provenance?: Record<string, unknown>;
};

export type BuyerReportResponse = {
  investigation_id: string;
  displayable: boolean;
  validation_status: string;
  buyer_report: BuyerReport | null;
  validation_violations?: { code: string; message: string; path?: string }[];
  report_provenance?: Record<string, unknown>;
};

export type DiligenceSearchSource = {
  source_id: string;
  title: string;
  url: string;
  domain?: string;
  publisher?: string | null;
  retrieved_at?: string;
};

export type DiligenceSearchResult = {
  status: string;
  summary: string;
  sources: DiligenceSearchSource[];
  search_topics?: string[];
  limitations?: string[];
  effect_on_engine?: string;
  provider?: string;
  location_scope?: string;
};

export type DiligenceSearchResponse = {
  investigation_id: string;
  diligence_search: DiligenceSearchResult;
};

export type SectionBody = {
  section_id?: string;
  factor_ids?: string[];
  highlights?: Record<string, unknown>[];
  unknowns?: string[];
  limitations?: string[];
  diligence_actions?: unknown[];
  mireye_context_types?: string[];
};

export type ParcelCandidate = {
  candidate_id: string;
  label: string;
  parcel_geometry: Record<string, unknown>;
  source_crs?: string;
  normalized_crs?: string | null;
  geometry_hash?: string | null;
  confidence?: number | null;
  provenance?: Record<string, unknown>;
  limitations?: string[];
  attributes?: Record<string, unknown>;
  validation_status?: string | null;
  validation_errors?: string[];
};

export type ParcelResolution = {
  schema_version?: string;
  resolution_id: string;
  adapter_id?: string;
  adapter_version?: string;
  provider_mode?: string;
  status: string;
  scenario_id?: string | null;
  input?: { raw_address?: string; normalized_address?: string | null };
  normalized_address?: string | null;
  geocode?: Record<string, unknown> | null;
  candidates: ParcelCandidate[];
  selection?: {
    selected_candidate_id?: string | null;
    confirmed_at?: string | null;
    confirmation_method?: string | null;
  } | null;
  confirmation_status?: {
    status?: string;
    selected_candidate_id?: string | null;
    confirmed_at?: string | null;
    confirmation_method?: string | null;
    confirmed?: boolean;
  };
  confirmed_parcel?: {
    parcel_geometry: Record<string, unknown>;
    geometry_id: string;
    geometry_reference: string;
    geometry_hash: string;
    source_crs: string;
  } | null;
  evidence_invalidation_required?: boolean;
  previous_geometry_hash?: string | null;
  provenance?: Record<string, unknown>;
  limitations?: string[];
  errors?: { code: string; message: string; path?: string }[];
  planner_binding?: {
    parcel_geometry: Record<string, unknown>;
    geometry_reference: string;
    geometry_hash: string;
    source_crs: string;
    geometry_id?: string;
  };
};

export type LandInputKind = "ADDRESS" | "COORDINATE";

export type ParcelResolutionCreateRequest = {
  input_kind?: LandInputKind;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  resolver_mode: ResolverMode;
  fixture_scenario_id?: string | null;
  allow_network?: boolean;
};

export type ParcelResolutionConfirmRequest = {
  selected_candidate_id: string;
  expected_geometry_hash: string;
  explicit_confirmation: true;
};

/** Demo fixture addresses — explicit, never silent LIVE fallback. */
export const DEMO_RESOLVER_PRESETS = [
  {
    id: "cper_complete_demo",
    label: "Complete land analysis (demo)",
    input_kind: "ADDRESS" as const,
    address: "Central Plains Experimental Range Demo, Nunn, CO",
    fixture_scenario_id: "cper_complete_demo",
  },
  {
    id: "one_valid_candidate",
    label: "Parcel confirmation only (demo)",
    input_kind: "ADDRESS" as const,
    address: "100 Demo Ranch Rd, Weld County, CO 80701",
    fixture_scenario_id: "one_valid_candidate",
  },
  {
    id: "multiple_candidates",
    label: "Multiple candidates (demo)",
    input_kind: "ADDRESS" as const,
    address: "200 Split Ranch Rd, Weld County, CO 80701",
    fixture_scenario_id: "multiple_candidates",
  },
] as const;

export const DEMO_COORD_PRESET = {
  id: "coord_one_valid_candidate",
  label: "Pin near demo ranch (fixture)",
  input_kind: "COORDINATE" as const,
  latitude: 40.495,
  longitude: -104.895,
  fixture_scenario_id: "coord_one_valid_candidate",
} as const;

const DEFAULT_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ||
  "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${DEFAULT_BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers || {}),
    },
  });
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (!res.ok) {
    const detail =
      typeof data === "object" && data && "detail" in data
        ? typeof (data as { detail: unknown }).detail === "string"
          ? String((data as { detail: unknown }).detail)
          : JSON.stringify((data as { detail: unknown }).detail)
        : `http_${res.status}`;
    throw new Error(detail);
  }
  return data as T;
}

export function getApiBase(): string {
  return DEFAULT_BASE || "(same-origin / Vite proxy)";
}

export const api = {
  health: () => request<Record<string, unknown>>("/health"),
  createParcelResolution: (body: ParcelResolutionCreateRequest) =>
    request<ParcelResolution>("/v1/parcel-resolutions", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getParcelResolution: (id: string) =>
    request<ParcelResolution>(`/v1/parcel-resolutions/${id}`),
  confirmParcelResolution: (id: string, body: ParcelResolutionConfirmRequest) =>
    request<ParcelResolution>(`/v1/parcel-resolutions/${id}/confirm`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createInvestigation: (body: InvestigationCreateRequest) =>
    request<Investigation>("/v1/investigations", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getInvestigation: (id: string) =>
    request<Investigation>(`/v1/investigations/${id}`),
  getTrace: (id: string) => request<Trace>(`/v1/investigations/${id}/trace`),
  getReport: (id: string) => request<Report>(`/v1/investigations/${id}/report`),
  generateBuyerReport: (id: string, provider?: "FIXTURE" | "OPENAI") =>
    request<BuyerReportResponse>(`/v1/investigations/${id}/buyer-report`, {
      method: "POST",
      body: JSON.stringify(provider ? { provider } : {}),
    }),
  runDiligenceSearch: (id: string, provider?: "FIXTURE" | "OPENAI") =>
    request<DiligenceSearchResponse>(`/v1/investigations/${id}/diligence-search`, {
      method: "POST",
      body: JSON.stringify(provider ? { provider } : {}),
    }),
};

/** Approved demo path only — never free-form path input in UI. */
export const APPROVED_CPER_PROFILE =
  "test-data/land-profiles/land_profile_cper_001.json";

export const HOLD_COPY =
  "HOLD means evidence is incomplete, not that the land is unsuitable.";

export const STAGE_MAP: {
  id: string;
  label: string;
  agent: string;
  description: string;
  match: (s: TraceStep) => boolean;
}[] = [
  {
    id: "resolve",
    label: "Resolve parcel",
    agent: "Parcel Agent",
    description: "Confirming the exact property boundary so every check uses the same land.",
    match: (s) =>
      s.tool_id === "geometry.resolve" || s.tool_id === "geometry.validate_one_parcel",
  },
  {
    id: "mireye_property",
    label: "Mireye Property context",
    agent: "Property Context Agent",
    description: "Reading fast property and location context from Mireye.",
    match: (s) => s.tool_id === "mireye.property_diligence",
  },
  {
    id: "mireye_land",
    label: "Mireye Land context",
    agent: "Land Context Agent",
    description: "Reading Mireye land signals for rapid context and quality checks.",
    match: (s) => s.tool_id === "mireye.point_land",
  },
  {
    id: "mireye_hazard",
    label: "Mireye Hazard context",
    agent: "Hazard Context Agent",
    description: "Checking Mireye hazard signals and preserving any unavailable sources.",
    match: (s) => s.tool_id === "mireye.point_hazard",
  },
  {
    id: "geometry",
    label: "Geometry validation",
    agent: "Parcel Geometry Agent",
    description: "Measuring parcel area, shape, and geometry quality.",
    match: (s) => s.tool_id === "factor.f06_parcel_configuration",
  },
  {
    id: "factors",
    label: "F01–F08 investigation",
    agent: "Land Evidence Agents",
    description: "Checking terrain, forage, water, soils, climate, roads, and woody cover.",
    match: (s) =>
      s.tool_id === "factor.f08_woody_reuse_rap" ||
      (Boolean(s.factor_id) &&
        s.tool_id !== "factor.f06_parcel_configuration" &&
        s.tool_id.startsWith("adapter")),
  },
  {
    id: "assemble",
    label: "Land Profile assembly",
    agent: "Evidence Assembly Agent",
    description: "Combining reviewed facts, coverage, provenance, and unknowns into one profile.",
    match: (s) => s.tool_id === "profile.assemble",
  },
  {
    id: "engine",
    label: "Engine evaluation",
    agent: "Matching Engine",
    description: "Applying fixed Cow-Calf and Sheep rules without inventing scores or thresholds.",
    match: (s) => s.tool_id === "engine.evaluate",
  },
  {
    id: "report",
    label: "Report generation",
    agent: "Report Agent",
    description: "Turning the engine result into a buyer-readable report with validation checks.",
    match: (s) =>
      s.tool_id === "output.project_unified" ||
      s.tool_id === "explanation.bind_and_product",
  },
  {
    id: "public_research",
    label: "Current public guidance",
    agent: "Public Diligence Agent",
    description: "Searching current government and university guidance for rules and follow-up checks.",
    match: (s) => s.tool_id === "diligence.web_search",
  },
];

export function operationLabel(id: string | null | undefined): string {
  if (id === "COW_CALF_OPERATION") return "Cow-Calf";
  if (id === "SHEEP_GRAZING") return "Sheep";
  return id || "—";
}

export function signalTone(signal: string | undefined): string {
  const s = (signal || "").toUpperCase();
  if (s === "NEEDS_VERIFICATION" || s === "UNKNOWN") return "signal-verify";
  if (s === "CONTEXT_DEPENDENT") return "signal-context";
  if (s.includes("FAIL") || s.includes("BLOCK")) return "signal-block";
  return "signal-neutral";
}
