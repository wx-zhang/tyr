import { StatusBadge } from "../../components/StatusBadge";
import { CollectorArtifactUpdate } from "./CollectorArtifacts";
import type { HistoryCaseEntry } from "./runHistoryGroups";
import { caseLatestSummary } from "./runHistoryPresentation";
import { caseLifecycleStatus, resultDisplay, RunTurnCard } from "./RunTurnCard";
import type { HistoryCaseOrigin } from "./ScientistHistoryUsed";

function safeSlug(id: string): string {
  return id.replace(/[^a-zA-Z0-9_-]/g, "-");
}

export function RunHistoryCase({
  entry,
  runId,
  isOpen,
  onToggle,
  now,
  flashIds,
  scientistIteration,
  caseOriginById,
  datasetCaseIds,
}: {
  entry: HistoryCaseEntry;
  runId: string;
  isOpen: boolean;
  onToggle: () => void;
  now: number;
  flashIds?: Set<string>;
  scientistIteration?: number;
  caseOriginById?: Map<string, HistoryCaseOrigin>;
  datasetCaseIds?: string[];
}) {
  const isBusy =
    ["active", "assessing"].includes(entry.progress?.state ?? "") ||
    entry.updates.some(
      (update) =>
        update.kind === "turn" &&
        ["waiting_for_tyr", "generating"].includes(update.turn.status),
    );
  const status = entry.progress
    ? caseLifecycleStatus(entry.progress)
    : { label: "—", tone: "neutral" as const };
  const verdictTurn = [...entry.updates]
    .reverse()
    .flatMap((update) =>
      update.kind === "turn" && update.turn.verdict ? [update.turn] : [],
    )[0];
  const verdict = entry.progress?.verdict ?? verdictTurn?.verdict;
  const result = verdict
    ? resultDisplay(
        verdict,
        entry.progress?.objectiveStatus ?? verdictTurn?.objectiveStatus,
        entry.progress?.outcome ?? verdictTurn?.outcome,
      )
    : null;
  const controlId = `history-scenario-execution-${safeSlug(entry.scenarioExecutionId ?? entry.caseId)}`;
  const updateLabel = `${entry.updates.length} ${entry.updates.length === 1 ? "update" : "updates"}`;
  const executionLabel = entry.progress
    ? `Scenario Execution ${String(entry.progress.order).padStart(2, "0")}`
    : "Scenario Execution";
  const scenarioId = entry.scenarioId ?? entry.progress?.scenarioId ?? "—";
  const scenarioExecutionId = entry.scenarioExecutionId ?? entry.caseId;
  return (
    <li
      className={`history-case${result ? ` history-case-outcome-${result.className}` : ""}${isOpen ? " is-open" : ""}`}
    >
      <h4 className="history-case-heading">
        <button
          type="button"
          className="history-toggle history-case-toggle"
          aria-expanded={isOpen}
          aria-controls={controlId}
          onClick={onToggle}
        >
          <span className="history-case-summary">
            <span className="history-case-number">{executionLabel}</span>
            <span className="history-case-description">
              {caseLatestSummary(entry)}
            </span>
            <span className="history-case-identifiers">
              <span className="history-case-id">
                Scenario <span className="mono">{scenarioId}</span>
              </span>
              <span className="history-case-id">
                Execution <span className="mono">{scenarioExecutionId}</span>
              </span>
            </span>
          </span>
          <span className="history-case-meta">
            <span className="history-case-status">
              <StatusBadge label={status.label} tone={status.tone} />
            </span>
            {result ? (
              <span className="history-case-result">
                <StatusBadge label={result.label} tone={result.tone} />
              </span>
            ) : null}
            {isBusy ? (
              <span className="tyr-waiting-spinner" aria-hidden="true" />
            ) : null}
            <span className="history-toggle-count">{updateLabel}</span>
          </span>
        </button>
      </h4>
      {isOpen ? (
        <div className="history-case-body" id={controlId}>
          <p className="history-case-body-label">Scenario Execution activity</p>
          {entry.updates.length > 0 ? (
            <ol
              className="turn-list"
              aria-label={`Updates for Scenario Execution ${scenarioExecutionId}`}
            >
              {entry.updates.map((update, index) =>
                update.kind === "artifact" ? (
                  <CollectorArtifactUpdate
                    key={`collector-${update.artifact.scenarioExecutionId ?? update.artifact.caseId}-${update.timestamp}`}
                    runId={runId}
                    artifact={update.artifact}
                  />
                ) : (
                  <RunTurnCard
                    key={update.turn.id}
                    turn={update.turn}
                    newest={index === entry.updates.length - 1}
                    flash={flashIds?.has(update.turn.id)}
                    now={now}
                    scientistIteration={scientistIteration}
                    caseOriginById={caseOriginById}
                    datasetCaseIds={datasetCaseIds}
                  />
                ),
              )}
            </ol>
          ) : (
            <p className="history-case-empty">
              No updates recorded for this Scenario Execution yet.
            </p>
          )}
        </div>
      ) : null}
    </li>
  );
}
