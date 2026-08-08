# F04 Atomicity and Source Audit — Soil, Wetness, and Ecological Site Context

> Status: `FIRST-STAGE AUDIT COMPLETE`  
> Language: English  
> Operations: Cow-Calf Operation and Sheep Grazing  
> Review date: 2026-08-07

## 1. Factor Boundary Decision

`Soil / Drainage / Ecological Site` must not be implemented as one score or one atomic Land Fact.

The v0.1 factor family is renamed:

> **F04 Soil, Wetness, and Ecological Site Context**

It contains source facts, continuous soil properties, controlled classifications, and an interpretive ecological-site reference. These objects have different semantics and must remain separable.

| Variable ID | Atomic object | Role | v0.1 decision |
|---|---|---|---|
| `VAR_F04_SOIL_MAPUNIT_COMPOSITION` | Map-unit identity, component identities, and component percentages | Source/coverage fact | `INCLUDE` |
| `VAR_F04_DRAINAGE_CLASS` | NRCS drainage class by soil component | Controlled soil property | `INCLUDE` |
| `VAR_F04_HYDROLOGIC_SOIL_GROUP` | Hydrologic soil group by component | Controlled hydrologic context | `INCLUDE AS CONTEXT` |
| `VAR_F04_AVAILABLE_WATER_STORAGE` | Available water storage over an explicitly declared depth interval | Continuous soil property | `INCLUDE CANDIDATE` |
| `VAR_F04_RESTRICTIVE_LAYER_DEPTH` | Depth to the first declared restrictive feature | Continuous/component property | `INCLUDE CANDIDATE` |
| `VAR_F04_SALINITY_EC` | Electrical conductivity over an explicitly declared depth interval | Continuous soil property | `INCLUDE CANDIDATE` |
| `VAR_F04_SOIL_PH` | Soil reaction over an explicitly declared depth interval | Continuous soil property | `CONTEXT CANDIDATE` |
| `VAR_F04_PONDING_FREQUENCY` | Soil-survey ponding interpretation | Controlled wetness context | `INCLUDE CANDIDATE` |
| `VAR_F04_FLOODING_FREQUENCY` | Soil-survey flooding interpretation | Controlled wetness context | `CONTEXT ONLY; dynamic hazard diligence owns flood screening` |
| `VAR_F04_ECOLOGICAL_SITE_REFERENCE` | Component-to-ecological-site identifier, correlation, and publication status | Interpretive reference | `INCLUDE WITH AVAILABILITY GATE` |

## 2. Non-Equivalences

```text
soil map unit != homogeneous soil
dominant component != whole parcel
component percentage != exact within-map-unit location
drainage class != current soil moisture
hydrologic soil group != measured infiltration rate
available water storage != forage production
soil-survey flooding frequency != FEMA flood hazard
ecological-site reference != current vegetation state
ecological-site reference != operation suitability score
reference plant community != current plant community
SSURGO value present != complete parcel coverage
```

## 3. Required Aggregation Governance

1. Preserve parcel intersections with soil map units before summarization.
2. Preserve map-unit keys, component keys, component percentages, horizons, source version, and query date.
3. Never substitute the dominant component for the entire map unit without an explicit limitation.
4. Never average controlled categories such as drainage class or hydrologic soil group as ordinal numbers.
5. For continuous horizon properties, freeze the depth interval, representative-value policy, null handling, and component/map-unit aggregation before runtime use.
6. Report coverage and uncertainty separately from the property value.
7. Keep flooding in F04 as soil/site context only; authoritative flood-hazard analysis belongs to its own Factor.

## 4. Ecological-Site Governance

NRCS Ecological Sites classify and describe land with recurring soil, vegetation, hydrology, climate, and response characteristics. The Ecological Site Description is an interpretive reference, not a direct observation of current parcel condition.

Runtime must preserve:

- ecological-site identifier and name;
- linked soil component and correlation status;
- publication/development status when available;
- source URL and access date;
- map-unit/component ambiguity;
- whether a public description is available.

Runtime must not infer:

- that the reference community is currently present;
- that a state-and-transition model state is observed remotely;
- that an ecological-site label alone favors Cow-Calf or Sheep;
- that missing public EDIT content means no ecological-site correlation exists.

## 5. First Authoritative Source Set

### `SRC_F04_001` — USDA-NRCS SSURGO

- Official page: https://www.nrcs.usda.gov/resources/data-and-reports/soil-survey-geographic-database-ssurgo
- Supports: Soil map and attribute access, including available water capacity, soil reaction, electrical conductivity, flooding frequency, and land-use interpretations.
- Does not support: Treating map units as homogeneous, current field condition, current forage production, or an operation suitability score.
- Applicability: `UNITED_STATES_SOIL_SURVEY_COVERAGE_WITH_GAPS`

### `SRC_F04_002` — USDA-NRCS Ecological Site Descriptions

- Official page: https://www.nrcs.usda.gov/getting-assistance/technical-assistance/ecological-sciences/ecological-site-descriptions
- Supports: Ecological Sites as a framework linking soils, vegetation, hydrology, climate, management response, and long-term potential.
- Does not support: Current vegetation state or direct animal-operation suitability from the site name.
- Applicability: `RANGELAND_AND_FORESTLAND_ECOLOGICAL_SITE_CONTEXT`

### `SRC_F04_003` — USDA-NRCS Ecological Site Descriptions in EDIT

- Official page: https://www.nrcs.usda.gov/publications/Ecological%20Site%20Extent%20-%20Query%20by%20Soil%20Survey%20Area%20%28Link%20to%20EDIT%29.html
- Supports: Soil Data Access linkage from soil components to the official public ecological-site repository.
- Limitation: Not all Ecological Site Descriptions are publicly available in EDIT.
- Applicability: `AVAILABILITY_DEPENDS_ON_COMPONENT_CORRELATION_AND_PUBLICATION_STATUS`

### `SRC_F04_004` — USDA-NRCS National Range and Pasture Handbook

- Official page: https://www.nrcs.usda.gov/conservation-basics/animals/livestock/national-range-and-pasture-handbook
- Supports: Ecological-site and grazing-land inventory, assessment, hydrology, erosion, and management context.
- Does not support: A universal RangeMatch soil threshold or animal ranking.
- Applicability: `UNITED_STATES_GRAZING_LAND_TECHNICAL_GUIDANCE`

## 6. First-Stage Decision

F04 is scientifically relevant but is not yet approved for a directional Cow-Calf or Sheep signal. The next gate is a data audit:

1. inspect Mireye soil fields and provenance;
2. verify USDA Soil Data Access access for the CPER parcel;
3. quantify map-unit and component coverage;
4. verify ecological-site linkage availability;
5. only then audit narrow species relationships.
