# F02 Evidence Registry - Herbaceous Resource

> Review status: `PRELIMINARY SOURCE-BY-SOURCE AUDIT COMPLETE`
> Factor decision: `CANDIDATE FOR MVP SHARED CORE`
> Rule status: `NO NUMERIC OR DIRECTIONAL PRODUCTION RULES APPROVED`
> Operations: Cow-Calf Operation and Sheep Grazing
> Last reviewed: 2026-08-07

## 1. Atomicity Decision

`Herbaceous Resource` is acceptable as a user-facing Factor family, but it is not one atomic variable and must not receive one combined score.

### Candidate atomic Land Facts

| Variable ID | Variable | Type | Current decision |
|---|---|---|---|
| `VAR_F02_PERENNIAL_HERB_COVER` | Perennial grass-and-forb fractional cover | Modeled Land Fact | `INCLUDE CANDIDATE` |
| `VAR_F02_ANNUAL_HERB_COVER` | Annual grass-and-forb fractional cover | Modeled Land Fact | `INCLUDE CANDIDATE` |
| `VAR_F02_ANNUAL_HERB_PRODUCTION` | Annual aboveground herbaceous production | Modeled Land Fact | `INCLUDE CANDIDATE` |
| `VAR_F02_16DAY_HERB_PRODUCTION` | Within-year 16-day herbaceous production series | Modeled time-series Land Fact | `INCLUDE CANDIDATE` |
| `VAR_F02_INTERANNUAL_PRODUCTION_VARIABILITY` | Versioned variability derived from annual production | Parcel-derived Context Variable | `INCLUDE CANDIDATE; METHOD NOT FROZEN` |
| `VAR_F02_BARE_GROUND` | Bare-ground fractional cover | Modeled Context Variable | `CONTEXT CANDIDATE; NOT FORAGE` |
| `VAR_F02_BOTANICAL_COMPOSITION` | Species or reviewed functional composition | Field/document Land Fact | `VERIFICATION REQUIRED` |
| `VAR_F02_PALATABILITY` | Operation- and season-specific palatability | Reviewed local/field interpretation | `VERIFICATION REQUIRED` |
| `VAR_F02_NUTRITIVE_VALUE` | Crude protein, energy/digestibility, fiber and related measures | Field/laboratory Land Fact | `VERIFICATION REQUIRED` |

### Prohibited equivalences

```text
herbaceous cover != herbaceous production
standing biomass != annual production
annual production != available forage
available forage != palatable forage
palatable forage != nutritionally adequate diet
RAP annual/perennial herbaceous class != grass/forb species composition
high modeled production != sustainable stocking capacity
```

### Derived metrics that must remain separate

`available_forage`, `usable_forage`, `carrying_capacity`, and `stocking_rate` are not atomic F02 Land Facts. They require additional reviewed inputs such as species composition, palatability, utilization policy, accessibility, season, current use, residual biomass, animal demand, management, and field verification.

## 2. Evidence Decisions

### Remote data capability

- RAP provides modeled fractional cover for annual and perennial grasses/forbs and modeled herbaceous production at annual and 16-day intervals.
- RAP functional groups do not provide parcel-specific plant species, palatability, toxicity, or laboratory nutritive value.
- NRCS guidance treats remote-sensing products as inventory and monitoring aids that require field validation.
- RAP values are modeled estimates with regional and component-specific error; parcel aggregation and uncertainty must be retained.

### Cow-Calf narrow relationship

> The amount, timing, composition, and nutritive value of herbaceous resources can affect cattle foraging opportunity and grazing performance. Modeled cover or production alone does not establish available, palatable, nutritionally adequate, or sustainably usable forage.

Status: `ACCEPTED_RELATIONSHIP_CANDIDATE`

Not approved:

- a minimum cover or production threshold;
- a direct positive score from RAP production;
- a carrying-capacity estimate;
- a universal grass/forb dietary ratio;
- a conclusion that higher standing biomass is always preferred.

### Sheep narrow relationship

> The amount, timing, composition, and nutritive value of herbaceous resources can affect sheep foraging opportunity. Sheep selection can differ from cattle and can vary with breed, season, management, plant composition, and forage quality; modeled cover or production alone does not establish usable or nutritionally adequate forage.

Status: `ACCEPTED_RELATIONSHIP_CANDIDATE`

Not approved:

- a fixed sheep preference for forbs or grasses;
- a direct positive score from herbaceous cover;
- a universal dietary ratio;
- a numeric Cow-Calf versus Sheep advantage;
- a carrying-capacity estimate.

## 3. Key Evidence Interpretation

The northern Great Plains patch-burn study is particularly important for governance: both cow-calf pairs and sheep consistently selected recently burned patches with higher protein and moisture and lower fiber, even though those patches could have lower available biomass. This directly demonstrates why quantity and quality must remain separate.

The Nevada summer-range study found both cattle and sheep diets dominated by graminoids in that ecological and seasonal context, while also identifying forbs as an important dietary component. The New Mexico mixed-species study found different cattle and sheep diet composition and an effect of bonding/management on sheep diets. These studies support species- and context-dependent interpretation, not universal dietary percentages.

## 4. Preliminary Factor Decision

| Criterion | Decision |
|---|---|
| Scientifically relevant to both Profiles | Yes |
| Shared measurable Land Facts | Yes |
| Remotely observable components | Yes, modeled cover and production |
| Complete forage interpretation remotely possible | No |
| Numeric suitability rule supported | No |
| Carrying-capacity rule supported | No |
| Candidate MVP status | `IN MVP SHARED CORE - CONDITIONAL` |

## 5. Next Audit Tasks

1. Obtain the current Mireye field catalog; the previously recorded endpoint returned HTTP 404 during the 2026-08-07 audit.
2. Execute and snapshot RAP v3 API contract tests against representative polygons.
3. Verify RAP geographic/application coverage and improved-pasture limitations from current metadata.
4. Freeze parcel aggregation separately for cover, annual production, 16-day production, and interannual variability.
5. Define field-verification triggers and decide whether another source is required outside reviewed rangeland coverage.
6. Only after the data gate, decide whether F02 can emit a directional qualitative signal or must initially remain `CONTEXT_DEPENDENT`.
