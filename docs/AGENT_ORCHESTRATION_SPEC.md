# RangeMatch Agent Orchestration Spec (v0.2)

> Status: `CURRENT_CANONICAL`
> Date: 2026-08-08
> Phase: Product Prototype + Agent Orchestration
> Frozen Factors: `F01–F08` (`demo_factor_scope: CLOSED`)
> F09+: `NOT_AUTHORIZED`
> Current baseline: `docs/CURRENT_SYSTEM_BASELINE.md`

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

## Canonical report order vs execution DAG

Canonical **report** order remains `F01…F08`. Execution is a **dependency DAG** (not that list as a serial chain). See `docs/PLANNER_ROUTING_SPEC.md` and `src/rangematch/planner.py`.

```text
resolve one geometry
→ Mireye PROPERTY/LAND/HAZARD context (non-canonical; after location)
→ F06 COMPUTE (geometry validity/hash/area/CRS)
→ peers in parallel: F01, F02, F03, F04, F05, F07
→ F08 REUSE F02-compatible RAP coverV3 (no duplicate RAP FETCH)
→ assemble Land Profile in report order F01–F08
→ EVALUATE engine → PROJECT unified output
→ GENERATE constrained Buyer Report → VALIDATE against Unified Output
→ RUN bounded Public Diligence official-source search (side branch; no Engine effect)
→ DISPLAY decision dashboard + validated narrative or deterministic fallback + appendix
```

Mireye contracts: `docs/MIREYE_PROTOTYPE_ADAPTER_CONTRACTS.md`.
Unified offline adapter: `src/rangematch/mireye_adapter.py` + `docs/schemas/mireye_normalized_context.schema.json` + `docs/MIREYE_FIELD_USAGE_REGISTRY.yaml`.
Mireye lookup and context adapters are implemented and have passed live checks on a clean network. Historical TLS/SafeBrowse failures remain in dated incident records and still fail closed if they recur.

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

## Unified output envelope

Product runs assemble into `docs/F01_F08_UNIFIED_OUTPUT_CONTRACT.md` (`RANGEMATCH_UNIFIED_OUTPUT@0.1.0`):

```text
run identity + parcel identity
→ Mireye typed context (non-canonical)
→ F01–F08 Factor results + Land Facts
→ Cow-Calf / Sheep operation evaluations
→ MatchResult (engine-authoritative)
→ buyer decision report mapping (parcel facts, evidence matrix, actions)
→ dynamic diligence findings with citations (non-F09)
```

Executable schema + projection are implemented (`docs/schemas/rangematch_unified_output.schema.json`, `src/rangematch/unified_output.py`). Factor science remains frozen.

## Out of scope for this version

- Full tool schema / OpenAPI
- Batch/portfolio parcel discovery
- Final regulatory or legal determination
- Numeric fit/ranking without approved differential rules
- Batch parcel search, portfolio ranking, ICP Finder, or regional site discovery

## Packaging note

Runtime packaging (API/UI) and optional Agent Skill submission packaging are now the next delivery phase. The Skill must reference canonical contracts rather than duplicate scientific rules. See `docs/PACKAGING_AND_DELIVERY_STRATEGY.md`.

## Completed product slices and next work

1. ~~Live/offline Mireye adapters implementing PROPERTY/LAND/HAZARD context contracts~~ — **done**; live verified on a clean network
2. ~~Planner executor that runs the DAG without changing science~~ — **done** (`docs/PLANNER_EXECUTOR_SPEC.md`)
3. ~~One-parcel API orchestration skeleton~~ — **done** (`docs/ONE_PARCEL_API_SPEC.md`, `src/rangematch/api.py`)
4. ~~Buyer UI consuming validated narrative with deterministic fallback~~ — **done** (`web/`)
5. ~~Constrained LLM Intent + Buyer Report + deterministic validation~~ — **done**; adversarial grounding tests included
6. ~~Address/coordinate parcel resolution, map selection, and explicit boundary confirmation~~ — **done**
7. ~~Public Diligence Agent with official-source citations~~ — **done**
8. ~~Buyer decision report v2 with parcel values and evidence matrix~~ — **done**
9. **Next:** competition packaging, deployment, and final end-to-end demo acceptance
