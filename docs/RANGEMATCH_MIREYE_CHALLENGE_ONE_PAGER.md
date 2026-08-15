# RangeMatch — Understand a parcel's natural foundation for cattle.

RangeMatch confirms a parcel through Mireye, builds a five-domain Natural Cattle Profile, combines it with reviewed cattle-environment knowledge and buyer context, asks the question most likely to change the interpretation, and exports a validated two-page Natural Cattle Foundation report.

## Problem

Ranch buyers and buyer-side advisors are pushed by listing language — “excellent year-round water,” “easy county-road access,” “ready for cattle” — to fly, hire title, or spend field time before anyone has checked whether the public evidence supports those lines. The usual waste is not “the land is bad.” It is a misordered cheque: a weekend trip to confirm facts already on the map, or a forage snapshot read as a stocking plan.

## How the Agent works

```text
Free-form U.S. address or coordinates
→ Mireye parcel entry
→ judge confirms one polygon
→ Mireye Environmental Profile
→ deterministic Gap Detector + only necessary supplements
→ Combined Evidence + Natural Cattle Profile
→ Deal Context v1
→ Initial Operating Conclusion + one high-value question
→ buyer answer → Deal Context v2 → revised conclusion
→ validated natural-foundation interpretation
→ two-page Natural Cattle Foundation report
```

Physical facts stay deterministic. DeepSeek may write provisional operating language and chat answers, but cannot invent wells, fences, stocking rates, legal access, or buy/no-buy. Malformed LLM output fails soft to a validated deterministic conclusion.

## Mireye + external evidence

**Mireye anchors the physical parcel.** It turns an address or coordinate into a traceable parcel/context and the investigation entry point.

RangeMatch then combines that parcel with federal land evidence (terrain, vegetation context, hydrography identities, soils, climate, road contact) and optional listing-claim forensics. F01–F08 are not “all from Mireye.” Mireye is the parcel grounding layer; the other sources supply the land evidence the Agent compares to seller speech.

## Reason / Decide / Act

- **Reason:** “Excellent water” goes past mapped hydrography. “Easy access” goes past road contact. “Ready for cattle” goes past a modeled growth snapshot.
- **Decide:** Form a provisional cattle operating conclusion, name the controlling constraint, and pick one high-information question.
- **Act:** After the buyer answers, show what changed and export the two-page report from the latest validated interpretation.

## Who pays

**Buyer-side ranch brokers, land advisors, and serious ranch buyers pay for RangeMatch to avoid wasted site visits and misordered professional diligence.**

The primary payer is the buyer-side ranch broker / land advisor, who repeats this decision across listings. The individual buyer is the beneficiary and second payer.

RangeMatch does not charge for a suitability score. It charges for not spending the next cheque in the wrong order.

## Demo scope and safety boundary

The demo route `/advisor-demo` accepts free-form U.S. street address or `lat,lng`. Failed lookups stay failed (`PARCEL_NOT_FOUND` vs `PARCEL_SERVICE_UNAVAILABLE`). The Agent never silently substitutes Nambe or CPER. Verified Nambe is an explicit Demo opt-in that creates a new run.

Each successful run exposes `run_id`, generation time, `geometry_hash`, `packet_hash`, `operating_profile_hash`, and `deal_context_version`. DeepSeek failure still yields a deterministic conclusion and Snapshot. Chat cannot mutate Packet, Deal Context, or Conclusion.

The Agent does **not** decide suitability, stocking rate, species ranking, legal access, usable water, or buy/no-buy. It does not compare cattle vs sheep, detect fences or facilities, or claim a complete livestock operating assessment or national production validation. Movement is labeled **movement context** — not a full livestock-movement analysis.

## Two-minute recording script

Record only at `http://127.0.0.1:5273/advisor-demo`. Do not open 5173 or 5174.

1. **0:00–0:15 Pain + product.** Buyer-side advisors need to know what to verify before travel. One sentence: parcel-grounded cattle operating diligence, not a score.
2. **0:15–0:35 Place.** Enter Nambe (or use the verified Nambe link). Confirm the Mireye polygon.
3. **0:35–0:55 Collect.** Show Mireye Profile → identified gaps → only planned supplements.
4. **0:55–1:15 Initial conclusion.** Show the Natural Cattle Foundation view and the one Agent question.
5. **1:15–1:35 Answer.** Choose seasonal grazing (or equivalent). Show Before / Your answer / What changed / Now.
6. **1:35–2:00 Report.** Download the two-page Natural Cattle Foundation report. Point to Mireye as the primary physical-world layer, the updated `deal_context_version`, and matching Profile/Packet hashes.

## Links

- Demo: `http://127.0.0.1:5273/advisor-demo`
- Product contract: `docs/RANGEMATCH_PRODUCT_AND_AGENT_CODE_FLOW.md`
- Repo README: `/README.md`
- Snapshot API: `GET /v1/advisor/runs/{id}/cattle-operating-snapshot.pdf`
- Video: _add URL at submission_
