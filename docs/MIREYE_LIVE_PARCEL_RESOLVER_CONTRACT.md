# Mireye Live Parcel Resolver Contract

> Status: `IMPLEMENTED — LIVE_VERIFIED_ON_CLEAN_NETWORK`  
> Date: 2026-08-08  
> Authority: Mireye public docs (Authentication, Geocode, Lookup, Field Catalog, Privacy) + RangeMatch parcel-resolution state machine  
> Related: `PARCEL_RESOLUTION_CONTRACT.md`, `MIREYE_PROTOTYPE_ADAPTER_CONTRACTS.md`, `mireye_adapter.py`, `mireye_parcel_resolver.py`  
> Implemented: offline fixtures + controlled live `/lookup` transport + parcel mapping + confirmation flow  
> Live verification: passed on a clean network; historical SafeBrowse failures remain dated incident records  
> Regrid licensing: does **not** block competition Demo; blocks commercial cache / redistribution / owner PII display only

## Purpose

Define the implemented **live data and governance contract** for using Mireye `/v1/lookup` as the RangeMatch Live Parcel Resolver.

Competition Demo land entries (both must converge on the same confirm flow):

```text
ADDRESS  → POST /v1/lookup  { kind: "address", input: "<full US address>", include_parcel: true }
COORDINATE → POST /v1/lookup { kind: "coord", input: "<lat>,<lng>", include_parcel: true }
```

Direction check:

```text
RangeMatch rules already align with Mireye:
  address ≠ coordinate
  coordinate ≠ parcel boundary
  parcel boundary requires explicit user confirmation
  null / partial_failures must remain visible
  no silent fixture substitution on live failure
  no auto buffer / circle from a pin
```

Gaps this document closes: auth env naming, geocode quality gate, `/lookup` disposition mapping, `parcel_unavailable` independence, retry policy, Field Catalog version/ETag gate, address privacy disclosure, Regrid licensing confirmation.

## Candidate live path

```text
ADDRESS path:
  full U.S. street address
    → Mireye POST /v1/lookup (kind=address, Bearer token)
    → persist normalized_address + accuracy_type
    → geocode quality gate (rooftop / nearest_rooftop_match)
    → disposition: resolved | clarify | no_match
    → if resolved: check parcel geometry AND parcel_unavailable
    → deterministic geometry validation
    → map select / confirm
    → PARCEL_CONFIRMED → Planner / F01–F08

COORDINATE path:
  map pin or lat,lng
    → validate format + U.S. envelope + lat/lng swap
    → Mireye POST /v1/lookup (kind=coord)
    → same disposition / geometry / confirm rules
    → pin is NEVER F01–F08 geometry and NEVER auto-buffered
```

Point context remains separate:

```text
Mireye POST /v1/fetch → POINT_LAND_CONTEXT / POINT_HAZARD_CONTEXT
  ≠ parcel-wide RAP / 3DEP / NOAA / SDA Land Facts
```

**Forbidden:**

```text
disposition == resolved  →  auto PARCEL_CONFIRMED
query pin / geocode point → F01–F08 geometry
query pin → fabricated circle / buffer parcel
```
## 1. Authentication

Official: `Authorization: Bearer <token>` only.  
Do **not** put the token in URL query params or custom API-key headers.  
Dashboard API tokens: default ~90-day expiry ([Mireye Authentication](https://docs.mireye.ai/authentication)).

### Environment variables

| Name | Role |
|---|---|
| `MIREYE_API_TOKEN` | **Canonical** credential name (matches Mireye docs) |
| `MIREYE_API_KEY` | Legacy alias — still accepted |
| `MIREYE_API_BASE_URL` | API origin (validated against official host) |

Resolution order:

```text
1. MIREYE_API_TOKEN (if non-empty)
2. MIREYE_API_KEY (if non-empty)
3. else NOT_CONFIGURED / missing
```

Never log or return the token. Prefer documenting `MIREYE_API_TOKEN` in `.env.example` and runbooks; keep `MIREYE_API_KEY` for existing local `.env` files.

## 2. Geocode quality gate

Mireye geocoding is lossy. Only these accuracy types may enter **parcel-level** lookup consideration ([Mireye Geocode](https://docs.mireye.ai/api-reference/geocode)):

```text
rooftop
nearest_rooftop_match
```

Not parcel-quality (examples): `range_interpolation`, street center, place centroid — rural interpolation may be kilometers off.

Live adapter **must persist** on the resolution record / geocode block:

```yaml
accuracy: <number|null>
accuracy_type: <string|null>
match_type: <string|null>
normalized_address: <string|null>
provider: Mireye
```

If accuracy is not parcel-quality:

```text
→ status GEOCODE_QUALITY_INSUFFICIENT (terminal for this attempt)
→ never auto-advance toward PARCEL_CONFIRMED
→ show normalized_address to the user
→ require a better address OR switch to Drop a pin / Enter coordinates
→ do not invent polygons; do not accept user freehand draw in this Demo
```

Still true: even rooftop quality **does not** make the geocode point a parcel boundary.

## 3. `/v1/lookup` disposition → Parcel Resolution status

Official dispositions: `resolved` | `clarify` | `no_match` ([Mireye Lookup](https://docs.mireye.ai/api-reference/lookup)).

| Mireye outcome | RangeMatch `status` | Notes |
|---|---|---|
| `resolved` + usable `parcel.geometry` | `NEEDS_BOUNDARY_CONFIRMATION` | Single candidate; user must still confirm |
| `clarify` (≤3 candidates) | `NEEDS_USER_SELECTION` | **Never** silent-pick first |
| `no_match` | `NO_MATCH` | Honest failure |
| `resolved` + `parcel_unavailable: true` (or missing geometry) | `PARCEL_DATA_UNAVAILABLE` | Address resolved; parcel fabric missing |
| Transport / TLS / auth failure after bounded retry | `BLOCKED_EXTERNAL` | Visible; no fixture swap |
| Geometry fails validation | `INVALID_GEOMETRY` | Deterministic reject |

`clarify` candidates are parcel **candidates** for the existing map UI — same confirmation rules as FIXTURE multi-candidate.

### APN-only

Mireye `/lookup` does **not** support Regrid attribute-search-by-APN today (`no_match` / `apn_not_supported_in_v1`).  
Do **not** market “enter any APN to analyze.” Competition Demo supported live entries:

- full street address (`kind=address`)  
- coordinates / map pin (`kind=coord`)  

**Not supported:** APN, boundary file upload, batch addresses, multi-parcel select, freehand draw, nationwide land search.
## 4. `resolved` ≠ parcel success

Even when disposition is `resolved`, Mireye may return:

```yaml
disposition: resolved
parcel_unavailable: true
parcel_unavailable_reason: regrid_quota_exhausted | no_parcel_at_point | parcel_match_too_far | parcel_lookup_transient_error | parcel_lookup_malformed_response | ...
```

Mandatory independent checks before confirmation is even offered:

```text
1. parcel.geometry exists
2. parcel_unavailable is not true
3. geometry passes RangeMatch validation (Polygon/MultiPolygon, EPSG:4326, one Feature after confirm)
4. user explicitly confirms boundary on the map
```

Preserve `parcel_unavailable` and `parcel_unavailable_reason` on provenance / limitations.  
Provenance for Regrid-sourced geometry must state `source: REGRID via Mireye` (not “federal cadastral”).

## 5. Retry policy

Honor Mireye `retryable` and `Retry-After` ([docs examples](https://docs.mireye.ai/api-reference/lookup)):

| Example | Behavior |
|---|---|
| `429` `resolve_busy` | Retry only if `retryable`; honor `Retry-After` (e.g. 3s) |
| `504` `resolve_timeout` | Bounded retry; honor `Retry-After` (e.g. 5s) |
| `422` invalid input | **No** retry |
| `404` address too coarse | **No** retry — ask user to refine address |
| `401` / auth_* | **No** blind retry |

Rules:

```text
retry only when retryable=true
→ bounded attempts
→ honor Retry-After
→ final failure remains visible (BLOCKED_EXTERNAL or mapped status)
→ never substitute FIXTURE / CPER success
```

## 6. Null and partial failures

Unchanged from existing adapter authority ([Mireye Introduction](https://docs.mireye.ai/introduction)):

- field-level failures → `partial_failures`  
- legitimate absence → `null` interpreted via Field Catalog `null_meaning`  
- never coerce null → 0 / false / “no risk”

## 7. Field Catalog version / ETag gate

Public catalog: `GET /v1/meta/fields` ([Field Catalog](https://docs.mireye.ai/api-reference/meta-fields)).

**Implemented (offline-first):** `src/rangematch/mireye_catalog_gate.py`

```text
FIXTURE: evaluate mireye/fixtures/field_catalog_v0.14.0.json
  → required fields + units/types from MIREYE_FIELD_USAGE_REGISTRY
  → major version must match pinned 0.14.x
  → status COMPATIBLE | INCOMPATIBLE
  → affects_parcel_resolution: always false

LIVE (gated): GET /v1/meta/fields without auth
  → If-None-Match / ETag → 304 NOT_MODIFIED
  → transport failure → FETCH_FAILED (not a parcel failure)
  → requires allow_network / RANGEMATCH_MIREYE_CATALOG_LIVE
```

API:

- `GET /health` includes `mireye_catalog_gate` (fixture evaluate; no live probe)
- `POST /v1/mireye/catalog-gate` with `{ "mode": "FIXTURE"|"LIVE", "allow_network": false }`

Do not permanently hardcode that `0.14.0` remains correct forever — pin for Demo, re-check on live refresh, block on major drift.

## 8. Address privacy disclosure

Mireye may log API requests for reliability, abuse prevention, and billing; queries are not used for model training; addresses and resolved coordinates from `/lookup` may be retained ~30 days for audit ([Privacy](https://www.mireye.com/privacy), [Lookup retention](https://docs.mireye.ai/api-reference/lookup)).

Product copy (buyer / privacy notice) should include:

> Property addresses sent for live resolution may be logged and retained by the geospatial provider for reliability and audit purposes.

If a user cannot accept address retention: geocode client-side (or elsewhere) and send only coordinates to `/fetch` or `/ask` — understanding that may forgo `/lookup` parcel geometry.

## 9. Regrid licensing — commercial / PII gate (not Demo-blocking)

`/lookup` parcel payload may include geometry, APN, area, zoning, owner, assessed value, sale records; free/growth tiers may null premium fields.

**Competition Demo:** may use returned geometry for **one investigation + user map confirmation** once network works. Licensing answers are **not** a Demo blocker.

**Blocked until written answers (commercial / redistribution / PII):**

1. May RangeMatch persist parcel geometry returned by `/v1/lookup` beyond a single investigation / long-term cache?  
2. May we display that geometry in a buyer-facing map/report at commercial scale / redistribution?  
3. What attribution is required?  
4. May we cache APN, zoning, assessed value, and sale history across users/sessions?  
5. Are owner-name fields permitted in our UI?  
6. Does the competition / current account include Regrid parcel calls nationwide?  
7. What happens after free/growth-tier credits expire?

### Until commercial answers arrive (Demo-safe posture)

```text
✓ competition Demo: one-shot geometry + user confirmation (when network available)
✓ provenance: source = REGRID via Mireye
✗ do not display or store owner names
✗ do not claim parcel data is purely federal
✗ do not assume nationwide parcel success rates
✗ no long-term commercial cache / redistribution of Regrid payloads
```
### Short confirmation email (template)

```text
Subject: RangeMatch — Regrid parcel geometry licensing via Mireye /v1/lookup

Hello Mireye team,

RangeMatch is evaluating /v1/lookup as our live address → parcel candidate path
(Regrid geometry for user confirmation on a diligence map, then deterministic
Factor analysis). We already use Bearer dashboard tokens and will not place
credentials in query strings.

Please confirm:

1. May we persist parcel geometry returned by /v1/lookup for a single investigation?
2. May we display that geometry in a buyer-facing map and report?
3. Required attribution text?
4. May we cache APN, zoning, assessed value, and sale history?
5. Are owner-name fields permitted in UI / stored records?
6. Does our account tier include nationwide Regrid parcel calls?
7. Behavior after free/growth credits expire?

We will keep owner fields redacted until you confirm otherwise.

Thank you,
[Name]
```

## Implementation checklist

- [x] Document auth: `MIREYE_API_TOKEN` canonical + `MIREYE_API_KEY` alias  
- [x] Document `/lookup` → Parcel Resolution status map  
- [x] Document geocode `accuracy_type` gate + required persisted fields  
- [x] Document independent `parcel_unavailable` handling → `PARCEL_DATA_UNAVAILABLE`  
- [x] Document Catalog version/ETag compatibility gate  
- [x] Document privacy + Regrid licensing email  
- [x] Offline Mireye parcel resolver adapter + fixture tests (`mireye_parcel_resolver.py`)  
- [x] Catalog ETag/version compatibility gate (`GET /v1/meta/fields`, public; offline fixture + gated LIVE fetch)  
- [x] Live HTTP `/lookup` transport on same `LiveParcelResolver` (Bearer; retryable; no fixture swap)  
- [ ] Live gate on non-intercepted network (one U.S. address → confirm → Investigation)  
- [ ] Then `/v1/fetch` Land/Hazard context verification  
- [ ] Regrid commercial/PII licensing answers (not a Demo blocker)  
## Explicit non-changes

- F01–F08 Factor science and thresholds  
- Engine HOLD-only ranking stance  
- Report Validator trusted-evidence rules  
- FIXTURE parcel resolver behavior (still the only working offline path)  
- Silent LIVE → FIXTURE fallback  
