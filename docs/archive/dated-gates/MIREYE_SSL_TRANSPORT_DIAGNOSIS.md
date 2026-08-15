# Mireye SSL Transport Diagnosis

> **Historical incident diagnosis.** Mireye live calls subsequently passed on a clean network. This document describes the intercepted SafeBrowse network path, not current product availability.

> Date: 2026-08-08  
> Target: `https://api.mireye.com`  
> Final classification: **`BLOCKED_EXTERNAL_NETWORK_MIDDLEBOX_PLAINTEXT_HTTP_ON_443`**  
> Success state for this slice: **`BLOCKED_EXTERNAL`** (with sanitized evidence)  
> Related: `docs/MIREYE_SSL_ADAPTER_INCIDENT_2026-08-08.md`, `docs/MIREYE_ADAPTER_LIVE_GATE_RESULTS.md`

## 1. Environment validation (sanitized)

| Check | Result |
|---|---|
| `MIREYE_API_BASE_URL` | Present; resolves exactly to `https://api.mireye.com` |
| Duplicate scheme / wrong port / path | None |
| `MIREYE_API_KEY` | Present (length recorded only; value never printed) |
| Process proxy env (sandbox sessions) | Often injects local HTTP proxy `127.0.0.1:<ephemeral>` via `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY`; `NO_PROXY` typically `127.0.0.1,::1,localhost` only |
| Outside sandbox (`all` permissions) | Proxy env may be absent; failure still reproduces |

Sanitized JSON: `test-data/mireye-normalized/diagnostics/mireye_transport_diagnosis.json`

## 2. Transport matrix (no Authorization)

| Check | Result / error class |
|---|---|
| DNS A/AAAA | OK — IPv4 `66.241.124.184` (Fly.io PTR), IPv6 present |
| Direct TLS IPv4/IPv6 | `SSL_WRONG_VERSION_NUMBER` / LibreSSL protocol-version alert |
| Plaintext HTTP probe to `:443` | **`HTTP/1.1 302 Found`** → `https://www.safebrowse.io/warn.html?[REDACTED]` |
| curl HEAD/health | Fail before HTTP status (TLS alert / wrong version) |
| Python stdlib / venv HTTPS | Same TLS failure class |
| Control: `api.github.com` + certifi | TLS OK (proves Python CA path is otherwise usable) |

## 3. Root cause

**Not** Mireye API authentication.  
**Not** adapter URL construction (official HTTPS origin validated).  
**Not** fixed by Python TLS version knobs or `certifi` alone.

`api.mireye.com:443` is intercepted on this network path by a **SafeBrowse-class middlebox** that answers **plain HTTP** (302 warn page) on the TLS port. Clients that send a TLS ClientHello therefore observe `SSL: WRONG_VERSION_NUMBER` / TLS protocol-version alerts.

Secondary issue (sandbox only): local `HTTP(S)_PROXY` to `127.0.0.1` can add `PROXY_TUNNEL_FAILED` / CONNECT noise. That is mitigated in-process; it does **not** clear the SafeBrowse intercept.

## 4. Environment / client affected

| Layer | Status |
|---|---|
| DNS | Healthy (Fly.io customer address) |
| Local Cursor/sandbox HTTP proxy | Can interfere; scoped bypass added |
| System curl (LibreSSL) | Blocked at TLS to Mireye |
| `.venv-livegate` Python 3.13 + OpenSSL 3.0.15 | Blocked at TLS to Mireye |
| System Python 3.13 | Same |
| Mireye server (expected) | Not reachable as TLS from this path |

## 5. Minimal fix applied (transport-only)

1. **`src/rangematch/mireye_transport.py`**
   - Validate base URL == official HTTPS origin
   - Sanitized proxy reporting (scheme/host/port only)
   - Verified SSL context via **certifi** when installed (`verify` remains required)
   - **`scoped_env_proxy_bypass()`** — temporarily clears proxy env for the Mireye request only, then restores (default on; override with `MIREYE_TRANSPORT_BYPASS_ENV_PROXY=0`)
   - Classify SafeBrowse plaintext-HTTP-on-443 as `BLOCKED_EXTERNAL_...`
2. **`live_mireye_request`** uses the transport helpers; errors are redacted (no key / Authorization leakage)
3. **`certifi`** added to `pyproject.toml` dependencies
4. Regression tests: `tests/test_mireye_transport.py`

No normalization semantics, F01–F08, Planner DAG, MatchResult, or science fixtures were changed.

## 6. What was not done (policy)

- No `verify=False`
- No custom CA install / system security changes
- No base-URL redirect away from `https://api.mireye.com`
- No global deletion of user proxy settings
- No Planner Executor work

## 7. Live gate after fix

All three CPER contexts remain **`BLOCKED_EXTERNAL`** until SafeBrowse (or equivalent) **whitelists** `api.mireye.com` or the machine uses a non-intercepting network path.

See refreshed `docs/MIREYE_ADAPTER_LIVE_GATE_RESULTS.md`.

## 8. Closure / re-run

After network whitelist:

1. Re-run `diagnose_mireye_transport` → expect `TRANSPORT_OK` on `/healthz`
2. Re-run `run_cper_live_gate` once
3. Save sanitized raw + normalized artifacts
4. Flip this diagnosis / live-gate docs to `LIVE_VERIFIED` or `PARTIAL`
5. Close `MIREYE_SSL_ADAPTER_INCIDENT` only after successful point QA
