# RangeMatch

**Know what to verify before you visit or spend.**

RangeMatch is an AI buyer’s agent for U.S. ranch listings. **Mireye** anchors the physical parcel. RangeMatch combines that parcel context with federal land evidence and listing-claim forensics, then decides the next diligence action — not suitability, not stocking, not buy/no-buy.

This is not a map website. The competition Demo is a deterministic Agent: reason over claims vs evidence, decide bottleneck and action order, act with copy-ready messages.

- **Primary payer:** buyer-side ranch broker / land advisor
- **Beneficiary / second payer:** serious ranch buyer
- **Demo geometry:** CPER is an engineering test geometry, not a real listing

One-pager: `docs/RANGEMATCH_MIREYE_CHALLENGE_ONE_PAGER.md`

## Mireye Challenge Demo (deterministic, no live LLM)

```bash
# Terminal A — Agent API (load MIREYE_API_TOKEN from .env)
export PYTHONPATH=src
uvicorn rangematch.api:app --reload --port 8001 --env-file .env

# Terminal B — Demo UI
cd web && npm install && npm run dev
```

Open **http://127.0.0.1:5273/advisor-demo**

RangeMatch pins this Demo to port **5273** (`strictPort: true`) so it does not collide with other Vite apps on 5173/5174. If 5273 is busy, stop that process and restart `npm run dev`.

The page does not load a pre-written Brief. Click **Run investigation**. The API executes:

```text
Accept place → Resolve parcel → Call Mireye (live HTTP)
→ Build agenda → Run agenda → Compare claims → Order actions → Validate brief
```

Mireye is a real `allow_network=true` call (`/v1/lookup` + `/v1/fetch`). Success or `BLOCKED_EXTERNAL` is the HTTP/token/API result. Failed Mireye contexts are not replaced with fixtures. F01–F08 on this Demo still use the CPER engineering land profile.

Each run returns a new `run_id`, `generated_at`, and `packet_hash`. CPER listing claims stay fixed. OpenAI is not required. The legacy HOLD buyer dashboard is unchanged.

```text
Mireye / parcel context
→ federal evidence + listing claims
→ Packet → gaps → bottleneck + action
→ three-page Brief → Validator → Demo UI
```

CPER Demo story: a buyer received “excellent water / easy access / ready for cattle,” and is deciding whether to fly this weekend or request title first. Water is the largest evidence gap; access paper is the first action; visit purpose depends on that document.

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
# Live (optional):
# export RANGEMATCH_LLM_PROVIDER=OPENAI
# export RANGEMATCH_LLM_MODEL=<supported configured model>
# export RANGEMATCH_LLM_API_KEY=...   # never commit
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
