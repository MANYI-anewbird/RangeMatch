# RangeMatch Mireye-First Product and Agent Execution Plan

> Status: `CURRENT_PRODUCT_AND_IMPLEMENTATION_AUTHORITY`
> Version: `2.1.0`
> Effective date: 2026-08-15
> Stage: competition-grade product, not a production livestock or purchase-decision system

## 0. Authority and migration

This is the single authority for product scope, user journey, data precedence, Agent architecture, execution order, gates, Demo story, and definition of done.

It supersedes earlier fixed F01-F08 orchestration, operating-diligence framing, access/title-first recommendations, Feed/Drink/Move-only profiles, HOLD-first reporting, one-page-only PDF plans, fixed two-page PDF mandates, and bounded six-intent chat framing. Frozen F01-F08 scientific and engineering contracts remain valid when those modules are invoked as supplements; they no longer make any Factor mandatory.

Migration rules:

1. Do not delete working adapters.
2. Do not mark a Phase complete until its Gate passes.
3. Preserve the verified Nambe path until the Mireye-first path passes end-to-end.
4. After migration, F01-F08 run only for deterministic gaps.
5. Access, title, road, fence, power, and infrastructure logic cannot control the primary conclusion (`HUMAN_ACCESS_INFRA_APPENDIX_ONLY`).

## 1. Locked product definition

RangeMatch is a Mireye-powered, parcel-grounded AI advisor that evaluates whether a property's **natural environment and natural resources form a credible foundation for cattle grazing**, explains the evidence in buyer language, asks for the missing local fact most likely to change the view, and updates its conclusion when the user responds.

The buyer's job is:

> For this confirmed parcel, explain what terrain, vegetation, water context, climate, and soils jointly imply for cattle use; identify the controlling natural factor; and tell me what environmental evidence would strengthen or change the view.

Primary users are ranch buyers, buyer-side land advisors, and acquisition analysts. The likely payer is a buyer-side advisor or acquisition team using the system repeatedly. This remains a product hypothesis; the competition proves the mechanism, not market scale.

### User deliverables

1. confirmed parcel;
2. Mireye-first environmental profile with provenance;
3. targeted supplemental evidence only where required;
4. directional natural-foundation conclusion;
5. an integrated expert explanation of how the land's natural resources work together;
6. one question that can refine the conclusion;
7. revised conclusion after the answer;
8. open-ended, read-only, parcel-grounded cattle advisor chat powered by two context sources (place materials + reviewed cattle knowledge);
9. Natural Cattle Foundation PDF: advisor narrative may span multiple pages; evidence appendix always begins on a new page.

### Out of scope

- title, easements, legal access, and roads as proof of entrance;
- electricity, buildings, corrals, chutes, loading areas, gates, and fences;
- price, appraisal, financing, profitability, and buy/no-buy;
- stocking rate, AUM, carrying capacity, herd size, and utilization rate;
- water rights, water quality, and verified livestock-water capacity;
- cattle-versus-sheep ranking and complete ranch operating readiness.

These fields may remain in technical history but cannot control the main conclusion, question, next action, UI, or PDF first page.

### Rule: `HUMAN_ACCESS_INFRA_APPENDIX_ONLY`

Access, legal-entrance, road-contact, power, fence, corral, building, and other **built / legal / operating-infrastructure** evidence is demoted, not deleted.

This rule covers that diligence layer only. It does **not** mean broad cultural, historical, or demographic “humanities” content.

| May | Must not |
|---|---|
| Keep working adapters and collected observations | Delete adapters solely because they left the primary path |
| Show retrieved non-empty rows in PDF Appendix or collapsed technical evidence | Control status, controlling factor, headline, or overall judgment |
| Label rows as physical/legal **context** (e.g. mapped road contact) | Imply legal access, buyability, title clearance, or operating readiness |
| Remain available on the LEGACY path until Phase 7 migrates presentation | Enter the primary LLM workbench selector or drive the Agent’s one question / next action |
| Run through a separate fail-soft Appendix collector after parcel confirmation | Be reintroduced as access-first product framing |

F07 / roads supply optional Appendix context through an isolated fail-soft collector. F07 remains outside the Gap Detector, Combined Environmental Evidence Packet, Natural Cattle Profile, primary LLM workbench, controlling-factor logic, proactive question, and next environmental action. Its failure cannot fail or alter the natural-foundation report.

> **Mireye builds the physical-world picture. RangeMatch plans cattle-specific evidence and reasoning. Supplements add depth only for deterministic gaps. The LLM may interpret evidence but never invent the physical world.**

## 2. Locked architecture

```text
Address / coordinate
  -> Mireye place resolution and parcel candidates
  -> explicit boundary confirmation
  -> Mireye environmental fetch
  -> Mireye Environmental Profile
  -> deterministic Environmental Gap Detector
       -> sufficient: continue
       -> insufficient: invoke named supplements only
  -> Combined Environmental Evidence Packet
  -> Natural Cattle Profile

Natural Cattle Profile + reviewed Cattle Knowledge + Deal Context
  -> validated LLM reasoning
  -> initial conclusion
  -> one high-information question
  -> user answer updates Deal Context
  -> revised conclusion
  -> open-ended two-brain grounded chat
  -> Natural Cattle Foundation PDF (variable-length narrative + new-page Appendix)
```

| Component | Owns | Does not own |
|---|---|---|
| Mireye | parcel entry, broad sourced physical fields, provenance | cattle judgment or silent parcel-wide promotion |
| Gap Detector | deterministic sufficiency and supplement plan | prose or invented tool calls |
| F01-F08 | deeper evidence when triggered | default workflow or final judgment |
| Knowledge Cards | reviewed cattle interpretation | parcel facts |
| Deal Context | intended use and user-provided local facts | independent verification |
| LLM | synthesis, provisional judgment, questions, communication | values, geometry, sources, tool routing, stocking claims |
| Validator | schema, references, provenance, prohibited claims | disguising invalid output |

## 3. Natural-environment scope

| Domain | Product question | Representative evidence |
|---|---|---|
| `FEED_VEGETATION` | Is there a credible natural forage/vegetation foundation? | land cover, herbaceous signal, NDVI, tree/shrub cover, bare ground, RAP depth |
| `WATER` | What natural water evidence exists and what is unverified? | hydrography, waterbody/flowline, permanence, gage/well and wetland context |
| `TERRAIN` | Does terrain appear to constrain cattle use? | elevation, slope, aspect, geometry, parcel distribution |
| `CLIMATE_HAZARD` | What climate or natural hazards shape the view? | precipitation, drought, heat, wildfire/flood context, temporal coverage |
| `SOIL_ECOLOGY` | What soil/ecological context affects vegetation or wetness? | drainage, hydrologic group, map unit, available water, ponding, restrictive layer |

Allowed statuses:

- `PROMISING_NATURAL_FOUNDATION`
- `CONDITIONAL_NATURAL_FOUNDATION`
- `ENVIRONMENTALLY_CONSTRAINED`
- `INSUFFICIENT_ENVIRONMENTAL_EVIDENCE`

Every conclusion contains status, headline, overall judgment, controlling factor, evidence references, limitations, evidence needed, next environmental check, confidence, Deal Context version, Profile hash, source, and validation status.

Missing evidence cannot produce `ENVIRONMENTALLY_CONSTRAINED`. Missing water is not no water. Point/context evidence is not parcel-wide proof.

`ENVIRONMENTALLY_CONSTRAINED` is permitted only when a versioned `approved_hard_constraint_rule_id` is triggered by complete, applicable `PARCEL` evidence and the Validator can reproduce that trigger. Candidate examples for future scientific review include: essentially no land remaining inside a reviewed usable-terrain envelope; a parcel-wide land-cover condition explicitly reviewed as outside the grazing-analysis domain; or a verified natural-hazard condition with an approved cattle-land exclusion rule. These examples are not runtime rules merely because they appear here. The current approved hard-constraint registry is empty, so this status remains disabled until a separate evidence review adds at least one rule. Until then the runtime must use `PROMISING`, `CONDITIONAL`, or `INSUFFICIENT` states.

## 4. Mireye-first data contract

After parcel confirmation, Mireye `/v1/fetch` is the default collection step. Fields come from a frozen cattle-environment manifest derived from live `/v1/meta/fields`.

Every field preserves:

```text
field_id, value, unit, provider, source_name, source_url,
dataset_vintage, fetched_at, confidence, status,
spatial_semantics, temporal_semantics, domain
```

Spatial semantics are mandatory:

- `POINT`: coordinate or centroid;
- `PARCEL`: returned or derived for confirmed polygon;
- `CONTEXT`: nearby, nearest-feature, jurisdictional, or hazard context.

The runtime never promotes `POINT` or `CONTEXT` to `PARCEL`.

Canonical authority is assigned per field, not per Mireye response envelope. A Mireye field may set `canonical_for_parcel_facts=true` only when the frozen field manifest identifies it as genuinely `PARCEL`, its returned semantics match that declaration, and its parcel/geometry reference matches the confirmed geometry hash. `POINT` and `CONTEXT` fields always remain non-canonical for parcel-wide facts. The legacy envelope-level `canonical_for_parcel_facts=false` remains valid only on the migration path and must not be copied into the new Profile as a blanket classification.

Evidence states: `RETRIEVED`, `PARTIAL`, `MISSING`, `SOURCE_UNAVAILABLE`, `NOT_APPLICABLE`, `REJECTED_BY_SEMANTICS_GATE`. Null is not evidence. Empty/failed observations do not enter buyer evidence tables.

The field manifest stores catalog version/ETag, fetch date, definitions, units, domain mapping, required/optional status, expected semantics, and content hash. Major catalog drift fails closed.

### Mireye Environmental Profile

```json
{
  "schema_version": "mireye_environmental_profile@1.0.0",
  "run_id": "...",
  "parcel_ref": {"parcel_resolution_id": "...", "geometry_hash": "...", "confirmed": true},
  "catalog_ref": {"version": "...", "manifest_hash": "..."},
  "observations": [],
  "coverage_summary": {
    "requested_field_count": 0,
    "retrieved_field_count": 0,
    "missing_field_count": 0,
    "point_count": 0,
    "parcel_count": 0,
    "context_count": 0,
    "retrieved_by_domain": {}
  },
  "profile_hash": "..."
}
```

All counts come from the current run; Demo numbers are never constants.

## 5. Deterministic Environmental Gap Detector

The Gap Detector decides domain sufficiency and supplemental tools. The LLM never chooses tools.

```json
{
  "domain": "FEED_VEGETATION",
  "coverage_status": "MIREYE_CONTEXT_PLUS_SUPPLEMENT",
  "available_evidence_refs": [],
  "missing_capabilities": [],
  "reason_codes": [],
  "supplemental_tool_ids": []
}
```

Allowed states: `SUFFICIENT_FROM_MIREYE`, `MIREYE_CONTEXT_PLUS_SUPPLEMENT`, `UNAVAILABLE`.

A supplement is allowed only when the capability is material, Mireye is missing or semantically insufficient, an approved adapter can supply it, the trigger is deterministic/tested, and failure can degrade honestly.

| Supplement | Conditional role |
|---|---|
| F01 / 3DEP | parcel-wide terrain depth absent from Mireye |
| F02 / RAP | parcel-wide herbaceous production/cover/time depth absent from Mireye |
| F03 / NHD | parcel hydrography inventory/drawable candidates absent from Mireye |
| F04 / SDA | parcel soil composition/ecological depth absent from point context |
| F05 / NOAA | precipitation/seasonality/drought depth absent from Mireye |
| F07 / roads | always attempted after confirmed parcel as fail-soft Appendix-only context; never a Gap Detector supplement or reasoning input |
| F08 / RAP woody | parcel woody/shrub depth absent from Mireye |

No F09 is authorized.

F06 is not a supplement. Confirmed geometry always triggers the low-cost F06 area/configuration derivation before the Gap Detector. Its outputs are `PARCEL` geometry facts bound to the confirmed geometry hash. The Gap Detector may consume them but never decides whether they run.

## 6. Combined Packet and Natural Cattle Profile

The Packet preserves accepted Mireye and supplement observations, provider/source provenance, spatial/temporal semantics, coverage/failures, gap decisions, natural candidate objects, and prohibited inferences.

Merge rules:

1. never average/overwrite different spatial semantics;
2. preserve values that answer different spatial questions;
3. use stable IDs/hashes;
4. expose conflicts; the LLM cannot resolve them;
5. retain failures technically but omit empty buyer rows.

The Profile uses `FEED_VEGETATION`, `WATER`, `TERRAIN`, `CLIMATE_HAZARD`, and `SOIL_ECOLOGY`. Every statement links to evidence IDs. Access, legal, power, fence, corral, and infrastructure are excluded from the primary LLM slice.

## 7. Knowledge, Deal Context, and LLM

Reviewed cards cover forage/vegetation, livestock water, terrain, climate/drought, soil/ecology, and evidence/spatial-semantics interpretation. `LEGAL_ACCESS_*` and all access/title cards are excluded from the primary workbench selector, not merely ignored by the prompt.

Minimum Deal Context:

```text
species = CATTLE
operation_type = UNKNOWN | SEASONAL_GRAZING | YEAR_ROUND_COW_CALF | OTHER
intended_grazing_months
user_supplied_water_information
user_supplied_vegetation_or_grazing_history
user_supplied_drought_or_supplementation_history
context_version, geometry_hash, provenance
```

The LLM may synthesize evidence, provide a provisional directional view, identify the controlling factor, explain limitations, ask one allowed question, update the conclusion, and answer open-ended grounded chat from the two-brain workbench (place materials + cattle knowledge). Intent labels are metadata only and do not restrict questions.

It may not invent facts; promote point/context evidence; interpret missing water as no water; convert RAP/NDVI to forage, AUM, or herd size; give legal/purchase/appraisal/water-right conclusions; choose supplements; or alter geometry, values, units, IDs, hashes, and source states.

Invalid/unavailable model output falls back to deterministic natural-environment prose without failing the evidence run.

## 8. User journey

```text
ENTER_PLACE
-> RESOLVE_WITH_MIREYE
-> CONFIRM_PARCEL
-> FETCH_MIREYE_ENVIRONMENT
-> BUILD_MIREYE_ENVIRONMENTAL_PROFILE
-> DETECT_ENVIRONMENTAL_GAPS
-> RUN_TARGETED_SUPPLEMENTS
-> BUILD_COMBINED_ENVIRONMENTAL_PACKET
-> BUILD_NATURAL_CATTLE_PROFILE
-> CREATE_OR_LOAD_DEAL_CONTEXT
-> GENERATE_INITIAL_CONCLUSION
-> ASK_ONE_ENVIRONMENTAL_QUESTION
-> APPLY_USER_ANSWER
-> GENERATE_REVISED_CONCLUSION
-> ENABLE_OPEN_GROUNDED_CHAT
-> EXPORT_NATURAL_FOUNDATION_PDF
```

Target outcomes: `PARCEL_NEEDS_CONFIRMATION`, `PARCEL_NOT_FOUND`, `PARCEL_SERVICE_UNAVAILABLE`, `ENVIRONMENTAL_PROFILE_COMPLETED`, `ENVIRONMENTAL_PROFILE_PARTIAL`, `INVESTIGATION_COULD_NOT_COMPLETE`.

During migration the public API keeps the existing `EVIDENCE_INVESTIGATION_COMPLETED` and `EVIDENCE_INVESTIGATION_INCOMPLETE` values. It also exposes `environmental_profile_outcome` using the target names. UI switches to the environmental field only after Gate 7; then the legacy investigation outcome remains as a deprecated compatibility alias for one release. The API must never change an existing outcome's meaning in place.

Mireye failure never swaps to fixture data. Nambe remains an explicit new Demo run. Questions target natural evidence such as operation type, grazing months, water months, pasture photos, dry-year history, or supplementation history - never title, entrance, power, fences, or facilities.

Question priority is deterministic: ask `operation_type` only when unknown; after it is answered, prioritize Water when Water is controlling or incomplete; otherwise select the highest-ranked unresolved domain, with vegetation/dry-year history before lower-value descriptive context. The Agent must not ask operation type repeatedly.

Flood, wildfire, and similar fields are natural-exposure context only. They may refine `CLIMATE_HAZARD`; they may not produce insurance, insurability, compliance, price, or purchase conclusions.

## 9. UI and PDF

Main UI order:

1. confirmed property and Mireye role;
2. natural cattle foundation;
3. controlling environmental factor;
4. an integrated expert reading of how the land's natural resources work together;
5. one question;
6. answer and updated view;
7. open-ended grounded chat (two brains);
8. report download;
9. collapsed technical evidence.

Do not show fixed F01-F08 as the default workflow. Show Mireye first, detected gaps, and supplements actually called.

PDF advisor narrative is `Natural Cattle Foundation`: Advisor's view, an integrated natural-landscape reading, what the buyer's plan changes, what would strengthen or weaken the view, how to refine the assessment, optional copy-ready request, and scope boundary. The five domains are an internal completeness check, not mandatory visible chapters. The narrative describes the land and its implications; it does not narrate Mireye, adapters, searches, missing calls, or collection steps. **The narrative may continue across as many pages as needed. No qualified LLM insight is removed solely to satisfy a fixed page count.**

The Appendix always begins on a **new page** after the narrative ends, titled `Environmental Evidence Retrieved`: evidence, value/unit, spatial semantics, status, provider (`MIREYE`, `RANGEMATCH_CORE`, or `RANGEMATCH_SUPPLEMENT`), and source/vintage. Only retrieved non-empty observations render. Mireye contribution counts are dynamic.

Under `HUMAN_ACCESS_INFRA_APPENDIX_ONLY`, the Appendix may include a separate optional block `Additional Property Context`. After parcel confirmation, F07 is attempted once through an isolated, time-bounded, fail-soft `APPENDIX_CONTEXT_COLLECTOR`. It translates only retrieved, non-empty mapped-road or other approved non-natural observations into short buyer language, paired with an explicit statement of what each observation does not establish. It is omitted when empty and contains at most four material rows. It does not enter the Combined Environmental Evidence Packet, Natural Cattle Profile, primary LLM workbench, Gap Detector, controlling factor, proactive question, next environmental action, or advisor narrative. F07 failure cannot fail or alter the report. If rendered, the narrative may contain only this neutral pointer: `Additional mapped property context is summarized in the Appendix and does not affect the natural-foundation judgment above.`

## 10. Implementation phases and gates

### Phase 0 - Authority freeze

**Status:** `COMPLETE_WITH_THIS_DOCUMENT`

**Gate 0:** one authority; old fixed-Factor and access-first plans are superseded.

### Phase 1 - Mireye field manifest and Profile schema

**Status:** `COMPLETE`

Deliver live catalog capture/version/hash, reviewed manifest, Profile schema, semantics enums, drift/null tests, and saved Nambe Profile fixture.

**Gate 1:** Nambe creates a non-empty schema-valid Profile; every accepted field has provider, source, status, and spatial semantics; point cannot pass as parcel.

**Gate 1 evidence:** `docs/mireye_cattle_environment_field_manifest.json`, `docs/schemas/mireye_environmental_profile.schema.json`, `src/rangematch/mireye_environmental_profile.py`, `test-data/mireye-environmental-profile/nambe_mireye_environmental_profile.json`, `tests/test_mireye_environmental_profile.py`.

### Phase 2 - Mireye-first collection

**Status:** `COMPLETE`

Make Mireye fetch the default post-confirmation step, batch manifest fields, build dynamic coverage, preserve partial/failure states, and keep legacy path behind a migration flag.

**Gate 2:** confirmed non-fixture parcel reaches a valid Mireye Profile without full F01-F08.

**Gate 2 evidence:** `src/rangematch/mireye_first_collection.py`, Advisor `collection_mode=MIREYE_FIRST` path in `advisor_agent.py`, `tests/test_mireye_first_collection.py`. Default Demo/API remains `collection_mode=LEGACY` (complete Nambe path). `MIREYE_FIRST` is an internal collection gate only — not the buyer report or LLM workbench.

**Contract note:** Phase 2 is an internal collection gate, not the final Demo reasoning path. Do not switch the buyer report, LLM workbench, or default recorded Demo to a Mireye-only evidence set. Preserve the current complete Nambe path until Phase 3 and Phase 4 add deterministic gaps and targeted F01–F05/F08 supplements. The final LLM must reason over the Combined Environmental Evidence Packet, not the Mireye Profile alone.

### Phase 3 - Gap Detector

**Status:** `COMPLETE`

Implement rules, reason codes, plan schema, and tests for complete, point-only, null, partial, failure, and drift cases.

**Gate 3:** identical input yields identical plan; every supplement has a tested reason; LLM cannot alter plan.

**Gate 3 evidence:** `docs/schemas/environmental_gap_plan.schema.json`, `src/rangematch/environmental_gap_detector.py`, `tests/test_environmental_gap_detector.py`. Detector only — supplements are not executed until Phase 4. F06 is never planned; F07 is never triggered.

### Phase 4 - Conditional supplements

**Status:** `COMPLETE`

Route F01-F05/F08 only from the plan; run F06 immediately after parcel confirmation; remove F07 default; retain timeouts/budget/isolation; merge without semantic overwrite.

**Gate 4 evidence:** `src/rangematch/environmental_supplement_runner.py`, `src/rangematch/environmental_evidence_packet.py`, `tests/test_environmental_supplements.py`, MIREYE_FIRST wiring in `advisor_agent.py`. Plan-only environmental adapters; failures stay `SOURCE_UNAVAILABLE` with no fixture swap; F06 always-on and not counted as a supplement. F07 is excluded from this path and handled only by the separate fail-soft Appendix collector; LEGACY Nambe path unchanged.

### Phase 5 - Natural Cattle Profile

**Status:** `COMPLETE`

Implement five-domain schema/projector, evidence withdrawal, controlling factor, infrastructure exclusion, and visible Soil & Ecology.

**Gate 5 evidence:** `docs/schemas/natural_cattle_profile.schema.json`, `src/rangematch/natural_cattle_profile.py`, `tests/test_natural_cattle_profile.py` (Gate 5 + Gate 5.1), MIREYE_FIRST step `PROJECT_NATURAL_CATTLE_PROFILE`. Every domain/`controlling_factor` supporting ref resolves in the current Combined Packet (dangling/stale/cross-run fail closed); semantic `profile_hash` is stable under `built_at`/order and changes when supporting evidence is removed; limitations/`SOURCE_UNAVAILABLE` cannot author land facts or `ENVIRONMENTALLY_CONSTRAINED`; redundant-evidence and controlling-factor withdrawal recompute deterministically. **Gate 5.1 hardening: PASSED.** Phase 6 remains unopened.

### Phase 6 - Reasoning migration

**Status:** `COMPLETE`

Add environmental cards, conclusion schema, question policy, revised loop, five-domain chat, fallback, and Validator.

**Gate 6 evidence:** `docs/schemas/advisor_natural_foundation_interpretation.schema.json`, `src/rangematch/advisor_natural_interpretation.py`, natural workbench card selector (excludes `LEGAL_ACCESS_*`), `select_natural_environment_question`, MIREYE_FIRST steps `CREATE_DEAL_CONTEXT` + `GENERATE_NATURAL_FOUNDATION_INTERPRETATION`, `tests/test_advisor_natural_interpretation.py`. LLM narrates from Natural Cattle Profile + cattle-env cards + Deal Context; status/controlling factor remain Profile-authored; malformed LLM falls back deterministically; PDF renderer unchanged.

### Phase 7 - UI/PDF migration

**Status:** `COMPLETE`

Reuse entry, confirmation, answer loop, chat, and the implemented variable-length renderer (advisor narrative pages plus Appendix on a new page). Replace operating/access language; show actual Mireye/supplement roles; add environmental provider and spatial-semantics columns. The earlier one-page Snapshot remains historical compatibility only.

**Gate 7 evidence:** `src/rangematch/advisor_natural_foundation_pdf.py`, API branch on `/cattle-operating-snapshot.pdf`, Demo main screen prefers `natural_foundation_interpretation`, `tests/test_advisor_natural_foundation_pdf.py`. Advisor narrative copies validated interpretation fields (no re-summary/LLM); Appendix begins on a new page and shows retrieved environmental rows + optional Related Property Context (≤4, omitted when empty); narrative may span multiple pages; LEGACY snapshot path unchanged.

### Phase 8 - Rehearsal/submission

**Status:** `IN_PROGRESS_LIVE_GATE_PASSED_RECORDING_PENDING`

Run Nambe live, optionally one more parcel, test DeepSeek and fallback, download PDF, record video, align One Pager/submission, and export key-free bundle.

**Gate 8:** recording shows address -> Mireye parcel -> Mireye Profile -> gaps -> supplements -> judgment -> answer -> revised judgment -> PDF.

**Live rehearsal evidence (2026-08-15):** Nambe completed on `collection_mode=MIREYE_FIRST` with explicit parcel confirmation, live Mireye Profile, deterministic gap plan, conditional supplements, Natural Cattle Profile, `LIVE_LLM` / `PASSED` DeepSeek interpretation, Natural Cattle Foundation PDF, honest supplement failures, and a successful seasonal-grazing answer update to Deal Context v2. An invalid custom address returned `PARCEL_NOT_FOUND` with no report or Nambe substitution. Phase 8 remains open until the two-minute recording and final submission-form check are completed. DeepSeek validation failure was also exercised and produced a validated deterministic fallback without failing the evidence run.

## 11. Implementation ledger

```yaml
authority_version: 2.0.0
product_scope: CATTLE_NATURAL_ENVIRONMENT_FOUNDATION
mireye_role_target: PRIMARY_PHYSICAL_WORLD_LAYER
supplement_role_target: CONDITIONAL_GAP_FILL
parcel_resolution: IMPLEMENTED
parcel_confirmation: IMPLEMENTED
mireye_context_fetch: IMPLEMENTED_BUT_NOT_PRIMARY_PROFILE
mireye_cattle_environment_manifest: IMPLEMENTED
mireye_environmental_profile_schema: IMPLEMENTED
mireye_environmental_profile_projector: IMPLEMENTED
mireye_first_collection_path: IMPLEMENTED_BEHIND_FLAG
collection_mode_default: LEGACY
environmental_gap_detector: IMPLEMENTED
environmental_gap_plan_schema: IMPLEMENTED
environmental_supplement_runner: IMPLEMENTED
combined_environmental_evidence_packet: IMPLEMENTED
natural_cattle_profile: IMPLEMENTED
natural_cattle_profile_schema: IMPLEMENTED
natural_foundation_interpretation: IMPLEMENTED
natural_foundation_interpretation_schema: IMPLEMENTED
natural_workbench_excludes_legal_access: IMPLEMENTED
fixed_f01_f08_collection: IMPLEMENTED_LEGACY_PATH
generic_packet: IMPLEMENTED_LEGACY_SHAPE
feed_drink_move_profile: IMPLEMENTED_SUPERSEDED_FOR_PRIMARY_PATH
deal_context: IMPLEMENTED_ON_MIREYE_FIRST_AND_LEGACY
initial_revised_conclusion: IMPLEMENTED_NATURAL_FOUNDATION_INTERPRETATION
grounded_chat: IMPLEMENTED_REQUIRES_FIVE_DOMAIN_INTENT_TIGHTENING
two_page_pdf: IMPLEMENTED_NATURAL_CATTLE_FOUNDATION
phase_0: COMPLETE
phase_1: COMPLETE
phase_2: COMPLETE
phase_3: COMPLETE
phase_4: COMPLETE
phase_5: COMPLETE
gate_5_1_hardening: PASSED
phase_6: COMPLETE
phase_7: COMPLETE
phase_8: IN_PROGRESS_LIVE_GATE_PASSED_RECORDING_PENDING
next_authorized_slice: PHASE_8_RECORDING_AND_SUBMISSION_CHECK
```

Update the ledger in the same change that passes a Gate. Component tests do not complete a Phase.

## 12. Code ownership map

New contracts/modules:

```text
docs/mireye_cattle_environment_field_manifest.json
docs/schemas/mireye_environmental_profile.schema.json
docs/schemas/environmental_gap_plan.schema.json
docs/schemas/natural_cattle_profile.schema.json
src/rangematch/mireye_environmental_profile.py
src/rangematch/environmental_gap_detector.py
src/rangematch/environmental_supplement_runner.py
src/rangematch/environmental_evidence_packet.py
src/rangematch/natural_cattle_profile.py
src/rangematch/advisor_natural_interpretation.py
src/rangematch/advisor_natural_foundation_pdf.py
```

Migrate `advisor_agent.py`, `advisor_conclusion.py`, `advisor_question.py`, `advisor_chat.py`, `advisor_snapshot.py`, and Advisor Demo components. Never hide the Gap Detector inside a prompt or UI.

## 13. Required tests

- catalog version/hash/drift;
- Mireye null/partial/failure;
- point/context/parcel isolation;
- dynamic coverage counts;
- deterministic gaps;
- skip supplement when sufficient;
- supplement only for named gap;
- supplement failure preserves Mireye evidence;
- conflicts visible;
- evidence withdrawal;
- Soil enters reasoning;
- no access/infrastructure recommendation;
- no invented facts or stocking/purchase conclusion;
- revised conclusion preserves physical facts;
- Appendix excludes empty/failed/rejected values;
- Demo fallback creates a separate run.

## 14. Competition definition of done

Complete means: place entry, Mireye parcel confirmation, Mireye primary environmental Profile, preserved provenance/semantics, deterministic gaps, only necessary supplements, five-domain Profile, directional conclusion, one environmental question and update, open-ended two-brain grounded chat, variable-length Natural Cattle Foundation report with Appendix on a new page, visible Mireye contribution, honest failures, and a rehearsed Nambe live Demo.

Until all pass, describe components accurately but do not declare the Mireye-first product complete.

The currently runnable Nambe experience is an `INTERIM_LEGACY_DEMO`: it demonstrates parcel confirmation, the existing evidence chain, adaptive answer, chat, and Natural Cattle Foundation PDF, but it is not the completed Mireye-first five-domain product. Submission/video language must preserve that distinction until Gate 8 passes.

## 15. Stop list

Until Phase 8 passes, do not add Sheep, F09, new suppliers, general RAG, title/access/infrastructure **analysis as a primary product path**, stocking calculations, LLM tool routing, hard-coded Mireye counts, more Demo locations, or unrelated dashboard redesign. Do not delete supplements or restore fixed F01-F08 order. Do not delete access/infrastructure adapters; follow `HUMAN_ACCESS_INFRA_APPENDIX_ONLY`.

The next authorized action is **Phase 8: Rehearsal/submission** — Nambe live run, optional second parcel, DeepSeek + fallback, PDF download, two-minute recording, One Pager/submission alignment, key-free bundle.
