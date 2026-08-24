import { useState } from "react";
import type { RunTurn } from "../../api/client";
import { StatusBadge } from "../../components/StatusBadge";
import { turnActivityPresentation } from "./runHistoryPresentation";
import type { HistoryCaseOrigin } from "./ScientistHistoryUsed";
import {
  formatDuration,
  formatTimestamp,
  formatWaited,
  resultDisplay,
  isSandboxOperation,
  turnWaitMs,
} from "./runTurnHelpers";
import { RunTurnDetail } from "./RunTurnDetail";

export {
  caseLifecycleStatus,
  caseStatus,
  discoveryFields,
  formatDuration,
  formatTimestamp,
  formatWaited,
  isDiscoveryResult,
  isEvaluation,
  isScientistGeneration,
  isSandboxOperation,
  label,
  resultDisplay,
  tone,
  turnWaitMs,
} from "./runTurnHelpers";

function safeSlug(id: string): string {
  return id.replace(/[^a-zA-Z0-9_-]/g, "-");
}

export function RunTurnCard({
  turn,
  newest,
  flash,
  now,
  scientistIteration,
  caseOriginById,
  datasetCaseIds,
}: {
  turn: RunTurn;
  newest?: boolean;
  flash?: boolean;
  now: number;
  scientistIteration?: number;
  caseOriginById?: Map<string, HistoryCaseOrigin>;
  datasetCaseIds?: string[];
}) {
  const presentation = turnActivityPresentation(turn, scientistIteration);
  const isCurrent =
    presentation.waiting ||
    turn.status === "generating" ||
    (presentation.sandboxOperation &&
      !["completed", "failed", "cancelled", "closed"].includes(turn.status));
  const [operatorOpen, setOperatorOpen] = useState<boolean | null>(null);
  const isOpen = operatorOpen ?? Boolean(newest || isCurrent);
  const controlId = `history-activity-${safeSlug(turn.id)}`;
  const waitMs = turnWaitMs(turn, now);
  const evaluationResult = presentation.evaluation
    ? resultDisplay(turn.verdict, turn.objectiveStatus, turn.outcome)
    : null;

  return (
    <li
      className={[
        "turn history-activity",
        isOpen ? "is-open" : "",
        newest ? "newest-turn is-latest" : "",
        isCurrent ? "is-current" : "",
        presentation.waiting ? "turn-waiting" : "",
        presentation.scientistGeneration ? "turn-scientist" : "",
        presentation.evaluation ? "turn-evaluation" : "",
        presentation.evaluation
          ? `verdict-${evaluationResult?.className ?? "unknown"}`
          : "",
        presentation.discovery ? "turn-discovery" : "",
        turn.status === "failed" || turn.status === "blocked"
          ? evaluationResult?.className === "protected"
            ? ""
            : "turn-failed"
          : "",
        flash ? "turn-flash" : "",
        turn.status === "generating" ? "turn-generating" : "",
        isSandboxOperation(turn) ? "turn-sandbox-operation" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      data-turn-id={turn.id}
    >
      <h3 className="history-activity-heading" aria-label={presentation.title}>
        <button
          type="button"
          className="history-activity-toggle"
          aria-expanded={isOpen}
          aria-controls={controlId}
          onClick={() => setOperatorOpen(!isOpen)}
        >
          <span className="history-activity-primary">
            <span className="history-activity-title">{presentation.title}</span>
            <span className="history-activity-summary">
              {presentation.summary}
            </span>
          </span>
          <span className="history-activity-meta">
            {isCurrent || newest ? (
              <span className="history-activity-latest">
                {isCurrent ? "Current" : "Latest"}
              </span>
            ) : null}
            <StatusBadge
              label={presentation.status.label}
              tone={presentation.status.tone}
              pulse={isCurrent}
            />
            <time
              className="history-activity-time mono"
              dateTime={turn.occurredAt ?? undefined}
              title={turn.occurredAt ?? undefined}
            >
              {formatTimestamp(turn.occurredAt)}
            </time>
            {waitMs != null ? (
              <span className="history-activity-duration mono">
                {isCurrent ? formatDuration(waitMs) : formatWaited(waitMs)}
              </span>
            ) : null}
          </span>
        </button>
      </h3>
      {presentation.scientistGeneration && turn.status === "generating" ? (
        <div className="turn-working-progress" aria-hidden="true">
          <span />
        </div>
      ) : null}
      {isOpen ? (
        <div className="history-activity-body" id={controlId}>
          <RunTurnDetail
            turn={turn}
            scientistIteration={scientistIteration}
            caseOriginById={caseOriginById}
            datasetCaseIds={datasetCaseIds}
          />
        </div>
      ) : null}
    </li>
  );
}
