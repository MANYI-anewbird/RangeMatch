# RangeMatch Documentation and Traceability Standard

> Status: `CANONICAL`
> Audience: RangeMatch builders, scientific reviewers, and Mireye reviewers
> Submission language: English
> Last updated: 2026-08-07

## 1. Language Policy

All documents used to build, review, validate, or submit RangeMatch must be written in English. This includes scientific evidence, Operation Profiles, variable definitions, data-source mappings, decision logic, limitations, validation records, and Mireye field audits.

The only canonical document maintained in Chinese is `RANGEMATCH_AGENT_BUILD_PLAN.md`, which is the owner-facing execution checklist. Chinese research notes and prior reports may remain in `backups/`, but they are non-canonical and must not be cited by the runtime or submitted as scientific specifications.

## 2. Required Traceability Chain

Every production relationship must support this complete chain:

```text
Source record
  -> supported scientific claim
  -> species requirement
  -> required Land Variable
  -> verified Mireye field or external source
  -> deterministic signal rule
  -> MatchResult explanation
```

Scientific evidence establishes whether a variable matters. It does not establish that Mireye provides that variable. Data availability is audited separately.

All geographic and descriptive context must follow `CONTEXT_DECOMPOSITION_STANDARD.md`. Place names are lookup/provenance fields, not causal suitability inputs. Measurable raw values are preserved before any reviewed deterministic interpretation.

## 3. Canonical Scientific Deliverables

1. `SOURCE_REGISTRY.md` - complete, human-verifiable source records.
2. `SPECIES_REQUIREMENTS_REGISTRY.md` - reviewed Cow-Calf and Sheep relationships.
3. `UNIFIED_LAND_VARIABLE_REGISTRY.yaml` - shared Land Facts and Context Variables.
4. `DATA_SOURCE_AND_MIREYE_AUDIT.yaml` - field availability, version, derivation, and external-data requirements.
5. `FACTOR_FREEZE_GATE.yaml` - unified stop condition for Factor research and implementation depth.
6. `DEMO_ACCEPTANCE.md` - four-Factor demo acceptance and reusability validation gate.
7. Factor-family audits such as `F05_CLIMATE_DROUGHT_ATOMICITY_AND_SOURCE_AUDIT.md` and matching data-source YAML files.
8. Cross-parcel validation plan, selection criteria, and result schema (`CROSS_PARCEL_VALIDATION_PLAN.md`, `CROSS_PARCEL_SELECTION_CRITERIA.yaml`, `CROSS_PARCEL_VALIDATION_RESULT_SCHEMA.yaml`).

Deterministic relationship behavior and golden tests are maintained in versioned Factor rule files such as `F01_TOPOGRAPHY_DETERMINISTIC_RULES.yaml` and `F01_TOPOGRAPHY_GOLDEN_TESTS.yaml`. These files consume reviewed requirements; they do not create scientific claims.

Land Fact instances conform to `LAND_FACT_SCHEMA.yaml`. Variable definitions
remain in `UNIFIED_LAND_VARIABLE_REGISTRY.yaml`; runtime observations must also
preserve independent applicability, coverage, quality, provenance, and
limitations. The Matching Engine must not infer applicability from value
presence or infer complete coverage from adapter success.

## 4. Operation Profile Construction

An Operation Profile is assembled from reviewed requirement records. It is not a free-form LLM summary.

Each requirement must contain:

- a stable `requirement_id`;
- the operation and production system;
- a narrow accepted claim;
- the required variable IDs;
- source IDs supporting that claim;
- conditions and limitations;
- relationship and numeric-rule status;
- human review status and date.

An Operation Profile may include only requirements whose `review_status` is `VERIFIED`. A qualitative relationship may be accepted while its numeric rule remains `NOT_APPROVED`.

## 5. Evidence Acceptance Gate

A relationship may become `ACCEPTED_RELATIONSHIP` only when:

- at least one complete and accessible authoritative source supports it;
- the claim does not exceed the source;
- study location and rule applicability are recorded separately;
- livestock, production system, environmental context, and limitations are explicit;
- required variables exist in the Unified Land Variable Registry;
- missing data remains `UNKNOWN`;
- numeric thresholds are reviewed independently;
- the LLM is not required to invent facts or scientific logic.

## 6. Mireye Submission Package

The review package should include the four canonical scientific deliverables, the deterministic rule specification, the Profile version manifest, and representative MatchResult traces. Every referenced Mireye field must include the exact field ID, inspected API/catalog version, access date, spatial semantics, and whether the value is direct, source-derived, parcel-derived, or unavailable.
