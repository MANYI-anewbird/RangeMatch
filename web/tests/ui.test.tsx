import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import goalInv from "../fixtures/goal_directed_investigation.json";
import goalReport from "../fixtures/goal_directed_report.json";
import goalTrace from "../fixtures/goal_directed_trace.json";
import goalBuyer from "../fixtures/goal_directed_buyer_report.json";
import discoveryInv from "../fixtures/discovery_investigation.json";
import discoveryReport from "../fixtures/discovery_report.json";
import discoveryTrace from "../fixtures/discovery_trace.json";
import discoveryBuyer from "../fixtures/discovery_buyer_report.json";
import failedBuyer from "../fixtures/buyer_report_failed.json";
import diligenceSearch from "../fixtures/diligence_search.json";
import {
  HASH_A,
  blockedLiveResolution,
  confirmedResolution,
  multiCandidateResolution,
  oneCandidateResolution,
} from "../fixtures/parcel_resolution_fixtures";
import { HOLD_COPY, analysisChoiceToApi } from "../src/api/client";
import { IntakePage } from "../src/pages/IntakePage";
import { InvestigationPage } from "../src/pages/InvestigationPage";

function jsonResponse(data: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(data),
  } as Response);
}

function mockInvestigationApis(opts: {
  inv: unknown;
  report: unknown;
  trace: unknown;
  buyer: unknown;
  buyerStatus?: number;
  search?: unknown;
  searchStatus?: number;
}) {
  vi.spyOn(globalThis, "fetch").mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/diligence-search")) {
      return jsonResponse(opts.search ?? diligenceSearch, opts.searchStatus ?? 200);
    }
    if (url.includes("/buyer-report")) {
      if ((init?.method || "GET").toUpperCase() === "POST") {
        return jsonResponse(opts.buyer, opts.buyerStatus ?? 200);
      }
      return jsonResponse(opts.buyer, opts.buyerStatus ?? 200);
    }
    if (url.includes("/report")) return jsonResponse(opts.report);
    if (url.includes("/trace")) return jsonResponse(opts.trace);
    return jsonResponse(opts.inv);
  });
}

describe("RangeMatch buyer UI", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("maps analysis choices to API modes", () => {
    expect(analysisChoiceToApi("GENERAL")).toEqual({
      mode: "DISCOVERY",
      intended_operation: null,
    });
    expect(analysisChoiceToApi("CATTLE")).toEqual({
      mode: "GOAL_DIRECTED",
      intended_operation: "COW_CALF_OPERATION",
    });
    expect(analysisChoiceToApi("SHEEP")).toEqual({
      mode: "GOAL_DIRECTED",
      intended_operation: "SHEEP_GRAZING",
    });
  });

  it("intake shows dual land entry and map layout", () => {
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: /select your land/i })).toBeInTheDocument();
    expect(screen.getByTestId("entry-address")).toBeInTheDocument();
    expect(screen.getByTestId("entry-coordinate")).toBeInTheDocument();
    expect(
      screen.getByText(/Real property search sends the address or coordinates to Mireye/i),
    ).toBeInTheDocument();
    expect(screen.getByTestId("intake-map-layout")).toBeInTheDocument();
    expect(screen.getByTestId("parcel-map")).toBeInTheDocument();
    expect(screen.getByTestId("start-analysis")).toBeDisabled();
    expect(screen.getByText(/No APN, boundary upload/i)).toBeInTheDocument();
    expect(screen.getByText(/minimized evidence summary—not API keys or raw source files/i)).toBeInTheDocument();
  });

  it("coordinate entry sends COORDINATE resolve body", async () => {
    const user = userEvent.setup();
    const bodies: unknown[] = [];
    const one = oneCandidateResolution();
    vi.spyOn(globalThis, "fetch").mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method || "GET").toUpperCase();
      if (url.includes("/v1/parcel-resolutions") && method === "POST" && !url.includes("/confirm")) {
        bodies.push(JSON.parse(String(init?.body || "{}")));
        return jsonResponse({
          ...one,
          input_kind: "COORDINATE",
          latitude: 40.495,
          longitude: -104.895,
        });
      }
      return jsonResponse({ detail: "unexpected" }, 500);
    });
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>,
    );
    await user.click(screen.getByTestId("entry-coordinate"));
    await user.click(screen.getByRole("button", { name: /Pin near demo ranch/i }));
    await user.click(screen.getByTestId("resolve-property"));
    expect(await screen.findByTestId("resolution-status")).toHaveTextContent(/confirm the boundary/i);
    expect(bodies[0]).toMatchObject({
      input_kind: "COORDINATE",
      latitude: 40.495,
      longitude: -104.895,
      resolver_mode: "FIXTURE",
      fixture_scenario_id: "coord_one_valid_candidate",
    });
    expect(bodies[0]).not.toHaveProperty("address");
  });

  it("requires explicit LIVE selection for custom coordinates and surfaces the reason", async () => {
    const user = userEvent.setup();
    const bodies: unknown[] = [];
    const one = oneCandidateResolution();
    vi.spyOn(globalThis, "fetch").mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method || "GET").toUpperCase();
      if (url.includes("/v1/parcel-resolutions") && method === "POST" && !url.includes("/confirm")) {
        bodies.push(JSON.parse(String(init?.body || "{}")));
        return jsonResponse({
          ...one,
          input_kind: "COORDINATE",
          latitude: 40.340917,
          longitude: -105.109158,
        });
      }
      return jsonResponse({ detail: "unexpected" }, 500);
    });

    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>,
    );
    await user.click(screen.getByTestId("entry-coordinate"));
    await user.clear(screen.getByTestId("coord-text"));
    await user.type(screen.getByTestId("coord-text"), "40.340917,-105.109158");
    await user.click(screen.getByTestId("resolve-property"));

    expect(bodies).toHaveLength(0);
    expect(screen.getByTestId("resolution-status")).toHaveTextContent(
      /Custom input cannot use demo data\. Select LIVE/i,
    );

    await user.click(screen.getByRole("button", { name: /Search a real property/i }));
    await user.click(screen.getByTestId("resolve-property"));
    expect(await screen.findByTestId("resolution-status")).toHaveTextContent(/confirm the boundary/i);
    expect(bodies[0]).toMatchObject({
      input_kind: "COORDINATE",
      latitude: 40.340917,
      longitude: -105.109158,
      resolver_mode: "LIVE",
      allow_network: true,
    });
    expect(bodies[0]).not.toHaveProperty("fixture_scenario_id");
  });

  it("resolves one candidate and keeps Start Analysis disabled until confirm", async () => {
    const user = userEvent.setup();
    const one = oneCandidateResolution();
    vi.spyOn(globalThis, "fetch").mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method || "GET").toUpperCase();
      if (url.includes("/v1/parcel-resolutions") && method === "POST" && !url.includes("/confirm")) {
        return jsonResponse(one);
      }
      return jsonResponse({ detail: "unexpected" }, 500);
    });
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>,
    );
    await user.click(screen.getByTestId("resolve-property"));
    expect(await screen.findByTestId("resolution-status")).toHaveTextContent(/confirm the boundary/i);
    expect(screen.getByTestId("start-analysis")).toBeDisabled();
    expect(screen.getByTestId("confirm-parcel")).toBeEnabled();
  });

  it("multiple candidates require selection before confirm", async () => {
    const user = userEvent.setup();
    const multi = multiCandidateResolution();
    vi.spyOn(globalThis, "fetch").mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method || "GET").toUpperCase();
      if (url.includes("/v1/parcel-resolutions") && method === "POST" && !url.includes("/confirm")) {
        return jsonResponse(multi);
      }
      return jsonResponse({ detail: "unexpected" }, 500);
    });
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>,
    );
    await user.click(screen.getByRole("button", { name: /Multiple candidates/i }));
    await user.click(screen.getByTestId("resolve-property"));
    expect(await screen.findByTestId("candidate-list")).toBeInTheDocument();
    expect(screen.getByTestId("confirm-parcel")).toBeDisabled();
    await user.click(screen.getByTestId("candidate-cand_demo_B"));
    expect(screen.getByTestId("confirm-parcel")).toBeEnabled();
    expect(screen.getByTestId("candidate-cand_demo_B")).toHaveAttribute("aria-pressed", "true");
  });

  it("map candidate click updates selection", async () => {
    const user = userEvent.setup();
    const multi = multiCandidateResolution();
    vi.spyOn(globalThis, "fetch").mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method || "GET").toUpperCase();
      if (url.includes("/v1/parcel-resolutions") && method === "POST" && !url.includes("/confirm")) {
        return jsonResponse(multi);
      }
      return jsonResponse({ detail: "unexpected" }, 500);
    });
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>,
    );
    await user.click(screen.getByRole("button", { name: /Multiple candidates/i }));
    await user.click(screen.getByTestId("resolve-property"));
    await screen.findByTestId("map-candidate-cand_demo_B");
    await user.click(screen.getByTestId("map-candidate-cand_demo_B"));
    expect(screen.getByTestId("candidate-cand_demo_B")).toHaveAttribute("aria-pressed", "true");
  });

  it("confirmation enables Start Analysis and passes parcel_resolution_id", async () => {
    const user = userEvent.setup();
    const one = oneCandidateResolution();
    const confirmed = confirmedResolution(one);
    const createBodies: unknown[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method || "GET").toUpperCase();
      if (url.includes("/confirm") && method === "POST") return jsonResponse(confirmed);
      if (url.includes("/v1/parcel-resolutions") && method === "POST") return jsonResponse(one);
      if (url.includes("/v1/investigations") && method === "POST") {
        createBodies.push(JSON.parse(String(init?.body || "{}")));
        return jsonResponse({
          investigation_id: "inv_from_resolution",
          status: "QUEUED",
          mode: "GOAL_DIRECTED",
          intended_operation: "COW_CALF_OPERATION",
          execution_source: "PARCEL_RESOLUTION",
          parcel_resolution_id: confirmed.resolution_id,
          geometry_hash: HASH_A,
          unified_output: null,
          limitations: ["investigation_job_queued", "no_automatic_cper_fixture_substitution"],
        });
      }
      return jsonResponse({ detail: "unexpected" }, 500);
    });
    render(
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<IntakePage />} />
          <Route path="/investigations/:id" element={<div data-testid="nav-ok">navigated</div>} />
        </Routes>
      </MemoryRouter>,
    );
    await user.click(screen.getByTestId("resolve-property"));
    await screen.findByTestId("confirm-parcel");
    await user.click(screen.getByTestId("confirm-parcel"));
    await waitFor(() => expect(screen.getByTestId("start-analysis")).toBeEnabled());
    await user.click(screen.getByTestId("mode-sheep"));
    await user.click(screen.getByTestId("start-analysis"));
    await screen.findByTestId("nav-ok");
    expect(createBodies[0]).toMatchObject({
      parcel_resolution_id: "pres_one_demo",
      execution_source: "PARCEL_RESOLUTION",
      mode: "GOAL_DIRECTED",
      intended_operation: "SHEEP_GRAZING",
    });
    expect(createBodies[0]).not.toHaveProperty("address");
    expect(createBodies[0]).not.toHaveProperty("parcel_geometry");
  });

  it("LIVE confirmation starts the network-backed F01-F08 investigation", async () => {
    const user = userEvent.setup();
    const one = oneCandidateResolution();
    const confirmed = confirmedResolution(one);
    const bodies: Record<string, unknown>[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method || "GET").toUpperCase();
      if (url.includes("/confirm") && method === "POST") return jsonResponse(confirmed);
      if (url.includes("/v1/parcel-resolutions") && method === "POST") return jsonResponse(one);
      if (url.includes("/v1/investigations") && method === "POST") {
        bodies.push(JSON.parse(String(init?.body || "{}")));
        return jsonResponse({
          investigation_id: "inv_live",
          status: "QUEUED",
          mode: "GOAL_DIRECTED",
          intended_operation: "COW_CALF_OPERATION",
          execution_source: "PARCEL_RESOLUTION",
          unified_output: null,
        });
      }
      return jsonResponse({ detail: "unexpected" }, 500);
    });
    render(
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<IntakePage />} />
          <Route path="/investigations/:id" element={<div data-testid="live-nav-ok">navigated</div>} />
        </Routes>
      </MemoryRouter>,
    );
    await user.click(screen.getByRole("button", { name: /Search a real property/i }));
    await user.click(screen.getByTestId("resolve-property"));
    await user.click(await screen.findByTestId("confirm-parcel"));
    await waitFor(() => expect(screen.getByTestId("start-analysis")).toBeEnabled());
    await user.click(screen.getByTestId("start-analysis"));
    await screen.findByTestId("live-nav-ok");
    expect(bodies[0]).toMatchObject({
      mireye_mode: "LIVE",
      allow_network: true,
      parcel_resolution_id: confirmed.resolution_id,
    });
  });

  it("geometry/hash change via new candidate clears confirmation", async () => {
    const user = userEvent.setup();
    const multi = multiCandidateResolution();
    const confirmed = confirmedResolution({
      ...multi,
      status: "NEEDS_USER_SELECTION",
      candidates: multi.candidates,
    });
    // Force confirmed state then switch candidate
    let phase: "resolve" | "confirm" = "resolve";
    vi.spyOn(globalThis, "fetch").mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method || "GET").toUpperCase();
      if (url.includes("/confirm") && method === "POST") {
        phase = "confirm";
        return jsonResponse({
          ...confirmed,
          status: "PARCEL_CONFIRMED",
          candidates: multi.candidates,
        });
      }
      if (url.includes("/v1/parcel-resolutions") && method === "POST") {
        return jsonResponse(multi);
      }
      return jsonResponse({ detail: "unexpected" }, 500);
    });
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>,
    );
    await user.click(screen.getByRole("button", { name: /Multiple candidates/i }));
    await user.click(screen.getByTestId("resolve-property"));
    await user.click(screen.getByTestId("candidate-cand_demo_001"));
    await user.click(screen.getByTestId("confirm-parcel"));
    await waitFor(() => expect(screen.getByTestId("start-analysis")).toBeEnabled());
    expect(phase).toBe("confirm");
    // Switching candidate clears confirmation lock
    await user.click(screen.getByTestId("candidate-cand_demo_B"));
    expect(screen.getByTestId("start-analysis")).toBeDisabled();
  });

  it("LIVE blocked state stays visible without fixture substitution", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method || "GET").toUpperCase();
      if (url.includes("/v1/parcel-resolutions") && method === "POST") {
        const body = JSON.parse(String(init?.body || "{}"));
        expect(body.resolver_mode).toBe("LIVE");
        expect(body.allow_network).toBe(true);
        expect(body.fixture_scenario_id).toBeFalsy();
        return jsonResponse(blockedLiveResolution);
      }
      return jsonResponse({ detail: "unexpected" }, 500);
    });
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>,
    );
    await user.click(screen.getByRole("button", { name: /Search a real property/i }));
    await user.clear(screen.getByLabelText(/Full U\.S\. street address/i));
    await user.type(screen.getByLabelText(/Full U\.S\. street address/i), "123 Main St, Denver, CO 80202");
    await user.click(screen.getByTestId("resolve-property"));
    expect(await screen.findByTestId("resolution-status")).toHaveTextContent(/blocked/i);
    expect(screen.getByText(/CPER\/demo fixtures were not substituted/i)).toBeInTheDocument();
    expect(screen.getByTestId("start-analysis")).toBeDisabled();
    expect(screen.queryByText(/engineering_test_geometry_cper/i)).not.toBeInTheDocument();
  });

  it("mobile layout landmarks present on intake", () => {
    const { container } = render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>,
    );
    expect(container.querySelector(".intake-map-layout")).toBeTruthy();
    expect(container.querySelector(".intake-controls")).toBeTruthy();
    expect(container.querySelector(".intake-map-panel")).toBeTruthy();
    expect(container.querySelector(".parcel-map-canvas")).toBeTruthy();
  });

  it("intake has no F09/batch controls", () => {
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>,
    );
    expect(screen.queryByRole("button", { name: /batch/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /f09/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /icp/i })).not.toBeInTheDocument();
  });

  it("polls investigation progress until terminal then loads buyer report", async () => {
    let polls = 0;
    const pendingTrace = {
      execution_status: "QUEUED",
      steps: [
        { step_id: "s1", tool_id: "geometry.resolve", status: "PENDING" },
        { step_id: "s2", tool_id: "adapter.usgs_3dep", status: "PENDING" },
      ],
    };
    const runningTrace = {
      execution_status: "RUNNING",
      steps: [
        { step_id: "s1", tool_id: "geometry.resolve", status: "SUCCEEDED" },
        { step_id: "s2", tool_id: "adapter.usgs_3dep", status: "RUNNING" },
      ],
    };
    vi.spyOn(globalThis, "fetch").mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method || "GET").toUpperCase();
      if (url.includes("/buyer-report") && method === "POST") {
        return jsonResponse(goalBuyer);
      }
      if (url.includes("/report")) return jsonResponse(goalReport);
      if (url.includes("/trace")) {
        if (polls < 2) return jsonResponse(pendingTrace);
        if (polls === 2) return jsonResponse(runningTrace);
        return jsonResponse(goalTrace);
      }
      if (url.includes("/investigations/")) {
        polls += 1;
        if (polls < 3) {
          return jsonResponse({
            ...goalInv,
            status: polls === 1 ? "QUEUED" : "RUNNING",
            unified_output: null,
          });
        }
        return jsonResponse(goalInv);
      }
      return jsonResponse({ detail: "unexpected" }, 500);
    });
    render(
      <MemoryRouter initialEntries={[`/investigations/${goalInv.investigation_id}`]}>
        <Routes>
          <Route path="/investigations/:id" element={<InvestigationPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByTestId("investigation-progress")).toBeInTheDocument();
    expect(screen.getByText(/land investigation is underway/i)).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: /investigation progress/i })).toBeInTheDocument();
    expect(screen.getByText("Land Evidence Agents")).toBeInTheDocument();
    expect(await screen.findByTestId("buyer-narrative", {}, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.queryByTestId("investigation-progress")).not.toBeInTheDocument();
  });

  it("renders validated buyer narrative as default view", async () => {
    mockInvestigationApis({
      inv: goalInv,
      report: goalReport,
      trace: goalTrace,
      buyer: goalBuyer,
    });
    render(
      <MemoryRouter initialEntries={[`/investigations/${goalInv.investigation_id}`]}>
        <Routes>
          <Route path="/investigations/:id" element={<InvestigationPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByTestId("buyer-narrative")).toBeInTheDocument();
    expect(screen.getByTestId("buyer-narrative")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Executive Summary" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Key Unknowns" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Current rules & local guidance" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Drought conditions and outlook/i })).toHaveAttribute(
      "href",
      "https://www.drought.gov/",
    );
    expect(screen.getByText(/does not change land facts or operation-fit decisions/i)).toBeInTheDocument();
    for (const title of [
      "What we found on this parcel",
      "Cow-Calf vs. Sheep",
      "Diligence Plan",
    ]) {
      expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
    }
    expect(screen.getAllByText(HOLD_COPY).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/selected/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Deterministic fallback report/i)).not.toBeInTheDocument();
    const unknowns = screen.getByRole("heading", { name: "Key Unknowns" }).closest("section");
    expect(unknowns).toBeTruthy();
    expect(
      within(unknowns as HTMLElement).getAllByText(/herbaceous|F02|water|F03|legal access|F07|woody|F08/i)
        .length,
    ).toBeGreaterThan(0);
  });

  it("never renders invalid buyer narrative body", async () => {
    const invalid = {
      ...failedBuyer,
      validation_status: "FAILED",
      displayable: false,
      buyer_report: {
        executive_summary: {
          heading: "SHOULD_NOT_RENDER",
          summary: "illegal narrative",
          findings: ["This invalid narrative must not appear"],
          evidence_refs: [],
          limitation_refs: [],
        },
      },
    };
    mockInvestigationApis({
      inv: goalInv,
      report: goalReport,
      trace: goalTrace,
      buyer: invalid,
    });
    render(
      <MemoryRouter initialEntries={[`/investigations/${goalInv.investigation_id}`]}>
        <Routes>
          <Route path="/investigations/:id" element={<InvestigationPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByTestId("deterministic-fallback")).toBeInTheDocument();
    expect(screen.queryByText(/This invalid narrative must not appear/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/SHOULD_NOT_RENDER/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Deterministic fallback report/i)).not.toBeInTheDocument();
  });

  it("falls back when buyer-report is NOT_CONFIGURED / failed", async () => {
    mockInvestigationApis({
      inv: goalInv,
      report: goalReport,
      trace: goalTrace,
      buyer: failedBuyer,
    });
    render(
      <MemoryRouter initialEntries={[`/investigations/${goalInv.investigation_id}`]}>
        <Routes>
          <Route path="/investigations/:id" element={<InvestigationPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByTestId("deterministic-fallback")).toBeInTheDocument();
    expect(screen.queryByText(/Deterministic fallback report/i)).not.toBeInTheDocument();
    expect(screen.getAllByText(HOLD_COPY).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Property" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Key Unknowns" })).toBeInTheDocument();
  });

  it("buyer appendix uses understandable land-check labels", async () => {
    const user = userEvent.setup();
    mockInvestigationApis({
      inv: goalInv,
      report: goalReport,
      trace: goalTrace,
      buyer: goalBuyer,
    });
    render(
      <MemoryRouter initialEntries={[`/investigations/${goalInv.investigation_id}`]}>
        <Routes>
          <Route path="/investigations/:id" element={<InvestigationPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByTestId("buyer-narrative")).toBeInTheDocument();
    await user.click(screen.getByText(/Data sources and methodology/i));
    expect(screen.getByLabelText(/Land checks and data sources/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Terrain and slope/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Trees and shrubs/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/match_result_hash/i)).not.toBeInTheDocument();
  });

  it("Discovery keeps Cow-Calf and Sheep as peers", async () => {
    mockInvestigationApis({
      inv: discoveryInv,
      report: discoveryReport,
      trace: discoveryTrace,
      buyer: discoveryBuyer,
    });
    render(
      <MemoryRouter initialEntries={[`/investigations/${discoveryInv.investigation_id}`]}>
        <Routes>
          <Route path="/investigations/:id" element={<InvestigationPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findAllByText(/peers/i)).toBeTruthy();
    expect(screen.getAllByText(/No winner or fit score is claimed/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/ · selected/i)).not.toBeInTheDocument();
  });

  it("Goal-directed marks selected operation", async () => {
    mockInvestigationApis({
      inv: goalInv,
      report: goalReport,
      trace: goalTrace,
      buyer: goalBuyer,
    });
    render(
      <MemoryRouter initialEntries={[`/investigations/${goalInv.investigation_id}`]}>
        <Routes>
          <Route path="/investigations/:id" element={<InvestigationPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText(/ · selected/i)).toBeInTheDocument();
    expect(screen.getByText(/Selected profile presented first/i)).toBeInTheDocument();
  });

  it("shows blocked address investigation honestly", async () => {
    const blocked = {
      investigation_id: "inv_blocked",
      status: "BLOCKED_EXTERNAL",
      mode: "GOAL_DIRECTED",
      intended_operation: "COW_CALF_OPERATION",
      execution_source: "DEMO_FIXTURE",
      unified_output: null,
      limitations: [
        "no_automatic_fixture_substitution",
        "no_fabricated_geometry",
        "BLOCKED_EXTERNAL",
      ],
    };
    vi.spyOn(globalThis, "fetch").mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/trace"))
        return jsonResponse({ steps: [], note: "no_execution_trace_for_blocked_investigation" });
      return jsonResponse(blocked);
    });
    render(
      <MemoryRouter initialEntries={["/investigations/inv_blocked"]}>
        <Routes>
          <Route path="/investigations/:id" element={<InvestigationPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText(/Investigation blocked/i)).toBeInTheDocument();
    expect(screen.getByText(/no fabricated geometry/i)).toBeInTheDocument();
  });

  it("responsive smoke: intake and result landmarks", async () => {
    const { container } = render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>,
    );
    expect(container.querySelector(".app-shell")).toBeTruthy();
    expect(container.querySelector(".intake-map-layout")).toBeTruthy();
    expect(screen.getByRole("form", { name: /investigation intake/i })).toBeInTheDocument();

    mockInvestigationApis({
      inv: goalInv,
      report: goalReport,
      trace: goalTrace,
      buyer: goalBuyer,
    });
    const result = render(
      <MemoryRouter initialEntries={[`/investigations/${goalInv.investigation_id}`]}>
        <Routes>
          <Route path="/investigations/:id" element={<InvestigationPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByTestId("buyer-narrative")).toBeInTheDocument();
    expect(result.container.querySelector(".app-shell")).toBeTruthy();
    expect(result.container.querySelector(".operation-matrix")).toBeTruthy();
  });
});
