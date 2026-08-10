# Cross-Parcel Validation Results (Portfolio Rollup)

> **Historical validation result.** Current runtime scope is F01–F08; this rollup remains an immutable record of the earlier cross-parcel gate.

> Status: `PASSED`  
> Date: 2026-08-08  
> Canonical conclusion: `docs/CROSS_PARCEL_VALIDATION_CONCLUSION.yaml`  
> Detailed aggregate: `docs/CROSS_PARCEL_FIVE_PARCEL_AGGREGATE_REVIEW.md`

## Locked conclusion

```yaml
cross_parcel_validation: PASSED
rule_behavior_across_environments: STABLE
species_differentiation: NOT_YET_ESTABLISHED
primary_bottlenecks:
  - F02_COVERAGE_AND_SCOPE
  - F03_VERIFIED_WATER
f06_selection: DEFERRED
```

## Decision gate answer

| Gate | Answer |
|---|---|
| Main bottleneck existing data quality? | **Yes** — deepen F02/F03 |
| Clear new decision gap requiring F06? | **No** — F06 deferred |
| Rules abnormal across environments? | **No** — stable; no mid-run rule change |

## Next phase

**F02/F03 Evidence Depth and Verification Upgrade** — `docs/F02_F03_EVIDENCE_DEPTH_UPGRADE_PLAN.md`

Priority: F03 verified water → F02 coverage/scope → Mireye SSL adapter incident (point QA only after fix).

Rerun the same five frozen parcels for before/after comparison. Do not select F06. Do not add unreviewed Cow–Sheep ranking rules.
