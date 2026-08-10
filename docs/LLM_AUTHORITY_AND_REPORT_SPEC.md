# Constrained LLM Authority and Buyer Report Spec

> Status: `EXECUTABLE_SLICE_V0_1`
> Date: 2026-08-08
> Scope: Intent Parser + Buyer Report Generator + Deterministic Validator
> Authority: Engine / Unified Output remain sole scientific decision source
> Current product presentation: `BUYER_DECISION_REPORT_V2`

## Purpose

Add real but tightly constrained LLM participation:

1. Natural-language user request → validated structured intent
2. Unified Output → buyer-readable structured report
3. Deterministic validation before any LLM report is shown

The LLM must **never** participate in F01–F08 Factor evaluation, scientific
rules, Cow-Calf/Sheep ranking, or Engine decision labels.

## Search side branch

Dynamic public research is handled by the separate
`DILIGENCE_SEARCH_AGENT_SPEC.md` contract. Search evidence may be cited in
buyer diligence context after its source gate passes, but it cannot modify
F01–F08, MatchResult, or operation ranking.

## Non-goals

- Packaging / Docker / Skill
- F09 / batch / ICP
- Silent fixture substitution for a requested live LLM call

## Versions

```text
INTENT_PROMPT_VERSION=RANGEMATCH_INTENT_PARSER@0.1.0
BUYER_REPORT_PROMPT_VERSION=RANGEMATCH_BUYER_REPORT@0.1.0
BUYER_REPORT_SCHEMA=docs/schemas/buyer_report.schema.json
INTENT_SCHEMA=docs/schemas/rangematch_intent.schema.json
```

## Provider design

| Provider | Env |
|---|---|
| `FIXTURE` | `RANGEMATCH_LLM_PROVIDER=FIXTURE` (default for tests/demo) |
| `OPENAI` | `RANGEMATCH_LLM_PROVIDER=OPENAI` + API key |

Environment:

```bash
RANGEMATCH_LLM_PROVIDER=FIXTURE|OPENAI
RANGEMATCH_LLM_MODEL=<model id>
RANGEMATCH_LLM_API_KEY=...   # or OPENAI_API_KEY
RANGEMATCH_LLM_BASE_URL=https://api.openai.com/v1   # optional
RANGEMATCH_LLM_TEMPERATURE=0
```

Rules:

- No model or key hardcoded in source
- No API key in logs, fixtures, hashes, responses, or docs
- Preserve `provider`, `model_id`, `prompt_version`, `generated_at`, `provider_status`
- Missing key for a live provider request → `provider_status: NOT_CONFIGURED`
- Live provider transport/API failure → `provider_status: FAILED_EXTERNAL`
- **Never** silently substitute fixture output when the caller requested a live provider

## Authority boundary

```yaml
llm_can:
  - parse natural language into structured intent under schema
  - write buyer-facing narrative grounded in Unified Output
  - translate Factor IDs into human names
  - explain HOLD, unknowns, and BLOCKED_EXTERNAL in plain language
  - propose diligence wording already implied by Engine unknowns/actions

llm_cannot:
  - change decision_label
  - change Factor signal
  - change ranking_permission / invent ranking
  - invent numeric land facts, URLs, sources, acreage, APN, geometry
  - claim carrying capacity, profitability, legal compliance, or permit certainty
  - claim a globally best land use
  - omit material unknowns required by the validator
```

## A. Intent Parser

### Input

- `user_request` (required string)
- exactly one optional structured parcel input: `address` | `parcel_geometry` | `existing_land_profile_reference`
- optional explicit UI selections (`mode`, `intended_operation`, `planned_actions`) — **authoritative when present**

### Output (`rangematch_intent.schema.json`)

- `intent_status`: `PARSED` | `NEEDS_CLARIFICATION` | `REJECTED`
- `rejection_code` when rejected (e. for batch: `REJECTED_OUT_OF_SCOPE_BATCH`)
- `mode`, `intended_operation`, `planned_actions`
- `parcel_input_reference`
- `clarification_questions`
- `parser_provenance`
- `prohibited_inferences_applied: true`

### Rules

- Explicit UI selections override LLM guesses.
- `GOAL_DIRECTED` requires one supported intended operation.
- `DISCOVERY` requires `intended_operation = null`.
- Unsupported operations → `NEEDS_CLARIFICATION` or `REJECTED` with supported options — **do not map** to Cow/Sheep.
- Do not invent address, APN, geometry, acreage, or planned actions.
- Do not create batch/portfolio/ICP intent.
- Do not interpret “best use” beyond currently supported Cow-Calf/Sheep.
- Schema validation after LLM parsing; invalid output fails closed.

### Examples

| Request | Result |
|---|---|
| “…cow-calf… may drill a well.” | `GOAL_DIRECTED` / `COW_CALF_OPERATION` / `planned_actions: [DRILL_WELL]` |
| “What can this parcel be used for?” | `DISCOVERY` / `intended_operation: null` |
| “Find the best 50 ranches in Colorado.” | `REJECTED` / `REJECTED_OUT_OF_SCOPE_BATCH` |

## B. Buyer Report Generator

### Input

- Validated Unified Output only
- User mode / intended operation / approved planned actions
- `match_result_hash`
- Compact evidence/reference index (no credentials, raw headers, cache paths)

### Output

Structured JSON (`buyer_report.schema.json`), not HTML.

Required top-level sections:

1. `executive_summary`
2. `property`
3. `land_and_resources`
4. `resilience_and_hazards`
5. `operation_comparison`
6. `key_unknowns`
7. `diligence_plan`
8. `methodology_and_limitations`
9. `evidence_references`
10. `claim_ledger`
11. `report_provenance`

Narrative sections include: `heading`, `summary`, `findings[]`, `evidence_refs[]`, `limitation_refs[]`.

These schema sections remain the validated narrative substrate. The current buyer UI does not display generic Property/Land/Hazards prose as the primary decision surface. It deterministically projects canonical Land Facts into:

- a parcel facts table with values, units, meaning, and evidence state;
- a Cow-Calf vs. Sheep evidence matrix;
- decision-changing diligence actions;
- the validated Executive Summary and Key Unknowns;
- current official-source guidance from the separate Diligence Search Agent.

This presentation projection may reorganize validated content but cannot add claims or alter Engine authority.

### Required buyer language

- Engine `HOLD` = buyer-facing **More evidence needed**, not unsuitable land
- Mireye `BLOCKED_EXTERNAL` in plain language; must not dominate the whole report
- Human Factor names
- Point context vs parcel-wide evidence
- Comparisons cover only Cow-Calf and Sheep
- Never claim a globally best land use

## C. Deterministic Report Validator

A report is **not displayable** until validation passes (`validation_status: PASSED`).

When the LLM provider is unavailable or validation fails, the failed narrative remains non-displayable. The buyer UI must preserve the successful deterministic investigation and render a clearly labeled **Deterministic fallback report** from the Engine/Unified Output sections. The fallback is not an LLM report and does not relax validation.

### Checks

1. **Authority** — decision labels, Factor signals, ranking permission match Engine/UO exactly; presentation order may change, science may not.
2. **Numeric grounding** — every buyer-visible numeric claim in section `summary`, section `findings`, and `claim_ledger` must:
   - resolve to a canonical Land Fact from Unified Output;
   - bind through `numeric_refs` (sections with bare numbers and no `numeric_refs` fail);
   - match value/unit within formatting tolerance, or an explicitly approved conversion (rounding; fraction → percent).
   No new arithmetic. Unknown ledger rows and verbatim Engine unknown strings may retain digits without inventing Land Facts.
3. **Evidence grounding** — trusted evidence IDs come **only** from Unified Output. `report.evidence_references` never expands the trusted set; declaring an invented `ref_id` there is a fabrication failure. Every `evidence_ref` / `numeric_ref` must resolve against that UO index; no fabricated URL/source/title; point facts remain point context.
4. **Unknown preservation** — material unknowns must remain for F02 coverage, F03 water verification, F07 legal access/entrance, F08 coverage/browse, and Mireye partial/`BLOCKED_EXTERNAL` when applicable. Valid Engine decision labels and unknowns remain displayable when grounded.
5. **Prohibited claims** — reject reports asserting:
   - carrying capacity
   - profitability
   - legal compliance / “permit not required” / water-rights certainty
   - suitability score / ranked best use when `ranking_permitted` is false
   - that HOLD means the land is unsuitable
   - fabricated live Mireye success when disposition is `BLOCKED_EXTERNAL`

Failed validation → `validation_status: FAILED` + `violations[]`; report body must not be treated as buyer-facing. UI keeps the labeled deterministic fallback when validation fails.

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/intent/parse` | Parse NL (+ optional UI overrides) → validated intent |
| `POST` | `/v1/investigations/{id}/buyer-report` | Generate + validate buyer report from stored Unified Output |
| `GET` | `/v1/investigations/{id}/buyer-report` | Return last validated buyer report if present |

`GET /health` includes LLM provider status summary (never keys).

## Implementation files

- `src/rangematch/llm_provider.py`
- `src/rangematch/intent_parser.py`
- `src/rangematch/buyer_report.py`
- `src/rangematch/report_validator.py`
- `docs/schemas/rangematch_intent.schema.json`
- `docs/schemas/buyer_report.schema.json`
- `test-data/llm/` fixtures
- `tests/test_intent_parser.py`
- `tests/test_buyer_report.py`
- `tests/test_report_validator.py`
- API wiring in `src/rangematch/api.py`
