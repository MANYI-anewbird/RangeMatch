# One-Parcel API Spec (Prototype)

> Status: `EXECUTABLE_PROTOTYPE_V0_2`  
> Date: 2026-08-08  
> Service: RangeMatch one-parcel investigation API  
> Canonical live Factors: **F01–F08 are wired** for a confirmed parcel  
> Live Mireye: supported only after `PARCEL_CONFIRMED`, with `mireye_mode: LIVE` and `allow_network: true`  
> Live parcel resolver: implemented through Mireye `/v1/lookup`; no fixture fallback on failure

## Purpose

Expose Planner + Executor through a stable HTTP API for **exactly one parcel per investigation**, including address **or** coordinates → parcel resolution → confirmation before investigation. Mireye Property/Land/Hazard contexts may be collected live after confirmation, but remain non-canonical and cannot replace F01–F08 Land Facts.

F03 runtime discovery uses USGS NHDPlus HR and creates mapped hydrography
candidates plus a deterministic max-3 imagery-review queue. It does not claim
NAIP review occurred and never creates `FIELD_VERIFIED` without a separate,
provenance-complete reviewed evidence package. F04 uses official USDA-NRCS SDA
tabular data and WFS map-unit intersections; EDIT page accessibility remains
unknown unless separately fetched and audited.

This slice does not implement Docker, Skill packaging, batch endpoints, F09, APN, boundary upload, freehand draw, or new scientific logic.

## Run

```bash
python -m pip install -e ".[api]"
export PYTHONPATH=src
uvicorn rangematch.api:app --reload --port 8000
```

**Storage:** in-memory investigation + parcel-resolution stores. **Process restart clears all records.** Persistence can replace `InMemoryParcelResolutionStore` later without changing handlers.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Service / schema / planner / executor / Mireye / LLM / parcel-resolver availability |
| `POST` | `/v1/parcel-resolutions` | Start ADDRESS or COORDINATE → candidate lookup |
| `GET` | `/v1/parcel-resolutions/{id}` | Resolution state, candidates, provenance |
| `POST` | `/v1/parcel-resolutions/{id}/confirm` | Explicit boundary confirmation → `PARCEL_CONFIRMED` |
| `POST` | `/v1/investigations` | Create one investigation |
| `GET` | `/v1/investigations/{id}` | Investigation state + unified output |
| `GET` | `/v1/investigations/{id}/trace` | Planner/executor step trace |
| `GET` | `/v1/investigations/{id}/report` | Deterministic report substrate from Unified Output |
| `POST` | `/v1/intent/parse` | Constrained LLM intent parse (schema-validated) |
| `POST` | `/v1/investigations/{id}/buyer-report` | Generate + validate LLM buyer report |
| `GET` | `/v1/investigations/{id}/buyer-report` | Return last validated buyer report |
| `POST` | `/v1/investigations/{id}/diligence-search` | Run constrained current official-source diligence search |
| `GET` | `/v1/investigations/{id}/diligence-search` | Return the last diligence-search result and citations |

No list/batch endpoint. No ICP. No F09. The map is a frontend parcel-confirmation interface, not an API concern.

The buyer-facing product does not expose the raw backend sections as the primary experience. It projects the same authoritative data into: dashboard, readable decision report, and technical evidence appendix. See `RANGEMATCH_PRODUCT_AND_AGENT_CODE_FLOW.md`.

LLM authority for the legacy Constrained Intent + Engine buyer-report path: see `docs/archive/product-history/LLM_AUTHORITY_AND_REPORT_SPEC.md`. Current Advisor Demo chat authority: `docs/TWO_BRAIN_ADVISOR_CHAT_CONTRACT.md`. Engine decisions are never altered by LLM output.  
Parcel resolution contract: see `docs/PARCEL_RESOLUTION_CONTRACT.md`.

## Health

```json
{
  "status": "ok",
  "schema_version": "RANGEMATCH_UNIFIED_OUTPUT@0.1.0",
  "planner_version": "RANGEMATCH_PLANNER@0.1.0",
  "executor_version": "RANGEMATCH_PLANNER_EXECUTOR@0.1.0",
  "live_mireye_availability": "CONFIGURED_LIVE_GATE_REQUIRED",
  "parcel_resolver_live": "CONFIGURED_LIVE_GATE_REQUIRED",
  "mireye_catalog_gate": {
    "status": "COMPATIBLE",
    "compatible": true,
    "affects_parcel_resolution": false
  },
  "storage": "in_memory_ephemeral"
}
```

Never returns secrets.

Health never makes a live network call. Configuration readiness is not a claim that the current network is available.

### Live Mireye investigation mode

```json
{
  "parcel_resolution_id": "pres_...",
  "mode": "DISCOVERY",
  "execution_source": "PARCEL_RESOLUTION",
  "mireye_mode": "LIVE",
  "allow_network": true
}
```

This mode is rejected before explicit parcel confirmation and without explicit network authorization. Property, point-land, and point-hazard calls fail independently. Their output is context/QA only (`canonical_for_parcel_facts: false`). After confirmation, F01 is collected from USGS 3DEP, F02 from RAP cover/production, F08 reuses the same RAP cover artifact, F05 reads canonical NOAA/NCEI `annprcp_norm`, and F06 is computed from geometry. RAP applicability and exact pixel coverage remain explicit gates. Climate values remain Land Facts, not suitability thresholds. A successful context or aggregate call cannot manufacture a score or ranking.

`POST /v1/mireye/catalog-gate` — Field Catalog compatibility gate (`FIXTURE` default; `LIVE` requires `allow_network: true`). Catalog failure is **not** a parcel failure.

## Parcel resolution

Competition Demo: two entries, one confirmation flow.

### POST /v1/parcel-resolutions

Address:

```json
{
  "input_kind": "ADDRESS",
  "address": "100 Demo Ranch Rd, Weld County, CO 80701",
  "resolver_mode": "FIXTURE",
  "fixture_scenario_id": "one_valid_candidate"
}
```

Coordinates (Drop a pin / Enter coordinates share `COORDINATE`):

```json
{
  "input_kind": "COORDINATE",
  "latitude": 40.495,
  "longitude": -104.895,
  "resolver_mode": "FIXTURE",
  "fixture_scenario_id": "coord_one_valid_candidate"
}
```

- `input_kind`: `ADDRESS` | `COORDINATE` (default `ADDRESS` for backward compatibility)
- `resolver_mode`: `FIXTURE` | `LIVE`
- `fixture_scenario_id`: optional for FIXTURE; if omitted, matched by address or lat/lng against `test-data/parcel-resolution/`
- COORDINATE validates format, U.S. envelope, and lat/lng swap (`coordinates.py`) before lookup
- LIVE without configured provider / without `allow_network` → `BLOCKED_EXTERNAL` / `NETWORK_NOT_AUTHORIZED` (no network, no CPER substitution)
- LIVE with `allow_network: true` → controlled Mireye `POST /v1/lookup` with `kind=address|coord` (`mireye_lookup_transport.py`); never FIXTURE fallback
- Live gate: `POST /v1/mireye/lookup-live-gate` (explicit `allow_network`; does not claim success when blocked)
- Live `/lookup` mapping (including `PARCEL_DATA_UNAVAILABLE`, `GEOCODE_QUALITY_INSUFFICIENT`): `docs/MIREYE_LIVE_PARCEL_RESOLVER_CONTRACT.md`
- Never fabricates polygons from address points or pins; pin ≠ F01–F08 geometry
- `disposition=resolved` alone must never become `PARCEL_CONFIRMED`
### GET /v1/parcel-resolutions/{resolution_id}

Returns normalized address, status, candidates, provenance, limitations, confirmation status, `evidence_invalidation_required`. No secrets.

### POST /v1/parcel-resolutions/{resolution_id}/confirm

```json
{
  "selected_candidate_id": "cand_demo_001",
  "expected_geometry_hash": "<sha256 hex>",
  "explicit_confirmation": true
}
```

| Rule | Behavior |
|---|---|
| `explicit_confirmation` false/missing | `422` |
| Unknown candidate | `404` / `400` |
| Stale / mismatched `expected_geometry_hash` | `409 STALE_GEOMETRY_HASH` |
| Success | `PARCEL_CONFIRMED` + `planner_binding` |
| Repeat same confirm | Idempotent / deterministic |

`planner_binding` fields: `parcel_geometry`, `geometry_reference`, `geometry_hash`, `source_crs: EPSG:4326`.

## POST /v1/investigations

Creates an **async investigation job**. Response returns immediately with
`status: QUEUED` and an `investigation_id`. Planner/Executor runs in a bounded
background worker. Poll `GET /v1/investigations/{id}` and `/trace` until a
terminal status.

Exactly one parcel input among:

- `address`
- `parcel_geometry`
- `existing_land_profile_reference`
- `parcel_resolution_id`

Plus:

```yaml
mode: GOAL_DIRECTED | DISCOVERY
intended_operation: COW_CALF_OPERATION | SHEEP_GRAZING | null
planned_actions: []
execution_source: EXISTING_LAND_PROFILE | DEMO_FIXTURE | PARCEL_RESOLUTION
```

### Execution sources

| Source | Behavior |
|---|---|
| `DEMO_FIXTURE` | Explicit CPER fixture replay only; response labeled `REPLAY_DEMO_FIXTURE_NOT_LIVE` |
| `EXISTING_LAND_PROFILE` | Reuse/evaluate path for a path under approved `test-data/` roots |
| `PARCEL_RESOLUTION` | Requires confirmed `parcel_resolution_id`; binds stored geometry + hash; **no** silent CPER swap |

### Blocked / fail-closed inputs

- Raw `address` without prior confirmed resolution → `BLOCKED_EXTERNAL`; use parcel-resolution endpoints first  
- Unconfirmed / blocked / invalid `parcel_resolution_id` → `409`  
- `parcel_resolution_id` combined with another parcel input → `422`  
- `parcel_geometry` alone does not trigger live adapters → `BLOCKED_INPUT` (unless validation-only failures)  
- Path traversal / paths outside approved roots → `400`  
- Multi-feature FeatureCollection → `400`  
- Multiple parcel input fields → `400`

Approved demo fixture reference:

```text
test-data/land-profiles/land_profile_cper_001.json
```

## Response shape

```json
{
  "investigation_id": "...",
  "status": "QUEUED | RUNNING | COMPLETED | PARTIAL | FAILED | BLOCKED_INPUT | BLOCKED_EXTERNAL",
  "mode": "GOAL_DIRECTED",
  "intended_operation": "COW_CALF_OPERATION",
  "execution_source": "DEMO_FIXTURE",
  "replay_label": "REPLAY_DEMO_FIXTURE_NOT_LIVE",
  "plan_ref": "...",
  "plan_sha256": "...",
  "execution_ref": null,
  "deterministic_execution_hash": null,
  "unified_output_ref": null,
  "unified_output": null,
  "limitations": ["investigation_job_queued"],
  "created_at": "..."
}
```

### Investigation job states

| Status | Meaning |
|---|---|
| `QUEUED` | Accepted; waiting for single-flight worker claim |
| `RUNNING` | Worker claimed; step states update on `/trace` |
| `COMPLETED` | Executor `SUCCEEDED` |
| `PARTIAL` | Factor-local / Mireye partial failures preserved |
| `FAILED` | Hard failure (e.g. geometry) |
| `BLOCKED_EXTERNAL` / `BLOCKED_INPUT` | Terminal sync reject (no fabricated geometry / no silent fixture) |

Rules:

- One investigation_id executes at most once (`try_claim` QUEUED→RUNNING).
- `/report` and `/buyer-report` require terminal status + Unified Output (409 while QUEUED/RUNNING).
- LIVE vs FIXTURE / BLOCKED_EXTERNAL remain explicit; never silent fixture fallback.
- F01–F08 science, Engine, Unified Output projection, and Report Validator are unchanged.
`PARCEL_RESOLUTION` investigations also include `parcel_resolution_id`, `geometry_hash`, `geometry_reference`, `source_crs`. Factor live collection for arbitrary resolved geometries is not performed in this prototype (expect `PARTIAL` with explicit limitations).

## Trace / report

- Trace: step_id, tool_id, action, status, reuse refs, failures, artifact refs — no credentials  
- Report: Property / Land & Resources / Resilience & Hazards / Operation Comparison / Diligence Plan from `unified_output.buyer_report` only

## Security

- No `MIREYE_API_KEY` in responses  
- No Authorization headers logged  
- GeoJSON body size limit  
- CORS restricted to local prototype origins  
- No arbitrary URL fetch from user input  

## Governance

One parcel; Engine authoritative; HOLD ≠ unsuitable; no numeric score; no legal conclusion; `explanation_binding_hash == match_result_hash`; planned_actions diligence-only.
