# OpenAI Live Gate Results — 2026-08-08

## Scope

Controlled live validation used only generic connectivity text and the public
CPER engineering fixture. No private user address or newly supplied parcel was
sent to OpenAI.

## Results

| Gate | Result |
|---|---|
| Backend credential presence | PASS (`OPENAI_API_KEY` configured; value never logged) |
| TLS connectivity | PASS after verified `certifi` CA context fix |
| Minimal JSON completion | PASS (`provider_status: OK`) |
| Live intent parse | PASS with explicit UI authority; incomplete model shape repaired from deterministic baseline |
| Live Buyer Report | PASS after prose-only overlay repair |
| Deterministic Report Validator | PASS; `displayable: true`; zero violations |
| Model used by current default | `gpt-4o-mini` |

## Authority repair

The deterministic system now creates the complete report structure, Engine
decisions, evidence references, unknowns, and claim ledger. Live LLM output may
replace only approved section `summary` and `findings` prose. It cannot replace
the authority or evidence structures.

Live intent output is also fail-closed: an incomplete model object is repaired
from the deterministic intent baseline before explicit UI selections are
applied. The repair state remains visible in provenance.

## Privacy / activation state

Automatic live use was explicitly authorized by the product owner after this
gate. The ordinary UI now defers to the backend provider configuration;
`RANGEMATCH_LLM_PROVIDER=OPENAI` activates live narrative generation. A compact
version of parcel evidence is transmitted to OpenAI only for intent/report
prose. `?llm=fixture` remains an explicit offline override. The deterministic
fallback remains available when the provider or Validator fails.

## Regression status

- Full backend suite after TLS fix: 411 passed.
- Focused post-repair LLM / validator tests: 26 passed.
