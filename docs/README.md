# RangeMatch Documentation Index

> Status: `CURRENT_CANONICAL`
> Alignment gate: `POST_LLM_ALIGNMENT_2026_08_08`

**Start here:** `CURRENT_SYSTEM_BASELINE.md` is the authoritative description of the current product, workflow, report, and implementation status.

This index separates current product authority from frozen science and historical records. Historical files remain useful audit evidence, but they must not override current canonical contracts.

## Current canonical product and runtime

- `MVP_SPEC.md`
- `CURRENT_SYSTEM_BASELINE.md`
- `PRODUCT_PROTOTYPE_SCOPE.md`
- `AGENT_ORCHESTRATION_SPEC.md`
- `PLANNER_ROUTING_SPEC.md`
- `PLANNER_EXECUTOR_SPEC.md`
- `ONE_PARCEL_API_SPEC.md`
- `PARCEL_RESOLUTION_CONTRACT.md`
- `MIREYE_LIVE_PARCEL_RESOLVER_CONTRACT.md`
- `MIREYE_PROTOTYPE_ADAPTER_CONTRACTS.md`
- `F01_F08_UNIFIED_OUTPUT_CONTRACT.md`
- `LLM_AUTHORITY_AND_REPORT_SPEC.md`
- `DILIGENCE_SEARCH_AGENT_SPEC.md`
- `BUYER_DASHBOARD_AND_SCORING_SPEC.md`
- `PACKAGING_AND_DELIVERY_STRATEGY.md`
- `DEMO_FACTOR_SCOPE.md`
- `RANGEMATCH_AGENT_BUILD_PLAN.md` (Chinese product-owner plan)

## Frozen scientific and deterministic contracts

The F01–F08 evidence registries, source audits, derivation specifications, deterministic rules, golden tests, live-gate results, and freeze-gate results are frozen scientific/engineering records. Product or UI work must not rewrite them without reopening the relevant Factor governance gate.

Key cross-Factor registries:

- `SOURCE_REGISTRY.md`
- `SPECIES_REQUIREMENTS_REGISTRY.md`
- `UNIFIED_LAND_VARIABLE_REGISTRY.yaml`
- `FACTOR_FREEZE_GATE.yaml`

## Current engineering evidence

- `FIRST_VERTICAL_SLICE.md`
- `MIREYE_LIVE_RECHECK_SUCCESS_2026-08-08.md`
- `ONE_PARCEL_PRODUCT_ACCEPTANCE_2026-08-08.md`
- `OPENAI_LIVE_GATE_RESULTS_2026-08-08.md`
- `DILIGENCE_SEARCH_LIVE_GATE_RESULTS_2026-08-08.md`
- `F03_COMPLETE_WORKFLOW_RESULTS.md`
- `CROSS_PARCEL_VALIDATION_RESULTS.md`

## Historical records

Documents whose titles describe an earlier milestone—such as `FIVE_FACTOR_PORTFOLIO_REVIEW.md`—are historical snapshots. Failed-network records including `MIREYE_ADAPTER_LIVE_GATE_RESULTS.md`, `MIREYE_SSL_TRANSPORT_DIAGNOSIS.md`, and `MIREYE_LIVE_RECHECK_RESULTS_2026-08-08.md` describe the earlier intercepted network. Their dates, outcomes, and test counts are intentionally preserved and are not current product status.

## Current readiness

```yaml
factor_scope: F01_F08_CLOSED_FROZEN
supported_operations:
  - COW_CALF_OPERATION
  - SHEEP_GRAZING
backend_tests: 423_PASSED
ui_tests: 22_PASSED
llm_intent_and_buyer_report: IMPLEMENTED
report_validator: HARDENED
buyer_report_ui: IMPLEMENTED
deterministic_ui_fallback: IMPLEMENTED
live_mireye: LIVE_VERIFIED_ON_CLEAN_NETWORK
parcel_map_ui: IMPLEMENTED_MAPLIBRE_2D
mireye_live_parcel_resolver: IMPLEMENTED
public_diligence_search: IMPLEMENTED_LIVE_VERIFIED
buyer_decision_report_v2: IMPLEMENTED
engine_behavior: HOLD_ONLY_NO_APPROVED_RANKING
next_slice: COMPETITION_PACKAGING_AND_DEPLOYMENT_READINESS
```

`HOLD_ONLY_NO_APPROVED_RANKING` is an intentional scientific limitation: the current prototype performs evidence-constrained diligence and does not yet claim a Cow-Calf-versus-Sheep suitability ranking.
