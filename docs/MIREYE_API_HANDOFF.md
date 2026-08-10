# Mireye API Handoff for RangeMatch

> Status: `AWAITING MIREYE MATERIALS`
> Purpose: Securely provide the documentation and test inputs required for the RangeMatch Live Data Availability Gate.
> Important: Never place a real API key in this document, chat, source code, screenshots, or Git.

## 1. Handoff Checklist

Place the available materials under:

```text
/Users/hongmanyi/RangeMatch/mireye/
```

Recommended structure:

```text
mireye/
  README.md
  openapi.yaml                 # or openapi.json
  field_catalog.json           # or CSV/XLSX supplied by Mireye
  postman_collection.json      # optional
  sample_request.json          # sanitized; no credential
  sample_response.json         # sanitized
  source_documents/            # PDFs or other official documentation

test-data/
  sample_parcel.geojson

.env                           # local secret; never committed
.env.example                   # variable names only
```

## 2. API Identification

Complete this section without entering a secret.

```yaml
provider: Mireye
api_product_name: TBD
api_version: TBD
documentation_url: TBD
base_url: TBD
environment: sandbox | production | TBD
support_contact: TBD
terms_or_license_url: TBD
```

## 3. Authentication

Record the authentication method, not the credential value.

```yaml
authentication_type: bearer_token | x_api_key | oauth2 | signed_request | other | TBD
header_name: Authorization | X-API-Key | TBD
token_prefix: Bearer | none | TBD
credential_environment_variable: MIREYE_API_TOKEN
credential_environment_variable_legacy_alias: MIREYE_API_KEY
additional_required_headers: []
token_expiration_behavior: dashboard_token_default_about_90_days
rate_limit_documentation: honor_retryable_and_Retry-After
```

Store the real credential only in:

```text
/Users/hongmanyi/RangeMatch/.env
```

Example local `.env` contents:

```dotenv
MIREYE_API_BASE_URL=https://replace-with-real-base-url
MIREYE_API_TOKEN=replace-with-real-secret
# MIREYE_API_KEY=replace-with-real-secret  # legacy alias still accepted
```

## 4. Required Endpoints

Provide the method and path for every available endpoint.

| Capability | Method | Path | Status | Notes |
|---|---|---|---|---|
| Health/version | TBD | TBD | Unknown | Used to record current API version |
| Field catalog/metadata | TBD | TBD | Unknown | Exact field IDs, units, source and semantics |
| Point analysis | TBD | TBD | Unknown | Must remain distinct from parcel analysis |
| Parcel/polygon analysis | TBD | TBD | Unknown | Preferred for parcel Land Facts |
| Parcel lookup/geometry | TBD | TBD | Unknown | If Mireye accepts parcel IDs |
| Batch request | TBD | TBD | Unknown | Optional |

## 5. Field Catalog Requirements

The field catalog or documentation should identify, where available:

```yaml
field_id: exact_machine_field_id
display_name: human-readable name
definition: exact scientific/data definition
unit: exact unit
data_type: number | string | category | geometry | object
spatial_semantics: point | pixel | parcel_summary | parcel_distribution
temporal_semantics: current | annual | normal | historical_series | other
source_dataset: upstream source
source_version: upstream version
resolution: spatial resolution or scale
coverage: documented geography
no_data_behavior: null | omitted | sentinel | other
confidence_or_uncertainty: description
last_updated: date or update policy
```

Do not map a Mireye field to a RangeMatch variable based only on a similar display name.

## 6. Test Parcel

Provide one engineering test geometry in GeoJSON. It may be a real demo parcel or a clearly labeled non-production test polygon.

Required information:

```yaml
test_parcel_id: TBD
geometry_file: /Users/hongmanyi/RangeMatch/test-data/sample_parcel.geojson
geometry_crs: EPSG:4326
is_real_property: true | false
expected_state: TBD
known_reference_facts: []
permission_to_call_sandbox_api: true | false
permission_to_call_production_api: true | false
```

Do not include owner names, private contact details, financial records, or other unnecessary personal information.

## 7. Sanitized Request and Response

If Mireye provides an example, save it without credentials. Preserve the complete response structure, including nulls, units, source metadata, confidence, and errors.

Before saving a sample, remove:

- API keys and tokens;
- cookies and signed URLs;
- owner or customer information;
- private parcel identifiers when unnecessary;
- request IDs that Mireye considers confidential.

## 8. RangeMatch Verification Procedure

After the handoff is complete, RangeMatch will perform the following read-only checks:

1. Confirm that `.env` is ignored by Git before reading credentials.
2. Verify the API base URL, health/version endpoint, and authentication behavior.
3. Retrieve and snapshot the current field catalog.
4. Record exact field IDs, units, spatial/temporal semantics, upstream sources, version, and no-data behavior.
5. Call the API for the test point and/or test parcel.
6. Store a sanitized response fixture without credentials.
7. Map only semantically matching fields into `DATA_SOURCE_AND_MIREYE_AUDIT.yaml`.
8. Compare F01 fields with USGS 3DEP and F02 fields with RAP where scientifically appropriate.
9. Mark every RangeMatch variable as `MIREYE_VERIFIED`, `OPEN_DATA_VERIFIED`, `DERIVABLE_VERIFIED`, `AUDIT_BLOCKED`, or another approved availability state.
10. Add API contract tests and document rate limits, failures, and fallback behavior.

## 9. Completion Gate

The Mireye handoff is complete only when:

- API documentation or an OpenAPI/Postman artifact is present;
- authentication method is documented;
- the real credential exists only in the ignored local `.env`;
- a current field catalog or equivalent metadata export is available;
- one test parcel is available;
- at least one authenticated test request succeeds;
- the sanitized response schema is saved;
- no secret appears in tracked files.

