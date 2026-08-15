# RangeMatch Natural Cattle Foundation Report Template

> Status: `CURRENT_BUYER_REPORT_TEMPLATE`
> Version: `1.0.0`
> Effective date: 2026-08-15
> Product authority: `RANGEMATCH_PRODUCT_AND_AGENT_CODE_FLOW.md` version 2.1.0
> Output: English PDF. Advisor narrative may span as many pages as needed. The Appendix always begins on a new page after the narrative. No qualified LLM insight is removed solely to satisfy a fixed page count.

## 0. Purpose

This template defines the buyer-facing structure for the Mireye-first RangeMatch Natural Cattle Foundation report.

The report must read like a cattle-land advisor explaining one confirmed parcel. It must not read like a Factor dashboard, API log, missing-data inventory, legal-diligence memo, or generic cattle guide.

The narrative must answer:

1. What is the current directional natural-foundation judgment?
2. Which natural environmental factor controls that judgment?
3. What kind of natural landscape is this, and how do its resources work together for the intended cattle use?
4. What did the buyer's answer change?
5. What environmental evidence would most improve the judgment next?

## 1. Required inputs

```text
confirmed_parcel
mireye_environmental_profile
environmental_gap_plan
combined_environmental_evidence_packet
natural_cattle_profile
reviewed_cattle_knowledge_cards
deal_context
initial_natural_foundation_conclusion
revised_natural_foundation_conclusion (when available)
conclusion_change (when available)
```

Every parcel-specific statement must reference accepted evidence from the combined Packet. General cattle interpretation must reference an approved Knowledge Card. User-provided information must retain `USER_SUPPLIED_UNVERIFIED` provenance unless separately verified.

## 2. Rendering rules

- Advisor narrative is buyer-facing prose and may continue across pages as needed.
- The Appendix is the environmental evidence appendix and always begins on a new page after the narrative.
- Default language is English.
- Use ordinary professional language; do not expose Factor IDs, observation IDs, hashes, schema names, enum names, adapter names, or internal workflow terminology in the advisor narrative.
- Lead with a conclusion, not a limitation or a description of the investigation.
- Explain uncertainty only where it changes the judgment.
- Do not list every missing field.
- Do not repeat the same limitation in multiple sections.
- Keep Mireye, adapter, search, fetch, coverage, and provider language out of the advisor narrative.
- Use evidence to describe the land; do not narrate how the evidence was collected.
- Treat the five environmental domains as an internal reasoning checklist, not mandatory buyer-facing chapter headings.
- Point, parcel, and context evidence must remain distinguishable.
- Mireye and supplements must retain separate provider attribution.
- No qualified LLM insight is removed solely to satisfy a fixed page count.
- The report must remain readable without opening technical evidence.

## 3. Allowed conclusion statuses

```text
PROMISING_NATURAL_FOUNDATION
CONDITIONAL_NATURAL_FOUNDATION
ENVIRONMENTALLY_CONSTRAINED
INSUFFICIENT_ENVIRONMENTAL_EVIDENCE
```

Buyer-facing labels:

| Status | Display label |
|---|---|
| `PROMISING_NATURAL_FOUNDATION` | Promising natural foundation |
| `CONDITIONAL_NATURAL_FOUNDATION` | Conditional natural foundation |
| `ENVIRONMENTALLY_CONSTRAINED` | Environmentally constrained |
| `INSUFFICIENT_ENVIRONMENTAL_EVIDENCE` | Environmental picture is not yet sufficient |

`ENVIRONMENTALLY_CONSTRAINED` may render only when a validated approved hard-constraint rule is present. Missing data alone cannot produce it.

---

# PAGE 1 - NATURAL CATTLE FOUNDATION

## Header

```text
RANGEMATCH
Natural Cattle Foundation
{{parcel_display_address}}
```

Optional status line:

```text
Current view: {{buyer_facing_status_label}} for {{intended_operation_label}}
```

Do not print run IDs, geometry hashes, provider HTTP status, or Factor progress in the header.

## Advisor’s view

### Narrative objective

Give the directional conclusion immediately. Describe the natural foundation, name the controlling factor, and state what that means for the buyer’s intended cattle use. Do not describe what RangeMatch, Mireye, or an investigation “found,” “returned,” “searched,” or “failed to find.”

### Template

```text
{{direct_directional_judgment}}

{{natural_foundation_in_plain_language}}

{{controlling_factor_and_practical_implication}}
```

### Recommended pattern

```text
This land has {{directional_natural_foundation}} for {{intended_operation_label}}, but {{controlling_environmental_factor}} currently controls the case.

{{terrain_vegetation_climate_soil_synthesis}}

{{why_the_controlling_factor_changes_practical_cattle_use}}
```

### Requirements

- 2-3 short paragraphs.
- First sentence contains a judgment.
- Describe the land, not the data pipeline.
- Use no more than one or two decision-relevant numbers on Page 1.
- Do not state suitability score, stocking rate, herd size, or purchase advice.

## How this land naturally reads

### Narrative objective

Give the reader a coherent mental picture of the property. Explain how terrain, vegetation, water, climate, and soil work together. The five domains are reasoning inputs, not visible subsections.

### Template

```text
{{landscape_character_and_terrain_pattern}}

{{vegetation_distribution_and_natural_forage_interpretation}}

{{climate_soil_and_water_relationship}}

{{whole_property_natural_resource_implication}}
```

### Required reasoning moves

The prose should perform at least two of the following when supported:

- explain whether mapped acreage is likely to be used evenly or unevenly;
- connect water distribution to practical use of vegetation;
- distinguish local point conditions from the broader parcel pattern without exposing technical labels;
- explain how terrain and vegetation structure interact;
- explain how climate and soil support or constrain vegetation persistence;
- identify whether the controlling factor can make otherwise favorable resources less useful.

### Prohibited evidence narration

Do not write:

```text
Mireye returned...
RangeMatch found...
The investigation did not produce...
The API showed...
No result was available...
The sampled field was...
```

Instead write the bounded insight:

```text
The property should not currently be planned as though dependable livestock water is already available.

Vegetation appears spatially mixed, so the mapped acreage should not automatically be treated as equally useful grazing ground.

Terrain does not currently appear to be the main natural limitation, although local steeper areas may shape how cattle use the parcel.
```

## What your plan changes

### Render condition

Render when the buyer’s operation type, grazing months, or other stated plan changes or narrows the interpretation.

### Template

```text
Because your intended use is {{user_plan_in_plain_language}}, {{how_the_resource_requirement_changes}}.

{{why_this_makes_the_case_more_or_less_achievable}}

{{remaining_condition_that_still_controls_the_view}}
```

### Requirements

- Explain the operating meaning of the answer; do not merely repeat it.
- If status remains unchanged, state what became more specific.
- Never manufacture change for Demo effect.
- Never alter physical facts based on a user answer.

## What would change my view

### Narrative objective

State the positive and negative conditions that would materially strengthen or weaken the current interpretation. This is the core expression of advisory judgment.

### Template

```text
I would become more confident if:

- {{positive_condition_1}}
- {{positive_condition_2_optional}}
- {{positive_condition_3_optional}}

I would become less confident if:

- {{negative_condition_1}}
- {{negative_condition_2_optional}}
- {{negative_condition_3_optional}}
```

Conditions must describe meaningful natural-resource evidence, not generic diligence activity. They may not introduce unsupported thresholds.

## To refine this assessment

### Narrative objective

Invite the user to provide the one environmental information package that would most improve the judgment. State what more precise assessment becomes possible afterward. Do not use an interrogative heading or audit-style demand.

### Standard Water copy

When `WATER` is controlling, use:

```text
Share the property’s livestock-water sources and their normal months of availability. With that information, I can give you a more precise assessment of how well the land supports your intended cattle use.
```

### Generic template

```text
Share {{highest_value_environmental_information}}. With that information, I can {{more_precise_judgment_enabled}}.
```

### Allowed information categories

- grazing months or operation type;
- water-source type, approximate location, seasonal availability, dry-year history, and photographs;
- pasture photographs;
- vegetation or grazing-history records;
- dry-year supplementation history;
- ecological or soil observations tied to an existing gap.

### Prohibited categories

- title, easement, or legal entrance material;
- electricity, utilities, fences, corrals, chutes, gates, loading, or buildings;
- purchase, appraisal, financing, or insurance material.

## Optional copy-ready request

Render only when the requested environmental information can be expressed as a short message to a seller, operator, land manager, or buyer.

```text
{{copy_ready_environmental_request}}
```

The message must remain subordinate to the advisory interpretation. It is not a substitute for “What would change my view.”

## Page 1 scope footer

```text
This is a preliminary cattle-land interpretation based on a confirmed parcel, sourced environmental evidence, reviewed cattle-land knowledge, and the buyer information currently available. It is not a stocking-rate, water-right, appraisal, insurance, legal-access, or purchase opinion.
```

When `Additional Property Context` is rendered on Page 2, Page 1 may add only this neutral pointer beneath the scope footer:

```text
Additional mapped property context is summarized in the Appendix and does not affect the natural-foundation judgment above.
```

Do not interpret road, access, building, utility, fence, or facility context elsewhere on Page 1.

---

# PAGE 2 - APPENDIX

## Header

```text
RANGEMATCH
Appendix
Natural evidence and additional property context
```

## A. Environmental Evidence Retrieved

Required columns:

| Domain | Evidence | Result | Spatial meaning | Provider | Underlying source |
|---|---|---|---|---|---|
| `{{domain}}` | `{{buyer_facing_evidence_label}}` | `{{formatted_value_and_unit}}` | `{{POINT_OR_PARCEL_OR_CONTEXT}}` | `{{MIREYE_OR_RANGEMATCH_SUPPLEMENT_OR_CORE}}` | `{{source_name_and_optional_vintage}}` |

### Row inclusion rule

Include a row only when:

```text
value is non-null and non-empty
AND evidence status is RETRIEVED or another explicitly displayable accepted state
AND spatial semantics are present
AND provider and source provenance are present
AND the observation passed the semantics gate
```

Exclude:

- null/empty values;
- failed or unavailable fields;
- rejected observations;
- placeholders;
- internal IDs and hashes;
- duplicated observations that do not add a different spatial or temporal meaning.

Zero is a valid value and must not be removed solely because it is zero. Its spatial meaning must be stated precisely.

### Provider labels

```text
MIREYE
RANGEMATCH_CORE
RANGEMATCH_SUPPLEMENT
USER_SUPPLIED_UNVERIFIED (only when intentionally included and clearly separated)
```

### Appendix footer

```text
Only retrieved, non-empty evidence is shown. Missing, failed, unavailable, and rejected observations remain in the technical record but are omitted from this buyer appendix. Point and context observations must not be interpreted as parcel-wide measurements.
```

## Dynamic provenance summary

The report may include a generated line such as:

```text
Mireye supplied {{mireye_displayed_observation_count}} of {{total_displayed_observation_count}} displayed environmental observations. RangeMatch added {{supplement_displayed_observation_count}} targeted parcel-wide supplements and {{core_displayed_observation_count}} confirmed-geometry derivations.
```

All counts must be computed from the current environmental evidence rows. Never hard-code the numbers.

## B. Additional Property Context

### Purpose

Translate a small number of already-retrieved non-natural observations into useful buyer context without allowing them to influence the natural cattle foundation judgment.

This section is optional and omitted entirely when no eligible non-empty observations exist.

### Required table

| Topic | What we can say | How to read it | What it does not establish |
|---|---|---|---|
| `{{context_topic}}` | `{{bounded_observation}}` | `{{plain_language_context_interpretation}}` | `{{explicit_non_conclusion}}` |

### Eligible context

- mapped road contact or nearest mapped road already present in the run;
- already-retrieved built or developed-land context;
- other human/property context explicitly classified `APPENDIX_ONLY`.

Do not render owner identity, valuation, mortgage, title opinion, zoning legality, inferred utility availability, or unverified facility suitability.

### Governing rules

```text
HUMAN_ACCESS_INFRA_APPENDIX_ONLY = true
maximum_rows = 4
non_empty_retrieved_values_only = true
may_trigger_new_collection = false
may_trigger_F07 = true
collection_role = APPENDIX_CONTEXT_COLLECTOR
collection_is_fail_soft = true
enters_natural_cattle_profile = false
enters_primary_llm_workbench = false
may_change_conclusion = false
may_be_controlling_factor = false
may_generate_question_or_next_action = false
```

### Interpretation examples

Allowed:

```text
Topic: Mapped road context
What we can say: A mapped road reaches the parcel boundary.
How to read it: The parcel is physically adjacent to the mapped road network.
What it does not establish: This does not establish a legal entrance, usable road condition, or recorded access.
```

Not allowed:

```text
The property has easy access.
Legal access is present.
Request title documents before continuing.
The road makes the property suitable for cattle.
```

The context interpretation may be produced from validated structured fields, but it must remain outside the primary conclusion and must pass a dedicated Appendix-only Validator.

---

## 4. LLM narrative contract

The LLM receives only:

- accepted Natural Cattle Profile statements;
- approved Knowledge Cards selected for active domains;
- current Deal Context;
- the deterministic conclusion skeleton;
- allowed evidence references;
- word and section budgets.

The LLM does not receive authority to:

- add observations;
- choose supplements;
- change evidence status or semantics;
- change the controlling factor without allowed structured support;
- create a stocking, legal, insurance, price, or purchase conclusion;
- write Knowledge Card principles as measured parcel facts.

The system validates structured narrative fields before PDF rendering. Invalid LLM output uses a deterministic narrative fallback; it does not silently substitute a fixture or preserve invalid prose.

## 5. Recommended page-one word budget

| Section | Target words |
|---|---:|
| Advisor’s view | 90-150 |
| How this land naturally reads | 180-300 |
| What your plan changes | 60-110 |
| What would change my view | 60-120 |
| To refine this assessment | 30-70 |
| Optional copy-ready request | 30-65 |
| Scope footer | 30-55 |

The renderer may omit a non-material domain paragraph to protect readability. It must not shrink body text below the approved readable minimum merely to preserve every optional sentence.

## 6. Final validation checklist

- [ ] Parcel is confirmed and address matches the report run.
- [ ] Conclusion uses an allowed status.
- [ ] Controlling factor is explicit.
- [ ] Page 1 contains no internal IDs or workflow jargon.
- [ ] Page 1 describes the land and its implications, not the search or collection process.
- [ ] Page 1 contains no “Mireye returned,” “RangeMatch found,” or equivalent provider narration.
- [ ] The five domains were checked internally but are not rendered as empty or mechanical chapters.
- [ ] The natural-resource story connects at least two domains into an insight.
- [ ] “What would change my view” contains meaningful positive and negative conditions.
- [ ] Every parcel statement has an evidence reference.
- [ ] General interpretation has approved knowledge support.
- [ ] Point/context evidence is not promoted to parcel.
- [ ] Missing water is not described as no water.
- [ ] No stocking, AUM, herd-size, legal, insurance, price, or purchase conclusion appears.
- [ ] Access/title/infrastructure do not drive the narrative.
- [ ] User answer is attributed and does not alter physical facts.
- [ ] Appendix contains only non-empty accepted observations.
- [ ] Appendix identifies spatial meaning, provider, and source.
- [ ] Mireye contribution counts are generated from current rows.
- [ ] Additional Property Context is omitted when empty and contains no more than four rows.
- [ ] F07 ran only through the time-bounded, fail-soft Appendix collector.
- [ ] F07 output did not enter the environmental packet, Profile, LLM, conclusion, question, or next action.
- [ ] Each context row states what it does not establish.
- [ ] No Appendix-only context entered the Natural Cattle Profile, primary LLM workbench, controlling factor, question, or next action.
- [ ] PDF renders without clipping, overflow, or unreadably small type.
- [ ] Advisor narrative may span multiple pages as needed; no qualified insight is dropped only to force a page count.
- [ ] Appendix begins on a new page after the advisor narrative ends.
