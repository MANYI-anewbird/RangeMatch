# RangeMatch Competition Product Prototype Scope

> Status: `CANONICAL_V0_1`
> Date: 2026-08-08
> Product surface: one U.S. parcel per run
> Current baseline: `docs/RANGEMATCH_PRODUCT_AND_AGENT_CODE_FLOW.md`

## Buyer and problem

The initial buyer is a serious ranch buyer or ranch operator screening a parcel before committing acquisition or diligence resources. The product reduces the risk of discovering too late that the land facts, water evidence, access context, environmental conditions, or operating constraints do not match the intended grazing operation.

## Product promise

The runnable prototype accepts an address or coordinate/map pin, resolves candidate parcels through Mireye, requires explicit polygon confirmation, and then runs the same one-parcel workflow. Existing Land Profiles remain an engineering replay path. APN-first lookup and user-drawn boundaries are not supported.

RangeMatch does not promise carrying capacity, profitability, legal compliance, or purchase approval.

## Interaction modes

### Goal-directed

The user selects Cow-Calf or Sheep. The Agent investigates that Profile first, then may show the peer Profile as an alternative. User intent changes investigation priority, not science.

### Discovery

The user does not choose an operation. Cow-Calf and Sheep are evaluated equally. Results are explicitly limited to the supported Profiles.

## Prototype workflow

```text
Single parcel input
→ Mireye property / land / hazard context
→ approved parcel-wide external adapters
→ normalized Land Profile
→ frozen F01–F08 deterministic evaluation
→ Cow-Calf / Sheep MatchResult
→ constrained explanation
→ unknowns, risk triggers, and diligence actions
```

## Frozen Factor scope

1. F01 Topography
2. F02 Herbaceous Resource
3. F03 Livestock Water
4. F04 Soil, Wetness, and Ecological Site
5. F05 Climate and Drought Exposure
6. F06 Parcel Configuration
7. F07 Road and Physical Access Context
8. F08 Woody and Shrub Vegetation Structure

No F09+ Factor is authorized for the competition prototype.

## Mireye role

- Property Diligence / lookup: parcel, jurisdiction, zoning, and property context when available.
- Land Read: rapid point-level terrain, soil, land-cover, and land-use context.
- Hazards Read: point-level flood, wetland, and wildfire-related triggers with surfaced partial failures.

Mireye context does not replace parcel-wide canonical RAP, SDA, NOAA, TIGER, DEM, or verified-water evidence paths. Point results remain point results.

## Dynamic diligence

The Public Diligence Agent performs a bounded, official-source search for current federal, state, and county guidance, permit triggers, drought context, and public-land constraints. It must not provide final legal advice, infer compliance, or write search conclusions into canonical Land Facts or MatchResult.

## Explicitly deferred

- Batch parcel search
- Portfolio ranking
- Regional site discovery
- Mireye ICP Finder workflow
- Numeric national suitability scores
- F09+ Factors
- Final legal compliance determination
- Carrying-capacity and profitability claims

## Buyer-facing report surface

The UI presents a decision dashboard, readable decision report, and evidence appendix. The readable report contains:

1. Executive Summary
2. Key Unknowns
3. What We Found on This Parcel
4. Cow-Calf vs. Sheep evidence matrix
5. Diligence Plan
6. Current Rules and Local Guidance
7. Methodology and Limitations

Presentation may simplify, but must not discard material unknowns, coverage limitations, source failures, or provenance access. Technical F01–F08 evidence and Agent trace remain available through progressive disclosure. Only a validator-passed LLM narrative is displayable; otherwise the UI uses a labeled deterministic Engine fallback. Contract version: `RANGEMATCH_UNIFIED_OUTPUT@0.1.0`.

## Planner stance

Investigation planning is a dependency DAG (`docs/PLANNER_ROUTING_SPEC.md`). Factor IDs define report order; execution peers after F06 may run in parallel; F08 reuses F02 RAP artifacts. The Planner Executor and confirmed-parcel live adapter paths are implemented. Historical SafeBrowse/TLS failures remain documented as incidents; Mireye lookup and Property/Land/Hazard calls have subsequently passed on a clean network. Any recurrence still fails visibly and never substitutes fixture data.

## Packaging stance

Packaging has two layers: (1) runnable engineering package (API + UI + engine), and (2) optional Agent Skill/submission instructions that reference rather than duplicate scientific rules. The one-parcel workflow is now ready for competition packaging and deployment preparation.

## Current implementation status

```yaml
backend_tests: 423_PASSED
ui_tests: 22_PASSED
llm_report_validator: HARDENED
buyer_report_ui: IMPLEMENTED
engine_behavior: HOLD_ONLY_NO_APPROVED_RANKING
live_mireye: LIVE_VERIFIED_ON_CLEAN_NETWORK
public_diligence_search: IMPLEMENTED
buyer_decision_report_v2: IMPLEMENTED
next_slice: COMPETITION_PACKAGING_AND_DEPLOYMENT_READINESS
```

The current Engine is scientifically conservative: it does not yet establish a Cow-Calf-versus-Sheep ranking, suitability score, carrying capacity, or purchase recommendation.

## Prototype success condition

The demonstration succeeds when the Agent can take one parcel, recognize Goal-directed or Discovery intent, call approved tools, preserve provenance and failures, reuse existing artifacts, produce the same deterministic MatchResult from the same inputs, project the unified output envelope, and present actionable unknowns and diligence steps without changing the science.
