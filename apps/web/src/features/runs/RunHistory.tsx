import { useMemo, useState } from "react";
import type { CaseProgress, CollectorArtifact, ProgressItem, RunTurn, TargetOrigin } from "../../api/client";
import { groupRunHistory, type HistoryGroup } from "./runHistoryGroups";
import { RunHistoryGroup } from "./RunHistoryGroup";
import type { HistoryCaseOrigin } from "./ScientistHistoryUsed";

export function RunHistory({
  turns,
  scenarioExecutions,
  cases,
  phases,
  artifacts,
  runId,
  isLive,
  persistedTurnsCount,
  hasMoreTurns,
  isLoadingTurns,
  isLoadingMore,
  isLoadingArtifacts,
  turnsError,
  onLoadMore,
  now,
  flashIds,
  caseOriginById,
  datasetCaseIds,
  targetOrigin,
}: {
  turns: RunTurn[];
  scenarioExecutions?: CaseProgress[];
  cases?: CaseProgress[];
  phases?: ProgressItem[];
  artifacts: CollectorArtifact[];
  runId: string;
  isLive: boolean;
  persistedTurnsCount?: number;
  hasMoreTurns?: boolean;
  isLoadingTurns?: boolean;
  isLoadingMore?: boolean;
  isLoadingArtifacts?: boolean;
  turnsError?: Error | null;
  onLoadMore?: () => Promise<void>;
  now: number;
  flashIds?: Set<string>;
  caseOriginById?: Map<string, HistoryCaseOrigin>;
  datasetCaseIds?: string[];
  targetOrigin?: TargetOrigin;
}) {
  const [operatorOverrides, setOperatorOverrides] = useState<Map<string, boolean>>(() => new Map());
  const executions = scenarioExecutions ?? cases ?? [];
  const groups = useMemo(
    () => groupRunHistory({ turns, cases: executions, artifacts, phases }),
    [turns, executions, artifacts, phases],
  );
  const groupOpenStates = useMemo(() => {
    const states = new Map<string, boolean>();
    for (const group of groups) {
      states.set(group.id, operatorOverrides.has(group.id) ? operatorOverrides.get(group.id)! : group.id === "discovery" ? !group.isTerminal : true);
    }
    return states;
  }, [groups, operatorOverrides]);
  const executionOpenStates = useMemo(() => {
    const states = new Map<string, boolean>();
    for (const group of groups) {
      for (const execution of group.cases) {
        states.set(execution.caseId, operatorOverrides.has(execution.caseId) ? operatorOverrides.get(execution.caseId)! : false);
      }
    }
    return states;
  }, [groups, operatorOverrides]);
  const handleToggleGroup = (groupId: string) => {
    setOperatorOverrides((previous) => {
      const next = new Map(previous);
      next.set(groupId, !(groupOpenStates.get(groupId) ?? false));
      return next;
    });
  };
  const handleToggleExecution = (executionId: string) => {
    setOperatorOverrides((previous) => {
      const next = new Map(previous);
      next.set(executionId, !(executionOpenStates.get(executionId) ?? false));
      return next;
    });
  };
  const count = persistedTurnsCount ?? turns.length;
  const hasUpdates = turns.length > 0 || artifacts.length > 0;
  return (
    <section className="run-history" aria-labelledby="history-title">
      <div className="section-heading"><h2 id="history-title">Experiment history</h2><span className="turn-count mono">{count} updates persisted</span></div>
      {hasMoreTurns && onLoadMore ? <button type="button" className="button button-secondary pagination-button" onClick={onLoadMore} disabled={isLoadingMore}>{isLoadingMore ? "Loading earlier updates…" : "Load earlier updates"}</button> : null}
      {isLoadingTurns ? <p className="secondary">Loading persisted updates…</p> : null}
      {turnsError ? <p className="callout callout-warning" role="alert">{turnsError.message}</p> : null}
      {!isLoadingTurns && !isLoadingArtifacts && !hasUpdates ? <p className="empty-state run-empty">{isLive ? "Waiting for the first update…" : "No updates have been persisted yet."}</p> : null}
{groups.map((group: HistoryGroup) => <RunHistoryGroup key={group.id} group={group} runId={runId} isOpen={groupOpenStates.get(group.id) ?? false} onToggle={() => handleToggleGroup(group.id)} caseOpenStates={executionOpenStates} onToggleCase={handleToggleExecution} now={now} flashIds={flashIds} caseOriginById={caseOriginById} datasetCaseIds={datasetCaseIds} targetOrigin={targetOrigin} />)}
    </section>
  );
}
