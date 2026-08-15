# Advisor Nambe report loop

> Status: `IMPLEMENTED — BUNDLE + CONDITIONAL BRIEF + PDF DOWNLOAD`  
> Date: 2026-08-12  
> Competition artifact: a real confirmed address, not a polished CPER PDF

## What judges should see

```text
address → Mireye candidates → user confirms outline
  → F01–F08 on that polygon
  → Mireye Property / Land / Hazard as context only
  → Generic Packet → Validator
  → LLM buyer prose (optional)
  → Download 3-page Buyer Brief
```

Mireye is the parcel entry and context anchor. It is not a substitute for USGS / RAP / NHD / NOAA / TIGER land facts.

Next product layer (does not replace this loop): `docs/LIVESTOCK_OPERATING_PROFILE_CONTRACT.md`. First closed loop is Nambe + Cattle → Operating Profile → ranch story PDF.

## Durable evidence

`GET /v1/advisor/runs/{run_id}/report-bundle` persists the in-memory run:

- user input and confirmed geometry/hash
- Mireye lookup + context status/payloads (secrets redacted)
- Unified Output when the worker still holds it
- Generic Evidence Packet, objects, action policy
- LLM workbench, insights, buyer report
- provenance / source status

Write a copy to `test-data/advisor/nambe/nambe_advisor_report_bundle.json` after a live Nambe run. Restarting 8001 clears memory.

## PDF

`GET /v1/advisor/runs/{run_id}/buyer-brief.pdf` renders only when `brief.validation_status=PASSED`.

- Page 1: LLM prose when Live LLM passed; otherwise the deterministic brief
- Page 2: listing-claim theater only when listing claims exist; otherwise public-evidence vs transaction documents
- Page 3: polygon observations, federal sources, Mireye provenance (`CONTEXT_ONLY` / `PARCEL_ENTRY`)

Demo UI: **Download 3-page Buyer Brief**.

## Knowledge

Four Demo-approved cards (not a national knowledge base):

- Legal access diligence
- Livestock water diligence
- RAP interpretation
- Evidence-status interpretation
