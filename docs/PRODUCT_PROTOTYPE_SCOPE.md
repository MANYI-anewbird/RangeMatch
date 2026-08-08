# RangeMatch Competition Product Prototype Scope

> Status: `CANONICAL_V0_1`  
> Date: 2026-08-08  
> Product surface: one U.S. parcel per run

## Buyer and problem

The initial buyer is a serious ranch buyer or ranch operator screening a parcel before committing acquisition or diligence resources. The product reduces the risk of discovering too late that the land facts, water evidence, access context, environmental conditions, or operating constraints do not match the intended grazing operation.

## Product promise

RangeMatch accepts an address, APN, parcel geometry, or existing Land Profile and produces an evidence-constrained comparison for the currently supported Cow-Calf and Sheep grazing Profiles. It explains what is known, what is not known, why the current decision label was produced, and what should be verified next.

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

Regulatory and land-rights investigation is a later dynamic workflow above the frozen Factors. It may investigate current federal, state, and county rules, permit triggers, water rights, zoning, and official-source currency. It must not provide final legal advice or write LLM conclusions into canonical Land Facts.

## Explicitly deferred

- Batch parcel search
- Portfolio ranking
- Regional site discovery
- Mireye ICP Finder workflow
- Numeric national suitability scores
- F09+ Factors
- Final legal compliance determination
- Carrying-capacity and profitability claims

## Prototype success condition

The demonstration succeeds when the Agent can take one parcel, recognize Goal-directed or Discovery intent, call approved tools, preserve provenance and failures, reuse existing artifacts, produce the same deterministic MatchResult from the same inputs, and present actionable unknowns and diligence steps without changing the science.
