import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
  cancelExperiment,
  fetchCollectorArtifacts,
  fetchTaskScenarios,
  fetchRun,
  fetchRunTurns,
  fetchRunVisualization,
  normalizeTargetOrigin,
  type RunTurn,
} from "../../api/client";
import { useRunEvents } from "../../api/useRunEvents";
import { LoadingStatus } from "../../components/LoadingStatus";
import { RunHeader } from "./RunHeader";
import { RunHistory } from "./RunHistory";
import { RunStagesPanel } from "./RunStagesPanel";
import { TyrNetworkMap } from "./TyrNetworkMap";
import {
  DEFAULT_REFRESH_MS,
  readStoredRefreshMs,
  REFRESH_STORAGE_KEY,
  terminalStates,
  type RefreshRateMs,
} from "./runHelpers";
import { useRunPageDerived } from "./useRunPageDerived";

function sameTurn(left: RunTurn | undefined, right: RunTurn): boolean {
  return Boolean(
    left &&
    left.status === right.status &&
    left.agentMessage === right.agentMessage &&
    left.tyrMessage === right.tyrMessage &&
    left.occurredAt === right.occurredAt &&
    left.repliedAt === right.repliedAt,
  );
}

export function RunPage() {
  const { id } = useParams();
  const runId = id ?? "unknown";
  const queryClient = useQueryClient();
  const [refreshMs, setRefreshMs] = useState<RefreshRateMs>(() =>
    readStoredRefreshMs(),
  );
  const visualization = useQuery({
    queryKey: ["run-visualization", runId],
    queryFn: () => fetchRunVisualization(runId),
    refetchInterval: (query) => {
      const state = query.state.data?.run?.state;
      if (state && terminalStates.has(state)) return false;
      return refreshMs;
    },
  });
  const runRecord = useQuery({
    queryKey: ["run", runId],
    queryFn: () => fetchRun(runId),
  });
  const taskId = visualization.data?.run?.task ?? runRecord.data?.task ?? null;
  const taskScenarios = useQuery({
    queryKey: ["task-scenarios", taskId],
    queryFn: () => fetchTaskScenarios(taskId!),
    enabled: Boolean(taskId),
  });
  const taskCases = taskScenarios;
  const turns = useQuery({
    queryKey: ["run-turns", runId],
    queryFn: () => fetchRunTurns(runId),
    refetchInterval: () => {
      const state = visualization.data?.run?.state;
      if (state && terminalStates.has(state)) return false;
      return refreshMs;
    },
  });
  const collectorArtifacts = useQuery({
    queryKey: ["collector-artifacts", runId],
    queryFn: () => fetchCollectorArtifacts(runId),
    refetchInterval: () => {
      const state = visualization.data?.run?.state;
      if (state && terminalStates.has(state)) return false;
      return refreshMs;
    },
  });
  const events = useRunEvents(runId);
  const [olderTurns, setOlderTurns] = useState<RunTurn[]>([]);
  const [visibleLatestTurns, setVisibleLatestTurns] = useState<RunTurn[]>([]);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [flashIds, setFlashIds] = useState<Set<string>>(() => new Set());
  const previousVisible = useRef<Map<string, RunTurn>>(new Map());

  const run = visualization.data?.run;
  const researchIterations =
    runRecord.data?.configuration?.researchIterations ?? 0;
  const latestTurns = turns.data?.items;
  const isLive = Boolean(run && !terminalStates.has(run.state));
  const waitingForTyr = Boolean(
    visibleLatestTurns.some(
      (turn) => turn.status === "waiting_for_tyr" && !turn.tyrMessage,
    ) ||
    latestTurns?.some(
      (turn) => turn.status === "waiting_for_tyr" && !turn.tyrMessage,
    ),
  );

  const { allTurns, datasetCaseIds, caseOriginById, agentWorking } =
    useRunPageDerived({
      turnsData: turns.data,
      olderTurns,
      visibleLatestTurns,
      datasetCasesData: taskCases.data,
      runRecordData: runRecord.data,
      isLive,
    });

  const selectRefreshMs = (next: RefreshRateMs) => {
    setRefreshMs(next);
    try {
      window.localStorage.setItem(REFRESH_STORAGE_KEY, String(next));
    } catch {
      /* ignore quota */
    }
  };

  const requestCancel = async () => {
    if (cancelling || !isLive) return;
    const confirmed = window.confirm(
      `Cancel Experiment ${runId}? The Experiment will stop. Existing evidence remains reviewable.`,
    );
    if (!confirmed) return;
    setCancelling(true);
    setCancelError(null);
    try {
      await cancelExperiment(runId);
      await queryClient.invalidateQueries({
        queryKey: ["run-visualization", runId],
      });
      await queryClient.invalidateQueries({ queryKey: ["run-turns", runId] });
    } catch (error) {
      setCancelError(
        error instanceof Error
          ? `Could not cancel Experiment: ${error.message}`
          : "Could not cancel Experiment",
      );
    } finally {
      setCancelling(false);
    }
  };

  useEffect(() => {
    setOlderTurns([]);
    setVisibleLatestTurns([]);
    setFlashIds(new Set());
    setCancelling(false);
    setCancelError(null);
    previousVisible.current = new Map();
  }, [runId]);

  useEffect(() => {
    if (latestTurns) setVisibleLatestTurns(latestTurns);
  }, [latestTurns]);

  useEffect(() => {
    if (!isLive && !waitingForTyr) return undefined;
    setNow(Date.now());
    const intervalMs = waitingForTyr ? Math.min(1000, refreshMs) : refreshMs;
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(timer);
  }, [isLive, waitingForTyr, refreshMs]);

  useEffect(() => {
    const previous = previousVisible.current;
    const next = new Map(visibleLatestTurns.map((turn) => [turn.id, turn]));
    const arrived = visibleLatestTurns
      .filter((turn) => !sameTurn(previous.get(turn.id), turn))
      .map((turn) => turn.id);
    previousVisible.current = next;
    if (!arrived.length || previous.size === 0) return;
    setFlashIds((current) => new Set([...current, ...arrived]));
    const timer = window.setTimeout(() => {
      setFlashIds((current) => {
        const nextFlash = new Set(current);
        for (const id of arrived) nextFlash.delete(id);
        return nextFlash;
      });
    }, 1200);
    return () => window.clearTimeout(timer);
  }, [visibleLatestTurns]);

  const loadOlder = async () => {
    const cursor = turns.data?.nextCursor;
    if (!cursor) return;
    setLoadingOlder(true);
    try {
      const page = await fetchRunTurns(runId, cursor);
      setOlderTurns((current) => [...page.items, ...current]);
    } finally {
      setLoadingOlder(false);
    }
  };

  return (
    <section
      className={`section-stack run-details run-review${isLive ? " run-live" : ""}`}
    >
      <RunHeader
        runId={runId}
        name={runRecord.data?.name}
        run={run}
        now={now}
        isLive={isLive}
        researchIterations={researchIterations}
        refreshMs={refreshMs}
        onSelectRefreshMs={selectRefreshMs}
        connectionState={events.connectionState}
        cancelling={cancelling}
        onRequestCancel={() => void requestCancel()}
      />

      {visualization.isLoading || runRecord.isLoading ? (
        <LoadingStatus label="Loading Experiment summary…" />
      ) : null}
      {cancelError ? (
        <p className="callout callout-warning" role="alert">
          {cancelError}
        </p>
      ) : null}
      {visualization.error ? (
        <p className="callout callout-warning" role="alert">
          {visualization.error.message}
        </p>
      ) : null}
      <nav className="run-review-nav" aria-label="Experiment sections">
        <a href="#review-results">Results &amp; activity</a>
        <a href="#review-lifecycle">Lifecycle</a>
        <a href="#review-network">Tyr network</a>
      </nav>

      <div id="review-results" className="run-review-section">
        <RunHistory
          turns={allTurns}
          scenarioExecutions={
            visualization.data?.scenarioExecutions ??
            visualization.data?.cases ??
            []
          }
          phases={visualization.data?.phases}
          artifacts={
            Array.isArray(collectorArtifacts.data)
              ? collectorArtifacts.data
              : []
          }
          runId={runId}
          isLive={isLive}
          persistedTurnsCount={turns.data?.latestSequence}
          hasMoreTurns={Boolean(turns.data?.nextCursor)}
          isLoadingTurns={turns.isLoading}
          isLoadingMore={loadingOlder}
          isLoadingArtifacts={collectorArtifacts.isLoading}
          turnsError={turns.error}
          artifactsError={collectorArtifacts.error}
          onRetryArtifacts={() => void collectorArtifacts.refetch()}
          onLoadMore={loadOlder}
          now={now}
          flashIds={flashIds}
          caseOriginById={caseOriginById}
          targetOrigin={normalizeTargetOrigin(
            visualization.data?.discoveryResult?.targetOrigin,
          )}
        />
      </div>
      <div id="review-lifecycle" className="run-review-section">
        <RunStagesPanel
          phases={visualization.data?.phases}
          run={run}
          isLive={isLive}
          waitingForTyr={waitingForTyr}
          agentWorking={agentWorking}
          isLoading={visualization.isLoading}
        />
      </div>

      <div id="review-network" className="run-review-section">
        <TyrNetworkMap runId={runId} isLive={isLive} refreshMs={refreshMs} />
      </div>
    </section>
  );
}
