# RangeMatch Four-Factor Demo Acceptance and Reusability Validation

> Status: `PASSED — TIER 2 AUTHORIZED`
> Language: English
> Scope: F01–F04 demo closure only
> Last updated: 2026-08-07

## 1. Distinction

| State | Meaning |
|---|---|
| Demo closure implementation | Complete: fixtures, engine, constrained explanation, HTML/JSON, CLI |
| Demo acceptance | Complete for the internal engineering acceptance surface; formal product UI/UX is deferred |

No new Factor work, including F05 / Tier 2, starts until this acceptance gate is checked.

## 2. Locked sequence

```text
No new Factors
→ Human HTML review
→ Confirm the six sections are understandable
→ Formal Factor Freeze Gate recorded
→ Verify geometry-replacement path
→ Check Demo Acceptance
→ Then decide Tier 2 (Climate/Drought first)
```

## 3. Product surface under review

Open:

```bash
PYTHONPATH=src python3 -m rangematch.cli demo-closure \
  test-data/land-profiles/land_profile_cper_001.json
```

Then open `test-data/land-profiles/land_profile_cper_001_demo_closure.html`.

Required sections:

1. Parcel Summary
2. Factor Evidence
3. Operation Comparison
4. Unknowns
5. Diligence Actions
6. Source Trace

## 4. Human acceptance checklist

- [x] Page clearly states `HOLD ≠ unsuitable`
- [x] `CONTEXT_DEPENDENT` is explained as context/evidence-quality, not a positive suitability score
- [x] Cow-Calf and Sheep are shown as peers with no ranking
- [x] Unknowns are easy to find
- [x] Sources can be traced back to Factors
- [x] Explanation text only restates the MatchResult
- [x] Engineering test geometry is not described as a real purchasable ranch
- [x] Page information density is acceptable for an internal engineering acceptance surface; this is not the final product UI/UX
- [x] After geometry replacement, geometry hash / provenance / MatchResult input hash change together

## 5. Geometry replacement validation

Minimal command:

```bash
PYTHONPATH=src python3 -m rangematch.cli replace-geometry \
  test-data/land-profiles/land_profile_cper_001.json \
  test-data/engineering_test_geometry_cper_002.geojson \
  --output /tmp/land_profile_cper_replaced.json
```

Expected behavior:

- new geometry id and reference are written;
- previous parcel-derived Factor evidence is invalidated;
- re-evaluation changes `input_sha256`;
- no live API calls are required for this validation path.

## 6. Freeze Gate reference

The canonical stop condition for every Factor is:

`docs/FACTOR_FREEZE_GATE.yaml`

## 7. Acceptance decision

- [x] Demo Acceptance passed
- [x] Reusability validated via geometry replacement
- [x] Tier 2 authorized to begin with Climate/Drought

Acceptance completed on 2026-08-07. The project may now proceed to:

> **Tier 2 — Climate/Drought**

The current HTML remains an internal validation surface. Responsive layout, visual polish, interaction design, and the formal product prototype are intentionally deferred to the product UI/UX phase.
