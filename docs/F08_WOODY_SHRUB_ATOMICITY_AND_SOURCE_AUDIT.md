# F08 Atomicity and Source Audit — Woody and Shrub Vegetation Structure

> Status: `FROZEN_V0_1`  
> Language: English  
> Factor ID: `F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE`  
> Review date: 2026-08-08  
> Freeze: `docs/F08_FREEZE_GATE_RESULTS.md`  
> Demo Factor scope: `CLOSED` (F01–F08)  
> F09+: `NOT_AUTHORIZED`  
> Next phase: Product Prototype + Agent Orchestration  
> F02 coverage upgrade: `DEFERRED`

## 0. Required Contract Fixes (applied)

```yaml
freeze_status: FROZEN_V0_1
data_reuse_gate: PASSED
signal: NEEDS_VERIFICATION
ranking_effect: NONE
coverage_status: COVERAGE_UNQUANTIFIED
full_test_suite: 161_PASSED
demo_factor_scope: CLOSED
f09_authorization: NOT_AUTHORIZED
```

1. **Percent vs fraction:** Runtime Land Facts use `*_fraction` in `[0.0, 1.0]`. RAP percent converts as `fraction = RAP_percent / 100`. Raw RAP percent is preserved in provenance.
2. **Rename:** `woody_canopy_cover_fraction` → `combined_modeled_woody_cover_fraction` (derived SHR+TRE context, not an independent canopy band).
3. **Shared quality:** Same RAP artifact/year/mask/geometry ⇒ same applicability and coverage. `COVERAGE_UNQUANTIFIED` must not become COMPLETE in F08.

## 1. Factor Boundary Decision

`Woody and Shrub Vegetation Structure` converts parcel-wide woody-layer cover evidence into reproducible **vegetation-structure context**.

### Exact F02 / F08 boundary

| Layer | Factor | Owns |
|---|---|---|
| Herbaceous | `F02_HERBACEOUS_RESOURCE` | `AFG`, `PFG`, herbaceous production (`AFG`/`PFG`/`HER`), seasonality/variability context, bare-ground (`BGR`) as F02 surface context |
| Woody | `F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE` | `SHR`, `TRE` as normalized fractions, derived combined modeled woody context, woody-specific applicability/coverage/year provenance |

Rules:

- F08 may provide context for interpreting F02 but **must not replace** F02 herbaceous facts.
- F02 must not emit `SHR`/`TRE` as herbaceous Land Facts.
- F08 must not emit `AFG`/`PFG`/`HER` as woody Land Facts.
- `BGR` remains F02 context unless a later reviewed surface-composition Factor is authorized; F08 does not absorb bare ground.
- Litter (`LTR`) is **not** a woody Land Fact in v0.1 (deferred); it may appear only as shared RAP response metadata.

F08 is **not**:

- browse availability, palatability, botanical composition, toxicity, or nutritive value;
- automatic grazing obstruction or brush-management recommendation;
- proof of low herbaceous production;
- carrying capacity, profitability, or operational success;
- a Cow-Calf versus Sheep ranking Factor;
- a numeric suitability score.

## 2. Candidate Variable Decisions

| Variable ID | Object | Atomic vs derived | v0.1 decision | Rationale |
|---|---|---|---|---|
| `VAR_F08_SHRUB_COVER_FRACTION` | Shrub cover fraction `[0,1]` | Source Land Fact (RAP `SHR` percent `/100`) | `INCLUDE` | Direct RAP coverV3 band normalized to fraction; raw percent in provenance |
| `VAR_F08_TREE_COVER_FRACTION` | Tree cover fraction `[0,1]` | Source Land Fact (RAP `TRE` percent `/100`) | `INCLUDE` | Direct RAP coverV3 band normalized to fraction; raw percent in provenance |
| `VAR_F08_COMBINED_MODELED_WOODY_COVER_FRACTION` | Combined modeled woody | Derived `SHR_frac + TRE_frac` | `INCLUDE` as **derived context only** | Not an independent RAP canopy band; null if either input is null |
| `VAR_F08_SOURCE_YEAR` | Cover year | Provenance / temporal key | `INCLUDE` | Required temporal semantics; shared with F02 RAP year when reused |
| `VAR_F08_APPLICABILITY_STATUS` | RAP domain applicability | QA property | `INCLUDE` | Reuse F02 RAP applicability gate; do not invent a second RAP domain rule |
| `VAR_F08_COVERAGE_STATUS` | Parcel RAP coverage usability | QA property | `INCLUDE` | Must equal shared F02 coverage for same artifact; deepening deferred |
| `VAR_F08_WOODY_COVER_SPATIAL_DISTRIBUTION` | Within-parcel woody pattern | Derived distribution | `DEFER` | Needs reviewed pixel/patch method; aggregate mean alone is insufficient |
| `VAR_F08_WOODY_COVER_TEMPORAL_CHANGE` | Multi-year woody change | Derived time series | `DEFER` | Needs frozen change window, baseline, and uncertainty policy |
| `VAR_F08_LITTER_COVER_FRACTION` | Litter cover (`LTR`) | Source band | `DEFER` | Not woody structure; avoid expanding F08 beyond woody layer |
| `VAR_F08_BROWSE_AVAILABILITY` | Usable browse | Operational inference | `REJECT` | Not supported by fractional shrub cover alone |
| `VAR_F08_WOODY_OBSTRUCTION_CLASS` | Grazing obstruction class | Suitability threshold | `REJECT` | No reviewed universal tree/shrub obstruction threshold |
| `VAR_F08_LCMS_WOODY_CLASS` | LCMS life-form class | Point / secondary | `DEFER` as Land Fact; Mireye QA only | Point sample ≠ parcel RAP woody cover |
| `VAR_F08_NLCD_TREE_CANOPY_PCT` | NLCD TCC percent | Point / secondary | `DEFER` as Land Fact; Mireye QA only | Point canopy ≠ parcel RAP `TRE` |
| `VAR_F08_WOODY_CANOPY_COVER_FRACTION` | Former name | — | `SUPERSEDED` | Renamed to `VAR_F08_COMBINED_MODELED_WOODY_COVER_FRACTION` |

## 3. Non-Equivalences

```text
shrub cover != browse availability
shrub cover != palatability
shrub cover != botanical species composition
shrub cover != toxicity or nutritive value
tree cover != automatic grazing obstruction
woody cover != proof of low herbaceous production
combined_modeled_woody (SHR_frac+TRE_frac) != independent RAP canopy band
Mireye point woody/tree field != parcel woody distribution
LCMS/NLCD class != RAP fractional cover
F08 woody context != F02 herbaceous resource
F08 context != Cow-Calf or Sheep preference / ranking
RAP cover components != forced exact 100% without product verification
RAP percent != Land Fact unit (Land Facts are fractions)
COVERAGE_UNQUANTIFIED != COMPLETE in F08
```

## 4. Unit Policy (fraction)

```yaml
runtime_land_fact_unit: fraction
valid_range: [0.0, 1.0]
rap_native_unit: percent_cover
conversion: fraction = RAP_percent / 100
preserve_raw_rap_percent_in_provenance: REQUIRED
```

Example (CPER-style RAP percent → Land Fact):

```yaml
raw_rap: { SHR: 6.73, TRE: 0.11 }
shrub_cover_fraction: 0.0673
tree_cover_fraction: 0.0011
combined_modeled_woody_cover_fraction: 0.0684
```

## 5. Combined Modeled Woody Rules

```text
combined_modeled_woody_cover_fraction =
  shrub_cover_fraction + tree_cover_fraction
```

- If either `SHR` or `TRE` (normalized) is null → combined is null.
- Do not treat null as 0.
- Do not clamp, truncate, or repair residual mass.
- Combined woody does **not** participate in any composition sum identity.

## 6. RAP Cover Composition Policy (sum-to-100)

RAP v3 `coverV3` returns six components as **percent** cover: `AFG`, `PFG`, `SHR`, `TRE`, `LTR`, `BGR`. Product materials describe them as percentage cover partitions of the land surface and they **often** approach 100%, but:

1. RangeMatch **must not force** `AFG+PFG+SHR+TRE+LTR+BGR = 100` as a Land Fact or repair rule.
2. Empirical CPER 2025 masked aggregate sums are **not exactly 100** in the existing fixture (~91% including litter).
3. Missing mass must remain **unknown / unallocated**, not reassigned to woody or herbaceous classes.
4. Optional QA may record `observed_component_sum_percent` as a limitation/note only.
5. F08 must not double-count by treating derived combined modeled woody as an additional independent cover class.

## 7. Proposed Canonical Data Path

```text
Canonical parcel path:
  RAP v3 coverV3 → SHR%, TRE% (+ year, mask, geometry_hash, response hash)
  → normalize to fractions (/100); preserve raw percent in provenance
  → shared RAP applicability + coverage record with F02
  → F08 Land Facts / Factor result

Mireye role:
  POINT_QA_AND_FAST_CONTEXT_ONLY
  fields of interest: lcms_class, tree_canopy_pct (if requested)
  never parcel Land Facts; never replace RAP SHR/TRE
```

Secondary land-cover (LCMS/NLCD national products outside Mireye point): **not required** for F08 v0.1. If later introduced, conflict with RAP → `NEEDS_VERIFICATION`, **no averaging**.

## 8. Shared F02 / F08 RAP Acquisition and Coverage Design

| Shared element | Policy |
|---|---|
| Preferred acquisition | One `coverV3` request for a given geometry_hash + year + mask |
| Artifact reuse | F02 and F08 MUST share the same `response_or_artifact_hash` when both consume that year |
| Duplicate API calls | Prohibited when a complete, hash-identified `coverV3` artifact already exists for the same request key |
| Applicability gate | Shared; outside/unknown scope preserved identically |
| Coverage record | Same `coverage_status` for the same artifact — including `COVERAGE_UNQUANTIFIED` |
| Domain / mask | Same mask behavior as F02 (`mask=true` cropland/development/water exclusion) |
| Factor storage | Separate Factor payloads / land_facts; shared provenance pointers |

### Demo quality alignment (mandatory)

```yaml
same_artifact: true
same_geometry_hash: true
same_source_year: true
same_mask: true
same_applicability_status: true
same_coverage_status: true

when_coverage_unquantified:
  input_quality_state: WOODY_CONTEXT_AVAILABLE_COVERAGE_UNQUANTIFIED
  signal: NEEDS_VERIFICATION
  ranking_effect: NONE
```

F08 must **not** emit `WOODY_CONTEXT_COMPLETE` → `CONTEXT_DEPENDENT` for the same unquantified artifact that yields F02 `NEEDS_VERIFICATION`. Complete woody context is reserved for future quantified shared coverage.

## 9. Narrow Species Relationships (context only; no numeric rules)

Reviewed separately for Cow-Calf and Sheep. LLM search/summary does **not** create thresholds or ranking.

### Cow-Calf (`COW_F08_001` — CONTEXT_ONLY_NO_NUMERIC_RULE)

- Cattle diets on many western ranges are grass-dominated; shrub use is often lower than sheep and is species-/site-dependent.
- Shrub fractional cover does **not** establish usable cattle browse, obstruction, or carrying capacity.
- Tree cover does **not** establish automatic cattle exclusion.

### Sheep (`SHEEP_F08_001` — CONTEXT_ONLY_NO_NUMERIC_RULE)

- Sheep often use more forbs/browse than cattle on some mountain/western ranges, but this is **not** universal and does not justify a ranking rule from RAP `SHR`/`TRE`.
- Shrub cover ≠ palatable browse availability or nutritive adequacy for sheep.
- No Sheep-above-Cattle score from woody metrics is approved.

### Shared prohibition

```text
ranking_effect: NONE
cow_sheep_signal_divergence_from_f08_alone: false
```

## 10. Evidence / QA States

| `input_quality_state` | Meaning | Demo signal |
|---|---|---|
| `WOODY_CONTEXT_AVAILABLE_COVERAGE_UNQUANTIFIED` | SHR/TRE available; shared coverage unquantified | `NEEDS_VERIFICATION` |
| `WOODY_CONTEXT_COMPLETE` | SHR/TRE + quantified shared coverage (future) | `CONTEXT_DEPENDENT` |
| `RAP_OUTSIDE_OR_UNKNOWN_APPLICABILITY` | Shared RAP applicability outside/unknown | `NEEDS_VERIFICATION` |
| `COVERAGE_MISSING` | Shared coverage missing/unknown | `NEEDS_VERIFICATION` |
| `POINT_ONLY_SECONDARY` | Only Mireye/LCMS/NLCD point fields | `NEEDS_VERIFICATION` |
| `CONFLICTING_SOURCES` | Material RAP vs secondary disagreement | `NEEDS_VERIFICATION` |
| `MISSING` | No woody RAP inputs | `UNKNOWN` |

## 11. Signal Policy

Allowed signals only:

- `CONTEXT_DEPENDENT`
- `NEEDS_VERIFICATION`
- `UNKNOWN`

Always: `ranking_effect: NONE`.

## 12. Provenance Requirements

Every F08 result must preserve:

- geometry_id / geometry_reference / geometry_hash  
- RAP product/version (`v3`), endpoint (`coverV3`), year, mask  
- `response_or_artifact_hash` (shared with F02 when reused)  
- applicability_status, coverage_status (aligned with F02)  
- raw RAP `SHR`/`TRE` percent measurements  
- normalized fraction Land Facts  
- algorithm/derivation version  
- limitations stating woody ≠ browse/obstruction/herbaceous replacement  

Geometry hash change invalidates F08 and requires recompute (shared with other parcel Factors).

## 13. Prohibited Interpretations

- Shrub cover → browse availability / palatability / nutrition / toxicity  
- Tree cover → automatic obstruction / REJECT  
- Woody cover → low herbaceous production certainty  
- Universal woody-cover thresholds or suitability classes  
- Cow-Calf vs Sheep ranking from F08  
- Forced sum-to-100 repair or double-counting of combined modeled woody  
- Treating null SHR/TRE as zero in combined derivation  
- Averaging RAP with LCMS/NLCD  
- Mireye point as parcel woody distribution  
- Upgrading shared `COVERAGE_UNQUANTIFIED` to COMPLETE in F08 alone  
- Carrying capacity, profitability, operational success claims  

## 14. Freeze / Phase Transition

**F08 v0.1 is `FROZEN_V0_1`. Demo Factor scope F01–F08 is `CLOSED`.**

Next phase: Product Prototype + Agent Orchestration (`docs/AGENT_ORCHESTRATION_SPEC.md`).

- Do **not** start F09+.  
- Do **not** deepen F02 coverage as a Factor gate.  
- Do **not** invent woody thresholds or species ranking.
