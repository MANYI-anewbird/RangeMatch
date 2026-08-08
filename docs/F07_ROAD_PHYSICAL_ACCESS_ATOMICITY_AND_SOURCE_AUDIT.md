# F07 Atomicity and Source Audit — Road and Physical Access Context

> Status: `FIRST-STAGE AUDIT APPROVED — IMPLEMENTATION AUTHORIZED`  
> Language: English  
> Factor ID: `F07_ROAD_AND_PHYSICAL_ACCESS`  
> Review date: 2026-08-08  
> Authorization: `APPROVED_V0_1_FOR_IMPLEMENTATION`  
> Implementation: `AUTHORIZED_FOR_IMPLEMENTATION`  
> Prior gate: F06 `FROZEN_V0_1`  
> F08: `NOT_YET_AUTHORIZED`  
> F02 coverage upgrade: `DEFERRED_FOR_DEMO`

## 1. Factor Boundary Decision

`Road and Physical Access Context` converts parcel geometry plus a reviewed mapped-road network into reproducible **physical-proximity / contact context**.

It is **not**:

- a legal-access, easement, deeded right-of-way, or title Factor;
- a suitability, truckability, or all-weather operability Factor;
- a travel-time, routing, or logistics-cost Factor;
- a Cow-Calf versus Sheep ranking Factor;
- a substitute for F06 parcel configuration;
- proof that livestock, equipment, or buyers can enter the parcel;
- a profitability or carrying-capacity Factor;
- a distance-threshold decision Factor.

Canonical measurement inputs:

```text
parcel geometry (Polygon / MultiPolygon; EPSG:4326; geometry_hash)
+ mapped road centerlines from US Census TIGER/Line 2025 All Roads
+ declared working CRS (local UTM, same policy family as F06)
```

Legal access, private ranch roads absent from the mapped layer, gates, driveway usable width, bridge/load limits, and seasonal closure require separate diligence and are out of v0.1 Land Facts.

## 2. Candidate Data Sources

| Source | Role | v0.1 decision | Notes |
|---|---|---|---|
| US Census TIGER/Line **2025 All Roads** | Canonical mapped-road inventory for CONUS engineering demo | `CANONICAL` | `source_id: US_CENSUS_TIGER_LINE_2025_ALL_ROADS`; county zip product path pinned below |
| TIGER/Line **Edges** filtered to road MTFCC codes | Separately versioned fallback only | `FALLBACK_SEPARATELY_VERSIONED` | **Not** an equivalent of All Roads; different `source_id` and `algorithm_version` when used |
| OpenStreetMap highway ways | Out of F07 v0.1 | `DEFER` | Not secondary QA in v0.1; no OSM fetch, conflict, or averaging in this slice |
| USFS / BLM / state forest road layers | Jurisdiction-specific densification | `DEFER` | Useful later for public-land parcels; not a national canonical sole source |
| NAVTEQ/HERE/Google proprietary roads | Commercial basemap | `OUT_OF_SCOPE_FOR_DEMO` | Licensing and reproducibility barriers |
| Parcel plat / title / easement records | Legal access | `DEFER` — diligence only | Required for legal claims; not substitutable by mapped roads |
| Aerial imagery driveway interpretation | Physical entrance hypothesis | `DEFER` | Remote hypothesis only; cannot establish legal or operational access in v0.1 |

### Canonical source (locked)

```text
source_id: US_CENSUS_TIGER_LINE_2025_ALL_ROADS
product: TIGER/Line 2025 All Roads
product_path_pattern: https://www2.census.gov/geo/tiger/TIGER2025/ROADS/tl_2025_{STATEFP}{COUNTYFP}_roads.zip
vintage: 2025 (must be recorded on every result)
geometry: road centerlines
attributes_retained: MTFCC (or equivalent class), LINEARID / persistent id when present, FULLNAME when present
```

### Fallback source (not equivalent)

```text
source_id: US_CENSUS_TIGER_LINE_EDGES_ROAD_FILTERED   # separately versioned when activated
role: FALLBACK_ONLY
equivalence_to_all_roads: false
requirement: different algorithm_version and source_id than All Roads path
```

### County coverage policy (locked)

For the default `search_window_m = 5000` fetch region:

1. Identify **all** counties whose areas intersect the 5000 m search window.
2. Request **every** corresponding All Roads county zip (`requested_county_fips`).
3. Load and record successfully loaded counties (`loaded_county_fips`).
4. If `loaded_county_fips` is a proper subset of `requested_county_fips`, coverage is `PARTIAL` or `UNKNOWN` → signal `NEEDS_VERIFICATION`. Do **not** silently measure as if coverage were complete.

Live fetch path, adapter, and CPER fixture hash are **not** part of this audit deliverable; they belong to the authorized implementation / live-data gate. Audit corrections above are locked before that work.

## 3. Candidate Variable Decisions

| Variable ID | Object | Atomic vs derived | v0.1 decision |
|---|---|---|---|
| `VAR_F07_MAPPED_ROAD_FEATURE_COUNT_IN_SEARCH_WINDOW` | Count of mapped road features retrieved in the declared search window | Derived inventory count | `INCLUDE` |
| `VAR_F07_ROAD_PARCEL_CONTACT_STATUS` | Geometric contact detail: INTERSECTS vs TOUCHES (and non-contact / empty / unknown) | Derived topology | `INCLUDE` |
| `VAR_F07_NEAREST_MAPPED_ROAD_DISTANCE_M` | Minimum parcel↔road centerline distance in working CRS | Derived measurement | `INCLUDE` |
| `VAR_F07_NEAREST_ROAD_CLASS_CONTEXT` | Class/MTFCC (or equivalent) of the nearest mapped road | Controlled category context | `INCLUDE` |
| `VAR_F07_NEAREST_ROAD_FEATURE_ID` | Persistent id of nearest feature when available (LINEARID preferred) | Identity / provenance | `INCLUDE` |
| `VAR_F07_SEARCH_WINDOW_M` | Adapter retrieval radius around parcel | Adapter parameter (recorded) | `INCLUDE` as provenance, **not** a suitability threshold |
| `VAR_F07_ROAD_SOURCE_COVERAGE_STATUS` | Whether road fetch/coverage is usable for measurement | Coverage/QA property | `INCLUDE` |
| `VAR_F07_LEGAL_ACCESS_STATUS` | Deeded / easement / permitted access | Legal diligence | `DEFER` |
| `VAR_F07_NETWORK_DRIVE_DISTANCE_M` | Routed network distance | Operational routing | `DEFER` |
| `VAR_F07_TRAVEL_TIME_CONTEXT` | Drive-time estimate | Logistics model | `DEFER` |
| `VAR_F07_SEASONAL_PASSABILITY` | Mud/snow/closure operability | Field/ops evidence | `DEFER` |
| `VAR_F07_PRIVATE_RANCH_ROAD_INVENTORY` | Unmapped internal ranch roads | Incomplete by design in national layers | `DEFER` |
| `VAR_F07_GATE_OR_ENTRANCE_LOCATION` | Physical entrance points | Field/remote review | `DEFER` |
| `VAR_F07_BRIDGE_OR_LOAD_LIMIT_CONTEXT` | Crossing constraints | Asset inventory | `DEFER` |

## 4. Non-Equivalences

```text
mapped road != legal access
mapped road != deeded easement or public right-of-way certainty
mapped road centerline intersection != usable driveway / gate / entrance
nearest mapped road != operational truck access
Euclidean parcel-to-centerline distance != network drive distance
Euclidean distance != travel time or logistics cost
TIGER absence != landlocked parcel
TIGER All Roads != TIGER Edges road-filtered (fallback is separately versioned)
OSM track != public legal access (OSM deferred from F07 v0.1 entirely)
road class / MTFCC != suitability class
search window != "too far" threshold
F07 physical-proximity context != F06 parcel shape/size
F07 context != Cow-Calf or Sheep preference
F07 context != profitability or carrying capacity
no mapped road in window != REJECT / unsuitable land
incomplete county All-Roads load != silent complete measure
```

## 5. CRS and Geometry Policy

Align with frozen F06 input boundaries where parcel geometry is involved:

1. Parcel `source_crs` for v0.1: **EPSG:4326 only**.
2. FeatureCollection parcel inputs: **exactly one** Polygon/MultiPolygon Feature; no silent `features[0]`; no auto-union.
3. Working CRS: **local UTM zone from parcel centroid**, meters.
4. Do **not** compute planar distances in longitude/latitude degrees.
5. Road geometries must be projected into the same working CRS before distance/contact.
6. If UTM selection fails (zone crossing, unsupported latitude, invalid lon/lat bounds): `CRS_UNSUPPORTED` → signal `NEEDS_VERIFICATION`.
7. Invalid / empty parcel geometry: do not measure roads; `NEEDS_VERIFICATION` or `UNKNOWN` as applicable.
8. Geometry hash change invalidates prior F07 measurements.
9. MultiPolygon parcels: nearest distance is the min over the whole geometry.

## 6. Frozen Formulas (v0.1)

### Search window (adapter parameter, not a decision threshold)

```text
search_window_m = W   # declared retrieval radius; default 5000
fetch_region = buffer(project(parcel → working_crs), W)
```

`W` is recorded on every result. Absence of roads inside `W` means **unobserved beyond the fetch window**, not a suitability failure.

### County All-Roads completeness

```text
requested_county_fips = counties intersecting fetch_region
loaded_county_fips    = counties successfully loaded from All Roads zips

if loaded_county_fips != requested_county_fips:
  road_source_coverage_status ∈ {PARTIAL, UNKNOWN}
  → NEEDS_VERIFICATION   # no silent distance/contact measure
```

Both `requested_county_fips` and `loaded_county_fips` are required provenance fields.

### Contact status (detail preserved)

```text
roads_in_window = road features intersecting fetch_region
d_i = distance(parcel_projected, road_i_projected)   # meters; 0 if intersects or touches

# Topology detail MUST be preserved (not collapsed away):
road_parcel_contact_status =
  INTERSECTS                 if any road intersects parcel interior/boundary as INTERSECTS
  TOUCHES                    if no INTERSECTS and any road TOUCHES parcel
  NO_CONTACT_IN_WINDOW       if roads_in_window non-empty and all d_i > 0
  NO_MAPPED_ROAD_IN_SEARCH_WINDOW if roads_in_window empty (and county coverage complete)
  UNKNOWN                    if road source/coverage unusable

# Optional combined summary may exist (e.g. INTERSECTS_OR_TOUCHES) but MUST NOT
# replace INTERSECTS vs TOUCHES detail.
```

### Nearest distance and stable tie-break

```text
nearest_mapped_road_distance_m = min(d_i) over roads_in_window
unit: meter

# Tie-break when multiple features share the same min distance:
#   1) distance_m ascending (already min)
#   2) stable feature ID ascending (LINEARID preferred; else persistent id)
nearest_road_feature = argmin (distance_m, stable_feature_id)
nearest_road_class_context = MTFCC_or_equivalent(nearest_road_feature)  # context only
nearest_road_feature_id = persistent_id(nearest_road_feature) if available else null
```

If `roads_in_window` is empty and county coverage is complete, distance is `null` and status records `NO_MAPPED_ROAD_IN_SEARCH_WINDOW`.

### Counts and class context

```text
mapped_road_feature_count_in_search_window = |roads_in_window|
```

No distance band classes (`close` / `moderate` / `far`) and no MTFCC→suitability mapping are approved.

### Algorithm version

```text
algorithm_version: F07_ROAD_PHYSICAL_ACCESS_DERIVATION@0.1.0
  # All Roads canonical path only

# If Edges road-filtered fallback is ever activated:
#   different source_id AND different algorithm_version (not interchangeable)
```

Must be written on every result once implementation exists.

## 7. Evidence / QA States

| `input_quality_state` | Meaning |
|---|---|
| `ROAD_CONTEXT_COMPLETE` | Parcel geometry usable; all requested county All-Roads files loaded; contact/distance derived with provenance |
| `NO_MAPPED_ROAD_IN_SEARCH_WINDOW` | Usable complete fetch; zero road features in window — context fact, not land failure |
| `ROAD_SOURCE_INCOMPLETE` | Fetch partial (including incomplete county set), vintage missing, required ids/class missing, or coverage unquantified |
| `PARTIAL` | County All-Roads coverage incomplete relative to `requested_county_fips` |
| `CRS_UNSUPPORTED` | Parcel/road CRS policy cannot be applied |
| `GEOMETRY_INVALID_OR_EMPTY` | Parcel geometry unusable |
| `MISSING` | Parcel or road inputs absent |
| `UNKNOWN` | Coverage/usability cannot be established |

`CONFLICTING_SOURCES` is reserved for future multi-source QA; **OSM is deferred from F07 v0.1** and must not be consulted as secondary QA in this slice.

## 8. Signal Policy

Allowed signals only:

- `CONTEXT_DEPENDENT` — measurable road proximity/contact context with complete provenance  
- `NEEDS_VERIFICATION` — incomplete county coverage, CRS/geometry failure, or source problems  
- `UNKNOWN` — missing inputs  

Always:

```text
ranking_effect: NONE
```

`NO_MAPPED_ROAD_IN_SEARCH_WINDOW` is still context (`CONTEXT_DEPENDENT`) with diligence to check legal access and unmapped ranch roads — **not** `REJECT`.

Incomplete county coverage (`PARTIAL` / `UNKNOWN` / `ROAD_SOURCE_INCOMPLETE`) → `NEEDS_VERIFICATION`, not a silent measure.

## 9. Provenance Requirements

Every F07 Factor result must preserve:

- parcel `geometry_id` / `geometry_reference` / `geometry_hash`
- `source_crs` / `working_crs`
- road `source_id` / product / vintage / fetch timestamp (`US_CENSUS_TIGER_LINE_2025_ALL_ROADS` for canonical path)
- `requested_county_fips` / `loaded_county_fips`
- response or artifact hash for the road extract used
- `search_window_m`
- `algorithm_version`
- contact topology detail (`INTERSECTS` vs `TOUCHES` when applicable)
- limitations and unknowns
- explicit statement that mapped roads do not establish legal access

## 10. Prohibited Interpretations

- Mapped road presence → ADVANCE  
- No mapped road in window → REJECT / unsuitable / landlocked certainty  
- Distance or MTFCC → suitability class or species ranking  
- Centerline contact → legal access or operational entrance  
- Treating Edges road-filtered as equivalent to All Roads without separate versioning  
- Silent measure under incomplete county All-Roads coverage  
- OSM densification / secondary QA in F07 v0.1  
- F07 claiming F08 vegetation, F03 water access routes, or fencing cost  
- Any Cow-Calf vs Sheep ranking from road metrics  
- Profitability, carrying-capacity, or distance-threshold conclusions  

## 11. Human Review Decisions (locked)

1. **Canonical source:** TIGER/Line **2025 All Roads** (`US_CENSUS_TIGER_LINE_2025_ALL_ROADS`); product path pattern locked.  
2. **Edges road-filtered:** separately versioned **FALLBACK** only — not equivalent.  
3. **Default `search_window_m = 5000`:** adapter fetch parameter (not a threshold).  
4. **INTERSECTS vs TOUCHES:** detail preserved in v0.1; optional combined summary may exist but must not replace detail.  
5. **OSM:** deferred from F07 v0.1 entirely (not secondary QA).  
6. **MultiPolygon nearest distance:** min over the whole geometry.  
7. **County completeness:** all intersecting county All-Roads files required; incomplete → `NEEDS_VERIFICATION`.  
8. **Nearest-feature tie-break:** `distance_m` ascending, then stable feature ID ascending (LINEARID preferred).

## 12. Implementation Readiness Recommendation

**F07 is APPROVED_V0_1_FOR_IMPLEMENTATION.** Human corrections above are applied; deterministic implementation may begin.

Locked audit artifacts:

- [`F07_ROAD_PHYSICAL_ACCESS_ATOMICITY_AND_SOURCE_AUDIT.md`](./F07_ROAD_PHYSICAL_ACCESS_ATOMICITY_AND_SOURCE_AUDIT.md)
- [`F07_DATA_SOURCE_AUDIT.yaml`](./F07_DATA_SOURCE_AUDIT.yaml)
- [`F07_ROAD_PHYSICAL_ACCESS_DERIVATION_SPEC.yaml`](./F07_ROAD_PHYSICAL_ACCESS_DERIVATION_SPEC.yaml)
- [`F07_ROAD_PHYSICAL_ACCESS_DETERMINISTIC_RULES.yaml`](./F07_ROAD_PHYSICAL_ACCESS_DETERMINISTIC_RULES.yaml)
- [`F07_ROAD_PHYSICAL_ACCESS_GOLDEN_TESTS.yaml`](./F07_ROAD_PHYSICAL_ACCESS_GOLDEN_TESTS.yaml)

Governance retained:

- `ranking_effect: NONE`
- context only; no legal-access, entrance, profitability, carrying-capacity, species-ranking, or distance-threshold conclusions
- empty window is `CONTEXT_DEPENDENT` with diligence, not `REJECT`

Still do **not**:

- Start F08 (remains `NOT_YET_AUTHORIZED`).  
- Deepen F02 coverage before the demo.  
- Invent distance/class thresholds or legal-access claims.  
- Treat All Roads and Edges road-filtered as interchangeable.
