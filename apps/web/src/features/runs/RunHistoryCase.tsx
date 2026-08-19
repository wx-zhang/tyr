import type { CollectorArtifact } from "../../api/client";
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
      (u) =>
        u.kind === "turn" &&
        (u.turn.status === "waiting_for_tyr" || u.turn.status === "generating"),
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

  const controlId = `history-case-${safeSlug(entry.caseId)}`;
  const updateLabel = `${entry.updates.length} ${entry.updates.length === 1 ? "update" : "updates"}`;
  const caseLabel = entry.progress
    ? `Case ${String(entry.progress.order).padStart(2, "0")}`
    : "Generated case";

  return (
    <li className={`history-case${isOpen ? " is-open" : ""}`}>
      <h4 className="history-case-heading">
        <button
          type="button"
          className="history-toggle history-case-toggle"
          aria-expanded={isOpen}
          aria-controls={controlId}
          onClick={onToggle}
        >
          <span className="history-case-number">{caseLabel}</span>
          <span className="history-case-summary">
            <span className="history-case-id mono">{entry.caseId}</span>
            <span className="history-case-description">
              {caseLatestSummary(entry)}
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
          <p className="history-case-body-label">Case activity</p>
          {entry.updates.length > 0 ? (
            <ol
              className="turn-list"
              aria-label={`Updates for ${entry.caseId}`}
            >
              {entry.updates.map((update, index) =>
                update.kind === "artifact" ? (
                  <CollectorArtifactUpdate
                    key={`collector-${(update.artifact as CollectorArtifact).caseId}-${update.timestamp}`}
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
              No updates recorded for this case yet.
            </p>
          )}
        </div>
      ) : null}
    </li>
  );
}
