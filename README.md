# RangeMatch

**Understand a parcel's natural foundation for cattle before deeper field work.**

RangeMatch is an AI natural-environment advisor for U.S. cattle-land screening. **Mireye** confirms the parcel and supplies the **primary Physical World Layer**. A deterministic Gap Detector calls RangeMatch supplements only for missing capabilities. Reviewed cattle-environment knowledge then combines with that parcel evidence so a grounded LLM can produce a directional natural-foundation assessment and support open-ended conversation about **this** property.

Unified product sentence:

> RangeMatch confirms a parcel with Mireye, builds a parcel-specific physical-world profile, fills material evidence gaps with targeted public sources, and combines that evidence with reviewed cattle knowledge. A grounded LLM then produces a directional natural-foundation assessment and supports open-ended conversation about that specific property. The advisor narrative may span multiple pages; the evidence appendix always begins on a new page.

- **Primary payer:** buyer-side ranch broker / land advisor
- **Beneficiary / second payer:** serious ranch buyer
- **Demo geometry:** CPER is an engineering test geometry, not a real listing

One-pager: `docs/RANGEMATCH_MIREYE_CHALLENGE_ONE_PAGER.md`  
Docs map: `docs/README.md`  
Canonical product + Agent flow: `docs/RANGEMATCH_PRODUCT_AND_AGENT_CODE_FLOW.md`  
Chat contract: `docs/TWO_BRAIN_ADVISOR_CHAT_CONTRACT.md`

## Competition Demo

RangeMatch confirms a parcel through Mireye, builds a five-domain Natural Cattle Profile (Terrain / Forage / Water / Climate / Soil), combines it with reviewed cattle-environment knowledge and buyer Deal Context, asks one question that can change the interpretation, exports a Natural Cattle Foundation PDF (variable-length advisor narrative + new-page Appendix), and offers open-ended grounded chat over the same two brains.

**Nambe is not a product prerequisite.** It is the verified Demo path, a regression fixture, and a standby exhibit if the network is down. CPER is an engineering fixture only.

**Demo entry is free-form** U.S. address or `lat,lng`. Failed lookups stay failed. The Agent never silently substitutes Nambe or CPER. Judges may opt into the verified Nambe Demo explicitly; that creates a new isolated run.

```text
free-form address / lat,lng
→ Mireye POST /v1/lookup
→ judge confirms exactly one polygon
→ Mireye cattle-environment Profile + confirmed-geometry core
→ deterministic Gap Detector
→ only planned F01–F05/F08 supplements (F06 always-on; F07 Appendix-only)
→ Combined Environmental Evidence → Natural Cattle Profile
→ Deal Context v1 + validated LLM interpretation + one question
→ answer → Deal Context v2 → revised interpretation
→ Natural Cattle Foundation PDF (narrative pages + Appendix on a new page)
→ open-ended two-brain grounded chat (read-only)
```

It does **not** claim a complete livestock operating assessment, cattle/sheep comparison, fence/facility detection, stocking rates, legal conclusions, or national production validation.

### Environment

Copy `.env.example` to `.env`. Required for live Demo:

| Variable | Role |
|---|---|
| `MIREYE_API_BASE_URL` | Mireye API origin |
| `MIREYE_API_TOKEN` | Bearer token (canonical). `MIREYE_API_KEY` is a legacy alias |
| `RANGEMATCH_LLM_PROVIDER` | `DEEPSEEK` or `OPENAI` for live prose, otherwise `FIXTURE` / omit |
| `DEEPSEEK_API_KEY` | DeepSeek key when provider is `DEEPSEEK` |
| `RANGEMATCH_LLM_API_KEY` | Shared live-LLM key alias (DeepSeek or OpenAI) |

Never commit `.env`.

### Start

```bash
# Terminal A — Agent API (ports are fixed: API 8001, UI 5273)
export PYTHONPATH=src
.venv/bin/uvicorn rangematch.api:app --reload --port 8001 --env-file .env \
  --reload-exclude '.venv' --reload-exclude '.venv-livegate' --reload-exclude 'web'

# Terminal B — Demo UI
cd web && npm install && npm run dev
```

Open **http://127.0.0.1:5273/advisor-demo**

RangeMatch pins this Demo to port **5273** (`strictPort: true`). If 5273 is busy, stop that process and restart `npm run dev`.

### Support scope and confirmation

- **Demo entry:** free-form U.S. street address or `lat,lng`. APN-only lookup is not supported. Verified Nambe is an explicit opt-in Demo run, not a silent fallback.
- **Messy language:** a standard street or `lat,lng` goes straight to Mireye. Phrases like `near Nunn Colorado` may be tidied by the LLM into a structured lookup. The LLM cannot invent coordinates, polygons, or pick a parcel. Mireye still locates the place; you still confirm the boundary.
- **Required confirm:** if Mireye returns one or more parcel polygons, the judge must confirm exactly one boundary. The Agent does not auto-pick.
- **After confirm:** Mireye builds the primary Profile; the Gap Detector invokes only the supplements needed for missing capabilities. F06 geometry is always-on core; F07 is Appendix-only and cannot control the natural-foundation judgment.
- **Adapter miss:** a timed-out or missing federal source still yields an honest limited investigation. It does not swap another parcel.
- **Lookup miss:** `PARCEL_NOT_FOUND` vs `PARCEL_SERVICE_UNAVAILABLE` fail closed with named outcomes. No fake report.
- **LLM miss:** DeepSeek/OpenAI failure fails soft. Interpretation and chat keep a validated deterministic fallback for this parcel; field-level soft fallbacks may apply inside natural-foundation prose without discarding the whole run.
- **CPER:** engineering fixture only, not a nationwide confirmation model.
- **Standby PDF:** keep a saved report from a successful Nambe run for network-down exhibit (do not substitute it for a failed live parcel).

Buyer-facing progress:

```text
Confirm parcel
Build natural cattle foundation
Ask one refining question
Download report
Open grounded chat
```

## Tests

```bash
export PYTHONPATH=src
.venv/bin/python -m unittest discover -s tests
cd web && npm test
```

Current baseline (2026-08-15 local): **687** backend tests passed; **34** UI tests passed.

## Current Demo status

```text
Mireye-first collection (MIREYE_FIRST): DONE
Natural Cattle Profile (Terrain / Forage / Water / Climate / Soil): DONE
Natural Foundation Interpretation + one refining question: DONE
Variable-length Natural Cattle Foundation PDF + new-page Appendix: DONE
Open-ended two-brain grounded chat (read-only): DONE
DeepSeek fail-soft + field-level soft fallbacks: DONE
Advisor Demo UI (/advisor-demo): DONE
```

See:

- `docs/README.md` — judge documentation map
- `docs/RANGEMATCH_PRODUCT_AND_AGENT_CODE_FLOW.md` — product + Agent authority
- `docs/TWO_BRAIN_ADVISOR_CHAT_CONTRACT.md` — chat grounding contract
- `docs/NATURAL_CATTLE_FOUNDATION_REPORT_TEMPLATE.md` — buyer report template
- `web/README.md` — Demo UI run notes

## Secrets

- Use `.env` locally (gitignored).
- Only `.env.example` is committed.
- Do not put API keys in docs, fixtures, or Skills.

<details>
<summary>Legacy engineering interfaces (not the competition Demo narrative)</summary>

The frozen F01–F08 Factor stack, Planner/Executor, One-Parcel investigation API, Constrained Intent Parser, and Engine HOLD buyer-report path remain in the repo for science and regression. They are **not** the Mireye-first Advisor Demo story.

- Factor / Planner contracts: `docs/F01_F08_UNIFIED_OUTPUT_CONTRACT.md`, `docs/PLANNER_EXECUTOR_SPEC.md`, `docs/PLANNER_ROUTING_SPEC.md`, `docs/AGENT_ORCHESTRATION_SPEC.md`
- Parcel resolution + One-Parcel API: `docs/PARCEL_RESOLUTION_CONTRACT.md`, `docs/ONE_PARCEL_API_SPEC.md`
- Legacy LLM buyer-report authority (archived): `docs/archive/product-history/LLM_AUTHORITY_AND_REPORT_SPEC.md`
- CPER fixture CLI / investigation replay: `python -m rangematch.cli evaluate …`, `POST /v1/investigations` with `execution_source: DEMO_FIXTURE`

Do not restore product behavior from these files without an explicit governance reopen.

</details>
