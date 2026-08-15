import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import brief from "../../test-data/advisor/cper_three_page_brief.json";
import packet from "../../test-data/advisor/cper_buyer_evidence_packet.json";
import { AdvisorDemoPage } from "../src/pages/AdvisorDemoPage";

vi.mock("../src/components/advisor/AdvisorDemoMap", () => ({
  AdvisorDemoMap: () => <div data-testid="advisor-demo-map" />,
}));

const SUCCESS_RUN = {
  status: "SUCCEEDED",
  run_id: "advisor_test_run_001",
  generated_at: "2026-08-12T21:00:00+00:00",
  fixture_id: "CPER",
  packet_hash: brief.packet_hash,
  geometry_hash: "a".repeat(64),
  llm_used: false,
  failed_step: null,
  error: null,
  investigation_outcome: "EVIDENCE_INVESTIGATION_COMPLETED",
  location_resolved: true,
  parcel_geometry_confirmed: true,
  steps: [
    { step_id: "GROUND_PARCEL", label: "Ground parcel", status: "SUCCEEDED" },
    { step_id: "GATHER_EVIDENCE", label: "Gather evidence", status: "SUCCEEDED" },
    { step_id: "COMPARE_CLAIMS", label: "Compare claims", status: "SUCCEEDED" },
    { step_id: "ORDER_ACTIONS", label: "Order actions", status: "SUCCEEDED" },
    { step_id: "VALIDATE_BRIEF", label: "Validate brief", status: "SUCCEEDED" },
  ],
  packet,
  brief,
  parcel_geometry: {
    type: "FeatureCollection",
    features: [],
  },
  operating_conclusion: {
    conclusion_id: "concl_demo_test01",
    status: "CONDITIONAL",
    headline: "Cattle operating case is conditional on the next cheap diligence step",
    summary:
      "Public evidence already frames a preliminary cattle operating picture for this tract.",
    primary_constraint:
      "The operating reading is still controlled by an unanswered buyer assumption.",
    confidence: "LOW",
    next_action: "Request access or title documents before travel.",
    next_spend_class: "DOCUMENT_REVIEW",
    what_would_change_view: [
      "Knowing seasonal versus year-round cow-calf changes how water demand should be read.",
    ],
    deal_context_version: 1,
    source: "DETERMINISTIC_FALLBACK",
    next_question: {
      question_id: "Q_OPERATION_TYPE",
      prompt:
        "Are you evaluating this property for seasonal grazing or a year-round cow-calf operation?",
      allowed_field: "operation_type",
      what_would_change_view_ref: "CHANGE_OPERATION_TYPE",
    },
  },
  initial_operating_conclusion: {
    conclusion_id: "concl_demo_test01",
    status: "CONDITIONAL",
    headline: "Cattle operating case is conditional on the next cheap diligence step",
    summary:
      "Public evidence already frames a preliminary cattle operating picture for this tract.",
    primary_constraint:
      "The operating reading is still controlled by an unanswered buyer assumption.",
    confidence: "LOW",
    next_action: "Request access or title documents before travel.",
    next_spend_class: "DOCUMENT_REVIEW",
    deal_context_version: 1,
    next_question: {
      question_id: "Q_OPERATION_TYPE",
      prompt:
        "Are you evaluating this property for seasonal grazing or a year-round cow-calf operation?",
      allowed_field: "operation_type",
      what_would_change_view_ref: "CHANGE_OPERATION_TYPE",
    },
  },
};

const FAILED_RUN = {
  status: "FAILED",
  run_id: "advisor_test_run_fail",
  generated_at: "2026-08-12T21:01:00+00:00",
  fixture_id: "CPER",
  packet_hash: null,
  llm_used: false,
  failed_step: "GATHER_EVIDENCE",
  error: "UnifiedOutputError: injected failure at GATHER_EVIDENCE",
  investigation_outcome: "INVESTIGATION_COULD_NOT_COMPLETE",
  location_resolved: true,
  parcel_geometry_confirmed: false,
  mireye_live: {
    mode: "UNIT_TEST_HOOK",
    lookup: { ok: false, error_class: "TIMEOUT", http_status: null },
  },
  steps: [
    { step_id: "GROUND_PARCEL", label: "Ground parcel", status: "SUCCEEDED" },
    { step_id: "GATHER_EVIDENCE", label: "Gather evidence", status: "FAILED" },
    { step_id: "COMPARE_CLAIMS", label: "Compare claims", status: "PENDING" },
    { step_id: "ORDER_ACTIONS", label: "Order actions", status: "PENDING" },
    { step_id: "VALIDATE_BRIEF", label: "Validate brief", status: "PENDING" },
  ],
  packet: null,
  brief: null,
  parcel_geometry: null,
};

const INCOMPLETE_RUN = {
  status: "SUCCEEDED",
  run_id: "advisor_test_run_incomplete",
  generated_at: "2026-08-12T21:02:00+00:00",
  address: "300 Random Ranch Rd, Weld County, CO 80701",
  packet_hash: null,
  llm_used: false,
  failed_step: null,
  error: null,
  investigation_outcome: "EVIDENCE_INVESTIGATION_INCOMPLETE",
  location_resolved: true,
  parcel_geometry_confirmed: false,
  limited_investigation: {
    normalized_address: "300 Random Ranch Rd, Weld County, CO 80701",
    location_resolved: true,
    parcel_geometry_confirmed: false,
    mireye_disposition: "resolved",
    confidence: 0.91,
    accuracy_type: "rooftop",
    geocode_point: { lat: 40.5, lng: -104.9 },
    cper_policy_blocked: true,
    full_buyer_report: false,
    message:
      "Location was recognized, but this parcel is not the CPER engineering demo.",
    next_step: "Review the resolved location.",
  },
  steps: [
    { step_id: "ACCEPT_PLACE", label: "Accept place", status: "SUCCEEDED" },
    { step_id: "RESOLVE_PARCEL", label: "Resolve parcel", status: "SUCCEEDED" },
    { step_id: "BUILD_AGENDA", label: "Build agenda", status: "SKIPPED" },
  ],
  packet: null,
  brief: null,
  parcel_geometry: null,
};

const CONFIRM_HASH_WEST = "a".repeat(64);
const CONFIRM_HASH_EAST = "b".repeat(64);

const NEEDS_CONFIRMATION_RUN = {
  status: "SUCCEEDED",
  run_id: "advisor_test_run_confirm",
  generated_at: "2026-08-12T21:03:00+00:00",
  address: "4213 Nambe Road, Indian Hills, CO",
  packet_hash: null,
  llm_used: false,
  failed_step: null,
  error: "Parcel needs confirmation",
  investigation_outcome: "PARCEL_NEEDS_CONFIRMATION",
  location_resolved: true,
  parcel_geometry_confirmed: false,
  parcel_resolution_id: "pr_advisor_test_confirm",
  parcel_candidates: [
    {
      candidate_id: "MIREYE-WEST",
      label: "West tract",
      parcel_id: "A",
      has_geometry: true,
      geometry_hash: CONFIRM_HASH_WEST,
    },
    {
      candidate_id: "MIREYE-EAST",
      label: "East tract",
      parcel_id: "B",
      has_geometry: true,
      geometry_hash: CONFIRM_HASH_EAST,
    },
  ],
  mireye_live: {
    mode: "UNIT_TEST_HOOK",
    lookup: { ok: true, disposition: "clarify", error_class: null, http_status: 200 },
  },
  steps: [
    { step_id: "ACCEPT_PLACE", label: "Accept place", status: "SUCCEEDED" },
    { step_id: "RESOLVE_PARCEL", label: "Resolve parcel", status: "NEEDS_CONFIRMATION" },
    { step_id: "CALL_MIREYE", label: "Call Mireye", status: "SKIPPED" },
  ],
  packet: null,
  brief: null,
  parcel_geometry: null,
};

function renderDemo() {
  return render(
    <MemoryRouter initialEntries={["/advisor-demo"]}>
      <Routes>
        <Route path="/advisor-demo" element={<AdvisorDemoPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function mockFetch(payload: unknown, ok = true) {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 500,
    json: async () => payload,
  }) as unknown as typeof fetch;
}

function fillPlaceAndRun(place = "4213 Nambe Road, Indian Hills, CO 80454") {
  fireEvent.change(screen.getByLabelText(/Enter a U\.S\. address or coordinates/i), {
    target: { value: place },
  });
  fireEvent.click(screen.getByRole("button", { name: /Run analysis/i }));
}

describe("Advisor demo route", () => {
  const writeText = vi.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    vi.restoreAllMocks();
    writeText.mockReset();
    writeText.mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    mockFetch(SUCCESS_RUN);
  });

  it("does not show a brief until the agent runs", () => {
    renderDemo();
    expect(screen.getByRole("button", { name: /Run analysis/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Enter a U\.S\. address or coordinates/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Try the verified Nambe example/i })).toBeInTheDocument();
    expect(screen.queryByLabelText(/Demo ranch \/ tract/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/called first on this Demo/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/POST \/v1\/lookup/i)).not.toBeInTheDocument();
    expect(screen.getByText(/No investigation yet/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Current cattle operating view/i })).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /Let’s understand this ranch/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/\bHOLD\b/)).not.toBeInTheDocument();
  });

  it("renders cattle operating view first after a successful agent run", async () => {
    renderDemo();
    fillPlaceAndRun();
    expect(
      await screen.findByRole("heading", {
        name: /Cattle operating case is conditional on the next cheap diligence step/i,
      }),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("investigation-outcome")).not.toBeInTheDocument();
    expect(screen.getByText(/Current cattle operating view/i)).toBeInTheDocument();
    expect(screen.getByText(/Primary constraint/i)).toBeInTheDocument();
    expect(screen.getByText(/Recommended next spend/i)).toBeInTheDocument();
    expect(screen.getByText("DOCUMENT_REVIEW")).toBeInTheDocument();
    expect(
      screen.getByText(
        /Are you evaluating this property for seasonal grazing or a year-round cow-calf operation/i,
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Seasonal grazing/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Year-round cow-calf/i })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Start to chat/i }).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByLabelText(/Suggested questions/i)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Download report/i })).toHaveAttribute(
      "href",
      "/v1/advisor/runs/advisor_test_run_001/cattle-operating-snapshot.pdf",
    );
    await userEvent.click(screen.getAllByRole("button", { name: /Start to chat/i })[0]);
    expect(screen.getByRole("heading", { name: /Ask about this analyzed parcel/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Suggested questions/i)).toBeInTheDocument();
    expect(screen.getByText(/View technical evidence/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Generate buyer explanation/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Do not send the client yet" })).not.toBeInTheDocument();
    expect(screen.queryByText(/three-page Buyer Report/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/POST \/v1\/lookup/i)).not.toBeInTheDocument();
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/v1/advisor/runs",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("4213 Nambe Road, Indian Hills, CO 80454"),
      }),
    );
  });

  it("keeps engineering and legacy brief inside technical evidence", async () => {
    renderDemo();
    fillPlaceAndRun();
    expect(await screen.findByText(/View technical evidence/i)).toBeInTheDocument();
    const tech = screen.getByText(/View technical evidence/i).closest("details");
    expect(tech).toBeTruthy();
    expect(tech).not.toHaveAttribute("open");
    fireEvent.click(screen.getByText(/View technical evidence/i));
    expect(tech).toHaveAttribute("open");
    expect(within(tech as HTMLElement).getByText(/advisor_test_run_001/)).toBeInTheDocument();
    expect(within(tech as HTMLElement).getByText(new RegExp(brief.packet_hash.slice(0, 12)))).toBeInTheDocument();
    expect(within(tech as HTMLElement).getByText(/Do not send the client yet/i)).toBeInTheDocument();
    expect(within(tech as HTMLElement).getByRole("button", { name: /Copy for Partner/i })).toBeInTheDocument();
    expect(within(tech as HTMLElement).getByRole("heading", { name: /Review on the map \(3\)/ })).toBeInTheDocument();
    expect(within(tech as HTMLElement).getByRole("heading", { name: /Catalog only \(6\)/ })).toBeInTheDocument();
    expect(within(tech as HTMLElement).getByRole("heading", { name: "Engine appendix" })).toBeInTheDocument();
  });

  it("copies outreach messages from technical evidence", async () => {
    renderDemo();
    fillPlaceAndRun();
    fireEvent.click(await screen.findByText(/View technical evidence/i));
    fireEvent.click(screen.getAllByRole("button", { name: /Copy for Title/i })[0]);
    expect(await screen.findByText("Copied")).toBeInTheDocument();
    expect(writeText).toHaveBeenCalled();
    const copied = String(writeText.mock.calls[0][0]);
    expect(copied.toLowerCase()).toMatch(/recorded legal entrance|easement|title/);
    fireEvent.click(screen.getAllByRole("button", { name: /Copy for Listing broker/i })[0]);
    fireEvent.click(screen.getAllByRole("button", { name: /Copy for Partner/i })[0]);
    expect(writeText).toHaveBeenCalledTimes(3);
  });

  it("falls back when the clipboard API is blocked", async () => {
    const execCommand = vi.fn().mockReturnValue(true);
    Object.defineProperty(document, "execCommand", {
      configurable: true,
      value: execCommand,
    });
    writeText.mockRejectedValueOnce(new Error("denied"));
    renderDemo();
    fillPlaceAndRun();
    fireEvent.click(await screen.findByText(/View technical evidence/i));
    fireEvent.click(await screen.findByRole("button", { name: /Copy for Title/i }));
    expect(await screen.findByText("Copied")).toBeInTheDocument();
    expect(execCommand).toHaveBeenCalledWith("copy");
  });

  it("shows a failure label when no copy method works", async () => {
    writeText.mockRejectedValueOnce(new Error("denied"));
    Object.defineProperty(document, "execCommand", {
      configurable: true,
      value: vi.fn().mockReturnValue(false),
    });
    renderDemo();
    fillPlaceAndRun();
    fireEvent.click(await screen.findByText(/View technical evidence/i));
    fireEvent.click(await screen.findByRole("button", { name: /Copy for Title/i }));
    expect(
      await screen.findByText("Copy failed — select the message and copy"),
    ).toBeInTheDocument();
  });

  it("clears a previous brief when a later run fails", async () => {
    renderDemo();
    fillPlaceAndRun();
    expect(
      await screen.findByRole("heading", {
        name: /Cattle operating case is conditional on the next cheap diligence step/i,
      }),
    ).toBeInTheDocument();
    mockFetch(FAILED_RUN);
    fireEvent.click(screen.getByRole("button", { name: /Run again/i }));
    const outcome = await screen.findByTestId("investigation-outcome");
    expect(outcome).toHaveAttribute("data-outcome", "INVESTIGATION_COULD_NOT_COMPLETE");
    expect(screen.getByRole("button", { name: /Edit location/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Try verified Nambe demo/i })).toBeInTheDocument();
    expect(screen.getByText(/timed out/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Current cattle operating view/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Generate buyer explanation/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByText(/Technical details/i));
    expect(within(outcome).getByText("GATHER_EVIDENCE")).toBeInTheDocument();
    expect(within(outcome).getByText(/error_class=TIMEOUT/)).toBeInTheDocument();
  });

  it("shows limited investigation without cattle operating view", async () => {
    mockFetch(INCOMPLETE_RUN);
    renderDemo();
    fillPlaceAndRun();
    const outcome = await screen.findByTestId("investigation-outcome");
    expect(outcome).toHaveAttribute("data-outcome", "EVIDENCE_INVESTIGATION_INCOMPLETE");
    expect(screen.getByRole("button", { name: /Review resolved location/i })).toBeInTheDocument();
    expect(
      within(outcome).getByText(/not the same as a confirmed parcel/i),
    ).toBeInTheDocument();
    expect(within(outcome).getByText(/Parcel boundary not confirmed/i)).toBeInTheDocument();
    expect(screen.getByTestId("limited-location")).toBeInTheDocument();
    expect(screen.queryByText(/Current cattle operating view/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Generate buyer explanation/i })).not.toBeInTheDocument();
    expect(screen.getByText(/No cattle operating Snapshot was generated/i)).toBeInTheDocument();
  });

  it("asks the user to confirm parcel when resolve is ambiguous", async () => {
    mockFetch(NEEDS_CONFIRMATION_RUN);
    renderDemo();
    fillPlaceAndRun();
    const outcome = await screen.findByTestId("investigation-outcome");
    expect(outcome).toHaveAttribute("data-outcome", "PARCEL_NEEDS_CONFIRMATION");
    expect(screen.getByRole("button", { name: /Confirm parcel/i })).toBeInTheDocument();
    expect(screen.getByText(/West tract/i)).toBeInTheDocument();
    expect(screen.getByText(/East tract/i)).toBeInTheDocument();
    expect(screen.queryByText("Full report today: CPER demo only")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Generate buyer explanation/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/Current cattle operating view/i)).not.toBeInTheDocument();
  });

  it("confirms the selected parcel then re-runs Advisor with the resolution id", async () => {
    const fetchMock = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const target = String(url);
      const method = (init?.method || "GET").toUpperCase();
      if (target.includes("/parcel-resolutions/") && target.endsWith("/confirm") && method === "POST") {
        return {
          ok: true,
          status: 200,
          json: async () => ({ status: "PARCEL_CONFIRMED" }),
        };
      }
      if (target === "/v1/advisor/runs" && method === "POST") {
        const body = JSON.parse(String(init?.body || "{}")) as {
          parcel_resolution_id?: string;
        };
        return {
          ok: true,
          status: 200,
          json: async () =>
            body.parcel_resolution_id ? SUCCESS_RUN : NEEDS_CONFIRMATION_RUN,
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => SUCCESS_RUN,
      };
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    renderDemo();
    fillPlaceAndRun();
    fireEvent.click(await screen.findByLabelText(/West tract/i));
    fireEvent.click(screen.getByRole("button", { name: /Confirm parcel/i }));
    expect(
      await screen.findByRole("heading", {
        name: /Cattle operating case is conditional on the next cheap diligence step/i,
      }),
    ).toBeInTheDocument();
    const confirmCall = fetchMock.mock.calls.find(([url, init]) =>
      String(url).includes("/parcel-resolutions/pr_advisor_test_confirm/confirm") &&
      String(init?.method || "").toUpperCase() === "POST",
    );
    expect(confirmCall).toBeTruthy();
    expect(JSON.parse(String(confirmCall?.[1]?.body))).toEqual({
      selected_candidate_id: "MIREYE-WEST",
      expected_geometry_hash: CONFIRM_HASH_WEST,
      explicit_confirmation: true,
    });
    const rerun = fetchMock.mock.calls.find(([url, init]) => {
      if (String(url) !== "/v1/advisor/runs") return false;
      if (String(init?.method || "").toUpperCase() !== "POST") return false;
      const body = JSON.parse(String(init?.body || "{}")) as {
        parcel_resolution_id?: string;
      };
      return body.parcel_resolution_id === "pr_advisor_test_confirm";
    });
    expect(rerun).toBeTruthy();
  });

  it("submits one answer and shows your answer / what changed / current view", async () => {
    const user = userEvent.setup();
    const revisedRun = {
      ...SUCCESS_RUN,
      deal_context: {
        context_version: 2,
        operation_type: "SEASONAL_GRAZING",
        geometry_hash: "a".repeat(64),
      },
      operating_conclusion: {
        ...SUCCESS_RUN.operating_conclusion,
        conclusion_id: "concl_demo_revised",
        headline: "Seasonal grazing reading is open, but livestock-water use is still unverified",
        primary_constraint:
          "Seasonal demand narrows the operating frame, but usable livestock water still controls travel.",
        deal_context_version: 2,
        next_question: {
          question_id: "Q_SELLER_WATER_CLAIM",
          prompt: "Is the seller claiming a developed year-round livestock-water system on this parcel?",
          allowed_field: "seller_water_claim",
          what_would_change_view_ref: "CHANGE_SELLER_WATER_CLAIM",
        },
      },
      revised_operating_conclusion: {
        conclusion_id: "concl_demo_revised",
        headline: "Seasonal grazing reading is open, but livestock-water use is still unverified",
        primary_constraint:
          "Seasonal demand narrows the operating frame, but usable livestock water still controls travel.",
        deal_context_version: 2,
        next_action: "Ask whether the seller claims a developed livestock-water system.",
        next_spend_class: "REMOTE_INFORMATION_REQUEST",
      },
      conclusion_change: {
        change_status: "CONCLUSION_CHANGED",
        summary: "The operating reading changed in headline, primary_constraint after incorporating the unverified user answer.",
        fields_changed: [
          { field: "headline", before: "old", after: "new" },
          { field: "primary_constraint", before: "old", after: "new" },
        ],
        user_answer: {
          question_id: "Q_OPERATION_TYPE",
          field: "operation_type",
          value: "SEASONAL_GRAZING",
          provenance: "USER_SUPPLIED_UNVERIFIED",
        },
      },
    };
    const fetchMock = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const target = String(url);
      const method = (init?.method || "GET").toUpperCase();
      if (target === "/v1/advisor/runs" && method === "POST") {
        return { ok: true, status: 200, json: async () => SUCCESS_RUN };
      }
      if (target.endsWith("/answers") && method === "POST") {
        return { ok: true, status: 200, json: async () => revisedRun };
      }
      return { ok: true, status: 200, json: async () => SUCCESS_RUN };
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    renderDemo();
    fillPlaceAndRun();
    await user.click(await screen.findByRole("button", { name: /Seasonal grazing/i }));
    expect(await screen.findByText(/What changed after your answer/i)).toBeInTheDocument();
    expect(screen.getByText("Seasonal grazing")).toBeInTheDocument();
    expect(screen.getByText("CONCLUSION CHANGED")).toBeInTheDocument();
    expect(
      screen.getAllByRole("heading", {
        name: /Seasonal grazing reading is open, but livestock-water use is still unverified/i,
      }).length,
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Updated operating view/i)).toBeInTheDocument();
    const update = screen.getByLabelText(/Conclusion update/i);
    expect(within(update).getByText("Your answer")).toBeInTheDocument();
    expect(within(update).getByText("What changed")).toBeInTheDocument();
    expect(within(update).getByText("Current view")).toBeInTheDocument();
    expect(within(update).getByText("Seasonal grazing")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/v1/advisor/runs/advisor_test_run_001/answers",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("SEASONAL_GRAZING"),
      }),
    );
  });

  it("keeps polling when investigation completes before the conclusion arrives", async () => {
    let polls = 0;
    const pending = {
      ...SUCCESS_RUN,
      status: "SUCCEEDED" as const,
      operating_conclusion: null,
      initial_operating_conclusion: null,
      chat_suggestions: [],
    };
    const ready = { ...SUCCESS_RUN };
    globalThis.fetch = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const target = String(url);
      const method = (init?.method || "GET").toUpperCase();
      if (target === "/v1/advisor/runs" && method === "POST") {
        return { ok: true, status: 200, json: async () => pending };
      }
      if (target === "/v1/advisor/runs/advisor_test_run_001" && method === "GET") {
        polls += 1;
        return {
          ok: true,
          status: 200,
          json: async () => (polls >= 2 ? ready : pending),
        };
      }
      return { ok: true, status: 200, json: async () => ready };
    }) as unknown as typeof fetch;

    renderDemo();
    fillPlaceAndRun();
    expect(
      await screen.findByRole("heading", {
        name: /Cattle operating case is conditional on the next cheap diligence step/i,
      }),
    ).toBeInTheDocument();
    expect(polls).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/Current cattle operating view/i)).toBeInTheDocument();
  });
});
