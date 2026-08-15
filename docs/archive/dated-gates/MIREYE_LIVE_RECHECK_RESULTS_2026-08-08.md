# Mireye Live Recheck Gate

> **Historical failed-network gate.** A later clean-network recheck succeeded. See `MIREYE_LIVE_RECHECK_SUCCESS_2026-08-08.md` and `CURRENT_SYSTEM_BASELINE.md`. The findings below remain valid only for the intercepted network path tested at that time.

> Date: 2026-08-08
> Gate status: `BLOCKED_EXTERNAL`
> Transport classification: `BLOCKED_EXTERNAL_NETWORK_MIDDLEBOX_PLAINTEXT_HTTP_ON_443`
> Official origin: `https://api.mireye.com`

## Decision

The narrow transport recheck did not reach Mireye TLS or HTTP application handling. DNS resolved and the configured base URL matched the official HTTPS origin, but the network path returned plaintext HTTP on port 443 with a SafeBrowse redirect. Direct TLS and the unauthenticated `/healthz` probe therefore failed before an API response was available.

Per the gate contract, authenticated Property, Land, and Hazard requests were **not attempted** after transport failed. This prevents an external middlebox failure from being mislabeled as an authentication, endpoint, or response-contract failure.

## Sanitized result

```yaml
base_url_validation: PASS
credential_present: true
dns: PASS
tls_direct: FAIL
https_health: FAIL_BEFORE_HTTP_RESPONSE
plaintext_http_on_443: true
safebrowse_redirect: true
classification: BLOCKED_EXTERNAL_NETWORK_MIDDLEBOX_PLAINTEXT_HTTP_ON_443
authenticated_context_calls: NOT_ATTEMPTED_TRANSPORT_GATE_FAILED
property_context: NOT_TESTED
land_context: NOT_TESTED
hazard_context: NOT_TESTED
f01_f08_writes: NONE
match_result_changes: NONE
```

## Evidence

- Sanitized diagnosis: `test-data/mireye-normalized/diagnostics/mireye_transport_recheck_2026-08-08.json`
- Previous root-cause analysis: `docs/MIREYE_SSL_TRANSPORT_DIAGNOSIS.md`
- Existing adapter gate: `docs/MIREYE_ADAPTER_LIVE_GATE_RESULTS.md`

No API key, Authorization value, or credential-bearing response body is stored in the diagnosis artifact.

## Runtime decision

```yaml
offline_fixture_adapter: READY
live_mireye_from_current_network: NOT_READY
planner_live_mireye: BLOCKED_EXTERNAL
parcel_map_workflow: NOT_BLOCKED
canonical_f01_f08_paths: NOT_BLOCKED
```

RangeMatch must continue to show `BLOCKED_EXTERNAL` and must not silently substitute a live failure with fixture data.

## Next recheck condition

Re-run this gate only after either:

1. `api.mireye.com` is allowed through SafeBrowse/network filtering; or
2. the machine is connected through a non-intercepting network, such as a verified mobile hotspot.

Only after the transport diagnosis becomes `TRANSPORT_OK` should the controlled CPER Property/Land/Hazard calls run.
