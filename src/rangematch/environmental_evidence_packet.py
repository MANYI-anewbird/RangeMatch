"""Combined Environmental Evidence Packet — Mireye + core + supplements.

Merge rules from the product authority:
1. never average/overwrite different spatial semantics
2. preserve values that answer different spatial questions
3. stable IDs/hashes
4. expose conflicts; LLM cannot resolve them
5. retain failures technically; omit empty buyer rows downstream
"""

from __future__ import annotations

from typing import Any, Mapping

from rangematch.environmental_supplement_runner import (
    build_combined_environmental_evidence_packet as _build,
)

SCHEMA_VERSION = "combined_environmental_evidence_packet@1.0.0"


def build_combined_environmental_evidence_packet(
    *,
    mireye_profile: Mapping[str, Any],
    gap_plan: Mapping[str, Any],
    supplement_execution: Mapping[str, Any],
    f06: Mapping[str, Any] | None = None,
    geometry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return _build(
        mireye_profile=mireye_profile,
        gap_plan=gap_plan,
        supplement_execution=supplement_execution,
        f06=f06,
        geometry=geometry,
    )


def buyer_visible_observations(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Appendix-safe rows: retrieved/partial with non-empty values only."""
    rows: list[dict[str, Any]] = []
    for key in ("mireye_observations", "core_observations", "supplement_observations"):
        for obs in packet.get(key) or []:
            if not isinstance(obs, Mapping):
                continue
            if obs.get("status") not in {"RETRIEVED", "PARTIAL"}:
                continue
            if obs.get("value") is None:
                continue
            if isinstance(obs.get("value"), str) and not str(obs.get("value")).strip():
                continue
            rows.append(dict(obs))
    return rows
