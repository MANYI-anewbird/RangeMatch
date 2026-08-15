# F01–F08 Unified Output Contract

> Status: `EXECUTABLE_V0_1`  
> Date: 2026-08-08  
> Contract version: `RANGEMATCH_UNIFIED_OUTPUT@0.1.0`  
> Schema: `docs/schemas/rangematch_unified_output.schema.json`  
> Projection: `src/rangematch/unified_output.py`  
> Golden: `test-data/land-profiles/unified_output_cper_001.json`  
> Scope: one U.S. parcel per run; frozen Factors F01–F08  
> F09 / new Factors: `NOT_AUTHORIZED`

## Purpose

Freeze the shared output contract from approved F01–F08 Land Facts through MatchResult and the buyer-facing product surface for the Product Prototype.

This document does **not** change scientific rules, Factor derivations, decision behavior, or fixtures. It defines how existing frozen outputs are assembled, named, and presented.

Related:

- `docs/LAND_FACT_SCHEMA.yaml@0.1.0` — Land Fact trust dimensions  
- `docs/AGENT_ORCHESTRATION_SPEC.md` — call order  
- `docs/DEMO_FACTOR_SCOPE.md` — Factor slice `CLOSED`  
- `docs/PRODUCT_PROTOTYPE_SCOPE.md` — buyer promise  

## Hard constraints

```yaml
parcels_per_run: 1
batch_icp_portfolio_workflows: NOT_AUTHORIZED
f09_or_new_factors: NOT_AUTHORIZED
scientific_rule_changes: false
executable_schema: docs/schemas/rangematch_unified_output.schema.json
projection_module: src/rangematch/unified_output.py
```

### Locked implementation decisions (v0.1)

1. **Jurisdiction** container required; values may be null; require `resolution_status`: `RESOLVED | PARTIAL | UNKNOWN | NOT_REQUESTED`.
2. **Coverage** uses `normalized_status` + preserved `source_status` + `details`. Projection normalizes aliases only; Factor runtime states are not rewritten.
3. **F07**: physical road context → Property; legal-access/entrance/passability → Diligence Plan; one canonical Factor result.
4. **`planned_actions: []`** optional run input; routes dynamic diligence only; cannot mutate F01–F08 or MatchResult.
5. **Hashes**: `engine_input_hash` (= MatchResult `input_sha256`), `match_result_hash` (canonical MatchResult), `explanation_binding_hash == match_result_hash`. Canonical hashing excludes timestamps, LLM prose, UI ordering, transient request IDs, and cache paths.

---

## 1. Run identity

Every product run emits a root envelope:

| Field | Type | Required | Notes |
|---|---|---|---|
| `run_id` | string | yes | Stable unique id for the run |
| `mode` | enum | yes | `GOAL_DIRECTED` \| `DISCOVERY` |
| `intended_operation` | enum \| null | yes | `COW_CALF_OPERATION` \| `SHEEP_GRAZING` \| `null` (`null` required in Discovery) |
| `created_at` | ISO-8601 UTC | yes | Run creation time |
| `contract_version` | string | yes | `RANGEMATCH_UNIFIED_OUTPUT@0.1.0` |
| `engine_version` | string | yes | Deterministic engine version used |
| `match_result_sha256` | string | yes | Hash of canonical MatchResult JSON |

Goal-directed: `intended_operation` selects presentation/investigation order only.  
Discovery: both Profiles are peers; results must state they apply only to currently supported Profiles.

---

## 2. Parcel identity

| Field | Type | Required | Notes |
|---|---|---|---|
| `geometry_id` | string | yes | Stable geometry identifier |
| `geometry_hash` | string | yes | SHA-256 of geometry artifact / bound geometry file |
| `geometry_reference` | string | yes | Repo-relative or URI reference |
| `source_crs` | string | yes | Must be `EPSG:4326` for current demo geometry path |
| `address` | string \| null | when available | From user or Property Diligence |
| `apn` | string \| null | when available | Assessor parcel number |
| `parcel_id` | string \| null | when available | Provider parcel id |
| `jurisdiction` | object | recommended | County / state / FIPS / zoning context when known |
| `geometry_validity` | object | yes | Validity flags from F06 (or equivalent); invalid geometry blocks silent measure |

One Feature / one FeatureCollection-with-exactly-one-Feature per run. Geometry hash change **invalidates** F01–F08 parcel evidence.

---

## 3. Mireye context (non-canonical)

Mireye payloads are stored separately and typed as:

```text
PROPERTY_DILIGENCE_CONTEXT
POINT_LAND_CONTEXT
POINT_HAZARD_CONTEXT
```

### Shared Mireye context fields

| Field | Required | Notes |
|---|---|---|
| `context_type` | yes | One of the three types above |
| `endpoint_or_preset` | yes | Mireye endpoint / preset id |
| `requested_point` | yes | Lon/lat (and CRS) used for the read |
| `disposition` | yes | Success / partial / failed disposition |
| `parcel_grade` | when available | Provider parcel grade |
| `fields` | yes | Returned field map (point semantics) |
| `confidence` | when available | Provider confidence |
| `source_urls` | recommended | Traceable source URLs |
| `fetched_at` | yes | ISO-8601 UTC |
| `dataset_vintage` | when available | Dataset year / vintage |
| `partial_failures` | yes | List; empty if none |

### Non-equivalence

```text
Mireye point context ≠ parcel-wide canonical F01–F08 Land Fact
PROPERTY_DILIGENCE_CONTEXT ≠ legal title opinion
POINT_HAZARD_CONTEXT ≠ final flood/wetland determination
```

Mireye may seed investigation and diligence; it must not overwrite RAP/SDA/NOAA/TIGER/DEM/verified-water Land Facts.

---

## 4. Unified Factor result (F01–F08)

Every Factor in `{F01…F08}` MUST expose:

| Field | Required | Notes |
|---|---|---|
| `factor_id` | yes | Canonical Factor id |
| `factor_version` | yes | Frozen derivation / algorithm version string |
| `input_quality_state` | yes | Factor-specific quality state |
| `signal` | yes | `CONTEXT_DEPENDENT` \| `NEEDS_VERIFICATION` \| `UNKNOWN` (current demo set) |
| `ranking_effect` | yes | Currently `NONE` for all frozen Factors |
| `land_facts` | yes | Array of Unified Land Facts (may be empty if MISSING) |
| `applicability` | yes | Shared / Factor applicability record |
| `coverage` | yes | Coverage record |
| `provenance` | yes | Geometry hash, artifact hashes, fetch times, endpoints |
| `limitations` | yes | Explicit non-interpretations and data limits |
| `unknowns` | yes | Material unknowns for this Factor |
| `diligence_actions` | yes | Factor-scoped next checks |
| `explanation_code` | yes | Stable machine code for explanation layer |

LLM may restate these fields; it may not invent or alter them.

---

## 5. Unified Land Fact

Aligns with `LAND_FACT_SCHEMA.yaml@0.1.0`. Required product-facing fields:

| Field | Required | Notes |
|---|---|---|
| `variable_id` | yes | Registry id |
| `value` | yes | Scalar / structured / `null` when unknown |
| `unit` | yes | Controlled unit (`fraction`, `percent_cover`, `m`, etc.) |
| `raw_value` | when applicable | e.g. RAP percent before `/100` |
| `spatial_semantics` | yes | e.g. `parcel_mean`, `parcel_aggregate`, `point` |
| `temporal_semantics` | yes | Year / period semantics |
| `geometry_hash` | yes | Must match run parcel geometry hash for parcel facts |
| `source_id` | yes | Canonical source id |
| `source_version` | yes | Product/version |
| `artifact_hash` | yes | `response_or_artifact_hash` |
| `derivation_algorithm_version` | yes | Derivation algorithm id@version |
| `applicability_status` | yes | Domain applicability |
| `coverage_status` | yes | Coverage enum |
| `confidence_or_quality_status` | yes | Quality/confidence state |
| `limitations` | yes | Non-empty when material limits apply |

Parcel-canonical Land Facts use parcel spatial semantics. Point Mireye fields use point semantics and live under §3, not here.

---

## 6. Operation evaluation

Supported operations (peers):

```text
COW_CALF_OPERATION
SHEEP_GRAZING
```

For each operation:

| Field | Required | Notes |
|---|---|---|
| `operation_id` | yes | |
| `operation_profile_version` | yes | Reviewed Profile version |
| `decision_label` | yes | See §7 |
| `factor_evaluations` | yes | Map of F01–F08 Factor evaluation summaries |
| `hard_constraints` | yes | Approved hard constraints only; empty array if none |
| `supporting_signals` | yes | Codes/signals that support proceeding |
| `limiting_signals` | yes | Codes/signals that limit confidence or require diligence |
| `unknowns` | yes | Operation-scoped unknowns |
| `confidence_limitation` | yes | Plain statement of evidence limits |
| `ranking_permission` | yes | Boolean; must be `false` while all Factor `ranking_effect` are `NONE` |

### Mode presentation rules

| Mode | Presentation | Science |
|---|---|---|
| `GOAL_DIRECTED` | Selected Profile may appear first | No scientific priority; no modified rules |
| `DISCOVERY` | Both Profiles peers | Qualify results as limited to currently supported Profiles |

---

## 7. MatchResult authority

### Allowed decision labels

```text
ADVANCE
REVIEW
HOLD
REDIRECT
REJECT
```

### Authority rules

1. **Engine output is authoritative.**  
2. **LLM cannot change** decision labels or Factor signals.  
3. **`HOLD` does not mean unsuitable** — it means evidence is insufficient for a stronger label.  
4. **No numeric suitability score** unless separately reviewed and approved (none authorized now).  
5. **`REDIRECT` requires reviewed differential evidence** between Profiles; not available from `ranking_effect: NONE` alone.  
6. **`ranking_effect: NONE` cannot create cross-profile ranking.**  
7. Explanation prose MUST bind to `match_result_sha256`.

Current CPER demo expectation: both operations `HOLD`; cross-profile ranking not permitted.

---

## 8. Buyer-facing report mapping

Exactly five product sections. UI may simplify presentation but **must not discard** material unknowns, coverage limitations, source failures, or provenance access.

| Section | Primary contract sources |
|---|---|
| **Backend: Property** | Parcel identity; Property Diligence context; F06 area/shape summary |
| **Backend: Land & Resources** | F01 topography; F02 herbaceous; F08 woody; F04 soil/site; F03 water |
| **Backend: Resilience & Hazards** | F05 climate/drought; POINT_HAZARD_CONTEXT; dynamic risk findings (§9) |
| **4. Operation Comparison** | Cow-Calf vs Sheep operation evaluations; MatchResult labels; unknowns; constraints |
| **5. Diligence Plan** | Factor diligence actions; regulatory / land-rights findings; professional verification flags |

Mapping invariants:

- These backend groups remain compatibility fields in Unified Output. Buyer Decision Report v2 projects their Land Facts into a parcel-specific facts table and evidence appendix instead of displaying generic group prose.
- F07 road contact appears as physical-access context or diligence, never as legal access certainty.  
- Mireye hazards remain **point triggers**, not parcel canonical flood maps.  
- Every `NEEDS_VERIFICATION` / `UNKNOWN` Factor must remain visible in Operation Comparison and/or Diligence Plan.

---

## 9. Dynamic diligence findings (non-canonical)

Separate structure — **not F09**, not written into canonical Land Facts.

Finding kinds include: risk triggers, regulatory research, land-rights research, permit investigation.

| Field | Required | Notes |
|---|---|---|
| `finding_id` | yes | |
| `finding_type` | yes | e.g. `RISK_TRIGGER`, `REGULATORY`, `LAND_RIGHTS`, `PERMIT` |
| `trigger` | yes | What prompted the finding |
| `jurisdiction` | yes | Federal / state / county / other |
| `official_sources` | yes | Reviewed official URLs / citations |
| `publication_or_effective_date` | when available | |
| `accessed_at` | yes | ISO-8601 UTC |
| `currency_status` | yes | Whether source appears current / stale / unknown |
| `applicability_status` | yes | How it may apply to this parcel/action |
| `limitations` | yes | |
| `professional_verification_required` | yes | Boolean; must be `true` for legal/permit conclusions |

Allowed finding dispositions only:

```text
POTENTIAL_TRIGGER
NO_TRIGGER_FOUND_IN_REVIEWED_SOURCES
UNKNOWN
PROFESSIONAL_CONFIRMATION_REQUIRED
```

No final legal opinion. No silent promotion into F01–F08 Land Facts.

---

## 10. Invalidation and determinism

1. **Geometry hash change** invalidates F01–F08 parcel-derived evidence; recompute required.  
2. **Source / artifact / algorithm version changes** must be visible in provenance and Factor versions.  
3. **Same input + same versions** → same MatchResult (byte-stable canonicalization for `match_result_sha256`).  
4. **LLM prose binds** to `match_result_sha256`; mismatch → refuse or regenerate explanation.  
5. **Missing / conflicting data** remains `UNKNOWN` or `NEEDS_VERIFICATION`; never imputed to known.  
6. Provenance-complete artifacts MUST be reused (no silent duplicate RAP/SDA/etc. fetches).  
7. F08 MUST share F02 `coverV3` artifact hash / year / mask / applicability / coverage when both present.

---

## 11. Compact YAML example (CPER engineering state)

Illustrative envelope only — does not regenerate fixtures. Reflects current frozen CPER demo semantics.

```yaml
contract_version: RANGEMATCH_UNIFIED_OUTPUT@0.1.0
run_id: cper_demo_run_illustrative
mode: DISCOVERY
intended_operation: null
created_at: "2026-08-08T12:00:00Z"
engine_version: "0.1.0"

parcel:
  geometry_id: ENGINEERING_TEST_GEOMETRY_CPER_001
  geometry_hash: 932edc9b3cb36b49b5a8fdd5ffa52cba17874720947865e0916ba069fad5f309
  geometry_reference: test-data/engineering_test_geometry_cper_001.geojson
  source_crs: EPSG:4326
  address: null
  apn: null
  jurisdiction:
    county: Weld
    state: CO
    county_fips: "08123"
  geometry_validity: { usable: true }

mireye_context:
  - context_type: POINT_LAND_CONTEXT
    note: Point QA only; not parcel F01–F08 Land Facts
  - context_type: POINT_HAZARD_CONTEXT
    note: Trigger context only when fetched

factor_signals_summary:
  F01_TOPOGRAPHY: CONTEXT_DEPENDENT
  F02_HERBACEOUS_RESOURCE: NEEDS_VERIFICATION
  F03_LIVESTOCK_WATER: NEEDS_VERIFICATION
  F04_SOIL_WETNESS_ECOLOGICAL_SITE: CONTEXT_DEPENDENT
  F05_CLIMATE_DROUGHT_EXPOSURE: CONTEXT_DEPENDENT
  F06_PARCEL_CONFIGURATION: CONTEXT_DEPENDENT
  F07_ROAD_AND_PHYSICAL_ACCESS: CONTEXT_DEPENDENT
  F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE: NEEDS_VERIFICATION

example_land_fact:
  variable_id: VAR_F08_SHRUB_COVER_FRACTION
  value: 0.06727234043361567
  unit: fraction
  raw_value: 6.727234043361567
  spatial_semantics: parcel_mean
  temporal_semantics: annual_2025
  geometry_hash: 932edc9b3cb36b49b5a8fdd5ffa52cba17874720947865e0916ba069fad5f309
  source_id: USDA_ARS_RAP_V3_COVER
  source_version: v3
  artifact_hash: 58bf1fc7aa91ce3d863bf419f59dad98ec18da36db23f570a1c9dc244d951160
  derivation_algorithm_version: F08_WOODY_SHRUB_DERIVATION@0.1.0
  applicability_status: IN_DOCUMENTED_PRODUCT_SCOPE
  coverage_status: COVERAGE_UNQUANTIFIED
  confidence_or_quality_status: LIMITED_BY_UNQUANTIFIED_COVERAGE
  limitations:
    - shrub cover is not browse availability

operation_comparison:
  COW_CALF_OPERATION:
    decision_label: HOLD
    ranking_permission: false
    confidence_limitation: >-
      Shared Factor evidence is context/quality only; forage coverage unquantified;
      livestock water not field-verified; woody coverage unquantified.
  SHEEP_GRAZING:
    decision_label: HOLD
    ranking_permission: false
    confidence_limitation: same_as_cow_calf_for_current_demo

cross_profile_comparison:
  ranking_permitted: false
  numeric_score: null
  note: ranking_effect NONE on all Factors; no reviewed differential REDIRECT rule active

buyer_sections:
  Property: [parcel, F06, F07 physical-access context]
  Land & Resources: [F01, F02, F08, F04, F03]
  Resilience & Hazards: [F05, mireye hazard context]
  Operation Comparison: [both HOLD, limiting signals, unknowns]
  Diligence Plan:
    - verify livestock water reliability and capacity
    - inspect botanical composition and palatability
    - confirm legal access and usable entrance
    - keep RAP coverage unquantified limitation visible
```

---

## 12. Schema readiness checklist

| Checklist item | Status |
|---|---|
| Run identity fields defined | YES |
| Parcel identity + one-parcel rule | YES |
| Mireye typed separately from Land Facts | YES |
| Unified Factor result fields for F01–F08 | YES |
| Unified Land Fact fields aligned to existing schema | YES |
| Operation evaluation + mode presentation rules | YES |
| MatchResult authority / label set locked | YES |
| Backend compatibility groups defined | YES |
| Buyer dashboard/report/appendix projection defined in current product specs | YES |
| Dynamic diligence non-canonical structure defined | YES |
| Invalidation + determinism rules defined | YES |
| Compact CPER example without invented scores | YES |
| No F09 / no new Factor / no rule changes in this doc | YES |
| Executable JSON Schema authored | YES |
| Typed Python projection module | YES (`unified_output.py`) |
| Adapter that projects Land Profile + MatchResult | YES |
| Golden tests for envelope projection | YES |
| Canonical MatchResult hashing + explanation binding | YES |

### Recommendation

**Executable schema slice is complete and ready for Planner implementation.**

Planner should emit/consume this envelope after tool calls + `evaluate_land_profile`, without modifying Factor science.  
Mireye typed contexts are normalized by `MIREYE_UNIFIED_CONTEXT_ADAPTER@0.1.0` (`src/rangematch/mireye_adapter.py`); Factors reference `context_id` + `field_id` only. Next: Planner Executor (no Factor science changes).

---

## Unresolved questions

1. When Property Diligence fails mid-run, should `jurisdiction.resolution_status` flip from `NOT_REQUESTED` to `UNKNOWN` automatically?  
2. Optional JSON Schema runtime validation dependency (`jsonschema`) vs keeping structural validators in `unified_output.py` only.  
3. Whether buyer UI should read `buyer_report` exclusively or also deep-link into `factors[]` for power users.

---

## Light-sync targets

- `docs/AGENT_ORCHESTRATION_SPEC.md` — point to this contract as the unified output envelope.  
- `docs/PRODUCT_PROTOTYPE_SCOPE.md` — acknowledge the current buyer decision report projection + contract version.  
- `docs/archive/product-history/RANGEMATCH_AGENT_BUILD_PLAN.md` — mark unified output contract drafted; executable schema next.
