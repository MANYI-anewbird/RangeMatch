# RangeMatch Context Decomposition Standard

> Status: `CANONICAL`
> Language: English
> Last updated: 2026-08-07

## 1. Core Principle

> A geographic or descriptive label must not be used as a causal suitability input when its meaning can be represented by measurable Land Variables or Context Variables.

RangeMatch is intended to match an operation to physical, environmental, infrastructural, and market conditions. It does not match an operation to a place name.

```text
Do not evaluate: "Texas"
Evaluate: the measurable conditions at the parcel
```

Another U.S. parcel with materially similar environmental and operational conditions should receive the same deterministic interpretation under the same rule and data versions, regardless of its state name.

## 2. Role of Coordinates and Place Names

Coordinates and parcel geometry are lookup keys and spatial anchors. They identify where data should be collected and how it should be aggregated. Latitude, longitude, state, county, and region names must not receive a suitability weight merely because they identify a place.

A coordinate may influence a decision only through an explicitly reviewed relationship or through variables retrieved or derived at that location, such as climate normals, elevation, growing season, soil, vegetation, water, hazard exposure, access, or market proximity.

Place names remain valid for:

- source and study provenance;
- jurisdiction and policy lookup;
- data retrieval and spatial joins;
- ecological-site or regional model selection when evidence requires it;
- validation-set stratification;
- human-readable reporting.

They are not direct biological suitability signals.

## 3. Required Decomposition Examples

| Vague label or statement | Required measurable decomposition |
|---|---|
| `Texas parcel` | Parcel geometry, latitude/longitude, elevation, climate normals, heat, precipitation, drought, soil, vegetation, water, hazards, access, jurisdiction |
| `Southern U.S.` | Temperature distribution, humidity, heat-load days, growing-season length, precipitation seasonality, wetness/flood exposure, vegetation productivity |
| `Northern U.S.` | Temperature distribution, freeze days, snow persistence, growing-season length, seasonal forage availability |
| `Arid` | Precipitation, reference evapotranspiration, aridity index, drought frequency/severity, soil-water capacity |
| `Rugged` | Slope distribution, terrain ruggedness method/value, topographic position, movement barriers |
| `Good access` | Legal road frontage, travel time, road class, seasonal accessibility, distance to processing/market/services |
| `Near population` | Population within declared travel-time bands, labor availability proxies, service access, market distance |
| `Brush country` | Shrub/woody cover, vegetation composition, palatability, toxicity, density, height, accessibility |

The exact variable set must be evidence-gated. This table defines decomposition direction, not automatic approval of every listed variable.

## 4. Quantification Rules

- Prefer measured numeric values with explicit units, spatial resolution, temporal window, source, and uncertainty.
- Prefer parcel distributions over one-point values when within-parcel variation matters.
- Use climate normals and variability metrics separately from current conditions.
- Preserve raw values before creating bins or qualitative labels.
- Any bin, threshold, normalization, or derived index must have a versioned deterministic method.
- A numeric value does not become a suitability signal until a reviewed Species Requirement defines its interpretation.
- Numeric precision must not exceed source resolution or confidence.
- Missing values remain `UNKNOWN`; they are never converted to zero, average, pass, or fail without an approved imputation policy.

## 5. Controlled Categorical Data

Numeric representation is preferred when scientifically meaningful, but RangeMatch must not force every concept into an arbitrary number. Some variables are legitimately categorical, including soil drainage class, ecological site, land-cover class, legal access status, water-right status, and verified infrastructure condition.

Categorical data must use a controlled vocabulary, documented provenance, and explicit unknown state. Ordinal encoding is permitted only when the ordering has a reviewed meaning. A category code must not be treated as a continuous measurement.

## 6. Layer Separation

Measurable inputs must remain in the appropriate decision layer:

- `Biophysical Land Facts`: terrain, climate, soil, vegetation, water, hazards.
- `Operational Facts`: parcel configuration, fencing, infrastructure, verified livestock water.
- `Access and Market Context`: travel time, road access, labor/service and market proximity.
- `Legal and Policy Diligence`: jurisdiction, zoning, permits, water rights, environmental restrictions.

Population and market data may influence operational feasibility or diligence priority. They must not silently modify biological grazing suitability.

## 7. Model-Invariance Test

Before approving a rule, reviewers must ask:

> If two parcels in different states have equivalent reviewed input variables, would this rule interpret them equivalently?

If the answer is no, the rule must identify the additional measurable variable, jurisdictional rule, or evidence-supported regional modifier that explains the difference. A state or regional name alone is not an acceptable explanation.

## 8. Agent Constraint

The Agent may use place names to retrieve data and explain provenance. It may not infer climate, terrain, vegetation, water, market access, policy, or suitability from a place name when the corresponding variables have not been collected. The correct state is `UNKNOWN` or `NEEDS_VERIFICATION`.

