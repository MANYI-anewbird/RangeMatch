"""Fail-soft collection for Appendix-only human/access context.

F07 is intentionally outside the environmental Gap Detector and Combined Evidence
Packet.  This collector runs after parcel confirmation only to populate Page 2B.
Its output must never enter the Natural Cattle Profile or the primary LLM workbench.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any, Callable, Mapping

from rangematch.advisor_generic_collect import (
    ADAPTER_TIMEOUT_S,
    _default_live_runners,
    _dependency_reason,
    _is_missing_dependency,
)

FACTOR_ID = "F07_ROAD_AND_PHYSICAL_ACCESS"
COLLECTION_ROLE = "APPENDIX_CONTEXT_COLLECTOR"
DISPLAYABLE_VARIABLES = frozenset({"VAR_F07_NEAREST_MAPPED_ROAD_DISTANCE_M"})


def _f07_observations(factor: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fact in factor.get("land_facts") or []:
        if not isinstance(fact, Mapping):
            continue
        variable_id = str(fact.get("variable_id") or "")
        value = fact.get("value")
        # Do not expose technical search-window counts as buyer context.
        if variable_id not in DISPLAYABLE_VARIABLES or value is None:
            continue
        rows.append(
            {
                "observation_id": f"APPENDIX_{variable_id}",
                "land_fact_ref": variable_id,
                "label": variable_id,
                "value": value,
                "unit": fact.get("unit"),
                "evidence_state": "RETRIEVED",
                "source_id": fact.get("source_id")
                or factor.get("canonical_source_id")
                or "US_CENSUS_TIGER_LINE_2025_ALL_ROADS",
                "spatial_semantics": fact.get("spatial_semantics") or "CONTEXT",
                "classification": "APPENDIX_ONLY",
            }
        )
    return rows


def collect_additional_property_context(
    *,
    geometry: Mapping[str, Any],
    geometry_id: str,
    geometry_hash: str,
    geometry_reference: str,
    runner: Callable[[], Any] | None = None,
    timeout_s: float | None = None,
) -> dict[str, Any]:
    """Run F07 fail-soft and return an isolated Appendix-only collection record."""
    if runner is None:
        runner = _default_live_runners(
            geometry=geometry,
            geometry_id=geometry_id,
            geometry_hash=geometry_hash,
            geometry_reference=geometry_reference,
            mireye_contexts={},
        )[FACTOR_ID]
    limit = ADAPTER_TIMEOUT_S if timeout_s is None else float(timeout_s)
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(runner)
    try:
        payload = future.result(timeout=max(0.0, limit))
        factor = dict(payload) if isinstance(payload, Mapping) else {}
        observations = _f07_observations(factor)
        return {
            "role": COLLECTION_ROLE,
            "factor_id": FACTOR_ID,
            "status": "SUCCEEDED" if observations else "PARTIAL",
            "error": None if observations else "NO_DISPLAYABLE_CONTEXT",
            "observations": observations,
            "may_affect_natural_profile": False,
            "may_enter_primary_llm_workbench": False,
            "may_change_conclusion": False,
        }
    except TimeoutError:
        future.cancel()
        return {
            "role": COLLECTION_ROLE,
            "factor_id": FACTOR_ID,
            "status": "SOURCE_UNAVAILABLE",
            "error": "ADAPTER_TIMEOUT",
            "observations": [],
            "may_affect_natural_profile": False,
            "may_enter_primary_llm_workbench": False,
            "may_change_conclusion": False,
        }
    except Exception as exc:  # noqa: BLE001 - Appendix failure must never fail the run
        reason = _dependency_reason(exc) if _is_missing_dependency(exc) else (str(exc) or type(exc).__name__)
        return {
            "role": COLLECTION_ROLE,
            "factor_id": FACTOR_ID,
            "status": "SOURCE_UNAVAILABLE",
            "error": reason,
            "observations": [],
            "may_affect_natural_profile": False,
            "may_enter_primary_llm_workbench": False,
            "may_change_conclusion": False,
        }
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
