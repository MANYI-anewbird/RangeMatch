# F04 Live Data Gate — CPER Engineering Geometry

> Status: `PASSED WITH POINT-VS-PARCEL LIMITATION`  
> Geometry: `ENGINEERING_TEST_GEOMETRY_CPER_001`  
> Date: 2026-08-07

## Result

The official USDA-NRCS Soil Data Access tabular and WFS services returned parcel-intersecting SSURGO data for the complete CPER engineering geometry.

| Check | Result |
|---|---|
| Requested parcel area | 1,404,078.70 m² |
| SDA-covered area | 1,404,078.70 m² within numeric tolerance |
| Coverage status | `COMPLETE_WITH_NUMERIC_TOLERANCE` |
| Intersecting map units | 5 |
| Soil components | 16 |
| Components with ecological-site linkage | 12 |
| Distinct ecological-site IDs | 6 |
| Horizon records | 56 |
| Component restriction records | 16 |
| Monthly wetness records | 192 |
| Public EDIT descriptions accessible | 3 of 6 confirmed; 3 TimeoutError → runtime `UNKNOWN` |

### Parcel map-unit distribution

| MUKEY | Parcel share |
|---|---:|
| `95151` | 42.21% |
| `95134` | 26.42% |
| `95132` | 15.52% |
| `95111` | 9.54% |
| `95143` | 6.31% |

The shares describe mapped polygon intersections. They do not remove within-map-unit component uncertainty.

## Mireye point result

Mireye returned all seven requested centroid fields without partial failure:

```yaml
soil_map_unit_name: Renohill-Shingle complex, 3 to 9 percent slopes
soil_drainage_class: Well drained
soil_ponding_frequency_class: None
soil_hydrologic_group: D
soil_restrictive_layer_depth_cm: 74
soil_restrictive_layer_kind: Paralithic bedrock
soil_available_water_capacity: 0.14 cm/cm
```

These are point/dominant-component context. The centroid lies in MUKEY `95151`, which covers approximately 42.21% of the parcel. Therefore the Mireye result must not be presented as the parcel-wide soil condition.

## Ecological-site linkage

SDA linked 12 of 16 components to six ecological-site IDs:

```text
R067BY002CO  Loamy Plains
R067BY024CO  Sandy Plains
R067BY033CO  Salt Flat
R067BY042CO  Clayey Plains
R067BY045CO  Shaly Plains
R067BY063CO  Gravel Breaks
```

This proves component-to-site linkage availability. It does not prove that every linked description is publicly available, that the reference community is currently present, or that a named site favors either operation.

For this CPER test, three linked descriptions returned HTTP 200 with response hashes. Three others recorded `TimeoutError` during fetch. Runtime treats timeout as `UNKNOWN`, not `NOT_ACCESSIBLE`. Public accessibility still does not convert descriptive content into a current parcel observation.

## Missing-data observations

- 2 of 56 horizon records have null AWC, EC, and pH representative values.
- 13 of 16 component records have no restrictive-layer record.
- 48 of 192 monthly records have null ponding and flooding classes.

These nulls remain `UNKNOWN`. They are not interpreted as zero, `None`, unrestricted soil, or absence of wetness.

## Frozen interpretation

```text
Mireye point soil fields
→ fast display and QA context

Official SDA parcel polygons + components + horizons
→ primary F04 Land Facts and coverage path

Ecological-site linkage
→ interpretive reference only
```

No directional Cow-Calf or Sheep signal is approved from this live gate.
