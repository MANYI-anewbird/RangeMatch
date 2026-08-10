# Mireye Prototype Adapter Contracts

> Status: `ACTIVE_PROTOTYPE — LIVE_LOOKUP_AND_CONTEXTS_VERIFIED`  
> Date: 2026-08-08  
> Offline adapter: `src/rangematch/mireye_adapter.py`  
> Live HTTP gate: **verified on a clean network**; earlier TLS/SafeBrowse failures are retained only as historical incident records  
> Role: typed non-canonical context for the Planner

## Authority

Mireye provides **fast investigation context**. It does **not** replace parcel-wide F01–F08 Land Facts from RAP, USGS 3DEP, USDA SDA, NOAA/NCEI, NHD/NAIP, or TIGER.

```text
PROPERTY_DILIGENCE_CONTEXT ≠ title / legal proof
POINT_LAND_CONTEXT ≠ parcel F01 / F02 / F04 / F08 facts
POINT_HAZARD_CONTEXT ≠ final flood / wetland / wildfire determination
```

## A. PROPERTY_DILIGENCE_CONTEXT

| Field | Value |
|---|---|
| `context_type` | `PROPERTY_DILIGENCE_CONTEXT` |
| Intended endpoint | `/v1/lookup` |
| Purpose | Address → jurisdiction / property context; **may also supply Regrid parcel geometry candidates** for Parcel Resolution (see live parcel contract) |
| Preserve | `disposition`, `parcel_unavailable`, `parcel_unavailable_reason`, geocode accuracy fields, `parcel_grade`, `confidence`, failures / partial results |
| Canonical authority | `NON_CANONICAL_CONTEXT` (point/jurisdiction context); parcel **geometry binding** still requires Parcel Resolution confirmation |
| Prohibited promotions | Title opinion, easement proof, legal access certainty, F01–F08 Land Facts; APN-only analysis (unsupported in Mireye v1) |

Failure behavior: keep `disposition` / `parcel_unavailable` / failures explicit; jurisdiction may become `UNKNOWN` or remain `NOT_REQUESTED` — never invent.

**Auth:** `Authorization: Bearer <token>`. Env: canonical `MIREYE_API_TOKEN`, legacy alias `MIREYE_API_KEY`.

**Lookup → Parcel Resolution:** documented in `MIREYE_LIVE_PARCEL_RESOLVER_CONTRACT.md`. Never map `resolved` alone to `PARCEL_CONFIRMED`.

## B. POINT_LAND_CONTEXT

| Field | Value |
|---|---|
| `context_type` | `POINT_LAND_CONTEXT` |
| Intended endpoint | `/v1/fetch` |
| Purpose | Point terrain + reviewed land-cover / land-use fields |
| Spatial semantics | Point / centroid only |
| Canonical authority | `NON_CANONICAL_POINT_QA` |
| Prohibited promotions | Cannot replace parcel-wide F01, F02, F04, or F08 facts |

Failure behavior: mark fields missing; do not fill from LLM; do not promote partial point success to parcel completeness.

## C. POINT_HAZARD_CONTEXT

| Field | Value |
|---|---|
| `context_type` | `POINT_HAZARD_CONTEXT` |
| Intended endpoint | `/v1/fetch` |
| Purpose | Flood / wetland / wildfire-related triggers |
| Preserve | `partial_failures` (must remain visible in plan + product Resilience & Hazards) |
| Canonical authority | `NON_CANONICAL_HAZARD_TRIGGER` |
| Prohibited promotions | Final parcel hazard map, legal compliance, insurance determination |

Failure behavior: surface `partial_failures`; disposition may be `PARTIAL` / `FAILED`; never silently drop.

## Planner placement

Mireye context steps are planned **after** location/geometry is available (resolved address or bound parcel), and **in parallel with each other** when independent. They are not prerequisites for F06 geometry computation unless the only input is an address that needs Property Diligence to obtain a parcel candidate.

## Live adapter readiness

The normalized adapter and controlled live transports are implemented. Mireye `/v1/lookup` parcel resolution and Property/Land/Hazard context calls have been verified on a clean network. The Planner must still fail closed on transport, authentication, partial-field, or catalog errors; it must never replace a failed live call with a fixture. The earlier SafeBrowse/TLS failure documents describe a historical environment incident, not the current product state.

### Live governance gates

| Gate | Requirement |
|---|---|
| Token env | Prefer `MIREYE_API_TOKEN`; accept `MIREYE_API_KEY` |
| Geocode quality | Persist `accuracy` / `accuracy_type` / `match_type`; block non-rooftop for parcel lookup |
| `parcel_unavailable` | Independent of `disposition`; → `PARCEL_DATA_UNAVAILABLE` |
| Retry | Only `retryable=true`; bounded; honor `Retry-After`; no fixture swap |
| Catalog gate | Public `GET /v1/meta/fields`: **implemented** offline (`mireye_catalog_gate.py`); LIVE fetch gated; ETag/version; required fields/units; major drift fail-closed; catalog failure ≠ parcel failure |
| Privacy | Disclose provider address retention (~30 days) |
| Regrid license | Not a competition Demo blocker; required before commercial cache / redistribution / owner PII |

Full text: `docs/MIREYE_LIVE_PARCEL_RESOLVER_CONTRACT.md`.
