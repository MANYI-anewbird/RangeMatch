"""Constrained LLM provider interface (FIXTURE | OPENAI).

Never logs or returns API keys. Never silently substitutes fixture output
when a live provider was requested.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

import certifi

ProviderName = Literal["FIXTURE", "OPENAI"]
ProviderStatus = Literal["OK", "FIXTURE", "NOT_CONFIGURED", "FAILED_EXTERNAL"]

REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_FIXTURE_ROOT = REPO_ROOT / "test-data" / "llm"

INTENT_PROMPT_VERSION = "RANGEMATCH_INTENT_PARSER@0.1.0"
BUYER_REPORT_PROMPT_VERSION = "RANGEMATCH_BUYER_REPORT@0.2.0"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class LLMCompletion:
    content: dict[str, Any] | None
    provider: str
    model_id: str | None
    prompt_version: str
    generated_at: str
    provider_status: ProviderStatus
    error_code: str | None = None
    error_message: str | None = None


class LLMProvider(Protocol):
    name: str

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        prompt_version: str,
        fixture_key: str | None = None,
    ) -> LLMCompletion: ...


def configured_provider_name() -> ProviderName:
    raw = (os.environ.get("RANGEMATCH_LLM_PROVIDER") or "FIXTURE").strip().upper()
    if raw in ("FIXTURE", "OPENAI"):
        return raw  # type: ignore[return-value]
    return "FIXTURE"


def configured_model_id() -> str | None:
    mid = (os.environ.get("RANGEMATCH_LLM_MODEL") or "").strip()
    return mid or None


def _api_key() -> str | None:
    for name in ("RANGEMATCH_LLM_API_KEY", "OPENAI_API_KEY"):
        val = (os.environ.get(name) or "").strip()
        if val:
            return val
    return None


def _temperature() -> float:
    raw = (os.environ.get("RANGEMATCH_LLM_TEMPERATURE") or "0").strip()
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _base_url() -> str:
    return (
        os.environ.get("RANGEMATCH_LLM_BASE_URL") or "https://api.openai.com/v1"
    ).rstrip("/")


def provider_health_summary() -> dict[str, Any]:
    name = configured_provider_name()
    key_present = bool(_api_key())
    status: ProviderStatus
    if name == "FIXTURE":
        status = "FIXTURE"
    elif not key_present:
        status = "NOT_CONFIGURED"
    else:
        status = "OK"
    return {
        "provider": name,
        "model_id": configured_model_id(),
        "provider_status": status,
        "credentials_configured": key_present,
        "intent_prompt_version": INTENT_PROMPT_VERSION,
        "buyer_report_prompt_version": BUYER_REPORT_PROMPT_VERSION,
    }


class FixtureLLMProvider:
    name = "FIXTURE"

    def complete_json(
        self,
        *,
        system: str,  # noqa: ARG002
        user: str,  # noqa: ARG002
        prompt_version: str,
        fixture_key: str | None = None,
    ) -> LLMCompletion:
        if not fixture_key:
            return LLMCompletion(
                content=None,
                provider=self.name,
                model_id="fixture",
                prompt_version=prompt_version,
                generated_at=utc_now_iso(),
                provider_status="FAILED_EXTERNAL",
                error_code="FIXTURE_KEY_REQUIRED",
                error_message="fixture_key required for FIXTURE provider",
            )
        path = LLM_FIXTURE_ROOT / f"{fixture_key}.json"
        if not path.is_file():
            return LLMCompletion(
                content=None,
                provider=self.name,
                model_id="fixture",
                prompt_version=prompt_version,
                generated_at=utc_now_iso(),
                provider_status="FAILED_EXTERNAL",
                error_code="FIXTURE_NOT_FOUND",
                error_message=f"missing fixture {fixture_key}",
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return LLMCompletion(
                content=None,
                provider=self.name,
                model_id="fixture",
                prompt_version=prompt_version,
                generated_at=utc_now_iso(),
                provider_status="FAILED_EXTERNAL",
                error_code="FIXTURE_INVALID",
                error_message="fixture root must be object",
            )
        return LLMCompletion(
            content=data,
            provider=self.name,
            model_id="fixture",
            prompt_version=prompt_version,
            generated_at=utc_now_iso(),
            provider_status="FIXTURE",
        )


class OpenAILLMProvider:
    name = "OPENAI"

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        prompt_version: str,
        fixture_key: str | None = None,  # noqa: ARG002
    ) -> LLMCompletion:
        key = _api_key()
        model = configured_model_id() or "gpt-4o-mini"
        generated_at = utc_now_iso()
        if not key:
            return LLMCompletion(
                content=None,
                provider=self.name,
                model_id=model,
                prompt_version=prompt_version,
                generated_at=generated_at,
                provider_status="NOT_CONFIGURED",
                error_code="LLM_CREDENTIALS_MISSING",
                error_message="live LLM provider requested but credentials are not configured",
            )
        payload = {
            "model": model,
            "temperature": _temperature(),
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{_base_url()}/chat/completions",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
        )
        try:
            tls_context = ssl.create_default_context(cafile=certifi.where())
            with urllib.request.urlopen(  # noqa: S310
                req,
                timeout=60,
                context=tls_context,
            ) as resp:
                raw = resp.read().decode("utf-8")
            parsed = json.loads(raw)
            content_text = (
                parsed.get("choices", [{}])[0].get("message", {}).get("content") or ""
            )
            content = json.loads(content_text)
            if not isinstance(content, dict):
                raise ValueError("LLM JSON root must be object")
            return LLMCompletion(
                content=content,
                provider=self.name,
                model_id=model,
                prompt_version=prompt_version,
                generated_at=generated_at,
                provider_status="OK",
            )
        except urllib.error.HTTPError as exc:
            # Do not include response body that might echo auth headers.
            return LLMCompletion(
                content=None,
                provider=self.name,
                model_id=model,
                prompt_version=prompt_version,
                generated_at=generated_at,
                provider_status="FAILED_EXTERNAL",
                error_code="LLM_HTTP_ERROR",
                error_message=f"http_{exc.code}",
            )
        except Exception as exc:  # noqa: BLE001
            return LLMCompletion(
                content=None,
                provider=self.name,
                model_id=model,
                prompt_version=prompt_version,
                generated_at=generated_at,
                provider_status="FAILED_EXTERNAL",
                error_code="LLM_PROVIDER_ERROR",
                error_message=type(exc).__name__,
            )


def get_provider(requested: str | None = None) -> LLMProvider:
    """Return provider. requested=None uses env. Live request never falls back to fixture."""
    name = (requested or configured_provider_name()).strip().upper()
    if name == "OPENAI":
        return OpenAILLMProvider()
    return FixtureLLMProvider()
