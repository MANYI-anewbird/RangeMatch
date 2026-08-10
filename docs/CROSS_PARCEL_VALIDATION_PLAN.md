# F01–F05 Cross-Parcel and Cross-Environment Validation Plan

> **Historical validation plan.** This plan predates the frozen F01–F08 product scope. Preserve its selection and anti-cherry-picking protocol as audit evidence; use `CURRENT_SYSTEM_BASELINE.md` for current product status.

> Status: `PASSED — CONCLUSION LOCKED; NEXT PHASE IS F02/F03 EVIDENCE DEPTH`  
> Registry: `test-data/cross-parcel-validation/parcel_registry.yaml`  
> Preflight: `test-data/cross-parcel-validation/slot_preflight_2026-08-08.yaml`  
> Aggregate: `docs/CROSS_PARCEL_FIVE_PARCEL_AGGREGATE_REVIEW.md`  
> Conclusion: `docs/CROSS_PARCEL_VALIDATION_CONCLUSION.yaml`  
> Next phase: `docs/F02_F03_EVIDENCE_DEPTH_UPGRADE_PLAN.md`  

> Date: 2026-08-08  
> Goal: Prove the frozen five-Factor loop works across environments before selecting F06  
> Related: `docs/FIVE_FACTOR_PORTFOLIO_REVIEW.md`, `docs/CROSS_PARCEL_SELECTION_CRITERIA.yaml`, `docs/CROSS_PARCEL_VALIDATION_RESULT_SCHEMA.yaml`

## 1. Locked objective

```text
F01–F05 Cross-Parcel and Cross-Environment Validation
```

This phase does **not** aim for `ADVANCE`. It aims to verify that the same reviewed rules remain deterministic, explainable, and scientifically bounded when the parcel and environment change.

F06 is **not selected**. Flood has **no default priority**.

## 2. What success means

Validation succeeds when, across 3–5 engineering test parcels:

1. The same F01–F05 rules produce deterministic, explainable MatchResults.
2. Place names / state names never enter suitability weight.
3. Applicability and coverage states change correctly with geography and product scope.
4. Source/API failure is recorded as data/verification failure, not land unsuitability.
5. Geometry, provenance, and hashes update correctly when the parcel changes.
6. Identical Cow-Calf and Sheep signals are attributed either to shared evidence boundaries or to missing species differential rules — never silently “fixed” by inventing ranking.

Post-validation decision gate:

```text
If the main bottleneck is existing data quality
→ deepen F02/F03

If a clear new decision gap appears
→ select F06

If rules behave abnormally across environments
→ repair existing Factors; do not expand
```

## 3. Standard run loop (every parcel)

```text
Geometry
→ F01–F05 data collection
→ applicability / coverage checks
→ Cow-Calf + Sheep evaluation
→ MatchResult comparison
→ Unknowns and diligence review
→ ValidationResult record (schema-compliant)
```

Minimum Factor expectations per parcel:

| Factor | Must collect / derive | Must assert |
|---|---|---|
| F01 | Parcel topography derivation or documented failure | Point ≠ parcel; provenance/hash |
| F02 | RAP or documented inapplicability/failure | Coverage quantified or explicitly `COVERAGE_UNQUANTIFIED` / outside scope |
| F03 | Candidate water inventory or documented failure | Candidates ≠ verified systems |
| F04 | SDA parcel path or documented failure | Point soil ≠ parcel; wetness ≠ FEMA flood |
| F05 | NOAA/NCEI canonical precip normals or documented failure | ACIS/Mireye cannot replace canonical precip; no precip threshold |

## 4. Engineering parcel set (target 3–5)

Use **engineering test geometries**, not purchasable ranch claims and not suitability ground truth. Selection criteria are frozen in `CROSS_PARCEL_SELECTION_CRITERIA.yaml`.

Required environment slots:

| Slot ID | Intent | Why it is in the set |
|---|---|---|
| `SLOT_HUMID_STRONG_HERB` | Humid / stronger herbaceous pasture or rangeland | Stress F02 resource contrast vs arid CPER-like cases |
| `SLOT_ARID_UNCERTAIN_WATER` | Arid grazing land with uncertain water | Stress F03 verification + F05 drought context |
| `SLOT_RUGGED_SHEEP_RELEVANT` | Rugged terrain with sheep-relevant topography | Stress F01 context and whether Cow/Sheep still stay peer |
| `SLOT_WATER_CANDIDATE_RICH` | Rich mapped water candidates, still unverified | Stress “candidates ≠ verified systems” |
| `SLOT_RAP_SCOPE_BOUNDARY` | RAP documented scope boundary or outside-scope case | Stress applicability / outside-product-scope behavior |

Baseline reference already available:

| Geometry | Role |
|---|---|
| `ENGINEERING_TEST_GEOMETRY_CPER_001` | Semi-arid plains baseline; full F01–F05 vertical slice complete |
| `ENGINEERING_TEST_GEOMETRY_CPER_002` | Geometry-replacement stress only; not a new environment slot |

CPER_001 may fill at most one slot (likely arid / uncertain-water adjacency). It must not fill all slots.

## 5. Validation dimensions

### 5.1 Determinism and explainability

- Same inputs → identical MatchResult hash/content.
- Explanation remains MatchResult-bound; no invented scores.

### 5.2 Place-name isolation

- State, county, site names appear only in lookup/provenance/display.
- No Factor evaluator may branch on place-name strings.

### 5.3 Applicability and coverage dynamics

- In-scope vs outside RAP / climate / soil product domains must change `applicability` / `coverage` / signals correctly.
- Adapter HTTP success alone must never become `COMPLETE` coverage.

### 5.4 Source-failure semantics

Allowed outcomes for data failure: `UNKNOWN`, `NEEDS_VERIFICATION`, or documented `NOT_ACCESSIBLE` where that Factor already defines it.

Prohibited: interpreting fetch timeout, empty response, or missing product coverage as “this land is bad for cattle/sheep.”

### 5.5 Geometry / provenance / hash integrity

- New geometry → new `geometry_hash`.
- Stale Factor evidence must invalidate (`EVIDENCE_INVALIDATED` / `MISSING`) until regenerated.
- Canonical precip / soil / topo provenance must cite the active geometry hash.

### 5.6 Cow–Sheep signal identity diagnosis

For each parcel record one of:

- `SHARED_EVIDENCE_BOUNDARY` — both Profiles correctly share the same incomplete evidence;
- `MISSING_SPECIES_DIFFERENTIAL_RULE` — prose differs but no approved ranking/differential rule exists;
- `UNEXPECTED_RUNTIME_DIVERGENCE` — Profiles diverge without an approved rule (**defect**);
- `APPROVED_DIFFERENTIAL_APPLIED` — only if a reviewed rule is later added (not expected in this phase).

## 6. Artifact layout

```text
test-data/cross-parcel-validation/
  parcel_registry.yaml
  <parcel_id>/
    geometry.geojson
    land_profile.json
    match_result.json
    validation_result.yaml
    notes.md                  # optional human notes; not runtime authority
    live-results/             # Factor fixtures for that parcel
```

Schema for each `validation_result.yaml`: `docs/CROSS_PARCEL_VALIDATION_RESULT_SCHEMA.yaml`.

Portfolio rollup after all parcels:

```text
docs/CROSS_PARCEL_VALIDATION_RESULTS.md
```

## 7. Execution order

1. Freeze this plan, selection criteria, and result schema (**this document set**).
2. Fill `parcel_registry.yaml` with 3–5 selected geometries and slot assignments.
3. Run the standard loop parcel-by-parcel; do not tune rules mid-flight to chase ADVANCE.
4. Write the portfolio rollup and apply the post-validation decision gate.
5. Only then choose deepen-F02/F03, F06, or Factor repair.

## 8. Explicit non-goals

- No new suitability thresholds.
- No Cow–Sheep ranking invented to force differentiation.
- No Flood Factor implementation in this phase.
- No treating engineering geometries as purchasable parcels or known-operation ground truth.
- No LLM override of MatchResults.

## 9. Stop rule for this phase

When 3–5 slot-satisfying parcels have schema-complete `validation_result` records and the portfolio rollup answers the decision gate, stop collecting more parcels unless a defect requires a targeted reproduction case.
