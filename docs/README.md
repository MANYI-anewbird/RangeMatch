# RangeMatch Documentation

> **Judges / new readers: start here.**  
> Last updated: 2026-08-15  
> Product authority: Mireye-first cattle natural-environment advisor

## Read in this order

| Order | Document | Why |
|---|---|---|
| 1 | [`../README.md`](../README.md) | How to run the Demo locally |
| 2 | [`RANGEMATCH_MIREYE_CHALLENGE_ONE_PAGER.md`](RANGEMATCH_MIREYE_CHALLENGE_ONE_PAGER.md) | One-page competition pitch |
| 3 | [`RANGEMATCH_PRODUCT_AND_AGENT_CODE_FLOW.md`](RANGEMATCH_PRODUCT_AND_AGENT_CODE_FLOW.md) | **Canonical** product, Agent flow, gates, definition of done |
| 4 | [`NATURAL_CATTLE_FOUNDATION_REPORT_TEMPLATE.md`](NATURAL_CATTLE_FOUNDATION_REPORT_TEMPLATE.md) | Buyer report content contract (variable-length narrative + new-page Appendix) |
| 5 | [`TWO_BRAIN_ADVISOR_CHAT_CONTRACT.md`](TWO_BRAIN_ADVISOR_CHAT_CONTRACT.md) | Open-ended grounded chat: place materials + cattle knowledge |
| 6 | [`../web/README.md`](../web/README.md) | Advisor Demo UI notes |

Everything else below supports implementation detail, frozen science, or archive. It must not contradict document 3.

## Product in one paragraph

RangeMatch confirms a parcel with Mireye, builds a parcel-specific physical-world profile, fills material evidence gaps with targeted public sources, and combines that evidence with reviewed cattle knowledge. A grounded LLM then produces a directional natural-foundation assessment and supports open-ended conversation about that specific property. The advisor narrative may span multiple pages; the evidence appendix always begins on a new page.

**Is:** parcel-confirmed cattle natural-environment foundation (Terrain, Forage, Water, Climate, Soil) with honest gaps, one refining question, variable-length report, open-ended grounded chat.

**Is not:** suitability score, stocking calculator, title/access opinion, buy/no-buy, or cattle-vs-sheep ranking.

## Current product contracts (keep open)

Mireye-first Advisor path:

- [`ADVISOR_PARCEL_CONFIRMATION_GATE.md`](ADVISOR_PARCEL_CONFIRMATION_GATE.md) — confirm one polygon before investigation
- [`ADVISOR_GENERIC_EVIDENCE_PACKET.md`](ADVISOR_GENERIC_EVIDENCE_PACKET.md) — combined environmental evidence rules
- [`ADVISOR_NAMBE_REPORT_LOOP.md`](ADVISOR_NAMBE_REPORT_LOOP.md) — Nambe verified Demo loop (opt-in fixture, not silent fallback)
- [`mireye_cattle_environment_field_manifest.json`](mireye_cattle_environment_field_manifest.json) — Mireye field catalog for cattle Profile
- [`schemas/`](schemas/) — JSON Schemas for Profile, Gap Plan, Interpretation, Chat, Deal Context, PDF bundles
- [`DOCUMENTATION_GOVERNANCE.md`](DOCUMENTATION_GOVERNANCE.md) — language + traceability rules
- [`PACKAGING_AND_DELIVERY_STRATEGY.md`](PACKAGING_AND_DELIVERY_STRATEGY.md)

Parcel / adapter (still used by runtime):

- [`PARCEL_RESOLUTION_CONTRACT.md`](PARCEL_RESOLUTION_CONTRACT.md)
- [`MIREYE_LIVE_PARCEL_RESOLVER_CONTRACT.md`](MIREYE_LIVE_PARCEL_RESOLVER_CONTRACT.md)
- [`MIREYE_PROTOTYPE_ADAPTER_CONTRACTS.md`](MIREYE_PROTOTYPE_ADAPTER_CONTRACTS.md)
- [`ONE_PARCEL_API_SPEC.md`](ONE_PARCEL_API_SPEC.md) — HTTP surfaces including Advisor Demo routes
- [`F01_F08_UNIFIED_OUTPUT_CONTRACT.md`](F01_F08_UNIFIED_OUTPUT_CONTRACT.md) — Factor output shape **when** a supplement runs

## Legacy runtime / science references (not current product contracts)

These remain useful for Factor science and older investigation APIs. They must **not** be read as the competition Demo product definition:

- [`AGENT_ORCHESTRATION_SPEC.md`](AGENT_ORCHESTRATION_SPEC.md)
- [`PLANNER_EXECUTOR_SPEC.md`](PLANNER_EXECUTOR_SPEC.md)
- [`PLANNER_ROUTING_SPEC.md`](PLANNER_ROUTING_SPEC.md)
- [`archive/product-history/LLM_AUTHORITY_AND_REPORT_SPEC.md`](archive/product-history/LLM_AUTHORITY_AND_REPORT_SPEC.md) — superseded Constrained Intent + Engine buyer-report authority

## Archive

See [`archive/README.md`](archive/README.md) for superseded product narratives and dated gate records.
