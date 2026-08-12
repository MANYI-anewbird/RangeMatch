# Agent Three-Page Workflow Contract

> Status: `LOCKED_PRODUCT_CONTRACT` — product locked; packet projection and graph Validator in progress
> Note: The three-page *product* contract is locked. A hand-written fixture is not a safe Agent
> contract. Packet numbers must come from Unified Output; the Validator must resolve the
> reference graph, `1..n` ranks, real packet hash, and geometry-aware navigation language
> before the LLM may write page one. Page three is still a kitchen pointer, not a finished appendix.
> Date: 2026-08-12
> Authority: This document is the upstream product contract for the three-page buyer shape.
> LLM reasoning space, Knowledge Cards, and insight validation live in
> `ADVISOR_INSIGHT_AND_REASONING_CONTRACT.md`.
> The three-page Advisor Brief defines the workflow. The workflow does not define a
> data-collection exercise that later hopes to fill a report.
> Science freeze: F01–F08, Engine, and Unified Output remain authoritative back-end
> ledgers. This contract changes orchestration and buyer output, not Factor rules.

## 1. Inversion rule

Define the action the buyer must be able to take after reading the brief. Then
derive the evidence, reasoning, and tool calls required to support that action.

If a fetch, inference, or tool step cannot improve:

1. page-one advisor judgment,
2. a page-two sendable or executable action, or
3. page-three evidence integrity,

it is not a default Agent step in this slice.

The Agent does not “collect as much data as possible.” It:

```text
review listing claims (when present)
→ locate evidence gaps
→ choose the highest-information next action
→ generate copy-ready messages
→ retain a complete evidence basis
```

## 2. Deliverable the Agent must produce

Every completed run that has a confirmed parcel delivers three layers:

```text
Page 1 — Advisor judgment
Page 2 — Actions the user can send or do today
Page 3 — Map, numbers, sources, Engine, technical audit (collapsed)
```

Page 1 is not a scientific report. Page 2 is not an appendix. Page 3 is the kitchen.

A generated PDF or HTML file is not the success event. Success is: the user copies
a sentence, sends a request, creates a visit task, or explicitly pauses a spend.

## 3. Recommended Agent workflow

```text
User submits listing text and/or address or coordinate
        ↓
Identify the current transaction decision (default: next diligence spend, not purchase)
        ↓
Confirm exactly one parcel
        ↓
Extract 1–3 material listing claims (paste or fixture until PDF parse exists)
        ↓
Plan minimum-necessary desktop calls (F01–F08 remain the default scan;
  each call must name the claim or action it serves)
        ↓
Run F01–F08 and candidate-object investigation
        ↓
Build Buyer Evidence Packet (LLM workbench; never raw adapter payloads)
        ↓
Claim-to-Evidence gaps (auditable; not a finding that the seller lied)
        ↓
Code emits bottleneck candidates and an allowed action set
        ↓
Retrieve approved Knowledge Cards for the open gaps
        ↓
LLM writes the buyer report (insight records + natural-language prose)
        ↓
Validator checks pages, citations, rails, and insight records
        ↓
Show the buyer report, or the deterministic six-section fallback
        ↓
Later: new evidence re-enters the packet (Deal Room; not this slice)
```

Do not emit a persuasive brief against an unconfirmed boundary. The only allowed
output in that state is: confirm the correct tract; further parcel calls would mislead.

## 4. Decision context (Step 1)

The first Agent question is not cattle versus sheep. It is the live transaction
question, for example:

- Is a weekend visit worth it?
- Should title review be paid first?
- Should the listing side be asked for water records?
- Should counsel review an easement?
- Should additional spend pause?
- Is there a field visit with a defined target?

```json
{
  "decision_context": {
    "current_stage": "PRE_VISIT",
    "decision_deadline": "THIS_WEEK",
    "candidate_actions": [
      "REQUEST_DOCUMENTS",
      "SCHEDULE_FIELD_VISIT",
      "ENGAGE_PROFESSIONAL",
      "PAUSE_ADDITIONAL_SPEND"
    ],
    "user_question": "Should I fly to inspect this parcel this weekend?"
  }
}
```

If the user is silent, default:

> The current goal is to choose the next diligence spend, not to decide a purchase.

Cow-Calf / Sheep remain optional intended-use context. They do not become a
suitability ranking and do not drive the first-page headline.

## 5. Parcel lock (Step 2)

Before any persuasive language:

- parse address or coordinate;
- return candidate parcels;
- require user confirmation of one boundary;
- lock `parcel_id` and `geometry_hash`;
- stop the full brief if confirmation fails.

Current locators: address or coordinate/pin. Listing URL, APN, and brochure OCR
are later. A run with no listing is valid; then page one is “what the land is
already telling you,” not claim-gap theater.

`parcels_per_run` remains 1.

## 6. Listing claims (Step 3)

Extract only claims that can change diligence order. Do not summarize the whole PDF.

v1 without PDF parse: user pastes 1–3 claims, or the CPER demo uses the frozen
fixture in `test-data/advisor/cper_listing_claims_fixture.json`.

Each claim is `SELLER_CLAIMED` until independently supported. The Agent must not
promote a listing sentence to a Land Fact.

## 7. Minimum-necessary data (Step 4)

F01–F08 remain the default desktop scan so the kitchen stays complete. The planner
must still record, for each adapter call, which claim or action it serves.

| User question or claim | Desktop evidence it serves |
|---|---|
| Excellent water | NHD candidates, object inventory, existing remote review |
| Easy access | TIGER road relationship; legal access still requires documents |
| Productive pasture | RAP cover/production and coverage state |
| Gentle terrain | 3DEP slope/elevation |
| Stable climate | NOAA normals; history is a later enhancement |
| Fly this weekend? | The above plus action cost and dependency |

A successful API response is not coverage, not product scope, not a verified
object, and not a field/legal fact.

## 8. Buyer Evidence Packet (Step 5)

Schema: `docs/schemas/buyer_evidence_packet.schema.json`.

The LLM receives this packet, the decision skeleton, and a few approved
Knowledge Cards only. It does not receive raw adapter JSON, the Page 3 kitchen,
Engine `HOLD` as a headline instruction, or Factor IDs as buyer copy. See
`ADVISOR_INSIGHT_AND_REASONING_CONTRACT.md`.

Every observation carries: id, value/unit/time, evidence_state, spatial meaning,
source, allowed support, prohibited support.

Candidate objects reuse source IDs (`USGS_NHDPLUS_HR:{layer}:{feature_id}`).
Never mint `WATER_CANDIDATE_*`. Carry `review_status` (`UNREVIEWED` | `SAMPLED`)
in addition to `evidence_state`. Until objects are projected, page-two field
actions stay category-level.

## 9. Claim-to-Evidence gap (Step 6)

This is the core intermediate product when listing claims exist.

```text
supported_portion  = what current evidence actually reaches
unsupported_portion = where listing language goes past that evidence
```

“看穿吹牛” must appear in the system as an auditable gap, not as an LLM judgment
that the seller is dishonest.

## 10. Bottlenecks versus actions (Steps 7–8)

Code emits at most three bottleneck **candidates** (it may label the largest
operating-evidence gap). Code emits an allowed action **candidate** set. Each
action states `can_establish` and `cannot_establish`, executor, cost class,
dependencies, and success/failure transition.

Bottleneck size and action order are independent. Water may be the larger
operating-evidence gap while access documents are the better first spend.

LLM reasoning space is defined in `ADVISOR_INSIGHT_AND_REASONING_CONTRACT.md`.
`execution_order` is the immutable deterministic fallback. The model may emit
`llm_recommended_order` only if it satisfies `allowed_first_actions`,
`action_dependencies`, and optional `allowed_permutations`. It must cite facts,
knowledge cards, considered actions, and rejected (in-set) actions. It must not
invent actions, objects, pins, or names absent from the workbench, and must not
mutate `execution_order`. CPER v1: only `ACTION_ACCESS_DOCUMENTS` may be first;
field water checks depend on that action.

Conflict rule: illegal recommended order → reject LLM, show `execution_order`.
Legal recommended order that differs from fallback → buyer report uses
recommended; kitchen retains fallback. See
`ADVISOR_INSIGHT_AND_REASONING_CONTRACT.md` §4.3.

## 11. LLM role (Step 9)

The LLM is a constrained reasoning brain, not a language overlay. Authority:
`ADVISOR_INSIGHT_AND_REASONING_CONTRACT.md`.

Input: `AdvisorLLMWorkbench` (allowlist projection) + a few approved Knowledge
Cards. Not the kitchen, not the raw Packet.
Output: structured insight records. The buyer letter is **rendered from
insights that already passed the Validator**. Free prose may elaborate only.

Allowed reasoning: combination meaning, reviewed livestock-diligence priors,
information value among candidates (no invented prices), if-A-then-B-still-not-C,
sendable questions and tasks.

Forbidden: changing numbers, object IDs, evidence states, or
`can_establish` / `cannot_establish`; actions outside the candidate set;
suitability; carrying capacity; species ranking; purchase advice;
“not verified” → “absent”; listing claim → fact; bbox/flowline → pin;
writing a Knowledge Card as a measured parcel fact.

Buyer-facing pages are continuous advisor prose. Ranks, hashes, and status
codes stay in the kitchen / “How we reached this report.”

## 12. Validator (Step 10)

The Validator checks all three pages **and** every insight record. Failure
hides unsafe LLM prose and falls back to deterministic six-section prose. It
must not fall back to a HOLD cover page.

Page 1: natural-language recommendation; no buy/sell verdict; no suitability /
stocking / species rank; no missing-as-absent; no listing-as-fact; no kitchen
vocabulary (F01–F08, HOLD, hashes, adapter codes) in buyer copy.

Page 2: every message bound to a claim or action id from the candidate set;
every object id exists in the packet; no pin language for bbox/line/polygon;
`can_establish` / `cannot_establish` preserved; `llm_recommended_order` respects `allowed_first_actions` and
`action_dependencies`; `execution_order` is unchanged.

Page 3: numeric Land Fact fidelity; units, year, spatial meaning; Engine,
coverage, limitations, provenance retained.

Copy-ready messages are validated in the same slice as they are generated.

## 13. Three pages (Step 11)

### Page 1 — Advisor judgment

- How this tract reads from public evidence
- Where listing language (if any) outruns that evidence
- What to do today (max two execution actions)
- Whether a visit already has a defined purpose
- What result would change the next step

Voice: a senior buyer-side ranch advisor in continuous prose, not chips or
status codes the buyer must decode. Do not inventory “we did not find.”
Gaps appear only as the close: materials to get, then the action they unlock.
Do not write “the land is worth flying to.” Diligence-order language only:
if the trip would only confirm facts already on the map, information value is low.

Do not write “this parcel is not ruled out” as a soft pass. Write: the decision
now is not to abandon the tract; it is to get named materials before flying.

### Page 2 — Sendable actions

Copy buttons for:

- listing broker
- title / counsel
- field visitor (category-level until objects exist)
- spouse / partner

### Page 3 — Evidence kitchen

Map, numbers, sources, time, evidence state, limitations, Engine, full audit.
Default collapsed.

## 14. Evidence return (Step 12)

Out of this slice. When it ships: bind new claims/observations to objects, update
state without silently promoting Engine F03 to `FIELD_VERIFIED`, withdraw or
narrow insights, re-rank bottlenecks, tell the user what changed.

## 15. Acceptance test

A run passes this contract only if a target buyer can, without a facilitator:

1. say what the land is already telling them;
2. name the listing line that outruns the evidence (or skip this if no listing);
3. copy or describe today’s action;
4. say whether a weekend trip has a purpose yet;
5. say what would change the next step.

They must not need Factor IDs, HOLD, or a list of absences to do that.

## 16. Implementation order for this contract

Packet, CPER Demo Brief, objects, and live Mireye on `/advisor-demo` are already
in the worktree. Remaining order is owned by
`ADVISOR_INSIGHT_AND_REASONING_CONTRACT.md` §12:

1. Insight / Knowledge Card schemas
2. v1 cards (water, access, RAP, field-task boundary)
3. CPER insight fixtures + adversarial Validator
4. Deterministic six-section buyer prose (kitchen collapsed)
5. Optional LLM on the workbench; fallback on failure
6. Real listing validation
7. Later: PDF/URL extract, evidence-update Deal Room, RAP annual history

Do not restart F01–F08 science to satisfy this contract.
Do not write a free-text prompt before the reasoning space is fixture-tested.
