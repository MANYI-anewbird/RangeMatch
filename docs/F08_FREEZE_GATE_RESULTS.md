# F08 Woody and Shrub Vegetation Structure Freeze Gate Results

> Status: `PASSED — FROZEN_V0_1`  
> Date: 2026-08-08  
> Full test suite at freeze: `161 passed`  
> Data-reuse gate: `docs/F08_LIVE_DATA_GATE_RESULTS_CPER.md` (`DATA_REUSE_VERIFIED` / `PASSED`)

## Decision

F08 Woody and Shrub Vegetation Structure v0.1 is frozen for the RangeMatch demo. The F01–F08 demo Factor scope is **CLOSED**. F09 remains unauthorized. Next phase is Product Prototype + Agent Orchestration.

```yaml
F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE:
  freeze_status: FROZEN_V0_1
  data_reuse_gate: PASSED
  signal: NEEDS_VERIFICATION
  ranking_effect: NONE
  coverage_status: COVERAGE_UNQUANTIFIED
  full_test_suite: 161_PASSED

demo_factor_scope:
  factors: F01_TO_F08
  status: CLOSED

f09_authorization: NOT_AUTHORIZED
```

## Gate evidence retained

- RAP `SHR`/`TRE` percent → Land Fact fraction (`/100`); raw percent in provenance
- `combined_modeled_woody_cover_fraction = shrub + tree`; null if either null; null ≠ 0
- F02/F08 share artifact hash, year, geometry hash, mask, applicability, coverage
- No duplicate RAP `coverV3` request when artifact exists
- `COVERAGE_UNQUANTIFIED` not upgraded to complete / `CONTEXT_DEPENDENT`
- Geometry replacement invalidates F08
- No browse, obstruction, carrying capacity, profitability, or Cow–Sheep ranking
- Executable goldens: `tests/test_f08_derivation.py`

## Human verification notes

Product-owner review confirmed percent→fraction, combined woody math, null policy, shared provenance, no RAP refetch, coverage alignment, geometry invalidation, prohibited interpretations, and `161 tests OK`.

## Next authorization

- Do **not** start F09 or any additional Factor.
- Proceed to **Product Prototype + Agent Orchestration** per `docs/AGENT_ORCHESTRATION_SPEC.md`.
