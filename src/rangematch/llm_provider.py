"""Constrained LLM provider interface (FIXTURE | OPENAI | DEEPSEEK).

Never logs or returns API keys. Never silently substitutes fixture output
when a live provider was requested.
"""

from __future__ import annotations

import json
import os
import random
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

import certifi

ProviderName = Literal["FIXTURE", "OPENAI", "DEEPSEEK"]
ProviderStatus = Literal["OK", "FIXTURE", "NOT_CONFIGURED", "FAILED_EXTERNAL"]
LIVE_LLM_PROVIDERS = frozenset({"OPENAI", "DEEPSEEK"})
DEEPSEEK_DEFAULT_BASE = "https://api.deepseek.com/v1"
DEEPSEEK_DEFAULT_MODEL = "deepseek-chat"

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
    request_id: str | None = None
    retry_count: int = 0


class LLMProvider(Protocol):
    name: str

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        prompt_version: str,
        fixture_key: str | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> LLMCompletion: ...


def is_live_llm_provider(name: str | None) -> bool:
    return (name or "").strip().upper() in LIVE_LLM_PROVIDERS


def configured_provider_name() -> ProviderName:
    raw = (os.environ.get("RANGEMATCH_LLM_PROVIDER") or "FIXTURE").strip().upper()
    if raw in ("FIXTURE", "OPENAI", "DEEPSEEK"):
        return raw  # type: ignore[return-value]
    return "FIXTURE"


def configured_model_id() -> str | None:
    mid = (os.environ.get("RANGEMATCH_LLM_MODEL") or "").strip()
    return mid or None


def _api_key() -> str | None:
    """OpenAI key resolution. Tests patch this symbol."""
    for name in ("RANGEMATCH_LLM_API_KEY", "OPENAI_API_KEY"):
        val = (os.environ.get(name) or "").strip()
        if val:
            return val
    return None


def _deepseek_api_key() -> str | None:
    for name in ("DEEPSEEK_API_KEY", "RANGEMATCH_LLM_API_KEY"):
        val = (os.environ.get(name) or "").strip()
        if val:
            return val
    return None


def _api_key_for(provider: str) -> str | None:
    if provider == "DEEPSEEK":
        return _deepseek_api_key()
    return _api_key()


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


def _base_url_for(provider: str) -> str:
    override = (os.environ.get("RANGEMATCH_LLM_BASE_URL") or "").strip().rstrip("/")
    if provider == "DEEPSEEK":
        if override and "deepseek" in override.lower():
            return override
        return DEEPSEEK_DEFAULT_BASE
    return override or "https://api.openai.com/v1"


def _default_model_for(provider: str) -> str:
    if provider == "DEEPSEEK":
        return DEEPSEEK_DEFAULT_MODEL
    return "gpt-4.1"


def _retry_delays() -> tuple[float, ...]:
    """Short bounded retry budget for a user-facing Demo request."""
    raw = (os.environ.get("RANGEMATCH_LLM_RETRY_DELAYS") or "0.5,1.5").strip()
    try:
        values = tuple(max(0.0, float(part)) for part in raw.split(",") if part.strip())
    except ValueError:
        return (0.5, 1.5)
    return values[:3]


def _openai_error_details(exc: urllib.error.HTTPError) -> tuple[str | None, str | None]:
    """Read only OpenAI's structured error type/code; never echo the full body."""
    try:
        payload = json.loads(exc.read(64_000).decode("utf-8", errors="replace"))
        error = payload.get("error") if isinstance(payload, dict) else None
        if not isinstance(error, dict):
            return None, None
        return (
            str(error.get("type") or "").strip() or None,
            str(error.get("code") or "").strip() or None,
        )
    except Exception:  # noqa: BLE001
        return None, None


def _retryable_429(error_type: str | None, error_code: str | None) -> bool:
    # Billing/quota exhaustion will not improve after sleeping.
    terminal = {"insufficient_quota", "billing_hard_limit_reached"}
    return not ({error_type, error_code} & terminal)


def provider_health_summary() -> dict[str, Any]:
    name = configured_provider_name()
    key_present = bool(_api_key_for(name)) if name != "FIXTURE" else False
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
        response_schema: dict[str, Any] | None = None,  # noqa: ARG002
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

    def __init__(self, name: str = "OPENAI") -> None:
        self.name = name

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        prompt_version: str,
        fixture_key: str | None = None,  # noqa: ARG002
        response_schema: dict[str, Any] | None = None,
    ) -> LLMCompletion:
        key = _api_key_for(self.name)
        model = configured_model_id() or _default_model_for(self.name)
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
        response_format: dict[str, Any]
        if response_schema is not None and self.name == "OPENAI":
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "rangematch_advisor_insights",
                    "strict": True,
                    "schema": response_schema,
                },
            }
        else:
            response_format = {"type": "json_object"}
        payload = {
            "model": model,
            "temperature": _temperature(),
            "response_format": response_format,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{_base_url_for(self.name)}/chat/completions",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
        )
        tls_context = ssl.create_default_context(cafile=certifi.where())
        delays = _retry_delays()
        retry_count = 0
        while True:
            try:
                with urllib.request.urlopen(  # noqa: S310
                    req,
                    timeout=60,
                    context=tls_context,
                ) as resp:
                    raw = resp.read().decode("utf-8")
                    headers = getattr(resp, "headers", None) or {}
                    request_id = headers.get("x-request-id") if hasattr(headers, "get") else None
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
                    request_id=request_id,
                    retry_count=retry_count,
                )
            except urllib.error.HTTPError as exc:
                error_type, error_code = _openai_error_details(exc)
                request_id = exc.headers.get("x-request-id") if exc.headers else None
                retryable = exc.code == 429 and _retryable_429(error_type, error_code)
                if retryable and retry_count < len(delays):
                    delay = delays[retry_count] * random.uniform(0.8, 1.2)
                    retry_count += 1
                    time.sleep(delay)
                    continue
                suffix = error_code or error_type
                return LLMCompletion(
                    content=None,
                    provider=self.name,
                    model_id=model,
                    prompt_version=prompt_version,
                    generated_at=generated_at,
                    provider_status="FAILED_EXTERNAL",
                    error_code="LLM_RATE_LIMITED" if exc.code == 429 else "LLM_HTTP_ERROR",
                    error_message=f"http_{exc.code}" + (f":{suffix}" if suffix else ""),
                    request_id=request_id,
                    retry_count=retry_count,
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
                    retry_count=retry_count,
                )


def get_provider(requested: str | None = None) -> LLMProvider:
    """Return provider. requested=None uses env. Live request never falls back to fixture."""
    name = (requested or configured_provider_name()).strip().upper()
    if name in LIVE_LLM_PROVIDERS:
        return OpenAILLMProvider(name)
    return FixtureLLMProvider()
