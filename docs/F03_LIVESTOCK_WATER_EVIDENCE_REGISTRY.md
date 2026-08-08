# F03 Evidence Registry — Livestock Water Availability and Distribution

> Review status: `V0.1 SOURCE-BY-SOURCE AUDIT FROZEN`  
> Factor decision: `IN MVP SHARED CORE — DATA-QUALITY RULES ONLY`  
> Rule status: `NO UNIVERSAL DISTANCE, DEMAND, OR CAPACITY THRESHOLD APPROVED`  
> Operations: Cow-Calf Operation and Sheep Grazing  
> Last reviewed: 2026-08-07  
> Verified-water evidence contract (review): [`F03_VERIFIED_WATER_EVIDENCE_CONTRACT.md`](./F03_VERIFIED_WATER_EVIDENCE_CONTRACT.md)

## 1. Atomicity Decision

`Livestock Water` is a Factor family, not one Land Fact. A mapped water feature is not a verified livestock water source.

| Variable ID | Variable | Type | Current decision |
|---|---|---|---|
| `VAR_F03_MAPPED_SURFACE_WATER` | Mapped streams, ponds, reservoirs, springs, canals, and related hydrography | Source Land Fact | `CONTEXT CANDIDATE` |
| `VAR_F03_SOURCE_INVENTORY` | Candidate and verified livestock watering points with type and coordinates | Parcel Land Fact | `INCLUDE CANDIDATE` |
| `VAR_F03_SOURCE_OPERATIONAL_STATUS` | Whether a source and delivery system currently function | Field/operator Land Fact | `VERIFICATION REQUIRED` |
| `VAR_F03_SOURCE_RELIABILITY` | Seasonal and drought-period reliability | Observed/document Land Fact | `VERIFICATION REQUIRED` |
| `VAR_F03_DELIVERABLE_CAPACITY` | Pump, well, spring, pipeline, storage, and trough delivery capacity | Measured Land Fact | `VERIFICATION REQUIRED` |
| `VAR_F03_WATER_QUALITY` | Livestock-relevant laboratory water quality | Laboratory Land Fact | `VERIFICATION REQUIRED` |
| `VAR_F03_LEGAL_ACCESS` | Ownership, easement, permit, allocation, and lawful access | Legal/diligence record | `VERIFICATION REQUIRED` |
| `VAR_F03_EUCLIDEAN_DISTANCE_TO_CANDIDATE_WATER` | Straight-line distance surface | Parcel-derived context | `CONTEXT ONLY` |
| `VAR_F03_TRAVEL_DISTANCE_TO_VERIFIED_WATER` | Traversable distance considering terrain, barriers, fencing, gates, and access | Operation-aware derived metric | `METHOD REVIEW REQUIRED` |
| `METRIC_F03_WATER_DEMAND_SCENARIO` | Demand based on species, class, head count, production stage, diet, temperature, and management | Operation scenario | `NOT A PERMANENT LAND FACT` |

### Required non-equivalences

```text
NHD feature != verified livestock water source
surface-water permanence pixel != accessible drinking source
nearest named waterbody != parcel water inventory
nearest groundwater-well depth != parcel well yield
nearby gage discharge != legal or physical livestock water supply
straight-line distance != traversable livestock distance
source presence != operational reliability
water quantity != water quality
physical water != legal access
```

## 2. Narrow Evidence Decisions

### Cow-Calf reviewed relationship

> Reliable, legally accessible livestock water and its spatial distribution can affect cattle health, performance, movement, and grazing distribution. Capacity must be evaluated for the declared animal count and service period. A mapped hydrographic feature alone does not establish usable cattle water.

Status: `ACCEPTED_RELATIONSHIP — VERIFIED_FOR_V0_1`

Not approved:

- a universal maximum distance to water;
- a national water-distribution penalty curve;
- a fixed gallons-per-head rule independent of animal and weather context;
- a conclusion that an NHD/JRC/NWIS record is a functioning livestock source;
- a hard exclusion from remote mapping alone.

### Sheep reviewed relationship

> Sheep require reliable, legally accessible water of adequate quantity and quality. Capacity must be evaluated for the declared animal count and service period. Remote water mapping alone does not establish accessible, reliable, adequate, or good-quality sheep water.

Status: `ACCEPTED_RELATIONSHIP — VERIFIED_FOR_V0_1`

Not approved:

- a universal sheep distance-to-water threshold;
- a fixed daily demand for every class and environment;
- an automatic Sheep advantage over Cow-Calf;
- treating forage moisture as proof that no drinking source is needed;
- a remote-only adequacy conclusion.

Deferred pending additional source audit:

- quantitative effects of animal size, production stage, diet moisture, and weather on demand;
- fresh-forage or snow substitution for a drinking-water source.

## 3. Source-by-Source Audit

### `SRC_F03_001` — USDA-NRCS Agriculture Handbook 590

- Title: *Ponds — Planning, Design, Construction, Agriculture Handbook 590*
- Organization: USDA Natural Resources Conservation Service
- Source type: Federal technical handbook
- URL: https://www.nrcs.usda.gov/sites/default/files/2023-05/NRCS%20Agricultural%20Handbook%20590.pdf
- Supported claim: Stockwater quantity and distribution matter; inadequate or inaccessible water can concentrate grazing and leave forage underused. Livestock class affects planning demand.
- Does not support: Universal parcel suitability thresholds or proof that a mapped pond is reliable, accessible, lawful, or good quality.
- Applicability: U.S. planning context; scenario-specific engineering required.
- Evidence strength: `STRONG FOR PLANNING RELATIONSHIP; ILLUSTRATIVE FOR DEMAND VALUES`

### `SRC_F03_002` — Ganskopp 2001

- Title: *Manipulating Beef Cattle Distribution with Salt and Water in Large Arid-Land Pastures: A GPS/GIS Assessment*
- Author: David C. Ganskopp
- Journal: *Applied Animal Behaviour Science* 73:251-262
- USDA record: https://www.ars.usda.gov/research/publications/publication/?seqNo115=120928
- Source type: Peer-reviewed field study; USDA-ARS record
- Study scope: Beef cattle in large arid-land pastures
- Supported claim: Moving water shifted cattle centers of activity and water was more effective than salt for changing distribution in the studied system.
- Does not support: A universal distance cutoff or identical response in all environments, breeds, seasons, pasture sizes, and management systems.
- Applicability: `CONTEXT_DEPENDENT`
- Evidence strength: `MODERATE_TO_STRONG`

### `SRC_F03_003` — Raynor et al. 2021

- Title: *Cattle Grazing Distribution Patterns Related to Topography Across Diverse Rangeland Ecosystems of North America*
- Source type: Peer-reviewed multi-site field study
- USDA PDF: https://www.ars.usda.gov/ARSUserFiles/1354/213.%20Raynor%20et%20al%202021%20REM%20cattle%20grazing%20patterns%20related%20to%20topography.pdf
- Supported claim: Water availability and distance interact with pasture size, environment, vegetation, and topography in cattle distribution; larger areas may require different treatment from studied pastures.
- Does not support: Promoting cited literature values into a universal RangeMatch threshold.
- Applicability: Multi-region cattle relationship; context dependent.
- Evidence strength: `STRONG FOR QUALITATIVE RELATIONSHIP`

### `SRC_F03_004` — Penn State Extension livestock water quality

- Title: *Livestock Water Quality*
- Organization: Penn State Extension
- URL: https://extension.psu.edu/livestock-water-quality
- Source type: University Extension guidance
- Supported claim: Cattle and sheep water intake and water-quality risk vary with body size, reproductive status, age, diet, weather, salinity, sulfates, nitrates, and other contaminants.
- Does not support: A parcel-specific quantity or quality conclusion without source testing and animal scenario.
- Applicability: General U.S. livestock diligence context.
- Evidence strength: `MODERATE`

### `SRC_F03_005` — University of Minnesota Extension

- Title: *The Importance of Water for Livestock*
- Organization: University of Minnesota Extension
- URL: https://extension.umn.edu/livestock-operations/water-livestock
- Source type: University Extension guidance
- Supported claim: Livestock require access to adequate high-quality water; laboratory testing is needed to evaluate salinity, nitrates, sulfates, pH, bacteria, and toxins.
- Does not support: Remote confirmation of water quality.
- Applicability: General livestock diligence.
- Evidence strength: `MODERATE`

## 4. Frozen v0.1 Factor Decision

| Criterion | Decision |
|---|---|
| Scientifically relevant to both Profiles | Yes |
| Shared atomic Land Facts possible | Yes |
| Remote screening components available | Yes |
| Remote confirmation of livestock-water adequacy possible | No |
| Numeric suitability rule supported | No |
| MVP status | `IN MVP SHARED CORE — DATA-QUALITY RULES ONLY` |

## 5. Frozen Runtime Boundary

1. Cow-Calf and Sheep requirements are approved only as qualitative relationships.
2. No numeric threshold, weight, hard constraint, directional suitability signal, or cross-species ranking is approved.
3. Remote candidate mapping remains `NEEDS_VERIFICATION`; missing evidence remains `UNKNOWN`.
4. Operational status, relevant-period reliability, scenario capacity, water quality, and legal access require records, measurements, or field verification.
5. Traversable distance remains deferred until terrain, fencing, barriers, gates, routes, and legal access are available.
