# Final Factor Research Intake — 2026-08-07

> Material: `Executive_Summary_US_Grazing_Factors_Final.pdf`  
> Author metadata: ChatGPT Deep Research  
> Language: English  
> Status: `PRIMARY RESEARCH BACKUP / EVIDENCE CANDIDATE`  
> Runtime rule status: Not approved

## Intake Decision

This English report is the primary research backup for the initial U.S. shared-factor investigation. It supersedes the earlier Chinese draft for working-reference purposes. The Chinese copy remains preserved for provenance and is not deleted.

The report is accepted as support for:

- the initial 10-factor candidate set;
- shared Land Facts with species-specific interpretation;
- candidate U.S. data-source families;
- validation design and scientific guardrails;
- hypotheses for later Evidence Registry ingestion.

It is not accepted as final authority for numeric thresholds, factor weights, hard constraints or production rules.

## Candidate Shared Core Factors

1. `F01` Terrain & Slope
2. `F02` Herbaceous (Grass/Forb) Cover
3. `F03` Shrub / Woody Browse Cover
4. `F04` Herbaceous Production (Forage Signal)
5. `F05` Soil / Site Water Capacity
6. `F06` Livestock Water Availability
7. `F07` Livestock Water Distribution
8. `F08` Precipitation
9. `F09` Drought Exposure / Variability
10. `F10` Flood / Wetness Exposure

These remain candidates until each Factor passes definition, evidence, data-coverage and rule review.

## Improvements Over the Earlier Draft

- Uses a U.S. grazing-land framework instead of Texas-only factor logic.
- Treats Cow-Calf, Sheep and Goat as peer profiles.
- Separates shared factors from species-specific rules.
- States that modeled production is not carrying capacity.
- Explicitly warns against universal thresholds.
- Treats missing mapped water as `UNKNOWN / NEEDS_VERIFICATION` rather than proof of no water.
- Includes a 10-factor data-mapping table, validation protocol and versioning guardrails.
- Provides a named source list on the final page.

## Remaining Evidence Gaps

The report still uses internal citation markers such as `【3†L198-L202】`. The final page names source families, but does not provide complete bibliographic records or URLs mapping every marker to an exact source. Before Evidence Registry admission, each supporting claim still requires:

- exact title and issuing organization;
- author where applicable;
- publication year/version;
- stable URL or document identifier;
- relevant page/section;
- study population and production system;
- geographic/ecological applicability;
- exact supported claim and limitations.

## Claims Requiring Special Review

- Cattle statements such as “typically avoid slopes `>20–30%`.”
- Sheep statements such as use of slopes up to approximately `45%`.
- Species diet percentages such as cattle `~70% grass`.
- Cattle statements such as water distance `<1.5 mi` and related distribution limits.
- Sheep/goat statements such as goats being “even more independent,” traveling farther, or requiring less water.
- Statements such as “high shrub cover penalizes cattle but boosts goats” without browse-species, palatability, density and accessibility conditions.
- Any example thresholds in the deterministic rule templates.
- Statements that a factor should be High/Medium/Low priority.
- Any implication that a high-production signal directly predicts viable stocking.

Rule-template values in the PDF are examples, not locked Matching Engine configuration.

All statements above are `candidate_evidence_hypotheses`. They must not enter Base Rules until the original source, studied production system, measurement method and applicability have been confirmed claim by claim.

## Mireye Verification Requirement

The PDF describes several possible Mireye or imagery-derived capabilities. These are hypotheses until checked against Mireye's actual field catalog. Do not assume that Mireye directly provides:

- herbaceous or shrub fractional cover;
- forage-production biomass;
- pond, tank or trough object detection;
- water-distribution distance rasters;
- soil proxies from imagery;
- all listed flood or wetness indices.

The Mireye field audit must map each candidate Factor to actual named fields, coverage, resolution, provenance and limitations.

## Evidence-Ingestion Rule

No claim from this backup may affect MatchResult until its original source has been recovered, scoped, reviewed and attached to a versioned Scientific Rule or Limitation Record.

Study location and rule applicability must be recorded separately. A Texas source does not automatically justify a Texas-specific rule; environmental differences should be represented through measurable Land Factors whenever possible.

## Next Use

Use this backup as the starting document for the formal U.S. factor review. Do not create another broad Factor summary. Begin with `F01 Terrain & Slope`, build its Evidence Registry entries for all three Profiles, and then create a Factor Decision Table assigning it one of:

- `IN MVP SHARED CORE`
- `CONTEXT ONLY`
- `DILIGENCE ONLY`
- `DEFERRED`
- `REJECTED / DUPLICATE`
