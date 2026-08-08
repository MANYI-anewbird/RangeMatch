# F01 Evidence Registry — Topography

> Review status: `PRELIMINARY EVIDENCE REVIEW COMPLETE`  
> Factor decision: `IN MVP SHARED CORE — CONDITIONAL`  
> Rule status: `NO PRODUCTION RULES APPROVED`  
> Last reviewed: 2026-08-07

## 1. Atomicity Decision

`Terrain & Slope` is acceptable as a user-facing factor family, but it is not an atomic scientific variable and must not receive one combined score.

### Approved atomic Land Facts / Context Variables

| ID | Variable | Type | Role |
|---|---|---|---|
| `F01A` | `slope_degrees` and parcel slope distribution | Observed/DEM-derived Land Fact | Measures gradient; no universal species cutoff |
| `F01B` | `terrain_ruggedness_index` | DEM-derived Land Fact | Measures local terrain heterogeneity independently of mean slope |
| `F01C` | `topographic_position_class` | DEM-derived Context Variable | Distinguishes lowland, plain, open slope, upland/ridge positions |
| `F01D` | `elevation` | Observed Land Fact / context | Context for climate, vegetation and production system; not inherently good or bad |
| `F01E` | `aspect` | DEM-derived Context Variable | Context for heat, moisture, snow and seasonal forage; not inherently good or bad |

### Must be separated from F01

| Candidate | Decision | Reason |
|---|---|---|
| `rock_outcrop_cover` | `DEFERRED SEPARATE FACTOR` | Surface cover/barrier variable, not equivalent to slope or ruggedness; current Mireye catalog has no direct field |
| `cliff_gully_barrier` | `DEFERRED SEPARATE FACTOR` | Discrete movement barrier requiring geometry/object evidence |
| `accessible_grazing_area` | `DERIVED MATCH METRIC` | Operation-specific result derived from topography, water, vegetation barriers, infrastructure and approved rules; must not be stored as a permanent Land Fact |

## 2. Governance Decision

- Do not write `steeper land is always worse` as a Base Rule.
- Do not write a national threshold such as `>10%`, `>20–30%` or `45%` without scoped evidence.
- Do not infer parcel terrain from one point sample.
- Evaluate slope, ruggedness and topographic position separately.
- Treat water distance, wetness, forage distribution, season, breed and herding as interacting variables.
- `accessible_grazing_area` can only be generated after operation-specific evaluation and must preserve uncertainty.

## 3. Evidence Records

### `E-F01-001` — NRCS Illinois Livestock Distribution Guidance

- Organization: USDA Natural Resources Conservation Service
- Title: *Illinois Grazing Manual Fact Sheet — Livestock Distribution*
- Year/version: 2000; hosted by NRCS in current document repository
- Source type: Authoritative Extension/management guidance
- URL: https://www.nrcs.usda.gov/sites/default/files/2022-12/Livestock-Distribution.pdf
- Study location: Illinois guidance; not an experimental study
- Rule applicability: `Regional` management guidance; qualitative mechanism candidate for broader U.S. review
- Supported claim:
  - Livestock distribution is affected by steep slopes, cliff faces, gullies and rock outcrop.
  - Animals tend to avoid steep areas because movement and grazing are more difficult.
  - Water, vegetation, exposure, season, fencing, trails and herding can alter distribution.
- Does not support:
  - species-specific numeric slope thresholds;
  - a hard exclusion;
  - combining rock outcrop and slope into one measurement.
- Evidence strength: `MODERATE` for qualitative management relationship
- Registry status: `ACCEPTED — QUALITATIVE / SCOPED`

### `E-F01-002` — Multi-Ecosystem U.S. Beef-Cattle Topography Study

- Authors: E.J. Raynor, S.P. Gersie, M.B. Stephenson, P.E. Clark, S.A. Spiegal, R.K. Boughton, D.W. Bailey, A. Cibils, B.W. Smith, J.D. Derner, R.E. Estell, R.M. Nielson, D.J. Augustine
- Title: *Cattle Grazing Distribution Patterns Related to Topography Across Diverse Rangeland Ecosystems of North America*
- Journal: *Rangeland Ecology & Management* 75 (2021), 91–103
- DOI: https://doi.org/10.1016/j.rama.2020.12.002
- USDA-hosted PDF: https://www.ars.usda.gov/ARSUserFiles/1354/213.%20Raynor%20et%20al%202021%20REM%20cattle%20grazing%20patterns%20related%20to%20topography.pdf
- Study location: Seven continental U.S. sites spanning arid, semiarid and subtropical rangelands
- Production system: Extensive beef-cattle grazing; late growing season
- Rule applicability: `Multi-region U.S.` for qualitative topographic-context relationships
- Supported claim:
  - Rugged topography, extensive distance to water and low stock density were associated with more uneven cattle grazing distribution.
  - Gentler terrain, smaller well-watered pastures and higher stock density were associated with more uniform distribution.
  - Topographic position classes predicted distribution better than topographic wetness index in this study.
  - Direction was context-dependent: arid/semiarid cattle often favored lowlands/flats, while subtropical cattle selected upland/sloped areas where lowlands were water-inundated.
- Does not support:
  - a national monotonic slope penalty;
  - a universal numeric cutoff;
  - slope-only prediction without wetness, water and vegetation context.
- Evidence strength: `HIGH`
- Registry status: `ACCEPTED — BASE RELATIONSHIP WITH CONTEXT`

### `E-F01-003` — Colorado Shortgrass-Steppe Cattle Study

- Authors: Samuel P. Gersie, David J. Augustine, Justin D. Derner
- Title: *Cattle Grazing Distribution in Shortgrass Steppe: Influences of Topography and Saline Soils*
- Journal: *Rangeland Ecology & Management* 72 (2019), 602–614
- DOI: https://doi.org/10.1016/j.rama.2019.01.009
- USDA-hosted PDF: https://www.ars.usda.gov/ARSUserFiles/1354/152.%20Gersie%20et%20al.%202019%20REM%20Cattle%20grazing%20distribution.pdf
- Study location: Central Plains Experimental Range, Colorado
- Production system: Semiarid shortgrass-steppe cattle grazing
- Rule applicability: `Ecological-site-specific` / `Regional`
- Supported claim:
  - Topographic position class predicted cattle distribution better than a wetness index in this system.
  - Saline vegetation context changed lowland use.
  - Slope/elevation coefficients can be site-specific and difficult to generalize.
- Does not support:
  - promoting cited earlier `>10%` guidance into a U.S.-wide Base Rule;
  - treating lowlands as always preferred.
- Evidence strength: `HIGH` for this ecological system
- Registry status: `ACCEPTED — CONTEXT / LIMITATION`

### `E-F01-004` — NRCS National Range and Pasture Handbook Guidance

- Organization: USDA Natural Resources Conservation Service
- Title: *National Range and Pasture Handbook, Subpart F — Management of Grazing Lands*
- Version: June 2022 (190-645-H)
- URL: https://directives.nrcs.usda.gov/sites/default/files2/1712930380/33916.pdf
- Source type: National technical guidance
- Study location: Not a study; U.S. guidance
- Rule applicability: `United States` as management guidance with mandatory local qualification
- Supported claim:
  - Slope and distance to drinking water can reduce usable grazing capacity.
  - Adjustments apply only to the affected portion of a management unit.
  - Local guides should address livestock kind, class, breed, climate and other factors.
- Numeric tables:
  - The handbook provides general example slope adjustments, but explicitly states local guidance may be more specific and other factors influence the values.
- Does not support:
  - copying its general table directly into a national deterministic rule;
  - applying one adjustment equally to cattle and sheep.
- Evidence strength: `HIGH` as guidance; `LOW` as universal numeric threshold evidence
- Registry status: `ACCEPTED — GUIDANCE / NOT A LOCKED THRESHOLD`

### `E-F01-005` — Utah Domestic-Sheep Resource Selection Study

- Authors: E.M. Baum, T.F. Robinson, R.T. Larsen, S.L. Peterson, R.J. Shields
- Title: *Resource Selection of Domestic Sheep on Mountainous Summer Habitat in Utah, United States*
- Journal: *Rangeland Ecology & Management* 84 (2022), 117–125
- DOI: https://doi.org/10.1016/j.rama.2022.05.009
- Study location: Mountainous summer habitat near Scofield Reservoir, Utah
- Production system: Domestic range sheep; summer grazing; managed/herded context
- Sample/measurement: 27,327 GPS locations from five functioning collars, July–September 2020
- Rule applicability: `Ecological-site-specific` / Western U.S. mountain-sheep evidence
- Supported claim:
  - Sheep selected gentler terrain, higher elevation, north-facing slopes and locations closer to water in this system.
  - Slope, ruggedness, elevation, aspect and water distance are distinct predictors.
- Does not support:
  - the Base Rule `sheep are unaffected by steep slope`;
  - a universal `45%` threshold (the number is discussed through older New Mexico evidence, not established as a universal result of this Utah study);
  - assuming higher elevation itself is universally favorable.
- Evidence strength: `MODERATE-HIGH` for this study system; limited cross-region generalizability
- Registry status: `ACCEPTED — SPECIES RELATIONSHIP WITH STRONG SCOPE LIMIT`

### `E-F01-006` — Sheep Breed and Management Context

- Authors: Carrie S. Wilson, J. Bret Taylor, Jonathan W. Spiess, et al., Hailey Wilmer
- Title: *Comparison of the flocking behavior of Katahdin and Rambouillet sheep breeds in an extensive range environment using GPS technology*
- Journal: *Animal Biotelemetry* 13, Article 7 (2025)
- DOI: https://doi.org/10.1186/s40317-025-00404-6
- Study location: U.S. Sheep Experiment Station; eastern Idaho / southwestern Montana range system
- Production system: Continuously herded bands of 800–1,000 ewes with lambs
- Rule applicability: `Regional` management-context evidence
- Supported claim:
  - Breed adaptation, rearing history and continuous herding affect use of rugged extensive range.
- Does not support:
  - a direct slope-response curve;
  - a numeric terrain threshold.
- Evidence strength: `MODERATE` as context
- Registry status: `ACCEPTED — MANAGEMENT MODIFIER EVIDENCE ONLY`

## 4. Preliminary Species Relationship Decisions

### Cow-Calf Base Profile

Approved qualitative proposition:

> Topography can influence cattle grazing distribution and the share of a parcel that is effectively used, but direction and magnitude depend on ruggedness, topographic position, water distribution, wetness, forage, season and management.

Not approved:

- universal slope penalty curve;
- national cutoff;
- `steep = reject`;
- lowland preference without wetness/vegetation context.

### Sheep Base Profile

Approved qualitative proposition:

> Slope, ruggedness, elevation, aspect and distance to water can influence sheep resource selection. Sheep may operate in rugged extensive systems, but available U.S. evidence does not justify treating steep slopes as cost-free or applying a universal slope-tolerance threshold.

Not approved:

- `sheep tolerate up to 45%` as a Base Rule;
- automatic positive score for ruggedness;
- comparison with cattle expressed as a fixed numeric advantage.

## 5. Mireye Field Audit

- Catalog endpoint: https://api.mireye.com/v1/meta/fields
- Catalog version reviewed: `0.14.0`
- Review date: 2026-08-07

### Directly available

| Field | Unit | Source | Limitation |
|---|---|---|---|
| `slope_degrees` | degrees | USGS 3DEP | Point value; not parcel distribution |
| `elevation` | meters NAVD88 | USGS 3DEP | Point value |
| `aspect_degrees` | degrees | USGS 3DEP | Point value |
| `aspect_cardinal` | category | USGS 3DEP | Point value |
| `parcel_boundary_geojson` | geometry | Regrid | Enables external parcel-wide DEM computation |
| `parcel_geometry_wkt` | geometry | Regrid | Polygon only; GeoJSON preferred for multipolygons |

### Not found as direct named fields

- terrain ruggedness index;
- topographic position class/index;
- rock/outcrop cover;
- parcel slope histogram/distribution;
- operation-accessible grazing area.

### Data decision

MVP must not characterize a parcel from one `slope_degrees` point. Use parcel geometry plus USGS 3DEP to compute parcel-wide slope distribution, ruggedness and topographic position, preserving resolution and coverage metadata. `Accessible grazing area` remains a downstream operation-specific derived MatchMetric.

## 6. F01 Status Decision

| Decision dimension | Result |
|---|---|
| Shared scientific relevance | Yes |
| Remotely measurable | Partly; external parcel-wide DEM processing required |
| Differentiating power | Yes, but no automatic species bonus |
| Universal numeric threshold available | No |
| Hard constraint justified | No |
| MVP status | `IN MVP SHARED CORE — CONDITIONAL` |

Conditions for rule drafting:

1. Implement atomic topographic Land Facts.
2. Keep contextual interactions explicit.
3. Do not use point slope as parcel slope.
4. Keep numeric thresholds unapproved unless evidence-specific and scoped.

## 7. Next Evidence Tasks

- Decide the parcel-wide DEM aggregation method and spatial resolution.
- Define a standard ruggedness metric and topographic-position classification.
- Decide whether rock/outcrop coverage enters the MVP as a separate factor or remains deferred.
- Draft machine-readable EvidenceRecord schema before converting these entries to structured data.
