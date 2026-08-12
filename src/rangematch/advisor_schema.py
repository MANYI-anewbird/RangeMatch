"""Draft 2020-12 JSON Schema gates for Advisor LLM objects.

Order in the live loop:
  LLM JSON → schema validation → semantic Validator → Renderer → report schema
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.jsonschema import DRAFT202012

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "docs" / "schemas"

INSIGHT_BUNDLE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://rangematch.local/schemas/advisor_insight_bundle.schema.json",
    "title": "RangeMatchAdvisorInsightBundle",
    "type": "object",
    "additionalProperties": False,
    "required": ["insights"],
    "properties": {
        "insights": {
            "type": "array",
            "minItems": 1,
            "items": {"$ref": "https://rangematch.local/schemas/advisor_insight_record.schema.json"},
        }
    },
}


@lru_cache(maxsize=None)
def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _registry() -> Registry:
    docs = {
        schema["$id"]: schema
        for schema in (
            _load_schema("advisor_llm_workbench.schema.json"),
            _load_schema("advisor_insight_record.schema.json"),
            _load_schema("advisor_buyer_report.schema.json"),
            _load_schema("advisor_knowledge_card.schema.json"),
            INSIGHT_BUNDLE_SCHEMA,
        )
    }
    return Registry().with_resources(
        (schema_id, DRAFT202012.create_resource(doc)) for schema_id, doc in docs.items()
    )


def _validator(schema: dict[str, Any]) -> Draft202012Validator:
    return Draft202012Validator(schema, registry=_registry())


def _format_errors(errors: list[Any], *, code: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for err in sorted(errors, key=lambda e: list(e.absolute_path)):
        path = ".".join(str(part) for part in err.absolute_path) or "$"
        rows.append({"code": code, "message": f"{path}: {err.message}"})
    return rows


def validate_workbench_schema(workbench: dict[str, Any]) -> list[dict[str, str]]:
    schema = _load_schema("advisor_llm_workbench.schema.json")
    return _format_errors(list(_validator(schema).iter_errors(workbench)), code="WORKBENCH_SCHEMA_INVALID")


def validate_knowledge_cards_schema(cards: list[dict[str, Any]]) -> list[dict[str, str]]:
    schema = _load_schema("advisor_knowledge_card.schema.json")
    validator = _validator(schema)
    rows: list[dict[str, str]] = []
    for index, card in enumerate(cards):
        for err in validator.iter_errors(card):
            path = ".".join(str(part) for part in err.absolute_path) or "$"
            rows.append(
                {
                    "code": "KNOWLEDGE_CARD_SCHEMA_INVALID",
                    "message": f"knowledge_cards[{index}].{path}: {err.message}",
                }
            )
    return rows


def validate_insight_bundle_schema(bundle: dict[str, Any]) -> list[dict[str, str]]:
    return _format_errors(
        list(_validator(INSIGHT_BUNDLE_SCHEMA).iter_errors(bundle)),
        code="INSIGHT_SCHEMA_INVALID",
    )


def validate_buyer_report_schema(report: dict[str, Any]) -> list[dict[str, str]]:
    schema = _load_schema("advisor_buyer_report.schema.json")
    return _format_errors(list(_validator(schema).iter_errors(report)), code="BUYER_REPORT_SCHEMA_INVALID")
