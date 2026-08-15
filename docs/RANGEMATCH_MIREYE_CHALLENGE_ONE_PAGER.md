# RangeMatch — Understand a parcel's natural foundation for cattle.

RangeMatch confirms a parcel through Mireye (primary Physical World Layer), builds a five-domain Natural Cattle Profile, combines it with reviewed cattle-environment knowledge and buyer context, asks the question most likely to change the interpretation, exports a Natural Cattle Foundation report whose advisor narrative may span multiple pages (Appendix always starts on a new page), and supports open-ended grounded chat about that specific property.

## Problem

Before a ranch buyer or buyer-side advisor spends travel or deeper diligence, they need an honest reading of what the **confirmed parcel's natural environment** implies for cattle use — terrain, forage context, water context, climate/hazard exposure, and soils — without inventing wells, fences, stocking rates, or legal access.

The waste RangeMatch targets is **misreading public natural evidence**: treating a modeled vegetation snapshot as available forage, treating mapped hydrography as proven drinkers, or flying before anyone has assembled a parcel-grounded natural picture.

## How the Agent works

```text
Free-form U.S. address or coordinates
→ Mireye parcel entry (primary Physical World Layer)
→ judge confirms one polygon
→ Mireye Environmental Profile
→ deterministic Gap Detector + only necessary supplements
→ Combined Evidence + Natural Cattle Profile
→ Deal Context v1
→ Natural Foundation Interpretation + one high-value question
→ buyer answer → Deal Context v2 → revised interpretation
→ Natural Cattle Foundation PDF (narrative pages + Appendix on a new page)
→ open-ended two-brain grounded chat (read-only)
```

Physical facts stay deterministic. DeepSeek may write directional natural-foundation language and chat answers, but cannot invent wells, fences, stocking rates, legal access, or buy/no-buy. Malformed LLM output fails soft to validated deterministic prose for **this** parcel.

## Mireye + external evidence

**Mireye is the primary Physical World Layer.** It confirms the parcel geometry and supplies the main environmental profile used for cattle natural-foundation screening.

A Gap Detector then calls RangeMatch supplements only where Mireye cannot cover a needed capability. F01–F08 are not “all from Mireye,” and they are not a mandatory full Factor tour. F06 geometry is always-on; F07 is Appendix-only and cannot control the natural-foundation judgment.

## Reason / Decide / Act

- **Reason:** Assemble Terrain / Forage / Water / Climate / Soil evidence for the confirmed parcel and keep spatial semantics honest (point values cannot pretend to be parcel-wide).
- **Decide:** Form a directional natural-foundation view, name the controlling natural factor, and ask one high-information environmental question.
- **Act:** After the buyer answers, show what changed, export the report from the latest validated interpretation, and allow open-ended grounded chat over the same evidence + cattle knowledge.

## Who pays

**Buyer-side ranch brokers, land advisors, and serious ranch buyers** use RangeMatch to screen a parcel's natural foundation before deeper field work.

The primary payer is the buyer-side ranch broker / land advisor. The individual buyer is the beneficiary and second payer.

RangeMatch does not charge for a suitability score. It charges for a parcel-grounded natural reading that stays honest about gaps.

## Demo scope and safety boundary

The demo route `/advisor-demo` accepts free-form U.S. street address or `lat,lng`. Failed lookups stay failed (`PARCEL_NOT_FOUND` vs `PARCEL_SERVICE_UNAVAILABLE`). The Agent never silently substitutes Nambe or CPER. Verified Nambe is an explicit Demo opt-in that creates a new run.

Each successful run exposes `run_id`, generation time, `geometry_hash`, packet/profile hashes, and `deal_context_version`. DeepSeek failure still yields a deterministic natural-foundation path for this parcel. Chat cannot mutate Packet, Profile, Interpretation, or Deal Context.

The Agent does **not** decide suitability, stocking rate, species ranking, legal access, usable water capacity, or buy/no-buy. It does not compare cattle vs sheep, detect fences or facilities, or claim a complete livestock operating assessment.

## Two-minute recording script

Record only at `http://127.0.0.1:5273/advisor-demo`. Do not open 5173 or 5174.

1. **0:00–0:15 Pain + product.** Before travel, understand the parcel's natural foundation for cattle. One sentence: Mireye-first physical world + cattle knowledge → directional advisor, not a score.
2. **0:15–0:35 Place.** Enter Nambe (or use the verified Nambe link). Confirm the Mireye polygon.
3. **0:35–0:55 Collect.** Show Mireye Profile → identified gaps → only planned supplements.
4. **0:55–1:15 Initial view.** Show the Natural Cattle Foundation judgment and the one Agent question.
5. **1:15–1:35 Answer.** Choose seasonal grazing (or equivalent). Show what changed.
6. **1:35–2:00 Report + chat.** Download the report (point to variable narrative length and Appendix on a new page). Optionally open grounded chat and ask one forage/water question grounded in this run.

## Links

- Demo: `http://127.0.0.1:5273/advisor-demo`
- Product contract: `docs/RANGEMATCH_PRODUCT_AND_AGENT_CODE_FLOW.md`
- Chat contract: `docs/TWO_BRAIN_ADVISOR_CHAT_CONTRACT.md`
- Repo README: `/README.md`
- Report PDF: `GET /v1/advisor/runs/{id}/cattle-operating-snapshot.pdf`
- Video: _add URL at submission_
