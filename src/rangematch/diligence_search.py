"""Bounded public-source search for non-canonical diligence context."""

from __future__ import annotations

import hashlib
import json
import os
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import certifi

SCHEMA_VERSION = "RANGEMATCH_DILIGENCE_SEARCH@0.1.0"
SEARCH_VERSION = "RANGEMATCH_DILIGENCE_SEARCH_AGENT@0.1.0"
TOPICS = {
    "REGULATION_AND_PERMITS",
    "LOCAL_AG_GUIDANCE",
    "CURRENT_DROUGHT",
    "PUBLIC_LAND_CONSTRAINTS",
}
ALLOWED_DOMAINS = [
    "usda.gov",
    "nrcs.usda.gov",
    "drought.gov",
    "droughtmonitor.unl.edu",
    "fema.gov",
    "fws.gov",
    "blm.gov",
]
REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "test-data" / "llm" / "diligence_search_fixture.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key() -> str | None:
    return (os.environ.get("RANGEMATCH_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip() or None


def _model() -> str:
    return (os.environ.get("RANGEMATCH_SEARCH_MODEL") or "gpt-5.6-terra").strip()


def _source_class(domain: str) -> str | None:
    if domain == "droughtmonitor.unl.edu" or domain.endswith(".edu"):
        return "UNIVERSITY_EXTENSION"
    if domain.endswith(".gov") or domain == "usda.gov":
        return "GOVERNMENT"
    return None


def _normalize_sources(raw_sources: list[dict[str, Any]], *, searched_at: str, jurisdiction: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_sources:
        url = str(item.get("url") or "").strip()
        parsed = urlparse(url)
        domain = (parsed.hostname or "").lower()
        source_class = _source_class(domain)
        clean_query = urlencode(
            [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"source", "campaign", "ref"}]
        )
        url = urlunparse(("https", domain, parsed.path.rstrip("/") or "/", "", clean_query, ""))
        if parsed.scheme != "https" or not source_class or url in seen:
            continue
        seen.add(url)
        out.append({
            "source_id": "DSRC_" + hashlib.sha256(url.encode()).hexdigest()[:12],
            "title": str(item.get("title") or domain).strip()[:300],
            "url": url,
            "domain": domain,
            "retrieved_at": searched_at,
            "published_at": item.get("published_at"),
            "source_class": source_class,
            "jurisdiction_scope": jurisdiction or "United States / applicability review required",
            "use_limit": "DILIGENCE_CONTEXT_ONLY",
        })
    return out[:12]


def _extract_response(response: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    texts: list[str] = []
    sources: list[dict[str, Any]] = []
    for item in response.get("output") or []:
        if item.get("type") == "web_search_call":
            action = item.get("action") or {}
            sources.extend(x for x in (action.get("sources") or []) if isinstance(x, dict))
        if item.get("type") == "message":
            for content in item.get("content") or []:
                if content.get("type") == "output_text" and content.get("text"):
                    texts.append(str(content["text"]))
                for annotation in content.get("annotations") or []:
                    citation = annotation.get("url_citation") if isinstance(annotation, dict) else None
                    candidate = citation or annotation
                    if isinstance(candidate, dict) and candidate.get("url"):
                        sources.append({"url": candidate.get("url"), "title": candidate.get("title")})
    return "\n".join(texts).strip(), sources


def run_diligence_search(*, jurisdiction: dict[str, Any] | None, topics: list[str] | None = None, provider: str = "FIXTURE") -> dict[str, Any]:
    requested = topics or sorted(TOPICS)
    invalid = sorted(set(requested) - TOPICS)
    if invalid:
        raise ValueError("unsupported_diligence_search_topics:" + ",".join(invalid))
    searched_at = _now()
    jur = jurisdiction or {}
    local_parts = [str(x) for x in (jur.get("county"), jur.get("state")) if x]
    jurisdiction_label = ", ".join(local_parts)
    search_location = jurisdiction_label or "United States (national screen only)"
    provider_u = provider.upper()
    if provider_u == "FIXTURE":
        data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        summary = str(data.get("summary") or "")
        raw_sources = list(data.get("sources") or [])
        provider_meta = {"name": "FIXTURE", "status": "FIXTURE", "model": "fixture", "search_version": SEARCH_VERSION}
    elif provider_u == "OPENAI":
        key = _key()
        if not key:
            return _failed_result(requested, searched_at, "NOT_CONFIGURED", "OPENAI", "credentials_missing")
        prompt = (
            "Research current public diligence context for an agricultural land buyer in "
            + search_location
            + ". Topics: " + ", ".join(requested) + ". "
            "Use only government or university sources. Explain what deserves follow-up. "
            "Do not claim parcel-specific legal compliance, permit certainty, water rights, "
            "usable water, forage condition, carrying capacity, profitability, or livestock fit. "
            "Lead with the named county/state or clearly state that only a national screen was possible. "
            "Use four short labeled bullets, one per topic, each ending with one buyer action. "
            "Keep the answer under 220 words and cite every material statement."
        )
        payload = {
            "model": _model(),
            "instructions": "You are a constrained agricultural land diligence researcher.",
            "input": prompt,
            "tools": [{"type": "web_search", "filters": {"allowed_domains": ALLOWED_DOMAINS}}],
            "include": ["web_search_call.action.sources"],
        }
        req = urllib.request.Request(
            (os.environ.get("RANGEMATCH_LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/") + "/responses",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        )
        try:
            with urllib.request.urlopen(req, timeout=90, context=ssl.create_default_context(cafile=certifi.where())) as resp:  # noqa: S310
                response = json.loads(resp.read().decode("utf-8"))
            summary, raw_sources = _extract_response(response)
            provider_meta = {"name": "OPENAI", "status": "OK", "model": _model(), "response_id": response.get("id"), "search_version": SEARCH_VERSION}
        except urllib.error.HTTPError as exc:
            return _failed_result(requested, searched_at, "FAILED", "OPENAI", "http_" + str(exc.code))
        except Exception as exc:  # noqa: BLE001
            return _failed_result(requested, searched_at, "FAILED", "OPENAI", type(exc).__name__)
    else:
        raise ValueError("unsupported_diligence_search_provider")
    sources = _normalize_sources(raw_sources, searched_at=searched_at, jurisdiction=jurisdiction_label)
    status = "COMPLETE" if summary and sources else ("PARTIAL" if summary or sources else "FAILED")
    return {
        "schema_version": SCHEMA_VERSION,
        "search_id": "dsearch_" + hashlib.sha256((searched_at + "|" + jurisdiction_label + "|" + str(requested)).encode()).hexdigest()[:16],
        "status": status,
        "topics": requested,
        "summary": summary,
        "sources": sources,
        "searched_at": searched_at,
        "location_scope": search_location,
        "provider": provider_meta,
        "effect_on_engine": "NONE",
        "limitations": [
            "Search evidence is diligence context only and does not modify F01-F08 or MatchResult.",
            "Source discovery does not prove that a rule applies to this parcel.",
            "No search result may establish usable water, forage condition, legal access, permit certainty, carrying capacity, or profitability.",
        ],
    }


def _failed_result(topics: list[str], searched_at: str, status: str, provider: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "search_id": "dsearch_" + hashlib.sha256((searched_at + "|" + reason).encode()).hexdigest()[:16],
        "status": status,
        "topics": topics,
        "summary": "",
        "sources": [],
        "searched_at": searched_at,
        "provider": {"name": provider, "status": status, "reason": reason, "search_version": SEARCH_VERSION},
        "effect_on_engine": "NONE",
        "limitations": ["Search failed closed; no evidence was added.", "F01-F08 and MatchResult were not changed."],
    }
