# F05 Atomicity and Source Audit — Climate and Drought Exposure

> Status: `FROZEN — V0.1 VERTICAL SLICE`  
> Freeze record: `docs/F05_FREEZE_GATE_RESULTS.md`  

> Language: English  
> Tier: `2 — reliable data path + qualitative rules`  
> Operations: Cow-Calf Operation and Sheep Grazing  
> Review date: 2026-08-07  
> Flood / FEMA hazard: `OUT OF SCOPE FOR F05`  
> Live gate: `docs/F05_LIVE_DATA_GATE_RESULTS_CPER.md` (`LIVE_VERIFIED`)

## 1. Factor Boundary Decision

MVP candidates listed Precipitation and Drought Exposure separately. For Tier 2 they are implemented as one Factor family only if atomic variables remain separable and no composite climate score is created.

The v0.1 factor family is named:

> **F05 Climate and Drought Exposure**

F05 covers climatological moisture supply, drought exposure context, and selected heat/temperature context relevant to grazing screening. It does **not** own flood hazard, soil-survey ponding/flooding interpretations, or verified livestock-water reliability.

| Variable ID | Atomic object | Role | v0.1 decision |
|---|---|---|---|
| `VAR_F05_MEAN_ANNUAL_PRECIPITATION` | Mean annual precipitation over an explicit normals period | Continuous climate Land Fact | `INCLUDE` |
| `VAR_F05_PRECIPITATION_SEASONALITY` | Within-year precipitation distribution or seasonality index | Continuous/derived climate context | `INCLUDE CANDIDATE` |
| `VAR_F05_INTERANNUAL_PRECIP_VARIABILITY` | Multi-year precipitation variability over an explicit window | Derived climate context | `INCLUDE CANDIDATE; METHOD NOT FROZEN` |
| `VAR_F05_DROUGHT_MONITOR_CATEGORY` | Current US Drought Monitor class at the parcel/point | Controlled current-condition context | `INCLUDE WITH STRONG LIMITATIONS` |
| `VAR_F05_DROUGHT_HISTORY_SUMMARY` | Multi-year drought frequency/severity summary over an explicit window | Derived drought exposure context | `INCLUDE CANDIDATE; METHOD NOT FROZEN` |
| `VAR_F05_MEAN_ANNUAL_TEMPERATURE` | Mean annual temperature normal | Continuous climate context | `INCLUDE AS CONTEXT` |
| `VAR_F05_HEAT_DAYS_ABOVE_32C` | Count of days above 32°C over an explicit annual definition | Continuous heat-exposure context | `CONTEXT CANDIDATE; NO BIOLOGICAL THRESHOLD APPROVED` |
| `VAR_F05_REFERENCE_ET_OR_ARIDITY` | Reference ET and/or aridity index over an explicit method | Derived climate context | `CANDIDATE; EXTERNAL DATA LIKELY REQUIRED` |

## 2. Non-Equivalences

```text
atmospheric precipitable water != land-surface precipitation
current USDM week != drought climatology or drought frequency
USDM null != historically drought-free land
drought category != forage failure
mean annual precipitation != available forage
precipitation != livestock-water reliability
heat-day count != approved animal heat-stress score
F04 soil-survey ponding/flooding != climate drought exposure
FEMA / flood hazard != F05 climate drought
short heat event != long-term climate normal
```

## 3. Relationship to Existing Factors

| Existing Factor | Allowed interaction in v0.1 | Prohibited shortcut |
|---|---|---|
| F02 Herbaceous Resource | F05 may later contextualize forage variability and diligence | Do not convert drought or low precip into an F02 negative score without a reviewed rule |
| F03 Livestock Water | F05 may support diligence about drought-period water reliability | Do not treat USDM class as proof that a mapped water source failed |
| F04 Soil / Wetness / Ecological Site | Keep soil-survey wetness and ecological-site climate narrative separate | Do not merge F04 ponding/flooding into F05 |
| Future Flood Factor | Owns flood hazard | F05 must not implement FEMA flood screens |

## 4. Required Aggregation and Temporal Governance

1. Every climate value must declare the normals or observation period, spatial support, and source version.
2. Preserve raw continuous values before any classification.
3. Current-week USDM and multi-year drought history are different variables; never overwrite one with the other.
4. Point climate samples are QA/display only unless a reviewed parcel aggregation method exists.
5. Missing climate values remain `UNKNOWN`; they are not imputed from state names or ecological-site labels.
6. No default precipitation or drought threshold is approved for Cow-Calf or Sheep ranking.

## 5. First Authoritative Source Set

### `SRC_F05_001` — NOAA nClimGrid / NCEI precipitation and temperature grids

- Role: Primary path for mean annual precipitation normals; temperature/heat context also available via NCEI products and Mireye adapters.
- Supports: Spatially explicit climate values with units and time windows.
- Does not support: Direct forage suitability, carrying capacity, or operation ranking.
- Applicability: `UNITED_STATES_WITH_PRODUCT_COVERAGE_LIMITS`
- CPER live precip path: NOAA/NCEI `prcp-1991_2020-monthly-normals-v1.0.nc` → `annprcp_norm` = **345.74 mm** for the engineering geometry (single intersecting 1/24° cell).

### `SRC_F05_002` — PRISM climate grids

- Role: Alternate or cross-check precipitation/temperature source where licensed/available.
- Supports: High-resolution climate surfaces commonly used in U.S. ecological interpretation.
- Does not support: Automatic biological thresholds for RangeMatch.
- Applicability: `UNITED_STATES_PRODUCT_DEPENDENT`

### `SRC_F05_003` — U.S. Drought Monitor (USDM)

- Official page: https://droughtmonitor.unl.edu/
- Role: Current drought-category context and potential input to a future history summary.
- Supports: Controlled drought classes D0–D4 with weekly updates.
- Does not support: Treating one current class as long-term drought exposure or as proof of failed forage/water.
- Applicability: `UNITED_STATES_CURRENT_CONDITION_CONTEXT`

### `SRC_F05_004` — USDA / NRCS / Extension drought and grazing management guidance

- Role: Narrow qualitative relationships between drought/climate stress and grazing risk, diligence, and management context.
- Does not support: Universal numeric penalties or hard exclusions without source-bound review.
- Applicability: `UNITED_STATES_GRAZING_MANAGEMENT_GUIDANCE`

### `SRC_F05_005` — Mireye climate fields (adapter audit only)

- Role: Fast point context where field semantics match F05 variables.
- Known useful fields in v0.14.0 catalog: `drought_category`, `mean_annual_dry_bulb_temperature_degc`, `days_above_32c_annual_count`.
- Known non-equivalent field: `precipitable_water_annual_mean_cm` is atmospheric water vapor, not rainfall.
- Gap: No verified land-surface annual precipitation field found in the v0.14.0 catalog snapshot.

## 6. Narrow Relationships (v0.1)

Frozen in `docs/F05_CLIMATE_DROUGHT_EVIDENCE_REGISTRY.md` and `docs/SPECIES_REQUIREMENTS_REGISTRY.md`.

### Cow-Calf — `COW_F05_001`

> Precipitation regime and drought exposure can affect forage reliability, water demand, livestock performance risk, and the need for drought contingency planning for cow-calf operations. A mean annual precipitation value or a current USDM class alone does not establish suitability, carrying capacity, forage failure, or livestock-water failure.

Status: `ACCEPTED_RELATIONSHIP — VERIFIED_FOR_V0_1` (`numeric_rule_status: NOT_APPROVED`)

### Sheep — `SHEEP_F05_001`

> Precipitation regime and drought exposure can affect forage reliability, water demand, and drought-management diligence for sheep grazing. Breed, management, diet moisture, and local forage composition can change sensitivity. Climate fields alone do not establish suitability or a universal numeric advantage or disadvantage relative to cattle.

Status: `ACCEPTED_RELATIONSHIP — VERIFIED_FOR_V0_1` (`numeric_rule_status: NOT_APPROVED`)

## 7. Prohibited Interpretations

- Do not create a composite climate/drought suitability score.
- Do not approve national precipitation or USDM thresholds for `REJECT`.
- Do not infer climate from Texas/West/arid place names.
- Do not treat Mireye `precipitable_water_annual_mean_cm` as rainfall.
- Do not treat a null or non-drought USDM point as proof of low drought risk over years.
- Do not let F05 quietly alter F02 or F03 ranking effects.
- Do not implement Flood/FEMA logic inside F05.

## 8. Decision and Next Gate

F05 is scientifically relevant for Tier 2. The CPER live data gate is complete:

```yaml
data_path_status: LIVE_VERIFIED
signal_status: NOT_YET_APPROVED
ranking_effect: NONE
```

Completed:

1. Freeze the F05 variable list into `UNIFIED_LAND_VARIABLE_REGISTRY.yaml`.
2. Complete `F05_DATA_SOURCE_AND_MIREYE_AUDIT.yaml` with exact field IDs, versions, and external-data methods.
3. Live-test CPER NOAA/NCEI precipitation and Mireye drought/temperature/heat paths without inventing thresholds.

Locked precip architecture:

```yaml
F05 precipitation primary path:
  source: NOAA/NCEI Direct Climate Normals NetCDF
  variable: annprcp_norm
  cper_value: 345.74
  unit: mm/year
  role: CANONICAL_LAND_FACT
ACIS:
  role: SECONDARY_QA_OR_FALLBACK
  canonical_runtime_source: false
```

Completed after the live gate:

1. Narrow Cow-Calf / Sheep qualitative requirements with source records.
2. v0.1 data-quality / context deterministic rules (`docs/F05_CLIMATE_DROUGHT_DETERMINISTIC_RULES.yaml`).

Engine wiring complete for v0.1 data-quality/context rules. CPER F05 evaluates to `CONTEXT_DEPENDENT` with `ranking_effect: NONE`.

Remaining outside this Factor freeze:

1. Keep Flood/Wetness as a separate later Factor.
2. Optional later methods (drought history, seasonality, variability) require a new reviewed version.
3. Do not add climate suitability thresholds without a new reviewed version.
