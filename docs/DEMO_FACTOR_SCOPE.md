# RangeMatch Demo Factor Scope — F01–F08 Only

> Status: `CLOSED`  
> Date: 2026-08-08  
> Product scope: time-constrained evidence-constrained screening demo  
> Current product phase: Competition Packaging + Deployment Readiness (see `RANGEMATCH_PRODUCT_AND_AGENT_CODE_FLOW.md`)

## Canonical scope

The RangeMatch demo Factor set is limited to exactly eight Factor families and is now **closed**. No F09 or later Factor may be started without a new authorization.

The product prototype accepts one parcel per run. Batch search and portfolio ranking are not part of this scope.

| Factor | Canonical name | Demo status |
|---|---|---|
| `F01` | Topography | `FROZEN_V0_1` |
| `F02` | Herbaceous Resource | Implemented; known coverage limitation retained (`COVERAGE_UNQUANTIFIED`) |
| `F03` | Livestock Water | Demo-complete evidence-depth workflow |
| `F04` | Soil, Wetness, and Ecological Site | `FROZEN_V0_1` |
| `F05` | Climate and Drought Exposure | `FROZEN_V0_1` |
| `F06` | Parcel Configuration | `FROZEN_V0_1` |
| `F07` | Road and Physical Access Context | `FROZEN_V0_1` |
| `F08` | Woody and Shrub Vegetation Structure | `FROZEN_V0_1` |

```yaml
demo_factor_scope:
  factors: F01_TO_F08
  status: CLOSED

f09_authorization: NOT_AUTHORIZED
```

## Completed execution order

```text
F03 demo completion
→ F06 Parcel Configuration
→ F07 Road and Physical Access Context
→ F08 Woody and Shrub Vegetation Structure (FROZEN_V0_1)
→ Product Prototype and Agent Orchestration   ← current phase
```

F02 raster coverage deepening, Flood/FEMA, fencing, infrastructure, zoning, legal-right automation as Factors, predator exposure, poisonous plants, and any F09+ remain deferred. They must not reopen the Factor build gate.

## Governance

- The eight-Factor set is a demo scope boundary, not a claim of sufficiency for purchase, carrying capacity, profitability, or operational decisions.
- Every Factor remains evidence-constrained, deterministic, versioned, and explicit about unknowns.
- No Factor authorizes invented thresholds, scores, hard exclusions, or Cow-Calf/Sheep ranking.
- Historical review documents remain valid records; this file records **closure** of the Factor slice.
- Agent orchestration may use Mireye diligence reads and dynamic regulatory investigation **without** adding new Factors.
- Goal-directed mode evaluates the user-selected Profile first; Discovery mode evaluates Cow-Calf and Sheep as peers.
- Historical five-parcel validation remains engineering evidence and does not authorize a user-facing batch workflow.

## Deferred work is not deleted

Deferred items remain product-development backlog candidates. They are not part of the closed demo Factor gate and must not block the Product Prototype.
