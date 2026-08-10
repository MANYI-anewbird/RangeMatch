import type { Trace, TraceStep } from "../api/client";
import { STAGE_MAP } from "../api/client";

const TERMINAL_STEP_STATUSES = new Set([
  "SUCCEEDED",
  "SKIPPED_REUSE",
  "PARTIAL",
  "FAILED",
  "BLOCKED_EXTERNAL",
  "BLOCKED_DEPENDENCY",
]);

function stageStatus(steps: TraceStep[]): string {
  if (!steps.length) return "PENDING";
  if (steps.some((s) => s.status === "RUNNING")) return "RUNNING";
  if (steps.some((s) => s.status === "BLOCKED_EXTERNAL")) return "BLOCKED_EXTERNAL";
  if (steps.some((s) => s.status === "FAILED" || s.status === "BLOCKED_DEPENDENCY"))
    return "FAILED";
  if (steps.some((s) => s.status === "PARTIAL")) return "PARTIAL";
  if (steps.every((s) => s.status === "SUCCEEDED" || s.status === "SKIPPED_REUSE"))
    return "SUCCEEDED";
  return "PENDING";
}

function statusLabel(status: string): string {
  if (status === "RUNNING") return "Working now";
  if (status === "SUCCEEDED") return "Complete";
  if (status === "PARTIAL") return "Complete with limits";
  if (status === "BLOCKED_EXTERNAL") return "External source unavailable";
  if (status === "FAILED") return "Needs attention";
  return "Waiting";
}

export function ProgressStages({ trace }: { trace: Trace | null }) {
  const steps = trace?.steps || [];
  const total = steps.length;
  const completed = steps.filter((step) => TERMINAL_STEP_STATUSES.has(step.status)).length;
  const progress = total ? Math.round((completed / total) * 100) : 0;
  const stages = STAGE_MAP.map((stage) => {
    const matched = steps.filter(stage.match);
    return { ...stage, matched, status: stageStatus(matched) };
  });
  const activeStage =
    stages.find((stage) => stage.status === "RUNNING") ||
    stages.find((stage) => stage.status === "PENDING") ||
    stages[stages.length - 1];

  return (
    <div className="agent-progress">
      <section className="agent-live-card" aria-live="polite">
        <div className="agent-orbit" data-active={activeStage?.status === "RUNNING"}>
          <span>{activeStage?.status === "RUNNING" ? <span className="agent-spinner" /> : progress}</span>
        </div>
        <div>
          <span className="agent-kicker">
            {activeStage?.status === "RUNNING" ? "Working now" : "Up next"}
          </span>
          <h2>{activeStage?.agent || "Preparing the investigation"}</h2>
          <p>{activeStage?.description || "Building the evidence plan for this parcel."}</p>
        </div>
      </section>

      <div className="agent-progress-summary">
        <div>
          <span className="agent-kicker">Investigation progress</span>
          <strong>{progress}% complete</strong>
        </div>
        <span className="agent-progress-count">{completed} of {total || "—"} checks</span>
      </div>
      <div
        className="agent-progress-track"
        role="progressbar"
        aria-label="Investigation progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress}
      >
        <span style={{ width: `${progress}%` }} />
      </div>

      <ol className="stage-list" aria-label="Investigation stages">
        {stages.map((stage, stageIndex) => {
          const { matched, status } = stage;
          const failures = matched
            .map((s) => s.failure)
            .filter(Boolean) as Record<string, unknown>[];
          return (
            <li key={stage.id} className="stage-item agent-stage" data-status={status}>
              <span className="agent-stage-marker" aria-hidden="true">
                {status === "RUNNING" ? <span className="agent-spinner" /> : null}
                {status === "SUCCEEDED" || status === "PARTIAL" ? "✓" : null}
                {status === "PENDING" ? String(stageIndex + 1) : null}
                {status === "FAILED" || status === "BLOCKED_EXTERNAL" ? "!" : null}
              </span>
              <div className="agent-stage-copy">
                <div className="agent-stage-heading">
                  <strong>{stage.agent}</strong>
                  <span className="agent-status">{statusLabel(status)}</span>
                </div>
                <p>{stage.description}</p>
                {matched.length > 0 && (
                  <details className="agent-technical-detail">
                    <summary>{stage.label} · technical steps ({matched.length})</summary>
                    <p>
                      {matched
                        .map((s) => `${s.tool_id} (${s.action || "—"}) → ${s.status}`)
                        .join(" · ")}
                    </p>
                  </details>
                )}
                {status === "BLOCKED_EXTERNAL" && (
                  <p className="agent-stage-warning">
                    This source could not be reached. RangeMatch keeps it visible and does not
                    invent a successful result.
                  </p>
                )}
                {failures.length > 0 && (
                  <ul className="unknown-list agent-failures">
                    {failures.map((failure, index) => (
                      <li key={index}>
                        {String(failure.error_code || "failure")}: {String(failure.message || "")}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
