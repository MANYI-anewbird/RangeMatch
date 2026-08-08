# F01–F05 Five-Parcel Aggregate Review

> Status: `COMPLETE — CONCLUSION LOCKED`  
> Date: 2026-08-08  
> Runner: `scripts/run_cross_parcel_validation.py`  
> Registry: `test-data/cross-parcel-validation/parcel_registry.yaml`  
> Locked conclusion: `docs/CROSS_PARCEL_VALIDATION_CONCLUSION.yaml`  
> Next phase: `docs/F02_F03_EVIDENCE_DEPTH_UPGRADE_PLAN.md`

## 0. Locked formal conclusion

```yaml
cross_parcel_validation: PASSED
rule_behavior_across_environments: STABLE
species_differentiation: NOT_YET_ESTABLISHED
primary_bottlenecks:
  - F02_COVERAGE_AND_SCOPE
  - F03_VERIFIED_WATER
f06_selection: DEFERRED
```

Interpretation: rules stayed stable across environments; the bottleneck is evidence depth of F02/F03, not a missing F06. Species differentiation is not yet established and must not be invented with unreviewed ranking rules.

## 1. Execution lock confirmation

| Lock | Status |
|---|---|
| Same code version (`engine_version` 0.1.0) | Held |
| Same F01–F05 rules | Held |
| Same data-source priority (NOAA canonical for F05; ACIS unused as Land Fact) | Held |
| Same missing/timeout semantics | Held |
| No parcel-specific rule adjustment | Held |
| No geometry reselection after freeze | Held |
| `runtime_rule_changed: false` on all new parcels | Held |

## 2. Parcel outcomes (observation only — not suitability)

| Parcel | Slot | Cow / Sheep | F05 NOAA mm | F01 slope med / p90 ° | F02 applicability | F02 PFG % | F03 mapped / verified |
|---|---|---|---|---|---|---|---|
| `XPV_CPER_001` | ARID_UNCERTAIN_WATER | HOLD / HOLD | 345.74 | 2.40 / 5.26 | IN_SCOPE | 32.99 | 9 / 0 |
| `XPV_KONZA_001` | HUMID_STRONG_HERB | HOLD / HOLD | 879.57 | 6.92 / 13.01 | IN_SCOPE | 78.11 | 34 / 0 |
| `XPV_REYNOLDS_001` | RUGGED_SHEEP_RELEVANT | HOLD / HOLD | 462.55 | 11.13 / 24.10 | IN_SCOPE | 34.87 | 8 / 0 |
| `XPV_ORDWAY_001` | WATER_CANDIDATE_RICH | HOLD / HOLD | 1342.19 | 1.29 / 3.78 | UNKNOWN | 15.39 | 24 / 0 |
| `XPV_KBS_MCSE_001` | RAP_SCOPE_BOUNDARY | HOLD / HOLD | 939.33 | 1.36 / 5.65 | OUTSIDE_SCOPE | 7.91 | 5 / 0 |

CPER contrast is observational only. Higher precip / PFG / slope / candidate counts are **not** suitability rankings.

## 3. Factor-signal pattern

Across all five parcels, Cow-Calf and Sheep signals were **IDENTICAL**. Diagnosis remains `MISSING_SPECIES_DIFFERENTIAL_RULE`.

Shared signal pattern on every parcel:

| Factor | Typical signal | Driver |
|---|---|---|
| F01 | `CONTEXT_DEPENDENT` | Parcel topography complete; no directional terrain score |
| F02 | `NEEDS_VERIFICATION` | Coverage unquantified (Konza/Reynolds/CPER) **or** scope gate (Ordway UNKNOWN / KBS OUTSIDE) |
| F03 | `NEEDS_VERIFICATION` | Mapped candidates only; verified livestock systems = 0 everywhere |
| F04 | `CONTEXT_DEPENDENT` | SDA parcel path complete; Mireye point QA degraded (see §5) |
| F05 | `CONTEXT_DEPENDENT` | NOAA/NCEI `annprcp_norm` complete; Mireye drought/temp QA degraded |

## 4. Slot stresses that worked without rule changes

1. **Humid strong herb (Konza):** NOAA precip ~880 mm and PFG ~78% contrast vs CPER; F02 still `NEEDS_VERIFICATION` via coverage, not ADVANCE.
2. **Rugged sheep-relevant (Reynolds):** slope p90 ~24° vs CPER ~5°; Cow/Sheep remain peer-identical — ruggedness did **not** invent Sheep ranking.
3. **Water-candidate-rich (Ordway):** 24 mapped candidates, 0 verified; F03 still candidates-not-verified. Candidate richness ≠ adequacy.
4. **RAP scope boundary (KBS):** F02 applicability `OUTSIDE_DOCUMENTED_PRODUCT_SCOPE`, explanation `F02_EXPL_SCOPE`. RAP values retained as facts under outside-scope discipline, not forage suitability.

## 5. Data-path degradation (not a rule defect)

```yaml
potential_rule_issue: null
investigation_required: true
runtime_rule_changed: false
data_path_issue: >
  Mireye HTTPS to api.mireye.com failed on this host with
  SSL: WRONG_VERSION_NUMBER for F04/F05 point QA on all four new parcels.
  SDA (F04 primary) and NOAA/NCEI NetCDF (F05 canonical) succeeded.
  Degradation recorded as PARTIAL/DEGRADED collection_status, not land unsuitability.
```

## 6. Post-validation decision gate

| Question | Finding |
|---|---|
| Main bottleneck existing data quality? | **Yes** — F02 coverage unquantified; F03 zero verified systems; Mireye QA path currently broken in this environment |
| Clear new decision gap requiring F06? | **No** — flood/FEMA still not forced by results |
| Rules abnormal across environments? | **No** — same HOLD / identical Cow-Sheep / ranking_effect NONE everywhere; scope and coverage gates fired correctly |

**Recommended next action (locked):** execute **F02/F03 Evidence Depth and Verification Upgrade** per `docs/F02_F03_EVIDENCE_DEPTH_UPGRADE_PLAN.md` — F03 verified water first, then F02 coverage/scope, then Mireye SSL as a separate adapter incident. Keep F06 deferred. After upgrades, rerun the same five frozen parcels for before/after comparison.

## 7. Artifacts

Per new parcel under `test-data/cross-parcel-validation/<parcel_id>/`:

- `land_profile.json`
- `match_result.json`
- `validation_result.yaml`
- `run_summary.json`
- `live-results/` (F01–F05 fixtures)
