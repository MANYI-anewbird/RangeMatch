# Parcel resolution fixtures

Explicit OFFLINE scenarios for `rangematch.parcel_resolution`.
Never used as silent LIVE fallback. CPER geometry appears only in
`silent_cper_substitution.json` as a negative test case.

Land entry kinds:

| Fixture | `input_kind` | Notes |
|---|---|---|
| `one_valid_candidate` | ADDRESS (default) | Full street address |
| `coord_one_valid_candidate` | COORDINATE | lat/lng query point → same confirm gate |
| most others | ADDRESS | Address-driven outcomes |
