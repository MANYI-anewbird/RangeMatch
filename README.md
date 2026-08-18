# RangeMatch

**The question:** A listing says “good grass, good water, ready for cattle.” Before you spend on a site visit, is this *parcel’s* natural environment actually a foundation for cattle — or just a story?

RangeMatch is a **parcel-grounded land advisor** for U.S. ranch buyers and buyer-side brokers. Confirm the boundary, read terrain / forage / water / climate / soil for **this** property, get a directional natural-foundation report, then ask follow-up questions that stay on this parcel.

**How we built that:** **Mireye** confirms the polygon and supplies the physical-world layer; a Gap Detector calls public supplements only where evidence is missing; a grounded LLM writes the buyer narrative and **cannot invent** wells, fences, stocking rates, or a buy/no-buy.

One-pager: [`docs/RANGEMATCH_MIREYE_CHALLENGE_ONE_PAGER.md`](docs/RANGEMATCH_MIREYE_CHALLENGE_ONE_PAGER.md)

---

## Decision this supports

Buyers already have a process: pick a region, short-list listings, then hit the expensive question — **is this land credible enough to justify travel and specialists?**

That check is supposed to be cheap desk work. Today it is ChatGPT plus a pile of unconnected maps. Listings sell. Generic AI talks. GIS dumps layers. Nobody translates *this parcel’s* physics into an operating reading.

Two decisions RangeMatch is built for:

1. **Go deeper or stop** — does the natural environment look Promising, Conditional, or Insufficient for cattle, and what factor is in control?
2. **What to verify next** — one high-value environmental question, then a revised reading after you answer.

Primary payer: buyer-side ranch broker / land advisor. Beneficiary: the serious ranch buyer.

---

## What you get

1. A **confirmed parcel** — you pick the polygon; the agent does not auto-pick.
2. A **Natural Cattle Profile** — Terrain, Forage, Water, Climate, Soil — with honest gaps.
3. A **directional judgment** plus the controlling natural factor.
4. **One refining question**, then an updated view.
5. A **Natural Cattle Foundation PDF** — advisor narrative (variable length) + evidence appendix on a new page.
6. **Grounded chat** — read-only, this parcel only.

Demo geometry: enter a free-form U.S. address or `lat,lng`. **Nambe** is an explicit opt-in demo path, not a silent fallback. **CPER** is an engineering fixture, not a listing.

---

## What it will not claim

No suitability score. No stocking rate / AUM. No title, easement, or legal-access opinion. No water-rights or drinker capacity. No fence / facility detection. No cattle-vs-sheep ranking. No buy / no-buy.

The land did not fail. The *match* to an intended use is what we read — and even that reading stays directional.

---

## How we got there (short)

| Step | Why it matters |
|---|---|
| Confirm one Mireye polygon | Generic AI has language; it does not have *this* boundary |
| Mireye environmental profile first | Physical facts stay deterministic |
| Gap Detector + only missing F01–F08 supplements | No mandatory full Factor tour; F06 geometry always-on; F07 appendix-only |
| Cattle knowledge + Deal Context | The LLM interprets evidence; it does not invent the physical world |
| One question → revised interpretation → PDF + chat | The output a broker would actually send a buyer |

Failed lookup stays failed (`PARCEL_NOT_FOUND` vs `PARCEL_SERVICE_UNAVAILABLE`). LLM failure fails soft to validated deterministic prose for this parcel — not another property.

---

## What’s in the repo

| Path | |
|---|---|
| [`docs/README.md`](docs/README.md) | Read order for judges / new readers |
| [`docs/RANGEMATCH_PRODUCT_AND_AGENT_CODE_FLOW.md`](docs/RANGEMATCH_PRODUCT_AND_AGENT_CODE_FLOW.md) | Canonical product + agent authority |
| [`docs/TWO_BRAIN_ADVISOR_CHAT_CONTRACT.md`](docs/TWO_BRAIN_ADVISOR_CHAT_CONTRACT.md) | Chat grounding |
| [`docs/NATURAL_CATTLE_FOUNDATION_REPORT_TEMPLATE.md`](docs/NATURAL_CATTLE_FOUNDATION_REPORT_TEMPLATE.md) | Buyer report contract |
| `src/rangematch/` | Agent API |
| `web/` | Advisor Demo UI (`/advisor-demo`) |
| `docs/archive/` | Superseded product notes and dated gates — not current authority |

---

## How we built it (technical)

Stack: **Mireye** `POST /v1/lookup` + environmental profile → FastAPI agent (`rangematch.api`) → deterministic Gap Detector → optional F01–F08 adapters → Combined Environmental Evidence → Natural Cattle Profile → Deal Context v1/v2 → DeepSeek or OpenAI (or `FIXTURE`) for interpretation and chat → `fpdf2` PDF. UI: Vite on port **5273**.

**Two brains.** Physical brain: Mireye + targeted public supplements. Cattle brain: reviewed cattle-environment knowledge. The advisor layer may write prose; it may not create wells, fences, stocking rates, legal access, or a purchase recommendation. Malformed LLM output fails soft.

**Supplements.** F01–F08 run only for deterministic gaps. F06 (parcel configuration / geometry) is always-on core. F07 (roads / physical access) is appendix-only and cannot control the natural-foundation judgment (`HUMAN_ACCESS_INFRA_APPENDIX_ONLY`).

**Demo contract.** Free-form U.S. street address or `lat,lng`. APN-only lookup is not supported. Messy phrases (`near Nunn Colorado`) may be tidied into a structured lookup; the LLM still cannot invent coordinates or pick a parcel. You confirm exactly one polygon. The agent never silently substitutes Nambe or CPER.

**Legacy path.** The frozen F01–F08 Factor stack, Planner/Executor, and One-Parcel investigation API remain for science and regression. They are not the Advisor Demo story. Do not restore product behavior from `docs/archive/` without an explicit reopen.

**Current Demo status (2026-08-15):** Mireye-first collection, five-domain Profile, interpretation + one question, variable-length PDF + new-page appendix, two-brain chat, DeepSeek fail-soft, `/advisor-demo` UI — all shipped. Local baseline: **687** backend tests, **34** UI tests.

---

## Setup

Copy `.env.example` to `.env`. Never commit `.env`.

| Variable | Role |
|---|---|
| `MIREYE_API_BASE_URL` | Mireye API origin |
| `MIREYE_API_TOKEN` | Bearer token (`MIREYE_API_KEY` is a legacy alias) |
| `RANGEMATCH_LLM_PROVIDER` | `DEEPSEEK` or `OPENAI` for live prose; otherwise `FIXTURE` |
| `DEEPSEEK_API_KEY` | When provider is `DEEPSEEK` |
| `RANGEMATCH_LLM_API_KEY` | Shared live-LLM alias |

```bash
# Terminal A — Agent API (API 8001, UI 5273)
export PYTHONPATH=src
.venv/bin/uvicorn rangematch.api:app --reload --port 8001 --env-file .env \
  --reload-exclude '.venv' --reload-exclude '.venv-livegate' --reload-exclude 'web'

# Terminal B — Demo UI
cd web && npm install && npm run dev
```

Open **http://127.0.0.1:5273/advisor-demo**. Port 5273 is pinned (`strictPort: true`).

```bash
export PYTHONPATH=src
.venv/bin/python -m unittest discover -s tests
cd web && npm test
```

---

## License

See [LICENSE](LICENSE).
