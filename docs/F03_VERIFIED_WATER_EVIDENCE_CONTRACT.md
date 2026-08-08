# F03 Verified-Water Evidence Contract (Review Brief)

> Status: `APPROVED_V0_1_1`  
> Date: 2026-08-08  
> Canonical machine contract: [`F03_VERIFIED_WATER_EVIDENCE_CONTRACT.yaml`](./F03_VERIFIED_WATER_EVIDENCE_CONTRACT.yaml) `@0.1.1`  
> Golden-test contract: [`F03_VERIFIED_WATER_GOLDEN_TEST_CONTRACT.yaml`](./F03_VERIFIED_WATER_GOLDEN_TEST_CONTRACT.yaml) `@0.1.1`  
> Adapter authorization: `APPROVED_FOR_SMALL_SCALE_PILOT` (remote-only; no FIELD_VERIFIED manufacturing)

## Governing question

> What evidence must a mapped water candidate satisfy before it may be promoted from “present on a map” to “a possibly usable livestock-water source”?

## Three-tier state machine

```text
MAPPED_CANDIDATE
→ REMOTELY_SUPPORTED_CANDIDATE   ← remote/open data 上限
→ FIELD_VERIFIED_LIVESTOCK_WATER ← field / 可靠运营记录 / reviewed equivalent / MIXED+qualified field basis
```

Open / remote data **must not** jump to `FIELD_VERIFIED_LIVESTOCK_WATER`.

## Dimension checklist (v0.1.1)

| Dimension | Evaluation | Remote promotion | Field verified |
|---|---|---|---|
| `feature_identity` | required | type declared | type declared |
| `physical_presence` | required | `confirmed` + allowed source | `confirmed` + field/operator/`reviewed_equivalent`, or `MIXED` + `qualified_field_basis` |
| `seasonal_reliability` | required; **unknown allowed remotely** | optional contributor to at-least-one | status ≠ unknown |
| `livestock_accessibility` | required; **unknown allowed remotely** | optional contributor to at-least-one | `supported` \| `constrained` |
| `capacity` | structured object | measured/documented may satisfy at-least-one | measured/documented **or** unknown + `unknown_rationale` |
| `water_quality` | `{status, diligence_required, evidence_source_ids}` | verified may satisfy at-least-one | `verified` \| `unknown` with `diligence_required: true` when unknown |
| `legal_access` | evaluate | may stay unresolved | `verified` \| `not_applicable` |
| `verification_level` | computed | — | — |

### Structured capacity / water quality

```yaml
capacity:
  status: measured | documented | unknown
  value: null
  unit: null
  scenario_reference: null
  unknown_rationale: required_when_status_unknown

water_quality:
  status: verified | unknown
  diligence_required: boolean   # true when status == unknown
  evidence_source_ids: []
```

### Remote promotion logic

Beyond confirmed presence, require **at least one** of:

- non-unknown `seasonal_reliability`
- `livestock_accessibility` in `{supported, constrained}`
- `capacity.status` in `{measured, documented}`
- `water_quality.status == verified`

`seasonal_reliability` / `livestock_accessibility` are **not** each independently mandatory for remote promotion.

### Single-date imagery

```text
physical_presence: confirmed_for_observation_date
seasonal_reliability: unknown
```

A single wet date does **not** justify perennial / intermittent / ephemeral.

## Frozen governance

- NHD feature ≠ livestock water  
- Near ≠ accessible  
- Water visible ≠ year-round reliable  
- Well location ≠ operable well  
- Missing legal access stays unresolved / UNKNOWN  
- `verified_count == 0` ≠ land has no water  
- No count/distance suitability thresholds  
- No Cow–Sheep ranking from water evidence  

## Review snapshot

```yaml
contract_version: 0.1.1
three_tier_state_machine: PASS
remote_evidence_ceiling: PASS
dimension_schema_alignment: PASS
mixed_and_reviewed_equivalent_path: PASS
golden_test_contract: PASS
adapter_authorization: APPROVED_FOR_SMALL_SCALE_PILOT
```

## Pilot scope (authorized)

```text
MAPPED_CANDIDATE → remote evidence collection → REMOTELY_SUPPORTED or remains MAPPED
```

Do **not** manufacture `FIELD_VERIFIED_LIVESTOCK_WATER` without real field/operator evidence. Verified count remaining zero is a correct result.
