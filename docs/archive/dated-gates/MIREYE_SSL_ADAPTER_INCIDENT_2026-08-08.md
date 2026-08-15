# Mireye SSL Adapter / Environment Incident — 2026-08-08

> Status: `RESOLVED_BY_NETWORK_CHANGE — original network remains filtered`
> Classification: **network middlebox / SafeBrowse intercept** (transport only)
> Affects: F04 / F05 Mireye **point QA** and unified Mireye live adapter

Latest controlled recheck: `docs/MIREYE_LIVE_RECHECK_RESULTS_2026-08-08.md`. Classification remains unchanged; DNS and configured origin pass, while SafeBrowse still returns plaintext HTTP on port 443 before TLS.

Follow-up on a different network passed TLS, `/healthz`, authenticated lookup, and the three CPER context calls. See `docs/MIREYE_LIVE_RECHECK_SUCCESS_2026-08-08.md`. The original network configuration remains a known external limitation; no TLS bypass was introduced.
> Does **not** invalidate: NOAA/NCEI F05 canonical precip, USDA SDA F04 parcel facts, RAP, NHD, MatchResults, offline Mireye normalization

## 1. Symptom

HTTPS calls to `api.mireye.com` failed with:

```text
SSL: WRONG_VERSION_NUMBER
```

(also LibreSSL `tlsv1 alert protocol version` via curl)

## 2. Diagnosis (2026-08-08)

Full write-up: `docs/MIREYE_SSL_TRANSPORT_DIAGNOSIS.md`

Root cause: on this network path, `api.mireye.com:443` answers **plain HTTP** `302` to `safebrowse.io`, so TLS ClientHello fails with wrong-version. DNS still points at Fly.io; the intercept is on-path, not an adapter URL bug.

Minimal transport mitigations shipped (proxy scope bypass + certifi verified context + classification). They do not clear SafeBrowse.

## 3. Scientific / product impact

| Artifact | Impact |
|---|---|
| Canonical NOAA precip Land Facts | None — retained |
| SDA parcel soil / wetness / ecosite facts | None — retained |
| RAP / NHD / 3DEP collection | None |
| MatchResult labels / factor signals | Not rewritten for this incident |
| Offline Mireye normalized contexts | Valid |
| Live Mireye gates | `BLOCKED_EXTERNAL` until whitelist |

```yaml
potential_rule_issue: null
investigation_required: false
runtime_rule_changed: false
land_facts_or_match_results_changed_by_incident: false
transport_diagnosis: BLOCKED_EXTERNAL_NETWORK_MIDDLEBOX_PLAINTEXT_HTTP_ON_443
```

## 4. Remediation policy

1. Whitelist `api.mireye.com` in SafeBrowse / parental-control / corporate filter, **or** use a non-intercepting network.
2. Re-run transport diagnosis → expect `TRANSPORT_OK`.
3. Re-run **Mireye point QA / live gate only** (CPER + frozen parcels as needed).
4. Do **not** re-run NOAA NetCDF, SDA, RAP, or NHD canonical paths unless those contracts change.

## 5. Closure criteria

- Successful Mireye `/healthz` TLS from this environment
- Successful `/v1/fetch` (and lookup if in scope) with sanitized artifacts
- Incident status → `CLOSED`
- No Factor rule version bump required solely for this fix
