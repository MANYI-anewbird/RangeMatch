# Mireye SSL Adapter / Environment Incident — 2026-08-08

> Status: `OPEN — ADAPTER/ENVIRONMENT ONLY`  
> Classification: data-path degradation  
> Affects: F04 / F05 Mireye **point QA** only  
> Does **not** invalidate: NOAA/NCEI F05 canonical precip, USDA SDA F04 parcel facts, RAP, NHD, MatchResults

## 1. Symptom

During cross-parcel F01–F05 runs for Konza, Reynolds, Ordway, and KBS MCSE, HTTPS calls to `api.mireye.com` failed with:

```text
SSL: WRONG_VERSION_NUMBER
```

Collection statuses:

- F04: `PARTIAL` / path `DEGRADED` (SDA primary path succeeded; Mireye point QA failed)
- F05: `PARTIAL` / path `DEGRADED` (NOAA/NCEI `annprcp_norm` succeeded; Mireye drought/temp/heat QA failed)

## 2. Scientific / product impact

| Artifact | Impact |
|---|---|
| Canonical NOAA precip Land Facts | None — retained |
| SDA parcel soil / wetness / ecosite facts | None — retained |
| RAP / NHD / 3DEP collection | None |
| MatchResult labels / factor signals | Not rewritten for this incident |
| Geometry freeze | Unchanged |

```yaml
potential_rule_issue: null
investigation_required: true
runtime_rule_changed: false
land_facts_or_match_results_changed_by_incident: false
```

## 3. Remediation policy

1. Diagnose transport/TLS/proxy/environment separately from Factor science.
2. After fix, re-run **Mireye point QA only** on the five frozen parcels.
3. Do **not** re-run NOAA NetCDF sampling, SDA tabular/WFS, RAP aggregate, or NHD inventory unless those contracts change.
4. Merge refreshed point-QA fixtures into existing Land Profiles without altering canonical precip values or SDA-derived distributions.

## 4. Closure criteria

- Successful Mireye `/v1/fetch` point QA on CPER and at least one non-CPER frozen parcel
- Point-QA fixtures updated with provenance
- Incident status set to `CLOSED`
- No Factor rule version bump required solely for this fix
