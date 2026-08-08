# F05 Evidence Registry — Climate and Drought Exposure

> Review status: `V0.1 FACTOR FROZEN`  
> Factor decision: `IN TIER 2 SHARED CORE — DATA-QUALITY / CONTEXT RULES ONLY`  
> Rule status: `NO UNIVERSAL PRECIPITATION, USDM, OR HEAT THRESHOLD APPROVED`  
> Operations: Cow-Calf Operation and Sheep Grazing  
> Last reviewed: 2026-08-08  
> Freeze record: `docs/F05_FREEZE_GATE_RESULTS.md`  
> Live gate: `docs/F05_LIVE_DATA_GATE_RESULTS_CPER.md`

## 1. Locked Data Architecture

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

Mireye:
  role: POINT_QA_AND_FAST_CONTEXT
  may_supply_canonical_parcel_precip: false
```

```text
NOAA/NCEI direct normals NetCDF  !=  ACIS time-series QA path
land-surface annprcp_norm        !=  atmospheric precipitable water
current USDM week                !=  drought history / frequency
345.74 mm CPER fact              !=  Cow-Calf or Sheep suitability signal
F05 climate context              !=  F02 forage score or F03 water verdict
F04 soil-survey wetness          !=  F05 drought exposure
```

## 2. Narrow Evidence Decisions

### Cow-Calf reviewed relationship

> Precipitation regime and drought exposure can affect forage reliability, water demand, livestock performance risk, and the need for drought contingency planning for cow-calf operations. A mean annual precipitation value or a current USDM class alone does not establish suitability, carrying capacity, forage failure, or livestock-water failure.

Status: `ACCEPTED_RELATIONSHIP — VERIFIED_FOR_V0_1`

Not approved:

- a universal mean-annual-precipitation cutoff;
- a national USDM-class penalty or `REJECT` rule;
- an automatic forage or carrying-capacity score from climate fields;
- treating one current drought class as multi-year drought climatology;
- mutating F02 or F03 ranking effects from F05 values alone;
- a Cow-Calf versus Sheep ranking from climate fields alone.

### Sheep reviewed relationship

> Precipitation regime and drought exposure can affect forage reliability, water demand, and drought-management diligence for sheep grazing. Breed, management, diet moisture, and local forage composition can change sensitivity. Climate fields alone do not establish suitability or a universal numeric advantage or disadvantage relative to cattle.

Status: `ACCEPTED_RELATIONSHIP — VERIFIED_FOR_V0_1`

Not approved:

- a universal sheep precipitation or heat-day threshold;
- automatic Sheep advantage or disadvantage versus Cow-Calf from climate;
- treating forage moisture or snow as proof that drinking water is unnecessary;
- equating current USDM class with long-term drought exposure;
- carrying-capacity or profitability conclusions from climate normals.

Deferred pending additional source audit:

- quantitative heat-stress biological thresholds by species and class;
- formal drought-history frequency method;
- precipitation-seasonality indices as ranking inputs.

## 3. Source-by-Source Audit

### `SRC_F05_001` — NOAA/NCEI Direct Climate Normals NetCDF

- Role: Canonical Land Fact path for mean annual precipitation (`annprcp_norm`).
- Supported claim: Declared-period land-surface precipitation normals with units and spatial support.
- Does not support: Suitability, carrying capacity, or species ranking.
- Evidence strength: `STRONG FOR DATA FACT; NONE FOR BIOLOGICAL THRESHOLD`

### `SRC_F05_003` — U.S. Drought Monitor

- Role: Current drought-category context.
- Supported claim: Controlled D0–D4 current-week classes.
- Does not support: Drought climatology, forage failure, or water-system failure from one week.
- Evidence strength: `STRONG FOR CURRENT CONDITION LABEL ONLY`

### `SRC_F05_004` — NRCS Prescribed Grazing (Code 528)

- Supported claim: Grazing management must balance forage supply and animal demand and prepare contingencies for drought and other episodic disturbances.
- Does not support: National numeric climate cutoffs for RangeMatch decisions.
- Evidence strength: `STRONG FOR QUALITATIVE MANAGEMENT RELATIONSHIP`

### `SRC_F05_007` — NDMC Managing Drought Risk on the Ranch

- Supported claim: Drought can reduce livestock performance and forage quantity/quality; precipitation, forage, and water should be monitored and balanced on critical decision dates.
- Does not support: Fixed precipitation thresholds or automatic USDM-to-failure mapping.
- Evidence strength: `STRONG FOR QUALITATIVE DROUGHT-PLANNING RELATIONSHIP`

### `SRC_F05_008` — NRCS Combating Drought on Pasture and Forage

- Supported claim: Stocking rate and pasture support change with growing conditions during drought; management must adjust to protect forage and soil.
- Does not support: Computing carrying capacity from mean annual precipitation alone.
- Evidence strength: `MODERATE_TO_STRONG FOR QUALITATIVE RELATIONSHIP`

### `SRC_F05_005` / `SRC_F05_006` — Mireye and ACIS

- Mireye: point QA only; precipitable water prohibited as rainfall.
- ACIS: secondary QA / time-series fallback; not canonical mean-annual precip.

## 4. Preliminary Factor Decision

| Criterion | Decision |
|---|---|
| Scientifically relevant to both Profiles | Yes |
| Shared measurable Land Facts | Yes (`annprcp_norm`, current USDM, temperature/heat context) |
| Canonical precip path locked | Yes — NOAA/NCEI direct normals NetCDF |
| Numeric suitability rule supported | No |
| Cross-species ranking from climate | No |
| May silently alter F02/F03 | No |
| v0.1 rule class | Data-quality and context only → `CONTEXT_DEPENDENT` / `NEEDS_VERIFICATION` / `UNKNOWN` |

## 5. Next Implementation Gate

1. Keep `docs/F05_CLIMATE_DROUGHT_DETERMINISTIC_RULES.yaml` as the only v0.1 evaluation logic.
2. Add golden tests for data-quality states; no threshold tests.
3. Integrate into the vertical slice only after those tests pass.
4. Leave Flood/Wetness as a later Factor.
