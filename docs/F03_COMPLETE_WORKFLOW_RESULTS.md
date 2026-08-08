# F03 Complete Workflow Results

> Gate: `docs/F03_DEMO_COMPLETION_GATE.yaml` — **PASSED**  
> Date: 2026-08-08  
> Gate-local decision at completion time: F06 / F07 were **not authorized**. This historical decision is superseded by `docs/DEMO_FACTOR_SCOPE.md`, which authorizes F06 first-stage work and fixes the Demo scope at F01–F08.

## Completed parts reviewed

1. F03 evidence contract v0.1.1 — `docs/F03_VERIFIED_WATER_EVIDENCE_CONTRACT.yaml`
2. Deterministic verification core — `src/rangematch/f03_verification.py`
3. Five-parcel remote collection — `docs/F03_FIVE_PARCEL_REMOTE_COLLECTION_RESULTS.md`
4. Field/operator evidence ingestion workflow — `docs/F03_FIELD_EVIDENCE_INGESTION_SPEC.yaml`
5. Synthetic state-transition fixtures — `test-data/f03_field_evidence_fixtures/`
6. Existing F03 runtime rules and CPER demo output — `docs/F03_WATER_DETERMINISTIC_RULES.yaml`, `test-data/land-profiles/`

No new F03 research or adapters were added for this completion audit.

## State machine

| Level | Implemented | Live CPER / five parcels | Synthetic only |
|---|---|---|---|
| `MAPPED_CANDIDATE` | yes | yes | yes |
| `REMOTELY_SUPPORTED_CANDIDATE` | yes | yes (5 of 15 sampled) | yes |
| `FIELD_VERIFIED_LIVESTOCK_WATER` | yes | **never** (`field_verified_count: 0`) | yes (TEST_ONLY) |

Remote/open adapters cannot produce `FIELD_VERIFIED`.

## Sampling disclosure

Across five frozen parcels:

```text
available candidates: 80
deterministically sampled / reviewed: 15
selection_method: STABLE_CANDIDATE_ID_ORDER_MAX_3
FIELD_VERIFIED total: 0
```

Unreviewed candidates are **UNREVIEWED**, not failed, absent, or rejected.

## CPER demo-facing F03 summary

Regenerated into Land Profile / MatchResult / demo closure without changing Factor signal:

| Item | Value |
|---|---|
| total mapped candidates | 9 |
| deterministically sampled for remote review | 3 |
| remotely supported | 2 |
| sampled but still mapped | 1 |
| field verified | 0 |
| unreviewed | 6 |
| sample coverage limitation | only 3 of 9 candidates were remotely reviewed |
| Factor state | `MAPPED_CANDIDATES_ONLY` |
| signal | `NEEDS_VERIFICATION` |
| ranking_effect | `NONE` |

Explicit demo statements:

- REMOTELY_SUPPORTED does not mean usable livestock water
- FIELD_VERIFIED remains zero
- six unsampled candidates are UNREVIEWED, not absent or rejected
- synthetic field-evidence demo is TEST_ONLY and not part of CPER
- water reliability, capacity, quality, livestock accessibility, and legal access remain unresolved

## Real / synthetic separation

| Stream | Location | Live profile write | Live validation stats |
|---|---|---|---|
| Five-parcel remote collection | `test-data/cross-parcel-validation/*/f03_remote_pilot/` | no FIELD_VERIFIED | included; FV=0 |
| Synthetic field ingestion demo | `test-data/f03_field_evidence_*` | prohibited for XPV_* | excluded |

## Runtime / ranking confirmation

```yaml
runtime_rules_changed: false
ranking_effect: NONE
suitability_thresholds_added: false
cow_sheep_ranking_added: false
cow_calf_sheep_relationship: PEERS
verified_count_zero_means_no_water: false
```

Geometry replacement invalidates F03 and sets `f03_evidence_relink_required: true`.

## Remaining F03 limitations

- Traversable distance still needs fencing/barrier/access inputs
- Most mapped candidates remain unreviewed under the max-3 sample
- No real field/operator evidence is attached to frozen parcels
- Waterbody / unmapped FCode candidates can have provenance-complete presence and still stay MAPPED without an approved remote attribute
- F02 coverage/scope depth remains an open next-phase item
- F06 remains deferred

## Decision

**F03 evidence-depth upgrade: COMPLETE for the authorized remote + synthetic field-workflow scope.**

F06 is **not** authorized to begin from this gate.
