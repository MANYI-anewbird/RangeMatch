"""Controlled Mireye POST /v1/lookup HTTP transport for LIVE parcel resolution.

Reuses verified HTTPS helpers from mireye_transport / mireye_adapter.
Never logs, persists, or returns Bearer tokens. Never falls back to FIXTURE.
Catalog gate context is recorded separately and does not redefine parcel status.

Contract: docs/MIREYE_LIVE_PARCEL_RESOLVER_CONTRACT.md
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Literal, Mapping, MutableMapping, Sequence
from urllib import error as urllib_error
from urllib import request as urllib_request

from rangematch.mireye_adapter import (
    MireyeAdapterError,
    _bypass_env_proxy_flag,
    _env_base_url,
    assert_no_credentials,
    resolve_mireye_api_token,
    sanitize_for_storage,
)
from rangematch.mireye_transport import (
    classify_tls_failure,
    mireye_urlopen,
    probe_plaintext_http_on_443,
    redact_transport_message,
)
from rangematch.unified_output import sha256_canonical

ENDPOINT_LOOKUP = "/v1/lookup"
MAX_INPUT_LEN = 256
MIN_INPUT_LEN = 1
MAX_RETRIES = 2  # additional attempts after the first
DEFAULT_MAX_SLEEP_SECONDS = 30.0
DEFAULT_TIMEOUT_SECONDS = 60.0

LookupKind = Literal["address", "coord"]

# Error classes exposed on transport meta / resolution provenance.
AUTH_FAILED = "AUTH_FAILED"
FORBIDDEN = "FORBIDDEN"
INVALID_INPUT = "INVALID_INPUT"
RATE_LIMITED = "RATE_LIMITED"
SERVER_ERROR = "SERVER_ERROR"
BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
RESPONSE_CONTRACT_CHANGED = "RESPONSE_CONTRACT_CHANGED"
MALFORMED_JSON = "MALFORMED_JSON"
NETWORK_NOT_AUTHORIZED = "NETWORK_NOT_AUTHORIZED"
TOKEN_MISSING = "TOKEN_MISSING"
APN_NOT_SUPPORTED = "APN_NOT_SUPPORTED_IN_V1"
RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
TRANSPORT_ERROR = "TRANSPORT_ERROR"

_RETRYABLE = frozenset({RATE_LIMITED, UPSTREAM_TIMEOUT, SERVER_ERROR})


@dataclass
class LookupHttpResponse:
    """Minimal injectable HTTP response (no Authorization headers stored)."""

    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)


HttpPostFn = Callable[..., LookupHttpResponse]
SleeperFn = Callable[[float], None]


@dataclass
class LookupTransportResult:
    ok: bool
    error_class: str | None
    http_status: int | None
    sanitized_response: dict[str, Any] | None
    response_hash: str | None
    request_hash: str | None
    attempts: int
    retries: int
    sleep_seconds: list[float]
    retrieved_at: str
    endpoint: str
    kind: LookupKind
    input_length: int
    input_fingerprint: str
    limitations: list[str] = field(default_factory=list)
    catalog_context: dict[str, Any] = field(default_factory=dict)
    retryable: bool = False
    disposition: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        """Sanitized public view — never includes token or raw Authorization."""
        payload = asdict(self)
        # Defense in depth
        text = json.dumps(payload, ensure_ascii=False)
        assert_no_credentials(text, label="lookup_transport_result")
        return payload


class LookupTransportError(RuntimeError):
    def __init__(self, error_class: str, message: str, *, result: LookupTransportResult | None = None):
        self.error_class = error_class
        self.message = message
        self.result = result
        super().__init__(f"{error_class}:{message}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _header_get(headers: Mapping[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if str(key).lower() == target:
            return str(value)
    return None


def parse_retry_after_seconds(
    value: str | None, *, max_sleep_seconds: float
) -> float:
    if value is None or str(value).strip() == "":
        return min(3.0, max_sleep_seconds)
    raw = str(value).strip()
    try:
        seconds = float(raw)
    except ValueError:
        # HTTP-date not parsed in this slice — use bounded default.
        seconds = 5.0
    if seconds < 0:
        seconds = 0.0
    return min(seconds, max_sleep_seconds)


def validate_lookup_input(input_text: str, *, kind: LookupKind) -> str:
    text = str(input_text or "").strip()
    if len(text) < MIN_INPUT_LEN or len(text) > MAX_INPUT_LEN:
        raise LookupTransportError(
            INVALID_INPUT,
            f"input length must be {MIN_INPUT_LEN}–{MAX_INPUT_LEN} characters",
        )
    if kind == "address" and re.match(r"(?i)^\s*apn\s*[:=]", text):
        raise LookupTransportError(
            APN_NOT_SUPPORTED,
            "APN-only lookup is not supported in Mireye /v1/lookup v1",
        )
    if kind == "coord":
        parts = [p.strip() for p in text.split(",")]
        if len(parts) != 2:
            raise LookupTransportError(INVALID_INPUT, "coord kind requires 'lat,lng'")
        try:
            float(parts[0])
            float(parts[1])
        except ValueError as exc:
            raise LookupTransportError(INVALID_INPUT, "coord values must be numeric") from exc
    return text


def classify_lookup_http_status(
    status: int, *, retryable_flag: bool | None = None
) -> tuple[str, bool]:
    """Return (error_class, retryable)."""
    if status == 401:
        return AUTH_FAILED, False
    if status == 403:
        return FORBIDDEN, False
    if status == 422:
        return INVALID_INPUT, False
    if status == 404:
        return INVALID_INPUT, False
    if status == 429:
        return RATE_LIMITED, True
    if status == 504:
        return UPSTREAM_TIMEOUT, True
    if status >= 500:
        # Allow explicit retryable flag from body; default retry 503/504-like.
        retryable = True if retryable_flag is None else bool(retryable_flag)
        return SERVER_ERROR, retryable
    if status == 200:
        return "OK", False
    return TRANSPORT_ERROR, False


def _default_http_post(
    *,
    url: str,
    headers: Mapping[str, str],
    body: bytes,
    timeout_seconds: float,
    bypass_env_proxy: bool,
) -> LookupHttpResponse:
    req = urllib_request.Request(
        url,
        data=body,
        method="POST",
        headers=dict(headers),
    )
    try:
        with mireye_urlopen(
            req, timeout=timeout_seconds, bypass_env_proxy=bypass_env_proxy
        ) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            raw_headers = {k: v for k, v in resp.headers.items()}
            # Strip any accidentally echoed authorization
            raw_headers = {
                k: v
                for k, v in raw_headers.items()
                if str(k).lower() not in {"authorization", "proxy-authorization"}
            }
            return LookupHttpResponse(
                status=int(status),
                body=resp.read(),
                headers=raw_headers,
            )
    except urllib_error.HTTPError as exc:
        raw_headers = {}
        if exc.headers:
            raw_headers = {
                k: v
                for k, v in exc.headers.items()
                if str(k).lower() not in {"authorization", "proxy-authorization"}
            }
        body = exc.read()
        return LookupHttpResponse(status=int(exc.code), body=body, headers=raw_headers)


def _body_retryable(payload: Any) -> bool | None:
    if not isinstance(payload, Mapping):
        return None
    if "retryable" in payload:
        return bool(payload.get("retryable"))
    err = payload.get("error")
    if isinstance(err, Mapping) and "retryable" in err:
        return bool(err.get("retryable"))
    return None


def _parse_json_body(body: bytes) -> tuple[dict[str, Any] | None, str | None]:
    if not body:
        return None, MALFORMED_JSON
    try:
        text = body.decode("utf-8")
        payload = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, MALFORMED_JSON
    if not isinstance(payload, dict):
        return None, RESPONSE_CONTRACT_CHANGED
    return payload, None


def lookup_parcel_via_mireye(
    input_text: str,
    *,
    kind: LookupKind = "address",
    allow_network: bool = False,
    include_parcel: bool = True,
    http_post: HttpPostFn | None = None,
    sleeper: SleeperFn | None = None,
    max_retries: int = MAX_RETRIES,
    max_sleep_seconds: float = DEFAULT_MAX_SLEEP_SECONDS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    catalog_context: Mapping[str, Any] | None = None,
    bypass_env_proxy: bool | None = None,
) -> LookupTransportResult:
    """POST /v1/lookup once (with bounded retries). Never returns the token."""
    retrieved_at = _utc_now()
    catalog_ctx = dict(catalog_context or {})
    catalog_ctx.setdefault("affects_parcel_resolution", False)

    limitations = [
        "Mireye /v1/lookup transport — no FIXTURE fallback on failure.",
        "Owner PII is redacted after sanitize; Authorization is never stored.",
        "Catalog compatibility is context only and does not redefine parcel status.",
    ]

    try:
        cleaned = validate_lookup_input(input_text, kind=kind)
    except LookupTransportError as exc:
        return LookupTransportResult(
            ok=False,
            error_class=exc.error_class,
            http_status=None,
            sanitized_response=None,
            response_hash=None,
            request_hash=None,
            attempts=0,
            retries=0,
            sleep_seconds=[],
            retrieved_at=retrieved_at,
            endpoint=ENDPOINT_LOOKUP,
            kind=kind,
            input_length=len(str(input_text or "")),
            input_fingerprint=sha256_canonical({"kind": kind, "len": len(str(input_text or ""))}),
            limitations=limitations + [exc.message],
            catalog_context=catalog_ctx,
        )

    request_body = {
        "input": cleaned,
        "kind": kind,
        "include_parcel": bool(include_parcel),
    }
    request_hash = sha256_canonical(request_body)
    input_fingerprint = sha256_canonical(
        {"kind": kind, "input_sha256": sha256_canonical({"input": cleaned})}
    )

    if not allow_network:
        return LookupTransportResult(
            ok=False,
            error_class=NETWORK_NOT_AUTHORIZED,
            http_status=None,
            sanitized_response=None,
            response_hash=None,
            request_hash=request_hash,
            attempts=0,
            retries=0,
            sleep_seconds=[],
            retrieved_at=retrieved_at,
            endpoint=ENDPOINT_LOOKUP,
            kind=kind,
            input_length=len(cleaned),
            input_fingerprint=input_fingerprint,
            limitations=limitations
            + [
                "NETWORK_NOT_AUTHORIZED: allow_network=false; no HTTP call made.",
                "CPER/demo fixtures were not substituted.",
            ],
            catalog_context=catalog_ctx,
        )

    token = resolve_mireye_api_token()
    if not token:
        return LookupTransportResult(
            ok=False,
            error_class=TOKEN_MISSING,
            http_status=None,
            sanitized_response=None,
            response_hash=None,
            request_hash=request_hash,
            attempts=0,
            retries=0,
            sleep_seconds=[],
            retrieved_at=retrieved_at,
            endpoint=ENDPOINT_LOOKUP,
            kind=kind,
            input_length=len(cleaned),
            input_fingerprint=input_fingerprint,
            limitations=limitations + ["MIREYE_API_TOKEN / MIREYE_API_KEY missing."],
            catalog_context=catalog_ctx,
        )

    try:
        base = _env_base_url()
    except MireyeAdapterError as exc:
        return LookupTransportResult(
            ok=False,
            error_class=BLOCKED_EXTERNAL,
            http_status=None,
            sanitized_response=None,
            response_hash=None,
            request_hash=request_hash,
            attempts=0,
            retries=0,
            sleep_seconds=[],
            retrieved_at=retrieved_at,
            endpoint=ENDPOINT_LOOKUP,
            kind=kind,
            input_length=len(cleaned),
            input_fingerprint=input_fingerprint,
            limitations=limitations + [str(exc)],
            catalog_context=catalog_ctx,
        )

    if bypass_env_proxy is None:
        bypass_env_proxy = _bypass_env_proxy_flag()
    url = f"{base}{ENDPOINT_LOOKUP}"
    body_bytes = json.dumps(request_body).encode("utf-8")
    # Headers used for the request only — never persisted.
    request_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }

    post = http_post or (
        lambda **kwargs: _default_http_post(
            bypass_env_proxy=bool(bypass_env_proxy), **kwargs
        )
    )
    sleep_fn = sleeper or time.sleep

    attempts = 0
    sleeps: list[float] = []
    last_error_class: str | None = None
    last_status: int | None = None
    last_safe: dict[str, Any] | None = None

    while attempts <= max_retries:
        attempts += 1
        try:
            resp = post(
                url=url,
                headers=request_headers,
                body=body_bytes,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            probe = probe_plaintext_http_on_443()
            error_class = classify_tls_failure(exc, plaintext_probe=probe)
            # Normalize middlebox classes to BLOCKED_EXTERNAL for parcel status.
            if "BLOCKED_EXTERNAL" in error_class or "MIDDLEBOX" in error_class:
                mapped = BLOCKED_EXTERNAL
            else:
                mapped = BLOCKED_EXTERNAL
            redacted = redact_transport_message(
                f"{error_class}:{type(exc).__name__}", api_key=token
            )
            return LookupTransportResult(
                ok=False,
                error_class=mapped,
                http_status=None,
                sanitized_response=None,
                response_hash=None,
                request_hash=request_hash,
                attempts=attempts,
                retries=max(0, attempts - 1),
                sleep_seconds=sleeps,
                retrieved_at=retrieved_at,
                endpoint=ENDPOINT_LOOKUP,
                kind=kind,
                input_length=len(cleaned),
                input_fingerprint=input_fingerprint,
                limitations=limitations
                + [
                    redacted,
                    "TLS/middlebox failure — visible BLOCKED_EXTERNAL; no FIXTURE swap.",
                ],
                catalog_context=catalog_ctx,
            )

        last_status = int(resp.status)
        payload, parse_error = _parse_json_body(resp.body)
        if parse_error and last_status == 200:
            return LookupTransportResult(
                ok=False,
                error_class=parse_error,
                http_status=last_status,
                sanitized_response=None,
                response_hash=None,
                request_hash=request_hash,
                attempts=attempts,
                retries=max(0, attempts - 1),
                sleep_seconds=sleeps,
                retrieved_at=retrieved_at,
                endpoint=ENDPOINT_LOOKUP,
                kind=kind,
                input_length=len(cleaned),
                input_fingerprint=input_fingerprint,
                limitations=limitations + [f"response parse error: {parse_error}"],
                catalog_context=catalog_ctx,
            )

        retryable_flag = _body_retryable(payload) if payload else None
        error_class, retryable = classify_lookup_http_status(
            last_status, retryable_flag=retryable_flag
        )
        last_error_class = error_class if error_class != "OK" else None

        if last_status == 200:
            if not isinstance(payload, dict) or "disposition" not in payload:
                return LookupTransportResult(
                    ok=False,
                    error_class=RESPONSE_CONTRACT_CHANGED,
                    http_status=last_status,
                    sanitized_response=sanitize_for_storage(payload)
                    if isinstance(payload, dict)
                    else None,
                    response_hash=sha256_canonical(sanitize_for_storage(payload))
                    if isinstance(payload, dict)
                    else None,
                    request_hash=request_hash,
                    attempts=attempts,
                    retries=max(0, attempts - 1),
                    sleep_seconds=sleeps,
                    retrieved_at=retrieved_at,
                    endpoint=ENDPOINT_LOOKUP,
                    kind=kind,
                    input_length=len(cleaned),
                    input_fingerprint=input_fingerprint,
                    limitations=limitations
                    + ["200 response missing disposition — contract drift."],
                    catalog_context=catalog_ctx,
                )
            safe = sanitize_for_storage(payload)
            assert_no_credentials(safe, label="lookup_response")
            # Owner redaction is also applied in map_mireye_lookup_to_parcel.
            disposition = str(safe.get("disposition") or "").lower() or None
            return LookupTransportResult(
                ok=True,
                error_class=None,
                http_status=200,
                sanitized_response=safe if isinstance(safe, dict) else None,
                response_hash=sha256_canonical(safe),
                request_hash=request_hash,
                attempts=attempts,
                retries=max(0, attempts - 1),
                sleep_seconds=sleeps,
                retrieved_at=retrieved_at,
                endpoint=ENDPOINT_LOOKUP,
                kind=kind,
                input_length=len(cleaned),
                input_fingerprint=input_fingerprint,
                limitations=limitations,
                catalog_context=catalog_ctx,
                disposition=disposition,
            )

        # Non-200
        if isinstance(payload, dict):
            last_safe = sanitize_for_storage(payload)
            assert_no_credentials(last_safe, label="lookup_error_body")
        else:
            last_safe = None

        if (
            retryable
            and error_class in _RETRYABLE
            and attempts <= max_retries
        ):
            wait = parse_retry_after_seconds(
                _header_get(resp.headers, "Retry-After"),
                max_sleep_seconds=max_sleep_seconds,
            )
            sleeps.append(wait)
            sleep_fn(wait)
            continue

        final_class = error_class
        if retryable and attempts > max_retries:
            final_class = RETRY_EXHAUSTED
        return LookupTransportResult(
            ok=False,
            error_class=final_class,
            http_status=last_status,
            sanitized_response=last_safe if isinstance(last_safe, dict) else None,
            response_hash=sha256_canonical(last_safe) if last_safe else None,
            request_hash=request_hash,
            attempts=attempts,
            retries=max(0, attempts - 1),
            sleep_seconds=sleeps,
            retrieved_at=retrieved_at,
            endpoint=ENDPOINT_LOOKUP,
            kind=kind,
            input_length=len(cleaned),
            input_fingerprint=input_fingerprint,
            limitations=limitations
            + [
                f"lookup failed: {final_class}",
                "No FIXTURE/CPER substitution.",
            ],
            catalog_context=catalog_ctx,
            retryable=retryable,
        )

    return LookupTransportResult(
        ok=False,
        error_class=last_error_class or RETRY_EXHAUSTED,
        http_status=last_status,
        sanitized_response=last_safe,
        response_hash=sha256_canonical(last_safe) if last_safe else None,
        request_hash=request_hash,
        attempts=attempts,
        retries=max(0, attempts - 1),
        sleep_seconds=sleeps,
        retrieved_at=retrieved_at,
        endpoint=ENDPOINT_LOOKUP,
        kind=kind,
        input_length=len(cleaned),
        input_fingerprint=input_fingerprint,
        limitations=limitations + ["retry loop exited without success"],
        catalog_context=catalog_ctx,
    )


def transport_error_to_parcel_status(error_class: str | None) -> str:
    """Map transport failure to parcel-resolution terminal status (not FIXTURE)."""
    if error_class in {None, ""}:
        return "BLOCKED_EXTERNAL"
    if error_class in {
        NETWORK_NOT_AUTHORIZED,
        TOKEN_MISSING,
        BLOCKED_EXTERNAL,
        AUTH_FAILED,
        FORBIDDEN,
        SERVER_ERROR,
        RETRY_EXHAUSTED,
        TRANSPORT_ERROR,
        UPSTREAM_TIMEOUT,
        RATE_LIMITED,
    }:
        return "BLOCKED_EXTERNAL"
    if error_class in {INVALID_INPUT, APN_NOT_SUPPORTED}:
        return "NO_MATCH"
    if error_class in {MALFORMED_JSON, RESPONSE_CONTRACT_CHANGED}:
        return "BLOCKED_EXTERNAL"
    return "BLOCKED_EXTERNAL"
