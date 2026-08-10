# Planner Routing Spec (Dependency DAG)

> Status: `IMPLEMENTED — DETERMINISTIC_DAG`  
> Date: 2026-08-08  
> Planner version: `RANGEMATCH_PLANNER@0.1.0`  
> Live execution: controlled by Executor and explicit network authorization  
> Current product status: see `CURRENT_SYSTEM_BASELINE.md`

## Purpose

Deterministic, testable investigation planner for **one parcel**. The Planner emits an approved tool DAG; the Executor—not the Planner—performs controlled adapter calls.

## Critical separation

| Concept | Order |
|---|---|
| Canonical **report** order | `F01, F02, F03, F04, F05, F06, F07, F08` |
| **Execution** order | Dependency DAG (not the report list) |

**Do not** implement a fixed chain `F06→F01→F02→F08→F04→F05→F03→F07` as the only schedule. Peers may be planned in parallel after gates.

## Execution dependency DAG

```text
[resolve/bind exactly one geometry]
        │
        ├─► [Mireye PROPERTY / LAND / HAZARD context]  (after location available)
        │
        └─► [F06 COMPUTE]  geometry validity, hash, area, working CRS, parcel config
                │
                ├─► F01 3DEP          ┐
                ├─► F02 RAP           │
                ├─► F03 NHD/NAIP      ├─ peers (parallel-capable)
                ├─► F04 SDA           │
                ├─► F05 NOAA          │
                └─► F07 TIGER         ┘
                        │
                        └─► F08 RAP woody REUSE F02 coverV3 artifact
                                │
                                ▼
                [assemble Land Profile in report order F01–F08]
                                │
                                ▼
                [EVALUATE engine → MatchResult]
                                │
                                ▼
                [PROJECT unified output]
                                │
                                ▼
                [validated buyer narrative + dashboard/report/appendix]
                                │
                                └─► [Public Diligence search side branch]
```

### Rules

1. Resolve and validate **exactly one** parcel geometry.  
2. **F06** after geometry resolution.  
3. After valid geometry + F06 gate, **F01, F02, F03, F04, F05, F07** are dependency peers.  
4. **F08** depends on a compatible F02 RAP `coverV3` artifact (same geometry hash, year, mask, applicability, coverage, artifact hash) and plans **REUSE**, never duplicate FETCH.  
5. Assemble Factor results in canonical report order F01–F08 regardless of completion order.

## Planner input

Exactly one of:

- `address` / place string  
- `parcel_geometry` (Feature or single-Feature FeatureCollection)  
- `land_profile` (existing)

Plus:

```yaml
mode: GOAL_DIRECTED | DISCOVERY
intended_operation: COW_CALF_OPERATION | SHEEP_GRAZING | null
planned_actions: []   # optional; dynamic diligence only
```

Mode rules match `AGENT_ORCHESTRATION_SPEC.md` / unified output contract.

## Planned-step fields

Every step must include:

```text
step_id
tool_id
purpose
input_refs
dependency_step_ids
action: FETCH | REUSE | COMPUTE | EVALUATE | PROJECT | EXPLAIN
expected_output_type
canonical_authority
failure_behavior
prohibited_promotions
```

Optional planning metadata: `factor_id`, `parallel_group`, `report_order_index`.

## Final DAG stages (required terminal sequence)

```text
assemble → evaluate → project → explain/product
```

## Hard constraints

- Planner itself makes no network calls; Executor network use must be explicit and adapter-scoped  
- One parcel only; no batch / ICP / portfolio / region search  
- No F09 / no new Factor  
- No Factor science or engine changes  
- No duplicate RAP call for F08  
- Planner cannot modify Engine decisions  
- Mireye remains non-canonical  
- `planned_actions` do not alter Factor DAG  
- Failures remain explicit  
- Same input + planner version → same DAG  

Public Diligence is a post-Engine side branch. It may search current official sources and return cited guidance, but it cannot mutate F01–F08, MatchResult, or operation labels.

## Implementation

- `src/rangematch/tool_registry.py`  
- `src/rangematch/planner.py`  
- Tests: `tests/test_planner.py`  
- Mireye contracts: `docs/MIREYE_PROTOTYPE_ADAPTER_CONTRACTS.md`  
