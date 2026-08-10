# Mireye parcel-lookup fixtures

Offline `/v1/lookup` payloads for the LIVE parcel resolver adapter
(`src/rangematch/mireye_parcel_resolver.py`).

**No network.** These fixtures exercise disposition mapping only.

| scenario_id | Expected RangeMatch status |
|---|---|
| `resolved_with_parcel` | `NEEDS_BOUNDARY_CONFIRMATION` |
| `resolved_parcel_unavailable` | `PARCEL_DATA_UNAVAILABLE` |
| `clarify_with_parcels` | `NEEDS_USER_SELECTION` |
| `clarify_points_only` | `AMBIGUOUS` |
| `no_match` | `NO_MATCH` |
| `geocode_range_interpolation` | `GEOCODE_QUALITY_INSUFFICIENT` |
| `apn_not_supported` | `NO_MATCH` |

Owner fields in payloads are redacted by the adapter.
