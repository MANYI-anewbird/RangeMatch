# RangeMatch Live Data Test Site - CPER

> Test site ID: `CPER_ENGINEERING_TEST_SITE`
> Status: `APPROVED FOR ENGINEERING VALIDATION`
> Operations under review: Cow-Calf Operation and Sheep Grazing
> Factors under test: F01 Topography and F02 Herbaceous Resource
> Last updated: 2026-08-07

## 1. Test-Site Role

The USDA-ARS Central Plains Experimental Range (CPER), northeast of Nunn, Colorado, is the first RangeMatch live-data engineering site.

It is not:

- a purchasable parcel;
- a private-user property;
- an official cadastral or pasture-boundary test unless a separately authoritative boundary is obtained;
- ground truth for optimal land use;
- suitability-label training data.

It is used to verify whether RangeMatch can retrieve, derive, aggregate, version, and reproduce F01 and F02 Land Facts on a real U.S. grazing research landscape.

## 2. Authoritative Context

USDA-ARS/LTAR states that CPER is owned and managed by USDA-ARS, covers approximately 62.8 km2 or 15,500 acres, is located northeast of Nunn, Colorado, and has a long history of livestock, vegetation, forage-production, climate, soil, and remote-sensing research.

The site is a shortgrass-steppe system dominated by warm-season shortgrasses. These descriptive facts are independent QA context only.

Sources:

- https://ltar.ars.usda.gov/sites/cper/
- https://www.ars.usda.gov/plains-area/fort-collins-co/center-for-agricultural-resources-research/rangeland-resources-systems-research/docs/rrsr/central-plains-experimental-research-location/

## 3. Public Coverage Extent

The public metadata coverage extent is stored in:

```text
test-data/cper_public_coverage_extent.geojson
```

The coordinates are independently reproduced in USDA/Data.gov metadata for multiple SGS-LTER/CPER datasets. The metadata describes the spatial extent as CPER coverage, but RangeMatch does not promote this bounding rectangle into a cadastral or pasture boundary.

Source:

- https://catalog.data.gov/dataset/sgs-lter-standard-met-data-cr21x-station-12-hourly-meteorological-data-on-the-central-plai

## 4. Small Engineering Geometry

The first test geometry is:

```text
test-data/engineering_test_geometry_cper_001.geojson
```

Properties:

```yaml
geometry_id: ENGINEERING_TEST_GEOMETRY_CPER_001
geometry_type: synthetic rectangle fully inside public CPER coverage extent
approximate_area_ha: 140.658
official_pasture_boundary: false
purchasable_parcel: false
suitability_ground_truth: false
```

The geometry was selected to approximate a realistic pasture-scale engineering test. Its shape and area must not be attributed to USDA as an official CPER pasture.

## 5. Independent QA Benchmarks

The following USDA site descriptions may be used only after RangeMatch produces its results:

```text
Elevation: 5,250-5,550 ft
Historical annual precipitation: 12.8 inches
Growing season: 133 days
Rangeland type: Short Grass Prairie
```

They must not be supplied to the F01/F02 runtime as input values. They are broad site-level descriptions, not expected exact statistics for the synthetic subpolygon.

## 6. Validation Order

### Test A - Small synthetic geometry

1. Validate GeoJSON and calculate an authoritative geodesic/projected area.
2. Run Mireye field/catalog and parcel-contract checks.
3. Run F01 USGS 3DEP retrieval and derivation.
4. Run F02 RAP v3 cover, annual production, and 16-day production requests.
5. Record coverage, masking, units, schema, source versions, hashes, and runtime.
6. Repeat each request and compare structured results.
7. Compare outputs with independent USDA context only after computation.

### Test B - Public coverage extent

After Test A passes, run the larger coverage extent to test multi-tile retrieval, masked/no-data behavior, performance, and aggregation scalability.

## 7. Pass/Fail Boundary

The test validates the data pipeline, not agricultural suitability. A successful result means RangeMatch can obtain and reproduce the reviewed Land Facts with explicit uncertainty and missing-data behavior. It does not mean CPER is an ideal Cow-Calf or Sheep property.

## 8. Mireye Test A Result

Tested at the synthetic geometry centroid (`40.825`, `-104.7625`) on 2026-08-07:

```yaml
mireye_api_version: 0.14.0
catalog: HTTP_200
catalog_field_count: 304
point_fetch: HTTP_200
partial_failures: []
f01_fields:
  elevation: 1646.923095703125 meters
  slope_degrees: 0.9686843752861023 degrees
  aspect_degrees: 301.71868896484375 degrees
  aspect_cardinal: NW
f02_context_fields:
  lcms_class: Grass/Forb/Herb & Shrubs Mix
  cdl_class: Grass/Pasture
```

Interpretation:

- Mireye connectivity, field discovery, and point lookup passed.
- The F01 values are point-level QA/display observations; they do not satisfy parcel-distribution requirements.
- No numeric Mireye herbaceous cover, herbaceous production, or RAP field was found in catalog v0.14.0.
- `lcms_class` and `cdl_class` are categorical point context only. They do not establish forage quantity, quality, availability, palatability, carrying capacity, or parcel composition.
- F01 still requires parcel-wide USGS 3DEP derivation. F02 still requires the independent RAP live contract test.

Reproducible, credential-free response fixtures are stored under `mireye/fixtures/`. No API key is present in them.
