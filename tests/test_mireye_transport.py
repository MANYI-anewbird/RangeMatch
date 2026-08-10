"""Regression tests for Mireye HTTPS transport configuration."""

from __future__ import annotations

import os
import ssl
import unittest
import urllib.request
from unittest import mock

from rangematch.mireye_transport import (
    OFFICIAL_MIREYE_HTTPS_ORIGIN,
    build_mireye_opener,
    build_ssl_context,
    classify_tls_failure,
    redact_transport_message,
    report_proxy_environment,
    sanitize_proxy_url,
    scoped_env_proxy_bypass,
    validate_mireye_base_url,
)


class MireyeTransportConfigTests(unittest.TestCase):
    def test_official_base_url_validates(self):
        result = validate_mireye_base_url(OFFICIAL_MIREYE_HTTPS_ORIGIN)
        self.assertTrue(result["ok"])
        self.assertTrue(result["exact_official_origin"])

    def test_trailing_slash_accepted(self):
        result = validate_mireye_base_url(OFFICIAL_MIREYE_HTTPS_ORIGIN + "/")
        self.assertTrue(result["ok"])
        self.assertTrue(result["endswith_slash"])

    def test_rejects_http_scheme(self):
        self.assertFalse(validate_mireye_base_url("http://api.mireye.com")["ok"])

    def test_rejects_wrong_host(self):
        self.assertFalse(validate_mireye_base_url("https://example.com")["ok"])

    def test_rejects_duplicate_scheme(self):
        self.assertFalse(
            validate_mireye_base_url("https://https://api.mireye.com")["ok"]
        )

    def test_rejects_explicit_wrong_port(self):
        self.assertFalse(validate_mireye_base_url("https://api.mireye.com:8443")["ok"])

    def test_sanitize_proxy_strips_userinfo(self):
        report = sanitize_proxy_url("http://alice:hunter2@127.0.0.1:8080")
        assert report is not None
        self.assertEqual(report["scheme"], "http")
        self.assertEqual(report["host"], "127.0.0.1")
        self.assertEqual(report["port"], 8080)
        self.assertTrue(report["has_userinfo"])
        blob = str(report)
        self.assertNotIn("hunter2", blob)
        self.assertNotIn("alice", blob)

    def test_report_proxy_environment_no_secrets(self):
        with mock.patch.dict(
            os.environ,
            {
                "HTTPS_PROXY": "http://alice:hunter2@127.0.0.1:9999",
                "NO_PROXY": "localhost",
            },
            clear=False,
        ):
            report = report_proxy_environment()
        text = str(report)
        self.assertNotIn("hunter2", text)
        self.assertNotIn("alice", text)
        self.assertEqual(report["proxies"]["HTTPS_PROXY"]["host"], "127.0.0.1")

    def test_bypass_env_proxy_opener_ignores_https_proxy(self):
        with mock.patch.dict(
            os.environ,
            {"HTTPS_PROXY": "http://127.0.0.1:9", "HTTP_PROXY": "http://127.0.0.1:9"},
            clear=False,
        ):
            before = os.environ.get("HTTPS_PROXY")
            self.assertTrue(before)
            with scoped_env_proxy_bypass():
                self.assertNotIn("HTTPS_PROXY", os.environ)
                self.assertEqual(os.environ.get("NO_PROXY"), "*")
                opener = build_mireye_opener()
                self.assertTrue(any(isinstance(h, urllib.request.HTTPSHandler) for h in opener.handlers))
            # Restored after scope
            self.assertEqual(os.environ.get("HTTPS_PROXY"), before)

    def test_ssl_context_is_verified(self):
        ctx = build_ssl_context()
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(ctx.check_hostname)

    def test_classify_safebrowse_plaintext_probe(self):
        exc = ssl.SSLError("WRONG_VERSION_NUMBER")
        probe = {
            "looks_like_http": True,
            "safebrowse_redirect": True,
            "status_line": "HTTP/1.1 302 Found",
        }
        self.assertEqual(
            classify_tls_failure(exc, plaintext_probe=probe),
            "BLOCKED_EXTERNAL_NETWORK_MIDDLEBOX_PLAINTEXT_HTTP_ON_443",
        )

    def test_redact_transport_message_strips_bearer_and_key(self):
        msg = redact_transport_message(
            "Bearer abcdefghijklmnop failed for sk-not-used",
            api_key="super-secret-key-value",
        )
        self.assertNotIn("abcdefghijklmnop", msg)
        self.assertNotIn("super-secret-key-value", msg)
        self.assertIn("[REDACTED]", msg)


if __name__ == "__main__":
    unittest.main()
