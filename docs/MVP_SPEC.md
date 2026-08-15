# RangeMatch MVP Specification

> Status: `LOCKED COMPETITION PROTOTYPE BASELINE`
> Last updated: 2026-08-08
> Knowledge and product data scope: United States
> Initial validation scope: Selected U.S. environments and reference cases
> Intended use: Competition MVP and first executable vertical slice

> Current implementation and report status: see `RANGEMATCH_PRODUCT_AND_AGENT_CODE_FLOW.md`. This specification defines product/scientific scope; later implementation milestones do not reopen its frozen rules.

## 1. Product Definition

RangeMatch is a constrained agricultural-land decision agent. Fixed, reviewed, and versioned agricultural knowledge defines the rules; physical-world data supplies land facts; deterministic and explainable logic evaluates the match; and the LLM interprets intent, plans and executes the investigation, and explains results without changing the science.

RangeMatch answers two questions:

1. Is this parcel a plausible match for the user's intended agricultural operation?
2. If the intended operation is a weak match, is another currently supported operation more appropriate for further investigation?

Core principle:

> The land did not fail. The match failed.

## 2. MVP Scope

### 2.1 Scope dimensions that must remain separate

- `knowledge_design_scope`: Reusable agricultural relationships designed for U.S. grazing systems.
- `data_coverage_scope`: The geography in which Mireye and approved supporting data can supply the required Land Facts; currently the United States.
- `initial_validation_scope`: Selected U.S. environment-by-operation combinations used to detect obvious scientific and engineering failures.
- `demo_scope`: One or more selected U.S. parcels used in the competition demonstration.
- `evidence_coverage`: The actual geography, livestock, production system, environment, and conditions represented by reviewed sources.

U.S. data coverage does not mean that every U.S. environment has been scientifically validated. A Base Profile must not be presented as an unqualified global biological truth.

### 2.2 Geographic boundary

- The knowledge architecture and evidence search target U.S. grazing systems.
- Mireye is the primary physical-world data layer and currently defines a U.S.-only operational boundary.
- The MVP is a preliminary screening product, not a local ranch-management prescription.
- No threshold is assumed to apply uniformly across all U.S. ecological systems.
- The Land Profile preserves ecological and rangeland context to support scoped interpretation and future modifiers.
- Texas may supply a demo parcel or reference case, but no state is the default scientific or validation boundary.

### 2.3 Peer Operation Profiles

The two MVP Operation Profiles are peers:

- `Cow-Calf Operation Base Profile`
- `Sheep Grazing Base Profile`

There is no architecture-level primary or secondary Profile. Priority comes only from user intent.

Every Profile records:

```yaml
knowledge_design_scope: United States
data_coverage_scope: United States
initial_validation_scope: selected U.S. environments and reference cases
demo_scope: one or more selected U.S. parcels
evidence_coverage: source-specific
regional_modifiers: optional_and_evidence_gated
```

The MVP excludes confined poultry, industrial hog production, confined dairy, aquaculture, crop suitability, solar, timber, and other non-grazing land uses.

### 2.4 Intended user

The initial user is a serious ranch buyer or ranch operator performing preliminary screening of a U.S. parcel.

### 2.5 Interaction boundary

The competition prototype evaluates **one parcel per run**. It does not provide batch parcel search, portfolio ranking, regional site discovery, or an ICP Finder workflow. Historical cross-parcel fixtures remain engineering validation evidence, not a user-facing batch feature.

### 2.6 Terminology

`Cow-Calf Operation` means a breeding production system maintaining cows and raising calves. It must never be translated or modeled as calf finishing or feedlot production.

## 3. User Modes

### 3.1 Goal-directed mode

The user provides a parcel and identifies an intended operation. The selected Profile is evaluated first because it represents the user's goal. Other peer Profiles may be shown as alternatives.

Example:

> Can I realistically operate a cow-calf grazing system on this property?

### 3.2 Discovery mode

When the user does not specify an operation, the system evaluates all currently reviewed and supported Profiles equally:

```text
Land Profile x Cow-Calf Profile
Land Profile x Sheep Profile
```

The comparison covers signals, constraints, confidence, evidence coverage, and unknowns. The system must say:

> Among currently supported operation models...

It must not claim to discover the objectively best use of the land.

## 4. Minimum Competition Loop

```text
Selected U.S. parcel
        -> two peer Operation Profiles
        -> exactly 8 reviewed shared Factor families (F01-F08)
        -> Mireye plus minimal authoritative external data
        -> normalized Land Profile
        -> deterministic relationship evaluation
        -> explicit unknowns and cross-Profile comparison
        -> REDIRECT when justified
        -> grounded LLM explanation
```

A complete ontology, full Reference Case Library, similarity engine, and national numeric score are not prerequisites for this loop.

## 5. Decision Output

- `ADVANCE`: The operation merits continued diligence under current evidence.
- `REVIEW`: The operation may fit, but material limitations or unresolved issues remain.
- `HOLD`: Evidence is insufficient for a reliable screening decision.
- `REDIRECT`: The intended operation is a weak match and another supported operation merits investigation.
- `REJECT`: Used only when reliable facts trigger a reviewed hard constraint.

The v1 relationship vocabulary is:

```text
STRONG_RESOURCE_SIGNAL
MODERATE_RESOURCE_SIGNAL
LIMITING_SIGNAL
CONTEXT_DEPENDENT
UNKNOWN
NEEDS_VERIFICATION
```

These signals must not be silently converted into a pseudo-precise numeric score.

Every MatchResult includes:

- preliminary suitability and decision label;
- evidence coverage and confidence limitation;
- supporting and limiting signals;
- reviewed hard constraints, if any;
- `KNOWN`, `INFERRED`, `UNKNOWN`, and `NEEDS_VERIFICATION` states;
- alternative-operation comparison;
- prioritized diligence actions;
- data, source, rule, engine, and Operation Profile versions.

## 6. Initial Factor Scope

The demo is limited to exactly eight reviewed Factor families. The canonical scope and execution order are maintained in `docs/DEMO_FACTOR_SCOPE.md`.

1. `F01` Topography
2. `F02` Herbaceous Resource
3. `F03` Livestock Water
4. `F04` Soil, Wetness, and Ecological Site
5. `F05` Climate and Drought Exposure
6. `F06` Parcel Configuration
7. `F07` Road and Physical Access Context
8. `F08` Woody and Shrub Vegetation Structure

No `F09` or later Factor is part of the time-constrained demo. Flood/FEMA, fencing, infrastructure, zoning/legal-right automation, predator exposure, poisonous plants, and additional Factor families remain post-demo backlog items.

This list fixes scope, not scientific conclusions. A Factor enters runtime only after source-by-source review, atomic-variable definition, data audit, deterministic-rule review, testing, and human approval.

Shared Land Facts retain one definition. Their scientific meaning, relationship status, limitations, and deterministic interpretation are defined independently for each Operation Profile.

## 7. Agent Authority Boundary

The Agent may:

- identify the parcel and interpret user intent;
- load approved Profile and rule versions;
- create an investigation plan from the approved Factor whitelist;
- choose approved tools and data sources, including retry and fallback behavior;
- preserve unavailable facts as unknown;
- explain deterministic MatchResults;
- propose prioritized diligence actions.

The Agent may not:

- add an unapproved scientific dimension;
- modify a Factor, relationship, threshold, weight, or hard constraint;
- invent a score or decision label;
- convert missing data into a known fact;
- write LLM conclusions into permanent Land Facts;
- override the Matching Engine;
- promote a research hypothesis into a production rule.

A newly discovered candidate Factor is sent to human review and cannot affect the current MatchResult.

## 7.1 Dynamic diligence workflows

Dynamic workflows may run alongside the frozen Factors without becoming new Factors:

- Mireye Property Diligence / lookup for parcel and jurisdiction context;
- Mireye Land Read for rapid point-level physical context;
- Mireye Hazards Read for flood, wetland, and wildfire-related triggers;
- later Regulatory & Land Rights investigation using current official sources.

These outputs remain separately typed as point context, diligence evidence, or investigation findings. They do not replace parcel-wide canonical Land Facts, alter the Matching Engine, or constitute final legal advice.

## 8. Knowledge, Evidence, and Data Boundaries

### 8.1 Canonical traceability chain

```text
Source record
  -> supported claim
  -> Species Requirement
  -> required Land Variable
  -> Mireye field or external data method
  -> deterministic signal rule
  -> MatchResult explanation
```

The canonical scientific documents are:

1. `SOURCE_REGISTRY.md`
2. `SPECIES_REQUIREMENTS_REGISTRY.md`
3. `UNIFIED_LAND_VARIABLE_REGISTRY.yaml`
4. `DATA_SOURCE_AND_MIREYE_AUDIT.yaml`

Each implemented Factor also requires a deterministic rule specification and golden-test suite. For F01 these are `F01_TOPOGRAPHY_DETERMINISTIC_RULES.yaml` and `F01_TOPOGRAPHY_GOLDEN_TESTS.yaml`.

The source registry and data audit are independent. Evidence that a variable matters does not prove that Mireye supplies it.

### 8.2 Evidence governance

Every source record must include a stable ID, complete title, authors or organization, year, source type, accessible URL or DOI, study scope, supported claim, unsupported extrapolations, applicability, limitations, evidence strength, and review status.

`study_location` and `rule_applicability` are separate fields. A study performed in Texas does not automatically create a Texas-only rule or a U.S.-wide rule.

Controlled applicability classes are:

```text
UNITED_STATES
MULTI_REGION_US
ECOLOGICAL_SITE_SPECIFIC
REGIONAL
STATE_POLICY_SPECIFIC
```

### 8.3 Geography governance

> Geographic names must not substitute for measurable environmental conditions. Climate, terrain, soil, vegetation, water, and drought must be represented as explicit data. State-specific rules are reserved for legal constraints, policy, or scientifically demonstrated regional relationships that cannot be represented adequately through those variables.

The complete implementation standard is defined in `CONTEXT_DECOMPOSITION_STANDARD.md`. Coordinates and parcel geometry are spatial lookup keys. They do not receive suitability weight by themselves unless a separately reviewed scientific relationship requires a coordinate-derived variable.

The system should preserve raw measurable values and their uncertainty before applying any classification. Numeric representation is preferred when meaningful, but controlled categorical variables are retained where arbitrary numeric encoding would create false precision.

Do not write:

- `Texas cattle prefer lower slopes.`
- `Texas is drought-prone, so reduce cattle suitability.`

Write scoped relationships instead:

- `Topography can affect cattle grazing distribution; direction and magnitude depend on environmental and management context.`
- `Drought exposure affects forage reliability and grazing risk.`

Before creating a Regional Modifier, reviewers must establish that:

1. measurable Land Variables cannot adequately express the difference;
2. the place name is more than the source location;
3. the relationship itself changes rather than only the input values;
4. authoritative evidence supports the change;
5. the issue is not legal or administrative and therefore better handled by diligence logic.

Legal and policy matters include water rights, zoning, permits, environmental restrictions, and fencing law. Regional biological context may include ecological-site baselines, toxic plants, parasites, predators, and wildlife risk.

### 8.4 Atomic Land Facts and derived metrics

Every Land Fact records:

- stable variable ID and definition;
- value and unit;
- spatial and temporal semantics;
- source and source version;
- acquisition time and freshness;
- confidence and resolution;
- observed, source-derived, parcel-derived, user-provided, or field-only status;
- missing-data state.

Every Land Fact must conform to `LAND_FACT_SCHEMA.yaml` and store six distinct
trust dimensions in addition to its variable identity:

```text
observation + source + applicability + coverage + quality + provenance + limitations
```

A returned value is not proof that the source is scientifically applicable to
the parcel. The Matching Engine must evaluate Land Facts in this order:

```text
Applicability Gate
→ Coverage Gate
→ Provenance / Quality Gate
→ Variable Derivation
→ Scientific Relationship Evaluation
→ Operation Comparison
```

For the MVP, an approved aggregate source may provide limited context when its
coverage is `COVERAGE_UNQUANTIFIED`; this caps confidence and prohibits a strong
Factor signal. Pixel-level raster verification is an optional enhancement path,
not an MVP hard dependency. Adapter success and coverage completeness are
separate states.

Operation-specific results such as `accessible_grazing_area` are derived MatchMetrics, not permanent Land Facts.

Explicit non-equivalences include:

```text
NHD feature != verified livestock water source
shrub cover != palatable browse availability
USGS 3DEP != rock-outcrop cover
parcel-to-water minimum distance != livestock water accessibility
point slope != parcel slope distribution
```

### 8.5 Analysis Results

Analysis Results are stored separately from Land Facts. They preserve all input versions and intermediate relationship evaluations. Identical inputs and versions must produce identical structured results.

## 9. Scientific and Profile Freeze Gate

A relationship may be included in a production Profile only when:

- at least one complete, accessible, authoritative source supports the narrow claim;
- the accepted claim does not exceed the evidence;
- livestock and production system are explicit;
- study scope, applicability, environmental conditions, management context, and limitations are recorded;
- all required variables exist in the Unified Land Variable Registry;
- data availability and derivation have been audited independently;
- missing data produces `UNKNOWN` or `NEEDS_VERIFICATION`;
- numeric rules have a separate approval status;
- human review status is `VERIFIED`.

Required status separation:

```yaml
relationship_status: ACCEPTED_RELATIONSHIP
numeric_rule_status: NOT_APPROVED
review_status: VERIFIED
```

`ACCEPTED_RELATIONSHIP` never implies that a threshold, penalty curve, weight, or hard exclusion has been approved.

## 10. Explicitly Unsupported Conclusions

The MVP does not output or guarantee:

- exact carrying capacity;
- profitability or investment return;
- probability of operating success;
- legal advice;
- confirmed water rights;
- unverified well yield or water reliability;
- unverified fencing quality;
- unverified actual forage productivity.

These issues produce `UNKNOWN` or `NEEDS_VERIFICATION` and a corresponding diligence action.

## 11. Validation Protocol

Select 6-10 Verified Operation Reference Cases across environment-by-operation combinations, including where feasible:

- Great Plains cow-calf grazing;
- Rocky Mountain or Intermountain rugged grazing;
- western sheep grazing;
- humid Southeast pasture;
- drought-constrained land;
- flood- or wetness-constrained land;
- a mixed-livestock operation.

### Known-operation validation

The verified real-world operation should normally be evaluated as a plausible fit. A material mismatch triggers review of source applicability, Profile relationships, variable quality, deterministic rules, and unknown handling.

### Cross-use validation

Different parcels should produce meaningfully different Profile signals. The system must not mechanically recommend cattle for every parcel.

A reference operation is not ground truth for optimal land use. Real operations also reflect owner preference, markets, infrastructure, labor, financing, and historical path dependence. Reference cases are sanity checks, not causal proof.

## 12. MVP Release Gate

- The eight demo Factor families (F01-F08) have been reviewed and implemented to their approved demo depth.
- All production relationships are human-reviewed and versioned.
- The four canonical scientific registries are internally consistent and traceable.
- Land Facts, rules, and results preserve complete provenance.
- Mireye field IDs and catalog versions are verified rather than inferred.
- Derived variables have deterministic, versioned methods.
- The Matching Engine passes golden tests and is deterministic.
- Unknown data is never silently imputed.
- No unapproved numeric threshold or hard constraint affects a result.
- The LLM cannot alter scientific logic, signals, or decision labels.
- Reports contain no unsupported precision or guarantees.
- The lightweight validation set reveals no obvious systematic contradiction.

## 13. Current Execution Order

1. Complete the source-by-source F01 Topography audit.
2. Freeze narrow Cow-Calf and Sheep F01 relationships.
3. Complete F01 variable definitions and independent Mireye/external-data audit.
4. Define deterministic qualitative signal behavior without numeric scoring.
5. Run the F01 vertical slice through all four canonical registries.
6. Apply the same process sequentially to the remaining candidate Factors.
7. Select a demo parcel and 6-10 cross-environment U.S. reference cases.
8. Build and test the non-LLM deterministic Matching Engine before adding LLM planning and explanation.
