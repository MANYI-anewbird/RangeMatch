# Livestock Operating Profile Contract

> Status: `COMPETITION FREEZE — GENERIC US ADDRESS + CATTLE LOOP`  
> Date: 2026-08-13  
> Closed loop: `any confirmable US parcel + Cattle → Operating Profile → LLM ranch story → 3-page PDF`  
> Nambe role: default example, video path, regression fixture, standby PDF — not a code prerequisite  
> Does not modify: F01–F08 science, Engine labels, Sheep Lens

## Endorsement

This is an **additive product layer**, not a rebuild of RangeMatch.

```text
address / coordinates
  → Mireye locate
  → user confirms parcel
  → F01–F08 collect
  → Unified Output
  → Generic Evidence Packet          (already shipped)
  → Livestock Operating Profile      (this contract)
  → Cattle / Sheep Lens
  → LLM operating narrative
  → Validator
  → three-page Ranch Operating Brief
```

Mireye remains parcel entry and context. Federal adapters remain canonical land facts. The Packet remains the evidence object. The Operating Profile **interprets that evidence as a livestock-use investigation**, not as a suitability score.

This does **not** reopen the 2026-08-12 product lock. RangeMatch is still a buyer-side diligence agent. The central question stays:

> What kind of livestock operating space is this, and what should be verified before the next spend?

It is **not**:

> Is this land suitable for cattle or sheep, and how many animals will it carry?

Cattle / Sheep is a **lens on diligence attention**. It must never become a score, a ranking, or a buy/no-buy.

---

## Phase 0 freeze — competition must / must not

### Must ship in the competition build

- Feed preliminary portrait
- Drink preliminary portrait
- Move preliminary portrait
- Cattle / Sheep lens (attention and questions only)
- Continuous advisor narrative (not a five-unknown checklist)
- Three-page PDF
- Live path: any confirmable supported U.S. parcel can enter investigation and receive a validated Operating Profile **or** an explicit limited/failure outcome. Richness of Feed/Drink/Move is not guaranteed.
- Limited honest report when adapters fail or dependencies are missing
- No invented fences, facilities, wells, or stocking rates

### Must not ship

- Stocking rate or herd-size calculation
- Suitability or cattle/sheep scores
- Automatic fence / gate / corral detection
- Complete water-right, title, or easement opinions
- National ranch ranking
- Deal Room
- Computer-vision facility recognition
- Profitability prediction
- Expanding Contain / Manage into empty “UNKNOWN” home-page cards

### First usable loop (do this before Sheep and extra parcels)

```text
Nambe + Cattle → Operating Profile (Feed / Drink / Move)
  → LLM ranch story → Validator → three-page PDF
```

Sheep lens and two more live parcels come **after** that loop is honest.

---

## Authority

| Object | Source of truth | Operating Profile may |
|---|---|---|
| Parcel outline | User-confirmed geometry + hash | Reference only |
| Land facts / numbers | Unified Output | Copy, never invent |
| Water / road objects | Evidence Packet candidate objects | Copy, never mint IDs |
| Evidence state | Packet observations / coverage | Copy |
| Action candidates + first-action lock | Deterministic action policy | Display; must not reorder |
| Mireye rows | Live contexts | Context only; never parcel facts |
| Operating statements | This projector | Emit structured `statement_type` only; no free prose |
| Species emphasis | Reviewed Knowledge Cards | Change questions and attention, not facts |
| Buyer prose | LLM after Validator gates | Narrate Profile + Packet; no new facts |
| HOLD / Engine | Appendix only | Never on pages 1–2 |

LLM does **not** project the Operating Profile.

---

## Profile object

Schema (Phase 1): `docs/schemas/livestock_operating_profile.schema.json`  
Module (Phase 1): `src/rangematch/livestock_operating_profile.py`

```json
{
  "schema_version": "RANGEMATCH_LIVESTOCK_OPERATING_PROFILE@0.1.0",
  "packet_hash": "",
  "unified_output_hash": "",
  "profile_hash": "",
  "parcel_ref": {},
  "species_lens": "CATTLE",
  "available_domains": ["FEED", "DRINK", "MOVE"],
  "operating_domains": {
    "feed": { "statements": [] },
    "drink": { "statements": [] },
    "move": { "statements": [] }
  },
  "operating_thesis_inputs": [],
  "domain_attention_order": ["DRINK", "MOVE", "FEED"],
  "action_execution_order": [],
  "field_visit_purpose": {},
  "provenance": {}
}
```

`species_lens`: `CATTLE` | `SHEEP` (Phase 1 emits `CATTLE` only).

`parcel_ref` must include `geometry_hash`, `geometry_id` / `parcel_id`, `confirmation_status`, and `policy_scope`. Generic runs stay `GENERIC_MINIMAL`. CPER engineering geometry / `build_cper_demo_policy` must not enter a Generic Profile.

Contain and Manage are **omitted** from `operating_domains` and `available_domains` until they have statements. The Profile may record empty inventory only as kitchen/action metadata. **LLM Workbench receives `profile_for_llm()` — populated domains only.** Empty Contain/Manage must never be sent as “fence unknown / facility unknown”.

### Statement record (structured; no prose)

Projector and LLM must not free-write the claim. Prose is rendered later from `statement_type`. Numbers stay on the observation; the Profile only holds refs.

```json
{
  "statement_id": "FEED_MODELED_PRODUCTION_SNAPSHOT",
  "domain": "FEED",
  "statement_type": "MODELED_PRODUCTION_SNAPSHOT",
  "value_refs": ["OBS_RAP_PROD"],
  "evidence_refs": ["OBS_RAP_PROD"],
  "object_refs": [],
  "qualifiers": [],
  "evidence_state": "MODELED",
  "spatial_scope": "PARCEL",
  "allowed_inferences": ["MODELED_VEGETATION_CONTEXT"],
  "prohibited_inferences": [
    "AVAILABLE_FORAGE",
    "CARRYING_CAPACITY",
    "HERD_SIZE"
  ],
  "displayable": true,
  "narrative_role": "PORTRAIT_INPUT"
}
```

`allowed_inferences` / `prohibited_inferences` are **fixed per `statement_type`**. Allowed and prohibited must not overlap. Dangerous inferences (stocking, usable water, legal access, suitability, absence-from-failure) must never appear in `allowed_inferences`.

`narrative_role` is one of `PORTRAIT_INPUT` | `ACTION_INPUT` | `GUARDRAIL_ONLY`. Only `PORTRAIT_INPUT` enters `operating_thesis_inputs`. `DRAWABLE_WATER_NONE` and `WATER_INVENTORY_UNAVAILABLE` are `GUARDRAIL_ONLY` (workbench may see them; Ranch Portrait must not). `NO_MAPPED_HYDROGRAPHY_LEADS` is `ACTION_INPUT` and is not “no water”.

`domain_attention_order` ranks **operating themes from Packet bottleneck rank** (Water → legal access / road → forage). It does not change Packet `execution_order` or `allowed_first_actions`. LLM must not reorder it. Nambe: `["DRINK", "MOVE", "FEED"]` while first action remains `ACTION_ACCESS_DOCUMENTS`.

`statement_type` is bound to a domain. `MODELED_PRODUCTION_SNAPSHOT` cannot live in Drink even if `domain` is rewritten.

`field_visit_purpose` reuses the existing visit-state authority (`VISIT_DEPENDS_ON_DOCUMENT` / `VISIT_PURPOSE_DEFINED` / `NO_DEFINED_VISIT_PURPOSE_YET`). No free-text purpose. Without drawable objects, purpose is category-level: no route, pin, or named water point.

```json
{
  "visit_state": "VISIT_DEPENDS_ON_DOCUMENT",
  "bound_action_ids": ["ACTION_ACCESS_DOCUMENTS", "ACTION_WATER_LOCATION_OR_INVENTORY"],
  "purpose_type": "WATER_INVENTORY_AFTER_ACCESS_DOCUMENT",
  "object_refs": []
}
```

Rules:

1. No new parcel facts. No hand-copied canonical numbers inside the Profile.
2. Every statement cites at least one canonical `evidence_ref` (observation id, candidate id, or `geometry_hash`).
3. Delete that evidence → the statement must disappear.
4. `SOURCE_UNAVAILABLE` / timeout / `DEPENDENCY_MISSING` means the layer was not obtained — not absence.
5. F03 failed or empty mapped search is **not** “no water”.
6. No listing claims → no fences, tanks, wells, or facilities.
7. Empty domains are not `available_domains` and are not passed to the LLM.
8. Single-year RAP / climate → no trend, stability, or resilience `statement_type`.
9. Phase 3 Move may add compactness, multipart/fragmentation, road relationship, and drawable-water spatial distribution. It must not emit livestock-to-water distance, terrain zones without slope distribution, gates, traversability, or paddocks. Geometry hash change forces recompute.

---

## Domain v0 (Feed / Drink / Move only)

Contain and Manage stay empty unless a later slice adds reviewed evidence. Do not staff five domains at once.

### Feed

Inputs: RAP production and cover if present, precipitation, soil context, coverage, time period.

May say: modeled herbaceous snapshot; cover signal if present; that herd size is not permitted.

Must not say: available forage, carrying capacity, “ready for cattle”, multi-year resilience.

### Drink

Inputs: NHD candidates, drawable precision, listing water claims if any, remote/field verification status.

May say: N mapped hydrography **investigation leads**; how many are drawable for a field route; none are livestock-water infrastructure until verified.

Must not say: “30 drinkers”, year-round supply, legal right, well/tank invention.

### Move

Inputs: confirmed geometry, area, slope (distribution only if present), elevation if present, drawable water geometry, mapped road relationship, fragmentation / validity.

May say: terrain character, compactness, fragmentation, road-to-boundary relationship, drawable-water distribution, whether terrain deserves field attention.

Must not say: walking distance to water as an operating fact, gate/entrance, legal access, pin-precision from `AREA_ONLY`.

Spatial derivation (Phase 3) is deterministic and recomputed when `geometry_hash` changes. Module: `src/rangematch/livestock_movement.py`.

| Derivation | Allowed labels | Forbidden leap |
|---|---|---|
| Compactness | compact / elongated / fragmented-multipart | good/bad ranch shape |
| Terrain | predominantly gentle / mixed / concentrated steeper zones — only with distribution | median-only invention of “zones” |
| Drawable water | distributed / concentrated / boundary-adjacent / no drawable distribution | livestock drinking distance |
| Road | touches boundary / crosses / nearby not touching / not obtained | legal access, gate, entrance |

---

## Species Lens (Phase 4, after Nambe+Cattle loop)

Four to six Demo-approved cards, not a national knowledge base. Suggested ids:

- `CATTLE_WATER_DISTRIBUTION_001`
- `CATTLE_HANDLING_CONTEXT_001`
- `CATTLE_MOVEMENT_CONTEXT_001`
- `SHEEP_FENCE_CONTEXT_001`
- `SHEEP_PREDATOR_CONTEXT_001`
- `SHEEP_SHELTER_CONTEXT_001`

Each card keeps the existing Knowledge Card rails (source, publisher, dates, reviewer, jurisdiction, species scope, allowed/prohibited use, version, content hash).

Lens **may** change: which domain is emphasized, which question is asked first, what a field inventory should record, how a broker/seller ask is worded.

Lens **must not** change: land facts, numbers, candidate objects, deterministic execution order, purchase conclusion, stocking, suitability.

Same Packet + Cattle vs Sheep: identical numbers and objects; different attention and questions; no `Cattle score` / `Sheep score`; no “this tract is better for sheep”.

---

## LLM and Validator (Phase 5)

Workbench becomes:

```text
Evidence Packet
+ Livestock Operating Profile
+ Species Knowledge Cards
+ Deterministic Action Policy
→ LLM Workbench
```

LLM task: one operating thesis; how Feed / Drink / Move jointly shape livestock use; species-lens emphasis; what actually decides a field trip; the next diligence spend.

Suggested narrative fields (buyer-facing):

```json
{
  "operating_thesis": "",
  "ranch_reading": "",
  "system_story": {
    "feed_and_water": "",
    "movement_and_management": "",
    "species_lens": ""
  },
  "attention_pivot": {},
  "conditional_path": {},
  "client_summary": ""
}
```

`evidence_chain` stays for the Validator only. It does not print on the buyer pages.

Reject: invented fence/well/tank/gate/barn; NHD as drinking water; RAP as available forage; herd size; species ranking; legal-access conclusion; Knowledge Card as a parcel fact; `SOURCE_UNAVAILABLE` rewritten as “there is none”.

One controlled LLM repair is allowed. Second failure → deterministic fallback. Live miss never becomes a CPER fixture.

---

## Three-page Ranch Operating Brief (Phase 6)

| Page | Question | Must not show |
|---|---|---|
| 1 How This Ranch Reads | What kind of livestock operating space is this? | Factor ids, unknown lists, HOLD |
| 2 How Livestock Would Use It | Feed → Water → Movement → Management as one story | Five-column “we don’t know” |
| 3 Before You Spend More | Who to ask, what the visit may do, what not to repurchase, copy-ready messages, folded kitchen | Buy/no-buy |

Page 1 may include a simple map and the species lens label. Page 2 may show vegetation/water/terrain/road **as evidence-scoped layers**, not as facilities. Page 3 keeps the current diligence advantage.

Gate 6 (human, 60 seconds, non-author): at least 4/5 —

1. What kind of ranch space is this, roughly?  
2. How do cattle vs sheep change attention?  
3. What is the largest operating question?  
4. What is the next spend?  
5. Did the report decide buy/no-buy? (correct answer: no)

---

## Demo UI (Phase 7)

Inputs: Place, Species (Cattle / Sheep), Run Agent.

Progress labels (buyer language):

```text
Confirm parcel
Build land picture
Trace feed and water
Read livestock movement
Apply species lens
Write ranch brief
Validate report
```

Do not put `F01`, `F02`, `Generic Packet`, `HOLD`, `Engine`, or `Adapter` on the first screen. Those stay in the technical kitchen.

Results: in-page three pages, PDF download, map, copy-ready messages, expandable kitchen, `LIVE_LLM` vs fallback only in technical detail.

---

## Live acceptance (Phase 8) — after Nambe+Cattle

Three fixed real parcels, each × Cattle / Sheep / partial adapter / LLM success / LLM fallback:

1. Nambe (already on the live path)  
2. A drier western tract with sparse water objects  
3. A wetter / more vegetated tract  

Each report must change with the parcel, differ by lens, and show no Nambe/CPER boilerplate, no fixture leak, no invented facilities, no truncated PDF, no hung Agent on timeout.

---

## Gates (summary)

| Gate | Pass condition |
|---|---|
| 1 Profile integrity | Evidence retract → statement retract; F03 fail ≠ no water; no listing ≠ facilities; no CPER policy on Generic Profile; unique `statement_id`; observation/geometry mutation changes `profile_hash` and invalidates old Move refs; `statement_type` binds domain; inference policy + no dangerous allowed; refs (`value_refs`, `object_refs`, thesis, parcel_ref, confirmation, policy_scope) must resolve; visit objects must be drawable; `GUARDRAIL_ONLY` excluded from thesis; empty domains excluded from LLM view and `domain_attention_order`; attention follows bottleneck rank; `action_execution_order` matches Packet; hashes present; tests must not overwrite the Nambe fixture |
| 2 Fixtures | Nambe live packet, CPER fixture, no mapped water, F03 timeout, no listing, non-drawable water ids, invalid geometry, missing adapter dependency |
| 3 Movement | No pin from `AREA_ONLY`; no NHD-as-drinker; no road-as-gate; recompute on geometry change; no distance/distribution without drawable objects |
| 4 Lens | Same Packet, Cattle vs Sheep: identical facts/objects; different questions; no scores |
| 5 LLM | Reject list above; one repair then fallback; no silent CPER swap |
| 6 Brief | 60-second 4/5 human test |
| 7 Live trio | Three real parcels, both lenses, partial failure, LLM success and fallback |

---

## Execution order (strict)

1. This contract (Phase 0) — **done when this file is the freeze**  
2. Schema + Generic Packet → Operating Profile projector  
3. Feed / Drink / Move projection  
4. Minimal movement spatial derivation  
5. Species Lens cards (after Nambe+Cattle narrative works)  
6. LLM workbench + narrative  
7. Validator adversarial tests  
8. Three-page PDF rewrite  
9. Demo UI  
10. Three-parcel live acceptance  
11. Competition packaging (one-pager, video, start scripts)

Do not start: facility CV, large knowledge base, stocking, multi-state production claims, cattle/sheep scores, F01–F08 rewrite.

---

## Relationship to shipped work

Keep:

- Mireye-first confirm gate  
- F01–F08 live collect with fail-soft  
- Generic Evidence Packet  
- Deterministic action policy  
- Validator-before-PDF  
- `GET /v1/advisor/runs/{id}/report-bundle` and buyer-brief PDF routes  

The current diligence Brief remains valid until the Ranch Operating Brief Validator passes. Do not delete Packet or kitchen; fold them under page 3.

---

## Definition of done for this coding slice (Gate 1 seal + Phase 3 movement)

- Gate 1 semantic reference tests green; fixture compare-only (`scripts/write_nambe_cattle_operating_profile.py` is the only writer)  
- Shared `derive_authoritative_visit_purpose(packet)` used by Brief and Profile  
- `domain_attention_order` from bottleneck rank  
- `GUARDRAIL_ONLY` / `ACTION_INPUT` excluded from thesis  
- `src/rangematch/livestock_movement.py`: compactness, fragmentation, drawable-water distribution, recompute on geometry change  
- No LLM, PDF, F01–F08 rewrite, or Sheep Lens
