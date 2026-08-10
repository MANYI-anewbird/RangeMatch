# RangeMatch Packaging and Delivery Strategy

> Status: `CANONICAL_V0_1`
> Date: 2026-08-08
> Principle: the one-parcel workflow now works; package it without duplicating scientific authority.

## Two delivery layers

### 1. Agent engineering package (runtime product)

The competition runtime is a local/cloud RangeMatch application — not a map website:

```text
planner → tools (Mireye + external adapters) → Land Profile
→ F01–F08 engine → Cow-Calf / Sheep profiles → explanation / diligence → API / UI
```

Current runtime shape:

```text
Python package + FastAPI service + frontend + env configuration
POST /api/investigations
GET  /api/investigations/{run_id}
```

### 2. Agent Skill / submission package (operator instructions)

Optional later package for Codex / Cursor / other agents:

```text
rangematch-agent/
├── SKILL.md
├── schemas/
├── references/
└── scripts/
```

This explains when to call RangeMatch, inputs, Goal-directed vs Discovery, how to run an investigation, how to explain results, and prohibited claims. It must **not** copy scientific rules into the prompt; rules stay in code and versioned registries.

## Repository stance

The buyer UI and one-parcel API are working. A broad monorepo migration is still unnecessary for the competition. Prefer a minimal deployment wrapper around the existing `src/rangematch` and `web` structure.

## Authorized build order

```text
unified output contract          ✅
executable schemas / projection  ✅
Planner DAG stub                 ✅
Mireye offline adapter           ✅
Planner executor (fixture)       ✅
One-parcel API prototype         ✅
Buyer UI + validated narrative       ✅
Report validator hardening           ✅
Address/coordinate parcel confirmation ✅
Live Mireye lookup/context             ✅
Public Diligence Agent                 ✅
Buyer decision report v2               ✅
→ deployment wrapper + final demo acceptance
→ Agent Skill / submission bundle
```

```yaml
package_now:
  python_package_cleanup: YES
  executable_schema: DONE
  planner_stub_dag: DONE
  mireye_adapters_offline: DONE
  planner_executor_fixture: DONE
  live_mireye: LIVE_VERIFIED_ON_CLEAN_NETWORK
  one_parcel_api: DONE
  api_ui: DONE
  llm_report_validator: HARDENED
  address_to_parcel_map: DONE
  public_diligence_search: DONE
  buyer_decision_report_v2: DONE
  docker: OPTIONAL_DEPLOYMENT_STEP
  agent_skill: READY_AFTER_FINAL_ACCEPTANCE
  submission_bundle: FINAL_STAGE
```

## Competition minimum delivery

Demo does not require Kubernetes. Minimum acceptable:

1. Startable backend
2. Accessible frontend
3. One real parcel workflow
4. Mireye key via environment variables only
5. F01–F08 deterministic engine
6. Visible Mireye + external tool calls
7. Sources and unknowns visible
8. README one-command run notes

Target later entrypoints:

```bash
cp .env.example .env   # set MIREYE_API_KEY
pip install -e .
rangematch serve
# or: docker compose up
```

## Light packaging prep (current)

Already present / keep improving in place:

- `pyproject.toml`, `src/rangematch/`, `.env.example`, `.gitignore`, `tests/`, `docs/`
- Executable unified output schema + projection
- CLI commands for evaluate / demo-closure / gates

Still deferred until workflow works:

- Full `apps/` split
- Docker Compose as primary path
- `agent-skill/` submission bundle
- Fancy packaging without orchestration

## One-line rule

> Package after the Agent runs: first orchestration and a real parcel workflow, then API/UI, then Skill/submission — never a pretty empty package.
