# RangeMatch Buyer Dashboard and Scoring Spec

Status: `IMPLEMENTED_V0_1_PRESENTATION_CONTRACT`

Current report implementation: `BUYER_DECISION_REPORT_V2` (see `docs/CURRENT_SYSTEM_BASELINE.md`).

## Product hierarchy

The buyer experience has three layers:

1. **Decision Dashboard** — parcel, climate, vegetation, water, access, operation fit, and evidence confidence.
2. **Easy-reading Report** — parcel-specific facts, evidence-limited Cow-Calf/Sheep comparison, decision-changing unknowns, and what to verify next.
3. **Appendices** — complete Land Fact/source table, provenance, Agent trace, methodology, and dynamic policy/land-rights findings.

F01–F08 remain canonical backend Factors. Buyer-facing labels group them into land systems and must not replace, mutate, or duplicate canonical Factor results.

## Operation fit

Operation fit and Evidence Confidence are separate concepts.

- Operation fit may only display a directional band when the deterministic Matching Engine has an approved directional rule.
- `HOLD` is displayed as `EVIDENCE INCOMPLETE`, never as a numeric score or an unsuitable verdict.
- `ranking_permitted: false` prohibits a best-use winner, ordinal rank, or visual treatment implying one.
- The LLM may explain an Engine band but may not create or modify it.

Until operation-specific directional rules are approved, v0.1 displays the Engine decision label and `Evidence incomplete` rather than fabricated Moderate/Strong values.

In buyer-facing prose and comparison cards, Engine `HOLD` is rendered as **More evidence needed**. Raw `HOLD` remains available in the appendix and API.

## Evidence confidence

Evidence Confidence is a presentation summary of data readiness, not biological suitability or probability of success.

For v0.1 it uses the eight canonical Factor signals:

- `UNKNOWN` or `MISSING`: no readiness credit.
- `NEEDS_VERIFICATION`: partial readiness.
- `CONTEXT_DEPENDENT`: reviewed context available.
- It must never override the Engine decision.

The UI displays qualitative bands only: `Low`, `Moderate`, or `High`. Technical details must identify the contributing Factor states.

## Evidence semantics

Every buyer-visible fact is labeled as one of:

- `MEASURED FACT`
- `MODELED CONTEXT`
- `FIELD VERIFICATION REQUIRED`
- `SOURCE UNAVAILABLE`

Missing seasonal observations must display `Not collected`; annual precipitation cannot be expanded into invented seasonal values.

## Dashboard content

- Confirmed parcel map and approximate area
- Current deterministic decision
- Cow-Calf and Sheep peer results
- Evidence Confidence
- Annual/seasonal climate availability
- Herbaceous, shrub, and tree context
- Mapped versus field-verified livestock water
- Terrain and mapped-road physical context
- Three prioritized diligence actions

## Readable decision report content

1. Executive Summary
2. Key Unknowns
3. Parcel facts table with value, unit, meaning, and evidence state
4. Cow-Calf vs. Sheep evidence matrix; if no differential rule exists, state that the evidence cannot distinguish them
5. Three decision-changing diligence actions
6. Current official-source guidance, only scoped locally when jurisdiction is resolved
7. Methodology and limitations

Generic Property/Land/Hazards prose must not replace parcel-specific values. Missing values are shown as `Not collected` and grouped as gaps rather than occupying empty dashboard cards.

## Appendix contract

Appendix A contains every available value, unit, spatial/temporal semantics, source, coverage, confidence, date, algorithm version, and limitation.

Appendix B contains dynamic policy and land-rights findings with jurisdiction, retrieval date, official source URL, applicability, and verification status. Dynamic findings are non-canonical and are not F09.

## Prohibited presentation

- No invented 0–100 suitability score
- No Cow-Calf/Sheep ranking when `ranking_permitted: false`
- No point value presented as parcel aggregate
- No mapped water presented as usable livestock water
- No mapped road presented as legal access
- No modeled production presented as available forage, carrying capacity, or stocking rate
- No LLM-authored scientific rule, threshold, or legal conclusion
