# Diligence Search Live Gate — 2026-08-08

## Result

```yaml
provider: OPENAI
api: Responses API
tool: web_search
model: gpt-5.6-terra
jurisdiction: Weld County, Colorado, United States
topics:
  - CURRENT_DROUGHT
  - LOCAL_AG_GUIDANCE
status: COMPLETE
approved_source_count: 12
effect_on_engine: NONE
```

The gate returned current drought context and local agricultural guidance with
clickable sources from Drought.gov, the U.S. Drought Monitor, and USDA NRCS.
The result also identified an apparent inconsistency within the county drought
dashboard and recommended checking the underlying weekly data rather than
turning the search text into a parcel fact.

## Governance confirmation

- Only HTTPS government / university sources survived normalization.
- Search results remained `DILIGENCE_CONTEXT_ONLY`.
- No F01–F08 Land Fact, Factor signal, Engine decision, or ranking changed.
- Search did not claim usable water, forage condition, legal access, permit
  certainty, carrying capacity, or profitability.
- The initial default `gpt-4o-mini` request failed with HTTP 400; the
  account-available web-search-capable `gpt-5.6-terra` model passed.

