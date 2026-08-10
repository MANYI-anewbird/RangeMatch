import { FormEvent, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  DEMO_COORD_PRESET,
  DEMO_RESOLVER_PRESETS,
  analysisChoiceToApi,
  api,
  type AnalysisChoice,
  type LandInputKind,
  type ParcelResolution,
  type ResolverMode,
} from "../api/client";
import { AppShell, Badge } from "../components/AppShell";
import { ParcelMap } from "../components/ParcelMap";

function statusMessage(status: string | undefined): string {
  switch (status) {
    case "NEEDS_BOUNDARY_CONFIRMATION":
      return "One candidate ready — confirm the boundary before analysis.";
    case "NEEDS_USER_SELECTION":
      return "Multiple candidates — select one parcel on the map or list.";
    case "PARCEL_CONFIRMED":
      return "Parcel boundary confirmed. Choose an analysis mode and start.";
    case "NO_MATCH":
      return "No parcel candidates matched this input.";
    case "AMBIGUOUS":
      return "Address or parcel match is ambiguous.";
    case "BLOCKED_EXTERNAL":
      return "External parcel/geocode provider blocked or not configured.";
    case "INVALID_GEOMETRY":
      return "Candidate geometry failed validation (not a usable parcel boundary).";
    case "PARCEL_DATA_UNAVAILABLE":
      return "Location resolved, but parcel boundary data is unavailable from the provider.";
    case "GEOCODE_QUALITY_INSUFFICIENT":
      return "Address geocode is not parcel-quality — switch to Drop a pin / Enter coordinates.";
    default:
      return status
        ? `Resolution status: ${status}`
        : "Select your land by address or map coordinates.";
  }
}

export function IntakePage() {
  const navigate = useNavigate();
  const [inputKind, setInputKind] = useState<LandInputKind>("ADDRESS");
  const [address, setAddress] = useState<string>(DEMO_RESOLVER_PRESETS[0].address);
  const [latitude, setLatitude] = useState<string>(String(DEMO_COORD_PRESET.latitude));
  const [longitude, setLongitude] = useState<string>(String(DEMO_COORD_PRESET.longitude));
  const [coordText, setCoordText] = useState(
    `${DEMO_COORD_PRESET.latitude},${DEMO_COORD_PRESET.longitude}`,
  );
  const [resolverMode, setResolverMode] = useState<ResolverMode>("FIXTURE");
  const [fixtureScenarioId, setFixtureScenarioId] = useState<string | null>(
    DEMO_RESOLVER_PRESETS[0].fixture_scenario_id,
  );
  const [analysisChoice, setAnalysisChoice] = useState<AnalysisChoice>("CATTLE");
  const [resolution, setResolution] = useState<ParcelResolution | null>(null);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [confirmedHash, setConfirmedHash] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resolverNotice, setResolverNotice] = useState<string | null>(null);
  const [busyResolve, setBusyResolve] = useState(false);
  const [busyStart, setBusyStart] = useState(false);
  const [apiDown, setApiDown] = useState(false);
  const busy = busyResolve || busyStart;

  const confirmed = resolution?.status === "PARCEL_CONFIRMED";
  const candidates = resolution?.candidates || [];
  const selected = candidates.find((c) => c.candidate_id === selectedCandidateId) || null;
  const selectedHash = selected?.geometry_hash || null;

  const queryPin = useMemo(() => {
    if (inputKind !== "COORDINATE") return null;
    const lat = Number(latitude);
    const lng = Number(longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
    return { latitude: lat, longitude: lng };
  }, [inputKind, latitude, longitude]);

  const canResolve = useMemo(() => {
    if (busyResolve) return false;
    if (inputKind === "ADDRESS") return Boolean(address.trim());
    return Number.isFinite(Number(latitude)) && Number.isFinite(Number(longitude));
  }, [busyResolve, inputKind, address, latitude, longitude]);

  const canConfirm = Boolean(
    resolution &&
      selectedCandidateId &&
      selectedHash &&
      !confirmed &&
      (resolution.status === "NEEDS_BOUNDARY_CONFIRMATION" ||
        resolution.status === "NEEDS_USER_SELECTION" ||
        resolution.status === "PARCEL_CANDIDATES_FOUND") &&
      selected?.validation_status !== "INVALID",
  );

  const canStart = confirmed && Boolean(resolution?.resolution_id) && !busy;

  const statusBanner = useMemo(() => {
    if (apiDown) return "API unavailable — cannot resolve parcels.";
    if (error && error.includes("STALE_GEOMETRY_HASH"))
      return "Stale geometry hash — re-select and confirm the current boundary.";
    if (error && error.includes("COORDINATES_APPEAR_SWAPPED"))
      return "Coordinates look swapped — enter latitude first (lat,lng).";
    if (error && error.includes("COORDINATES_OUTSIDE_US"))
      return "Point is outside the U.S. envelope — adjust the pin.";
    if (error) return `Parcel lookup failed: ${error}`;
    if (!resolution && resolverNotice) return resolverNotice;
    return statusMessage(resolution?.status);
  }, [apiDown, error, resolution?.status, resolverNotice]);

  function clearConfirmationState() {
    setConfirmedHash(null);
    if (resolution?.status === "PARCEL_CONFIRMED") {
      setResolution({
        ...resolution,
        status:
          (resolution.candidates?.length || 0) > 1
            ? "NEEDS_USER_SELECTION"
            : "NEEDS_BOUNDARY_CONFIRMATION",
        confirmed_parcel: null,
        confirmation_status: {
          ...(resolution.confirmation_status || {}),
          confirmed: false,
          confirmed_at: null,
          confirmation_method: "PENDING",
        },
        selection: {
          selected_candidate_id: selectedCandidateId,
          confirmed_at: null,
          confirmation_method: "PENDING",
        },
      });
    }
  }

  function onSelectCandidate(id: string) {
    if (confirmed && id !== selectedCandidateId) {
      setSelectedCandidateId(id);
      setConfirmedHash(null);
      clearConfirmationState();
      return;
    }
    if (confirmed) return;
    if (selectedCandidateId && selectedCandidateId !== id) {
      setConfirmedHash(null);
    }
    setSelectedCandidateId(id);
  }

  function applyAddressPreset(preset: (typeof DEMO_RESOLVER_PRESETS)[number]) {
    setInputKind("ADDRESS");
    setAddress(preset.address);
    setFixtureScenarioId(preset.fixture_scenario_id);
    setResolverMode("FIXTURE");
    setResolution(null);
    setSelectedCandidateId(null);
    setConfirmedHash(null);
    setError(null);
    setApiDown(false);
    setResolverNotice(null);
  }

  function applyCoordPreset() {
    setInputKind("COORDINATE");
    setLatitude(String(DEMO_COORD_PRESET.latitude));
    setLongitude(String(DEMO_COORD_PRESET.longitude));
    setCoordText(`${DEMO_COORD_PRESET.latitude},${DEMO_COORD_PRESET.longitude}`);
    setFixtureScenarioId(DEMO_COORD_PRESET.fixture_scenario_id);
    setResolverMode("FIXTURE");
    setResolution(null);
    setSelectedCandidateId(null);
    setConfirmedHash(null);
    setError(null);
    setApiDown(false);
    setResolverNotice(null);
  }

  function onDropPin(lat: number, lng: number) {
    setInputKind("COORDINATE");
    setLatitude(lat.toFixed(6));
    setLongitude(lng.toFixed(6));
    setCoordText(`${lat.toFixed(6)},${lng.toFixed(6)}`);
    if (resolverMode === "FIXTURE") {
      const nearDemo =
        Math.abs(lat - DEMO_COORD_PRESET.latitude) < 1e-3 &&
        Math.abs(lng - DEMO_COORD_PRESET.longitude) < 1e-3;
      setFixtureScenarioId(nearDemo ? DEMO_COORD_PRESET.fixture_scenario_id : null);
      setResolverNotice(
        nearDemo
          ? null
          : "Custom coordinates cannot use demo data. Select LIVE to send this point to the parcel lookup service.",
      );
    }
    setResolution(null);
    setSelectedCandidateId(null);
    setConfirmedHash(null);
  }

  function syncCoordsFromText(text: string) {
    setCoordText(text);
    const parts = text.split(",").map((p) => p.trim());
    if (parts.length === 2) {
      setLatitude(parts[0]);
      setLongitude(parts[1]);
      if (resolverMode === "FIXTURE") {
        const lat = Number(parts[0]);
        const lng = Number(parts[1]);
        const nearDemo =
          Number.isFinite(lat) &&
          Number.isFinite(lng) &&
          Math.abs(lat - DEMO_COORD_PRESET.latitude) < 1e-3 &&
          Math.abs(lng - DEMO_COORD_PRESET.longitude) < 1e-3;
        setFixtureScenarioId(nearDemo ? DEMO_COORD_PRESET.fixture_scenario_id : null);
        setResolverNotice(
          nearDemo
            ? null
            : "Custom coordinates cannot use demo data. Select LIVE to send this point to the parcel lookup service.",
        );
      }
    }
  }

  async function onResolve() {
    setError(null);
    setApiDown(false);
    setBusyResolve(true);
    setResolution(null);
    setSelectedCandidateId(null);
    setConfirmedHash(null);
    if (resolverMode === "FIXTURE" && !fixtureScenarioId) {
      setResolverNotice(
        "Custom input cannot use demo data. Select LIVE, then resolve the property.",
      );
      setBusyResolve(false);
      return;
    }
    try {
      const body =
        inputKind === "ADDRESS"
          ? {
              input_kind: "ADDRESS" as const,
              address: address.trim(),
              resolver_mode: resolverMode,
              ...(resolverMode === "LIVE" ? { allow_network: true } : {}),
              ...(resolverMode === "FIXTURE" && fixtureScenarioId
                ? { fixture_scenario_id: fixtureScenarioId }
                : {}),
            }
          : {
              input_kind: "COORDINATE" as const,
              latitude: Number(latitude),
              longitude: Number(longitude),
              resolver_mode: resolverMode,
              ...(resolverMode === "LIVE" ? { allow_network: true } : {}),
              ...(resolverMode === "FIXTURE" && fixtureScenarioId
                ? { fixture_scenario_id: fixtureScenarioId }
                : {}),
            };
      const created = await api.createParcelResolution(body);
      setResolution(created);
      const valid = (created.candidates || []).filter(
        (c) => c.validation_status !== "INVALID",
      );
      if (created.status === "NEEDS_BOUNDARY_CONFIRMATION" && valid.length === 1) {
        setSelectedCandidateId(valid[0].candidate_id);
      } else if (created.selection?.selected_candidate_id) {
        setSelectedCandidateId(created.selection.selected_candidate_id);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "request_failed";
      setError(msg);
      if (/failed to fetch|network|http_5/i.test(msg)) setApiDown(true);
    } finally {
      setBusyResolve(false);
    }
  }

  async function onConfirm() {
    if (!resolution || !selectedCandidateId || !selectedHash) return;
    setError(null);
    setBusyResolve(true);
    try {
      const confirmedRes = await api.confirmParcelResolution(resolution.resolution_id, {
        selected_candidate_id: selectedCandidateId,
        expected_geometry_hash: selectedHash,
        explicit_confirmation: true,
      });
      setResolution(confirmedRes);
      setConfirmedHash(
        confirmedRes.confirmed_parcel?.geometry_hash ||
          confirmedRes.planner_binding?.geometry_hash ||
          selectedHash,
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : "confirm_failed";
      setError(msg);
      if (msg.includes("STALE_GEOMETRY_HASH")) {
        setConfirmedHash(null);
      }
    } finally {
      setBusyResolve(false);
    }
  }

  async function onStartAnalysis(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!canStart || !resolution) {
      setError("Confirm a parcel boundary before starting analysis.");
      return;
    }
    // Guard: hash drift clears start
    const liveHash =
      resolution.confirmed_parcel?.geometry_hash ||
      resolution.planner_binding?.geometry_hash;
    if (confirmedHash && liveHash && confirmedHash !== liveHash) {
      setError("STALE_GEOMETRY_HASH: confirmed hash no longer matches.");
      clearConfirmationState();
      return;
    }
    setBusyStart(true);
    try {
      const { mode, intended_operation } = analysisChoiceToApi(analysisChoice);
      const created = await api.createInvestigation({
        parcel_resolution_id: resolution.resolution_id,
        mode,
        intended_operation,
        planned_actions: [],
        execution_source: "PARCEL_RESOLUTION",
        mireye_mode: resolverMode === "LIVE" ? "LIVE" : "FIXTURE",
        ...(resolverMode === "LIVE" ? { allow_network: true } : {}),
      });
      navigate(`/investigations/${created.investigation_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "request_failed");
    } finally {
      setBusyStart(false);
    }
  }

  return (
    <AppShell
      badges={
        <>
          {resolverMode === "FIXTURE" ? (
            <Badge kind="replay">Demo mode</Badge>
          ) : (
            <Badge kind="parcel">Real property search</Badge>
          )}
          {confirmed && <Badge kind="parcel">Parcel confirmed</Badge>}
        </>
      }
    >
      <section className="intake-hero" aria-labelledby="intake-title">
        <p className="analysis-eyebrow">Agricultural land intelligence</p>
        <h1 id="intake-title">Understand the land before you commit.</h1>
        <p>
          Confirm one U.S. parcel, choose what you want to explore, and let RangeMatch build an
          evidence-led Cow-Calf and Sheep diligence report.
        </p>
        <div className="intake-promise-row" aria-label="RangeMatch investigation principles">
          <span>One parcel</span>
          <span>Eight land checks</span>
          <span>Clear next steps</span>
        </div>
      </section>

      <nav className="intake-stepper" aria-label="Investigation setup steps">
        <div data-state={resolution ? "complete" : "active"}>
          <span>1</span><strong>Find the parcel</strong>
        </div>
        <div data-state={confirmed ? "complete" : resolution ? "active" : "pending"}>
          <span>2</span><strong>Confirm the boundary</strong>
        </div>
        <div data-state={confirmed ? "active" : "pending"}>
          <span>3</span><strong>Choose your investigation</strong>
        </div>
      </nav>

      <div className="intake-map-layout" data-testid="intake-map-layout">
        <section className="intake-controls" aria-label="Parcel resolution intake">
          <div className="intake-section-card intake-find-card">
            <div className="intake-section-heading">
              <span className="intake-section-number">01</span>
              <div>
                <h2 className="display">Select your land</h2>
                <p>Use a full street address, or identify rural land with a map pin or coordinates.</p>
              </div>
            </div>

            <div className="field compact-field">
            <span id="entry-label">How do you want to find the parcel?</span>
            <div className="choice-row" role="group" aria-labelledby="entry-label">
              <button
                type="button"
                className="choice"
                aria-pressed={inputKind === "ADDRESS"}
                data-testid="entry-address"
                onClick={() => {
                  setInputKind("ADDRESS");
                  setFixtureScenarioId(DEMO_RESOLVER_PRESETS[0].fixture_scenario_id);
                  setResolution(null);
                }}
              >
                Search by address
              </button>
              <button
                type="button"
                className="choice"
                aria-pressed={inputKind === "COORDINATE"}
                data-testid="entry-coordinate"
                onClick={() => {
                  setInputKind("COORDINATE");
                  setFixtureScenarioId(DEMO_COORD_PRESET.fixture_scenario_id);
                  setResolution(null);
                }}
              >
                Drop a pin / Enter coordinates
              </button>
            </div>
            </div>

            <div className="resolver-row">
            <div className="field compact-field">
            <span id="resolver-label">Search mode</span>
            <div className="choice-row" role="group" aria-labelledby="resolver-label">
              <button
                type="button"
                className="choice"
                aria-pressed={resolverMode === "FIXTURE"}
                onClick={() => {
                  setResolverMode("FIXTURE");
                  if (!fixtureScenarioId) {
                    setResolverNotice(
                      "Fixture mode only supports the reviewed demo input. Choose a demo preset or select LIVE.",
                    );
                  }
                }}
              >
                Try the demo
              </button>
              <button
                type="button"
                className="choice"
                aria-pressed={resolverMode === "LIVE"}
                onClick={() => {
                  setResolverMode("LIVE");
                  setFixtureScenarioId(null);
                  setResolverNotice("LIVE parcel lookup selected. Your input will be sent to Mireye when you resolve.");
                }}
              >
                Search a real property
              </button>
            </div>
            </div>

            <details className="demo-disclosure">
              <summary>How real property search uses your input</summary>
              <p>
                <strong>Real property search sends the address or coordinates to Mireye</strong>
                to locate a parcel boundary. Demo mode uses a prepared example and sends no
                property input. RangeMatch never silently replaces a failed real search with demo data.
              </p>
            </details>
            </div>

          {resolverMode === "FIXTURE" && inputKind === "ADDRESS" && (
            <div className="field demo-preset-field">
              <span id="preset-label">Demo addresses</span>
              <div className="choice-row" role="group" aria-labelledby="preset-label">
                {DEMO_RESOLVER_PRESETS.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    className="choice"
                    aria-pressed={fixtureScenarioId === p.fixture_scenario_id}
                    onClick={() => applyAddressPreset(p)}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {resolverMode === "FIXTURE" && inputKind === "COORDINATE" && (
            <div className="field demo-preset-field">
              <span id="coord-preset-label">Demo coordinates</span>
              <div className="choice-row" role="group" aria-labelledby="coord-preset-label">
                <button
                  type="button"
                  className="choice"
                  aria-pressed={fixtureScenarioId === DEMO_COORD_PRESET.fixture_scenario_id}
                  onClick={applyCoordPreset}
                >
                  {DEMO_COORD_PRESET.label}
                </button>
              </div>
            </div>
          )}

          {inputKind === "ADDRESS" ? (
            <div className="field property-search-field">
              <label htmlFor="address">Full U.S. street address</label>
              <input
                id="address"
                type="text"
                value={address}
                onChange={(e) => {
                  setAddress(e.target.value);
                  if (resolverMode === "FIXTURE") {
                    const match = DEMO_RESOLVER_PRESETS.find(
                      (p) => p.address.toLowerCase() === e.target.value.trim().toLowerCase(),
                    );
                    setFixtureScenarioId(match?.fixture_scenario_id ?? null);
                    setResolverNotice(
                      match
                        ? null
                        : "Custom addresses cannot use demo data. Select LIVE to send this address to the parcel lookup service.",
                    );
                  }
                }}
                placeholder="Street, city, state, ZIP"
              />
              <span className="hint">
                We’ll find the parcel boundary and ask you to confirm it on the map.
              </span>
            </div>
          ) : (
            <div className="field property-search-field">
              <label htmlFor="coord-text">Coordinates (lat,lng)</label>
              <input
                id="coord-text"
                type="text"
                value={coordText}
                onChange={(e) => syncCoordsFromText(e.target.value)}
                placeholder="40.495,-104.895"
                data-testid="coord-text"
              />
              <div className="choice-row" style={{ marginTop: "0.5rem" }}>
                <label htmlFor="latitude" className="sr-only-focusable">
                  Latitude
                </label>
                <input
                  id="latitude"
                  type="number"
                  step="any"
                  value={latitude}
                  onChange={(e) => {
                    setLatitude(e.target.value);
                    syncCoordsFromText(`${e.target.value},${longitude}`);
                  }}
                  aria-label="Latitude"
                  data-testid="latitude"
                />
                <input
                  id="longitude"
                  type="number"
                  step="any"
                  value={longitude}
                  onChange={(e) => {
                    setLongitude(e.target.value);
                    syncCoordsFromText(`${latitude},${e.target.value}`);
                  }}
                  aria-label="Longitude"
                  data-testid="longitude"
                />
              </div>
              <span className="hint">
                Click inside the property or enter coordinates. We’ll find the parcel boundary
                and ask you to confirm it.
              </span>
            </div>
          )}

          <div className="actions intake-primary-action">
            <button
              type="button"
              className="btn btn-primary"
              onClick={onResolve}
              disabled={!canResolve}
              data-testid="resolve-property"
            >
              {busyResolve ? "Resolving…" : "Resolve property"}
            </button>
          </div>

          <div
            className={`resolution-status status-${(resolution?.status || "idle").toLowerCase()}`}
            data-testid="resolution-status"
            role="status"
          >
            {statusBanner}
          </div>

          </div>

          {resolution?.limitations && resolution.limitations.length > 0 && (
            <details className="intake-limitations" data-testid="resolution-limitations">
              <summary>Resolution limitations ({resolution.limitations.length})</summary>
              <ul className="unknown-list">
              {resolution.limitations.map((lim) => (
                <li key={lim} className="highlight-item">
                  {lim}
                </li>
              ))}
              </ul>
            </details>
          )}

          <div className="intake-section-card intake-confirm-card" data-enabled={Boolean(resolution)}>
            <div className="intake-section-heading">
              <span className="intake-section-number">02</span>
              <div>
                <h2>Confirm the parcel boundary</h2>
                <p>The highlighted polygon—not the address point—becomes the investigation geometry.</p>
              </div>
            </div>

            {candidates.length > 1 && (
            <div className="field" data-testid="candidate-list">
              <span id="cand-label">Candidate parcels</span>
              <ul className="candidate-list" aria-labelledby="cand-label">
                {candidates.map((c) => (
                  <li key={c.candidate_id}>
                    <button
                      type="button"
                      className="candidate-item"
                      aria-pressed={selectedCandidateId === c.candidate_id}
                      data-testid={`candidate-${c.candidate_id}`}
                      disabled={false}
                      onClick={() => onSelectCandidate(c.candidate_id)}
                    >
                      <strong>{c.label}</strong>
                      <span className="muted">{c.candidate_id}</span>
                      {c.geometry_hash && (
                        <code className="hash-chip">{c.geometry_hash.slice(0, 12)}…</code>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="actions intake-primary-action">
            <button
              type="button"
              className="btn btn-primary"
              onClick={onConfirm}
              disabled={!canConfirm || busy}
              data-testid="confirm-parcel"
            >
              Confirm this parcel
            </button>
          </div>
          </div>

          <form
            onSubmit={onStartAnalysis}
            aria-label="Investigation intake"
            className="intake-section-card intake-analysis-card"
            data-enabled={confirmed}
          >
            <div className="intake-section-heading">
              <span className="intake-section-number">03</span>
              <div>
                <h2>What should RangeMatch investigate?</h2>
                <p>General exploration keeps both operations as peers; a chosen goal is presented first.</p>
              </div>
            </div>
            <div className="field">
              <span id="mode-label" className="sr-only-focusable">Analysis mode</span>
              <div className="analysis-mode-grid" role="group" aria-labelledby="mode-label">
                <button
                  type="button"
                  className="choice"
                  aria-pressed={analysisChoice === "GENERAL"}
                  onClick={() => setAnalysisChoice("GENERAL")}
                  data-testid="mode-general"
                >
                  <strong>General Exploration</strong>
                  <span>Compare Cow-Calf and Sheep as peers</span>
                </button>
                <button
                  type="button"
                  className="choice"
                  aria-pressed={analysisChoice === "CATTLE"}
                  onClick={() => setAnalysisChoice("CATTLE")}
                  data-testid="mode-cattle"
                >
                  <strong>Cattle</strong>
                  <span>Investigate a Cow-Calf goal first</span>
                </button>
                <button
                  type="button"
                  className="choice"
                  aria-pressed={analysisChoice === "SHEEP"}
                  onClick={() => setAnalysisChoice("SHEEP")}
                  data-testid="mode-sheep"
                >
                  <strong>Sheep</strong>
                  <span>Investigate a Sheep grazing goal first</span>
                </button>
              </div>
            </div>

            {error && (
              <div className="error-banner" role="alert" data-testid="intake-error">
                {error}
              </div>
            )}

            <div className="actions intake-start-action">
              <button
                className="btn btn-primary"
                type="submit"
                disabled={!canStart}
                data-testid="start-analysis"
              >
                {busyStart ? "Starting analysis…" : "Start Analysis"}
              </button>
              <span>Usually a few minutes · progress stays visible</span>
            </div>
            <p className="analysis-data-use-note">
              To write the plain-language report, RangeMatch may send a minimized evidence
              summary—not API keys or raw source files—to the configured OpenAI provider.
            </p>
          </form>
        </section>

        <section className="intake-map-panel" aria-label="Parcel map">
          <div className="map-panel-heading">
            <div>
              <p className="analysis-eyebrow">Evidence map</p>
              <h2>Parcel boundaries</h2>
            </div>
            <Badge kind={confirmed ? "parcel" : "point"}>{confirmed ? "Boundary locked" : "Awaiting confirmation"}</Badge>
          </div>
          <p className="map-instruction">
            {inputKind === "COORDINATE"
              ? "Drop a pin to set the lookup point, then resolve. Candidate parcels show as outlines; confirm one polygon before analysis."
              : "Neutral outlines for all candidates; highlight shows selection"}
            {confirmed ? "; amber outline locks the confirmed parcel." : "."}
            {" "}
            Changing selection after confirm clears confirmation.
          </p>
          <ParcelMap
            candidates={candidates}
            selectedCandidateId={selectedCandidateId}
            confirmed={confirmed}
            onSelectCandidate={onSelectCandidate}
            interactive={true}
            pinDropEnabled={inputKind === "COORDINATE" && !confirmed}
            queryPin={queryPin}
            onDropPin={onDropPin}
          />
          <div className="map-legend-row">
            <span><i className="map-key candidate-key" /> Candidate</span>
            <span><i className="map-key selected-key" /> Selected</span>
            <span><i className="map-key confirmed-key" /> Confirmed</span>
          </div>
          <p className="map-footnote">
            Map evidence does not score suitability. No APN, boundary upload, batch, or freehand draw.
          </p>
        </section>
      </div>
    </AppShell>
  );
}
