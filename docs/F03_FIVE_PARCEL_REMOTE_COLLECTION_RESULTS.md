# F03 Five-Parcel Remote Collection Results

> Status: `COLLECTION_GATE_PASSED`  
> Contract: F03 Verified-Water Evidence Contract `0.1.1`  
> Collection ID: `F03_FIVE_PARCEL_REMOTE_COLLECTION`  
> As of: `2026-08-08`  
> Runner: `scripts/run_f03_five_parcel_remote_collection.py`  
> Machine summary: `test-data/cross-parcel-validation/f03_five_parcel_remote_collection_summary.json`

## Scope

Applied the CPER provenance-complete remote-evidence workflow to all five frozen parcels:

```text
XPV_CPER_001
XPV_KONZA_001
XPV_REYNOLDS_001
XPV_ORDWAY_001
XPV_KBS_MCSE_001
```

Authorized transition only:

```text
MAPPED_CANDIDATE → REMOTELY_SUPPORTED_CANDIDATE | remains MAPPED_CANDIDATE
```

Explicit non-goals for this collection:

- no FIELD_VERIFIED / field or operator evidence ingestion
- no F03 runtime rule changes
- no suitability thresholds
- no Cow-Calf / Sheep ranking
- no F06 / F07

## Deterministic sampling method

```text
selection_method: STABLE_CANDIDATE_ID_ORDER_MAX_3
```

Rules:

1. Load the frozen parcel F03 candidate inventory.
2. Sort by `(candidate_id, source_layer, source_feature_id, object_id)`.
3. Take at most **3** candidates.
4. Do **not** select by expected promotion, FCode seasonal class, or desired species outcome.

Implemented in `stable_sample_f03_candidates()` (`src/rangematch/f03_verification.py`).

## Evidence product

Presence confirmation uses:

| Field | Value |
|---|---|
| Provider | USDA Farm Service Agency |
| Product | NAIP orthoimagery |
| Access path | Microsoft Planetary Computer STAC (`naip` collection) |
| Local artifacts | GeoTIFF crop + STAC item JSON under each parcel `f03_remote_pilot/artifacts/` |

Required provenance fields match the CPER gate: provider, product, source URL/item ID, acquisition/review dates, reviewer/adapter id, candidate/parcel geometry hashes, artifact/STAC hashes, supported/unsupported claims, limitations, freshness.

## Aggregate counts

| Parcel | Available | Sampled | MAPPED | REMOTELY_SUPPORTED | FIELD_VERIFIED | Provenance-complete packages | Data-path failures | Conflicts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| XPV_CPER_001 | 9 | 3 | 1 | 2 | 0 | 3 | 0 | 0 |
| XPV_KONZA_001 | 34 | 3 | 3 | 0 | 0 | 3 | 0 | 0 |
| XPV_REYNOLDS_001 | 8 | 3 | 0 | 3 | 0 | 3 | 0 | 0 |
| XPV_ORDWAY_001 | 24 | 3 | 3 | 0 | 0 | 3 | 0 | 0 |
| XPV_KBS_MCSE_001 | 5 | 3 | 3 | 0 | 0 | 3 | 0 | 0 |
| **Total** | **80** | **15** | **10** | **5** | **0** | **15** | **0** | **0** |

Interpretation:

- **NHD-only** evidence remains `MAPPED_CANDIDATE`.
- **Provenance-complete NAIP presence** was obtained for all 15 sampled candidates.
- Promotion to `REMOTELY_SUPPORTED` still requires presence **plus** at least one approved remote attribute (here: NHD FCode seasonal class for stream permanence codes `46003` / `46006` / `46007`).
- Sampled waterbodies / unmapped FCodes (`39001`, `39004`, `46000`) correctly stayed `MAPPED_CANDIDATE` even with complete imagery provenance — not a data-path failure and not a land-suitability judgment.
- Remote evidence never produced `FIELD_VERIFIED_LIVESTOCK_WATER`.

## Parcel Factor state before / after

| Parcel | Before `input_quality_state` | Before verified count | After sampled remote levels | After parcel Factor state |
|---|---|---:|---|---|
| XPV_CPER_001 | MAPPED_CANDIDATES_ONLY | 0 | 1 MAPPED / 2 REMOTELY_SUPPORTED | MAPPED_CANDIDATES_ONLY |
| XPV_KONZA_001 | MAPPED_CANDIDATES_ONLY | 0 | 3 MAPPED | MAPPED_CANDIDATES_ONLY |
| XPV_REYNOLDS_001 | MAPPED_CANDIDATES_ONLY | 0 | 3 REMOTELY_SUPPORTED | MAPPED_CANDIDATES_ONLY |
| XPV_ORDWAY_001 | MAPPED_CANDIDATES_ONLY | 0 | 3 MAPPED | MAPPED_CANDIDATES_ONLY |
| XPV_KBS_MCSE_001 | MAPPED_CANDIDATES_ONLY | 0 | 3 MAPPED | MAPPED_CANDIDATES_ONLY |

Parcel Land Fact `input_quality_state` remains `MAPPED_CANDIDATES_ONLY` because `field_verified_count` stays `0`. Remote support is recorded in pilot results only; it does not rewrite frozen Land Facts or MatchResults in this step.

## Runtime behavior confirmation

```yaml
runtime_rules_changed: false
suitability_thresholds_added: false
cow_sheep_ranking_added: false
ranking_effect: NONE
field_verified_count_total: 0
geometries: FROZEN_UNCHANGED
```

## Source / provenance failures

No DEGRADED/FAILED imagery data-path statuses remained after the crop-read fix.

If retrieval fails in a future re-run:

- record `data_path_status: FAILED` or `DEGRADED`
- keep the candidate `MAPPED_CANDIDATE`
- do **not** treat failure as a land problem

## Per-parcel result directories

```text
test-data/cross-parcel-validation/XPV_CPER_001/f03_remote_pilot/
test-data/cross-parcel-validation/XPV_KONZA_001/f03_remote_pilot/
test-data/cross-parcel-validation/XPV_REYNOLDS_001/f03_remote_pilot/
test-data/cross-parcel-validation/XPV_ORDWAY_001/f03_remote_pilot/
test-data/cross-parcel-validation/XPV_KBS_MCSE_001/f03_remote_pilot/
```

Each contains `remote_pilot_result.json`, `artifacts/`, and `presence_provenance_<feature_id>.json` for promoted candidates.

## Collection gate

```yaml
five_parcel_remote_collection_gate: PASSED
reasons: []
```

Gate criteria satisfied:

- all five frozen parcels processed
- deterministic sampling recorded
- provenance requirements enforced for REMOTELY_SUPPORTED
- zero FIELD_VERIFIED
- runtime rules / ranking / suitability unchanged
- failures (if any) isolated as data-path status

## Next gate

Do **not** begin field/operator evidence ingestion until this remote-collection gate is accepted.  
Do **not** start F06 or F07 from this document.
