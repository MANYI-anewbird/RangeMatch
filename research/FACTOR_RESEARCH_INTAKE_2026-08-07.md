# Factor Research Intake — 2026-08-07

> Material: `factor-research-chatgpt-deep-research-2026-08-07.pdf`  
> Author metadata: ChatGPT Deep Research  
> Status: `BACKUP / EVIDENCE CANDIDATE`  
> Not approved for runtime rules

## 1. Intended Use

This report is retained as a research backup for:

- candidate shared core Factors;
- candidate US data sources;
- candidate species-specific relationships;
- potential Scientific Rule hypotheses;
- questions that require primary-source verification.

It must not be imported directly into the Scientific Rule Library or Matching Engine.

## 2. Useful Contributions

The report supports the current direction of selecting shared Land Factors that can be interpreted differently by three peer Operation Profiles. Its principal candidate set is:

1. Slope / terrain
2. Grass/herbaceous cover
3. Shrub/woody cover
4. Vegetation/forage productivity
5. Soil drainage
6. Water availability
7. Water distribution
8. Precipitation
9. Drought exposure
10. Flood exposure
11. Road access / parcel configuration

It also identifies useful candidate US data families:

- USGS 3DEP / DEM
- USDA NRCS SSURGO / STATSGO / Web Soil Survey
- USGS National Hydrography Dataset
- NOAA / NIDIS climate and drought products
- FEMA flood products
- MODIS / Landsat vegetation products
- parcel and road datasets

These are leads for the Factor-to-source coverage matrix, not yet confirmed field mappings.

## 3. Evidence Quality Assessment

### Acceptable as research hypotheses

- Cattle, sheep and goats can interpret grass, browse, terrain and water distribution differently.
- Precipitation and drought affect forage availability and variability.
- Remote vegetation indices do not directly prove forage species, quality or usable productivity.
- Water presence does not prove reliable supply, legal access, yield or seasonal availability.
- Soil maps and remote land-cover products require uncertainty and field-validation handling.

### Must be verified before becoming rules

- Numeric slope tolerances such as cattle `>10%` and sheep `45%`.
- Water-distance thresholds such as `250–300 m`, `500 m` or `1 km`.
- Cover thresholds such as grass or shrub `>50%`.
- Rock-cover threshold such as `>30%`.
- Consecutive rainfall rules such as `<80% of normal for two years`.
- Proposed factor importance scores and species-specific weights.
- Any claim that goats or sheep can generally travel farther from water.
- Any universal claim that well-drained soil is always more suitable for grazing.

Each threshold requires the original source, study population, production system, geographic applicability, measurement definition and uncertainty before review.

## 4. Issues Preventing Direct Rule Adoption

### Missing resolvable bibliography

The report cites tokens such as `【12†L76-L82】`, `【23†L140-L148】` and `【25†L123-L126】`, but the PDF does not contain a full reference list mapping those tokens to title, author, organization, publication year and URL. These citations are not sufficient for the Evidence Registry.

### Hard-constraint overreach

The report suggests treating absence of detected surface water or nearby known water points as a hard constraint. Remote non-detection does not establish absence of wells, tanks, seasonal sources, water infrastructure or the feasibility of adding water. The safe default is generally `UNKNOWN / NEEDS VERIFICATION`, unless an approved rule and authoritative evidence prove infeasibility.

### Arbitrary or insufficiently scoped thresholds

Several templates convert illustrative values into deterministic boundaries without enough provenance. They must remain hypotheses until individually validated.

### Regional modifier risk

The report proposes changing thresholds or factor weights by ecological region. RangeMatch should first represent regional differences through local Factor values. A Regional Modifier is allowed only when evidence shows that the factor-to-operation relationship itself changes after controlling for the measured environmental context.

### Factor-definition mixing

Some proposed Factors combine distinct concepts:

- surface-water presence, groundwater/well evidence, supply reliability and legal water access;
- roads, access rights, parcel fragmentation and internal ranch circulation;
- vegetation greenness, forage productivity, forage quality and edible species composition;
- slope, rock cover and usable grazing area.

The ontology must separate these atomic facts before matching logic is written.

## 5. Required Evidence-Ingestion Workflow

For every candidate claim:

1. Recover the original primary or authoritative source.
2. Record organization, author, title, year, URL and source type.
3. Capture the exact supported relationship without strengthening it.
4. Record animal class, production system and management assumptions.
5. Record geographic and ecological applicability.
6. Record measurement definition, units and spatial/temporal scale.
7. Classify it as biological relationship, operational relationship, contextual evidence or illustrative threshold.
8. Determine whether it supports a hard constraint, suitability relationship or limitation only.
9. Add uncertainty and missing-data behavior.
10. Submit the rule for human review and versioning.

Until all ten steps are complete, the claim remains `evidence_candidate` and cannot affect a production MatchResult.

## 6. Recommended Next Action

Use the report as the starting hypothesis list for the comprehensive US Factor Search. For each of the eleven candidate Factors:

- validate whether it belongs in the shared core;
- split it into atomic Factor definitions where necessary;
- locate authoritative US-wide or explicitly region-scoped evidence;
- compare interpretation across Cow-Calf, Sheep and Goat Profiles;
- audit whether Mireye already exposes the required field;
- record what remains field-only or legally unverifiable.

## 7. Intake Decision

`ACCEPTED AS BACKUP` — valuable for research direction and source discovery.

`NOT ACCEPTED AS SCIENTIFIC RULES` — thresholds, weights, hard constraints and citations require primary-source recovery and review.

