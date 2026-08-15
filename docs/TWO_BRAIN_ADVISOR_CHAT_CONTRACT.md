# Two-Brain Advisor Chat Contract

> Status: `CURRENT_CHAT_CONTRACT`  
> Version: `1.0.0`  
> Effective date: 2026-08-15  
> Product authority: `RANGEMATCH_PRODUCT_AND_AGENT_CODE_FLOW.md`  
> Supersedes: bounded six-intent diligence chat framing; archived `LLM_AUTHORITY_AND_REPORT_SPEC.md` Intent + Engine buyer-report chat assumptions

## 0. Purpose

Define how RangeMatch Chat answers questions about **one confirmed parcel** after a succeeded Advisor run.

RangeMatch Chat is an open-ended cattle advisor grounded in two brains:

1. **Place materials (Physical World brain)** — verified physical evidence and readings for this parcel  
2. **Cattle knowledge (Knowledge brain)** — reviewed cattle-environment interpretation cards

## 1. Inputs (read-only)

For `collection_mode=MIREYE_FIRST` the chat workbench is built from:

| Brain | Run artifacts |
|---|---|
| Place materials | Combined Environmental Evidence Packet observations; Natural Cattle Profile domains; Natural Foundation Interpretation projected to an advisor view; Deal Context |
| Cattle knowledge | Approved `natural_cattle` knowledge cards (`topic` + `statement`) |

Chat **must not** mutate Packet, Profile, Interpretation, or Deal Context. Mutation attempts fail closed.

Legacy Buyer Packet + Operating Conclusion chat remains available only on non-`MIREYE_FIRST` runs.

## 2. Behavior

- Live answers are ordinary LLM prose over the two sources above — like handing those documents to a normal assistant.
- Prefer place materials for parcel facts; use cattle knowledge for how to interpret them.
- If a fact is absent from both sources, say so. Do not invent wells, fences, gates, drinkers, stocking rates, legal access, or buy/no-buy.
- Intent labels (`WATER`, `FEED`, …) are **metadata only**. They do not restrict which questions may be answered.
- API responses keep a stable JSON turn shape (`judgment`, `answer`, refs, follow-up) for the UI; that schema is not a product content ban.
- Validation is a **schema gate**. Content bans that previously rejected natural prose are removed. Unknown evidence/knowledge refs are dropped quietly rather than forcing a fallback when the answer itself is usable.
- FIXTURE / provider failure falls soft to a deterministic turn assembled from the same place materials.

## 3. UI contract

- Chat opens as a dedicated overlay from the Advisor Demo after a succeeded run.
- Copy must disclose the two-brain grounding (place evidence + reviewed cattle-environment knowledge).
- Suggested questions are optional shortcuts, not a closed catalog of allowed topics.

## 4. Out of scope

- Editing physical evidence or Deal Context through chat
- Treating the PDF file bytes as the chat document (chat reads structured run artifacts, not the PDF binary)
- National encyclopedic cattle advice disconnected from this parcel's materials
- Legal, appraisal, financing, or purchase instructions

## 5. Related code

- `src/rangematch/advisor_chat.py` — workbench, prompt, schema gate, fail-soft
- `src/rangematch/advisor_agent.py` — `post_advisor_chat` MIREYE_FIRST path
- `test-data/advisor/knowledge/` — approved knowledge cards
- `web/src/pages/AdvisorDemoPage.tsx` — Property chat overlay
