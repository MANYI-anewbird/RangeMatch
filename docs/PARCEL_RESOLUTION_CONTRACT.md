# Parcel Resolution Contract

> Status: `IMPLEMENTED — DUAL_LAND_ENTRY; LIVE_MIREYE_RESOLVER + FIXTURE_MODE + MAP_CONFIRMATION`  
> Date: 2026-08-08  
> Schema: `docs/schemas/parcel_resolution.schema.json`  
> Module: `src/rangematch/parcel_resolution.py`  
> Coordinates: `src/rangematch/coordinates.py`  
> Store: `src/rangematch/parcel_resolution_store.py` (in-memory; restart clears)  
> API: `src/rangematch/api.py` (`/v1/parcel-resolutions*`)  
> Fixtures: `test-data/parcel-resolution/`  
> Live contract: `docs/MIREYE_LIVE_PARCEL_RESOLVER_CONTRACT.md`  
> Scope: address **or** coordinates → parcel candidate → user confirmation → Planner-ready geometry → investigation binding  
> Non-goals: APN-only lookup; boundary upload; batch; multi-parcel selection; freehand boundary drawing; F09; 3D

## Purpose

Insert **parcel selection before** the existing investigation workflow. Competition Demo locks **two land entries** that converge on the **same** confirmation path:

```text
1. Search by address          (input_kind=ADDRESS)
2. Drop a pin / Enter coords  (input_kind=COORDINATE — one type, two UIs)

ADDRESS:
  full U.S. street address
    → Mireye /lookup(kind=address)   [LIVE]
    → parcel candidate(s)

COORDINATE:
  map click or lat,lng
    → validate format + U.S. envelope + lat/lng swap detection
    → Mireye /lookup(kind=coord)     [LIVE]
    → parcel candidate(s)

BOTH:
  → show parcel polygon(s)
  → user confirms exactly one boundary
  → General / Cattle / Sheep
  → Start Analysis → Planner investigation
```

This contract binds **cadastral / parcel-boundary geometry** for Planner entry. It does **not** reopen F01–F08 Factor science, Engine rules, Unified Output projection, or Buyer Report validation.

## Authority

```yaml
deterministic_code_must:
  - normalize and validate ADDRESS or COORDINATE input / geocode / candidate / confirmation state
  - validate U.S. query points (format, envelope, lat/lng swap) for COORDINATE
  - validate candidate geometry (type, CRS, one-Feature FeatureCollection)
  - compute geometry_hash and bind provenance
  - refuse fabricated, buffered, circular, or inferred polygons from an address or pin
  - refuse treating geocode point or pin as F01–F08 geometry
  - refuse silent CPER / fixture substitution for live or unmatched inputs

llm_may:
  - interpret messy address intent into a candidate string for deterministic normalize
  - explain ambiguity / multiple candidates in buyer language

llm_must_not:
  - invent or repair parcel boundaries
  - invent APN / ownership / zoning / legal access / purchasability as verified
  - silently substitute demo geometries (including CPER)
```

Engine remains authoritative for Cow-Calf / Sheep decisions (currently HOLD-only, no approved ranking). Parcel resolution only supplies geometry binding.

## Resolution states

| Status | Meaning |
|---|---|
| `ADDRESS_ACCEPTED` | Raw address accepted and normalized |
| `GEOCODED` | Geocode produced a point (not a parcel) |
| `PARCEL_CANDIDATES_FOUND` | Lookup returned ≥1 candidate records |
| `NEEDS_USER_SELECTION` | Multiple candidates; user must pick exactly one |
| `NEEDS_BOUNDARY_CONFIRMATION` | Exactly one candidate selected (or only one found); user must confirm boundary |
| `PARCEL_CONFIRMED` | User confirmed; geometry validated; Planner-ready binding present |
| `NO_MATCH` | No parcel candidates (including geocode OK + lookup empty/fail) |
| `AMBIGUOUS` | Geocode or parcel match too ambiguous to present a safe candidate set |
| `BLOCKED_EXTERNAL` | External geocode/parcel provider unavailable or blocked |
| `INVALID_GEOMETRY` | Candidate/confirmation geometry failed contract checks |
| `PARCEL_DATA_UNAVAILABLE` | Address/location resolved, but provider returned no usable parcel geometry (`parcel_unavailable` or missing geometry) |
| `GEOCODE_QUALITY_INSUFFICIENT` | Geocode accuracy is not parcel-quality (`rooftop` / `nearest_rooftop_match` only for live parcel lookup) |

Terminal failure / blocked states: `NO_MATCH`, `AMBIGUOUS`, `BLOCKED_EXTERNAL`, `INVALID_GEOMETRY`, `PARCEL_DATA_UNAVAILABLE`, `GEOCODE_QUALITY_INSUFFICIENT`.  
Only `PARCEL_CONFIRMED` may enter RangeMatch investigation with bound geometry.

### Mireye `/v1/lookup` mapping (implemented)

See `MIREYE_LIVE_PARCEL_RESOLVER_CONTRACT.md`. Summary:

| Mireye | RangeMatch |
|---|---|
| `resolved` + parcel geometry | `NEEDS_BOUNDARY_CONFIRMATION` |
| `clarify` | `NEEDS_USER_SELECTION` |
| `no_match` | `NO_MATCH` |
| `resolved` + `parcel_unavailable` | `PARCEL_DATA_UNAVAILABLE` |
| non-parcel-quality geocode | `GEOCODE_QUALITY_INSUFFICIENT` |
| transport failure | `BLOCKED_EXTERNAL` |

`disposition == resolved` never implies `PARCEL_CONFIRMED`.

## State machine

```text
                  ┌─────────────────────┐
                  │  ADDRESS_ACCEPTED   │
                  └──────────┬──────────┘
                             │ geocode
              ┌──────────────┼──────────────────┐
              ▼              ▼                  ▼
        BLOCKED_EXTERNAL  AMBIGUOUS /        GEOCODED
                          NO_MATCH              │
                                                │ find candidates
                     ┌──────────────────────────┼────────────────────┐
                     ▼                          ▼                    ▼
               BLOCKED_EXTERNAL            NO_MATCH        PARCEL_CANDIDATES_FOUND
               / INVALID_GEOMETRY                                │
                                      ┌──────────────────────────┤
                                      ▼                          ▼
                            NEEDS_USER_SELECTION      NEEDS_BOUNDARY_CONFIRMATION
                                      │               (single candidate)
                                      │ user selects
                                      └──────────────► NEEDS_BOUNDARY_CONFIRMATION
                                                              │
                                                              │ user confirms
                                                              ▼
                                                       PARCEL_CONFIRMED
                                                              │
                                              geometry change after confirm
                                                              ▼
                                              new geometry_hash +
                                              evidence_invalidation_required
                                              → NEEDS_BOUNDARY_CONFIRMATION
```

Rules:

1. **Exactly one** confirmed parcel may enter RangeMatch.  
2. Address text is **not** parcel geometry.  
3. A geocoded point / dropped pin / entered `lat,lng` is **not** a parcel boundary and **not** F01–F08 geometry.  
4. Never fabricate, buffer, circle, or infer a parcel polygon from an address or query point.  
5. Never silently substitute CPER or another fixture.  
6. Multiple candidates → `NEEDS_USER_SELECTION` (no auto-pick).  
7. A single candidate still → `NEEDS_BOUNDARY_CONFIRMATION`.  
8. Confirmed geometry must be `Polygon` or `MultiPolygon` in `EPSG:4326`.  
9. After confirmation, FeatureCollection must contain **exactly one** Feature.  
10. Geometry changes → new `geometry_hash` and invalidate prior F01–F08 evidence (reuse `geometry_replace` semantics when Land Profile exists).  
11. Ownership, APN, zoning, legal access, purchasability are **unverified** unless independently supported — never treated as proven by this adapter alone.  
12. No LLM may invent or repair boundaries; deterministic code validates geometry and confirmation state.  
13. ADDRESS requires a full U.S. street address; persist `normalized_address` and geocode `accuracy_type`; non-parcel-quality geocode → `GEOCODE_QUALITY_INSUFFICIENT` (prompt map/coords entry).  
14. COORDINATE: validate format + U.S. envelope; detect lat/lng swap; lookup point only.  
15. Not supported in this Demo: APN, boundary upload, batch addresses, multi-parcel select, freehand draw, nationwide land search.

## Adapter interface

```text
ParcelResolver
  normalize_address(raw_address) -> NormalizedAddress
  geocode_address(normalized) -> GeocodeResult
  find_parcel_candidates(geocode) -> list[ParcelCandidate]
  validate_candidate(candidate) -> CandidateValidation
  confirm_parcel(resolution, candidate_id, *, confirmation) -> ResolutionRecord
```

| Mode | Behavior (this slice) |
|---|---|
| `FIXTURE` / `OFFLINE` | Load explicit scenario fixtures under `test-data/parcel-resolution/`; no network |
| `LIVE` | Controlled Mireye `/v1/lookup` transport for address or coordinate input; requires explicit network authorization and configured token; must not fall back to CPER or fixtures |

Environment:

```bash
RANGEMATCH_PARCEL_RESOLVER=FIXTURE   # safe default
MIREYE_API_TOKEN=...                 # required for controlled LIVE mode
```

## Confirmed parcel → Planner input

`PARCEL_CONFIRMED` must expose bindings directly usable by `build_investigation_plan(..., parcel_geometry=...)`:

| Field | Requirement |
|---|---|
| `parcel_geometry` | GeoJSON FeatureCollection with exactly one Feature; geometry Polygon or MultiPolygon |
| `geometry_reference` | Stable source/reference string (fixture path, provider URI, or registry id) |
| `geometry_hash` | SHA-256 hex (64) of canonical GeoJSON for the confirmed FeatureCollection |
| `source_crs` | `EPSG:4326` |

Also retained on the resolution record: `geometry_id`, full provenance, limitations, and unverified attribute caveats.

## Provenance contract

Every candidate and the confirmed parcel must preserve:

| Field | Notes |
|---|---|
| `source` | Human/registry name of boundary source |
| `provider` | Adapter/provider id (`FIXTURE`, future live id) |
| `request_id` / `reference_id` | Provider request or fixture reference |
| `retrieved_at` | ISO-8601 UTC when retrieved (fixture: scenario timestamp) |
| `source_crs` | CRS as provided by source |
| `normalized_crs` | Must be `EPSG:4326` after acceptance |
| `geometry_hash` | Canonical hash of normalized geometry payload |
| `confidence` / `status` | Provider confidence + resolution status |
| `limitations` | Explicit caveats (unverified APN/ownership, fixture-only, etc.) |

## Prohibited behaviors

- Treating address text, geocode Point, or query pin as parcel boundary or F01–F08 geometry  
- Buffering / circles / convex-hull / voronoi / “reasonable acre” polygon invention  
- Auto-confirming the only candidate without `NEEDS_BOUNDARY_CONFIRMATION`  
- Auto-selecting among multiple candidates  
- Silent CPER or any demo geometry substitution when LIVE/unmatched  
- Network calls or API key assumptions in the FIXTURE resolver  
- FeatureCollection with 0 or 2+ Features after confirmation  
- Accepting non-`EPSG:4326` without explicit, tested normalization (unsupported CRS → `INVALID_GEOMETRY` in this slice)  
- Claiming verified ownership, APN, zoning, legal access, or purchasability from this adapter alone  
- LLM inventing or repairing rings / holes / CRS  
- APN entry, boundary file upload, batch addresses, freehand draw, multi-parcel confirm, nationwide search  


## API (implemented)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/parcel-resolutions` | Start resolution from `ADDRESS` or `COORDINATE` |
| `GET` | `/v1/parcel-resolutions/{resolution_id}` | Fetch current resolution record + status |
| `POST` | `/v1/parcel-resolutions/{resolution_id}/confirm` | Explicit boundary confirmation → `PARCEL_CONFIRMED` |

Start body (address):

```json
{
  "input_kind": "ADDRESS",
  "address": "<full U.S. street address>",
  "resolver_mode": "FIXTURE|LIVE",
  "fixture_scenario_id": "<optional>",
  "allow_network": false
}
```

Start body (coordinates — Drop a pin / Enter coordinates share this kind):

```json
{
  "input_kind": "COORDINATE",
  "latitude": 40.495,
  "longitude": -104.895,
  "resolver_mode": "FIXTURE|LIVE",
  "fixture_scenario_id": "<optional>",
  "allow_network": false
}
```

Confirm body:

```json
{
  "selected_candidate_id": "<id>",
  "expected_geometry_hash": "<sha256>",
  "explicit_confirmation": true
}
```

Storage: in-memory via `parcel_resolution_store.InMemoryParcelResolutionStore` (**restart clears state**).  
Investigations may accept `parcel_resolution_id` only when status is `PARCEL_CONFIRMED`.  
Map Intake UI: address vs pin/coords → same confirm → mode → Start Analysis (`web/src/pages/IntakePage.tsx`).

## Geometry hash and evidence invalidation

- Hash input: canonical JSON (`sort_keys`, compact separators) of the confirmed one-Feature FeatureCollection (EPSG:4326).  
- Any geometry mutation after confirmation yields a **new** hash.  
- Downstream Land Profiles / F01–F08 evidence tied to the previous hash must be invalidated (see `geometry_replace.replace_geometry`).  
- This module signals `evidence_invalidation_required: true`; it does not recompute Factor science.

## Fixtures (required coverage)

| Scenario id | Expectation |
|---|---|
| `one_valid_candidate` | ADDRESS → `NEEDS_BOUNDARY_CONFIRMATION` → confirm → `PARCEL_CONFIRMED` |
| `coord_one_valid_candidate` | COORDINATE → same confirmation gate |
| `multiple_candidates` | → `NEEDS_USER_SELECTION` |
| `no_match` | → `NO_MATCH` |
| `geocode_ok_parcel_lookup_fail` | Geocode OK; lookup fails/empty → `NO_MATCH` |
| `blocked_external` | → `BLOCKED_EXTERNAL` |
| `invalid_polygon` | → `INVALID_GEOMETRY` |
| `feature_collection_empty` | → `INVALID_GEOMETRY` |
| `feature_collection_multi` | → `INVALID_GEOMETRY` |
| `unsupported_crs` | → `INVALID_GEOMETRY` |
| `geometry_changed_after_confirmation` | New hash + `evidence_invalidation_required` |
| `address_point_as_boundary` | Point offered as parcel → `INVALID_GEOMETRY` |
| `silent_cper_substitution` | Attempted CPER swap → rejected |

## Remaining production questions

1. **Primary candidate** — Mireye `/v1/lookup` (Regrid geometry nationwide attempt). Direct Regrid purchase is optional only if licensing/quota fails.  
2. **Regrid via Mireye license** — persist geometry? buyer map/report display? attribution? cache APN/zoning/value/sales? owner names? nationwide quota? post-credit behavior? (email template in `MIREYE_LIVE_PARCEL_RESOLVER_CONTRACT.md`)  
3. **Coverage gaps** — rural / unincorporated / multi-county; surface `NO_MATCH` vs `PARCEL_DATA_UNAVAILABLE` vs `AMBIGUOUS`.  
4. **APN** — Mireye v1 does not support APN-only lookup; do not market APN entry until a separate provider exists.  
5. **CRS & topology QA** — reject-only in this product (no silent ring repair).  
6. **PII** — redact owner names until written permission.  
7. **Catalog drift** — live Field Catalog ETag/version gate before promoting point fields (see live contract §7).  
8. **Privacy copy** — disclose ~30-day address/coordinate retention by the geospatial provider.

## Readiness

| Gate | Status |
|---|---|
| Contract + schema + FIXTURE resolver + tests | Done |
| HTTP endpoints + investigation binding | Done (`api.py`) |
| Map confirmation UI | Done (`web/` MapLibre 2D) |
| Mireye live parcel resolver contract | Done |
| LIVE `/lookup` offline mapper + fixtures | Done (`mireye_parcel_resolver.py`) |
| LIVE HTTP `/lookup` | **Implemented and live-verified on a clean network** |
| Silent LIVE→FIXTURE fallback | **Forbidden** |

**Regrid licensing scope:** does **not** block competition Demo or one-shot investigation confirmation. It blocks long-term commercial caching, redistribution, and owner-name display until written answers arrive.

**Recommendation:** Keep FIXTURE as the deterministic replay path and LIVE as the competition user path. Preserve explicit network authorization, Catalog compatibility checks, visible failures, and user confirmation; never auto-confirm on `resolved`.

## Implementation files

- `docs/PARCEL_RESOLUTION_CONTRACT.md`  
- `docs/schemas/parcel_resolution.schema.json`  
- `src/rangematch/parcel_resolution.py`  
- `src/rangematch/parcel_resolution_store.py`  
- `src/rangematch/api.py` (parcel-resolution routes + investigation binding)  
- `tests/test_parcel_resolution.py`  
- `tests/test_api_parcel_resolution.py`  
- `test-data/parcel-resolution/`
