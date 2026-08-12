# RangeMatch — Know what to verify before you visit or spend.

An AI buyer’s agent that combines Mireye parcel intelligence with federal land evidence and listing claims to decide the next ranch-property diligence action.

## Problem

Ranch buyers and buyer-side advisors are pushed by listing language — “excellent year-round water,” “easy county-road access,” “ready for cattle” — to fly, hire title, or spend field time before anyone has checked whether the public evidence supports those lines. The usual waste is not “the land is bad.” It is a misordered cheque: a weekend trip to confirm facts already on the map, or a forage snapshot read as a stocking plan.

## How the Agent works

```text
Mireye parcel / physical-world context
→ federal land evidence + listing claims
→ Buyer Evidence Packet
→ claim-to-evidence gaps
→ bottleneck + action order
→ three-page Decision Brief
→ Validator
```

The Agent reasons over claims versus evidence, decides the cheapest next diligence step, and acts by producing copy-ready messages. Numbers, ranks, objects, and visit-purpose state are deterministic. A live LLM is optional and cannot change facts.

## Mireye + external evidence

**Mireye anchors the physical parcel.** It turns an address or coordinate into a traceable parcel/context and the investigation entry point.

RangeMatch then combines that parcel with:

- USGS 3DEP terrain
- RAP vegetation snapshots
- USGS NHD hydrography identities
- SSURGO/SDA soils
- NOAA climate
- TIGER road contact
- listing-claim forensics

F01–F08 are not “all from Mireye.” Mireye is the parcel grounding layer; the other sources supply the land evidence the Agent compares to seller speech.

## Reason / Decide / Act

- **Reason:** “Excellent water” goes past mapped hydrography. “Easy access” goes past road contact. “Ready for cattle” goes past a modeled growth snapshot.
- **Decide:** Livestock-water use is the larger evidence gap. Access documents are the first action because they are cheaper than a flight.
- **Act:** Copy-ready messages for title/counsel, listing broker, partner, and a geometry-safe field task. No invented pins.

Visit purpose on the CPER demo is `VISIT_DEPENDS_ON_DOCUMENT`: the trip depends on access paper; if the entrance basis holds, the visit has a defined purpose.

## Who pays

**Buyer-side ranch brokers, land advisors, and serious ranch buyers pay for RangeMatch to avoid wasted site visits and misordered professional diligence.**

The primary payer is the buyer-side ranch broker / land advisor, who repeats this decision across listings. The individual buyer is the beneficiary and second payer.

RangeMatch does not charge for a suitability score. It charges for not spending the next cheque in the wrong order.

## Demo scope and safety boundary

The demo route `/advisor-demo` starts empty. The judge enters a place (CPER demo chip) and clicks **Run investigation**. The API calls live Mireye (`/v1/lookup` + `/v1/fetch`) with `allow_network=true`, then executes the CPER agenda, Packet, Brief, and Validator. Each run shows `run_id`, generation time, packet hash, and the real Mireye lookup/context statuses. Failed Mireye steps are not dressed as fixture success. CPER is an engineering test geometry, not a purchasable ranch and not a real listing. Listing claims stay fixed for the Challenge Demo. F01–F08 stay on the CPER land profile.

The Agent does **not** decide suitability, stocking rate, species ranking, legal access, usable water, or buy/no-buy. OpenAI is not required. Kitchen / Engine HOLD stays in the appendix. 3 mapped water areas can be drawn; 6 identities stay inventory-only.

## Two-minute recording script

Record only at `http://127.0.0.1:5273/advisor-demo`. Do not open 5173 or 5174.

1. **0:00–0:12 Who pays.** Title, then the payer line: buyer-side ranch brokers and land advisors deciding what to verify before the client travels or spends.
2. **0:12–0:28 Run the Agent.** Show the empty brief, select CPER, click **Run investigation**. Name **Call Mireye** as it hits live HTTP. Point to lookup / Property / Land / Hazard statuses (success or the real block), then this run’s `run_id` and packet hash.
3. **0:28–0:48 Reason.** Three listing lines outrun the public evidence. Do not walk F01–F08 or the source chips.
4. **0:48–1:05 Decide.** Water is the largest evidence gap; access paper is the first action because it is cheaper than a flight.
5. **1:05–1:25 Act.** Copy the title/counsel message, paste it into a notes window, then copy the listing-broker message.
6. **1:25–1:40 Visit purpose.** The trip depends on access documentation; if the entrance basis holds, the visit has a defined job.
7. **1:40–1:52 Kitchen.** Open once: 3 drawable water areas, 6 inventory-only identities. No invented pins.
8. **1:52–2:00 Close.** RangeMatch does not score the ranch. It orders the next cheque.

After the take, confirm the pasted title text matches the on-screen message. If copy fails, the button must say `Copy failed — select the message and copy`.

## Links

- Demo: `http://127.0.0.1:5273/advisor-demo`
- Product contract: `docs/AGENT_THREE_PAGE_WORKFLOW_CONTRACT.md`
- Repo README: `/README.md`
- Video: _add URL at submission_
