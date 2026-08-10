# F03/F04 Confirmed-Parcel Live Gate — 2026-08-08

## Result

`PASSED`

The one-parcel LIVE workflow resolved and explicitly confirmed the CPER test
parcel, then ran the same Planner/Executor path used by the product. No fixture
was substituted for a failed live source.

## F03 — Livestock Water

- Canonical discovery source: USGS NHDPlus HR
- State: `MAPPED_CANDIDATES_ONLY`
- Signal: `NEEDS_VERIFICATION`
- `FIELD_VERIFIED`: zero
- Stable max-3 remote-review queue created
- Imagery review: `PENDING_PROVENANCE_COMPLETE_REVIEW`
- Ranking effect: `NONE`

NHD geometry and FCode attributes provide candidate context only. They do not
prove physical presence on the current date, livestock accessibility,
reliability, capacity, water quality, infrastructure, or legal access. NAIP
imagery must have complete acquisition/review/artifact provenance before it
can support remote promotion; this runtime did not manufacture that review.

## F04 — Soil, Wetness, and Ecological Site

- Canonical sources: USDA-NRCS SDA SSURGO tabular + SDA WFS MapunitPoly
- Coverage: `COMPLETE`
- Requested area: `1,948,514.793268538 m²`
- Valid SDA area: `1,948,514.793268425 m²`
- Coverage fraction: `0.9999999999999419`
- State: `PARCEL_COMPLETE`
- Signal: `CONTEXT_DEPENDENT`
- Ranking effect: `NONE`

The adapter preserves component distributions, drainage/hydrologic groups,
monthly ponding/flooding context, restrictive-layer records, and ecological
site linkages. It does not create a composite soil score. EDIT public-page
accessibility was not fetched in this runtime and therefore remains unknown.

## Whole investigation

- F01–F08 collection/derivation attempted after parcel confirmation
- Factor-local failures: none
- Investigation: `COMPLETED`
- Cow-Calf: `HOLD`
- Sheep: `HOLD`
- Ranking permitted: false
- Full backend suite after integration: `409 passed`

`HOLD` continues to mean incomplete reviewed decision evidence, not that the
parcel is unsuitable.
