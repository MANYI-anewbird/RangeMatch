# RangeMatch Species Requirements Registry

> Status: `ACTIVE - QUALITATIVE RELATIONSHIPS ONLY`
> Operation Profiles: Cow-Calf Operation, Sheep Grazing
> Current audited slices: `F01 Topography`, `F03 Livestock Water`, `F05 Climate/Drought`
> Last updated: 2026-08-08

Operation Profiles are compiled deterministically from verified requirements in this registry. Profile prose is explanatory output, not a source of scientific rules.

## F05 Climate and Drought Exposure — Reviewed Requirements

### `COW_F05_001` — Precipitation regime and drought exposure context

```yaml
operation: COW_CALF_OPERATION
production_system: EXTENSIVE_GRAZING
decision_factor: F05_CLIMATE_DROUGHT_EXPOSURE
required_variables:
  - VAR_F05_MEAN_ANNUAL_PRECIPITATION
context_variables:
  - VAR_F05_DROUGHT_MONITOR_CATEGORY
  - VAR_F05_MEAN_ANNUAL_TEMPERATURE
  - VAR_F05_HEAT_DAYS_ABOVE_32C
candidate_variables:
  - VAR_F05_DROUGHT_HISTORY_SUMMARY
  - VAR_F05_PRECIPITATION_SEASONALITY
  - VAR_F05_INTERANNUAL_PRECIP_VARIABILITY
accepted_claim: >-
  Precipitation regime and drought exposure can affect forage reliability, water
  demand, livestock performance risk, and the need for drought contingency
  planning for cow-calf operations. A mean annual precipitation value or a
  current USDM class alone does not establish suitability, carrying capacity,
  forage failure, or livestock-water failure.
relationship_status: ACCEPTED_RELATIONSHIP
numeric_rule_status: NOT_APPROVED
sources: [SRC_F05_001, SRC_F05_003, SRC_F05_004, SRC_F05_007, SRC_F05_008]
data_method_sources: [SRC_F05_005, SRC_F05_006]
review_status: VERIFIED_FOR_V0_1
limitations:
  - No universal precipitation or USDM threshold is approved.
  - F05 must not silently alter F02 or F03 ranking effects.
```

### `SHEEP_F05_001` — Precipitation regime and drought exposure context

```yaml
operation: SHEEP_GRAZING
production_system: EXTENSIVE_OR_HERDED_GRAZING
decision_factor: F05_CLIMATE_DROUGHT_EXPOSURE
required_variables:
  - VAR_F05_MEAN_ANNUAL_PRECIPITATION
context_variables:
  - VAR_F05_DROUGHT_MONITOR_CATEGORY
  - VAR_F05_MEAN_ANNUAL_TEMPERATURE
  - VAR_F05_HEAT_DAYS_ABOVE_32C
candidate_variables:
  - VAR_F05_DROUGHT_HISTORY_SUMMARY
  - VAR_F05_PRECIPITATION_SEASONALITY
  - VAR_F05_INTERANNUAL_PRECIP_VARIABILITY
accepted_claim: >-
  Precipitation regime and drought exposure can affect forage reliability, water
  demand, and drought-management diligence for sheep grazing. Breed, management,
  diet moisture, and local forage composition can change sensitivity. Climate
  fields alone do not establish suitability or a universal numeric advantage or
  disadvantage relative to cattle.
relationship_status: ACCEPTED_RELATIONSHIP
numeric_rule_status: NOT_APPROVED
sources: [SRC_F05_001, SRC_F05_003, SRC_F05_004, SRC_F05_007, SRC_F05_008]
data_method_sources: [SRC_F05_005, SRC_F05_006]
review_status: VERIFIED_FOR_V0_1
limitations:
  - No universal sheep climate threshold or Cow-Calf versus Sheep ranking is approved.
  - Current USDM is not drought climatology.
```

## F03 Livestock Water — Reviewed Requirements

### `COW_F03_001` — Water availability, distribution, and adequacy

```yaml
operation: COW_CALF_OPERATION
production_system: EXTENSIVE_GRAZING
decision_factor: F03_LIVESTOCK_WATER
required_variables:
  - VAR_F03_SOURCE_INVENTORY
  - VAR_F03_SOURCE_OPERATIONAL_STATUS
  - VAR_F03_SOURCE_RELIABILITY
  - VAR_F03_DELIVERABLE_CAPACITY
  - VAR_F03_WATER_QUALITY
  - VAR_F03_LEGAL_ACCESS
accepted_claim: >-
  Reliable, legally accessible livestock water and its spatial distribution can
  affect cattle health, performance, movement, and grazing distribution.
  Capacity must be evaluated for the declared animal count and service period.
  A mapped hydrographic feature alone does not establish usable cattle water.
relationship_status: ACCEPTED_RELATIONSHIP
numeric_rule_status: NOT_APPROVED
sources: [SRC_F03_001, SRC_F03_002, SRC_F03_003, SRC_F03_004, SRC_F03_005]
review_status: VERIFIED_FOR_V0_1
```

### `SHEEP_F03_001` — Water availability, quality, and contextual demand

```yaml
operation: SHEEP_GRAZING
production_system: EXTENSIVE_OR_HERDED_GRAZING
decision_factor: F03_LIVESTOCK_WATER
required_variables:
  - VAR_F03_SOURCE_INVENTORY
  - VAR_F03_SOURCE_OPERATIONAL_STATUS
  - VAR_F03_SOURCE_RELIABILITY
  - VAR_F03_DELIVERABLE_CAPACITY
  - VAR_F03_WATER_QUALITY
  - VAR_F03_LEGAL_ACCESS
accepted_claim: >-
  Sheep require reliable, legally accessible water of adequate quantity and
  quality. Capacity must be evaluated for the declared animal count and service
  period. Remote water mapping alone does not establish accessible, reliable,
  adequate, or good-quality sheep water.
relationship_status: ACCEPTED_RELATIONSHIP
numeric_rule_status: NOT_APPROVED
sources: [SRC_F03_001, SRC_F03_005]
review_status: VERIFIED_FOR_V0_1
deferred_claims_requiring_additional_source_audit:
  - quantitative effects of animal size, production stage, diet moisture, and weather on demand
  - fresh-forage or snow substitution for a drinking-water source
```

## F02 Herbaceous Resource - Review Candidates

### `COW_F02_001` - Herbaceous resource quantity, timing, composition, and quality

```yaml
operation: COW_CALF_OPERATION
production_system: EXTENSIVE_GRAZING
decision_factor: F02_HERBACEOUS_RESOURCE
required_variables:
  - VAR_F02_PERENNIAL_HERB_COVER
  - VAR_F02_ANNUAL_HERB_COVER
  - VAR_F02_ANNUAL_HERB_PRODUCTION
  - VAR_F02_16DAY_HERB_PRODUCTION
  - VAR_F02_INTERANNUAL_PRODUCTION_VARIABILITY
verification_variables:
  - VAR_F02_BOTANICAL_COMPOSITION
  - VAR_F02_PALATABILITY
  - VAR_F02_NUTRITIVE_VALUE
accepted_claim: >-
  The amount, timing, composition, and nutritive value of herbaceous resources
  can affect cattle foraging opportunity and grazing performance. Modeled cover
  or production alone does not establish available, palatable, nutritionally
  adequate, or sustainably usable forage.
relationship_status: ACCEPTED_RELATIONSHIP_CANDIDATE
numeric_rule_status: NOT_APPROVED
sources: [SRC_F02_001, SRC_F02_005, SRC_F02_006, SRC_F02_007]
data_method_sources: [SRC_F02_002, SRC_F02_003, SRC_F02_004]
review_status: PENDING_FINAL_REVIEW
```

### `SHEEP_F02_001` - Herbaceous resource quantity, timing, composition, and quality

```yaml
operation: SHEEP_GRAZING
production_system: EXTENSIVE_OR_HERDED_GRAZING
decision_factor: F02_HERBACEOUS_RESOURCE
required_variables:
  - VAR_F02_PERENNIAL_HERB_COVER
  - VAR_F02_ANNUAL_HERB_COVER
  - VAR_F02_ANNUAL_HERB_PRODUCTION
  - VAR_F02_16DAY_HERB_PRODUCTION
  - VAR_F02_INTERANNUAL_PRODUCTION_VARIABILITY
verification_variables:
  - VAR_F02_BOTANICAL_COMPOSITION
  - VAR_F02_PALATABILITY
  - VAR_F02_NUTRITIVE_VALUE
accepted_claim: >-
  The amount, timing, composition, and nutritive value of herbaceous resources
  can affect sheep foraging opportunity. Sheep selection can differ from cattle
  and vary with breed, season, management, plant composition, and forage quality;
  modeled cover or production alone does not establish usable or nutritionally
  adequate forage.
relationship_status: ACCEPTED_RELATIONSHIP_CANDIDATE
numeric_rule_status: NOT_APPROVED
sources: [SRC_F02_001, SRC_F02_005, SRC_F02_006, SRC_F02_007]
data_method_sources: [SRC_F02_002, SRC_F02_003, SRC_F02_004]
review_status: PENDING_FINAL_REVIEW
```

## Cow-Calf Operation

### `COW_F01_001` - Topography and grazing distribution

```yaml
operation: COW_CALF_OPERATION
production_system: EXTENSIVE_GRAZING
decision_factor: F01_TOPOGRAPHY
required_variables:
  - VAR_F01_SLOPE_DISTRIBUTION
  - VAR_F01_TERRAIN_RUGGEDNESS
  - VAR_F01_TOPOGRAPHIC_POSITION
  - VAR_F01_ELEVATION
  - VAR_F01_ASPECT
accepted_claim: >-
  Topography can affect cattle grazing distribution and effective parcel use,
  but direction and magnitude depend on water distribution, wetness,
  vegetation, stocking and management context.
relationship_status: ACCEPTED_RELATIONSHIP
numeric_rule_status: NOT_APPROVED
sources:
  - SRC_F01_001
  - SRC_F01_002
  - SRC_F01_003
  - SRC_F01_004
limitations:
  - No universal slope cutoff or monotonic national penalty is supported.
  - Parcel terrain cannot be represented by one point sample.
review_status: VERIFIED
```

## Sheep Grazing

### `SHEEP_F01_001` - Topography and resource selection

```yaml
operation: SHEEP_GRAZING
production_system: EXTENSIVE_OR_HERDED_GRAZING
decision_factor: F01_TOPOGRAPHY
required_variables:
  - VAR_F01_SLOPE_DISTRIBUTION
  - VAR_F01_TERRAIN_RUGGEDNESS
  - VAR_F01_TOPOGRAPHIC_POSITION
  - VAR_F01_ELEVATION
  - VAR_F01_ASPECT
accepted_claim: >-
  Topographic variables can affect sheep resource selection. Sheep can operate
  in rugged extensive systems, but terrain response depends on breed, season,
  forage, water and herding or management context.
relationship_status: ACCEPTED_RELATIONSHIP
numeric_rule_status: NOT_APPROVED
sources:
  - SRC_F01_001
  - SRC_F01_004
  - SRC_F01_005
  - SRC_F01_006
limitations:
  - A universal 45 percent slope-tolerance rule is not supported.
  - Ruggedness must not receive an automatic positive signal.
review_status: VERIFIED
```
