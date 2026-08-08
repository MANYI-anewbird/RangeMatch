# RangeMatch Source Registry

> Status: `ACTIVE - SOURCE-BY-SOURCE AUDIT`
> Language: English
> Current audited slices: `F01 Topography`, `F02 Herbaceous Resource`, `F03 Livestock Water`, `F04 Soil/Site`, `F05 Climate/Drought candidates`
> Last updated: 2026-08-07

This registry contains sources, not rules. A study location is never treated automatically as the boundary of rule applicability.

## F05 Climate and Drought Exposure

### `SRC_F05_001`

- Title: *NOAA/NCEI Direct Climate Normals NetCDF (1991–2020 gridded precipitation normals)*
- Organization: NOAA National Centers for Environmental Information
- Source type: `FEDERAL_CLIMATE_GRID`
- URL: https://www.ncei.noaa.gov/products/land-based-station/us-climate-normals
- Primary live access (CPER): https://www.ncei.noaa.gov/data/oceans/archive/arc0196/0245564/1.1/data/0-data/prcp-1991_2020-monthly-normals-v1.0.nc
- Canonical variable: `annprcp_norm`
- Runtime role: `CANONICAL_LAND_FACT` for `VAR_F05_MEAN_ANNUAL_PRECIPITATION`
- Supported claim: Provides spatially explicit U.S. precipitation normals with units and declared normals period suitable as climate Land Facts.
- Does not support: Direct forage suitability, carrying capacity, livestock-water reliability, or operation ranking.
- Rule applicability: `UNITED_STATES_WITH_PRODUCT_COVERAGE_LIMITS`
- Review status: `LIVE_VERIFIED_CANONICAL_PRECIP_PATH_ON_CPER — SIGNAL_NOT_APPROVED`
- CPER note: 1991–2020 `annprcp_norm` = 345.74 mm/year for `ENGINEERING_TEST_GEOMETRY_CPER_001` (single intersecting ~4 km cell).

### `SRC_F05_002`

- Title: *PRISM Climate Group gridded climate data*
- Organization: Oregon State University PRISM Climate Group
- Source type: `RESEARCH_CLIMATE_GRID`
- URL: https://prism.oregonstate.edu/
- Runtime role: `ALTERNATE_OR_CROSS_CHECK_ONLY`
- Supported claim: Provides high-resolution U.S. climate surfaces that may cross-check precipitation and temperature.
- Does not support: Automatic RangeMatch biological thresholds or free redistribution assumptions without license review.
- Rule applicability: `UNITED_STATES_PRODUCT_DEPENDENT`
- Review status: `ALTERNATE_CANDIDATE — NOT_PRIMARY_PATH`

### `SRC_F05_003`

- Title: *U.S. Drought Monitor*
- Organization: National Drought Mitigation Center / partner agencies
- Source type: `FEDERAL_CURRENT_CONDITION_PRODUCT`
- URL: https://droughtmonitor.unl.edu/
- Runtime role: `CURRENT_CONDITION_CONTEXT`
- Supported claim: Provides controlled current drought categories D0–D4 for the United States.
- Does not support: Equating one current class with multi-year drought frequency, forage failure, or water-source failure.
- Rule applicability: `UNITED_STATES_CURRENT_CONDITION_CONTEXT`
- Review status: `VERIFIED_FOR_NARROW_CURRENT_CONDITION_CLAIM`

### `SRC_F05_004`

- Title: *Conservation Practice Standard — Prescribed Grazing (Code 528)*
- Organization: USDA Natural Resources Conservation Service
- Source type: `FEDERAL_CONSERVATION_PRACTICE_STANDARD`
- URL: https://www.nrcs.usda.gov/sites/default/files/2024-01/528_NHCP_CPS_Grazing_Management_2023_0.pdf
- Supported claim: Grazing plans must balance forage supply and animal demand and include contingency preparations for drought and other episodic disturbances; weather/drought tools may support forage projections.
- Does not support: A universal precipitation or USDM class threshold for parcel suitability or Cow-Calf versus Sheep ranking.
- Rule applicability: `UNITED_STATES_GRAZING_MANAGEMENT_GUIDANCE`
- Review status: `VERIFIED_FOR_NARROW_QUALITATIVE_RELATIONSHIP`

### `SRC_F05_005`

- Title: *Mireye climate and drought point fields (adapter audit)*
- Organization: Mireye
- Source type: `ADAPTER_POINT_CONTEXT`
- Runtime role: `POINT_QA_AND_FAST_CONTEXT`
- Supported claim: Where field semantics match, provides point samples for current USDM class, mean annual temperature, and heat-day counts.
- Does not support: Parcel-aggregate precipitation; treating `precipitable_water_annual_mean_cm` as land-surface rainfall.
- Rule applicability: `POINT_SEMANTICS_ONLY`
- Review status: `LIVE_VERIFIED_POINT_QA_ON_CPER`

### `SRC_F05_006`

- Title: *RCC-ACIS GridData precipitation series*
- Organization: NOAA Regional Climate Centers / ACIS
- Source type: `FEDERAL_CLIMATE_WEB_SERVICE`
- URL: https://www.rcc-acis.org/
- Runtime role: `SECONDARY_QA_OR_FALLBACK`
- Canonical runtime source: `false`
- Grids tested on CPER: `[1, 21]`
- Supported claim: Can return CPER precipitation time series useful for QA, supplemental analysis, or future interannual-variability methods.
- Does not support: Replacing NOAA/NCEI direct climate normals NetCDF as the canonical mean-annual-precipitation Land Fact.
- Rule applicability: `UNITED_STATES_SERVICE_DEPENDENT`
- Review status: `CAPABILITY_PROBED_SECONDARY_ONLY`

### `SRC_F05_007`

- Title: *Managing Drought Risk on the Ranch*
- Organization: National Drought Mitigation Center / University of Nebraska–Lincoln collaborators
- Source type: `FEDERAL_AND_UNIVERSITY_DROUGHT_PLANNING_GUIDANCE`
- URL: https://drought.unl.edu/ranchplan/
- Handbook PDF: https://drought.unl.edu/archive/Documents/Ranchplan/ranch-plan-handbook-to-print-9.14.pdf
- Supported claim: Drought can reduce livestock performance and forage quantity/quality; ranch drought plans should monitor precipitation, forage, and water resources and balance forage supply with demand on critical dates.
- Does not support: A fixed national precipitation cutoff, automatic forage-failure score from one USDM week, or species ranking.
- Rule applicability: `UNITED_STATES_RANCH_DROUGHT_PLANNING_CONTEXT`
- Review status: `VERIFIED_FOR_NARROW_QUALITATIVE_RELATIONSHIP`

### `SRC_F05_008`

- Title: *Combating the Effects of Drought on Pasture and Forage*
- Organization: USDA Natural Resources Conservation Service
- Source type: `FEDERAL_EXTENSION_STYLE_GUIDANCE`
- URL: https://www.nrcs.usda.gov/sites/default/files/2022-10/NRCS-CB%20Pasture-Drought%20Brochure.pdf
- Supported claim: Drought interacts with stocking rate and pasture management; animal numbers a pasture can support change with climate/growing conditions.
- Does not support: Computing carrying capacity or suitability from mean annual precipitation alone.
- Rule applicability: `UNITED_STATES_PASTURE_DROUGHT_MANAGEMENT_CONTEXT`
- Review status: `VERIFIED_FOR_NARROW_QUALITATIVE_RELATIONSHIP`

## F04 Soil, Wetness, and Ecological Site Context

### `SRC_F04_001`

- Title: *Soil Survey Geographic Database (SSURGO)*
- Organization: USDA Natural Resources Conservation Service
- Source type: `FEDERAL_SOIL_DATABASE`
- URL: https://www.nrcs.usda.gov/resources/data-and-reports/soil-survey-geographic-database-ssurgo
- Supported claim: SSURGO provides soil spatial and tabular information including available water capacity, soil reaction, electrical conductivity, and flooding frequency.
- Does not support: Homogeneous map units, current field condition, current forage production, or operation suitability.
- Rule applicability: `UNITED_STATES_SOIL_SURVEY_COVERAGE_WITH_GAPS`
- Review status: `VERIFIED_FOR_DATA_CAPABILITY`

### `SRC_F04_002`

- Title: *Ecological Site Descriptions*
- Organization: USDA Natural Resources Conservation Service
- Source type: `FEDERAL_ECOLOGICAL_CLASSIFICATION_GUIDANCE`
- URL: https://www.nrcs.usda.gov/getting-assistance/technical-assistance/ecological-sciences/ecological-site-descriptions
- Supported claim: Ecological Sites link recurring soil, vegetation, hydrology, climate, disturbance, and management-response characteristics.
- Does not support: Current parcel vegetation state or direct livestock-operation suitability from a site label.
- Rule applicability: `RANGELAND_AND_FORESTLAND_ECOLOGICAL_SITE_CONTEXT`
- Review status: `VERIFIED_FOR_NARROW_CLASSIFICATION_CLAIM`

### `SRC_F04_003`

- Title: *Ecological Site Descriptions in EDIT — Query by Soil Survey Area*
- Organization: USDA Natural Resources Conservation Service
- Source type: `FEDERAL_LIVE_REFERENCE_SERVICE`
- URL: https://www.nrcs.usda.gov/publications/Ecological%20Site%20Extent%20-%20Query%20by%20Soil%20Survey%20Area%20%28Link%20to%20EDIT%29.html
- Supported claim: Soil Data Access can link soil components to ecological-site references in EDIT.
- Limitation: Not every Ecological Site Description is publicly available in EDIT.
- Rule applicability: `COMPONENT_AND_PUBLICATION_DEPENDENT`
- Review status: `VERIFIED_FOR_SERVICE_ROLE`

### `SRC_F04_004`

- Title: *National Range and Pasture Handbook*
- Organization: USDA Natural Resources Conservation Service
- Source type: `NATIONAL_TECHNICAL_GUIDANCE`
- URL: https://www.nrcs.usda.gov/conservation-basics/animals/livestock/national-range-and-pasture-handbook
- Supported claim: Grazing-land inventory and planning use ecological-site, soil, hydrology, erosion, vegetation, and management context.
- Does not support: A universal soil threshold or Cow-Calf versus Sheep ranking.
- Rule applicability: `UNITED_STATES_GRAZING_LAND_GUIDANCE`
- Review status: `VERIFIED_FOR_GOVERNANCE_CONTEXT`

## F03 Livestock Water

### `SRC_F03_001`

- Title: *Ponds — Planning, Design, Construction, Agriculture Handbook 590*
- Organization: USDA Natural Resources Conservation Service
- Source type: `FEDERAL_TECHNICAL_HANDBOOK`
- URL: https://www.nrcs.usda.gov/sites/default/files/2023-05/NRCS%20Agricultural%20Handbook%20590.pdf
- Supported claim: Stockwater quantity and spatial distribution affect grazing use; livestock class and operating scenario affect planning demand.
- Does not support: Universal RangeMatch water thresholds or remote verification of a functioning source.
- Rule applicability: `UNITED_STATES_PLANNING_CONTEXT`
- Evidence strength: `HIGH_FOR_NARROW_PLANNING_RELATIONSHIP`
- Review status: `VERIFIED_FOR_NARROW_CLAIM`

### `SRC_F03_002`

- Title: *Manipulating Beef Cattle Distribution with Salt and Water in Large Arid-Land Pastures: A GPS/GIS Assessment*
- Author: David C. Ganskopp
- Year: 2001
- Journal: *Applied Animal Behaviour Science* 73:251-262
- Source type: `PEER_REVIEWED_FIELD_STUDY`
- USDA URL: https://www.ars.usda.gov/research/publications/publication/?seqNo115=120928
- Study scope: Beef cattle in large arid-land pastures.
- Supported claim: Moving water shifted cattle centers of activity in the studied system.
- Does not support: A universal distance cutoff or response magnitude.
- Rule applicability: `CONTEXT_DEPENDENT`
- Evidence strength: `MODERATE_TO_STRONG`
- Review status: `VERIFIED_FOR_NARROW_CLAIM`

### `SRC_F03_003`

- Title: *Cattle Grazing Distribution Patterns Related to Topography Across Diverse Rangeland Ecosystems of North America*
- Year: 2021
- Source type: `PEER_REVIEWED_MULTI_SITE_FIELD_STUDY`
- USDA PDF: https://www.ars.usda.gov/ARSUserFiles/1354/213.%20Raynor%20et%20al%202021%20REM%20cattle%20grazing%20patterns%20related%20to%20topography.pdf
- Supported claim: Water and distance interact with pasture size, topography, vegetation, and environmental context in cattle distribution.
- Does not support: A national distance-to-water threshold.
- Rule applicability: `MULTI_REGION_CONTEXT_DEPENDENT`
- Evidence strength: `STRONG_FOR_QUALITATIVE_RELATIONSHIP`
- Review status: `VERIFIED_FOR_NARROW_CLAIM`

### `SRC_F03_004`

- Title: *Livestock Water Quality*
- Organization: Penn State Extension
- Source type: `UNIVERSITY_EXTENSION_GUIDANCE`
- URL: https://extension.psu.edu/livestock-water-quality
- Supported claim: Cattle and sheep water intake and quality risk vary with animal and environmental context; water chemistry and contaminants require evaluation.
- Does not support: Parcel-specific quantity or quality without measurements.
- Rule applicability: `GENERAL_LIVESTOCK_DILIGENCE`
- Evidence strength: `MODERATE`
- Review status: `VERIFIED_FOR_NARROW_CLAIM`

### `SRC_F03_005`

- Title: *The Importance of Water for Livestock*
- Organization: University of Minnesota Extension
- Source type: `UNIVERSITY_EXTENSION_GUIDANCE`
- URL: https://extension.umn.edu/livestock-operations/water-livestock
- Supported claim: Livestock require adequate high-quality water and laboratory testing is needed for key water-quality risks.
- Does not support: Remote confirmation of water quality or supply adequacy.
- Rule applicability: `GENERAL_LIVESTOCK_DILIGENCE`
- Evidence strength: `MODERATE`
- Review status: `VERIFIED_FOR_NARROW_CLAIM`

## F02 Herbaceous Resource

### `SRC_F02_001`

- Title: *National Range and Pasture Handbook, Subpart E - Inventory, Assessment, and Monitoring for Grazing Lands*
- Organization: USDA Natural Resources Conservation Service
- Version: June 2022, 190-645-H
- Source type: `NATIONAL_TECHNICAL_GUIDANCE`
- URL: https://directives.nrcs.usda.gov/sites/default/files2/1712930361/33915.pdf
- Study location: Not an experimental study
- Supported claim: Remote products can estimate plant cover by life form, bare ground, biomass, and annual production and can support grazing-land inventory, monitoring, and trend analysis. The handbook states that these tools require field validation.
- Does not support: Treating modeled cover or production as verified forage availability, species composition, palatability, nutritive value, or carrying capacity.
- Rule applicability: `UNITED_STATES_GUIDANCE`
- Evidence strength: `HIGH_AS_GOVERNANCE_GUIDANCE`
- Review status: `VERIFIED_FOR_NARROW_CLAIM`

### `SRC_F02_002`

- Title: *Improving Landsat predictions of rangeland fractional cover with multitask learning and uncertainty*
- Authors: Brady W. Allred et al.
- Year: 2021
- Journal: *Methods in Ecology and Evolution*
- Source type: `PEER_REVIEWED_REMOTE_SENSING_METHOD`
- DOI: https://doi.org/10.1111/2041-210X.13564
- Supported claim: RAP produces modeled fractional-cover estimates for rangeland functional groups with an uncertainty-aware multitask method.
- Does not support: Plant-species composition, palatability, nutritive value, or direct livestock suitability.
- Rule applicability: `US_RANGELAND_DATA_METHOD`
- Evidence strength: `HIGH_AS_DATA_METHOD`
- Review status: `VERIFIED_FOR_DATA_METHOD`

### `SRC_F02_003`

- Title: *Annual and 16-day rangeland production estimates for the western United States*
- Authors: Matthew O. Jones, Nathaniel P. Robinson, David E. Naugle, Jeremy D. Maestas, Matthew C. Reeves, Robert W. Lankston, Brady W. Allred
- Year: 2021
- Journal: *Rangeland Ecology & Management*, 77, 112-117
- Source type: `PEER_REVIEWED_REMOTE_SENSING_METHOD`
- DOI: https://doi.org/10.1016/j.rama.2021.04.003
- Supported claim: RAP provides modeled annual and 16-day aboveground herbaceous production estimates partitioned into annual and perennial grass/forb groups for its documented coverage.
- Does not support: Standing biomass at inspection time, livestock-available forage, palatability, nutritive value, sustainable utilization, or stocking capacity.
- Rule applicability: `DOCUMENTED_RAP_PRODUCT_COVERAGE`
- Evidence strength: `HIGH_AS_DATA_METHOD`
- Review status: `VERIFIED_FOR_DATA_METHOD`

### `SRC_F02_004`

- Title: *An accuracy assessment of satellite-derived rangeland fractional cover*
- Authors: Georgia Harrison, Matthew B. Rigge, Timothy J. Assal, Cara Applestein, Darren K. James, Sarah E. McCord
- Year: 2025
- Journal: *Ecological Indicators*
- Source type: `PEER_REVIEWED_ACCURACY_ASSESSMENT`
- DOI: https://doi.org/10.1016/j.ecolind.2025.113267
- USGS record: https://www.usgs.gov/publications/accuracy-assessment-satellite-derived-rangeland-fractional-cover
- Study scope: More than 17,000 field plots from continental U.S. rangeland monitoring programs
- Supported claim: RAP fractional-cover error varies by component and ecoregion; perennial herbaceous and bare-ground components had among the largest nationwide errors in this assessment, and wetland/riparian applications require particular caution.
- Does not support: Rejecting RAP entirely or treating a pixel estimate as field truth.
- Rule applicability: `CONTINENTAL_US_DATA_QUALITY`
- Evidence strength: `HIGH`
- Review status: `VERIFIED_FOR_DATA_LIMITATION`

### `SRC_F02_005`

- Title: *Spatio-temporal patterns of rangeland forage nutritive value and grazer selection with patch-burning in the US northern Great Plains*
- Authors: J.W. Spiess, D.A. McGranahan, M.T. Berti, C.K. Gasch, T. Hovick, B. Geaumont
- Year: 2024
- Journal: *Journal of Environmental Management*, 357, 120731
- Source type: `PEER_REVIEWED_FIELD_STUDY`
- DOI: https://doi.org/10.1016/j.jenvman.2024.120731
- Study location: Northern Great Plains; six 65-ha pastures across four summer grazing seasons
- Livestock/production system: Cow-calf pairs and gestating ewes in patch-burn grazing systems
- Supported claim: Both livestock types selected recently burned patches characterized by higher protein/moisture and lower fiber even when available biomass was lower, demonstrating that forage quantity and nutritive value are distinct.
- Does not support: A universal biomass preference rule, national nutritive threshold, or direct RAP-to-suitability conversion.
- Rule applicability: `NORTHERN_GREAT_PLAINS_CONTEXT_WITH_BROADER_LIMITATION_VALUE`
- Evidence strength: `HIGH_FOR_STUDY_SYSTEM`
- Review status: `VERIFIED_FOR_NARROW_CLAIM`

### `SRC_F02_006`

- Title: *Diet Composition, Forage Selection, and Potential for Forage Competition Among Elk, Deer, and Livestock on Aspen-Sagebrush Summer Range*
- Authors: Jeffrey L. Beck, James M. Peek
- Year: 2005
- Journal: *Rangeland Ecology & Management*, 58(2), 135-147
- Source type: `PEER_REVIEWED_FIELD_STUDY`
- DOI: https://doi.org/10.2111/03-13.1
- Study location: Northeastern Nevada; summer range; 1998-2000 diet data
- Livestock/production system: Cattle and domestic sheep sharing aspen-sagebrush summer range
- Supported claim: Cattle and sheep diets were mostly graminoids in this study system, while forbs were also an important dietary resource; botanical composition matters beyond total herbaceous cover.
- Does not support: A universal grass/forb ratio or national preference threshold.
- Rule applicability: `ECOLOGICAL_AND_SEASONAL_CONTEXT`
- Evidence strength: `MODERATE_TO_HIGH_FOR_STUDY_SYSTEM`
- Review status: `VERIFIED_FOR_NARROW_CLAIM`

### `SRC_F02_007`

- Title: *Diet selection of bonded and non-bonded free-ranging sheep and cattle*
- Authors: D.M. Anderson, C.V. Hulet, S.K. Hamadeh, J.N. Smith, L.W. Murray
- Year: 1990
- Journal: *Applied Animal Behaviour Science*, 26(3), 231-242
- Source type: `PEER_REVIEWED_FIELD_STUDY`
- DOI: https://doi.org/10.1016/0168-1591(90)90139-5
- Study location: New Mexico rangeland context
- Livestock/production system: Free-ranging cattle and bonded/non-bonded sheep
- Supported claim: Cattle and sheep diet composition differed in this system, and bonding/management altered sheep diet composition.
- Does not support: Universal species dietary percentages or a national ranking rule.
- Rule applicability: `REGIONAL_MANAGEMENT_CONTEXT`
- Evidence strength: `MODERATE`
- Review status: `VERIFIED_FOR_CONTEXT_ONLY`

## `SRC_F01_001`

- Title: *Illinois Grazing Manual Fact Sheet - Livestock Distribution*
- Organization: USDA Natural Resources Conservation Service
- Year: 2000
- Source type: `AUTHORITATIVE_MANAGEMENT_GUIDANCE`
- URL: https://www.nrcs.usda.gov/sites/default/files/2022-12/Livestock-Distribution.pdf
- Study location: Illinois; guidance rather than an experimental study
- Livestock/production system: Grazing livestock; management guidance
- Supported claim: Steep slopes, cliffs, gullies, rock outcrops, water, vegetation, season, fencing, trails, and herding can affect livestock distribution.
- Does not support: Species-specific national slope cutoffs; a hard exclusion; treating rock cover as slope.
- Rule applicability: `REGIONAL_QUALITATIVE_GUIDANCE`
- Evidence strength: `MODERATE`
- Review status: `VERIFIED_FOR_NARROW_CLAIM`

## `SRC_F01_002`

- Title: *Cattle Grazing Distribution Patterns Related to Topography Across Diverse Rangeland Ecosystems of North America*
- Authors: E.J. Raynor et al.
- Year: 2021
- Journal: *Rangeland Ecology & Management*, 75, 91-103
- Source type: `PEER_REVIEWED_MULTI_SITE_STUDY`
- DOI: https://doi.org/10.1016/j.rama.2020.12.002
- USDA PDF: https://www.ars.usda.gov/ARSUserFiles/1354/213.%20Raynor%20et%20al%202021%20REM%20cattle%20grazing%20patterns%20related%20to%20topography.pdf
- Study location: Seven continental U.S. rangeland sites
- Livestock/production system: Beef cattle; extensive grazing
- Supported claim: Topography affects cattle distribution, but direction and magnitude interact with water, stocking context, vegetation, and wetness. Topographic position can be more informative than a simple monotonic slope assumption.
- Does not support: A national slope penalty curve or universal cutoff.
- Rule applicability: `MULTI_REGION_US_QUALITATIVE_RELATIONSHIP`
- Evidence strength: `HIGH`
- Review status: `VERIFIED_FOR_NARROW_CLAIM`

## `SRC_F01_003`

- Title: *Cattle Grazing Distribution in Shortgrass Steppe: Influences of Topography and Saline Soils*
- Authors: Samuel P. Gersie, David J. Augustine, Justin D. Derner
- Year: 2019
- Journal: *Rangeland Ecology & Management*, 72, 602-614
- Source type: `PEER_REVIEWED_SITE_STUDY`
- DOI: https://doi.org/10.1016/j.rama.2019.01.009
- USDA PDF: https://www.ars.usda.gov/ARSUserFiles/1354/152.%20Gersie%20et%20al.%202019%20REM%20Cattle%20grazing%20distribution.pdf
- Study location: Central Plains Experimental Range, Colorado
- Livestock/production system: Cattle; semiarid shortgrass steppe
- Supported claim: Topographic position and saline vegetation context affected cattle distribution; fitted topographic relationships were site-dependent.
- Does not support: Universal lowland preference or national numeric slope rules.
- Rule applicability: `ECOLOGICAL_SITE_SPECIFIC`
- Evidence strength: `HIGH_WITH_LIMITED_GENERALIZABILITY`
- Review status: `VERIFIED_FOR_NARROW_CLAIM`

## `SRC_F01_004`

- Title: *National Range and Pasture Handbook, Subpart F - Management of Grazing Lands*
- Organization: USDA Natural Resources Conservation Service
- Version: June 2022, 190-645-H
- Source type: `NATIONAL_TECHNICAL_GUIDANCE`
- URL: https://directives.nrcs.usda.gov/sites/default/files2/1712930380/33916.pdf
- Study location: Not an experimental study
- Livestock/production system: U.S. grazing-land management
- Supported claim: Slope and distance to drinking water may reduce usable grazing capacity; adjustments require local qualification and apply to affected portions of a management unit.
- Does not support: Copying example tables into a universal deterministic rule or applying one adjustment equally to cattle and sheep.
- Rule applicability: `UNITED_STATES_GUIDANCE_REQUIRING_LOCAL_QUALIFICATION`
- Evidence strength: `HIGH_AS_GUIDANCE_LOW_AS_UNIVERSAL_THRESHOLD`
- Review status: `VERIFIED_FOR_NARROW_CLAIM`

## `SRC_F01_005`

- Title: *Resource Selection of Domestic Sheep on Mountainous Summer Habitat in Utah, United States*
- Authors: E.M. Baum, T.F. Robinson, R.T. Larsen, S.L. Peterson, R.J. Shields
- Year: 2022
- Journal: *Rangeland Ecology & Management*, 84, 117-125
- Source type: `PEER_REVIEWED_RESOURCE_SELECTION_STUDY`
- DOI: https://doi.org/10.1016/j.rama.2022.05.009
- Study location: Mountainous summer habitat near Scofield Reservoir, Utah
- Livestock/production system: Managed domestic range sheep; summer grazing
- Sample: 27,327 GPS locations from five functioning collars, July-September 2020
- Supported claim: Slope, ruggedness, elevation, aspect, and water distance were distinct predictors; sheep selected gentler terrain in this study context.
- Does not support: A universal 45% threshold or the claim that steep terrain has no cost for sheep.
- Rule applicability: `WESTERN_US_MOUNTAIN_SYSTEM_CONTEXT`
- Evidence strength: `MODERATE_TO_HIGH_WITH_SCOPE_LIMIT`
- Review status: `VERIFIED_FOR_NARROW_CLAIM`

## `SRC_F01_006`

- Title: *Comparison of the flocking behavior of Katahdin and Rambouillet sheep breeds in an extensive range environment using GPS technology*
- Authors: Carrie S. Wilson et al.
- Year: 2025
- Journal: *Animal Biotelemetry*, 13, Article 7
- Source type: `PEER_REVIEWED_MANAGEMENT_CONTEXT_STUDY`
- DOI: https://doi.org/10.1186/s40317-025-00404-6
- Study location: U.S. Sheep Experiment Station range system, eastern Idaho/southwestern Montana
- Livestock/production system: Continuously herded bands of ewes with lambs
- Supported claim: Breed adaptation, rearing history, and herding affect the use of rugged extensive range.
- Does not support: A direct slope response curve or numeric terrain threshold.
- Rule applicability: `REGIONAL_MANAGEMENT_CONTEXT`
- Evidence strength: `MODERATE`
- Review status: `VERIFIED_FOR_CONTEXT_ONLY`
