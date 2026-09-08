import { Link } from "react-router-dom";
import { StatusBadge } from "../../components/StatusBadge";
import type { RunConnectionState } from "../../api/useRunEvents";
import { label, tone, formatTimestamp } from "./RunTurnCard";
import {
  connectionDetail,
  connectionLabel,
  formatRefreshRate,
  formatRelative,
  isRefreshRateMs,
  REFRESH_RATES_MS,
  type RefreshRateMs,
} from "./runHelpers";

export function RunHeader({
  runId,
  name,
  run,
  now,
  isLive,
  researchIterations,
  refreshMs,
  onSelectRefreshMs,
  connectionState,
  cancelling,
  onRequestCancel,
}: {
  runId: string;
  name?: string | null;
  run?: {
    state?: string;
    actionMode?: string;
    executionMode?: string;
    task?: string;
    startedAt?: string | null;
    latestUpdateAt?: string | null;
  };
  now: number;
  isLive: boolean;
  researchIterations?: number;
  refreshMs: RefreshRateMs;
  onSelectRefreshMs: (ms: RefreshRateMs) => void;
  connectionState: RunConnectionState;
  cancelling: boolean;
  onRequestCancel: () => void;
}) {
  const effectiveResearchIterations = researchIterations ?? 0;
  const taskParts = run?.task?.split("/").filter(Boolean) ?? [];
  const title = name?.trim() || taskParts[taskParts.length - 1] || "Experiment";
  const updatesLabel =
    connectionState === "connected"
      ? "Updates connected"
      : `Updates ${connectionLabel(connectionState).toLowerCase()}`;
  return (
    <header className="run-header">
      <div className="run-header-main">
        <Link className="run-review-back" to="/runs">
          Back to Experiments
        </Link>
        <div className="run-title">
          <h1>{title}</h1>
          <StatusBadge
            label={label(run?.state)}
            tone={tone(run?.state)}
            pulse={isLive}
          />
          <span
            className={`run-mode${run?.actionMode === "approval_required" ? " run-mode-actions" : ""}`}
          >
            {run?.actionMode ? label(run.actionMode) : "Mode unavailable"}
          </span>
          {run?.executionMode ? (
            <span className="run-mode run-execution-mode">
              {label(run.executionMode)}
            </span>
          ) : null}
        </div>
        <p className="run-review-id">
          <span>Experiment ID</span> <span className="mono">{runId}</span>
        </p>
        <dl className="run-facts">
          <div>
            <dt>Task</dt>
            <dd className="mono">{run?.task ?? "Pending"}</dd>
          </div>
          <div>
            <dt>Started</dt>
            <dd className="mono" title={run?.startedAt ?? undefined}>
              {formatTimestamp(run?.startedAt)}
            </dd>
          </div>
          <div>
            <dt>Latest update</dt>
            <dd className="mono" title={run?.latestUpdateAt ?? undefined}>
              {isLive
                ? formatRelative(run?.latestUpdateAt, now)
                : formatTimestamp(run?.latestUpdateAt)}
            </dd>
          </div>
          {effectiveResearchIterations > 0 ? (
            <div>
              <dt>Research Iterations</dt>
              <dd className="mono tabular">{effectiveResearchIterations}</dd>
            </div>
          ) : null}
        </dl>
      </div>
      <div className="run-header-tools">
        <label className="field-group run-review-refresh">
          <span className="field-label">Refresh rate</span>
          <select
            value={refreshMs}
            title="How often to refresh Experiment data"
            onChange={(event) => {
              const ms = Number(event.currentTarget.value);
              if (isRefreshRateMs(ms)) onSelectRefreshMs(ms);
            }}
          >
            {REFRESH_RATES_MS.map((ms) => (
              <option key={ms} value={ms}>
                {formatRefreshRate(ms)}
              </option>
            ))}
          </select>
        </label>
        <div className="run-header-meta">
          <p
            className={`run-connection connection-${connectionState}`}
            role="status"
            aria-live="polite"
            title={connectionDetail(connectionState)}
          >
            <span className="connection-dot" aria-hidden="true" />
            <span className="connection-label">{updatesLabel}</span>
          </p>
          {isLive ? (
            <button
              type="button"
              className="run-cancel"
              disabled={cancelling}
              onClick={onRequestCancel}
            >
              {cancelling ? "Cancelling…" : "Cancel Experiment"}
            </button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
