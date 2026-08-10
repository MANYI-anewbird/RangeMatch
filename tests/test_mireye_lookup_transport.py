"""Deterministic tests for controlled Mireye /v1/lookup HTTP transport."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from rangematch.api import _assert_no_secrets, app, reset_store_for_tests
from rangematch.mireye_adapter import assert_no_credentials, resolve_mireye_api_token
from rangematch.mireye_lookup_transport import (
    AUTH_FAILED,
    BLOCKED_EXTERNAL,
    FORBIDDEN,
    INVALID_INPUT,
    LookupHttpResponse,
    MALFORMED_JSON,
    NETWORK_NOT_AUTHORIZED,
    RATE_LIMITED,
    RESPONSE_CONTRACT_CHANGED,
    RETRY_EXHAUSTED,
    TOKEN_MISSING,
    UPSTREAM_TIMEOUT,
    classify_lookup_http_status,
    lookup_parcel_via_mireye,
    parse_retry_after_seconds,
    transport_error_to_parcel_status,
)
from rangematch.parcel_resolution import LiveParcelResolver, start_parcel_resolution


ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "test-data" / "mireye-parcel-lookup"


def _scenario_lookup(name: str) -> dict:
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))[
        "lookup_response"
    ]


def _json_response(status: int, payload: dict, *, headers: dict | None = None) -> LookupHttpResponse:
    return LookupHttpResponse(
        status=status,
        body=json.dumps(payload).encode("utf-8"),
        headers=dict(headers or {}),
    )


class FakeClock:
    def __init__(self) -> None:
        self.sleeps: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.sleeps.append(float(seconds))


class LookupTransportUnitTests(unittest.TestCase):
    def test_token_alias_prefers_token(self):
        old_t = os.environ.pop("MIREYE_API_TOKEN", None)
        old_k = os.environ.pop("MIREYE_API_KEY", None)
        try:
            os.environ["MIREYE_API_KEY"] = "legacy"
            self.assertEqual(resolve_mireye_api_token(), "legacy")
            os.environ["MIREYE_API_TOKEN"] = "canonical"
            self.assertEqual(resolve_mireye_api_token(), "canonical")
        finally:
            if old_t is None:
                os.environ.pop("MIREYE_API_TOKEN", None)
            else:
                os.environ["MIREYE_API_TOKEN"] = old_t
            if old_k is None:
                os.environ.pop("MIREYE_API_KEY", None)
            else:
                os.environ["MIREYE_API_KEY"] = old_k

    def test_network_not_authorized_without_allow(self):
        result = lookup_parcel_via_mireye("100 Main St, Denver, CO", allow_network=False)
        self.assertFalse(result.ok)
        self.assertEqual(result.error_class, NETWORK_NOT_AUTHORIZED)
        self.assertEqual(result.attempts, 0)

    def test_missing_token(self):
        old_t = os.environ.pop("MIREYE_API_TOKEN", None)
        old_k = os.environ.pop("MIREYE_API_KEY", None)
        try:
            result = lookup_parcel_via_mireye(
                "100 Main St, Denver, CO",
                allow_network=True,
                http_post=lambda **kwargs: (_ for _ in ()).throw(AssertionError("no call")),
            )
            self.assertEqual(result.error_class, TOKEN_MISSING)
        finally:
            if old_t is not None:
                os.environ["MIREYE_API_TOKEN"] = old_t
            if old_k is not None:
                os.environ["MIREYE_API_KEY"] = old_k

    def test_apn_rejected(self):
        result = lookup_parcel_via_mireye("APN: R1234567", allow_network=False)
        self.assertEqual(result.error_class, "APN_NOT_SUPPORTED_IN_V1")

    def test_resolved_parcel_maps_through_resolver(self):
        payload = _scenario_lookup("resolved_with_parcel")
        clock = FakeClock()
        calls = {"n": 0}

        def http_post(**kwargs):
            calls["n"] += 1
            auth = kwargs["headers"].get("Authorization", "")
            self.assertTrue(auth.startswith("Bearer "))
            self.assertEqual(auth, "Bearer test-token-xyz")
            return _json_response(200, payload)

        with mock.patch.dict(os.environ, {"MIREYE_API_TOKEN": "test-token-xyz"}, clear=False):
            with mock.patch(
                "rangematch.mireye_lookup_transport._env_base_url",
                return_value="https://api.mireye.com",
            ):
                record = start_parcel_resolution(
                    "300 Mireye Ranch Rd, Weld County, CO 80701",
                    mode="LIVE",
                    allow_network=True,
                    http_post=http_post,
                    sleeper=clock,
                )
        self.assertEqual(record["status"], "NEEDS_BOUNDARY_CONFIRMATION")
        self.assertEqual(calls["n"], 1)
        self.assertEqual(clock.sleeps, [])
        blob = json.dumps(record)
        self.assertNotIn("test-token-xyz", blob)
        self.assertNotIn("MUST_BE_REDACTED", blob)
        self.assertNotIn("engineering_test_geometry_cper", blob)
        assert_no_credentials(blob, label="resolved_record")
        self.assertEqual(
            record["candidates"][0]["provenance"]["source"], "REGRID via Mireye"
        )
        self.assertIn("mireye_lookup", record["provenance"])
        self.assertFalse(
            record["provenance"]["mireye_lookup"]["catalog_context"].get(
                "affects_parcel_resolution"
            )
        )

    def test_clarify_selection(self):
        payload = _scenario_lookup("clarify_with_parcels")

        def http_post(**kwargs):
            return _json_response(200, payload)

        with mock.patch.dict(os.environ, {"MIREYE_API_TOKEN": "tok"}, clear=False):
            with mock.patch(
                "rangematch.mireye_lookup_transport._env_base_url",
                return_value="https://api.mireye.com",
            ):
                record = start_parcel_resolution(
                    "302 Split Mireye Rd, Weld County, CO 80701",
                    mode="LIVE",
                    allow_network=True,
                    http_post=http_post,
                    sleeper=FakeClock(),
                )
        self.assertEqual(record["status"], "NEEDS_USER_SELECTION")

    def test_no_match(self):
        payload = _scenario_lookup("no_match")

        def http_post(**kwargs):
            return _json_response(200, payload)

        with mock.patch.dict(os.environ, {"MIREYE_API_TOKEN": "tok"}, clear=False):
            with mock.patch(
                "rangematch.mireye_lookup_transport._env_base_url",
                return_value="https://api.mireye.com",
            ):
                record = start_parcel_resolution(
                    "304 Unknown Mireye Rd, Nowhere, CO 80000",
                    mode="LIVE",
                    allow_network=True,
                    http_post=http_post,
                    sleeper=FakeClock(),
                )
        self.assertEqual(record["status"], "NO_MATCH")

    def test_parcel_unavailable(self):
        payload = _scenario_lookup("resolved_parcel_unavailable")

        def http_post(**kwargs):
            return _json_response(200, payload)

        with mock.patch.dict(os.environ, {"MIREYE_API_TOKEN": "tok"}, clear=False):
            with mock.patch(
                "rangematch.mireye_lookup_transport._env_base_url",
                return_value="https://api.mireye.com",
            ):
                record = start_parcel_resolution(
                    "301 Mireye Ranch Rd, Weld County, CO 80701",
                    mode="LIVE",
                    allow_network=True,
                    http_post=http_post,
                    sleeper=FakeClock(),
                )
        self.assertEqual(record["status"], "PARCEL_DATA_UNAVAILABLE")

    def test_insufficient_quality(self):
        payload = _scenario_lookup("geocode_range_interpolation")

        def http_post(**kwargs):
            return _json_response(200, payload)

        with mock.patch.dict(os.environ, {"MIREYE_API_TOKEN": "tok"}, clear=False):
            with mock.patch(
                "rangematch.mireye_lookup_transport._env_base_url",
                return_value="https://api.mireye.com",
            ):
                record = start_parcel_resolution(
                    "305 Rural Mile Marker Rd, Weld County, CO 80701",
                    mode="LIVE",
                    allow_network=True,
                    http_post=http_post,
                    sleeper=FakeClock(),
                )
        self.assertEqual(record["status"], "GEOCODE_QUALITY_INSUFFICIENT")

    def test_http_401(self):
        clock = FakeClock()

        def http_post(**kwargs):
            return _json_response(401, {"error": "auth_invalid"})

        with mock.patch.dict(os.environ, {"MIREYE_API_TOKEN": "tok"}, clear=False):
            with mock.patch(
                "rangematch.mireye_lookup_transport._env_base_url",
                return_value="https://api.mireye.com",
            ):
                result = lookup_parcel_via_mireye(
                    "100 Main St, Denver, CO",
                    allow_network=True,
                    http_post=http_post,
                    sleeper=clock,
                )
        self.assertEqual(result.error_class, AUTH_FAILED)
        self.assertEqual(result.attempts, 1)
        self.assertEqual(clock.sleeps, [])

    def test_http_403(self):
        def http_post(**kwargs):
            return _json_response(403, {"error": "forbidden"})

        with mock.patch.dict(os.environ, {"MIREYE_API_TOKEN": "tok"}, clear=False):
            with mock.patch(
                "rangematch.mireye_lookup_transport._env_base_url",
                return_value="https://api.mireye.com",
            ):
                result = lookup_parcel_via_mireye(
                    "100 Main St, Denver, CO",
                    allow_network=True,
                    http_post=http_post,
                    sleeper=FakeClock(),
                )
        self.assertEqual(result.error_class, FORBIDDEN)

    def test_http_422_no_retry(self):
        clock = FakeClock()
        calls = {"n": 0}

        def http_post(**kwargs):
            calls["n"] += 1
            return _json_response(422, {"error": "invalid"})

        with mock.patch.dict(os.environ, {"MIREYE_API_TOKEN": "tok"}, clear=False):
            with mock.patch(
                "rangematch.mireye_lookup_transport._env_base_url",
                return_value="https://api.mireye.com",
            ):
                result = lookup_parcel_via_mireye(
                    "100 Main St, Denver, CO",
                    allow_network=True,
                    http_post=http_post,
                    sleeper=clock,
                )
        self.assertEqual(result.error_class, INVALID_INPUT)
        self.assertEqual(calls["n"], 1)
        self.assertEqual(clock.sleeps, [])

    def test_429_retry_after(self):
        clock = FakeClock()
        calls = {"n": 0}
        payload = _scenario_lookup("resolved_with_parcel")

        def http_post(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return _json_response(
                    429,
                    {"error": "resolve_busy", "retryable": True},
                    headers={"Retry-After": "3"},
                )
            return _json_response(200, payload)

        with mock.patch.dict(os.environ, {"MIREYE_API_TOKEN": "tok"}, clear=False):
            with mock.patch(
                "rangematch.mireye_lookup_transport._env_base_url",
                return_value="https://api.mireye.com",
            ):
                result = lookup_parcel_via_mireye(
                    "300 Mireye Ranch Rd, Weld County, CO 80701",
                    allow_network=True,
                    http_post=http_post,
                    sleeper=clock,
                    max_sleep_seconds=5.0,
                )
        self.assertTrue(result.ok)
        self.assertEqual(calls["n"], 2)
        self.assertEqual(clock.sleeps, [3.0])

    def test_504_retry_then_success(self):
        clock = FakeClock()
        calls = {"n": 0}
        payload = _scenario_lookup("no_match")

        def http_post(**kwargs):
            calls["n"] += 1
            if calls["n"] <= 2:
                return _json_response(
                    504,
                    {"error": "resolve_timeout", "retryable": True},
                    headers={"Retry-After": "2"},
                )
            return _json_response(200, payload)

        with mock.patch.dict(os.environ, {"MIREYE_API_TOKEN": "tok"}, clear=False):
            with mock.patch(
                "rangematch.mireye_lookup_transport._env_base_url",
                return_value="https://api.mireye.com",
            ):
                result = lookup_parcel_via_mireye(
                    "304 Unknown Mireye Rd, Nowhere, CO 80000",
                    allow_network=True,
                    http_post=http_post,
                    sleeper=clock,
                    max_sleep_seconds=5.0,
                )
        self.assertTrue(result.ok)
        self.assertEqual(calls["n"], 3)
        self.assertEqual(clock.sleeps, [2.0, 2.0])

    def test_retry_exhausted(self):
        clock = FakeClock()
        calls = {"n": 0}

        def http_post(**kwargs):
            calls["n"] += 1
            return _json_response(
                429,
                {"error": "resolve_busy", "retryable": True},
                headers={"Retry-After": "1"},
            )

        with mock.patch.dict(os.environ, {"MIREYE_API_TOKEN": "tok"}, clear=False):
            with mock.patch(
                "rangematch.mireye_lookup_transport._env_base_url",
                return_value="https://api.mireye.com",
            ):
                result = lookup_parcel_via_mireye(
                    "100 Main St, Denver, CO",
                    allow_network=True,
                    http_post=http_post,
                    sleeper=clock,
                    max_retries=2,
                    max_sleep_seconds=5.0,
                )
        self.assertEqual(result.error_class, RETRY_EXHAUSTED)
        self.assertEqual(calls["n"], 3)
        self.assertEqual(len(clock.sleeps), 2)

    def test_malformed_json(self):
        def http_post(**kwargs):
            return LookupHttpResponse(status=200, body=b"not-json{", headers={})

        with mock.patch.dict(os.environ, {"MIREYE_API_TOKEN": "tok"}, clear=False):
            with mock.patch(
                "rangematch.mireye_lookup_transport._env_base_url",
                return_value="https://api.mireye.com",
            ):
                result = lookup_parcel_via_mireye(
                    "100 Main St, Denver, CO",
                    allow_network=True,
                    http_post=http_post,
                    sleeper=FakeClock(),
                )
        self.assertEqual(result.error_class, MALFORMED_JSON)

    def test_response_contract_changed(self):
        def http_post(**kwargs):
            return _json_response(200, {"fields": {}, "ok": True})  # no disposition

        with mock.patch.dict(os.environ, {"MIREYE_API_TOKEN": "tok"}, clear=False):
            with mock.patch(
                "rangematch.mireye_lookup_transport._env_base_url",
                return_value="https://api.mireye.com",
            ):
                result = lookup_parcel_via_mireye(
                    "100 Main St, Denver, CO",
                    allow_network=True,
                    http_post=http_post,
                    sleeper=FakeClock(),
                )
        self.assertEqual(result.error_class, RESPONSE_CONTRACT_CHANGED)

    def test_tls_middlebox_blocked_external(self):
        def http_post(**kwargs):
            raise OSError("WRONG_VERSION_NUMBER")

        with mock.patch.dict(os.environ, {"MIREYE_API_TOKEN": "tok"}, clear=False):
            with mock.patch(
                "rangematch.mireye_lookup_transport._env_base_url",
                return_value="https://api.mireye.com",
            ):
                with mock.patch(
                    "rangematch.mireye_lookup_transport.probe_plaintext_http_on_443",
                    return_value={
                        "looks_like_http": True,
                        "safebrowse_redirect": True,
                        "status_line": "HTTP/1.1 302",
                    },
                ):
                    result = lookup_parcel_via_mireye(
                        "100 Main St, Denver, CO",
                        allow_network=True,
                        http_post=http_post,
                        sleeper=FakeClock(),
                    )
                    record = start_parcel_resolution(
                        "100 Main St, Denver, CO",
                        mode="LIVE",
                        allow_network=True,
                        http_post=http_post,
                        sleeper=FakeClock(),
                    )
        self.assertEqual(result.error_class, BLOCKED_EXTERNAL)
        self.assertEqual(
            transport_error_to_parcel_status(result.error_class), "BLOCKED_EXTERNAL"
        )
        self.assertEqual(record["status"], "BLOCKED_EXTERNAL")
        self.assertNotIn("cand_demo", json.dumps(record))

    def test_no_fixture_fallback_on_live_failure(self):
        def http_post(**kwargs):
            return _json_response(500, {"error": "boom", "retryable": False})

        with mock.patch.dict(os.environ, {"MIREYE_API_TOKEN": "tok"}, clear=False):
            with mock.patch(
                "rangematch.mireye_lookup_transport._env_base_url",
                return_value="https://api.mireye.com",
            ):
                record = start_parcel_resolution(
                    "100 Demo Ranch Rd, Weld County, CO 80701",
                    mode="LIVE",
                    allow_network=True,
                    http_post=http_post,
                    sleeper=FakeClock(),
                )
        self.assertEqual(record["status"], "BLOCKED_EXTERNAL")
        self.assertEqual(record["candidates"], [])
        self.assertNotIn("cand_demo_001", json.dumps(record))

    def test_credential_redaction_in_result(self):
        payload = _scenario_lookup("resolved_with_parcel")

        def http_post(**kwargs):
            return _json_response(200, payload)

        with mock.patch.dict(
            os.environ, {"MIREYE_API_TOKEN": "super-secret-token-value"}, clear=False
        ):
            with mock.patch(
                "rangematch.mireye_lookup_transport._env_base_url",
                return_value="https://api.mireye.com",
            ):
                result = lookup_parcel_via_mireye(
                    "300 Mireye Ranch Rd, Weld County, CO 80701",
                    allow_network=True,
                    http_post=http_post,
                    sleeper=FakeClock(),
                )
        blob = json.dumps(result.to_public_dict())
        self.assertNotIn("super-secret-token-value", blob)
        self.assertNotIn("Bearer ", blob)
        assert_no_credentials(blob, label="transport_public")

    def test_parse_retry_after_capped(self):
        self.assertEqual(parse_retry_after_seconds("100", max_sleep_seconds=5.0), 5.0)
        self.assertEqual(parse_retry_after_seconds("2", max_sleep_seconds=5.0), 2.0)

    def test_classify_status(self):
        self.assertEqual(classify_lookup_http_status(401)[0], AUTH_FAILED)
        self.assertEqual(classify_lookup_http_status(429)[0], RATE_LIMITED)
        self.assertTrue(classify_lookup_http_status(504)[1])
        self.assertFalse(classify_lookup_http_status(422)[1])


class LookupLiveGateAPITests(unittest.TestCase):
    def setUp(self) -> None:
        reset_store_for_tests()
        self.client = TestClient(app)

    def test_live_gate_without_allow_network(self):
        r = self.client.post(
            "/v1/mireye/lookup-live-gate",
            json={"address": "100 Main St, Denver, CO 80202", "allow_network": False},
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertFalse(body["live_success_claimed"])
        self.assertFalse(body["allow_network"])
        self.assertEqual(
            body["parcel_resolution"]["status"], "BLOCKED_EXTERNAL"
        )
        assert_no_credentials(body, label="live_gate")

    def test_parcel_create_live_requires_allow_network(self):
        r = self.client.post(
            "/v1/parcel-resolutions",
            json={
                "address": "100 Main St, Denver, CO 80202",
                "resolver_mode": "LIVE",
                "allow_network": False,
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "BLOCKED_EXTERNAL")

    def test_health_still_no_network_lookup(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        # Health must not invent live lookup success
        self.assertIn(
            r.json()["live_mireye_availability"],
            {"CONFIGURED_LIVE_GATE_REQUIRED", "NOT_CONFIGURED"},
        )

    def test_secret_scan_allows_safe_authorization_policy_prose(self):
        _assert_no_secrets(
            {"limitations": ["Authorization is never stored."]},
            where="safe_policy_prose",
        )


if __name__ == "__main__":
    unittest.main()
