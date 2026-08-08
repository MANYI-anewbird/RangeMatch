# F02 RAP Coverage, Masking, and Improved-Pasture Audit

> Status: `REVIEW COMPLETE — RUNTIME COVERAGE GAP IDENTIFIED`  
> Product: USDA-ARS Rangeland Analysis Platform v3  
> Test geometry: `ENGINEERING_TEST_GEOMETRY_CPER_001`  
> Review date: 2026-08-07

## 1. Decision

RAP v3 is approved as the primary modeled cover and production source for parcels whose rangeland applicability has been established. It is not approved as a universal U.S. pasture source.

An improved pasture, cultivated forage field, hay field, or mixed agricultural parcel must not inherit rangeland interpretation merely because RAP returns a numeric value. It receives `OUTSIDE_DOCUMENTED_PRODUCT_SCOPE` unless reviewed land-use evidence establishes that the analyzed area is within RAP's intended rangeland domain.

This is an applicability decision, not a claim that RAP necessarily returns no pixels outside rangeland. Availability of a modeled value and scientific fitness for the decision are separate gates.

## 2. Official Product Scope

The current RAP site describes the platform as vegetation data for U.S. rangelands and says its maps should be used with local knowledge and site-specific information. The production documentation describes modeled new aboveground rangeland production, not standing biomass. The RAP interface states that its mask removes pixels that are not rangeland.

The downloadable general-audience FGDC metadata currently linked by RAP is older than the v3 API. It describes western-U.S. rangeland models and must not be used to claim nationwide v3 scientific validation. It remains useful for model lineage and limitations, while current v3 geography/version claims require current v3 documentation.

Official references:

- https://rangelands.app/support/46-new-to-rap-start-here-landing
- https://rangelands.app/support/49-rangeland-production
- https://rangelands.app/support/71-api-documentation
- https://rangelands.app/rap/
- https://rangelands.app/support/54-using-rap-in-rangeland-decision-making
- https://rangelands.app/support/59-rap-metadata

## 3. Mask Contract

The documented API `mask` option excludes cropland, development, and water. The API returns the requested mask state and AOI means, but it does not return:

- requested AOI area;
- eligible unmasked area;
- masked area;
- no-data area;
- valid pixel count;
- valid coverage fraction;
- land-cover classes responsible for exclusion.

Therefore:

```text
HTTP 200 + numeric AOI mean + mask=true
!=
quantified parcel coverage
```

## 4. CPER Masked/Unmasked Test

Both masked and unmasked 2025 polygon requests returned HTTP 200. Their values differed, confirming that the mask affects the aggregate, but the responses did not reveal how much area was removed.

```yaml
coverV3:
  masked:
    AFG: 12.567423553079283
    PFG: 32.98657702821575
    BGR: 26.41437204009802
  unmasked:
    AFG: 12.576553221450688
    PFG: 32.97255565824872
    BGR: 26.413487031262818
productionV3_lbs_per_acre:
  masked_HER: 937.6780475452124
  unmasked_HER: 937.6344203261126
```

The magnitude of these differences must not be converted into masked-area fraction.

## 5. Pixel-Level Completion Path

RAP publishes the following Google Earth Engine assets:

```text
projects/rap-data-365417/assets/vegetation-cover-v3
projects/rap-data-365417/assets/npp-partitioned-v3
projects/rap-data-365417/assets/npp-partitioned-16day-v3
```

RAP states that a Google Earth Engine account is required to export or process these raster assets. No authenticated Earth Engine runtime is configured in the current RangeMatch environment. Pixel-level area accounting is therefore not runtime verified.

The completion implementation must:

1. use the same geometry, years, v3 assets, and mask definition as the aggregate request;
2. calculate requested, eligible, masked, no-data, and valid pixel areas in an equal-area/projected computation;
3. record asset IDs, image IDs, projection, nominal scale, reducer settings, geometry hash, request timestamp, and result hash;
4. compare independently aggregated values with the public API result under an explicit tolerance;
5. preserve `COVERAGE_UNQUANTIFIED` until those outputs exist.

## 6. Runtime Classification

| Situation | F02 quality state |
|---|---|
| RAP series returned; pixel areas absent | `COVERAGE_UNQUANTIFIED` |
| Version-matched pixel accounting complete | `COMPLETE_RANGELAND_COVERAGE` |
| Some reviewed eligible area lacks data | `PARTIAL_RANGELAND_COVERAGE` |
| Improved pasture/cultivated forage/mixed agriculture without established rangeland applicability | `OUTSIDE_DOCUMENTED_PRODUCT_SCOPE` |
| No valid response | `MISSING` |

No current finding authorizes a directional Cow-Calf or Sheep signal.

