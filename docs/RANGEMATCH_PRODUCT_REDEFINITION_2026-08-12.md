# RangeMatch Product Redefinition

> Status: Product definition closed 2026-08-12. Next work is Slice A (contracts, tests, code).
> Date: 2026-08-12
> Intended review repository: `/Users/hongmanyi/RangeMatch`
> Product stage: Competition demo moving toward a narrow buyer-side MVP
>
> Locked constraints in this revision: reuse source `candidate_id`s (do not mint `WATER_CANDIDATE_*`); carry `review_status`; one parcel per run; Desktop Triage can ship with category-level actions; F03 Engine states are not rewritten by the workspace ladder; code ranks bottlenecks; Deal Room / listing-URL / APN / evidence-return are north-star or later, not the competition-demo gate.

## 1. Executive Decision

RangeMatch should no longer be framed as a grazing-land suitability evaluator.

It should be defined as:

> **A buyer-side, parcel-level evidence investigation and due-diligence workspace for U.S. grazing-land transactions.**

Chinese product definition:

> **RangeMatch 是面向美国牧场土地交易买方的地块证据调查与尽调工作台。**

The product does not determine whether land is suitable for cattle or sheep. It organizes available evidence, identifies the unresolved facts most likely to affect the buyer's next decision, and directs the next highest-value diligence action.

The central product question is therefore not:

> Is this land suitable?

It is:

> **Is this parcel worth moving into the next stage of diligence, and what exactly should be verified next?**

This is a product redefinition, not a rejection of the existing scientific and engineering work. F01–F08, the deterministic Engine, Unified Output, Buyer Report, and Validator remain core product infrastructure. Their presentation and orchestration must now serve a buyer-side diligence workflow rather than a suitability narrative.

---

## 2. Why This Product Should Exist

A grazing-land buyer currently has to assemble evidence across:

- listing descriptions and broker brochures;
- parcel boundaries and ownership records;
- terrain, vegetation, climate, soils, mapped water, and roads;
- seller statements;
- title and easement documents;
- water records;
- field observations and photographs;
- attorney, broker, ranch consultant, well specialist, and other professional input.

The buyer's problem is not merely lack of data. The problem is that different pieces of information have different authority, spatial meaning, and verification status. They are frequently confused with one another:

- mapped water is confused with usable livestock water;
- road contact is confused with legal access;
- modeled production is confused with available forage;
- missing verification is confused with absence;
- a seller claim is confused with a verified fact;
- a complete climate measurement is confused with an agricultural conclusion.

Existing land-data products are strong at exposing parcels and map layers. RangeMatch should differentiate by turning land evidence into a transaction-specific investigation sequence.

The product value is:

> **Reduce wasted site visits and misordered diligence spending by telling the buyer what is already known, what could still change the investigation, and what to verify next.**

---

## 3. Product Promise

### 3.1 What RangeMatch promises

For one user-confirmed U.S. parcel and an intended grazing use, RangeMatch should:

1. Collect available F01–F08 public and modeled evidence.
2. Separate measured facts, modeled results, mapped candidates, seller claims, and verified evidence.
3. Explain what compatible observations jointly establish.
4. Explain what those observations do not establish.
5. Identify no more than three current decision bottlenecks.
6. Recommend the next diligence actions in dependency and information-value order.
7. Bind object-level actions to real candidate objects when the Evidence Packet contains sufficient identity and geometry; otherwise emit category-level actions only.
8. Produce a shareable buyer-facing Decision Brief and a separate technical audit layer.
9. Later: accept documents, photographs, field observations, and professional findings in a persistent workspace.
10. Later: update or withdraw insights when supporting evidence changes, without silently promoting Engine Factor states.

### 3.2 What RangeMatch does not promise

RangeMatch must not claim:

- that a parcel is suitable or unsuitable for cattle or sheep;
- a stocking rate or carrying capacity;
- that cattle are better than sheep, or vice versa;
- forage availability, palatability, or nutritional adequacy from RAP alone;
- verified livestock-water sufficiency from mapped hydrography;
- legal access from physical road contact;
- profitability, ROI, appraisal value, or purchase recommendation;
- legal certainty, permit certainty, title certainty, or water-right certainty;
- that an unverified object is absent;
- that a modeled or point-level result is a field-verified parcel fact.

### 3.3 Product language

Recommended English value proposition:

> **Know what to verify before you visit—or spend.**

Recommended Chinese value proposition:

> **去现场、请律师或花下一笔钱之前，先知道该核实什么。**

Supporting description:

> Submit a U.S. grazing-land parcel. RangeMatch organizes the available evidence, identifies the unresolved issues most likely to affect the next stage of diligence, and produces a prioritized investigation plan.

---

## 4. Product Form

RangeMatch should not be designed as a one-time PDF generator. The durable product is a diligence workspace with three connected layers. The competition demo only has to prove Desktop Triage plus a shareable Decision Brief. The persistent Deal Room is the north star, not the next implementation gate.

### 4.1 Desktop Triage

Current implemented locators: address or coordinate/pin, then user confirmation of one parcel.

Later locators, not demo-complete: listing URL, APN, uploaded polygon, brochure or listing PDF.

The system:

- resolves a candidate parcel;
- requires user confirmation of the relevant boundary;
- runs the currently supported F01–F08 investigation;
- generates a first evidence portrait;
- identifies the initial bottlenecks;
- recommends whether the next useful step is document collection, a field visit, professional review, or correction of the parcel/input.

The first value moment is:

> **Within one session, the user understands what is already established and selects one concrete next diligence action.**

### 4.2 Parcel Diligence Workspace

Every investigated parcel becomes a persistent deal workspace containing:

- confirmed parcel and geometry history;
- listing claims;
- public and modeled evidence;
- candidate objects;
- bottlenecks;
- diligence tasks;
- seller documents;
- field observations and media;
- professional verification;
- evidence-state history;
- generated briefs and revisions.

This workspace is the core commercial product. The report is a snapshot of it. Do not delay the Buyer Report retask or candidate-object projection until the full Deal Room exists.

### 4.3 Decision Brief

At any transaction stage, the user can produce a shareable Decision Brief for:

- the buyer;
- a buyer-side broker or advisor;
- a partner or spouse;
- a title or water attorney;
- a ranch or forage consultant;
- a well specialist;
- a lender or investment committee.

Different views may emphasize different tasks, but all must derive from the same Evidence Ledger.

### 4.4 Product model

```text
Address or coordinate now; listing URL / APN / polygon later
                         ↓
                 Confirm exactly one parcel
                         ↓
                  Run F01–F08
                         ↓
                Unified Output
                         ↓
             Buyer Evidence Packet
                         ↓
          Bottlenecks + candidate objects
                         ↓
     LLM evidence interpretation and action rationale
                         ↓
                  Deterministic Validator
                         ↓
     Diligence Workspace + shareable Decision Brief
                         ↓
       Documents / field evidence / professional input
                         ↓
         Evidence update, insight withdrawal, new tasks
```

---

## 5. Target Users

## 5.1 Primary Persona: Buyer-Side Ranch Broker or Land Advisor

This should be the first commercial user, even when the end reader is the buyer.

### Profile

- Handles multiple ranch, pasture, or grazing-land opportunities each year.
- Represents a buyer or is responsible for buyer-side investigation quality.
- Receives listing links, brochures, parcel data, photographs, and seller claims.
- Coordinates among buyer, listing broker, attorney, ranch consultant, well specialist, and lender.
- Currently works across browser tabs, GIS tools, PDFs, email, text messages, spreadsheets, and personal notes.
- Needs to decide quickly whether a property deserves a visit or further professional expense.

### Primary Job to Be Done

> When a client sends me a grazing-property listing, help me organize the public evidence and identify the questions that matter most, so I can decide what investigation should happen next and brief the buyer clearly.

### Desired outcomes

- Spend less time manually assembling land context.
- Avoid site visits that cannot resolve the current decision bottleneck.
- Ask the listing side specific, evidence-backed questions.
- Coordinate professionals without asking each person to review the entire property from scratch.
- Demonstrate disciplined buyer representation.
- Maintain a repeatable evidence record across multiple transactions.

### Why this is the preferred first customer

- Repeated parcel volume.
- Existing workflow and willingness to pay for time savings.
- Sufficient expertise to evaluate output quality.
- Ability to bring buyers and specialists into the product.
- Better retention characteristics than a one-time individual buyer.

The first cohort should favor advisors whose incentives are clearly aligned with the buyer. A seller-side agent may value presentation and speed but may not welcome a system designed to challenge listing claims.

## 5.2 Secondary Persona: Serious Ranch Buyer or Expanding Operator

### Profile

- Has an active purchase intention and approximate budget.
- Is evaluating one or several specific parcels.
- May understand livestock operations but not every state's land, title, water, or GIS systems.
- Wants to avoid buying the wrong property, not merely explore maps.
- May be purchasing across state or county boundaries.

### Primary Job to Be Done

> When I find a property I may purchase, help me distinguish sales claims from supported evidence and tell me what I need to verify before I spend more money.

### Product experience

This user should receive a simpler buyer-facing interface and should not be expected to understand Factor IDs, rule versions, adapter failures, or evidence-registry mechanics.

## 5.3 Collaborative Personas

These users participate in a parcel workspace but are not necessarily the initial buyer or purchaser of the product:

- title or water-right attorney;
- ranch or forage consultant;
- well inspector or hydrologist;
- soil, vegetation, or ecological-site specialist;
- agricultural lender;
- buyer partner or investment committee member.

Their experience should be task-specific. They should receive a narrow question, relevant object, source evidence, and requested output—not a requirement to read the entire report.

## 5.4 Explicitly Unsupported Users for v1

- users seeking nationwide property discovery or automatic ranking;
- users without a specific parcel;
- users seeking carrying-capacity or stocking-rate estimates;
- users asking which species is best;
- non-grazing use cases such as solar, timber, subdivision, or industrial siting;
- users seeking formal legal, appraisal, veterinary, engineering, or agricultural advice.

---

## 6. Jobs to Be Done

### Functional jobs

1. Bind a listing or location to the correct parcel.
2. Gather parcel-specific public and modeled evidence.
3. Compare listing claims with independent evidence.
4. Identify the highest-information unresolved issue.
5. Decide whether to collect documents, visit the property, or engage a professional next.
6. Prepare an object-specific visit and question list.
7. Record what was observed or verified.
8. Explain how new evidence changes the investigation.
9. Share the current evidence state with collaborators.
10. Preserve a transaction audit trail.

### Emotional jobs

- Feel less overwhelmed by scattered land information.
- Avoid the embarrassment and cost of asking the wrong professional the wrong question.
- Feel that the next expense has a clear purpose.
- Maintain confidence without relying on false certainty.
- Explain a cautious decision to a partner or client.

### Social jobs

- Demonstrate disciplined buyer representation.
- Show that seller claims were not accepted at face value.
- Give specialists clear scopes of work.
- Create a professional, shareable record of diligence.

---

## 7. User Journey Map

## Stage 0: Opportunity Enters the Pipeline

### Trigger

The buyer or advisor encounters a listing and considers whether it deserves attention.

### User inputs

Now:

- address;
- coordinate or map pin.

Later, not required to retask the report:

- listing URL;
- APN;
- uploaded polygon;
- optional brochure or listing PDF.

### Product responsibilities

- parse the supplied locator;
- identify candidate parcels for confirmation;
- surface match quality and ambiguity;
- require user confirmation of exactly one parcel;
- avoid running a persuasive report against an unconfirmed boundary.

Unified Output remains `parcels_per_run: 1`. A multi-parcel pipeline is a later commercial feature, not v1 science or demo scope.

### User question

> Are we looking at the correct land?

### Success criterion

Exactly one parcel is confirmed for investigation.

### Failure path

If the parcel cannot be confirmed, the product requests clarification. It must not silently continue with a nearby point or guessed boundary.

## Stage 1: Desktop Triage

### User goal

Understand whether the property deserves further investigation and what kind of investigation is needed.

### Product responsibilities

- run the supported F01–F08 adapter stack;
- preserve partial failures and spatial semantics;
- construct Unified Output;
- project Unified Output into the buyer-facing Evidence Packet;
- identify the initial bottleneck candidates;
- produce a concise Desktop Triage Brief.

### User sees

- confirmed parcel context;
- measured facts;
- modeled observations;
- mapped candidates;
- seller claims if a listing was supplied;
- no more than three current bottlenecks;
- the next recommended investigation channel.

### User question

> What do we already know, and what is the next useful step?

### Desired action

The user selects at least one next diligence action.

## Stage 2: Choose the Next Investigation Channel

The product does not decide whether to buy the land. It helps the user decide how to reduce uncertainty next.

Possible paths:

### Document-first

Use when a seller, title, access, water, lease, or easement document could resolve the leading bottleneck before a visit.

### Field-visit-first

Use when a mapped or remotely supported object requires physical confirmation and the Evidence Packet contains sufficient identity and geometry to navigate responsibly.

### Professional-review-first

Use when the next question requires legal, water, well, forage, soil, engineering, or other professional judgment.

### Pause additional spend

Use when the parcel is unresolved, a required adapter failed, the data product is outside scope, or the next expense cannot yet answer a defined question.

This state is about the investigation, not a judgment that the land is bad.

## Stage 3: Prepare the Visit or Request

### Product responsibilities

- bind each action to a real candidate object or an explicit inventory-creation task;
- provide the correct geometry type and navigation precision;
- distinguish points, bounding boxes, lines, polygons, and named map features;
- state what the action can establish;
- state what it cannot establish;
- identify the person or role best suited to complete it.

### Example task structure

```json
{
  "action_id": "ACTION_WATER_001",
  "candidate_id": "USGS_NHDPLUS_HR:NetworkNHDFlowline:120638830",
  "target_label": "Little Owl Creek mapped flowline segment",
  "target_type": "NETWORK_NHD_FLOWLINE",
  "navigation_precision": "AREA_OR_SEGMENT_ONLY",
  "action": "Inspect the relevant flowline segment and record visible water, livestock accessibility, and evidence of developed water infrastructure.",
  "suggested_executor": "buyer or buyer-side field representative",
  "resolves": ["physical observation at visit date"],
  "does_not_establish": [
    "year-round reliability",
    "water quality",
    "legal right to use",
    "ownership or legal access"
  ]
}
```

This example is legal only after that `candidate_id`, geometry kind, and navigation precision are in the Buyer Evidence Packet. Until then, do not print the GNIS name or imply a pin.

### Critical rule

If Buyer Report receives only aggregate counts, it must produce category-level actions. It must not invent a point, name, route, well, water source, or a new `candidate_id` scheme such as `WATER_CANDIDATE_*`. Reuse the source identifier already produced by the adapter, e.g. `USGS_NHDPLUS_HR:{layer}:{feature_id}`.

## Stage 4: Collect Documents and Field Evidence

### User actions

- upload photographs or video;
- record GPS location;
- upload seller disclosures, well logs, title material, easements, water records, or inspection notes;
- answer structured observation questions;
- invite a professional collaborator.

### Product responsibilities

- extract proposed claims from documents or media;
- keep extracted claims separate from verified facts;
- require the appropriate human or professional confirmation;
- record evidence source, date, object, and scope;
- preserve contradictions rather than merging them away.

### Evidence progression

Workspace observation states (product ledger, not an F03 Engine upgrade path):

```text
MAPPED_CANDIDATE
→ REMOTELY_SUPPORTED
→ FIELD_OBSERVED
→ DOCUMENT_SUPPORTED
→ PROFESSIONALLY_VERIFIED
```

These states may sit on different axes (a photograph is not a water-right opinion). They must not silently promote Engine F03 to `FIELD_VERIFIED_LIVESTOCK_WATER`. That Engine state still requires the contracted field-evidence package (operation, seasonal reliability, capacity, quality, legal access, livestock access). A geolocated photo plus a well log may support “a physical system exists at the documented location” without changing the Factor to field-verified.

Not every evidence type must follow the same sequence, and later evidence must not retroactively upgrade facts outside its scope.

## Stage 5: Understand What Changed

This should become the strongest product moment.

After evidence is added, RangeMatch should show:

- which prior bottleneck changed;
- which insight was confirmed, narrowed, contradicted, or withdrawn;
- which inference is newly permitted;
- which inference remains prohibited;
- what the next bottleneck is;
- what task now has the highest information value.

Example:

```text
Before
Mapped water candidate; livestock use not verified.

New evidence
Seller well log and geolocated field photograph confirm that a well and tank exist.

Now supported
The physical system exists at the documented location.

Still unresolved
Legal right, seasonal reliability, deliverable capacity, water quality,
and livestock distribution.

Investigation change
“Does a system exist?” is no longer the leading question.
“Can the buyer legally and reliably use it for the intended operation?” becomes the next question.
```

## Stage 6: Collaborate With Professionals

### Product responsibilities

- create a narrow professional task;
- include relevant candidate object and source material;
- state the exact question requiring professional review;
- prevent the professional's conclusion from being generalized beyond its scope;
- record the result in the Evidence Ledger.

Example:

> Confirm whether any recorded livestock-water right that the seller associates with this parcel transfers with the land and permits the intended use. Attach only candidate objects and documents that are already in the Evidence Packet. Do not assess forage or operational carrying capacity. Do not treat an NHD flowline ID as a water-right identifier.

## Stage 7: Produce a Transaction-Stage Decision Brief

The user generates a shareable brief before a field visit, offer, inspection deadline, professional engagement, or internal decision meeting.

The brief should communicate:

- current parcel confirmation status;
- facts already established;
- material claims not yet verified;
- current bottlenecks;
- completed and pending actions;
- how recent evidence changed the investigation;
- the next recommended diligence action;
- important limitations;
- technical provenance in an appendix.

It must not issue a buy/no-buy or suitability judgment.

## Stage 8: Close, Pause, or Exit the Investigation

The user records the transaction outcome separately from scientific facts:

- proceeding to offer;
- continuing investigation;
- paused;
- property no longer available;
- user chose not to proceed;
- purchased;
- unsupported scope.

The product should preserve:

- which evidence changed the investigation;
- which tasks were completed;
- which questions remained unresolved;
- what the user decided;
- that the user's transaction decision is not an Engine Land Fact.

For professional users, the completed workspace becomes reusable transaction knowledge without becoming an unreviewed scientific rule.

---

## 8. Buyer Evidence Packet

The LLM should not consume raw adapter responses or receive the Engine label as the primary narrative instruction.

The Buyer Evidence Packet should contain at least:

```json
{
  "parcel": {},
  "observations": [],
  "seller_claims": [],
  "candidate_objects": [],
  "evidence_gaps": [],
  "bottleneck_candidates": [],
  "available_actions": [],
  "prohibited_inferences": [],
  "engine_ledger_reference": {}
}
```

## 8.1 Evidence state vocabulary

Buyer-facing evidence must distinguish:

- `MEASURED`
- `PARCEL_DERIVED`
- `MODELED`
- `MAPPED_CANDIDATE`
- `SELLER_CLAIMED`
- `REMOTELY_SUPPORTED`
- `FIELD_OBSERVED`
- `DOCUMENT_SUPPORTED`
- `PROFESSIONALLY_VERIFIED`
- `REJECTED_AS_SOURCE`
- `COVERAGE_UNQUANTIFIED`
- `NOT_VERIFIED`
- `NOT_APPLICABLE`
- `MISSING`

Internal scientific states may be more detailed. The buyer UI should collapse this vocabulary into a small display set such as `MEASURED`, `MODELED`, `MAPPED`, `CLAIMED`, `VERIFIED`, and `UNKNOWN`, with the full state available on expand. Never dump thirteen chips on the first screen. Buyer-facing labels must never imply more authority than the underlying evidence.

## 8.2 Candidate Object contract

Object-level actions require an object-level contract.

Minimum shape:

```json
{
  "candidate_id": "USGS_NHDPLUS_HR:NetworkNHDFlowline:120638830",
  "candidate_type": "WATERBODY | FLOWLINE | ROAD_SEGMENT | SELLER_CLAIMED_WELL | OTHER",
  "source_feature_type": "NHDWaterbody | NetworkNHDFlowline | TIGER_Road | USER_CLAIM",
  "display_name": "Little Owl Creek",
  "geometry": {
    "kind": "POINT | BBOX | LINE | POLYGON",
    "centroid": null,
    "bbox": null,
    "geometry_reference": null,
    "field_navigation_precision": "EXACT | APPROXIMATE | AREA_ONLY | NOT_NAVIGABLE"
  },
  "parcel_relationship": {
    "intersects": null,
    "distance_m": null,
    "relationship_status": "DERIVED | SOURCE_REPORTED | UNKNOWN"
  },
  "evidence_state": "MAPPED_CANDIDATE | REMOTELY_SUPPORTED | FIELD_VERIFIED",
  "review_status": "UNREVIEWED | SAMPLED",
  "remote_support_basis": [],
  "legal_access_status": "NOT_VERIFIED",
  "livestock_use_status": "NOT_VERIFIED",
  "allowed_action_language": [],
  "prohibited_inferences": []
}
```

Identity rules:

- Reuse the adapter's stable identifier. For NHD: `USGS_NHDPLUS_HR:{layer}:{feature_id}`. For TIGER: the existing `nearest_road_feature_id` / LINEARID. Never mint `WATER_CANDIDATE_*` or `W-03`.
- `display_name` is GNIS or map name if present, otherwise `unnamed {layer} {feature_id}`. Absence of a name is not absence of a feature.
- F07 road objects are the same class of gap. v1 projects water candidates first. Do not write “inspect that road” until a road object is in the packet.

State rules:

- `evidence_state` and `review_status` are both required. On CPER, 9 candidates are mapped, 3 were sampled, 2 are remotely supported, 6 remain `UNREVIEWED`. `UNREVIEWED` is not a synonym of `MAPPED`.
- `allowed_action_language` is filled by deterministic templates from `geometry.kind` + `evidence_state` + `review_status`. The LLM may rephrase a permitted template. It may not invent targets or pin language.

Geometry and inference rules:

- A bounding box or centroid must not be presented as a precise pin.
- A flowline must not be called a water-source point.
- A mapped or remotely supported feature must not be called usable livestock water.
- A feature within or touching a parcel does not establish ownership or legal access.
- A GNIS or map name is identification context, not operational evidence.
- If navigation precision is `AREA_ONLY`, `APPROXIMATE`, or `NOT_NAVIGABLE`, the task must describe an area or segment rather than a point destination.

---

## 9. Bottleneck Contract

A bottleneck is not merely an unknown. It is an unresolved fact that currently has high potential to change the next investigation decision.

Minimum shape:

```json
{
  "bottleneck_id": "BOTTLENECK_WATER_VERIFICATION",
  "title": "Mapped water has not been verified for livestock use",
  "supporting_evidence_refs": [],
  "affected_candidate_ids": [],
  "blocked_inferences": [],
  "why_now": "",
  "priority_basis": {
    "decision_impact": "HIGH | MEDIUM | LOW",
    "information_gain": "HIGH | MEDIUM | LOW",
    "dependency": [],
    "cost_class": "DESKTOP | DOCUMENT_REQUEST | FIELD_HALF_DAY | PROFESSIONAL_REVIEW | UNKNOWN"
  },
  "next_action_ids": [],
  "counterfactuals": []
}
```

### Bottleneck ranking principles

The system should consider:

1. Whether resolving the issue could change the next investigation stage.
2. Whether other tasks depend on it.
3. Whether it can be resolved through a defined action.
4. Whether the Evidence Packet contains a real target object.
5. Expected information gain.
6. Approximate cost class.
7. Whether the task duplicates an already complete measurement.

Deterministic product policy emits an ordered list of at most three `bottleneck_id`s, plus `priority_basis`, `supporting_evidence_refs`, `affected_candidate_ids`, `blocked_inferences`, structured `counterfactuals`, and `next_action_ids`. The LLM writes `title` / `why_now` against those IDs only. It must not reorder bottlenecks, add a fourth, or decide that water outranks access by prose.

---

## 10. LLM Role

The LLM is an evidence interpreter and investigation planner.

### Allowed LLM work

- explain compatible observations together;
- identify the current investigation tension;
- distinguish what is supported from what remains unverified;
- translate technical evidence states into buyer language;
- warn against parcel-specific misinterpretations;
- explain bottleneck priority supplied or constrained by product policy;
- create action rationale from real actions and objects;
- create conditional counterfactuals;
- adapt one Evidence Packet for buyer, broker, attorney, or specialist views;
- revise or withdraw language when evidence changes.

### Prohibited LLM work

- suitability determination;
- carrying-capacity or stocking-rate estimation;
- species ranking;
- invention of thresholds, weights, facts, objects, coordinates, documents, or new `candidate_id` schemes;
- GIS computation or coverage calculation in prose;
- upgrading `MAPPED`, `MODELED`, or `SELLER_CLAIMED` evidence to verified;
- inferring legal access, water rights, reliability, quality, or capacity;
- interpreting absence of verification as absence of the resource;
- recommending purchase or guaranteeing performance.

### Required LLM output

```json
{
  "headline": "",
  "combined_insights": [],
  "primary_bottlenecks": [],
  "misinterpretation_warnings": [],
  "next_actions": [],
  "counterfactuals": []
}
```

Every insight, warning, action rationale, and counterfactual must reference evidence, bottleneck, action, or candidate-object IDs.

---

## 11. Engine and Validator Roles

## 11.1 Engine

The Engine remains the authoritative scientific ledger.

It should continue to:

- evaluate reviewed deterministic rules;
- preserve unknown and verification states;
- retain `HOLD`, `REVIEW`, `ADVANCE`, `REDIRECT`, and `REJECT` where allowed;
- record rule, data, source, and profile versions;
- prevent missing values from becoming zero;
- preserve cross-profile ranking restrictions;
- maintain full decision traces.

The Engine label should remain available in technical and audit views. It should not drive the buyer-facing report headline.

## 11.2 Validator

The Validator must continue to reject:

- numbers without valid Land Fact references;
- invented acreage, objects, locations, wells, water sources, or roads;
- evidence-state upgrades;
- point-to-parcel generalization;
- suitability, stocking, profitability, and species-ranking claims;
- mapped water presented as usable water;
- road contact presented as legal access;
- unconditional claims derived from counterfactuals.

The Validator should be extended to support:

- combined insights with multiple evidence references;
- bottleneck references;
- candidate-object references;
- action-target validity;
- navigation precision constraints;
- conditional counterfactual language;
- insight withdrawal tests;
- omission of `HOLD` from buyer-facing narrative;
- prioritization without requiring equal Factor coverage.

### Withdrawal requirement

For any generated insight:

```text
Insight supported by Evidence A + Evidence B
→ remove or downgrade Evidence A
→ insight must disappear, narrow, or be explicitly downgraded
```

This should become a first-class evaluation suite.

---

## 12. Decision Brief Structure

The buyer report should follow the buyer's decision sequence rather than F01–F08 order.

## 12.1 Investigation status

- confirmed parcel status;
- data-run status;
- current investigation path;
- no more than three bottlenecks;
- most recent evidence change.

Do not use `HOLD` as the cover headline.

## 12.2 What is already established

Show only decision-relevant evidence:

- parcel and area context;
- terrain;
- climate measurements;
- modeled vegetation and production;
- mapped water candidates;
- mapped roads;
- soil, wetness, and ecological context.

Every item displays its evidence state and spatial meaning.

## 12.3 What these observations jointly mean

The LLM explains compatible observations without turning them into a suitability conclusion.

Example:

> Annual precipitation already has a canonical measured value, so repeating that lookup is not currently the highest-information next expense. Mapped water and physical road contact remain operationally and legally unverified, so those issues are more likely to benefit from targeted documents or field investigation.

This is a diligence-priority statement, not a claim that climate is agriculturally adequate.

## 12.4 What would be easy to misread

Parcel-specific warnings such as:

- mapped water does not establish a drinking system;
- a remotely supported feature does not establish year-round water;
- road intersection does not establish legal entry;
- RAP production does not establish available forage;
- zero field-verified systems does not mean no water exists.

## 12.5 What to do next

No more than three actions. Each action shows:

- target object or inventory task;
- why it is prioritized now;
- suggested executor;
- cost class;
- what it can resolve;
- what it cannot resolve;
- what changes if it succeeds or fails.

## 12.6 Evidence change history

Show how uploaded or verified evidence changed:

- evidence state;
- insight language;
- bottleneck priority;
- next action.

## 12.7 Technical appendix

Place here:

- Engine decisions;
- F01–F08 details;
- evidence and source versions;
- limitation IDs;
- hashes and provenance;
- complete unknown list;
- technical `HOLD` explanation.

---

## 13. Product States

Buyer-facing investigation states should be distinct from Engine match decisions.

Recommended investigation states:

- `PARCEL_CONFIRMATION_REQUIRED`
- `DESKTOP_SCAN_RUNNING`
- `DESKTOP_SCAN_COMPLETE`
- `DOCUMENT_COLLECTION_RECOMMENDED`
- `FIELD_VISIT_WORTH_CONSIDERING`
- `PROFESSIONAL_REVIEW_RECOMMENDED`
- `BLOCKED_BY_MISSING_OBJECTS`
- `PARTIAL_DATA_AVAILABLE`
- `PAUSE_ADDITIONAL_SPEND`
- `OUTSIDE_SUPPORTED_SCOPE`
- `EVIDENCE_UPDATE_AVAILABLE`
- `INVESTIGATION_CLOSED`

These states must not imply that the land itself passed or failed.

`BLOCKED_BY_MISSING_OBJECTS` means object-level navigation is unavailable. It must not suppress Desktop Triage or the Decision Brief. In that state the product still emits category-level actions (“review mapped hydrography candidates”) and must not invent named points. The buyer UI should collapse this list into a small set of investigation-path labels; thirteen equal chips are not a first-screen design.

---

## 14. MVP Scope

## 14.1 Competition Demo

The CPER engineering geometry can demonstrate:

- F01–F08 collection and Unified Output;
- evidence-state separation;
- three decision bottlenecks;
- aggregate water-candidate reasoning;
- buyer-language interpretation;
- next-action prioritization;
- Validator protections;
- Engine/audit separation.

The demo must clearly state that CPER is an engineering test geometry, not a purchasable parcel, cadastral parcel, official pasture boundary, or suitability ground truth.

Object-level actions may be demonstrated only after candidate objects are projected from the remote-pilot artifact into the Buyer Evidence Packet. Until then, water actions must remain category-level.

## 14.2 Report-productization slice (do this first)

These items may use the CPER engineering geometry. They do not wait for a Deal Room, listing-URL parser, or a second live listing:

1. One confirmed parcel per run (`parcels_per_run: 1`).
2. Existing F01–F08 adapter execution and Unified Output.
3. Buyer Evidence Packet derived from Unified Output.
4. Revised LLM Buyer Report task (combined insights, traps, actions, counterfactuals).
5. Deterministic bottleneck contract: code emits an ordered 1–3, LLM explains only.
6. Candidate Object projection for water, reusing source IDs; category-level actions until objects are in the packet.
7. Object-valid next actions or explicit inventory tasks.
8. Updated Validator, including object, navigation-precision, counterfactual, and withdrawal tests.
9. Engine `HOLD` moved to the technical appendix.
10. Shareable Decision Brief UI around the buyer journey rather than Factor order.

## 14.3 Next, not the same gate

After the CPER brief no longer narrates HOLD:

11. At least a minimal evidence-update workflow (does not rewrite F03 Engine states).
12. Validation against several real, user-confirmed listings, not CPER alone.

These prove live gates and the update loop. They must not block rewriting the CPER report.

## 14.4 Immediate enhancement after report refactor

RAP annual history from 1986 onward is the preferred first data enhancement because:

- the provider and public API already exist;
- the current adapter is oriented around a single year;
- historical variability adds narrative and context without adding suitability rules;
- it is cheaper and more directly visible than new data providers or species thresholds.

The historical view may describe modeled variation and the position of a selected year within the returned history. It must not predict future production or derive usable forage or carrying capacity.

## 14.5 Later enhancements

- richer parcel spatial zoning;
- RAP 16-day production;
- seller-document extraction;
- field photo and media capture;
- professional collaboration permissions;
- mobile and offline visit workflows;
- transaction pipeline management;
- state-specific official-record workflows.

## 14.6 Explicit non-goals

- suitability scoring;
- stocking-rate calculation;
- automatic Cow-Calf versus Sheep ranking;
- national property ranking;
- autonomous buy/no-buy advice;
- automatic legal conclusions;
- expanding the Factor list merely to make the report appear complete.

---

## 15. Success Metrics

## 15.1 North Star Metric

> **Number of high-priority diligence tasks completed or explicitly dispositioned per active parcel workspace.**

The product creates value when it advances an investigation, not when it merely generates a report.

## 15.2 Activation metrics

- parcel confirmation rate;
- successful first scan rate;
- time from input to first bottleneck;
- percentage of first sessions in which the user selects a next action;
- percentage of reports with at least one valid real-object task or explicit inventory task.

## 15.3 Value metrics

- percentage of parcels where the user completes a recommended task;
- percentage where the user requests a specific document from the listing side;
- percentage where the user changes the order of diligence spending;
- percentage where an evidence update changes a bottleneck;
- avoided or deferred field visits reported by users;
- time saved preparing a buyer or professional brief.

## 15.4 Trust and safety metrics

- parcel correction rate;
- unsupported numeric-claim rejection rate;
- invented-object rejection rate;
- evidence-state upgrade rejection rate;
- percentage of mapped candidates incorrectly interpreted as verified in user testing;
- insight withdrawal accuracy;
- user reports that a task target does not exist or cannot be located;
- false implication rate for suitability, legal access, water sufficiency, or species ranking.

## 15.5 Professional retention metrics

- parcels investigated per active professional per month;
- repeat use across separate transactions;
- collaborator invitations per parcel;
- evidence updates per parcel;
- Decision Briefs shared at transaction milestones.

Monthly consumer retention is not an appropriate primary measure for low-frequency individual buyers.

---

## 16. Commercial Model

## 16.1 Professional plan

Primary commercial motion:

- buyer-side broker or advisor seats;
- included parcel scans;
- persistent parcel workspaces;
- buyer and professional sharing;
- branded Decision Briefs;
- transaction evidence history;
- later, multi-parcel pipeline management without suitability ranking.

## 16.2 Individual buyer plan

- one parcel Desktop Triage Brief;
- limited evidence updates;
- ability to invite an advisor or professional;
- upgrade path to a persistent workspace.

## 16.3 Later team plan

- buyer-representation teams;
- land-investment teams;
- agricultural lenders or risk teams;
- shared templates and review policies;
- organization-level evidence governance.

Do not begin with a generic low-price monthly consumer subscription. Purchase frequency is too low and trust requirements are too high.

---

## 17. Current Engineering Interpretation

The primary implementation repository is:

```text
/Users/hongmanyi/RangeMatch
```

The current system already contains substantial infrastructure:

- F01–F08 adapters and evidence contracts;
- parcel and investigation workflows;
- Unified Output;
- deterministic Matching Engine;
- Buyer Report generator;
- Report Validator;
- CPER fixtures and live-gate artifacts;
- web report experiences.

Therefore, the next phase is not a data-layer rebuild.

The immediate implementation order should be:

1. Rewrite the Buyer Report task around combined insights, bottlenecks, actions, and counterfactuals.
2. Move buyer-facing `HOLD` language into the technical appendix.
3. Define and implement the Bottleneck contract (code ranks; LLM explains).
4. Project real F03 candidate objects into the Buyer Evidence Packet, reusing source `candidate_id`s and carrying `review_status`.
5. Bind actions to those IDs or to explicit inventory tasks; keep category-level language until the packet has objects.
6. Extend the Validator for object validity, navigation precision, counterfactuals, insight references, and withdrawal tests.
7. Update the report UI around the buyer journey rather than Factor order.

After that CPER brief works:

8. Validate on real user-confirmed listing parcels.
9. Add a minimal evidence-update workflow that does not rewrite F03 Engine states.
10. Add RAP annual history as the first non-blocking data enhancement.

Do not restart the Mireye, F01, or F01–F08 engineering program merely to implement this product direction. Do not wait for listing-URL, APN, Deal Room, GEE coverage, 16-day RAP, or species numeric rules.

---

## 18. Product Acceptance Tests

The redefined product is working only when the following are true.

### First-session comprehension

After reviewing one brief, a target user can answer without facilitator help:

1. What is already known?
2. What is modeled or merely mapped?
3. What is the leading unresolved issue?
4. What should happen next?
5. What would that next action establish?
6. What would it still not establish?

### Action specificity

- Every object-level action references a valid object.
- Every aggregate-only action is clearly category-level.
- No bounding box is presented as a precise destination.
- No mapped flowline or waterbody is described as a verified livestock system.

### Scientific safety

- No suitability or species-ranking implication.
- No stocking or carrying-capacity estimate.
- No modeled-to-field-verified upgrade.
- No missing-to-absent inference.
- No physical-road-to-legal-access inference.
- All visible numeric claims reconcile to Land Facts.

### Product value

- The user selects or completes a next action.
- The action has a defined information purpose.
- A later evidence update changes, confirms, or explicitly preserves the bottleneck state.
- The user does not describe the product as “a report that says it does not know.”

---

## 19. Final Definition

RangeMatch is not a grazing suitability oracle and not merely a land-data report generator.

It is:

> **An AI-assisted, buyer-side diligence workflow that turns parcel data, listing claims, mapped candidates, field observations, and professional documents into a traceable evidence record, a prioritized investigation plan, and an updated transaction brief.**

Chinese definition:

> **RangeMatch 是一个 AI 辅助的牧场买方尽调工作流：它把地块数据、挂牌声明、地图候选、现场观察和专业文件组织成可追踪的证据，识别当前最可能改变交易调查的缺口，并安排下一项最有信息价值的核实行动。**

The durable strategic shift is:

```text
From: generating a land conclusion
To: advancing a transaction investigation

From: a one-time report
To: a living parcel Evidence Deal Room

From: a low-frequency consumer tool first
To: a repeatable buyer-side broker/advisor workflow first
```

