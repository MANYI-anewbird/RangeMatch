# Advisor Generic Evidence Packet

> Status: `IMPLEMENTED — PROJECTOR + MINIMAL POLICY + CONFIRMED RUN CHAIN (v0)`  
> Date: 2026-08-12  
> Module: `src/rangematch/advisor_generic_packet.py`  
> Collect: `src/rangematch/advisor_generic_collect.py`  
> Assembler: `src/rangematch/advisor_packet.py` (`project_buyer_evidence_packet`)  
> Run: `src/rangematch/advisor_agent.py` (`TRACK_GENERIC` after `PARCEL_CONFIRMED`)  
> Depends on: `docs/ADVISOR_PARCEL_CONFIRMATION_GATE.md`  
> Non-goals (this slice): LLM action invention; CPER claim inheritance; silent CPER substitution when adapters fail

## Purpose

Project a Buyer Evidence Packet from **any** Unified Output without inheriting CPER demo claims, objects, policy scope, or fixture paths.

```text
Confirmed parcel Unified Output
  → observations (canonical land facts + coverage/failure)
  → F03 candidate objects (or empty / failed)
  → listing claims (empty if none)
  → evidence gaps
  → minimal generic action policy (3 classes)
  → packet (policy_scope=GENERIC_MINIMAL)
```

## Hard rules

1. Never call `build_cper_demo_policy` or `project_cper_buyer_evidence_packet` for non-CPER geometry.
2. Never copy CPER listing claims, F03 fixture paths, or CPER display labels into a generic packet.
3. `listing_claims=[]` is valid.
4. Missing land facts → observation `evidence_state=SOURCE_UNAVAILABLE` (or coverage failure), not invented numbers.
5. Bottleneck/action ranking is deterministic from confirmation status, decision stage, F03 mode, and dependencies — not LLM.

## Minimal action classes (v0)

| Class | Action id(s) | Role |
|---|---|---|
| Legal access paper | `ACTION_ACCESS_DOCUMENTS` | Document request before travel |
| Livestock water verify | `ACTION_WATER_*` (mode-dependent) | Field/document ask from mapped-water state |
| RAP / forage interpret | `ACTION_INTERPRET_RAP_FORAGE` | Desktop: modeled production ≠ stocking plan |

## API

```python
from rangematch.advisor_generic_packet import (
    build_generic_minimal_policy,
    project_generic_buyer_evidence_packet,
)

packet = project_generic_buyer_evidence_packet(
    unified_output,
    listing_claims=[],  # or caller-supplied
    confirmation_status="CONFIRMED",
    unified_output_ref="<path or opaque ref>",
    candidate_inventory=None,  # or inventory
    f03_status=None,           # FAILED | AVAILABLE | inferred
)
```

## Advisor run chain

Confirmed non-CPER (`parcel_resolution_id` → `PARCEL_CONFIRMED`) continues:

```text
CALL_MIREYE → BUILD_AGENDA (generic plan) → RUN_AGENDA (F01–F08 collect + UO)
  → COMPARE_CLAIMS (project_generic_buyer_evidence_packet)
  → ORDER_ACTIONS / VALIDATE_BRIEF
```

- Production collect uses live adapters; each failure is `PARTIAL` / `SOURCE_UNAVAILABLE`.
- Unit tests inject `set_advisor_factor_collect_for_tests` — no USGS/RAP/NHD/TIGER sockets.
- F06 is always derived from the confirmed geometry (not invented climate/water numbers).
- Outcome is `EVIDENCE_INVESTIGATION_COMPLETED` with `policy_scope=GENERIC_MINIMAL` even when most adapters fail.

## Next

Optional LLM overlay after Validator; live-adapter reliability on real listings. Do not reopen CPER demo policy as a nationwide default.
