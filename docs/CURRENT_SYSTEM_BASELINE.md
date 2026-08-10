# RangeMatch Current System Baseline

> Status: `CURRENT_CANONICAL`
> Effective date: 2026-08-08
> Audience: product, engineering, scientific review, competition submission
> Supersedes: stale phase/status statements in earlier milestone documents

## Product definition

RangeMatch is a constrained agricultural-land investigation and operation-matching Agent for one confirmed U.S. parcel per run. It combines Mireye context, approved parcel-wide public data, frozen agricultural knowledge, deterministic evaluation, bounded current-source search, and validated LLM explanation.

The competition prototype supports two peer Operation Profiles: Cow-Calf Operation and Sheep Grazing. Goal-directed mode presents the user-selected Profile first. Discovery mode evaluates both supported Profiles as peers. User intent changes presentation and investigation priority, not scientific rules.

## Current user journey

```text
Address or map coordinate
→ Mireye parcel lookup
→ user selects and confirms one parcel polygon
→ General Exploration / Cattle / Sheep
→ visible Agent progress
→ Mireye context + F01–F08 parcel evidence
→ deterministic Matching Engine
→ Unified Output
→ validated buyer narrative
→ bounded Public Diligence search
→ decision dashboard + readable report + evidence appendix
```

Addresses are intended for properties with a usable street address. Rural, undeveloped, and ranch parcels may enter through a map pin or latitude/longitude. A point is only a lookup input; it never becomes the F01–F08 analysis geometry and is never buffered into an invented parcel.

## Authority boundaries

| Layer | Authority |
|---|---|
| Mireye | Parcel candidate lookup; rapid Property/Land/Hazard context; point QA and diligence triggers |
| External adapters | Canonical parcel evidence from 3DEP, RAP, NHD/NAIP, SDA, NOAA/NCEI, geometry, and TIGER/Line |
| Agricultural Knowledge Layer | Frozen reviewed Factors, species requirements, evidence and limitations |
| Deterministic Engine | Factor signals, unknowns, operation decision labels, ranking permission |
| LLM Intent/Report | Intent normalization and readable explanation within Engine/Unified Output constraints |
| Public Diligence Agent | Current official-source regulation/guidance search; no Factor or Engine mutation |

Unknown evidence remains unknown. A successful API response does not prove scientific applicability or parcel coverage. Mireye point context does not replace parcel aggregates. The LLM cannot manufacture measurements, thresholds, scores, legal compliance, carrying capacity, profitability, or operation ranking.

## Frozen Factor scope

1. F01 Topography
2. F02 Herbaceous Resource
3. F03 Livestock Water
4. F04 Soil, Wetness, and Ecological Site
5. F05 Climate and Drought Exposure
6. F06 Parcel Configuration
7. F07 Road and Physical Access Context
8. F08 Woody and Shrub Vegetation Structure

F09+ remains outside the competition scope. Dynamic regulation, policy, permit, and land-rights research is a diligence side branch, not F09 and not a canonical Land Fact source.

## Buyer output

The product has three layers:

1. **Decision dashboard** — parcel map, area, climate, vegetation, water, mapped road context, operation states, evidence readiness, and top actions.
2. **Readable decision report** — Executive Summary; Key Unknowns; parcel-specific measured/modeled facts; Cow-Calf vs. Sheep evidence matrix; decision-changing diligence actions; current local guidance; methodology.
3. **Evidence appendix** — F01–F08 variables, units, periods, spatial semantics, provenance, coverage, applicability, limitations, and Agent trace.

Buyer-facing `More evidence needed` maps to Engine `HOLD`. It means evidence is incomplete, not that the parcel is unsuitable. No numeric suitability score or best-use winner is displayed while `ranking_permitted: false`.

## Current implementation status

```yaml
parcel_entries: [ADDRESS, COORDINATE_OR_MAP_PIN]
parcel_confirmation: IMPLEMENTED_MAPLIBRE_2D
live_mireye_lookup: LIVE_VERIFIED
live_mireye_contexts: PROPERTY_LAND_HAZARD_COMPLETE_ON_CLEAN_NETWORK
frozen_factor_scope: F01_F08
supported_operations: [COW_CALF_OPERATION, SHEEP_GRAZING]
planner_executor: IMPLEMENTED
async_progress_ui: IMPLEMENTED
one_parcel_api: IMPLEMENTED_IN_MEMORY
validated_llm_buyer_report: IMPLEMENTED
public_diligence_search: IMPLEMENTED_LIVE_VERIFIED
buyer_decision_report_v2: IMPLEMENTED
engine_ranking: NOT_PERMITTED
backend_tests: 423_PASSED
frontend_tests: 22_PASSED
frontend_production_build: PASSED
```

Test counts are a 2026-08-08 checkpoint, not a permanent contract.

## Explicit non-goals for the competition build

- Batch parcel search, portfolio ranking, or regional site discovery
- Mireye ICP Finder workflow
- APN-first nationwide parcel resolution
- User-drawn or automatically buffered analysis geometry
- Numeric nationwide livestock-fit scores
- Carrying-capacity, stocking-rate, profitability, or purchase guarantees
- Final legal, permit, zoning, water-right, or environmental-compliance determinations
- F09+ scientific Factors

## Documentation precedence

1. This baseline and `docs/README.md`
2. Current canonical product/runtime contracts
3. Frozen scientific and deterministic Factor contracts
4. Dated acceptance/live-gate records
5. Historical planning/research snapshots

Dated records preserve what was true at the time. Their old test counts, network incidents, and next-step statements do not override this baseline.
