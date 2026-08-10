# One-Parcel Product Acceptance — 2026-08-08

## Status

`ENGINEERING_FLOW_PASSED / DEMO_POLISH_CONDITIONAL`

This acceptance used the running React UI and FastAPI service, not a direct
adapter script. The test followed the buyer flow from a coordinate lookup to a
validated report.

## Accepted path

```text
Coordinate 40.825,-104.7625
→ LIVE Mireye parcel lookup
→ one parcel candidate
→ explicit boundary confirmation
→ DISCOVERY mode
→ LIVE F01–F08 collection/derivation
→ Land Profile
→ deterministic Cow-Calf + Sheep Engine
→ Unified Output
→ validated buyer narrative
→ Evidence Details + Agent trace
```

## Results

- Parcel resolution: `PARCEL_CONFIRMED`
- Geometry hash remained bound through the investigation
- Investigation: `COMPLETED`
- F01–F08 trace stage: `SUCCEEDED`
- Cow-Calf: `HOLD`
- Sheep: `HOLD`
- Ranking permitted: `false`
- Buyer narrative: validator-passed display path
- Evidence Details showed F01 through F08 in canonical order
- Agent trace showed geometry, Mireye contexts, Factors, assembly, Engine,
  projection, and explanation binding
- No silent fixture substitution occurred
- Backend regression: `411 passed`
- Frontend regression: `21 passed`
- Frontend production build: passed

## Product wiring fixed during acceptance

The UI previously exposed a LIVE resolver button but did not send
`allow_network: true`, and Start Analysis always sent
`mireye_mode: BLOCKED_EXTERNAL`. The UI now:

- authorizes network access only after the buyer explicitly selects LIVE;
- sends LIVE parcel resolution with `allow_network: true`;
- sends the confirmed-parcel investigation with `mireye_mode: LIVE` and
  `allow_network: true`;
- keeps FIXTURE behavior explicit and separate.

The F03 trace tool was renamed from the misleading
`adapter.nhd_naip_water` to `adapter.nhd_water_candidates`. Runtime F03
performs NHD candidate discovery and creates an imagery-review queue; it does
not imply that a provenance-complete NAIP review has occurred.

## Remaining demo blockers / polish

1. **In-memory stores** — parcel resolutions and investigations disappear on
   restart. Add a small persistent store before deployment.
2. **Buyer report provider** — the UI defaults to the deterministic fixture
   provider for reproducible demos. Run and record a controlled OPENAI provider
   gate before claiming live LLM generation.
3. **Buyer-facing copy** — raw limitation identifiers and geometry hashes are
   too prominent above the report. Move them into Evidence Details.
4. **Executive summary specificity** — the current validated narrative is
   accurate but generic; a grounded LLM report should summarize the actual
   parcel facts and most material next checks without changing Engine labels.
5. **Known scientific limitations** — RAP coverage/applicability remains
   unresolved for this parcel; F03 has no field-verified water and no completed
   NAIP review. These are correct `NEEDS_VERIFICATION` outcomes, not software
   failures.

## Completed product slice

`ASYNC_INVESTIGATION_JOB_AND_PROGRESS — PASSED_FOR_SINGLE_PROCESS_DEMO`

The slice must preserve the existing Planner DAG and Factor contracts:

```text
POST investigation → return id immediately
→ background executor updates step states
→ UI polls /trace
→ report endpoints become available on completion
```

No F01–F08 science or Engine behavior changed. Acceptance details:
[`ASYNC_INVESTIGATION_JOB_ACCEPTANCE_2026-08-08.md`](./ASYNC_INVESTIGATION_JOB_ACCEPTANCE_2026-08-08.md).
