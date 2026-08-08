# F08 Data-Reuse Gate Results — CPER

> Status: `DATA_REUSE_VERIFIED`  
> Date: 2026-08-08  
> Source: USDA ARS RAP v3 `coverV3` (shared with F02)  
> Algorithm: `F08_WOODY_SHRUB_DERIVATION@0.1.0`  
> Network RAP request issued: `false`

## Decision

```yaml
live_gate_id: F08_RAP_COVERV3_DATA_REUSE_CPER
status: DATA_REUSE_VERIFIED
input_quality_state: WOODY_CONTEXT_AVAILABLE_COVERAGE_UNQUANTIFIED
signal: NEEDS_VERIFICATION
explanation_code: F08_EXPL_COVERAGE_UNQUANTIFIED
ranking_effect: NONE
reused_existing_artifact: true
duplicate_coverV3_fetch: false
network_rap_request_issued: false
```

## Derived measurements

| Variable | Value |
|---|---|
| raw_rap_shr_percent | 6.727234043361567 |
| raw_rap_tre_percent | 0.10557150211526739 |
| shrub_cover_fraction | 0.06727234043361567 |
| tree_cover_fraction | 0.0010557150211526738 |
| combined_modeled_woody_cover_fraction | 0.06832805545476835 |
| unit | fraction |
| source_year | 2025 |
| mask | true |

## Shared F02 / F08 provenance

| Field | Value |
|---|---|
| response_or_artifact_hash | `58bf1fc7aa91ce3d863bf419f59dad98ec18da36db23f570a1c9dc244d951160` |
| geometry_hash | `932edc9b3cb36b49b5a8fdd5ffa52cba17874720947865e0916ba069fad5f309` |
| source_year | 2025 |
| mask | true |
| applicability_status | `IN_DOCUMENTED_PRODUCT_SCOPE` |
| coverage_status | `COVERAGE_UNQUANTIFIED` |
| same_artifact | true |
| same_geometry_hash | true |
| same_source_year | true |
| same_mask | true |
| same_applicability_status | true |
| same_coverage_status | true |

Artifact reused: `test-data/live-results/cper/rap_coverV3_2025.json`  
Hash matches F02 `VAR_F02_PERENNIAL_HERB_COVER` provenance `response_or_artifact_hash`.

## Artifacts

- Derivation result: `test-data/live-results/cper/f08_derivation_result_2026-08-08.json`
- Live-gate JSON: `test-data/live-results/cper/f08_live_gate_cper_2026-08-08.json`
- Land Profile: `test-data/land-profiles/land_profile_cper_001.json`
- MatchResult: `test-data/land-profiles/match_result_cper_001.json`
- Demo closure: `test-data/land-profiles/land_profile_cper_001_demo_closure.{json,html}`

## Limitations preserved

- Woody cover ≠ browse / obstruction / herbaceous failure / ranking
- Combined modeled woody is derived context, not an independent RAP band
- Shared coverage remains unquantified (F02 deepening deferred)
- Mireye point fields were not used as parcel Land Facts
- F09 not started
