import { StatusBadge } from "../../components/StatusBadge";
import type { RunConnectionState } from "../../api/useRunEvents";
import { label, tone, formatTimestamp } from "./RunTurnCard";
import {
  connectionDetail,
  connectionLabel,
  formatRefreshRate,
  formatRelative,
  REFRESH_RATES_MS,
  type RefreshRateMs,
} from "./runHelpers";

export function RunHeader({
  runId,
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
  return (
    <header className="run-header">
      <div className="run-header-main">
        <p className="eyebrow">Experiment details</p>
        <div className="run-title">
          <h1>Experiment <span className="mono">{runId}</span></h1>
          <StatusBadge label={label(run?.state)} tone={tone(run?.state)} pulse={isLive} />
          <span className={`run-mode${run?.actionMode === "approval_required" ? " run-mode-actions" : ""}`}>
            {label(run?.actionMode ?? "read_only")}
          </span>
          {run?.executionMode ? <span className="run-mode run-execution-mode">{label(run.executionMode)}</span> : null}
        </div>
        <dl className="run-facts">
          <div><dt>Task</dt><dd className="mono">{run?.task ?? "Pending"}</dd></div>
          <div><dt>Started</dt><dd title={run?.startedAt ?? undefined}>{formatTimestamp(run?.startedAt)}</dd></div>
          <div><dt>Latest update</dt><dd title={run?.latestUpdateAt ?? undefined}>{isLive ? formatRelative(run?.latestUpdateAt, now) : formatTimestamp(run?.latestUpdateAt)}</dd></div>
          {effectiveResearchIterations > 0 ? <div><dt>Research Iterations</dt><dd className="mono tabular">{effectiveResearchIterations}</dd></div> : null}
        </dl>
      </div>
      <div className="run-header-tools">
        <div className="refresh-rate" role="radiogroup" aria-label="Refresh rate" title="How often to refresh Experiment data">
          {REFRESH_RATES_MS.map((ms) => <button key={ms} type="button" role="radio" className={refreshMs === ms ? "is-selected" : undefined} aria-checked={refreshMs === ms} onClick={() => onSelectRefreshMs(ms)}>{formatRefreshRate(ms)}</button>)}
        </div>
        <div className="run-header-meta">
          <p className={`run-connection connection-${connectionState}`} role="status" aria-live="polite" title={connectionDetail(connectionState)}>
            <span className="connection-dot" aria-hidden="true" /><span className="connection-label">{connectionLabel(connectionState)}</span>
          </p>
          {isLive ? <button type="button" className="run-cancel" disabled={cancelling} onClick={onRequestCancel}>{cancelling ? "Cancelling…" : "Cancel Experiment"}</button> : null}
        </div>
      </div>
    </header>
  );
}
