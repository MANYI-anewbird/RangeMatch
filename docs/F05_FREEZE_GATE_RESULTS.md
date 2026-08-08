# F05 Freeze Gate Results — Climate and Drought Exposure

> Status: `PASSED — F05 FROZEN`  
> Date: 2026-08-08  
> Gate: `docs/FACTOR_FREEZE_GATE.yaml`  
> Full test suite: `63 passed`

## Frozen state

```yaml
F05_CLIMATE_DROUGHT_EXPOSURE:
  canonical_data_path: NOAA_NCEI_DIRECT_NORMALS_NETCDF
  canonical_variable: annprcp_norm
  cper_value_mm_per_year: 345.74
  signal: CONTEXT_DEPENDENT
  ranking_effect: NONE
  numeric_rules: NOT_APPROVED
  engine_integrated: true
  golden_tests_complete: true
  full_test_suite: 63_passed
  freeze_status: FROZEN
```

## Checklist against `FACTOR_FREEZE_GATE.yaml`

| Gate item | Evidence | Result |
|---|---|---|
| `authoritative_relationship_reviewed` | `COW_F05_001` / `SHEEP_F05_001` in `SPECIES_REQUIREMENTS_REGISTRY.md`; evidence registry + SRC_F05_004/007/008 | PASS |
| `atomic_variables_defined` | `VAR_F05_*` in `UNIFIED_LAND_VARIABLE_REGISTRY.yaml` | PASS |
| `primary_data_path_live_tested` | NOAA/NCEI Direct Normals NetCDF on CPER; `docs/F05_LIVE_DATA_GATE_RESULTS_CPER.md` | PASS |
| `applicability_and_coverage_behavior_defined` | Rules + derivation validate period/units/coverage/provenance; single-cell CPER coverage recorded | PASS |
| `missing_data_behavior_defined` | `MISSING→UNKNOWN`; incomplete→`NEEDS_VERIFICATION`; point-only→`NEEDS_VERIFICATION` | PASS |
| `prohibited_interpretations_recorded` | Evidence registry, rules YAML, Factor limitations | PASS |
| `deterministic_behavior_tested` | `tests/test_f05_climate.py` + full suite 63 passed | PASS |
| `numeric_thresholds.required` | `false`; none approved | PASS |

### Required evidence of completion

| Requirement | Location | Result |
|---|---|---|
| Reviewed requirement records | `docs/SPECIES_REQUIREMENTS_REGISTRY.md` | PASS |
| Variable IDs in registry | `docs/UNIFIED_LAND_VARIABLE_REGISTRY.yaml` | PASS |
| Data-source / Mireye audit | `docs/F05_DATA_SOURCE_AND_MIREYE_AUDIT.yaml`, `docs/SOURCE_REGISTRY.md` | PASS |
| Golden / executable missing/unknown/deterministic tests | `tests/test_f05_climate.py` | PASS |
| Prohibited interpretations listed | rules + evidence registry + demo Factor limitations | PASS |

## Demo closure inspection

Inspected: `test-data/land-profiles/land_profile_cper_001_demo_closure.{html,json}`

| Surface | F05 finding | Result |
|---|---|---|
| Signal | `CONTEXT_DEPENDENT` — “Context only — not a positive suitability score” | PASS |
| Limitations | Explicitly states precip is a Land Fact not a suitability score; no thresholds; Flood out of scope | PASS |
| Unknowns | Drought history / seasonality / heat threshold not frozen; context ≠ failure | PASS |
| Diligence | Retain NOAA normals + treat USDM as current-condition only | PASS |
| Source Trace | Derivation spec, NOAA fixture, Mireye fixture, NOAA hash | PASS |

### HOLD interpretation

HTML states: **“HOLD does not mean the land is unsuitable.”**  
Cow-Calf and Sheep both remain `HOLD` for incomplete shared evidence, not climate rejection. PASS.

### `345.74 mm` interpretation

- Present only as a structured MatchResult / Land Fact field (`canonical_precip_mm`).
- Not rendered in the Factor Evidence table as “low precipitation,” arid, negative, or carrying-capacity language.
- Explanation layer does not convert the value into a suitability judgment.
- Limitations/unknowns explicitly forbid suitability / carrying-capacity conclusions. PASS.

## Geometry replacement

`replace_geometry` invalidates every Factor under `factors`, including F05:

- Removes canonical precip block
- Sets `input_quality_state: MISSING` + `EVIDENCE_INVALIDATED`
- Post-replace evaluation → `UNKNOWN` / `F05_EXPL_MISSING`

Executable coverage: `tests/test_geometry_replace.py` (all factors) plus explicit F05 assertion.

## Stop rule

F05 research for v0.1 stops here. Further climate thresholds, drought-history methods, seasonality indices, or Flood work require a **new reviewed version / separate Factor**, not silent expansion of this freeze.

**Flood is not the automatic next Factor** merely because it is adjacent in Tier 2 examples.
