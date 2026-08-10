# Mireye Adapter Live Gate Results — CPER

> **Historical failed-network gate.** Live lookup and context calls subsequently passed on a clean network; see `MIREYE_LIVE_RECHECK_SUCCESS_2026-08-08.md`. Preserve this file as fail-closed transport evidence only.

> Date: 2026-08-08
> Gate: `MIREYE_ADAPTER_CPER_LIVE_GATE`
> Adapter: `MIREYE_UNIFIED_CONTEXT_ADAPTER@0.1.0`
> Historical status: **`BLOCKED_EXTERNAL`** on the original filtered network
> Transport class: `BLOCKED_EXTERNAL_NETWORK_MIDDLEBOX_PLAINTEXT_HTTP_ON_443`
> Evidence: `docs/MIREYE_SSL_TRANSPORT_DIAGNOSIS.md`
> Diagnosis JSON: `test-data/mireye-normalized/diagnostics/mireye_transport_diagnosis.json`
> Summary: `test-data/mireye-normalized/live-gate-cper/live_gate_summary.json`
> Latest recheck: `docs/MIREYE_LIVE_RECHECK_RESULTS_2026-08-08.md` — still `BLOCKED_EXTERNAL`; authenticated context calls were not attempted because the transport gate failed.

> Current-network follow-up: `docs/MIREYE_LIVE_RECHECK_SUCCESS_2026-08-08.md` — `TRANSPORT_OK`; Property, Land, and Hazard contexts live-verified.

## Scope

Controlled one-shot live attempts for CPER centroid `(40.825, -104.7625)`:

| Context | Endpoint | Preset / input |
|---|---|---|
| `POINT_LAND_CONTEXT` | `POST /v1/fetch` | `terrain` + `lcms_class`, `land_use_class` |
| `POINT_HAZARD_CONTEXT` | `POST /v1/fetch` | `flood_risk` + `tree_canopy_pct`, `ndvi_current` |
| `PROPERTY_DILIGENCE_CONTEXT` | `POST /v1/lookup` | coordinate `kind=coord` (OpenAPI-supported; no invented address) |

## Endpoint / adapter status (post transport fix)

| Context | HTTP | Adapter status | Gate status | Error class |
|---|---|---|---|---|
| POINT_LAND_CONTEXT | n/a | `FAILED` | `BLOCKED_EXTERNAL` | middlebox plaintext HTTP on :443 |
| POINT_HAZARD_CONTEXT | n/a | `FAILED` | `BLOCKED_EXTERNAL` | same |
| PROPERTY_DILIGENCE_CONTEXT | n/a | `FAILED` | `BLOCKED_EXTERNAL` | same (coordinate lookup attempted) |

No sanitized live raw/normalized context bodies were written because TLS never completed (middlebox returned plain HTTP 302 to SafeBrowse before any Mireye API body).

Offline normalization fixtures remain valid under `test-data/mireye-normalized/`.

## Safety confirmations

| Check | Result |
|---|---|
| API keys/tokens in live-gate / diagnosis artifacts | **Absent** (`credential_safety: PASS`) |
| F01–F08 Land Fact writes | **None** |
| MatchResult changes | **None** |
| Invented address for lookup | **None** |
| `verify=False` / custom CA | **Not used** |
| Official HTTPS host retained | **Yes** (`https://api.mireye.com`) |

## Transport mitigations shipped

- Process-local proxy bypass for Mireye requests (`MIREYE_TRANSPORT_BYPASS_ENV_PROXY`, default on)
- certifi-backed verified SSL context
- Fail-closed base URL validation
- Explicit `BLOCKED_EXTERNAL` classification when `:443` speaks SafeBrowse plain HTTP

These do **not** bypass SafeBrowse. Live HTTP requires network whitelist or a non-intercepting path.

## Planner Executor live-readiness

| Mode | Ready? |
|---|---|
| Offline / fixture-backed Mireye contexts | **YES** |
| Live Mireye from this host/network | **NO** — `BLOCKED_EXTERNAL` |
| Planner Executor slice | May proceed **fixture-backed / fail-closed**; must not assume live Mireye until diagnosis flips to `TRANSPORT_OK` |
