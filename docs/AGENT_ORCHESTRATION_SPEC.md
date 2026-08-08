# RangeMatch Agent Orchestration Spec (v0.2 draft)

> Status: `DRAFT_FOR_PROTOTYPE`  
> Date: 2026-08-08  
> Phase: Product Prototype + Agent Orchestration  
> Frozen Factors: `F01–F08` (`demo_factor_scope: CLOSED`)  
> F09+: `NOT_AUTHORIZED`

## Purpose

Define the **call order** when the Agent receives an address or parcel. The Agent plans and explains; it does **not** invent Land Facts, thresholds, rankings, or override the deterministic engine.

The competition prototype evaluates **one parcel per run**. Batch search, portfolio screening, region-wide site discovery, and the Mireye ICP Finder pattern are explicitly deferred.

## User modes

### Goal-directed

The user identifies an intended supported operation, for example Cow-Calf. The selected Profile is investigated first because it reflects user intent. The peer Sheep Profile may still be displayed as an alternative comparison. User priority does not make either Profile scientifically primary.

### Discovery

The user asks what the parcel may support without selecting an operation. Cow-Calf and Sheep are evaluated equally against the same Land Profile. The Agent must qualify any comparison as applying only to the currently supported Profiles; it must not claim to discover the objectively best use of the land.

## Authority split

| Layer | May do | Must not do |
|---|---|---|
| Agent Planner | Resolve place → geometry; choose tools; sequence fetches; explain MatchResult | Invent values, scores, or decisions |
| Mireye | Point / diligence context reads | Replace parcel RAP/SDA/NOAA/TIGER Land Facts |
| External adapters | Approved parcel paths (RAP, SDA, NOAA, TIGER, geometry) | Silent duplicate fetches of hash-complete artifacts |
| Deterministic engine | Emit Factor signals, HOLD/unknowns/diligence | Be overridden by LLM |

## Input contract

Accepted entry points (one per run):

1. **Address / place string** → geocode / resolve → candidate parcel geometry  
2. **Parcel geometry** (GeoJSON Feature / FeatureCollection with exactly one Feature)  
3. **Existing Land Profile** (re-evaluate only; skip fetch when provenance-complete)

The run also records:

```yaml
mode: GOAL_DIRECTED | DISCOVERY
intended_operation: COW_CALF | SHEEP_GRAZING | null
```

`intended_operation` is required for `GOAL_DIRECTED` and must be null for `DISCOVERY`.

Required before Factor work:

```text
geometry_id, geometry_reference, geometry_hash, source_crs=EPSG:4326
```

Geometry hash change **invalidates** F01–F08 evidence and forces recompute.

## Canonical tool order

```text
1. Resolve geometry
   address/place → parcel candidate(s) → bind geometry + hash
   OR accept supplied parcel geometry

2. Mireye context (point / diligence) — non-authoritative for parcel Land Facts
   a. Property Diligence / lookup  # resolve parcel, jurisdiction, zoning/property context
   b. Land Read                    # terrain, soil, land-cover / land-use point context
   c. Hazards Read                 # flood, wetland, wildfire-related point triggers
   Store as POINT_QA / diligence context only.
   Do not promote Mireye point fields to F01–F08 Land Facts.
   Check disposition, parcel_grade, confidence, provenance, and partial_failures.

3. Parcel Factor collection (F01–F08 frozen paths only)
   Prefer reuse of provenance-complete artifacts (geometry_hash + year/mask/source key).
   Suggested dependency-aware order:
     F06 Parcel Configuration          # geometry metrics; no remote required
     F01 Topography                    # approved DEM path
     F02 Herbaceous (RAP cover/production)
     F08 Woody/Shrub                   # MUST reuse F02 coverV3 artifact; no duplicate RAP
     F04 Soil / wetness / ecological site  # SDA primary; Mireye soil = QA only
     F05 Climate / drought             # NOAA precip canonical; Mireye drought = QA
     F03 Livestock water               # mapped candidates + evidence workflow
     F07 Road / physical access        # TIGER 2025 All Roads

4. Assemble Land Profile
   Attach Land Facts, applicability, coverage, provenance, limitations, unknowns.

5. Deterministic engine
   evaluate_land_profile → MatchResult
   (Cow-Calf / Sheep peer; ranking_effect remains NONE unless later reviewed)

6. Explanation + diligence packaging
   Constrained explanation bound to MatchResult.
   Surface unknowns and diligence actions (including regulatory/land-rights
   follow-ups as dynamic investigation — not as new frozen Factors).

7. Product surface
   Buyer-oriented UI / demo closure narrative from MatchResult only.
```

## Hard routing rules

1. **No F09+ Factor** without new authorization.  
2. **F08 reuses F02** `coverV3` artifact (same hash/year/mask/applicability/coverage).  
3. **No duplicate remote call** when a complete artifact already exists for the request key.  
4. **Mireye ≠ parcel truth** for RAP/SDA/NOAA/TIGER Land Facts.  
5. Missing / unquantified / conflicting evidence → `UNKNOWN` or `NEEDS_VERIFICATION`; never invent.  
6. Engine decisions and Factor signals are authoritative; Agent may only restate them.  
7. Regulatory & land-rights work is a **dynamic diligence workflow**, not a new Factor in this phase.
8. One parcel per run; no batch list, ICP screening, portfolio ranking, or region-search workflow in the prototype.
9. Goal-directed priority changes investigation order only; it does not change Profile rules or evidence standards.
10. Discovery evaluates Cow-Calf and Sheep as peers and must state that the comparison is limited to supported Profiles.

## Minimal planner outputs

Each run should produce:

```yaml
plan_id: ...
mode: GOAL_DIRECTED | DISCOVERY
intended_operation: COW_CALF | SHEEP_GRAZING | null
geometry: { geometry_id, geometry_hash, geometry_reference }
tool_calls: [ { tool, purpose, reuse_or_fetch } ]
mireye_context_refs: [...]
land_profile_ref: ...
match_result_ref: ...
explanation_ref: ...
open_diligence: [...]
prohibited_claims_applied: true
```

## Out of scope for this draft

- Full tool schema / OpenAPI  
- Buyer UI wireframes  
- Regulatory workflow detail (separate doc after planner stub)  
- Competition demo script (after orchestration + UI skeleton)  
- Unifying F01–F08 output contract schema (next short doc recommended)
- Batch parcel search, portfolio ranking, ICP Finder, or regional site discovery

## Immediate next docs

1. `F01_F08_UNIFIED_OUTPUT_CONTRACT.md` — frozen Factor → Land Profile / MatchResult shape  
2. Mireye Property Diligence / Land / Hazards adapter notes  
3. Planner tool-routing stub (code) bound to this order
