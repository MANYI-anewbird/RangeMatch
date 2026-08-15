# Advisor Parcel Confirmation Gate

> Status: `GATED — REQUIRED FOR FULL ADVISOR INVESTIGATION`  
> Date: 2026-08-12  
> Depends on: `docs/PARCEL_RESOLUTION_CONTRACT.md`, `docs/MIREYE_LIVE_PARCEL_RESOLVER_CONTRACT.md`  
> Module: `src/rangematch/advisor_parcel_gate.py`  
> Advisor: `src/rangematch/advisor_agent.py`

## Purpose

Freeze the rule that **Mireye-first entry is not enough for a complete Advisor report**.

```text
Mireye /lookup  →  location may be recognized
User confirms exactly one polygon  →  PARCEL_CONFIRMED
Only then  →  full evidence investigation / Generic Packet / Buyer Report
```

This gate **reuses** the existing parcel-resolution confirm path. It does **not** invent a second confirmation schema.

## Authority

| Concern | Source of truth |
|---|---|
| Polygon source | Candidate / confirmed `provenance.source` + `provider` (e.g. `REGRID via Mireye`) |
| Geometry identity | `confirmed_parcel.geometry_hash` (SHA-256 of canonical one-Feature FC) |
| User confirm record | `selection.{selected_candidate_id, confirmed_at, confirmation_method}` |
| Multi-candidate / multi-APN | Exactly one `selected_candidate_id`; APN is never an entry path |
| Full Advisor investigation | `status == PARCEL_CONFIRMED` |

## Hard gate

Full Advisor investigation (Generic Packet → action policy → three-page report) may proceed only when:

```yaml
status: PARCEL_CONFIRMED
confirmed_parcel:
  parcel_geometry: <one-Feature Polygon|MultiPolygon FC>
  geometry_hash: <64-char sha256 hex>
  geometry_reference: <string>
  source_crs: EPSG:4326
selection:
  selected_candidate_id: <string>
  confirmed_at: <ISO-8601>
  confirmation_method: USER_BOUNDARY_CONFIRMATION
```

Without that record:

- `parcel_geometry_confirmed` must remain `false`
- Advisor must not emit a complete Buyer Report for a random address
- `location_resolved=true` must never be labeled “Parcel confirmed”

## Advisor outcome mapping

| Parcel resolution | Advisor `investigation_outcome` |
|---|---|
| `NEEDS_USER_SELECTION` / `NEEDS_BOUNDARY_CONFIRMATION` | `PARCEL_NEEDS_CONFIRMATION` |
| Confirmed + Generic Packet path complete | `EVIDENCE_INVESTIGATION_COMPLETED` |
| Confirmed + Packet/policy not yet available | `EVIDENCE_INVESTIGATION_INCOMPLETE` |
| Lookup / transport / no usable polygon | `INVESTIGATION_COULD_NOT_COMPLETE` (or limited location-only incomplete when location resolved without fabric) |

## Multi-APN / multi-candidate

- Mireye `clarify` or multiple valid polygons → `NEEDS_USER_SELECTION`
- Never auto-pick the first candidate
- Soft `attributes.apn` labels are unverified; they do not prove identity
- APN-only lookup remains unsupported (`MIREYE_LIVE_PARCEL_RESOLVER_CONTRACT.md`)

## CPER Challenge Demo exception (frozen)

The CPER engineering complete path may bind fixture geometry **after** a successful Mireye location resolve for the canonical CPER demo address only:

```text
geometry_source = CPER_ENGINEERING_FIXTURE
parcel_geometry_confirmed = true   # investigation object for Demo only
confirmation_method ≠ USER_BOUNDARY_CONFIRMATION
```

This exception:

- must not apply to any other address
- must not silently substitute CPER geometry for LIVE unmatched inputs
- is not a nationwide confirmation model

## API binding

| Step | API |
|---|---|
| Start / stage candidates | Existing `POST /v1/parcel-resolutions` **or** Advisor staging helper that writes the same record shape |
| Confirm boundary | `POST /v1/parcel-resolutions/{id}/confirm` with `explicit_confirmation` + `expected_geometry_hash` |
| Continue Advisor | `POST /v1/advisor/runs` with `parcel_resolution_id` of a `PARCEL_CONFIRMED` record |

## Non-goals (this gate)

- Durable resolution storage beyond the current in-memory store
- APN entry, multi-parcel confirm, freehand draw, boundary upload
- Treating confirmation as a CPER report

## Success for this slice

1. Contract frozen and referenced by Advisor.
2. Unique Mireye polygon candidates stage a real resolution id and stop at `PARCEL_NEEDS_CONFIRMATION`.
3. Confirmed non-CPER resolution sets `parcel_geometry_confirmed=true` and continues to Generic Packet / brief — never a CPER report.
4. Tests use hooks/fixtures only — no live network.
