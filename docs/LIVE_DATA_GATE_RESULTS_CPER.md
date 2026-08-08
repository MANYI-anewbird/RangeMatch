# CPER Live Data Gate Results

> Geometry: `ENGINEERING_TEST_GEOMETRY_CPER_001`  
> Test date: 2026-08-07  
> Scope: F01 Topography and F02 Herbaceous Resource  
> This is a data-pipeline test, not an agricultural suitability determination.

## F01 — USGS 3DEP

The USGS 3DEP ImageServer successfully exported a buffered, approximately 10-meter bare-earth DEM in UTM zone 13N. RangeMatch clipped the derived grid by the parcel cell-center rule and computed the frozen Horn slope and circular aspect outputs.

```yaml
retrieval: PASSED
derivation: PASSED
quality_state: PARCEL_COMPLETE
source_lock:
  mosaic_method: esriMosaicLockRaster
  object_id: 4878
  tile_id: USGS_13_n41w105
  title: USGS 1/3 Arc Second n41w105 20260708
  acquisition_date: 2021-09-22
  publication_date: 2026-07-08
  vertical_datum: NAVD88
parcel_cell_count: 13904
represented_cell_center_area_m2: 1396148.118585952
elevation_m:
  coverage_fraction: 1.0
  minimum: 1642.6004638671875
  maximum: 1673.9375
  mean: 1653.886711682494
  median: 1653.8697509765625
slope_degrees:
  coverage_fraction: 1.0
  minimum: 0.007808418630414449
  maximum: 15.240698617612289
  mean: 2.7665328388681374
  median: 2.395727249934432
aspect:
  coverage_fraction: 1.0
  mean_eastness: 0.09129856760794036
  mean_northness: -0.28668371218180433
```

The numeric outputs are Land Facts only. They do not authorize a slope threshold, species score, usable-area estimate, or hard exclusion.

## F02 — USDA-ARS RAP v3

The official RAP polygon API accepted the CPER GeoJSON Feature with `mask=true` and `year=2025`.

```yaml
coverV3:
  runtime_status: VERIFIED_HTTP_200
  AFG_percent: 12.567423553079283
  PFG_percent: 32.98657702821575
  SHR_percent: 6.727234043361567
  TRE_percent: 0.10557150211526739
  LTR_percent: 12.472237472241313
  BGR_percent: 26.41437204009802
productionV3:
  runtime_status: VERIFIED_HTTP_200
  unit: pounds_per_acre
  AFG: 271.9241124966907
  PFG: 665.7539350485226
  HER: 937.6780475452124
production16dayV3:
  runtime_status: VERIFIED_HTTP_200
  interval_count: 23
  first_interval: 2025-01-16
  last_interval: 2025-12-31
  summed_AFG_pounds_per_acre: 271.92411249669146
  summed_PFG_pounds_per_acre: 665.7539350485227
  summed_HER_pounds_per_acre: 937.6780475452128
  annual_consistency_check: PASSED_WITH_FLOATING_POINT_TOLERANCE
```

RAP outputs are modeled functional-group cover and modeled production. They are not field-verified botanical composition, standing biomass, available forage, palatability, nutritive value, carrying capacity, or stocking rate.

## Gate Decision

| Path | Decision |
|---|---|
| USGS 3DEP retrieval | Passed |
| F01 elevation/slope/aspect derivation | Passed with locked 1/3 arc-second source provenance |
| RAP `coverV3` polygon contract | Passed |
| RAP `productionV3` polygon contract | Passed |
| RAP `production16dayV3` polygon contract | Passed; 23 intervals and annual-sum consistency verified |

The F01 parcel data path and the three reviewed RAP polygon contracts have passed this engineering geometry. Production readiness still requires frozen F02 temporal/variability derivations, coverage and masking rules, improved-pasture scope handling, and golden tests.

## F02 Baseline Method Sanity Check

The v0.1 baseline method selected the ten most recent aligned complete years, 2016-2025, from 40 returned annual records (1986-2025).

```yaml
baseline_status: COMPLETE
quality_state: COVERAGE_UNQUANTIFIED
selected_years: [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
valid_aligned_year_count: 10
HER_production_lbs_per_acre:
  minimum: 576.8850191455485
  maximum: 1240.634161944852
  mean: 959.3139946688398
  median: 996.9935092257698
  p25: 834.5020382401939
  p75: 1129.403755252743
relative_IQR: 0.29579100995507923
```

The relative IQR is descriptive context only. No low/moderate/high variability class or operation penalty is approved. The result remains `COVERAGE_UNQUANTIFIED` because the aggregate API response does not report eligible, masked, no-data, or valid pixel areas.
