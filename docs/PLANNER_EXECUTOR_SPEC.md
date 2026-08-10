# Planner Executor Spec

> Status: `IMPLEMENTED — FIXTURE_AND_CONTROLLED_LIVE_PATHS`  
> Date: 2026-08-08  
> Executor version: `RANGEMATCH_PLANNER_EXECUTOR@0.1.0`  
> Planner version: `RANGEMATCH_PLANNER@0.1.0`  
> Live network: explicit adapter authorization only  
> Live Mireye: verified on a clean network; historical SafeBrowse incident remains in dated audit records

## Purpose

Execute an approved Planner dependency DAG using registered fixture-backed or controlled live tool runners, then produce the Unified Output envelope and its validated buyer-facing projections.

This slice does **not** change F01–F08 science, engine decisions, Planner DAG construction, Mireye normalization semantics, or source Land Profile / MatchResult fixtures.

## Lifecycle

```text
validate plan (planner_version + plan_sha256)
        │
        ▼
resolve runners via tool registry only
        │
        ▼
topological execution (sequential groups; parallel_group metadata retained)
        │
        ├─ geometry validate / resolve
        ├─ Mireye contexts (fixture success OR visible BLOCKED_EXTERNAL)
        ├─ F06
        ├─ peer Factors F01/F02/F03/F04/F05/F07
        ├─ F08 REUSE F02 artifact (never duplicate RAP FETCH)
        ├─ assemble Land Profile (canonical report order F01–F08)
        ├─ evaluate engine → MatchResult
        ├─ project Unified Output
        ├─ bind constrained explanation
        └─ optionally run Public Diligence search as a non-canonical side branch
        │
        ▼
execution record + deterministic_execution_hash
```

## Step statuses

| Status | Meaning |
|---|---|
| `PENDING` | Not started |
| `RUNNING` | In progress |
| `SUCCEEDED` | Completed with usable outputs |
| `PARTIAL` | Completed with preserved partial failures / gaps |
| `FAILED` | Runner failed closed |
| `BLOCKED_EXTERNAL` | External transport/policy block (e.g. documented Mireye SafeBrowse class) |
| `BLOCKED_DEPENDENCY` | Upstream hard dependency blocked/failed |
| `SKIPPED_REUSE` | Intentionally skipped because reuse path already satisfied (rare; F08 normally `SUCCEEDED` with reuse refs) |

## Dependency failure policy

1. **Geometry failure** → block F06 and all parcel-wide F01–F08; no MatchResult that pretends to evaluate a parcel.  
2. **F02 failure** → F08 `BLOCKED_DEPENDENCY`; no separate RAP fetch; other peers may continue.  
3. **Mireye `BLOCKED_EXTERNAL` / PARTIAL** → does **not** block canonical Factor adapters; remains visible in trace + Unified Output with limitations / diligence note.  
4. **Individual peer Factor failure** → preserve UNKNOWN / NEEDS_VERIFICATION; continue independent peers; assembly must not invent Land Facts.  
5. **Engine / project / explanation** → engine consumes assembled Land Profile only; projection consumes Engine MatchResult; `explanation_binding_hash == match_result_hash`; explanation cannot change labels.

## Runner registry

Runners are keyed by approved `tool_id` from `tool_registry.py`. Unauthorized tools (`F09`, batch, ICP, portfolio, region) are rejected.

The original fixture-backed runner registry remains the deterministic replay and test path:

| tool_id | runner_id |
|---|---|
| `geometry.validate_one_parcel` | `fixture.geometry_validate` |
| `geometry.resolve` | `fixture.geometry_resolve` |
| `mireye.property_diligence` | `fixture.mireye_property` |
| `mireye.point_land` | `fixture.mireye_point_land` |
| `mireye.point_hazard` | `fixture.mireye_point_hazard` |
| `factor.f06_parcel_configuration` | `fixture.factor_f06` |
| `adapter.usgs_3dep` | `fixture.factor_f01` |
| `adapter.rap_cover_production` | `fixture.factor_f02_rap` |
| `adapter.nhd_water_candidates` | `fixture.factor_f03` |
| `adapter.usda_sda` | `fixture.factor_f04` |
| `adapter.noaa_ncei_precip` | `fixture.factor_f05` |
| `adapter.tiger_roads` | `fixture.factor_f07` |
| `factor.f08_woody_reuse_rap` | `fixture.factor_f08_reuse` |
| `profile.assemble` | `fixture.assemble_land_profile` |
| `engine.evaluate` | `fixture.engine_evaluate` |
| `output.project_unified` | `fixture.project_unified` |
| `explanation.bind_and_product` | `fixture.explanation_bind` |
| `diligence.dynamic_from_planned_actions` | `fixture.dynamic_diligence` |

## Determinism

- `deterministic_execution_hash` hashes non-volatile execution fields only.  
- **Excluded:** `started_at`, `completed_at`, and other wall-clock timestamps.  
- Same plan + fixtures + executor/planner versions → same hash.

## Network / credentials

- Fixture runners must not open sockets; tests assert this boundary.  
- Live runners require explicit authorization, bounded retry, source-specific validation, and fail-closed behavior.  
- Credentials never enter execution artifacts, hashes, or logs.

## Implementation

- `src/rangematch/planner_executor.py`  
- `src/rangematch/tool_runners.py`  
- `tests/test_planner_executor.py`  
- Example records: `test-data/planner-executor/`
