# Mireye Audit Fixtures

These credential-free files preserve the API contracts used by the RangeMatch live-data audit on 2026-08-07.

| File | Purpose | SHA-256 |
|---|---|---|
| `field_catalog_v0.14.0.json` | Public field catalog returned by `GET /v1/meta/fields` | `205aa856ec719270d338205fe9b41eaca294b7afb95e94fe8296a196562f3ab4` |
| `openapi_v0.14.0.json` | Public OpenAPI schema returned by `GET /v1/openapi.json` | `e0f8aa69e51770395380d735e6d6675c89c2fb243eeb4f4ae7fba4f83fa58e32` |
| `cper_001_point_response_2026-08-07.json` | Authenticated `POST /v1/fetch` response for the CPER engineering-test centroid | `0e923174d5158af14afe0411d582934f4ccb6c625d24ac9072d3c4da9d255d7f` |

The response fixture contains only requested coordinates, returned field data, provenance, confidence, timestamps, and status. It contains no request header, token, or API key.

These fixtures verify a point lookup only. They must not be treated as parcel aggregation or agricultural suitability evidence.
