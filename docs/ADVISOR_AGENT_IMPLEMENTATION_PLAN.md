# RangeMatch Advisor Agent Implementation Plan

> **Superseded for current execution order on 2026-08-14.** Retained as implementation history. Use `RANGEMATCH_PRODUCT_AND_AGENT_CODE_FLOW.md`.

> Status: `ACTIVE_IMPLEMENTATION_PLAN`  
> Date: 2026-08-12  
> Product authority: `docs/AGENT_THREE_PAGE_WORKFLOW_CONTRACT.md` (buyer shape); `docs/ADVISOR_INSIGHT_AND_REASONING_CONTRACT.md` (LLM reasoning)  
> Current-system authority: `docs/CURRENT_SYSTEM_BASELINE.md`  
> Scientific authority: frozen F01–F08 contracts, Unified Output, and Engine  
> Scope: confirmed parcel → Buyer Evidence Packet → decision skeleton → optional constrained LLM report → Validator  
> Explicit non-scope: suitability, carrying capacity, stocking rate, species ranking, buy/no-buy advice, and the complete Deal Room

## 0. Executive Implementation Decision

RangeMatch will implement the new buyer experience as a bounded orchestration layer above the existing parcel, F01–F08, Unified Output, and Engine infrastructure.

This is not a data-layer rewrite. It is a controlled replacement of the buyer-facing report path:

```text
Current buyer path
Unified Output → HOLD-era Buyer Report → current Validator → current UI

Target buyer path
Unified Output
→ canonical Buyer Evidence Packet
→ claim/evidence gaps
→ bottleneck candidates + allowed action set + hard rails
→ approved Knowledge Cards for open gaps
→ deterministic six-section prose fallback
→ constrained LLM reasoning (optional)
→ Advisor Validator (pages + insight records)
→ ordinary-buyer report; kitchen collapsed
```

The target product is considered implemented only when a real, user-confirmed parcel can pass this path without hand-written evidence, invented objects, or reliance on a live LLM for safety or basic usefulness.

No plan can guarantee external APIs, models, user behavior, or commercial success with absolute certainty. This plan makes delivery controllable by requiring deterministic authority, fail-closed validation, staged gates, reproducible fixtures, live-source degradation paths, and real-user validation before launch claims.

## 1. Product Outcome

For one user-confirmed U.S. parcel and a current buyer decision context, the Agent must produce three layers.

### Page 1 — Advisor judgment

The buyer can understand, without technical interpretation:

- how the tract currently reads from available evidence;
- which listing claim outruns the evidence, if listing claims were supplied;
- what to do today;
- whether a visit has a defined information purpose;
- what result would change the next step;
- what completed lookup should not be purchased again.

### Page 2 — Sendable and executable actions

The buyer receives copy-ready messages or tasks for the relevant audience:

- listing broker;
- title/counsel;
- field visitor;
- partner or decision collaborator.

Every action must state what it can establish, what it cannot establish, its target, its executor, and its success/failure transition.

### Page 3 — Evidence kitchen

The default-collapsed technical layer contains:

- parcel identity and geometry binding;
- canonical Land Facts;
- candidate objects and map geometry;
- source, time, spatial semantics, coverage, and limitations;
- Engine decisions and trace;
- Packet/report hashes and validation record.

### Success event

Generating a file is not sufficient. The first product success event is that the user can select, copy, send, execute, or explicitly decline a high-value diligence action.

## 2. Authority and Safety Model

| Layer | Owns | Must not own |
|---|---|---|
| Parcel workflow | Candidate resolution and explicit confirmation of exactly one parcel | Persuasive report before parcel confirmation |
| F01–F08 adapters | Canonical public/modeled evidence | Suitability or transaction decision |
| Unified Output | Versioned evidence and Engine ledger | Buyer-facing narrative priority |
| Evidence projector | Exact projection of canonical facts and source objects | New numbers, thresholds, or conclusions |
| Product policy | Hard rails, bottleneck candidates, allowed action set | Scientific fact mutation; finished advisor speech |
| LLM | Combination, information-value, conditions, and sendable prose inside the candidate set | Numbers, IDs, states, object geometry, actions outside the set, suitability / stocking / buy-no-buy |
| Advisor Validator | Schema, grounding, reference, language, state, and displayability enforcement | Repairing unsafe prose by guessing |
| UI | Progressive disclosure, copy actions, task state | Hiding failed validation or implying a land verdict |

The Engine remains authoritative in the kitchen. Its `HOLD` state must not drive the buyer-facing cover, and removing `HOLD` from Pages 1–2 must not delete it from the audit trail.

## 3. Non-Negotiable Engineering Rules

1. **One confirmed parcel per run.** No persuasive brief against an unconfirmed boundary.
2. **Canonical facts only.** Packet numeric values and units must equal Unified Output exactly. Display rounding is separate.
3. **Fail closed.** Missing canonical source, broken reference, stale hash, invalid object, or failed validation prevents LLM/display use.
4. **No raw adapter payloads to the LLM.** The LLM receives a validated Buyer Evidence Packet, the decision skeleton, and a few approved Knowledge Cards only. Not the kitchen.
5. **No LLM authority over facts, `execution_order`, or hard rails.** Code owns numbers, states, objects, the candidate set, `action_dependencies`, and `allowed_first_actions`. The LLM may emit `llm_recommended_order` only inside those rails. See `ADVISOR_INSIGHT_AND_REASONING_CONTRACT.md`.
6. **No invented objects.** Object-level language requires a source object in the Packet.
7. **Geometry controls language.** BBOX, LINE, POLYGON, POINT, and navigation precision determine allowed task wording.
8. **Unknown is not absent.** Missing verification cannot become a negative fact.
9. **API success is not evidence completion.** Transport, adapter result, coverage, applicability, object identity, and verification remain distinct states.
10. **Fallback remains useful.** LLM failure returns a deterministic six-section prose report, never a `HOLD` cover page.
11. **Product policy is separate from evidence projection.** CPER demo rules must not silently become generic parcel rules.
12. **No stage advances on documentation alone.** Each gate requires executable tests and inspected artifacts.

## 4. Delivery States

Every work item and phase uses only these states:

```text
NOT_STARTED
IN_PROGRESS
BLOCKED
IMPLEMENTED_NOT_GATED
GATE_PASSED
```

Definitions:

- `IMPLEMENTED_NOT_GATED`: code exists, but required negative tests or final-context verification have not passed.
- `GATE_PASSED`: all required artifacts, tests, and review evidence exist.
- A later phase may prototype early, but it cannot be called production-ready until every prerequisite gate passes.

## 5. Current Starting Point

### Existing infrastructure to preserve

- address and coordinate/map-pin parcel resolution;
- explicit parcel confirmation;
- F01–F08 adapters and scientific contracts;
- investigation workflow and Unified Output;
- deterministic Engine;
- current API and React UI foundations;
- existing Buyer Report, Validator, and deterministic fallback as the legacy path;
- CPER engineering fixture and live-gate artifacts.

### Advisor work already implemented

- locked three-page product contract;
- Buyer Evidence Packet schema;
- Advisor three-page report schema;
- CPER synthetic listing claims;
- deterministic canonical observation projection;
- CPER policy prototype;
- canonical Packet hash binding;
- reference-graph validation;
- rank/action sequence validation;
- warning-only claim gap support;
- first navigation-precision checks;
- fail-closed Unified Output load (`PACKET_SOURCE_UNAVAILABLE`);
- F03 candidate-object projection into the CPER Packet (9 identities; objects do not reorder bottlenecks);
- explicit Packet policy (`policy=None`; CPER demo is never a silent default);
- duplicate Land Fact ID rejection and parcel/Land Fact geometry-hash checks;
- deterministic three-page fallback with real Page 3 kitchen content;
- drawable vs inventory split (`AREA_ONLY` + `map_layers` only when geometry can be drawn);
- five CPER fallback boundary fixtures (no-listing, no mapped water, F03 failure, decision context, non-drawable identities).

### Not yet implemented

- generic evidence-driven policy independent of CPER;
- production Advisor API/report route;
- bounded LLM overlay for the Advisor contract;
- three-page buyer UI;
- full real-listing validation;
- evidence-return/Deal Room loop.

### Current truth statement

The live buyer UI remains the HOLD-era report. The Advisor Brief is not yet the production output. CPER proves the proposed experience and contract path; it does not prove stable output for arbitrary real listings.

## 6. Target Module Boundaries

```text
src/rangematch/
  advisor_packet.py          canonical Packet assembly only
  advisor_candidates.py      source candidate-object projection
  advisor_claim_gaps.py      claim/evidence comparison
  advisor_bottlenecks.py     deterministic bottleneck policy
  advisor_actions.py         deterministic action ordering/templates
  advisor_brief.py           deterministic three-page generator
  advisor_llm.py             bounded prose overlay
  advisor_validator.py       final integrated validation facade
  advisor_contract.py        shared hashes/indexes/contract primitives
```

Tests should converge toward:

```text
tests/
  test_advisor_packet.py
  test_advisor_candidates.py
  test_advisor_claim_gaps.py
  test_advisor_bottlenecks.py
  test_advisor_actions.py
  test_advisor_brief.py
  test_advisor_llm.py
  test_advisor_validator.py
  test_advisor_withdrawal.py
  test_advisor_api.py
  test_advisor_real_parcel_matrix.py
```

The initial combined files may remain while the contract is small, but production logic must be split before the Advisor route becomes the default.

## 7. Phase and Gate Plan

## Phase 0 — Freeze and Record the Legacy Baseline

**Status:** `GATE_PASSED` for documentation; rerun before production cutover.

### Objective

Preserve a truthful comparison point and prevent the new Advisor path from being confused with the currently deployed buyer report.

### Inputs

- `docs/CURRENT_SYSTEM_BASELINE.md`
- legacy Buyer Report prompt/schema/Validator;
- existing backend and frontend test suites;
- CPER Unified Output and current UI fixture.

### Required work

- Mark the Advisor Brief as not live.
- Record legacy endpoint/report version and fallback behavior.
- Preserve the CPER legacy report fixture.
- Record current test commands and runtime environments.
- Record current OpenAI provider state without treating credential presence as availability.

### Gate 0 acceptance

- Current baseline explicitly distinguishes legacy and Advisor paths.
- Existing backend suite passes in the complete live-gate environment.
- Existing frontend suite and production build pass.
- No document claims the Advisor UI is already shipped.

### Gate evidence

- `.venv-livegate/bin/python -m unittest discover -s tests`
- `npm test -- --run`
- `npm run build`
- dated baseline entry

## Phase 1 — Canonical Evidence Projection

**Status:** `IMPLEMENTED_NOT_GATED` — CPER observation projection, fail-closed source load, duplicate-ID rejection, and parcel/Land Fact geometry-hash checks exist. Gate 1 is not declared passed until the remaining required tests and review are accepted.

### Objective

Build observations from Unified Output without hand-written numeric facts, IDs, units, or temporal/spatial semantics.

### Inputs

- confirmed parcel metadata;
- Unified Output;
- canonical Land Facts.

### Outputs

- canonical Land Fact index;
- projected observations;
- Packet parcel binding;
- technical Unified Output reference;
- canonical Packet hash.

### Required work

- Reject duplicate Land Fact IDs instead of last-write-wins.
- Reject missing/unloadable Unified Output with `PACKET_SOURCE_UNAVAILABLE`.
- Require explicit canonical Land Facts in in-memory/API validation paths.
- Compare Packet parcel geometry hash with every projected Land Fact geometry hash where supplied.
- Copy canonical value, unit, temporal semantics, spatial semantics, source ID/version, coverage, applicability, quality, and limitations needed by Page 3.
- Keep `display_value` or formatting rules separate from canonical values.
- Remove repository-specific default source paths from generic runtime construction.

### Failure states

- source unavailable;
- duplicate variable ID;
- missing required fact;
- value/unit/geometry mismatch;
- parcel not confirmed.

### Gate 1 acceptance

- Changing an ID, canonical value, unit, geometry hash, or source binding fails validation.
- Removing the Unified Output source fails closed.
- The CPER Packet fixture is generated from code and byte/structure compared in tests.
- No projected numeric value is manually authored in the fixture-building path.
- Packet schema validation passes.

### Gate 1 required tests

- wrong Land Fact ID;
- rounded canonical value;
- unit mutation;
- duplicate Land Fact ID;
- missing source file/in-memory source;
- geometry hash mismatch;
- unconfirmed parcel;
- display rounding does not change canonical value.

## Phase 2 — Separate Generic Projection From CPER Demo Policy

**Status:** `IMPLEMENTED_NOT_GATED` — explicit policy; CPER demo rejected on non-CPER geometry; five boundary fixtures exist. Not a production ranker.

### Objective

Ensure a real listing does not inherit CPER-specific bottlenecks or actions merely because it uses the same projector.

### Required separation

```text
Evidence projection
  project_observations()
  project_candidate_objects()

Policy derivation
  derive_claim_evidence_gaps()
  rank_bottlenecks()
  order_actions()

Demo assembly
  build_cper_demo_policy()

Packet assembly
  project_buyer_evidence_packet(..., policy=required)
  CPER fixture → explicit build_cper_demo_policy
  real parcel → fail closed without a production policy
```

### Policy inputs

- decision context;
- evidence states and coverage/applicability;
- claim gaps;
- candidate-object readiness;
- adapter failures;
- available actions;
- cost class and dependencies.

### Gate 2 acceptance

- Evidence projector emits no bottleneck or action by itself.
- CPER policy is explicitly versioned and fixture-only.
- A no-listing fixture produces no claim-gap theater.
- A fixture with no mapped water cannot claim mapped-water leads.
- A failed F03 adapter is represented as source failure, not “no water.”
- Changing decision context can change action order without changing evidence.
- CPER remains water bottleneck rank 1 and access-document action order 1 under its frozen demo policy.

## Phase 3 — F03 Candidate Object Projection

**Status:** `IMPLEMENTED_NOT_GATED`  
**Next work:** only Page 3-blocking reconciliation or precision defects. Do not treat this phase as the next primary build.

CPER inventory + remote-pilot projection is in the worktree (`advisor_packet.project_candidate_objects`, `tests/test_advisor_f03_objects.py`). Objects do not auto-change bottleneck rank or action order.

### Objective

Project real NHD/remote-review candidates into the Packet so the product can create object-specific field tasks without inventing pins, names, or wells.

### Initial source

```text
test-data/cross-parcel-validation/XPV_CPER_001/
  f03_remote_pilot/remote_pilot_result.json
```

### Candidate Object minimum contract

- source-stable `candidate_id`;
- candidate type and source feature type;
- source display name, if present;
- geometry kind;
- geometry reference, bbox and/or centroid as actually available;
- field-navigation precision;
- parcel relationship and derivation status;
- evidence state;
- review status;
- remote-support basis;
- legal-access and livestock-use status;
- allowed action language;
- prohibited inferences.

### Identity rules

- NHD IDs use `USGS_NHDPLUS_HR:{layer}:{feature_id}`.
- Do not mint `WATER_CANDIDATE_*`, `W-01`, or replacement IDs.
- Missing names produce neutral source-type labels, not invented names.
- A candidate missing a stable source ID cannot receive an object-level action.

### Geometry rules

| Source shape | Packet geometry | Maximum navigation precision | Allowed buyer language |
|---|---|---|---|
| verified source point | POINT | EXACT only when source supports it | point/location |
| centroid only | POINT | APPROXIMATE | approximate location |
| bounding box | BBOX | AREA_ONLY | area shown on map |
| flowline | LINE | AREA_ONLY | mapped segment/reach |
| waterbody polygon | POLYGON when coordinates exist; otherwise BBOX | AREA_ONLY | mapped waterbody area. CPER remote-pilot currently supplies bbox only, so CPER waterbodies are BBOX/AREA_ONLY until a polygon is actually present. |
| insufficient geometry | source kind or null-safe representation | NOT_NAVIGABLE | inventory/document task only |

### State rules

- `MAPPED_CANDIDATE` is not `REMOTELY_SUPPORTED`.
- `REMOTELY_SUPPORTED` is not `FIELD_VERIFIED`.
- `review_status=UNREVIEWED` remains distinct from evidence state.
- A geolocated photo does not silently satisfy the Engine F03 field-verification contract.

### Gate 3 acceptance

- CPER projects the source inventory without loss or invention.
- Expected CPER counts reconcile: 9 mapped, 3 sampled, 2 remotely supported, 6 unreviewed.
- Every projected ID resolves to the source artifact.
- Flowlines are not rendered or described as points.
- Bboxes/centroids never become exact pins.
- Object changes invalidate the old Packet hash and Brief.
- Removing an object withdraws or downgrades its dependent task.
- Candidate aggregate counts reconcile with projected objects or carry an explicit partial-inventory state.

### Gate 3 required negative tests

- invented candidate ID;
- duplicate candidate ID;
- exact precision on LINE/BBOX/POLYGON;
- object-level action for missing ID;
- object name not bound to the action candidate;
- remotely supported promoted to verified;
- unreviewed count silently omitted;
- object count/aggregate mismatch;
- deleted object leaves stale action/message.

## Phase 4 — Claim-to-Evidence Gap Engine

**Status:** `IMPLEMENTED_NOT_GATED` for CPER fixture only.

### Objective

Compare material listing claims with the exact boundary of current evidence without declaring that the seller lied.

### v1 inputs

- up to three user-pasted claims;
- frozen CPER synthetic claims;
- no dependency on PDF/OCR for launch.

### Supported initial categories

- livestock water;
- legal/physical access;
- forage/productivity;
- terrain;
- climate;
- general “ready for cattle” or suitability language.

### Output

- claim ID and source reference;
- supported portion with evidence references;
- unsupported portion;
- risk of misreading;
- action/message reference or warning-only state.

### Rules

- All listing claims enter as `SELLER_CLAIMED`.
- Supported portions require observation/object references.
- Warning-only gaps may have null action/message IDs.
- No claim language may become a Land Fact.
- No listing supplied means the module emits no claim gaps.

### Gate 4 acceptance

- “Excellent water” stops at mapped/remote evidence actually present.
- “Easy access” stops at physical road context.
- “Ready for cattle” cannot create suitability, stocking, or species claims.
- A forage warning is not attached to an unrelated access action.
- Removing supporting evidence withdraws or narrows the gap language.
- Unknown claim categories remain seller claims and produce a neutral request or no gap, not invented policy.

## Phase 5 — Deterministic Bottleneck Policy

**Status:** `IMPLEMENTED_NOT_GATED` for CPER policy only.

### Objective

Select no more than three unresolved facts with the highest potential to change the next investigation decision.

### Ranking inputs

- decision impact;
- information gain;
- dependencies;
- actionability;
- candidate-object availability;
- cost class;
- whether the measurement is already complete;
- source/adapter failure state;
- current decision deadline.

### Required distinction

```text
bottleneck_rank = importance of unresolved evidence
execution_order = practical order of next actions
```

Water may remain bottleneck 1 while an inexpensive access-document request runs first.

### Rules

- Rank is code-owned and strictly `1..n` in output order.
- Maximum three bottlenecks.
- An unknown without a defined action does not automatically enter the top three.
- Completed measurements are not recommended for repurchase.
- Adapter failure is not absence of the resource.
- The LLM cannot add, remove, or reorder bottlenecks.

### Gate 5 acceptance

- CPER yields the frozen expected rank under the CPER policy.
- Removing/downgrading supporting evidence changes or removes the dependent bottleneck.
- No-water-candidate and F03-failure fixtures produce different states and language.
- Four candidate bottlenecks are deterministically reduced to three with traceable reason codes.
- Re-running identical input and policy version produces identical output.

## Phase 6 — Deterministic Action Ordering

**Status:** `IMPLEMENTED_NOT_GATED` for CPER policy only.

### Objective

Turn bottlenecks into no more than three actions that can be sent or performed, with Page 1 showing at most two actions for today.

### Supported action types

- confirm parcel;
- document request;
- category-level field review;
- object-level field review;
- professional review;
- pause additional spend.

### Ordering considerations

1. hard dependencies;
2. current executability;
3. information gain;
4. cost class;
5. deadline;
6. object/navigation readiness;
7. duplicate/redundant work.

### Required action fields

- action ID and execution order;
- action type;
- specificity;
- target category/object;
- suggested executor;
- cost class;
- why now;
- can establish;
- cannot establish;
- success transition;
- failure transition.

### Gate 6 acceptance

- Order is deterministic and strictly `1..n`.
- Missing objects force category-level or non-navigation actions.
- `NOT_NAVIGABLE` objects cannot generate navigation tasks.
- Every action has both capability and limitation statements.
- Every action resolves to a bottleneck, claim gap, parcel correction, or explicit investigation state.
- Success/failure transitions do not make suitability, legal, or purchase conclusions.

## Phase 7 — Deterministic Three-Page Brief

**Status:** `IMPLEMENTED_NOT_GATED` — deterministic generator emits all three pages, including a real Page 3 kitchen. Gate 7 still needs adversarial Validator coverage on this fallback.

### Objective

Generate a complete, useful brief without any live LLM dependency.

### Page 1 requirements

- grounded tract read;
- up to three listing/evidence gaps;
- up to two actions for today;
- visit-purpose state and rationale;
- conditional next-step transition;
- completed lookups not worth repeating.

### Page 2 requirements

- message specs derived from Packet actions/claims;
- deterministic message templates;
- copy-ready body;
- action and optional claim binding;
- geometry-appropriate field wording.

### Page 3 requirements

- actual map layer references and object geometry;
- canonical observation rows;
- evidence state and spatial/time meaning;
- coverage/applicability/limitations;
- Engine decision and trace references;
- source versions and hashes;
- Packet/report validation record.

Page 3 cannot be counted complete when it contains only boolean presence flags and a Unified Output pointer.

### Gate 7 acceptance

- LLM disabled: all three pages still render and remain actionable.
- Pages 1–2 contain no Factor IDs, `HOLD`, geometry hashes, adapter codes, or raw coverage enums.
- Page 3 reconciles to Unified Output and Engine.
- Fallback never becomes an “unknown list” cover.
- Every Page 2 message resolves to an exact Packet message spec and action.
- Brief hash matches the Packet hash.

## Phase 8 — Integrated Advisor Validator

**Status:** `IN_PROGRESS`

### Objective

Create one production validation facade for Packet, deterministic Brief, and LLM overlay.

### Validation domains

1. JSON schema and required-field integrity;
2. parcel and geometry binding;
3. canonical Land Fact ID/value/unit/time/spatial fidelity;
4. candidate identity/state/geometry fidelity;
5. complete reference graph;
6. rank/order sequence;
7. Packet/Brief hash binding;
8. claim-state preservation;
9. object and navigation language;
10. action capability/limitation preservation;
11. forbidden suitability/ranking/purchase/legal/water claims;
12. missing-as-absent language;
13. Pages 1–2 kitchen leakage;
14. Page 3 completeness;
15. displayability/status consistency;
16. insight withdrawal after evidence removal/downgrade.

### Fail behavior

```text
unsafe LLM overlay
→ discard overlay
→ validate deterministic fallback
→ display fallback only if fallback passes

unsafe Packet or deterministic fallback
→ no persuasive brief
→ explicit system/source/parcel remediation state
```

### Gate 8 required suites

- schema mutations;
- numeric/unit/source mutations;
- reference-graph mutations;
- stale Packet/report binding;
- object geometry matrix;
- adversarial names and pin language;
- evidence withdrawal;
- listing-claim promotion;
- prohibited inference language;
- failed/displayable inconsistency;
- fallback safety.

### Gate 8 acceptance

- Every known mutation fails with a stable code.
- No validator branch silently disables grounding when a source is missing.
- Validation output is deterministic.
- The production API invokes the same validator used by tests.

## Phase 9 — Constrained Advisor LLM Reasoning

**Status:** `NOT_STARTED`  
**Authority:** `ADVISOR_INSIGHT_AND_REASONING_CONTRACT.md`

### Entry prerequisites

- Gates 1–8 relevant to Packet and deterministic Brief pass.
- Insight + Knowledge Card schemas exist.
- v1 cards (water, access, RAP, field-task) are `APPROVED`.
- CPER pass fixtures and adversarial reject fixtures exist.
- Deterministic six-section prose fallback is complete.

### Objective

The LLM does professional advisor reasoning inside a published candidate set. It is not a language overlay on a finished letter.

### LLM input (workbench)

- validated Buyer Evidence Packet (facts only);
- bottleneck candidates and allowed action candidates;
- hard rails and prohibited inferences;
- a few approved Knowledge Cards for the open gaps;
- role: buyer-side ranch advisor; output: six-section prose + insight records.

### LLM-writable fields

- buyer-facing prose for the six report sections;
- insight records (`reasoning_type`, refs, considered/rejected actions, conditions);
- copy-ready message bodies bound to candidate action IDs;
- `llm_recommended_order` among **allowed** candidates, subject to `allowed_first_actions` and `action_dependencies`.

### Immutable fields

- all numeric facts and units;
- parcel and candidate IDs;
- evidence/review states;
- geometry and navigation precision;
- `can_establish` and `cannot_establish` semantics;
- Packet `execution_order`, `action_dependencies`, `allowed_first_actions`;
- the candidate action set itself (no new action types);
- Engine ledger;
- validation and provenance.

### Operational requirements

- new prompt/version identifier plus `playbook_version`;
- structured JSON output;
- bounded retries for transient errors only;
- explicit handling for 429, timeout, invalid JSON, and provider outage;
- no silent fixture substitution for a requested live provider;
- deterministic six-section fallback on failure;
- observable provider/fallback provenance.

### Gate 9 acceptance

- Model cannot add an action outside the candidate set.
- Model cannot mutate `execution_order` or pick a first action outside `allowed_first_actions`.
- Model cannot introduce a number absent from the Packet.
- Field visit cannot be first when it depends on `ACTION_ACCESS_DOCUMENTS` (CPER) or when `visit_purpose` depends on a document.
- Knowledge Card text written as a parcel fact is rejected.
- Wrong object name or precision is rejected.
- Evidence removal withdraws or narrows dependent insights.
- 429/outage still yields a useful deterministic prose report.
- Human review confirms the model is doing combination / information-value reasoning, not reciting a pre-written letter.

## Phase 10 — Three-Page API and UI

**Status:** `NOT_STARTED`

### Objective

Make the Advisor Brief the usable buyer experience while preserving the legacy path behind a version/feature flag until cutover.

### API requirements

- explicit Advisor report version/endpoint;
- Packet creation and validation status;
- deterministic/LLM generator provenance;
- progress states;
- stable error/remediation states;
- feature flag and legacy compatibility.

### UI information hierarchy

```text
Default view
  Advisor judgment
  Today’s actions
  Visit purpose
  What changes next

Second layer
  Copy-ready messages/tasks
  Action status

Collapsed kitchen
  Map
  Evidence table
  Candidate objects
  Sources/limitations
  Engine/audit
```

### UI rules

- no Factor navigation as the primary structure;
- no `HOLD` cover;
- at most two Page 1 actions and three bottlenecks;
- evidence states collapsed to buyer language with technical expansion;
- no map pin when geometry does not support it;
- copy action preserves exactly the validated message body;
- accessible on laptop and mobile widths;
- technical appendix remains inspectable.

### Gate 10 acceptance

- UI tests cover loading, partial data, fallback, invalid Packet, and provider failure.
- Target user can answer the five contract questions in two minutes without facilitation.
- Copy buttons produce the validated text exactly.
- Screen reader/keyboard path covers primary actions and disclosures.
- Legacy UI can be restored by feature flag during rollout.

## Phase 11 — Real-Listing Validation Matrix

**Status:** `NOT_STARTED`

### Objective

Prove the system is not a CPER-only demo and identify supported production conditions.

### Minimum validation set

Use several user-confirmed, non-sensitive or authorized real listings that cover:

- multiple states/counties;
- address and coordinate entry;
- parcel resolved/unresolved/ambiguous cases;
- mapped water present/absent/source failure;
- road contact/no contact/partial coverage;
- RAP applicability and coverage variation;
- complete and partial adapter runs;
- listings with and without material claims;
- candidate objects with POINT/BBOX/LINE/POLYGON/NOT_NAVIGABLE cases where available.

### Measures

- parcel confirmation success/correction;
- adapter and Packet completeness;
- candidate-object reconciliation;
- false-object and false-pin rate;
- time to first bottleneck/action;
- user comprehension;
- copy/send/action-selection rate;
- whether the brief changes visit/document/professional sequencing;
- unsafe inference rejection rate;
- deterministic fallback rate and usefulness.

### Gate 11 acceptance

- Every case has a stored expected outcome and reviewed brief.
- Partial failures produce useful, truthful output or an explicit remediation state.
- No real case relies on CPER hard-coded policy.
- No false object or false precision survives validation.
- Target users understand the first page and can state the next action.
- Production claims are limited to the observed supported conditions.

## Phase 12 — Controlled Cutover

**Status:** `NOT_STARTED`

### Objective

Make Advisor Brief the default buyer route without changing scientific authority or losing rollback capability.

### Required work

- versioned API/report contract;
- feature flag;
- deterministic fallback monitoring;
- validation-error monitoring;
- source/adapter partial-failure monitoring;
- legacy route retention during observation window;
- privacy and logging review;
- user-support copy for parcel/source remediation states.

### Gate 12 acceptance

- Gates 0–11 passed and evidence linked.
- Production deploy and rollback rehearsed.
- No buyer route depends on OpenAI availability.
- Advisor report is default only for validated supported conditions.
- Engine and technical appendix remain available.
- Baseline and documentation index updated from “next contract” to “live.”

## 8. Work That Must Wait

The following work must not block the Advisor Brief and must not be started merely to make the demo appear richer:

- broad PDF/listing-URL ingestion;
- persistent multi-user Deal Room;
- national APN-first lookup;
- multi-parcel ranking;
- new scientific Factors;
- carrying-capacity or stocking models;
- cattle-versus-sheep ranking;
- automatic legal/water-right conclusions;
- RAP 16-day production;
- sophisticated mobile/offline field collection.

After the report path is validated, the preferred first data enhancement is RAP annual history, because it uses an existing provider and adds honest temporal context without creating a suitability rule.

## 9. Cross-Cutting Test Strategy

### Golden fixtures

- CPER aggregate-only Packet;
- CPER with projected F03 objects;
- no-listing parcel;
- unconfirmed parcel;
- no mapped-water candidates;
- F03 adapter failure;
- RAP coverage unquantified;
- road contact and no-contact cases;
- LLM unavailable/429;
- invalid object precision.

### Mutation testing

Systematically mutate:

- IDs;
- values and units;
- hashes;
- geometry hashes;
- evidence/review states;
- references;
- ranks/orders;
- object names/types/precision;
- displayability/validation status;
- prohibited prose.

Every mutation must have a stable expected violation code.

### Withdrawal testing

For every insight/action/message:

```text
remove or downgrade supporting evidence
→ dependent output disappears, narrows, or explicitly downgrades
→ stale Brief hash fails
```

### Determinism testing

Identical Packet inputs and policy versions must produce identical:

- bottleneck rank;
- action order;
- deterministic Brief;
- Packet/report hashes;
- validation output.

LLM prose may vary only within allowed fields and must pass semantic constraints.

### Full regression

At each gate:

- focused Advisor suite;
- full backend suite in declared complete environment;
- frontend tests/build when UI/API contracts change;
- schema validation;
- fixture regeneration check;
- dirty-worktree review to avoid overwriting unrelated user changes.

## 10. Observability and Failure Handling

Production events must distinguish:

- parcel unresolved/unconfirmed;
- source transport failure;
- adapter failure;
- applicability/coverage limitation;
- candidate-object projection failure;
- Packet validation failure;
- deterministic Brief validation failure;
- LLM provider failure;
- LLM overlay rejection;
- deterministic fallback displayed;
- user copied/selected/completed/declined an action.

Never aggregate these into a generic “report failed” metric. They imply different product remedies.

No secrets, full private documents, or unnecessary buyer PII may enter logs. Provider payload logging must be minimized and governed.

## 11. Product Acceptance Metrics

### First-session comprehension

Without facilitation, the target buyer/advisor can answer:

1. What does the land already tell me?
2. Which listing claim goes beyond the evidence?
3. What should I do today?
4. Does a visit have a defined purpose?
5. What result changes the next step?

### Action value

- user copies or selects a next action;
- action has a defined information purpose;
- user understands what it cannot establish;
- evidence update changes or preserves the investigation state explicitly;
- user does not describe the output as “a report that only says it does not know.”

### Trust and safety

- zero invented candidate IDs in accepted reports;
- zero false exact pins in accepted reports;
- zero modeled-to-verified promotions;
- zero road-contact-to-legal-access claims;
- zero mapped-water-to-usable-water claims;
- zero suitability, carrying-capacity, species-ranking, or buy/no-buy claims;
- full numeric reconciliation on accepted reports.

## 12. Definition of Done

The Advisor Agent is done for the narrow buyer-side MVP only when all are true:

- one real user-confirmed parcel enters the workflow;
- required F01–F08 results or honest partial failures enter Unified Output;
- the Packet is generated without hand-authored facts;
- source objects, when available, are projected with correct identity and precision;
- code emits bottleneck candidates and an allowed action set;
- deterministic six-section prose fallback is complete and useful;
- LLM reasoning is optional, cited, and bounded by the Insight contract;
- Validator fails closed across all authority boundaries;
- Pages 1–2 are understandable without kitchen vocabulary;
- Page 3 contains real evidence, not only pointers;
- multiple real-listing cases pass reviewed acceptance;
- the UI supports copying/selecting the next action;
- deployment has observability, fallback, and rollback;
- current-system documentation is updated truthfully.

Until then, the correct status is one of:

```text
PRODUCT_CONTRACT_LOCKED
IMPLEMENTATION_IN_PROGRESS
CPER_DEMO_VALIDATED
REAL_LISTING_VALIDATION_PENDING
```

Do not use `PRODUCTION_READY` early.

## 13. Immediate Execution Queue

The next work must occur in this order. Do not treat an already-landed item as unfinished work.

Already in the worktree (do not redo): fail-closed source load; CPER/generic projector split; F03 object projection; explicit policy requirement; Gate 1 duplicate-ID and geometry-hash checks; deterministic three-page fallback with real Page 3 kitchen; drawable/non-drawable split; five CPER boundary fixtures.

Remaining, in this order:

1. Keep using the five CPER fallback boundary fixtures (no-listing, no mapped water, F03 failure ≠ zero leads, decision-context action order, identities-without-geometry). Expand only if a new brief path appears.
2. Consolidate Advisor Validator and adversarial suites against the fallback Brief.
3. Implement generic claim-gap / bottleneck / action policy as a versioned module. Required before real-listing production claims (Phase 11). Not required before CPER Page 3 or CPER fallback.
4. Ship Insight / Knowledge Card schemas, v1 cards, and adversarial Validator (see `ADVISOR_INSIGHT_AND_REASONING_CONTRACT.md` §12). Do not write a free prompt first.
5. Replace the buyer default with six-section deterministic prose; keep kitchen / Demo process collapsed or in “How we reached this.”
6. Add the constrained LLM reasoning path and repair provider operational readiness.
7. Validate multiple real listings.
8. Cut over only after Gates 0–11 that apply to the claimed supported conditions.

Why this order: a generic nationwide ranker is easy to overbuild. The next buyer value is a readable, cited advisor letter. CPER demo policy remains explicit and fixture-only until Phase 11. Challenge Demo stays LLM-optional.

## 14. Phase Ledger

This table must be updated when a gate changes state. Every `GATE_PASSED` row must link to tests and dated evidence.

| Phase | Current state | Gate evidence | Next required proof |
|---|---|---|---|
| 0 Legacy baseline | GATE_PASSED | Current baseline; existing test records | Rerun at cutover |
| 1 Canonical projection | IMPLEMENTED_NOT_GATED | Observation projector; fail-closed source; duplicate-ID reject; geometry-hash check; CPER fixture generated from code | Formal Gate 1 review; remaining required tests if any |
| 2 Generic/CPER policy split | IMPLEMENTED_NOT_GATED | Explicit `policy`; five CPER boundary fixtures; generic rank/order raise | Adversarial Validator on those fixtures before LLM |
| 3 F03 object projection | IMPLEMENTED_NOT_GATED | 9 CPER objects; empty geometry → `NOT_NAVIGABLE` and off `map_layers` | Do not invent pins or promote hashes to drawable geometry |
| 4 Claim gaps | IMPLEMENTED_NOT_GATED | CPER fixture | Generic/no-listing/withdrawal cases |
| 5 Bottleneck policy | IMPLEMENTED_NOT_GATED | CPER fixture only | Evidence-driven policy matrix before real-listing claims |
| 6 Action policy | IMPLEMENTED_NOT_GATED | CPER fixture only | Dependency/cost/object matrix before real-listing claims |
| 7 Deterministic Brief | IMPLEMENTED_NOT_GATED | `advisor_brief.generate_deterministic_brief`; real Page 3 kitchen | Adversarial Validator suite; no-listing/no-water fallback cases |
| 8 Advisor Validator | IN_PROGRESS | Packet + Brief contract tests | Full mutation/withdrawal/geometry suites on the fallback Brief |
| 9 LLM reasoning | IN_PROGRESS | Insight schemas, 4 cards, CPER pass + adversarial tests; no renderer/LLM yet | Six-section renderer from validated fields, then optional live LLM |
| 10 API/UI | NOT_STARTED | Legacy API/UI only | Three-page tests and usability gate |
| 11 Real listings | NOT_STARTED | CPER only | Reviewed multi-case matrix |
| 12 Cutover | NOT_STARTED | — | Deploy/rollback and monitoring gate |

## 15. Documentation Precedence for This Work

1. `ADVISOR_INSIGHT_AND_REASONING_CONTRACT.md` — LLM reasoning space, cards, insights, Validator, delivery order.
2. `AGENT_THREE_PAGE_WORKFLOW_CONTRACT.md` — three-page buyer shape and Packet rules.
3. `ADVISOR_AGENT_IMPLEMENTATION_PLAN.md` — engineering order and gates.
4. `CURRENT_SYSTEM_BASELINE.md` — what is actually live now.
5. Buyer Evidence Packet and three-page schemas — machine-readable contract.
6. Frozen F01–F08, Unified Output, and Engine contracts — scientific authority.
7. Dated gate results — evidence of what passed at a specific time.

If a later implementation convenience conflicts with the product contract or scientific authority, the convenience must change. If the product contract itself needs to change, record the decision and version the schemas/policies; do not silently loosen the Validator.
