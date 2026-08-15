# Five-Factor Portfolio Review

> **Historical milestone record.** This review captured the system immediately after F05. The active competition scope is now frozen at F01–F08; current product status is defined in `CURRENT_SYSTEM_BASELINE.md`.

> Status: `REVIEW COMPLETE — F06 NOT SELECTED`  
> Date: 2026-08-08  
> Scope: F01–F05 after F05 freeze  
> Interactive summary: Cursor canvas `five-factor-portfolio-review`  
> Full suite at review: `63 passed`

## Frozen portfolio

```text
F01 Topography
F02 Herbaceous Resource
F03 Livestock Water
F04 Soil / Wetness / Ecological Site
F05 Climate and Drought Exposure
```

F05 authority stack (retained as the architectural lesson of the climate slice):

```text
NOAA/NCEI canonical Land Fact
ACIS secondary QA/fallback
Mireye point QA/context
Deterministic DQ interpretation
No invented suitability threshold
```

## 1. Do the five Factors cover the core MVP decision?

MVP questions (`MVP_SPEC.md`):

1. Is this parcel a plausible match for the intended grazing operation?
2. If weak, is another supported operation more appropriate?

| MVP need | Coverage today | Verdict |
|---|---|---|
| Terrain usability | F01 context | Covered as context |
| Forage opportunity | F02 model path; coverage unquantified | Partial — main biophysical gap |
| Livestock water | F03 candidates only | Partial — discovery without verification |
| Soil / site | F04 context | Covered as context |
| Climate / drought | F05 Land Fact + USDM QA | Covered as context; no threshold |
| Parcel size / layout | Not implemented | Gap |
| Flood hazard | Deferred; not F04/F05 | Gap |
| Road / legal access | Tier 3 backlog | Gap |
| Fencing / infrastructure | Tier 3 backlog | Gap |
| Cow vs Sheep preference | No ranking rule | Gap |

**Verdict:** The five Factors cover the **core biophysical screening context** for a grazing parcel. They do **not** yet cover the full MVP diligence surface or support `ADVANCE`. Spec still targets **8–12** shared Factors.

## 2. Which HOLD reasons most deserve the next investment?

CPER runtime (both Profiles):

```text
F01 CONTEXT_DEPENDENT
F02 NEEDS_VERIFICATION   ← coverage unquantified
F03 NEEDS_VERIFICATION   ← 9 candidates, 0 verified systems
F04 CONTEXT_DEPENDENT
F05 CONTEXT_DEPENDENT    ← fact present; no suitability rule
decision: HOLD / ranking_effect: NONE
```

Highest leverage to reduce HOLD pressure **without inventing thresholds**:

1. **Deepen F02** — quantify RAP eligible/masked/valid coverage; complete F02 final review.
2. **Deepen F03** — verified livestock-water system contract (operation, reliability, capacity, quality, legal access), not more NHD alone.
3. **Cross-parcel validation** — prove the five-Factor loop is reusable before adding F06.

Adding Flood alone will **not** exit HOLD while F02/F03 remain NEEDS_VERIFICATION and ranking stays NONE.

## 3. Have Cow-Calf and Sheep Profiles diverged enough?

| Layer | Status |
|---|---|
| Architecture | Peers by design |
| Requirements prose | Distinct ACCEPTED claims on F01/F03/F05; F02 CANDIDATE; F04 none |
| Runtime MatchResult | **Identical** signals and HOLD |
| Approved differential ranking rule | **None** |

**Verdict:** Dual Profiles are scientifically framed but **not yet productively differentiated**. Discovery mode cannot prefer one operation. Next knowledge work is a narrow, source-bound differential — or continue peers-with-HOLD until evidence supports ranking.

## 4. Buyer diligence questions still without a Factor

- Parcel acreage / configuration / adjacency
- Road and legal access
- Flood / FEMA hazard (explicitly not inside F05)
- Fencing and working infrastructure
- Verified forage quality (botany, palatability, nutrition) — diligence under F02, not a new Factor ID
- Verified water system facts — diligence under F03

## 5. Candidate F06 scoring (no selection)

| Candidate | Science / buyer value | Data readiness | Dev cost | HOLD impact | Standing |
|---|---|---|---|---|---|
| Flood / FEMA hazard | Useful diligence; isolate from F04/F05 | Not live-gated | Medium–High | Low alone | **Candidate only — no default** |
| Acreage & parcel configuration | High buyer relevance | Geometry-native | Low–Medium | Indirect | Strong if next is a Factor |
| Road / legal access | High diligence relevance | Mixed / legal | Medium | Diligence-shaped | Tier 3 style |
| Fencing / infrastructure | Operationally relevant | Weak remote certainty | High for verified claims | Low | Later |
| Deepen F02/F03 (not F06) | Highest MVP fit | Paths exist | Medium–High | **Highest** | Prefer before/parallel to F06 |

## 6. Cross-parcel validation vs more Factors

CPER is one engineering geometry. Before locking F06, the portfolio should prefer a short validation pass:

- second geometry via `replace-geometry` + regenerated Factors where feasible;
- at least one contrasting U.S. environment reference case;
- confirm HOLD language and Factor authority patterns still hold.

This reduces the risk of baking CPER-specific assumptions into the next Factor.

## Recommended sequence (still no F06 choice)

```text
1. Keep F05 closed / frozen
2. Cross-parcel / cross-environment validation of F01–F05  ← ACTIVE
3. Decide deepen-F02 and/or deepen-F03 vs new Factor
4. Only then select F06 from the candidate table
```

**Flood remains eligible and must not inherit priority from climate adjacency.**

## Decision recorded

- F05 milestone: **closed / frozen**
- F06: **not selected**
- Next locked goal: **F01–F05 Cross-Parcel and Cross-Environment Validation**
- Plan artifacts:
  - `docs/CROSS_PARCEL_VALIDATION_PLAN.md`
  - `docs/CROSS_PARCEL_SELECTION_CRITERIA.yaml`
  - `docs/CROSS_PARCEL_VALIDATION_RESULT_SCHEMA.yaml`
  - `test-data/cross-parcel-validation/parcel_registry.yaml`
