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
  llm_used: false,
  failed_step: null,
  error: null,
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
    expect(screen.getByRole("button", { name: /Run investigation/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Place/i)).toBeInTheDocument();
    expect(screen.getByText("Accept place")).toBeInTheDocument();
    expect(screen.getByText("Call Mireye")).toBeInTheDocument();
    expect(screen.getByText("Build agenda")).toBeInTheDocument();
    expect(screen.getByText("Run agenda")).toBeInTheDocument();
    expect(screen.getByText(/called live on this Demo/i)).toBeInTheDocument();
    expect(screen.getByText("Validate brief")).toBeInTheDocument();
    expect(screen.getByText(/No brief yet/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "What RangeMatch noticed" })).not.toBeInTheDocument();
    expect(
      screen.getByText(
        /Built for buyer-side ranch brokers and land advisors deciding what to verify before their client travels or spends/i,
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/\bHOLD\b/)).not.toBeInTheDocument();
  });

  it("renders this-run identity after a successful agent run", async () => {
    renderDemo();
    fireEvent.click(screen.getByRole("button", { name: /Run investigation/i }));
    expect(await screen.findByRole("heading", { name: "What RangeMatch noticed" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Do not send the client yet" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "What you can do now" })).toBeInTheDocument();
    expect(screen.getByText("Visit depends on access paper")).toBeInTheDocument();
    expect(screen.getByText(/advisor_test_run_001/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Generate buyer explanation \(LIVE LLM\)/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Buyer explanation provider/i)).toHaveValue("OPENAI");
    expect(screen.getByText(/Buyer explanation: LIVE LLM/i)).toBeInTheDocument();
    expect(screen.getByText(/Do not send the client yet/i)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(brief.packet_hash.slice(0, 12)))).toBeInTheDocument();
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/v1/advisor/runs",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("Central Plains Experimental Range Demo"),
      }),
    );
  });

  it("posts OPENAI by default for buyer explanation and can switch to fixture", async () => {
    const user = userEvent.setup();
    renderDemo();
    fireEvent.click(screen.getByRole("button", { name: /Run investigation/i }));
    expect(await screen.findByRole("button", { name: /Generate buyer explanation \(LIVE LLM\)/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Generate buyer explanation \(LIVE LLM\)/i }));
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/v1/advisor/runs/advisor_test_run_001/buyer-explanation",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ provider: "OPENAI" }),
      }),
    );
    await user.selectOptions(screen.getByLabelText(/Buyer explanation provider/i), "FIXTURE");
    expect(screen.getByRole("button", { name: /Generate buyer explanation \(fixture\)/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Generate buyer explanation \(fixture\)/i }));
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/v1/advisor/runs/advisor_test_run_001/buyer-explanation",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ provider: "FIXTURE" }),
      }),
    );
  });

  it("copies title, listing, and partner messages from the run result", async () => {
    renderDemo();
    fireEvent.click(screen.getByRole("button", { name: /Run investigation/i }));
    expect(await screen.findByRole("button", { name: /Copy for Title/i })).toBeInTheDocument();
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
    fireEvent.click(screen.getByRole("button", { name: /Run investigation/i }));
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
    fireEvent.click(screen.getByRole("button", { name: /Run investigation/i }));
    fireEvent.click(await screen.findByRole("button", { name: /Copy for Title/i }));
    expect(
      await screen.findByText("Copy failed — select the message and copy"),
    ).toBeInTheDocument();
  });

  it("clears a previous brief when a later run fails", async () => {
    renderDemo();
    fireEvent.click(screen.getByRole("button", { name: /Run investigation/i }));
    expect(await screen.findByRole("heading", { name: "What RangeMatch noticed" })).toBeInTheDocument();
    mockFetch(FAILED_RUN);
    fireEvent.click(screen.getByRole("button", { name: /Run again/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/GATHER_EVIDENCE failed/i);
    expect(screen.queryByRole("heading", { name: "What RangeMatch noticed" })).not.toBeInTheDocument();
    expect(screen.queryByText(/advisor_test_run_001/)).not.toBeInTheDocument();
  });

  it("keeps kitchen collapsed and separates 3 drawable from 6 inventory identities", async () => {
    const user = userEvent.setup();
    renderDemo();
    fireEvent.click(screen.getByRole("button", { name: /Run investigation/i }));
    expect(await screen.findByText(/Evidence kitchen/i)).toBeInTheDocument();
    const kitchen = screen.getByText(/Evidence kitchen/i).closest("details");
    expect(kitchen).toBeTruthy();
    expect(kitchen).not.toHaveAttribute("open");
    await user.click(screen.getByText(/Evidence kitchen/i));
    expect(kitchen).toHaveAttribute("open");
    expect(screen.getByRole("heading", { name: /Review on the map \(3\)/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Catalog only \(6\)/ })).toBeInTheDocument();
    const appendix = screen.getByRole("heading", { name: "Engine appendix" }).closest("section");
    expect(appendix).toBeTruthy();
    expect(
      within(appendix as HTMLElement).getByText(/Engine decision labels stay confined/i),
    ).toBeInTheDocument();
  });
});
