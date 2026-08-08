# F05 Live Data Gate — CPER Engineering Geometry

> Status: `LIVE_VERIFIED`  
> Geometry: `ENGINEERING_TEST_GEOMETRY_CPER_001`  
> Date: 2026-08-07  
> Suitability rules: `NOT WRITTEN`

## Acceptance block

```yaml
data_path_status: LIVE_VERIFIED
signal_status: NOT_YET_APPROVED
ranking_effect: NONE
```

This gate verifies data capability only. It does not approve numeric thresholds, Cow-Calf / Sheep directional signals, or ranking effects.

## Scope completed

```text
CPER geometry
├── NOAA NCEI parcel precipitation
│   ├── value + unit
│   ├── observation/normals period
│   ├── spatial resolution
│   ├── parcel coverage
│   └── source/version/provenance
│
└── Mireye point QA
    ├── drought_category
    ├── mean annual temperature
    └── annual days above 32°C
```

Out of scope for this gate: drought-history summary method freeze, PRISM primary path, Flood Factor, F02/F03 signal mutation, suitability rules.

## Locked precipitation architecture

```yaml
F05 precipitation primary path:
  source: NOAA/NCEI Direct Climate Normals NetCDF
  variable: annprcp_norm
  cper_value: 345.74
  unit: mm/year
  role: CANONICAL_LAND_FACT

ACIS:
  grids_tested: [1, 21]
  capability: CPER precipitation time series available
  role: SECONDARY_QA_OR_FALLBACK
  canonical_runtime_source: false
```

Role separation:

- NOAA/NCEI direct normals NetCDF → formal long-term mean annual precipitation Land Fact
- ACIS → proves a precipitation time-series path is available for QA, supplemental analysis, or future interannual variability; not the canonical runtime source
- Mireye → point QA and fast context only
- `345.74 mm` → measured Land Fact only; no Cow-Calf / Sheep suitability signal

## NOAA NCEI precipitation result

Primary path: NOAA/NCEI 1991–2020 gridded precipitation normals (`annprcp_norm`), downloaded directly from NCEI HTTPS. PRISM remains alternate only. ACIS grids `1` and `21` returned usable CPER series and are retained as secondary QA/fallback, not canonical.

| Field | Value |
|---|---|
| Mean annual precipitation | **345.74 mm** (13.612 in) |
| Unit | millimeter |
| Normals period | 1991–2020 |
| Spatial resolution | 1/24° (~4 km) nClimGrid-compatible CONUS grid |
| Parcel coverage | Complete for the CPER engineering rectangle; **1 intersecting cell** covers the ~0.015° × 0.010° test polygon |
| Spatial support | `PARCEL_BBOX_INTERSECTING_GRID_CELLS` |
| Product file | `prcp-1991_2020-monthly-normals-v1.0.nc` |
| Access path | `NOAA_NCEI_DIRECT_HTTPS_NETCDF` |
| Source URL | https://www.ncei.noaa.gov/data/oceans/archive/arc0196/0245564/1.1/data/0-data/prcp-1991_2020-monthly-normals-v1.0.nc |
| Product page | https://www.ncei.noaa.gov/products/land-based-station/us-climate-normals |
| nClimGrid reference | https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc:C00332 |
| Fixture | `test-data/live-results/cper/cper_noaa_ncei_annprcp_normals_1991_2020_2026-08-07.json` |

The engineering geometry is smaller than one climate cell. The live value is therefore a single-cell land-surface precipitation normal assigned to the parcel bbox, not a multi-cell area-weighted mosaic. That is a valid coverage result for this geometry; it is not a claim that sub-cell precipitation variability is resolved.

## Mireye point QA

Centroid sample only (`lat=40.825`, `lng=-104.7625`). Point QA must not be presented as parcel-aggregate climate.

| Field | Value | Source | Status |
|---|---|---|---|
| `drought_category` | `D3` | `USDM_CURRENT` (valid through 2026-08-03) | ok |
| `mean_annual_dry_bulb_temperature_degc` | `9.12 degC` | `NOAA_NCEI_NORMALS_GRIDDED` 1991–2020 | ok |
| `days_above_32c_annual_count` | `32 days` | `NOAA_NCEI_NCLIMGRID_DAILY` | ok |

Fixture: `test-data/live-results/cper/cper_mireye_f05_centroid_2026-08-07.json`

`precipitable_water_annual_mean_cm` remains prohibited as precipitation and was not used for the precip Land Fact.

## Boundary checks confirmed

- Current USDM category ≠ drought history summary
- Land-surface precipitation ≠ atmospheric precipitable water
- F05 does not mutate F02 or F03 signals
- F04 soil-survey wetness remains independent of any future Flood Factor
- No numeric thresholds or species ranking approved

## Frozen interpretation

```text
NOAA NCEI gridded annual precipitation normals
→ primary parcel precipitation Land Fact path for F05

Mireye drought / temperature / heat-day fields
→ point QA and display context only

Current USDM class
→ current-condition context only; not drought climatology
```

## Next gate

Architecture, narrow relationships, and v0.1 data-quality/context rules are now documented. Remaining work:

1. Wire golden tests and engine evaluation for F05 data-quality states.
2. Integrate into the vertical slice without directional suitability thresholds.
3. Keep Flood/Wetness as a later separate Factor.
