"""Mireye HTTPS transport helpers (TLS / proxy / URL validation only).

Does not change normalization semantics. Never logs or returns API keys.
"""

from __future__ import annotations

import os
import re
import socket
import ssl
import urllib.error
import urllib.request
from contextlib import contextmanager
from typing import Any, Iterator, Mapping
from urllib.parse import urlparse

OFFICIAL_MIREYE_HTTPS_ORIGIN = "https://api.mireye.com"
OFFICIAL_HOST = "api.mireye.com"
OFFICIAL_PORT = 443

# Process-local bypass of HTTP(S)_PROXY for Mireye only. Cursor/sandbox often
# injects a local HTTP proxy that breaks HTTPS CONNECT; transparent SafeBrowse
# interception is a separate external class and is not solved by this flag.
DEFAULT_BYPASS_ENV_PROXY = True

_PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)
_NO_PROXY_KEYS = ("NO_PROXY", "no_proxy")


class MireyeTransportError(RuntimeError):
    """Sanitized transport failure with a stable error_class."""

    def __init__(self, error_class: str, message: str, *, details: Mapping[str, Any] | None = None):
        self.error_class = error_class
        self.details = dict(details or {})
        super().__init__(f"{error_class}:{message}")


def sanitize_proxy_url(url: str | None) -> dict[str, Any] | None:
    """Report proxy as scheme/host/port only — never userinfo or full URL."""
    if not url:
        return None
    parsed = urlparse(url)
    return {
        "present": True,
        "scheme": parsed.scheme or None,
        "host": parsed.hostname,
        "port": parsed.port,
        "has_userinfo": bool(parsed.username or parsed.password),
        "path": parsed.path or "",
    }


def report_proxy_environment() -> dict[str, Any]:
    proxies: dict[str, Any] = {}
    for name in _PROXY_ENV_KEYS:
        raw = os.environ.get(name)
        if raw:
            proxies[name] = sanitize_proxy_url(raw)
    no_proxy = os.environ.get("NO_PROXY") or os.environ.get("no_proxy")
    return {"proxies": proxies, "NO_PROXY": no_proxy}


def validate_mireye_base_url(base_url: str | None) -> dict[str, Any]:
    """Validate configured base URL against the official HTTPS origin."""
    raw = (base_url or "").strip()
    normalized = raw.rstrip("/")
    parsed = urlparse(normalized)
    duplicate_scheme = bool(re.search(r"https?://https?://", raw, re.I))
    exact = normalized == OFFICIAL_MIREYE_HTTPS_ORIGIN
    ok = (
        exact
        and parsed.scheme == "https"
        and parsed.hostname == OFFICIAL_HOST
        and parsed.port is None
        and (parsed.path in ("", "/"))
        and not parsed.query
        and not parsed.fragment
        and not parsed.username
        and not parsed.password
        and not duplicate_scheme
    )
    return {
        "ok": ok,
        "exact_official_origin": exact,
        "scheme": parsed.scheme or None,
        "hostname": parsed.hostname,
        "port": parsed.port,
        "path": parsed.path or "",
        "query_present": bool(parsed.query),
        "fragment_present": bool(parsed.fragment),
        "has_userinfo": bool(parsed.username or parsed.password),
        "endswith_slash": raw.endswith("/"),
        "duplicate_scheme": duplicate_scheme,
        "expected": OFFICIAL_MIREYE_HTTPS_ORIGIN,
    }


def build_ssl_context() -> ssl.SSLContext:
    """Verified TLS context; prefer certifi CAs when available (no verify=False)."""
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


@contextmanager
def scoped_env_proxy_bypass() -> Iterator[None]:
    """Temporarily clear proxy env vars for this process only; restore on exit.

    Does not permanently modify the user shell environment. Required because
    urllib ignores ProxyHandler({}) and ProxyHandler({scheme: None}) is unsafe.
    """
    saved_proxy = {k: os.environ.pop(k) for k in _PROXY_ENV_KEYS if k in os.environ}
    saved_no_proxy = {k: os.environ.pop(k) for k in _NO_PROXY_KEYS if k in os.environ}
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
    try:
        yield
    finally:
        for k in _NO_PROXY_KEYS:
            os.environ.pop(k, None)
        os.environ.update(saved_no_proxy)
        os.environ.update(saved_proxy)


def build_mireye_opener() -> urllib.request.OpenerDirector:
    """HTTPS opener with verified SSL context."""
    return urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=build_ssl_context())
    )


def probe_plaintext_http_on_443(host: str = OFFICIAL_HOST, timeout: float = 8.0) -> dict[str, Any]:
    """Detect middleboxes that speak plain HTTP on :443 (causes WRONG_VERSION_NUMBER)."""
    result: dict[str, Any] = {
        "host": host,
        "port": OFFICIAL_PORT,
        "ok": False,
        "looks_like_http": False,
        "safebrowse_redirect": False,
        "status_line": None,
    }
    try:
        with socket.create_connection((host, OFFICIAL_PORT), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(
                f"GET /healthz HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode()
            )
            data = sock.recv(512)
    except Exception as exc:  # noqa: BLE001
        result["error_class"] = type(exc).__name__
        result["message"] = str(exc)[:160]
        return result

    ascii_prefix = "".join(chr(b) if 32 <= b < 127 else "." for b in data[:160])
    if "safebrowse" in ascii_prefix.lower() or data.startswith(b"HTTP/"):
        # Persist only a sanitized summary — never middlebox query tokens/URLs.
        status = (
            data.split(b"\r\n", 1)[0].decode("ascii", "replace")
            if data.startswith(b"HTTP/")
            else "UNKNOWN"
        )
        ascii_prefix = (
            f"{status} | location_host=safebrowse.io | query=[REDACTED]"
            if b"safebrowse" in data.lower()
            else status
        )
    result["ok"] = True
    result["looks_like_http"] = data.startswith(b"HTTP/")
    result["first_bytes_ascii"] = ascii_prefix
    if data.startswith(b"HTTP/"):
        result["status_line"] = data.split(b"\r\n", 1)[0].decode("ascii", "replace")
    lowered = data.lower()
    result["safebrowse_redirect"] = b"safebrowse" in lowered
    return result


def classify_tls_failure(
    exc: BaseException, *, plaintext_probe: Mapping[str, Any] | None = None
) -> str:
    msg = str(exc)
    probe = dict(plaintext_probe or {})
    if probe.get("looks_like_http") and (
        probe.get("safebrowse_redirect") or "302" in str(probe.get("status_line") or "")
    ):
        return "BLOCKED_EXTERNAL_NETWORK_MIDDLEBOX_PLAINTEXT_HTTP_ON_443"
    if "WRONG_VERSION_NUMBER" in msg or "wrong version number" in msg.lower():
        if probe.get("looks_like_http"):
            return "BLOCKED_EXTERNAL_NETWORK_MIDDLEBOX_PLAINTEXT_HTTP_ON_443"
        return "SSL_WRONG_VERSION_NUMBER"
    if "Tunnel connection failed" in msg:
        return "PROXY_TUNNEL_FAILED"
    if isinstance(exc, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in msg:
        return "SSL_CERTIFICATE_VERIFY_FAILED"
    if "timed out" in msg.lower():
        return "TIMEOUT"
    return f"TRANSPORT_{type(exc).__name__}"


def redact_transport_message(message: str, api_key: str | None = None) -> str:
    text = str(message)
    if api_key:
        text = text.replace(api_key, "[REDACTED]")
    text = re.sub(r"(?i)bearer\s+[a-z0-9._\-]+", "Bearer [REDACTED]", text)
    text = re.sub(r"://[^/\s]+:[^/@\s]+@", "://[REDACTED]@", text)
    return text[:300]


def diagnose_mireye_transport(*, base_url: str | None = None) -> dict[str, Any]:
    """Sanitized transport diagnosis for docs/fixtures (no Authorization)."""
    base = (
        base_url or os.environ.get("MIREYE_API_BASE_URL") or OFFICIAL_MIREYE_HTTPS_ORIGIN
    ).rstrip("/")
    key_present = bool(
        (os.environ.get("MIREYE_API_TOKEN") or "").strip()
        or (os.environ.get("MIREYE_API_KEY") or "").strip()
    )
    report: dict[str, Any] = {
        "target_host": OFFICIAL_HOST,
        "base_url_validation": validate_mireye_base_url(base),
        "key_present": key_present,
        "proxy_environment": report_proxy_environment(),
        "ssl": {
            "openssl_version": ssl.OPENSSL_VERSION,
            "certifi_used": False,
        },
        "dns": {},
        "plaintext_http_probe": {},
        "tls_direct": {},
        "https_health_no_auth": {},
        "classification": None,
    }
    try:
        import certifi  # noqa: F401

        report["ssl"]["certifi_used"] = True
    except Exception:
        report["ssl"]["certifi_used"] = False

    try:
        infos = socket.getaddrinfo(OFFICIAL_HOST, OFFICIAL_PORT, type=socket.SOCK_STREAM)
        report["dns"] = {
            "ok": True,
            "records": [
                {
                    "family": "IPv6" if item[0] == socket.AF_INET6 else "IPv4",
                    "addr": item[4][0],
                }
                for item in infos
            ],
        }
    except Exception as exc:  # noqa: BLE001
        report["dns"] = {"ok": False, "error_class": type(exc).__name__}

    report["plaintext_http_probe"] = probe_plaintext_http_on_443()

    try:
        ctx = build_ssl_context()
        with socket.create_connection((OFFICIAL_HOST, OFFICIAL_PORT), timeout=12) as sock:
            with ctx.wrap_socket(sock, server_hostname=OFFICIAL_HOST) as ss:
                report["tls_direct"] = {"ok": True, "version": ss.version()}
    except Exception as exc:  # noqa: BLE001
        report["tls_direct"] = {
            "ok": False,
            "error_class": classify_tls_failure(
                exc, plaintext_probe=report["plaintext_http_probe"]
            ),
            "message": redact_transport_message(str(exc)),
        }

    try:
        with scoped_env_proxy_bypass():
            opener = build_mireye_opener()
            req = urllib.request.Request(
                f"{OFFICIAL_MIREYE_HTTPS_ORIGIN}/healthz",
                method="GET",
                headers={"Accept": "application/json"},
            )
            with opener.open(req, timeout=20) as resp:
                report["https_health_no_auth"] = {
                    "ok": True,
                    "http_status": getattr(resp, "status", None) or resp.getcode(),
                    "bypass_env_proxy": True,
                }
    except urllib.error.HTTPError as exc:
        report["https_health_no_auth"] = {
            "ok": True,
            "http_status": exc.code,
            "note": "tls_ok_http_error",
            "bypass_env_proxy": True,
        }
    except Exception as exc:  # noqa: BLE001
        report["https_health_no_auth"] = {
            "ok": False,
            "error_class": classify_tls_failure(
                exc, plaintext_probe=report["plaintext_http_probe"]
            ),
            "message": redact_transport_message(str(exc)),
            "bypass_env_proxy": True,
        }

    if report["https_health_no_auth"].get("ok"):
        report["classification"] = "TRANSPORT_OK"
    elif report["plaintext_http_probe"].get("safebrowse_redirect") or (
        report["plaintext_http_probe"].get("looks_like_http")
        and not report["tls_direct"].get("ok")
    ):
        report["classification"] = "BLOCKED_EXTERNAL_NETWORK_MIDDLEBOX_PLAINTEXT_HTTP_ON_443"
    elif not report["dns"].get("ok"):
        report["classification"] = "DNS_FAILURE"
    else:
        report["classification"] = report["tls_direct"].get("error_class") or report[
            "https_health_no_auth"
        ].get("error_class")

    return report


def mireye_urlopen(
    request: urllib.request.Request,
    *,
    timeout: float,
    bypass_env_proxy: bool = DEFAULT_BYPASS_ENV_PROXY,
):
    """Open a Mireye HTTPS request with verified TLS and scoped proxy policy."""
    opener = build_mireye_opener()
    if bypass_env_proxy:
        with scoped_env_proxy_bypass():
            return opener.open(request, timeout=timeout)
    return opener.open(request, timeout=timeout)
