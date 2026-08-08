# RangeMatch First Executable Vertical Slice

This prototype evaluates one CPER engineering Land Profile with the closed F01–F08 Factor set and no LLM decision authority.

```text
Parcel input / CPER fixture
→ F01–F08 data collection/fixtures
→ Normalized Land Profile
→ Deterministic engine
→ Cow-Calf / Sheep peer evaluation
→ HOLD + unknowns + diligence actions
→ constrained explanation
→ minimal product interface
```

Expected v0.1 result:

```yaml
F01_TOPOGRAPHY: CONTEXT_DEPENDENT
F02_HERBACEOUS_RESOURCE: NEEDS_VERIFICATION
F03_LIVESTOCK_WATER: NEEDS_VERIFICATION
F04_SOIL_WETNESS_ECOLOGICAL_SITE: CONTEXT_DEPENDENT
F05_CLIMATE_DROUGHT_EXPOSURE: CONTEXT_DEPENDENT
F06_PARCEL_CONFIGURATION: CONTEXT_DEPENDENT
F07_ROAD_PHYSICAL_ACCESS_CONTEXT: CONTEXT_DEPENDENT
F08_WOODY_SHRUB_VEGETATION_STRUCTURE: NEEDS_VERIFICATION
COW_CALF_OPERATION: HOLD
SHEEP_GRAZING: HOLD
cross_profile_ranking: NOT_PERMITTED
```

`HOLD` does not mean that CPER is unsuitable. Shared Factors are implemented as data-quality/context evidence. F02 pixel coverage remains unquantified, F03 contains mapped hydrography candidates rather than a verified livestock-water system, F04 is soil/wetness/ecological-site context without a directional suitability signal, F05 retains `annprcp_norm` as a Land Fact without a climate suitability threshold, F06 reports parcel geometry measurements without suitability or fencing-cost inference, F07 reports mapped-road spatial context without establishing legal access, and F08 reports modeled woody structure without establishing browse or obstruction. The fixture is engineering evidence, not suitability ground truth.

## Current milestone

> **Demo Factor scope:** `CLOSED` (F01–F08)  
> **Current phase:** Product Prototype + Agent Orchestration (`docs/AGENT_ORCHESTRATION_SPEC.md`)  
> **F03 evidence-depth upgrade:** COMPLETE  
> **F02 coverage upgrade:** DEFERRED (limitations retained)  
> **F06 / F07 / F08:** `FROZEN_V0_1`  
> **F09:** `NOT_AUTHORIZED`  

- F01–F08 demo Factor slice closed; no new Factors without authorization
- F08 freeze: `docs/F08_FREEZE_GATE_RESULTS.md` (data-reuse `PASSED`; suite `161 passed`)
- Agent call order: geometry → Mireye diligence reads → F01–F08 adapters (reuse artifacts) → Land Profile → engine → explanation
- Cross-parcel conclusion remains locked: `docs/CROSS_PARCEL_VALIDATION_CONCLUSION.yaml`

## Demo closure product surface

The local demo proves the reusable product loop, not a polished UI. It renders six sections only:

1. Parcel Summary
2. Factor Evidence
3. Operation Comparison
4. Unknowns
5. Diligence Actions
6. Source Trace

Generate the local demo artifacts:

```bash
PYTHONPATH=src python3 -m rangematch.cli demo-closure \
  test-data/land-profiles/land_profile_cper_001.json
```

Outputs:

- `test-data/land-profiles/land_profile_cper_001_demo_closure.html`
- `test-data/land-profiles/land_profile_cper_001_demo_closure.json`

Open the HTML file in a browser. The constrained explanation is bound to the MatchResult hash and cannot alter decision labels.

## Geometry replacement path

Prove the CPER fixture is not the only admissible input:

```bash
PYTHONPATH=src python3 -m rangematch.cli replace-geometry \
  test-data/land-profiles/land_profile_cper_001.json \
  test-data/engineering_test_geometry_cper_002.geojson \
  --output /tmp/land_profile_cper_replaced.json \
  --geometry-reference test-data/engineering_test_geometry_cper_002.geojson
```

Expected: new geometry id/hash, invalidated Factor evidence, and a different MatchResult `input_sha256` after `evaluate`.

## Factor notes

The F03 fixture includes nine parcel-intersecting NHD candidates and a parcel-wide Euclidean-distance distribution. Under `STABLE_CANDIDATE_ID_ORDER_MAX_3`, three candidates were deterministically sampled for remote review: two are `REMOTELY_SUPPORTED`, one sampled candidate remains `MAPPED`, and six unsampled candidates are **UNREVIEWED** (not absent or rejected). `REMOTELY_SUPPORTED` does not mean usable livestock water. `FIELD_VERIFIED` remains 0. Factor state stays `MAPPED_CANDIDATES_ONLY` / `NEEDS_VERIFICATION` / `ranking_effect: NONE`. Reliability, capacity, quality, livestock accessibility, and legal access remain unresolved. These facts must not be interpreted as verified livestock-water systems or traversable animal-access distance.

The F04 fixture preserves parcel map-unit coverage, non-renormalized component support weights, controlled-category distributions, restrictive-layer uncertainty, and ecological-site references from official USDA SDA and EDIT fixtures. EDIT fetch timeouts remain `UNKNOWN`, not `NOT_ACCESSIBLE`. Mireye centroid soil fields are point QA/display only. Available-water storage derivation exists as a parameterized function, but no approved depth interval is applied in the Land Profile.

## Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m rangematch.cli evaluate \
  test-data/land-profiles/land_profile_cper_001.json
```
