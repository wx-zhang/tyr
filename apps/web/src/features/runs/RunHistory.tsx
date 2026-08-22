import { useMemo, useState } from "react";
import type {
  CaseProgress,
  CollectorArtifact,
  ProgressItem,
  RunTurn,
} from "../../api/client";
import { groupRunHistory, type HistoryGroup } from "./runHistoryGroups";
import { RunHistoryGroup } from "./RunHistoryGroup";
import type { HistoryCaseOrigin } from "./ScientistHistoryUsed";

const terminalCaseStates = new Set([
  "completed",
  "failed",
  "cancelled",
  "blocked",
]);

export function RunHistory({
  turns,
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
}: {
  turns: RunTurn[];
  cases: CaseProgress[];
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
}) {
  const [operatorOverrides, setOperatorOverrides] = useState<
    Map<string, boolean>
  >(() => new Map());

  const groups = useMemo(
    () => groupRunHistory({ turns, cases, artifacts, phases }),
    [turns, cases, artifacts, phases],
  );

  const groupOpenStates = useMemo(() => {
    const states = new Map<string, boolean>();
    for (const g of groups) {
      if (operatorOverrides.has(g.id)) {
        states.set(g.id, operatorOverrides.get(g.id)!);
      } else {
        states.set(g.id, g.id === "discovery" ? !g.isTerminal : true);
      }
    }
    return states;
  }, [groups, operatorOverrides]);

  const caseOpenStates = useMemo(() => {
    const states = new Map<string, boolean>();
    for (const g of groups) {
      for (const c of g.cases) {
        if (operatorOverrides.has(c.caseId)) {
          states.set(c.caseId, operatorOverrides.get(c.caseId)!);
        } else {
          states.set(c.caseId, false);
        }
      }
    }
    return states;
  }, [groups, operatorOverrides]);

  const handleToggleGroup = (groupId: string) => {
    setOperatorOverrides((prev) => {
      const next = new Map(prev);
      const current = groupOpenStates.get(groupId) ?? false;
      next.set(groupId, !current);
      return next;
    });
  };

  const handleToggleCase = (caseId: string) => {
    setOperatorOverrides((prev) => {
      const next = new Map(prev);
      const current = caseOpenStates.get(caseId) ?? false;
      next.set(caseId, !current);
      return next;
    });
  };

  const totalLoaded = turns.length;
  const count = persistedTurnsCount ?? totalLoaded;
  const hasUpdates = turns.length > 0 || artifacts.length > 0;

  return (
    <section className="run-history" aria-labelledby="history-title">
      <div className="section-heading">
        <h2 id="history-title">Run history</h2>
        <span className="turn-count mono">{count} updates persisted</span>
      </div>

      {hasMoreTurns && onLoadMore ? (
        <button
          type="button"
          className="button button-secondary pagination-button"
          onClick={onLoadMore}
          disabled={isLoadingMore}
        >
          {isLoadingMore ? "Loading earlier updates…" : "Load earlier updates"}
        </button>
      ) : null}

      {isLoadingTurns ? (
        <p className="secondary">Loading persisted updates…</p>
      ) : null}

      {turnsError ? (
        <p className="callout callout-warning" role="alert">
          {turnsError.message}
        </p>
      ) : null}

      {!isLoadingTurns && !isLoadingArtifacts && !hasUpdates ? (
        <p className="empty-state run-empty">
          {isLive
            ? "Waiting for the first update…"
            : "No updates have been persisted yet."}
        </p>
      ) : null}

      {groups.map((group) => (
        <RunHistoryGroup
          key={group.id}
          group={group}
          runId={runId}
          isOpen={groupOpenStates.get(group.id) ?? false}
          onToggle={() => handleToggleGroup(group.id)}
          caseOpenStates={caseOpenStates}
          onToggleCase={handleToggleCase}
          now={now}
          flashIds={flashIds}
          caseOriginById={caseOriginById}
          datasetCaseIds={datasetCaseIds}
        />
      ))}
    </section>
  );
}
