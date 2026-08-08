# F07 Live Data Gate Results — CPER

> Status: `LIVE_VERIFIED`  
> Date: 2026-08-08  
> Source: US Census TIGER/Line 2025 All Roads  
> Adapter: `F07_TIGER_LINE_2025_ALL_ROADS_ADAPTER@0.1.0`  
> OSM consulted: `false`  
> Edges fallback used: `false`

## Decision

```yaml
live_gate_id: F07_TIGER2025_ALL_ROADS_CPER
status: LIVE_VERIFIED
signal: CONTEXT_DEPENDENT
ranking_effect: NONE
input_quality_state: ROAD_CONTEXT_COMPLETE
county_coverage_status: COMPLETE
legal_access_inferred: false
usable_entrance_inferred: false
```

## County coverage

| Field | Value |
|---|---|
| requested_county_fips | `08123` (Weld County, CO) |
| loaded_county_fips | `08123` |
| missing_county_fips | `[]` |
| status | `COMPLETE` |

County membership was resolved by intersecting the 5000 m projected search window with TIGER/Line 2025 national county polygons (`tl_2025_us_county.zip`). Only Weld County intersects the CPER engineering-geometry window.

## Derived measurements

| Variable | Value |
|---|---|
| search_window_m | 5000 |
| working_crs | EPSG:32613 |
| mapped_road_feature_count_in_search_window | 45 |
| road_parcel_contact_status | INTERSECTS |
| intersects_feature_count | 4 |
| touches_feature_count | 0 |
| nearest_mapped_road_distance_m | 0.0 |
| nearest_road_feature_id | 110417652669 |
| nearest_road_class_context | S1400 |

Nearest-feature selection uses distance ascending, then stable `LINEARID` ascending.

## Provenance

- Canonical source id: `US_CENSUS_TIGER_LINE_2025_ALL_ROADS`
- Product vintage: `2025`
- County inventory: `https://www2.census.gov/geo/tiger/TIGER2025/COUNTY/tl_2025_us_county.zip`
- Roads product path: `https://www2.census.gov/geo/tiger/TIGER2025/ROADS/tl_2025_{county_fips}_roads.zip`
- Algorithm version: `F07_ROAD_PHYSICAL_ACCESS_DERIVATION@0.1.0`
- Geometry reference: `test-data/engineering_test_geometry_cper_001.geojson`
- Window roads artifact: `test-data/live-results/cper/f07_tiger2025_all_roads_search_window.geojson`
- Derivation result: `test-data/live-results/cper/f07_derivation_result_2026-08-08.json`
- Live-gate JSON: `test-data/live-results/cper/f07_live_gate_cper_2026-08-08.json`

Downloaded zip caches are stored under `test-data/live-results/cper/tiger2025_cache/` (gitignored).

## Non-claims preserved

- Mapped road contact ≠ legal access
- Mapped road contact ≠ usable entrance / gate
- Euclidean centerline distance ≠ drive time or network distance
- Empty/non-empty window ≠ landlocked certainty or REJECT
- MTFCC ≠ suitability class
- No Cow-Calf vs Sheep ranking from F07

## Remaining limitations

1. Private/ranch roads absent from TIGER All Roads remain unknown.
2. Legal access / easement / deeded ROW are diligence-only and not derived.
3. Seasonal passability, truckability, and bridge/load limits are deferred.
4. Network routing / travel time are deferred.
5. Edges road-filtered fallback remains documented only and is not implemented in v0.1.
6. OSM remains deferred entirely from F07 v0.1.

## Freeze-gate recommendation

**Conditional PASS for freeze review.** Core implementation, adapter, CPER live gate, county-coverage completeness, contact detail, tie-break, engine wiring, and golden suite are in place with `ranking_effect: NONE`. Human freeze review should confirm the CPER live-gate artifacts and that no legal-access or threshold language entered MatchResult/demo surfaces before marking `FROZEN_V0_1` and authorizing F08.
