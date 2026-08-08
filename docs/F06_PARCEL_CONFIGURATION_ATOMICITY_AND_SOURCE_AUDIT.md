# F06 Atomicity and Source Audit — Parcel Configuration

> Status: `FIRST-STAGE AUDIT APPROVED — IMPLEMENTATION AUTHORIZED`  
> Language: English  
> Factor ID: `F06_PARCEL_CONFIGURATION`  
> Review date: 2026-08-08  
> Authorization: `AUTHORIZED_FOR_FIRST_STAGE_AUDIT`  
> F07: `AUTHORIZED_FOR_FIRST_STAGE_AUDIT` after F06 freeze recheck  
> F02 coverage upgrade: `DEFERRED_FOR_DEMO` (existing limitations preserved)

## 1. Factor Boundary Decision

`Parcel Configuration` converts parcel geometry into reproducible measurable context.

It is **not**:

- a suitability Factor;
- a fencing-cost or profitability Factor;
- a carrying-capacity Factor;
- a Cow-Calf versus Sheep ranking Factor;
- a substitute for F01 topography or F07 road/physical access.

Canonical source:

```text
parcel geometry (Polygon / MultiPolygon) + geometry_hash + declared CRS
```

No remote land-cover, soils, hydrography, or road network is required for v0.1 F06.

## 2. Candidate Variable Decisions

| Variable ID | Object | Atomic vs derived | v0.1 decision |
|---|---|---|---|
| `VAR_F06_PARCEL_AREA` | Parcel area | Derived measurement from geometry | `INCLUDE` |
| `VAR_F06_PARCEL_PERIMETER` | Parcel exterior perimeter | Derived measurement from geometry | `INCLUDE` |
| `VAR_F06_POLYGON_PART_COUNT` | Count of polygon parts | Discrete geometry property | `INCLUDE` |
| `VAR_F06_DISCONNECTED_PART_COUNT` | Count of disconnected components | Duplicate of part count for v0.1 simple MultiPolygon policy | `DEFER_AS_REDUNDANT` |
| `VAR_F06_COMPACTNESS` | Isoperimetric quotient `4πA/P²` | Derived from area + perimeter | `INCLUDE` |
| `VAR_F06_PERIMETER_TO_AREA_RATIO` | `P/A` | Derived; informationally redundant with compactness for screening | `DEFER_AS_REDUNDANT` |
| `VAR_F06_BOUNDARY_COMPLEXITY` | Unspecified complexity index | No independent frozen formula | `DEFER` |
| `VAR_F06_NARROW_SECTION_CONTEXT` | Narrow-corridor / pinch-point context | Requires skeleton/width method not yet reviewed | `DEFER` |
| `VAR_F06_GEOMETRY_VALIDITY` | OGC-validity / repair status | Geometry QA property | `INCLUDE` |
| `VAR_F06_GEOMETRY_COVERAGE_STATUS` | Whether geometry is usable for parcel measurement | Coverage/QA property | `INCLUDE` |

## 3. Non-Equivalences

```text
parcel area != grazable area
parcel area != carrying capacity
parcel perimeter != fencing cost
compactness != operational efficiency
compactness != suitability
multi-part geometry != unsuitable land
invalid geometry != land without value
projected measurement != legal survey acreage
F06 context != F07 road/physical access
F06 context != Cow-Calf or Sheep preference
```

## 4. CRS and Measurement Policy

### Required

1. Canonical input geometry is WGS84 longitude/latitude (`EPSG:4326`) or another explicitly declared geographic CRS.
2. **Do not** compute planar area or perimeter in longitude/latitude degrees.
3. v0.1 working CRS for CONUS engineering parcels: **local UTM zone from parcel centroid**, meters (`EPSG:326xx` / `EPSG:327xx` as applicable), matching F01 working-grid policy.
4. Preserve and report:
   - `working_crs` (EPSG code);
   - `source_crs`;
   - `geometry_hash`;
   - `algorithm_version`;
   - raw measurements and units;
   - provenance (`fetched_or_derived_at`, adapter/reviewer id).
5. If the parcel crosses a UTM zone boundary, spans unsupported latitude, or otherwise fails CRS selection: `input_quality_state = NEEDS_VERIFICATION` / signal `NEEDS_VERIFICATION`. Do not silently choose an arbitrary projection.

### Optional later (not required for first implementation)

- Geodesic area/perimeter (e.g., GeographicLib) as secondary QA against UTM results.
- Equal-area projected CRS review for parcels outside CONUS demo scope.

## 5. Proposed Frozen Formulas (pre-implementation)

Formulas must be frozen before code lands. Proposed v0.1 freeze:

### Area

```text
A = area(project(geometry → working_crs))
unit: square_meter
```

Standard polygon semantics apply: interior rings are subtracted from area.

Also store convenience display fields only after raw SI values exist:

```text
area_ha = A / 10000
area_acre = A / 4046.8564224   # international acre display conversion
```

Display conversions are not separate Land Facts and must not become thresholds.

### Perimeter

```text
P = length(exterior_rings(project(geometry → working_crs)))
unit: meter
```

Interior rings (holes) are **excluded** from v0.1 perimeter unless a later reviewed revision explicitly includes them. Hole presence is recorded as a limitation/note.

### Polygon part count

```text
part_count =
  1 if geometry.type == Polygon
  N if geometry.type == MultiPolygon with N polygon parts
```

Empty geometry → measurement blocked (`MISSING` / `UNKNOWN` path).

### Compactness (isoperimetric quotient)

```text
C = 4 * π * A / (P^2)   when P > 0 and A > 0
unit: dimensionless
range: (0, 1] for simple closed shapes in Euclidean plane
```

If `P == 0` or `A == 0`: compactness = `null`, signal path `NEEDS_VERIFICATION` or `UNKNOWN` per rules.

### Geometry validity

```text
validity_status ∈ {VALID, INVALID, REPAIRED_FOR_MEASUREMENT, UNKNOWN}
```

`REPAIRED_FOR_MEASUREMENT` requires recording the repair method and that legal/survey boundaries were not altered as authority.

### Geometry coverage status

```text
coverage_status ∈ {
  PARCEL_GEOMETRY_COMPLETE,
  EMPTY_GEOMETRY,
  INVALID_UNUSABLE,
  CRS_UNSUPPORTED,
  COVERAGE_UNQUANTIFIED
}
```

`PARCEL_GEOMETRY_COMPLETE` means a measurable non-empty geometry is available for F06 derivation. It does **not** mean RAP/soil/climate coverage is complete.

## 6. Redundant / Deferred Variables

| Variable | Decision | Reason |
|---|---|---|
| `disconnected_part_count` | Deferred redundant | For v0.1 MultiPolygon policy, equals `polygon_part_count` |
| `perimeter_to_area_ratio` | Deferred redundant | Function of A and P; compactness already encodes shape-from-A/P |
| `boundary_complexity` | Deferred | No independent reviewed formula |
| `narrow_section_context` | Deferred | Needs skeleton / minimum-width method review; not demo-blocking |

## 7. Provenance Requirements

Every F06 Land Fact / Factor result must preserve:

- `geometry_id` / `geometry_reference`
- `geometry_hash`
- `source_crs` and `working_crs`
- `algorithm_version` (derivation spec version)
- `area_m2`, `perimeter_m`, `compactness`, `polygon_part_count` as applicable
- `geometry_validity`
- `geometry_coverage_status`
- `derived_at`
- `limitations`

## 8. Prohibited Interpretations

- Acreage thresholds for ADVANCE / HOLD / REJECT
- Compactness or perimeter thresholds for suitability
- Inferring fencing cost, labor, or profitability from perimeter
- Inferring carrying capacity from area
- Inferring operational success from compactness
- Cow-Calf vs Sheep ranking from any F06 metric
- Treating invalid or multi-part geometry as land failure
- Using F06 as a substitute for F07 road/physical access

## 9. Allowed Signals Only

```text
CONTEXT_DEPENDENT
NEEDS_VERIFICATION
UNKNOWN
ranking_effect: NONE
```

## 10. Open Questions

1. Geodesic area/perimeter QA is deferred until after the first deterministic implementation; it is not required for v0.1.
2. Should holes be included in perimeter in a later revision, and if so under what livestock-operations rationale?
3. Is international acre vs U.S. survey acre the display convention when acres are shown (raw m² remains canonical)?
4. For MultiPolygon parts that touch at a point/edge, is topological “connected component” counting needed later, or is geometric part count sufficient for demo?
5. Invalid geometry is not automatically repaired in v0.1; it remains `NEEDS_VERIFICATION`.

## 11. Implementation Readiness Recommendation

**F06 is APPROVED FOR DETERMINISTIC IMPLEMENTATION** of a narrow v0.1 slice:

Include: area, perimeter, polygon_part_count, compactness, geometry_validity, geometry_coverage_status.  
Defer: disconnected_part_count, perimeter_to_area_ratio, boundary_complexity, narrow_section_context.

Historical note: this audit originally said not to start F07 before F06 freeze.  
F06 is now `FROZEN_V0_1`; F07 is `AUTHORIZED_FOR_FIRST_STAGE_AUDIT` only.  
Do **not** deepen F02 coverage before the demo.  
Do **not** add thresholds or species ranking in F06.

Human review of this audit, derivation spec, rules, and golden-test contract passed on 2026-08-08. Implementation code may begin without changing the frozen formulas or governance. Automatic geometry repair is prohibited in v0.1; invalid geometry follows the `INVALID_UNUSABLE` / `NEEDS_VERIFICATION` path.
