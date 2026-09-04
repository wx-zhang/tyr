import type { CollectorArtifact, TargetOrigin } from "../../api/client";
import { StatusBadge } from "../../components/StatusBadge";
import { CollectorArtifactUpdate } from "./CollectorArtifacts";
import { RunHistoryCase } from "./RunHistoryCase";
import type { HistoryGroup } from "./runHistoryGroups";
import { RunTurnCard } from "./RunTurnCard";
import type { HistoryCaseOrigin } from "./ScientistHistoryUsed";

function groupStatus(state: string) {
  if (state === "active")
    return { label: "In progress", tone: "info" as const };
  if (state === "queued") return { label: "Queued", tone: "neutral" as const };
  if (state === "pending")
    return { label: "Not started", tone: "neutral" as const };
  if (state === "completed")
    return { label: "Completed", tone: "success" as const };
  if (state === "failed") return { label: "Failed", tone: "danger" as const };
  if (state === "blocked")
    return { label: "Blocked", tone: "warning" as const };
  if (state === "cancelled")
    return { label: "Cancelled", tone: "neutral" as const };
  return { label: "Status unavailable", tone: "neutral" as const };
}
function targetOriginLabel(origin: TargetOrigin): string {
  if (origin === "provided") return "Provided target";
  if (origin === "fallback-live") return "Provided target · fell back to discovery";
  return "Discovered live";
}

export function RunHistoryGroup({
  group,
  runId,
  isOpen,
  onToggle,
  caseOpenStates,
  onToggleCase,
  now,
  flashIds,
  caseOriginById,
  datasetCaseIds,
  targetOrigin,
}: {
  group: HistoryGroup;
  runId: string;
  isOpen: boolean;
  onToggle: () => void;
  caseOpenStates: Map<string, boolean>;
  onToggleCase: (caseId: string) => void;
  now: number;
  flashIds?: Set<string>;
  caseOriginById?: Map<string, HistoryCaseOrigin>;
  datasetCaseIds?: string[];
  targetOrigin?: TargetOrigin;
}) {
  const controlId = `history-${group.id}`;
  const showTargetOrigin = group.id === "discovery" && targetOrigin !== undefined;
  const status = groupStatus(group.state);
  const iterMatch = group.id.match(/^(?:iteration|research-iteration)-(\d+)$/);
  const researchIteration = iterMatch ? Number(iterMatch[1]) : undefined;

  const completedCases = group.cases.filter(
    (entry) =>
      entry.progress?.state &&
      ["completed", "failed", "cancelled", "blocked"].includes(
        entry.progress.state,
      ),
  ).length;
  const countDisplay =
    group.id === "cases" || group.id === "scenario-executions"
      ? `${completedCases} of ${group.cases.length} Scenario Executions complete`
      : group.updates.length > 0
        ? `${group.updates.length} ${group.updates.length === 1 ? "update" : "updates"}`
        : group.cases.length > 0
          ? `${group.cases.length} ${group.cases.length === 1 ? "Scenario Execution" : "Scenario Executions"}`
          : null;

  return (
    <div
      className={`history-group history-group-${group.id}${isOpen ? " is-open" : ""}`}
    >
      <h3 className="history-group-heading">
        <button
          type="button"
          className="history-toggle"
          aria-expanded={isOpen}
          aria-controls={controlId}
          onClick={onToggle}
        >
          <span className="history-toggle-label">{group.label}</span>
          <span className="history-toggle-status">
            <StatusBadge
              label={status.label}
              tone={status.tone}
              pulse={group.isBusy}
            />
          </span>
          {showTargetOrigin ? (
            <span className="history-toggle-origin">
              <StatusBadge label={targetOriginLabel(targetOrigin!)} tone="neutral" />
            </span>
          ) : null}
          {countDisplay !== null ? (
            <span className="history-toggle-count">{countDisplay}</span>
          ) : null}
        </button>
      </h3>
      {(["cases", "scenario-executions"] as string[]).includes(group.id) && group.cases.length > 0 ? (
        <progress
          className="history-case-progress"
          aria-label="Scenario Execution progress"
          aria-valuenow={completedCases}
          aria-valuemax={group.cases.length}
          value={completedCases}
          max={group.cases.length}
        />
      ) : null}
      {isOpen ? (
        <div className="history-group-body" id={controlId}>
          {group.updates.length > 0 ? (
            <ol
              className="turn-list"
              aria-label={
                group.id === "discovery"
                  ? "Discovery updates"
                  : group.id === "other"
                    ? "Other updates"
                    : `${group.label} updates`
              }
            >
              {group.updates.map((update, index) =>
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
                    newest={index === group.updates.length - 1}
                    flash={flashIds?.has(update.turn.id)}
                    now={now}
                    scientistIteration={researchIteration}
                    caseOriginById={caseOriginById}
                    datasetCaseIds={datasetCaseIds}
                  />
                ),
              )}
            </ol>
          ) : null}
          {group.cases.length > 0 ? (
            <ul className="history-case-list" aria-label={group.label}>
              {group.cases.map((caseEntry) => (
                <RunHistoryCase
                  key={caseEntry.caseId}
                  entry={caseEntry}
                  runId={runId}
                  isOpen={caseOpenStates.get(caseEntry.caseId) ?? false}
                  onToggle={() => onToggleCase(caseEntry.caseId)}
                  now={now}
                  flashIds={flashIds}
                  scientistIteration={researchIteration}
                  caseOriginById={caseOriginById}
                  datasetCaseIds={datasetCaseIds}
                />
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
