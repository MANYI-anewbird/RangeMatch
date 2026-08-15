# Advisor Insight and Reasoning Contract

> **Superseded as the current LLM product contract on 2026-08-14.** Retained for earlier safety rationale. Current authority is `RANGEMATCH_PRODUCT_AND_AGENT_CODE_FLOW.md`: interpretation may be provisional and directional, while physical facts remain strict.

> Status: `IMPLEMENTABLE_PRODUCT_CONTRACT` — P0 review 2026-08-12 incorporated; not `LOCKED` until schema + CPER fixtures exist  
> Date: 2026-08-12  
> Product authority: this document for LLM reasoning; `AGENT_THREE_PAGE_WORKFLOW_CONTRACT.md` for the three-page buyer shape  
> Engineering plan: `ADVISOR_AGENT_IMPLEMENTATION_PLAN.md`  
> Science freeze: F01–F08, Unified Output, and Engine are unchanged  
> Explicit non-scope: suitability, carrying capacity, stocking rate, species ranking, buy/no-buy, raw adapter payloads, kitchen-as-prompt, wide-open prompts

This document replaces the older Advisor workflow that treated the LLM as a **language overlay** on a fully written brief. The LLM is a **constrained reasoning brain**. The deterministic system is the **fact base, safety rail, and audit ledger**.

P0 closures in this revision: action-order authority vs Packet `execution_order`; machine `depends_on` / `withdraw_when`; Mireye `context_refs`; Knowledge Card provenance; structure validated before buyer prose is rendered.

## 1. Product definition

> RangeMatch is an evidence-constrained ranch buyer’s advisor. The technical system first establishes parcel facts, hard rails, and an allowed action set. The LLM then uses a projected workbench plus reviewed livestock-diligence knowledge to produce **structured insights**. The user-facing report is rendered from insights that already passed the Validator.

```text
AdvisorLLMWorkbench     = what the model may see
Structured insights     = what the Validator checks
Rendered buyer report   = what ordinary users read
Evidence kitchen        = audit / judges / developers; default collapsed
```

The kitchen is **not** the LLM context. The full Buyer Evidence Packet is **not** dumped into the prompt. The LLM never receives raw adapter JSON, Engine `HOLD` as a headline, or Factor IDs as buyer copy.

Ordinary users do not need HTTP, agenda, hashes, or internal step status. The Challenge Demo may still show **How RangeMatch reached this report** (including live Mireye statuses) so judges can see the Agent run. That shell is not the buyer product.

## 2. System split

```text
API / Mireye / F01–F08
  what this tract measured

Deterministic rules and this contract
  what must never change or be inferred

LLM + reviewed knowledge cards
  structured insights: combination meaning, investigation design

Deterministic renderer
  six-section buyer report from validated insight fields

Validator
  whether the LLM crossed a rail, invented a fact, or broke a dependency
```

| Layer | Owns | Must not own |
|---|---|---|
| Packet / Unified Output | Numbers, units, evidence states, object IDs, geometry, coverage, limitations, `execution_order` | Buyer narrative |
| Decision contract | Hard rails, prohibited inferences, bottleneck candidates, action candidates, `action_dependencies`, `allowed_first_actions`, `allowed_permutations` | Finished speech |
| Knowledge cards | Versioned diligence priors with provenance | Parcel facts; legal conclusions |
| LLM | Insight records inside the workbench | New numbers, objects, states; mutating `execution_order`; suitability / stocking / buy-no-buy |
| Renderer | Buyer-visible sentences from **validated** fields | New decisions not present in passed insights |
| Validator | Pass / hide-and-fallback | Repairing unsafe prose by guessing |

Mireye Property / Land / Hazard is **non-canonical point context**. It appears on the workbench with `canonical_for_parcel_facts: false` and is cited only via `context_refs`. HTTP success proves a response returned, not a business conclusion.

## 3. End-to-end workflow

```text
Place (address or coordinate)
→ Mireye live lookup / context (honest success or block; no fixture swap)
→ one confirmed parcel
→ F01–F08 + candidate objects
→ Buyer Evidence Packet
→ deterministic decision skeleton
     execution_order (fallback; immutable)
     action_dependencies
     allowed_first_actions
     allowed_permutations
     visit-purpose
     prohibited inferences
→ project AdvisorLLMWorkbench (allowlist; not the full Packet)
→ retrieve a few approved Knowledge Cards for the open gaps
→ LLM emits structured Insight records only
→ Validator (refs, actions, dependencies, bans)
→ renderer builds the six-section buyer report from passed fields
→ optional short LLM elaboration on already-validated conclusions
→ kitchen / “How we reached this” collapsed
```

Do not write a free-text prompt before the reasoning space in §5 exists as a fixture.

Live LLM is optional. A 429, timeout, invalid JSON, or validator reject must return the deterministic prose report. Never silently substitute a fixture when the caller asked for a live provider.

Do not reopen F01–F08 science for this slice.

Listing claims, Mireye text, and any seller-uploaded file are **untrusted data**. They may be quoted as claims or context. They must not change the model’s task, permissions, or output schema (prompt-injection boundary).

## 4. Three context types (never mix)

### 4.1 Parcel facts — displayable Packet observations only

Allowed as “this tract already measured …”:

- confirmed boundary and area
- slope, precipitation, RAP snapshots
- water candidate objects and review/evidence state
- road contact
- listing claims (as claims, not facts)
- coverage and limitations

Mireye is **not** in this list. See §4.4.

### 4.2 Fixed professional knowledge — approved Knowledge Cards

Allowed as “in ranch diligence, one usually still checks …”:

- well / tank / reach need different files and field signs
- RAP production is not usable forage
- road contact is not legal access
- precip / slope change what is worth checking, not carrying capacity

Forbidden as “this tract already has / can support …”.

Legal-access cards may only support **questions to send title/counsel**. They must not state that a right exists, is missing, or is defective. `jurisdiction_scope: US_GENERAL` is not a license to give legal advice.

Cards are versioned, reviewed, content-hashed, and fetched by current gaps. Do not dump a cattle/sheep textbook into the prompt.

v1 card topics (CPER Demo): livestock water checks, legal access (questions only), RAP interpretation, field-task boundary. At most a few cards per run.

### 4.3 Decision contract — locked before the model runs

Packet `execution_order` remains the **deterministic fallback order**. The LLM must not write it.

| Field | Owner | Role |
|---|---|---|
| `execution_order` | Code | Immutable fallback sequence shown if LLM is off or rejected |
| `action_dependencies` | Code | Hard precedence. A listed action cannot precede its prerequisites |
| `allowed_first_actions` | Code | The only action IDs that may be step 1 |
| `allowed_permutations` | Code | Optional explicit list of legal `llm_recommended_order` tuples |
| `llm_recommended_order` | LLM | Order among candidates that satisfies the three fields above |

CPER v1 (must be encoded in the workbench, not only in prose):

```json
{
  "allowed_first_actions": ["ACTION_ACCESS_DOCUMENTS"],
  "action_dependencies": {
    "ACTION_WATER_FIELD_CATEGORY": ["ACTION_ACCESS_DOCUMENTS"]
  }
}
```

If `allowed_permutations` is present, `llm_recommended_order` must be one of those tuples. If it is absent, the Validator derives legality from `allowed_first_actions` + `action_dependencies` + the candidate set.

The LLM may explain why a legal permutation is better than `execution_order`. It may not invent a new action type, drop a dependency, or pick a first action outside `allowed_first_actions`.

Validator conflict rule:

```text
execution_order              → Packet / fallback UI; LLM cannot mutate
llm_recommended_order        → buyer “do today” only if it passed rails
if they differ               → both are retained; report uses recommended
                               order; kitchen shows the fallback order
if recommended is illegal    → reject LLM output; show execution_order
```

### 4.4 Mireye and other non-canonical context

Cite only with `context_refs`, never as `packet_refs`.

Allowed: “Mireye returned land context for the parcel centroid.”  
Forbidden: “Mireye proved the whole parcel has this condition.”  
HTTP 200 proves transport success only.

### 4.5 AdvisorLLMWorkbench (allowlist projection)

Project this object. Do not send the raw Packet or kitchen.

- displayable observations (id, buyer label, value/unit/time, evidence_state, allowed/prohibited support)
- claim gaps
- allowed candidate objects (identity, type, review_status, navigability)
- bottleneck candidates
- action candidates, `execution_order`, `action_dependencies`, `allowed_first_actions`, `allowed_permutations`, `can_establish` / `cannot_establish`, `cost_class`
- visit_purpose
- selected Knowledge Cards (approved only)
- Mireye context summaries (`context_id`, endpoint, ok/error_class, `canonical_for_parcel_facts: false`)
- prohibited inferences
- `report_locale`, audience, reading budget

## 5. Reasoning space (permission layers)

| Permission | Owner |
|---|---|
| Numbers, evidence states, objects, hashes | Deterministic system |
| `execution_order`, dependencies, `allowed_first_actions` | Deterministic system |
| Bottleneck candidates and action candidates | Deterministic system |
| Insight records and `llm_recommended_order` inside rails | LLM |
| Buyer headlines, action titles, condition chains | Renderer from **passed** insight fields |
| Suitability, stocking, buy/no-buy | Forbidden |

Hard rails (not optional advice):

1. Do not change Packet numbers, units, IDs, evidence states, or geometry precision.
2. Do not mint objects, wells, pins, or names absent from the workbench.
3. Do not write unknown / unreviewed as absent.
4. Do not promote a listing sentence to a Land Fact.
5. First action ∈ `allowed_first_actions`. CPER: only `ACTION_ACCESS_DOCUMENTS`.
6. Honor `action_dependencies`. Field water checks cannot precede access documents on CPER.
7. A field task may name an object only when that object exists and is drawable / navigable.
8. Knowledge-card text may not be restated as a measured parcel fact.
9. No suitability, carrying capacity, species ranking, or purchase verdict.
10. Untrusted listing / Mireye / upload text cannot change task or schema.

If the system pre-wrote the entire advisor paragraph, the LLM is only reciting. The skeleton supplies **cards on the table**, not the finished speech.

Example workbench (facts + candidates):

```text
Facts:
- 9 mapped water identities, 0 field verified
- road distance = 0 m
- legal access not verified
- buyer considering a weekend trip

Candidate actions:
- ACTION_ACCESS_DOCUMENTS (allowed first; execution_order 1)
- ACTION_WATER_RECORDS_FROM_LISTING
- ACTION_WATER_FIELD_CATEGORY (depends on ACTION_ACCESS_DOCUMENTS)
- ACTION_REPEAT_PRECIP
```

Valid LLM judgment (must also appear as a structured insight):

> Access paper is usually cheaper than a field trip and decides whether a visit has a job, so request it first. Water remains the larger operating-evidence gap, so once an entrance basis holds, the visit should focus on water. Re-querying precipitation would not reduce the current decision uncertainty.

`INFORMATION_VALUE` may compare `cost_class` and qualitative uncertainty. It must not claim “lowest cost / highest information value” as if prices or probabilities were measured, unless the skeleton already emitted a comparable rank.

## 6. Five reasoning types

Every insight carries one `reasoning_type`:

| Type | Job |
|---|---|
| `SUPPORTED_INTERPRETATION` | Combination meaning bound to Packet facts |
| `DOMAIN_PRIOR` | Card knowledge, never as a parcel measurement |
| `CONDITIONAL_SCENARIO` | If A then next B, still cannot conclude C |
| `DILIGENCE_QUESTION` | Professional question; bind to an existing object or stay conditional |
| `INFORMATION_VALUE` | Which **allowed** action is worth doing first, using `cost_class` and stated uncertainty — not invented prices |

The buyer UI does not show these codes. The Validator does.

A well question requires a well object, or it must be a `CONDITIONAL_SCENARIO` (“if a well is found on site, then request a well log”). A well log still cannot prove current yield, quality, operating condition, or legal right.

`rejected_actions` may only cite IDs in the candidate set. `ACTION_REPEAT_PRECIP` is legal only if that action is a candidate. If the set has one action, `rejected_actions` is optional. If it has two or more, an `INFORMATION_VALUE` insight must include `considered_actions` and at least one rejected or deferred candidate.

## 7. Knowledge Card schema (v1)

```json
{
  "knowledge_id": "WATER_WELL_DILIGENCE_001",
  "topic": "livestock_water",
  "statement": "A well log may support existence and construction of a well; it does not establish current yield, water quality, operating condition, or legal right.",
  "source_id": "SRC_WELL_LOG_LIMITS_001",
  "source_title": "…",
  "source_url_or_citation": "…",
  "source_publisher": "…",
  "source_date": "…",
  "reviewed_by": "…",
  "reviewed_at": "…",
  "review_basis": "statement checked against source; no parcel-specific claim",
  "effective_jurisdictions": ["US_GENERAL"],
  "species_scope": ["cattle", "sheep"],
  "review_status": "APPROVED",
  "allowed_use": ["diligence_question", "conditional_reasoning"],
  "prohibited_use": ["parcel_fact", "suitability_verdict", "legal_conclusion"],
  "content_hash": "sha256:…",
  "expires_or_review_after": "2027-08-12",
  "version": "1.0"
}
```

`allowed_use` / `prohibited_use` are enforced in code. Cards missing provenance, `content_hash`, reviewer, or `review_status: APPROVED` never enter the workbench.

Legal-access cards: `allowed_use` includes `diligence_question` only for title/counsel questions. `legal_conclusion` is always prohibited.

## 8. Insight record (hidden structure)

The model emits insight records. It does **not** emit a free-standing decision letter as the sole carrier of the recommendation.

```json
{
  "insight_id": "INSIGHT_ACCESS_FIRST_001",
  "recommendation": "Request access documents before booking the trip.",
  "reasoning_type": "INFORMATION_VALUE",
  "packet_refs": ["OBS_ROAD", "BOTTLENECK_WATER_EVIDENCE"],
  "context_refs": [],
  "knowledge_refs": ["LEGAL_ACCESS_DILIGENCE_001"],
  "llm_recommended_order": [
    "ACTION_ACCESS_DOCUMENTS",
    "ACTION_WATER_FIELD_CATEGORY"
  ],
  "considered_actions": [
    "ACTION_ACCESS_DOCUMENTS",
    "ACTION_WATER_FIELD_CATEGORY",
    "ACTION_REPEAT_PRECIP"
  ],
  "rejected_actions": [
    {
      "action_id": "ACTION_REPEAT_PRECIP",
      "reason": "does_not_reduce_current_decision_uncertainty"
    }
  ],
  "conditions": [
    {
      "if_action_id": "ACTION_ACCESS_DOCUMENTS",
      "if_result": "ENTRANCE_BASIS_SUPPORTED",
      "then_action_id": "ACTION_WATER_FIELD_CATEGORY",
      "still_cannot_establish": [
        "year_round_stock_water",
        "legal_access_without_documents"
      ]
    }
  ]
}
```

`depends_on` and `withdraw_when` are **computed by the Validator** from `packet_refs`, `context_refs`, `knowledge_refs`, and action IDs. The model must not author a natural-language `withdrawal_rule`.

```json
{
  "depends_on": {
    "packet_refs": ["OBS_ROAD", "BOTTLENECK_WATER_EVIDENCE"],
    "action_refs": ["ACTION_ACCESS_DOCUMENTS", "ACTION_WATER_FIELD_CATEGORY"],
    "knowledge_refs": ["LEGAL_ACCESS_DILIGENCE_001"],
    "context_refs": []
  },
  "withdraw_when": [
    { "ref": "OBS_ROAD", "events": ["REMOVED", "FAILED", "DOWNGRADED"] },
    { "ref": "ACTION_ACCESS_DOCUMENTS", "events": ["REMOVED"] }
  ]
}
```

Insights that are not pure `DOMAIN_PRIOR` fail without `packet_refs` or `context_refs` as appropriate. A Mireye-only sentence fails without `context_refs`. A Land Fact sentence that cites only `context_refs` fails.

`if` / `then` in conditions must be enumerated IDs or result enums, not free text, before they may drive the rendered report.

## 9. What the buyer reads

Renderer builds the report from **passed** insight fields. Headline, recommended first action, `llm_recommended_order`, and condition chains are copied from those fields (localized). Free prose may elaborate; it must not introduce a new first action, a new object, or a new verdict.

Default locale is `report_locale` on the workbench (Challenge Demo: `en-US` or `zh-CN`, one per run). Audience default: ordinary buyer; Challenge one-pager payer line remains buyer-side broker.

Reading budget:

- one-line recommendation: ≤ 140 characters
- first screen (sections 1–3): short letter, not a memo
- jargon: first use in buyer words (e.g. “recorded entrance,” not “TIGER”)

Sections:

1. **One-line recommendation** — from `recommendation` / first of `llm_recommended_order`.
2. **Why** — from `INFORMATION_VALUE` + Packet-backed facts.
3. **Where listing speech jumps** — from claim-gap insights.
4. **What to do now** — copy-ready messages bound to candidate action IDs.
5. **If the result changes** — from structured `conditions`.
6. **Professional reminders** — from `DILIGENCE_QUESTION` / `DOMAIN_PRIOR` cards.

Voice: a senior buyer-side ranch advisor. Not a data table, not a Factor recap, not “we did not find.”

Technical board lives under **How RangeMatch reached this report** (default collapsed).

## 10. Validator

Failure hides the LLM report and shows the deterministic fallback (`execution_order`). Never fall back to a HOLD cover page.

Reject when any of these is true:

- a number, unit, ID, or evidence state does not match the Packet
- an object, pin, or well is named that is not on the workbench
- a Knowledge Card is written as a measured parcel fact
- a recommended action is outside the candidate set
- `llm_recommended_order` violates `allowed_first_actions`, `action_dependencies`, or `allowed_permutations`
- the model mutated `execution_order`
- `rejected_actions` cites a non-candidate ID
- suitability, stocking, species rank, or buy/no-buy appears
- claim language is treated as a Land Fact
- a Mireye citation uses `packet_refs` instead of `context_refs`, or treats HTTP success as a parcel-wide proof
- kitchen vocabulary (F01–F08, HOLD, adapter codes) appears in rendered buyer copy
- a cited Packet, context, or card ID is missing
- a `depends_on` ref was removed/failed/downgraded and the insight was not withdrawn
- rendered headline / first action / condition disagrees with passed insight fields
- listing or Mireye text attempted to change task or schema
- a transport / Mireye / provider failure is dressed as success

Do **not** use a second LLM to judge whether prose “means the same thing.” Bind those decisions to fields, then render.

## 11. Deterministic fallback

If the LLM is off, missing, 429, or rejected, render the **same six sections** from Packet `execution_order`, claim gaps, `can_establish` / `cannot_establish`, and visit-purpose.

Fallback is a readable advisor letter, not chips. CPER fallback first action is `ACTION_ACCESS_DOCUMENTS`.

Challenge Demo today may stay LLM-off. Do not take a live OpenAI dependency to record the competition video.

## 12. Delivery order

Do this sequence. Do not invert “write prompt” ahead of “lock the space.”

| Step | Work | Exit |
|---|---|---|
| 0 | Keep Challenge Demo honest: live Mireye, no fixture swap, LLM optional | Running Demo bar |
| 1 | Keep this file as implementable (P0 closed). Do not mark `LOCKED` until step 5 | This file |
| 2 | Schema: `AdvisorLLMWorkbench`, Knowledge Card, Insight record, Packet `action_policy` | DONE: `docs/schemas/advisor_*.schema.json`; packet `action_policy` |
| 3 | Three provisional CPER trial cards (not an official KB) | DONE: legal access, livestock water, RAP |
| 4 | CPER fixture: workbench + hand-authored insights that pass | DONE |
| 5 | Adversarial six-pack: only the valid insight is accepted | DONE in `tests/test_advisor_llm.py` |
| 6 | Renderer: six-section buyer report from validated fields | DONE: `advisor_report.py` |
| 7 | Wire LLM to emit insight records; FIXTURE default; live miss ≠ fixture | DONE: `POST /v1/advisor/runs/{id}/buyer-explanation` |
| 8 | Live provider gate: 429 / timeout / invalid JSON → fallback; no silent fixture | Provenance visible |
| 9 | Only then: more cards, generic policy, real listings | Separate gates |

## 13. Packet / schema delta (required before LLM wiring)

Add to the Packet or a sibling decision-skeleton object (do not silently overload `execution_order`):

```text
action_dependencies        map<action_id, action_id[]>
allowed_first_actions      action_id[]
allowed_permutations       action_id[][]   (optional)
```

Insight / workbench schemas (new files):

```text
docs/schemas/advisor_llm_workbench.schema.json
docs/schemas/advisor_knowledge_card.schema.json
docs/schemas/advisor_insight_record.schema.json
```

Existing `execution_order` (1..3) stays required on Packet actions as the fallback sequence.

## 14. Documentation precedence for this slice

1. This file — LLM reasoning space, workbench, cards, insights, validator, delivery order.
2. `AGENT_THREE_PAGE_WORKFLOW_CONTRACT.md` — three-page buyer shape and Packet rules; LLM steps defer here.
3. `ADVISOR_AGENT_IMPLEMENTATION_PLAN.md` — gates and engineering queue.
4. Packet and new insight schemas — machine contract.
5. Frozen F01–F08 / Unified Output / Engine — science.
6. `LLM_AUTHORITY_AND_REPORT_SPEC.md` — legacy HOLD-era report; does not authorize Advisor overlay behavior.

If an implementation convenience conflicts with this contract, change the convenience.
