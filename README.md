# RangeMatch

**Understand a parcel's natural foundation for cattle before deeper field work.**

RangeMatch is an AI natural-environment advisor for U.S. cattle-land screening. **Mireye** confirms the parcel and supplies the primary physical-world profile. A deterministic Gap Detector calls RangeMatch supplements only for missing capabilities; a validated LLM then explains the resulting Terrain, Forage, Water, Climate, and Soil picture for the buyer's intended cattle use.

This is not a map website. The competition Demo is a deterministic Agent: reason over claims vs evidence, decide bottleneck and action order, act with copy-ready messages.

- **Primary payer:** buyer-side ranch broker / land advisor
- **Beneficiary / second payer:** serious ranch buyer
- **Demo geometry:** CPER is an engineering test geometry, not a real listing

One-pager: `docs/RANGEMATCH_MIREYE_CHALLENGE_ONE_PAGER.md`

## Competition Demo

RangeMatch confirms a parcel through Mireye, builds a five-domain Natural Cattle Profile, combines it with reviewed cattle-environment knowledge and buyer context, asks one question that can change the interpretation, and exports a validated two-page Natural Cattle Foundation report.

**Nambe is not a product prerequisite.** It is the verified Demo path, a regression fixture, and a standby exhibit if the network is down. CPER is an engineering fixture only.

**Demo entry is free-form** U.S. address or `lat,lng`. Failed lookups stay failed. The Agent never silently substitutes Nambe or CPER. Judges may opt into the verified Nambe Demo explicitly; that creates a new isolated run.

```text
free-form address / lat,lng
→ Mireye POST /v1/lookup
→ judge confirms exactly one polygon
→ Mireye cattle-environment Profile + confirmed-geometry core
→ deterministic Gap Detector
→ only planned F01–F05/F08 supplements
→ Combined Environmental Evidence → Natural Cattle Profile
→ Deal Context v1 + validated LLM interpretation + one question
→ answer → Deal Context v2 → revised interpretation
→ two-page Natural Cattle Foundation report
```

It does **not** claim a complete livestock operating assessment, cattle/sheep comparison, fence/facility detection, stocking rates, legal conclusions, or national production validation.

### Environment

Copy `.env.example` to `.env`. Required for live Demo:

| Variable | Role |
|---|---|
| `MIREYE_API_BASE_URL` | Mireye API origin |
| `MIREYE_API_TOKEN` | Bearer token (canonical). `MIREYE_API_KEY` is a legacy alias |
| `RANGEMATCH_LLM_PROVIDER` | `DEEPSEEK` or `OPENAI` for live prose, otherwise `FIXTURE` / omit |
| `DEEPSEEK_API_KEY` | DeepSeek key when provider is `DEEPSEEK` |
| `RANGEMATCH_LLM_API_KEY` | Shared live-LLM key alias (DeepSeek or OpenAI) |

Never commit `.env`.

### Start

```bash
# Terminal A — Agent API (ports are fixed: API 8001, UI 5273)
export PYTHONPATH=src
.venv/bin/uvicorn rangematch.api:app --reload --port 8001 --env-file .env \
  --reload-exclude '.venv' --reload-exclude '.venv-livegate' --reload-exclude 'web'

# Terminal B — Demo UI
cd web && npm install && npm run dev
```

Open **http://127.0.0.1:5273/advisor-demo**

RangeMatch pins this Demo to port **5273** (`strictPort: true`). If 5273 is busy, stop that process and restart `npm run dev`.

### Support scope and confirmation

- **Demo entry:** free-form U.S. street address or `lat,lng`. APN-only lookup is not supported. Verified Nambe is an explicit opt-in Demo run, not a silent fallback.
- **Messy language:** a standard street (`4213 Nambe Rd`) or `lat,lng` goes straight to Mireye. Phrases like `near Nunn Colorado` may be tidied by the LLM into a structured lookup. The LLM cannot invent coordinates, polygons, or pick a parcel. Mireye still locates the place; you still confirm the boundary. If cleanup fails, add a state, ZIP, or coordinates.
- **Required confirm:** if Mireye returns one or more parcel polygons, the judge must confirm exactly one boundary. The Agent does not auto-pick.
- **After confirm:** Mireye builds the primary Profile; the Gap Detector invokes only the F01–F05/F08 supplements needed for missing capabilities. F06 geometry is always-on core and F07 is never triggered by this path.
- **Adapter miss:** a timed-out or missing federal source still yields an honest limited investigation or Snapshot path. It does not swap another parcel.
- **Lookup miss:** `PARCEL_NOT_FOUND` vs `PARCEL_SERVICE_UNAVAILABLE` fail closed with named outcomes. No fake report.
- **LLM miss:** DeepSeek/OpenAI failure fails soft to a validated deterministic conclusion and Snapshot.
- **CPER:** engineering fixture only, not a nationwide confirmation model.
- **Standby PDF:** keep a saved Snapshot from a successful Nambe run for network-down exhibit (do not substitute it for a failed live parcel).

Buyer-facing progress:

```text
Confirm parcel
Build ranch picture
Trace feed, water and movement
Write advisor brief
Validate report
```

If the OpenAI key is missing or validation fails, the Agent uses a deterministic cattle story for **this** confirmed parcel. It does not silently swap Nambe or CPER.

## Tests

```bash
export PYTHONPATH=src
python -m unittest tests.test_advisor_workflow_contract tests.test_advisor_f03_objects tests.test_advisor_boundary_fixtures tests.test_advisor_agent tests.test_advisor_api
cd web && npm test
```

## Current phase (engineering baseline)

```text
F01–F08 demo Factor scope: CLOSED / FROZEN
Unified output + Planner + fixture Executor: DONE
One-parcel HTTP API prototype: DONE (fixture replay + confirmed live parcel path)
Parcel Resolution API: DONE (FIXTURE replay + LIVE Mireye lookup)
Buyer-facing UI + parcel map confirmation: DONE (web/ — MapLibre 2D; consumes API only)
Constrained LLM Intent + Buyer Report: DONE; validator hardened
Live Mireye parcel + Property/Land/Hazard context: VERIFIED on a clean network
Public Diligence Agent: live official-source search + citations DONE
Buyer decision report v2: parcel facts + evidence matrix + actions DONE
Backend tests: 423 passed; UI tests: 22 passed; production build passed
Next product slice: competition packaging and deployment readiness
```

See:

- `docs/README.md` — documentation authority and current status
- `docs/MIREYE_LIVE_PARCEL_RESOLVER_CONTRACT.md` — live `/lookup` → parcel mapping; Regrid license gates commercial cache/PII only
- `docs/LLM_AUTHORITY_AND_REPORT_SPEC.md`
- `web/README.md` — buyer UI run instructions
- `docs/PACKAGING_AND_DELIVERY_STRATEGY.md`
- `docs/AGENT_ORCHESTRATION_SPEC.md`
- `docs/F01_F08_UNIFIED_OUTPUT_CONTRACT.md`
- `docs/PRODUCT_PROTOTYPE_SCOPE.md`
- `docs/ONE_PARCEL_API_SPEC.md`
- `docs/PARCEL_RESOLUTION_CONTRACT.md`
- `docs/MIREYE_LIVE_PARCEL_RESOLVER_CONTRACT.md`
- `docs/PLANNER_EXECUTOR_SPEC.md`

## Quick local checks (engineering)

```bash
cp .env.example .env
# set MIREYE_API_TOKEN when calling Mireye (legacy MIREYE_API_KEY also accepted); never commit secrets

python -m pip install -e ".[api]"
# `.[api]` includes jsonschema plus live adapter extras: numpy, netCDF4, rasterio.
# Missing adapter packages must not crash Advisor; Factors become SOURCE_UNAVAILABLE.
export PYTHONPATH=src
python -m unittest discover -s tests
python -m rangematch.cli evaluate test-data/land-profiles/land_profile_cper_001.json
```

## One-parcel API (prototype)

Supports fixture replay, existing Land Profiles, and confirmed live parcel resolution. Restart clears in-memory investigations **and** parcel resolutions. Live calls require explicit network authorization and configured credentials; failures never silently substitute fixtures.

```bash
python -m pip install -e ".[api]"
export PYTHONPATH=src
uvicorn rangematch.api:app --reload --port 8001 --env-file .env
# Use the same venv that installed netCDF4/rasterio. A missing optional
# adapter dependency marks that Factor SOURCE_UNAVAILABLE; it does not abort RUN_AGENDA.
# After a validated Brief: GET /v1/advisor/runs/{id}/buyer-brief.pdf
# Persist a run: GET /v1/advisor/runs/{id}/report-bundle
```

Health:

```bash
curl -s http://127.0.0.1:8001/health
```

### Parcel resolution (FIXTURE)

```bash
curl -s -X POST http://127.0.0.1:8001/v1/parcel-resolutions \
  -H 'Content-Type: application/json' \
  -d '{
    "address": "100 Demo Ranch Rd, Weld County, CO 80701",
    "resolver_mode": "FIXTURE",
    "fixture_scenario_id": "one_valid_candidate"
  }'

# Then confirm with selected_candidate_id + expected_geometry_hash + explicit_confirmation: true
# GET /v1/parcel-resolutions/{id}
# POST /v1/investigations with parcel_resolution_id + execution_source: PARCEL_RESOLUTION
```

See `docs/PARCEL_RESOLUTION_CONTRACT.md` and `docs/ONE_PARCEL_API_SPEC.md`.

### CPER Goal-directed demo replay

```bash
curl -s -X POST http://127.0.0.1:8001/v1/investigations \
  -H 'Content-Type: application/json' \
  -d '{
    "existing_land_profile_reference": "test-data/land-profiles/land_profile_cper_001.json",
    "mode": "GOAL_DIRECTED",
    "intended_operation": "COW_CALF_OPERATION",
    "planned_actions": [],
    "execution_source": "DEMO_FIXTURE",
    "mireye_mode": "BLOCKED_EXTERNAL"
  }'
```

CPER Discovery demo replay:

```bash
curl -s -X POST http://127.0.0.1:8001/v1/investigations \
  -H 'Content-Type: application/json' \
  -d '{
    "existing_land_profile_reference": "test-data/land-profiles/land_profile_cper_001.json",
    "mode": "DISCOVERY",
    "intended_operation": null,
    "planned_actions": [],
    "execution_source": "DEMO_FIXTURE",
    "mireye_mode": "BLOCKED_EXTERNAL"
  }'
```

Then `GET /v1/investigations/{id}`, `/trace`, and `/report`.

Raw address is not accepted as analysis geometry. Resolve and confirm the parcel through `/v1/parcel-resolutions` before starting an investigation.

## Constrained LLM (Intent + Buyer Report)

Default provider is `FIXTURE` (no network, no key).

```bash
export RANGEMATCH_LLM_PROVIDER=FIXTURE
# Live (optional — DeepSeek is the current Demo live path):
# export RANGEMATCH_LLM_PROVIDER=DEEPSEEK
# export RANGEMATCH_LLM_MODEL=deepseek-chat
# export DEEPSEEK_API_KEY=...   # never commit
```

Only reports that pass the deterministic validator are displayed as LLM narratives. If the provider is unavailable or validation fails, the UI preserves the investigation and presents a clearly labeled deterministic fallback assembled from Engine output. See `docs/LLM_AUTHORITY_AND_REPORT_SPEC.md`.

## Buyer UI prototype

```bash
# Terminal A — API (as above)
# Terminal B
cd web && npm install && npm run dev
```

Open http://127.0.0.1:5273 — Vite proxies `/health` and `/v1` to the API. Details in `web/README.md`. The Challenge Demo is `/advisor-demo` on the same port.

Docker Compose / Skill packaging remain **planned**, not the current entrypoint.

## Secrets

- Use `.env` locally (gitignored).
- Only `.env.example` is committed.
- Do not put API keys in docs, fixtures, or Skills.
