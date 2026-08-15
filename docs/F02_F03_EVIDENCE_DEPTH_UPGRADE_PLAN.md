# F02/F03 Evidence Depth and Verification Upgrade Plan

> **Historical work plan.** F03 demo evidence-depth work was completed and F02 deepening was deferred for the competition demo. Current scope and next work are defined in `RANGEMATCH_PRODUCT_AND_AGENT_CODE_FLOW.md`.

> Status: `ACTIVE — NEXT PHASE LOCKED`  
> Date: 2026-08-08  
> Prior phase conclusion: `docs/CROSS_PARCEL_VALIDATION_CONCLUSION.yaml`  
> Goal: Deepen F02 coverage/scope evidence and F03 verified-water pathways without selecting F06 or inventing ranking

## 1. Locked objective

```text
F02/F03 Evidence Depth and Verification Upgrade
```

Cross-parcel validation passed with stable rule behavior. The bottleneck is evidence depth of existing Factors, not a missing Factor.

## 2. Priority order

### Priority 1 — F03 verified water

Current state on all five frozen parcels:

```text
mapped_candidate_count > 0
verified_livestock_water_system_count = 0
```

Required work:

1. Define a deterministic **candidate → verified livestock-water system** pathway.
2. Keep non-equivalences frozen:
   - NHD feature ≠ verified livestock water
   - proximity / Euclidean distance ≠ reliability or access
   - remote visibility ≠ operational drinking source
3. Verification dimensions that must be explicit before promotion:
   - reliability (including seasonal / drought-period status)
   - accessibility (physical reach for livestock; traversable path remains method-review)
   - capacity / deliverable supply for a declared use period
   - legal access (ownership, easement, permit, water right)
   - seasonal / operational status
4. Missing verification remains `NEEDS_VERIFICATION` or `UNKNOWN`; never invent suitability.

Deliverables:

- [x] Verification evidence contract — `docs/F03_VERIFIED_WATER_EVIDENCE_CONTRACT.yaml` (+ review brief `.md`)
- [x] Allowed promotion states and prohibited shortcuts (three-tier machine)
- [x] Golden-test contract — `docs/F03_VERIFIED_WATER_GOLDEN_TEST_CONTRACT.yaml`
- [x] Contract review / approval gate — `APPROVED_V0_1_1` / `APPROVED_FOR_SMALL_SCALE_PILOT`
- [x] Deterministic schema validator + promotion evaluator — `src/rangematch/f03_verification.py`
- [x] Executable golden tests — `tests/test_f03_verified_water.py`
- [x] Small remote-only pilot on CPER — `scripts/run_f03_remote_pilot.py` → `test-data/cross-parcel-validation/XPV_CPER_001/f03_remote_pilot/`
- [ ] Review pilot; only then consider five-parcel remote collection (still no FIELD_VERIFIED manufacturing)

### Priority 2 — F02 coverage and scope

Required work:

1. Establish raster-level **eligible / masked / no-data / valid** area quantification (GEE or equivalent version-matched raster path).
2. Preserve applicability discipline:
   - `IN_DOCUMENTED_PRODUCT_SCOPE`
   - `OUTSIDE_DOCUMENTED_PRODUCT_SCOPE` (KBS is a correct outcome; do not force RAP)
   - `UNKNOWN` (Ordway triggers diligence, not inference)
3. Aggregate API remains a fast path; quantified coverage upgrades confidence only when areas are actually measured.
4. Do not convert cover/production into available forage, palatability, or carrying capacity.

Deliverables:

- Coverage derivation contract and fixture schema
- Scope decision table tied to frozen parcel slots
- Engine/golden updates only if coverage states change under existing gate order
- Before/after coverage fields on the five frozen parcels

### Priority 3 — Mireye SSL adapter incident

Track separately: `docs/MIREYE_SSL_ADAPTER_INCIDENT_2026-08-08.md`.

- Do not alter Land Facts or MatchResults because of the incident.
- After fix, re-run **point QA only**.
- Do **not** re-fetch canonical NOAA precip, SDA parcel soils, RAP, or NHD unless those paths themselves change.

## 3. Before / after comparison protocol

Use the same five frozen parcels:

```text
XPV_CPER_001
XPV_KONZA_001
XPV_REYNOLDS_001
XPV_ORDWAY_001
XPV_KBS_MCSE_001
```

Comparison axes after the upgrade:

```text
before evidence upgrade
vs.
after evidence upgrade
```

Compare:

- F02 coverage status and applicability explanation codes
- F03 verified count and verification dimension completeness
- MatchResult labels/signals (expect HOLD to remain common until verification truly lands)
- Diligence actions and unknowns
- Geometry hashes unchanged

Do not replace geometries. Do not add unreviewed Cow–Sheep ranking rules.

## 4. Explicit non-goals

- F06 selection remains deferred
- Flood/FEMA has no default priority
- No suitability thresholds from precip, PFG, or candidate counts
- No promotion of mapped hydrography to verified water by proximity alone
- No forcing RAP on KBS outside-scope land
- No inferring Ordway RAP applicability from place name or PFG magnitude

## 5. Stop rule for this phase

Stop when:

1. F03 verification pathway is reviewed and test-locked (even if most parcels still have verified = 0).
2. F02 raster coverage can be quantified on at least the in-scope frozen parcels, or a documented blocker remains with `COVERAGE_UNQUANTIFIED`.
3. Five-parcel before/after rerun is recorded under the same schema.
4. Decision gate is re-applied: deepen further, select F06 only if a true new gap appears, or repair a demonstrated rule defect.

### Status as of 2026-08-08

- Item 1 for **F03** is satisfied by `docs/F03_DEMO_COMPLETION_GATE.yaml` (**PASSED**).
- F03 evidence-depth upgrade is **COMPLETE** for the authorized remote + synthetic field-workflow scope.
- Item 2 (**F02 coverage**) is **DEFERRED_FOR_DEMO** by product-owner priority; preserve existing F02 limitations and runtime behavior until after the demo.
- Demo path now authorizes **F06 Parcel Configuration** first-stage audit (`docs/F06_PARCEL_CONFIGURATION_ATOMICITY_AND_SOURCE_AUDIT.md`); F07 remains not yet authorized.
