# Mireye Live Recheck Gate — Success

> Date: 2026-08-08
> Network classification: `TRANSPORT_OK`
> Runtime status: `LIVE_VERIFIED_ON_CURRENT_NETWORK`

## Gate results

```yaml
transport:
  dns: PASS
  tls: PASS
  healthz_http_status: 200
  safebrowse_redirect: false

catalog:
  http_status: 200
  status: COMPATIBLE
  observed_version: 0.14.0
  field_count: 304
  missing_required_fields: 0
  unit_mismatches: 0
  type_mismatches: 0

lookup:
  input: PUBLIC_DOCUMENTATION_EXAMPLE_ADDRESS
  http_status: 200
  transport_ok: true
  disposition: resolved
  parcel_status: PARCEL_DATA_UNAVAILABLE
  parcel_geometry_returned: false
  fixture_fallback: false

cper_contexts:
  PROPERTY_DILIGENCE_CONTEXT: COMPLETE
  POINT_LAND_CONTEXT: COMPLETE
  POINT_HAZARD_CONTEXT: COMPLETE
  partial_failures: 0

confirmed_parcel_investigation:
  input: CPER_PUBLIC_COORDINATE
  lookup_http_status: 200
  parcel_candidate_count: 1
  parcel_confirmation: PARCEL_CONFIRMED
  property_context: COMPLETE
  point_land_context: PARTIAL
  point_hazard_context: COMPLETE
  failed_contexts: 0
  investigation_status: PARTIAL
  f06_geometry_compute: SUCCEEDED
  f06_signal: CONTEXT_DEPENDENT
  remaining_f01_f05_f07_f08_live_collection: NOT_PERFORMED
  fixture_substitution: false

f01_3dep_confirmed_parcel_gate:
  status: LIVE_VERIFIED
  source_product: USGS_3DEP_1_3_ARC_SECOND_SEAMLESS_DEM
  source_tile: n41w105
  coverage_fraction: 1.0
  valid_slope_cells: 19683
  elevation_median_m: 1649.6339111328125
  slope_median_degrees: 1.891524753346898
  slope_p90_degrees: 5.171279222147744
  signal_interpretation: CONTEXT_ONLY_NO_SUITABILITY_THRESHOLD
  ranking_effect: NONE
  production_adapter: USGS_3DEP_F01_ADAPTER@0.1.0
  executor_wired: true
  unified_output_coverage: COMPLETE
  artifact_hash: 37390225c1354290adda92ae61957e8c77761385838904a6ee4251a5daded33a

f02_f08_rap_confirmed_parcel_gate:
  status: LIVE_VERIFIED
  production_adapter: USDA_ARS_RAP_V3_AGGREGATE_ADAPTER@0.1.0
  coverV3_request_count: 1
  productionV3_request_count: 1
  duplicate_coverV3_fetch: false
  f08_reuses_f02_cover_artifact: true
  cover_response_hash: 31189e94767499745db98db2b25ea5aff627a5e9b58018c05cc12cf2a16dcfc2
  applicability_status: UNKNOWN
  coverage_status: COVERAGE_UNQUANTIFIED
  f02_signal: NEEDS_VERIFICATION
  f08_signal: NEEDS_VERIFICATION
  ranking_effect: NONE

f05_noaa_confirmed_parcel_gate:
  status: LIVE_PATH_VERIFIED_FROM_CANONICAL_LOCAL_NETCDF
  production_adapter: NOAA_NCEI_DIRECT_NORMALS_ADAPTER@0.1.0
  variable: annprcp_norm
  normals_period: 1991-2020
  value_mm: 345.74
  coverage_status: COMPLETE_SINGLE_CELL_COVERS_SMALL_PARCEL
  artifact_hash: 6d1dcb9620f11d50f6da41910c642753198c8dffbf526607630bae0a0f75e1d2
  signal: CONTEXT_DEPENDENT
  ranking_effect: NONE
  mutates_f02_f03_f04: false

safety:
  credential_scan: PASS
  owner_pii_persisted: false
  f01_f08_writes: false
  match_result_changed: false
```

## F07 confirmed-parcel runtime integration

The confirmed-parcel runtime now derives F07 from the canonical U.S. Census
TIGER/Line 2025 All Roads path. The adapter resolves every county intersecting
the 5 km retrieval window, preserves `INTERSECTS` versus `TOUCHES`, and uses
the frozen stable nearest-road tie-break. Only mapped-road physical context
enters the Land Profile: legal access, a usable entrance, drive time,
passability, and landlocked status remain explicitly unresolved.

For the confirmed CPER geometry, the controlled cached-source gate returned
complete Weld County coverage, 54 mapped features in the window,
`INTERSECTS`, and nearest mapped-road distance `0.0 m`. These are measured
context facts, not suitability or legal-access conclusions;
`ranking_effect` remains `NONE`.

The complete controlled LIVE investigation also passed after parcel
confirmation: F01/F02/F05/F07/F08 were collected with no Factor-local
failures; F06 was derived from geometry; Cow-Calf and Sheep both remained
`HOLD`; ranking remained prohibited. The investigation remains `PARTIAL`
because F03 and F04 have not yet been connected to this live parcel path.

## Interpretation

Mireye transport, authentication, the public field catalog, `/v1/lookup`, and the three normalized CPER context paths are live-verified from the current network. The lookup example did not return a parcel polygon; this is an honest `PARCEL_DATA_UNAVAILABLE` result and does not invalidate transport or authentication success.

A second gate used a public CPER coordinate. Mireye returned one Regrid parcel polygon, RangeMatch explicitly confirmed its geometry hash, and the Investigation Executor consumed all three live context paths. The final rerun returned all three contexts as `COMPLETE`. F06 was computed deterministically from the confirmed geometry and entered Unified Output as `CONTEXT_DEPENDENT` with `ranking_effect: NONE`. The investigation remained `PARTIAL` because F01–F05, F07, and F08 live collection is not yet wired for the newly resolved geometry; no demo Factor fixture was substituted.

RangeMatch must continue to require an actual returned polygon plus explicit user confirmation before an investigation starts. A `resolved` address alone is not a parcel.

## Artifacts

- `test-data/mireye-normalized/diagnostics/mireye_transport_recheck_after_network_change_2026-08-08.json`
- `test-data/mireye-normalized/live-recheck/catalog_gate_after_network_change_2026-08-08.json`
- `test-data/mireye-normalized/live-recheck/lookup_live_gate_berdoll_2026-08-08.json`
- `test-data/mireye-normalized/live-recheck/cper-contexts-2026-08-08/`
- `test-data/mireye-normalized/live-recheck/cper_live_coordinate_parcel_investigation_gate_2026-08-08.json`
- `test-data/live-results/cper-live-confirmed-parcel/f01/f01_live_gate_summary.json`
- `test-data/live-results/cper-live-confirmed-parcel/f01/f01_derivation_result.json`

All stored artifacts are sanitized and must remain free of API tokens and Authorization values.
