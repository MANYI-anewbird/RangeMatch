# Async Investigation Job and Progress Acceptance — 2026-08-08

## Status

`PASSED_FOR_SINGLE_PROCESS_DEMO`

The one-parcel investigation now returns a job record immediately and exposes
real Planner/Executor state through the existing investigation and trace APIs.
The buyer UI polls those APIs and does not use a simulated time-based progress
sequence.

## Accepted lifecycle

```text
POST /v1/investigations
→ QUEUED response with no Unified Output
→ atomic single-flight claim
→ RUNNING with partial step trace updates
→ COMPLETED | PARTIAL | FAILED
→ deterministic report and validated buyer-report path become available
```

## UI behavior

- Shows a progress bar derived from terminal Planner step counts.
- Shows the active Agent and a buyer-readable sentence describing its work.
- Preserves parallel Factor steps and real source failures from `/trace`.
- Keeps raw tool IDs behind a `Technical steps` disclosure.
- Displays external-source failure honestly and does not convert it to success.
- Loads the deterministic report and Buyer Report only after a terminal state.
- Spinner and progress transitions respect `prefers-reduced-motion`.
- SafeStructure-inspired product polish is complete: a high-focus analysis
  surface, buyer-readable active Agent card, progress hierarchy, and explicit
  safeguards are implemented without copying the reference brand.
- Visual QA: `design-qa.md` (`final result: passed`).

## Verification

- Backend full suite: **411 passed**.
- Frontend suite: **21 passed**.
- Frontend production build: **passed**.
- Local HTTP replay acceptance:
  - create response: `QUEUED`;
  - terminal response: `PARTIAL` because Mireye was intentionally
    `BLOCKED_EXTERNAL`;
  - canonical F01–F08, Engine, Unified Output, and explanation steps completed;
  - report endpoint returned HTTP `200` after terminal completion.
- The replay completed in roughly 64 ms, so `RUNNING` is normally too brief for
  a human to see on this fixture; executable tests cover the observable
  `QUEUED` and `RUNNING` polling states.

## Preserved authority boundaries

- No F01–F08 science, thresholds, ranking rules, or Engine labels changed.
- Progress is presentation only and cannot mutate the Land Profile,
  MatchResult, or Unified Output.
- Factor-local and external failures remain visible and fail closed.
- Report generation remains bound to the deterministic MatchResult.

## Deployment limitations

This is a demo-grade async implementation, not a durable distributed queue:

- records and jobs are process-local and disappear on restart;
- multiple API workers do not share job state;
- FastAPI background tasks do not provide crash recovery or retries after
  process loss;
- a production deployment needs a shared persistent store and job queue;
- the frontend build succeeds but still reports a large JavaScript chunk
  warning, so route/vendor code splitting is a later performance task.
