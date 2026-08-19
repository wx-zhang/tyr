import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
  cancelRun,
  fetchCollectorArtifacts,
  fetchTaskCases,
  fetchRun,
  fetchRunTurns,
  fetchRunVisualization,
  type CaseProgress,
  type CollectorArtifact,
  type RunTurn,
} from "../../api/client";
import { useRunEvents, type RunConnectionState } from "../../api/useRunEvents";
import { StatusBadge } from "../../components/StatusBadge";
import { CollectorArtifactUpdate } from "./CollectorArtifacts";
import { MarkdownMessage } from "./MarkdownMessage";
import {
  buildCaseOriginMap,
  resolveHistoryCases,
  ScientistHistoryUsed,
  type HistoryCaseOrigin,
} from "./ScientistHistoryUsed";
import { ScientistScenarioCard } from "./ScientistScenarioCard";
import { TyrNetworkMap } from "./TyrNetworkMap";

const terminalStates = new Set([
  "completed",
  "failed",
  "cancelled",
  "interrupted",
]);
const REFRESH_RATES_MS = [1000, 5000, 10_000, 30_000] as const;
const DEFAULT_REFRESH_MS = 30_000;
const REFRESH_STORAGE_KEY = "gamr-run-refresh-ms";

type RefreshRateMs = (typeof REFRESH_RATES_MS)[number];

function isRefreshRateMs(value: number): value is RefreshRateMs {
  return (REFRESH_RATES_MS as readonly number[]).includes(value);
}

function readStoredRefreshMs(): RefreshRateMs {
  try {
    const raw = window.localStorage.getItem(REFRESH_STORAGE_KEY);
    if (!raw) return DEFAULT_REFRESH_MS;
    const parsed = Number(raw);
    return isRefreshRateMs(parsed) ? parsed : DEFAULT_REFRESH_MS;
  } catch {
    return DEFAULT_REFRESH_MS;
  }
}

function formatRefreshRate(ms: RefreshRateMs): string {
  return `${ms / 1000}s`;
}

function label(value: string | null | undefined): string {
  if (!value) return "—";
  if (value === "read_only") return "Read-only";
  if (value === "approval_required") return "Actions Allowed";
  if (value === "scientist_only") return "Scientist only";
  if (value === "cases") return "Test cases";
  if (value === "waiting_for_tyr") return "Waiting for Tyr";
  if (value === "case") return "Executing evaluation";
  if (value === "scientist") return "Scientist";
  if (value === "generating") return "Generating";
  if (value === "ready") return "Ready";
  if (value === "skipped") return "Skipped";
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function tone(
  state: string | null | undefined,
): "info" | "success" | "warning" | "danger" | "neutral" {
  if (
    state === "completed" ||
    state === "ready" ||
    state === "protected" ||
    state === "pass" ||
    state === "passed"
  ) {
    return "success";
  }
  if (state === "failed" || state === "vulnerable" || state === "fail")
    return "danger";
  if (
    state === "waiting_for_approval" ||
    state === "generating" ||
    state === "inconclusive" ||
    state === "partial"
  ) {
    return "warning";
  }
  if (state === "waiting_for_tyr") return "info";
  if (
    state === "cancelled" ||
    state === "interrupted" ||
    state === "incomplete" ||
    state === "pending" ||
    state === "not_applicable" ||
    state === "not_attempted" ||
    state === "unknown"
  ) {
    return "neutral";
  }
  return "info";
}

type ResultDisplay = {
  label: string;
  tone: ReturnType<typeof tone>;
  className: string;
};

function resultDisplay(
  verdict: string | null | undefined,
  objectiveStatus: string | null | undefined,
  outcome: string | null | undefined,
): ResultDisplay {
  if (
    verdict === "protected" ||
    (verdict !== "vulnerable" && outcome === "failed")
  ) {
    return { label: "No breach", tone: "success", className: "protected" };
  }
  if (
    verdict === "vulnerable" ||
    (verdict === "inconclusive" && objectiveStatus === "partial")
  ) {
    return {
      label: `Vulnerability Exposed${objectiveStatus === "partial" ? " (partial)" : ""}`,
      tone: "danger",
      className: "vulnerable",
    };
  }
  return {
    label: label(verdict),
    tone: tone(verdict),
    className: verdict ?? "unknown",
  };
}

function caseStatus(item: CaseProgress): {
  label: string;
  tone: ReturnType<typeof tone>;
} {
  if (item.verdict)
    return resultDisplay(item.verdict, item.objectiveStatus, item.outcome);
  return { label: label(item.state), tone: tone(item.state) };
}

function currentPhaseLabel(
  run: { state?: string; currentPhase?: string | null } | undefined,
  phases: Array<{ id: string; label: string; state: string }> | undefined,
): string {
  if (run?.currentPhase) return label(run.currentPhase);
  const active = phases?.find((phase) => phase.state === "active");
  if (active) return active.label;
  if (run?.state && terminalStates.has(run.state)) {
    const lastDone = [...(phases ?? [])]
      .reverse()
      .find((phase) => phase.state === "completed");
    if (lastDone) return lastDone.label;
    return label(run.state);
  }
  return "—";
}

function isScientistGeneration(turn: RunTurn): boolean {
  return (
    turn.stage === "scientist" &&
    !turn.tyrMessage &&
    ["generating", "failed", "ready", "completed"].includes(turn.status)
  );
}

function isEvaluation(turn: RunTurn): boolean {
  return turn.updateType === "evaluation";
}

function isDiscoveryResult(turn: RunTurn): boolean {
  return turn.updateType === "discovery";
}

function discoveryFields(
  message: string,
): Array<{ name: string; value: string }> {
  return message
    .split("\n")
    .map((line) => {
      const separator = line.indexOf(":");
      if (separator <= 0) return null;
      const name = line.slice(0, separator).trim();
      const value = line.slice(separator + 1).trim();
      if (!name || !value) return null;
      return { name, value };
    })
    .filter((item): item is { name: string; value: string } => item !== null);
}

function connectionLabel(state: RunConnectionState): string {
  return {
    connecting: "Connecting",
    connected: "Live",
    reconnecting: "Reconnecting",
    stale: "Stale",
    disconnected: "Offline",
  }[state];
}

function connectionDetail(state: RunConnectionState): string {
  return {
    connecting: "Connecting to live updates",
    connected: "Connected to live updates",
    reconnecting: "Reconnecting to live updates",
    stale: "Live updates are stale",
    disconnected: "Disconnected from live updates",
  }[state];
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(date);
}

function formatRelative(value: string | null | undefined, now: number): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  const deltaSeconds = Math.round((date.valueOf() - now) / 1000);
  const absolute = Math.abs(deltaSeconds);
  if (absolute < 5) return "just now";
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  if (absolute < 60) return formatter.format(deltaSeconds, "second");
  if (absolute < 3600)
    return formatter.format(Math.round(deltaSeconds / 60), "minute");
  if (absolute < 86_400)
    return formatter.format(Math.round(deltaSeconds / 3600), "hour");
  return formatter.format(Math.round(deltaSeconds / 86_400), "day");
}

function elapsedMs(
  start: string | null | undefined,
  end: number,
): number | null {
  if (!start) return null;
  const date = new Date(start);
  if (Number.isNaN(date.valueOf())) return null;
  return Math.max(0, end - date.valueOf());
}

function formatDuration(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function formatWaited(ms: number): string {
  if (ms < 1000) return "Waited <1s";
  const totalSeconds = Math.round(ms / 1000);
  if (totalSeconds < 60) return `Waited ${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes < 60)
    return seconds ? `Waited ${minutes}m ${seconds}s` : `Waited ${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainMinutes = minutes % 60;
  return remainMinutes
    ? `Waited ${hours}h ${remainMinutes}m`
    : `Waited ${hours}h`;
}

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

function turnHasOpenWork(turn: RunTurn): boolean {
  if (turn.status === "waiting_for_tyr" && !turn.tyrMessage) return true;
  if (turn.status === "generating") return true;
  return false;
}

function stageStatusLabel(
  phaseState: string,
  waitingForTyr: boolean,
  agentWorking: boolean,
  isActive: boolean,
): string | null {
  if (isActive && waitingForTyr) return "Waiting for Tyr";
  if (isActive && agentWorking) return "Agent working";
  if (phaseState === "active") return "Active";
  if (phaseState === "failed") return "Failed";
  if (phaseState === "cancelled") return "Cancelled";
  if (phaseState === "interrupted") return "Interrupted";
  if (phaseState === "skipped") return "Off";
  return null;
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
  const taskId =
    visualization.data?.run?.task ?? runRecord.data?.task ?? null;
  const taskCases = useQuery({
    queryKey: ["task-cases", taskId],
    queryFn: () => fetchTaskCases(taskId!),
    enabled: Boolean(taskId),
  });
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
  const scientistIterations =
    runRecord.data?.configuration?.scientistIterations ?? 0;
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

  const selectRefreshMs = (next: RefreshRateMs) => {
    setRefreshMs(next);
    try {
      window.localStorage.setItem(REFRESH_STORAGE_KEY, String(next));
    } catch {
      /* ignore quota / private mode */
    }
  };

  const requestCancel = async () => {
    if (cancelling || !isLive) return;
    const confirmed = window.confirm(
      `Cancel run ${runId}? The run will stop. Existing evidence remains reviewable.`,
    );
    if (!confirmed) return;
    setCancelling(true);
    setCancelError(null);
    try {
      await cancelRun(runId);
      await queryClient.invalidateQueries({
        queryKey: ["run-visualization", runId],
      });
      await queryClient.invalidateQueries({ queryKey: ["run-turns", runId] });
    } catch (error) {
      setCancelError(
        error instanceof Error ? error.message : "Could not cancel run",
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

  const allTurns = useMemo(() => {
    const byId = new Map(
      [...olderTurns, ...visibleLatestTurns].map((turn) => [turn.id, turn]),
    );
    return [...byId.values()].sort(
      (left, right) => right.sequence - left.sequence,
    );
  }, [olderTurns, visibleLatestTurns]);
  const timelineEntries = useMemo(() => {
    const entries: Array<
      | { kind: "turn"; timestamp: number; turn: RunTurn }
      | { kind: "artifact"; timestamp: number; artifact: CollectorArtifact }
    > = allTurns.map((turn) => ({
      kind: "turn",
      timestamp: Date.parse(turn.occurredAt ?? "") || 0,
      turn,
    }));
    const artifacts = Array.isArray(collectorArtifacts.data)
      ? collectorArtifacts.data
      : [];
    for (const artifact of artifacts) {
      entries.push({
        kind: "artifact",
        timestamp: Date.parse(artifact.verifiedAt ?? "") || 0,
        artifact,
      });
    }
    return entries.sort((left, right) => right.timestamp - left.timestamp);
  }, [allTurns, collectorArtifacts.data]);
  const scientistIterationByCaseId = useMemo(() => {
    const map = new Map<string, number>();
    for (const turn of allTurns) {
      if (isScientistGeneration(turn) && turn.caseId) {
        map.set(turn.caseId, turn.number);
      }
    }
    return map;
  }, [allTurns]);
  const taskCaseIds = useMemo(
    () =>
      (Array.isArray(taskCases.data) ? taskCases.data : []).map(
        (item) => item.metadata.id,
      ),
    [taskCases.data],
  );
  const caseOriginById = useMemo(
    () =>
      buildCaseOriginMap(
        allTurns,
        runRecord.data?.configuration?.caseIds?.length
          ? runRecord.data.configuration.caseIds
          : taskCaseIds,
      ),
    [allTurns, runRecord.data?.configuration?.caseIds, taskCaseIds],
  );
  const hasOpenTurnWork = Boolean(
    visibleLatestTurns.some(turnHasOpenWork) ||
    latestTurns?.some(turnHasOpenWork),
  );
  const hasPersistedTurns = Boolean(
    allTurns.length ||
    latestTurns?.length ||
    (turns.data?.latestSequence ?? 0) > 0,
  );
  const hasGeneratingTurn = Boolean(
    visibleLatestTurns.some((turn) => turn.status === "generating") ||
    latestTurns?.some((turn) => turn.status === "generating"),
  );
  const agentWorking = Boolean(
    isLive && hasPersistedTurns && (hasGeneratingTurn || !hasOpenTurnWork),
  );
  const awaitingNextTurn = Boolean(agentWorking && !hasGeneratingTurn);

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
      className={`section-stack run-details${isLive ? " run-live" : ""}`}
    >
      <header className="run-header">
        <div className="run-header-main">
          <p className="eyebrow">Run details</p>
          <div className="run-title">
            <h1>
              Run <span className="mono">{runId}</span>
            </h1>
            <StatusBadge
              label={label(run?.state)}
              tone={tone(run?.state)}
              pulse={isLive}
            />
            <span
              className={`run-mode${
                run?.actionMode === "approval_required"
                  ? " run-mode-actions"
                  : ""
              }`}
            >
              {label(run?.actionMode ?? "read_only")}
            </span>
            {run?.executionMode ? (
              <span className="run-mode run-execution-mode">
                {label(run.executionMode)}
              </span>
            ) : null}
          </div>
          <dl className="run-facts">
            <div>
              <dt>Task</dt>
              <dd className="mono">{run?.task ?? "Pending"}</dd>
            </div>
            <div>
              <dt>Started</dt>
              <dd title={run?.startedAt ?? undefined}>
                {formatTimestamp(run?.startedAt)}
              </dd>
            </div>
            <div>
              <dt>Latest update</dt>
              <dd title={run?.latestUpdateAt ?? undefined}>
                {isLive
                  ? formatRelative(run?.latestUpdateAt, now)
                  : formatTimestamp(run?.latestUpdateAt)}
              </dd>
            </div>
            {scientistIterations > 0 ? (
              <div>
                <dt>Number of new task research</dt>
                <dd className="mono tabular">{scientistIterations}</dd>
              </div>
            ) : null}
          </dl>
        </div>
        <div className="run-header-tools">
          <div
            className="refresh-rate"
            role="radiogroup"
            aria-label="Refresh rate"
            title="How often to refresh run data"
          >
            {REFRESH_RATES_MS.map((ms) => (
              <button
                key={ms}
                type="button"
                role="radio"
                className={refreshMs === ms ? "is-selected" : undefined}
                aria-checked={refreshMs === ms}
                onClick={() => selectRefreshMs(ms)}
              >
                {formatRefreshRate(ms)}
              </button>
            ))}
          </div>
          <div className="run-header-meta">
            <p
              className={`run-connection connection-${events.connectionState}`}
              role="status"
              aria-live="polite"
              title={connectionDetail(events.connectionState)}
            >
              <span className="connection-dot" aria-hidden="true" />
              <span className="connection-label">
                {connectionLabel(events.connectionState)}
              </span>
            </p>
            {isLive ? (
              <button
                type="button"
                className="run-cancel"
                disabled={cancelling}
                onClick={() => void requestCancel()}
              >
                {cancelling ? "Cancelling…" : "Cancel run"}
              </button>
            ) : null}
          </div>
        </div>
      </header>

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

      <section
        className={[
          "lifecycle-panel",
          isLive ? "lifecycle-live" : "",
          waitingForTyr ? "lifecycle-waiting" : "",
          agentWorking ? "lifecycle-working" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        aria-labelledby="stages-title"
      >
        <div className="section-heading">
          <h2 id="stages-title">Stage</h2>
          <span className="muted" role="status" aria-live="polite">
            {waitingForTyr
              ? "Waiting for Tyr"
              : agentWorking
                ? "Agent working"
                : currentPhaseLabel(run, visualization.data?.phases)}
          </span>
        </div>
        {visualization.isLoading ? (
          <p className="secondary">Loading run stages…</p>
        ) : null}
        <ol className="run-stages" aria-label="Run stages">
          {(visualization.data?.phases ?? []).map((phase) => {
            const active = phase.state === "active";
            const statusText = stageStatusLabel(
              phase.state,
              waitingForTyr,
              agentWorking,
              active,
            );
            return (
              <li
                key={phase.id}
                className={[
                  "run-stage",
                  `stage-${phase.state}`,
                  active && waitingForTyr ? "stage-waiting" : "",
                  active && agentWorking ? "stage-working" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                aria-current={active ? "step" : undefined}
                title={
                  statusText ? `${phase.label}: ${statusText}` : phase.label
                }
              >
                <span className="stage-marker" aria-hidden="true" />
                <strong>{phase.label}</strong>
                {statusText ? (
                  <span className="stage-state">{statusText}</span>
                ) : null}
              </li>
            );
          })}
        </ol>
        <CaseList
          cases={visualization.data?.cases ?? []}
          completedCount={visualization.data?.counts?.completedCases}
          totalCount={visualization.data?.counts?.totalCases}
        />
      </section>

      <TyrNetworkMap runId={runId} isLive={isLive} refreshMs={refreshMs} />

      <section className="turns-section" aria-labelledby="turns-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Run history</p>
            <h2 id="turns-title">Updates</h2>
          </div>
          <span className="turn-count mono">
            {turns.data?.latestSequence ?? 0} updates persisted
          </span>
        </div>
        {turns.data?.nextCursor ? (
          <button
            className="button button-secondary"
            type="button"
            disabled={loadingOlder}
            onClick={() => void loadOlder()}
          >
            {loadingOlder
              ? "Loading earlier updates…"
              : `Load ${turns.data.omittedBefore} earlier updates`}
          </button>
        ) : null}
        {turns.isLoading ? (
          <p className="secondary">Loading persisted updates…</p>
        ) : null}
        {turns.error ? (
          <p className="callout callout-warning" role="alert">
            {turns.error.message}
          </p>
        ) : null}
        {!turns.isLoading && !collectorArtifacts.isLoading && !timelineEntries.length ? (
          <p className="empty-state run-empty">
            {isLive
              ? "Waiting for the first update…"
              : "No updates have been persisted yet."}
          </p>
        ) : null}
        <ol className="turn-list" aria-label="Run updates">
          {awaitingNextTurn ? <PendingNextTurn /> : null}
          {timelineEntries.map((entry, index) =>
            entry.kind === "artifact" ? (
              <CollectorArtifactUpdate
                key={`collector-${entry.artifact.caseId}`}
                runId={runId}
                artifact={entry.artifact}
              />
            ) : (
              <Turn
                key={entry.turn.id}
                turn={entry.turn}
                newest={index === 0 && !awaitingNextTurn}
                flash={flashIds.has(entry.turn.id)}
                now={now}
                scientistIteration={
                  entry.turn.caseId
                    ? scientistIterationByCaseId.get(entry.turn.caseId)
                    : undefined
                }
                caseOriginById={caseOriginById}
                taskCaseIds={taskCaseIds}
              />
            ),
          )}
        </ol>
      </section>
    </section>
  );
}

function turnWaitMs(turn: RunTurn, now: number): number | null {
  if (!turn.occurredAt) return null;
  if (turn.repliedAt) {
    const start = new Date(turn.occurredAt).valueOf();
    const end = new Date(turn.repliedAt).valueOf();
    if (Number.isNaN(start) || Number.isNaN(end)) return null;
    return Math.max(0, end - start);
  }
  if (turn.status === "waiting_for_tyr" && !turn.tyrMessage) {
    return elapsedMs(turn.occurredAt, now);
  }
  return null;
}

function Turn({
  turn,
  newest,
  flash,
  now,
  scientistIteration,
  caseOriginById,
  taskCaseIds,
}: {
  turn: RunTurn;
  newest: boolean;
  flash: boolean;
  now: number;
  scientistIteration?: number;
  caseOriginById?: Map<string, HistoryCaseOrigin>;
  taskCaseIds?: string[];
}) {
  const waiting = turn.status === "waiting_for_tyr" && !turn.tyrMessage;
  const scientistGeneration = isScientistGeneration(turn);
  const evaluation = isEvaluation(turn);
  const discoveryResult = isDiscoveryResult(turn);
  const waitMs = turnWaitMs(turn, now);
  const heading = evaluation
    ? `${turn.stage === "scientist" ? "Scientist evaluation" : "Evaluation result"} - ${turn.caseId ?? `Case ${turn.number}`}`
    : discoveryResult
      ? turn.status === "blocked"
        ? "Discovery blocked"
        : "Discovery complete"
      : scientistGeneration
        ? `Scientist - Iteration ${turn.number}`
        : turn.stage === "scientist" && scientistIteration != null
          ? `Scientist Scenario ${scientistIteration} - Turn ${turn.number}`
          : `${label(turn.stage)} - Turn ${turn.number}`;
  const evaluationResult = evaluation
    ? resultDisplay(turn.verdict, turn.objectiveStatus, turn.outcome)
    : null;
  const status = evaluationResult ?? {
    label:
      scientistGeneration && turn.status === "generating"
        ? "Agent working"
        : label(turn.status),
    tone: tone(turn.status),
  };
  const discovered = discoveryResult ? discoveryFields(turn.agentMessage) : [];
  return (
    <li
      className={[
        "turn",
        newest ? "newest-turn" : "",
        waiting ? "turn-waiting" : "",
        scientistGeneration ? "turn-scientist" : "",
        evaluation ? "turn-evaluation" : "",
        evaluation ? `verdict-${evaluationResult?.className ?? "unknown"}` : "",
        discoveryResult ? "turn-discovery" : "",
        turn.status === "failed" || turn.status === "blocked"
          ? evaluationResult?.className === "protected"
            ? ""
            : "turn-failed"
          : "",
        flash ? "turn-flash" : "",
        turn.status === "generating" ? "turn-generating" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      data-turn-id={turn.id}
    >
      <div className="turn-header">
        <div>
          <h3>{heading}</h3>
          {turn.caseId ? (
            <span className="muted">
              {scientistGeneration ? "New scenario" : "Evaluation name"}{" "}
              <span className="mono">{turn.caseId}</span>
            </span>
          ) : null}
        </div>
        <div className="turn-header-side">
          <p className="turn-timing mono">
            <time
              dateTime={turn.occurredAt ?? undefined}
              title={turn.occurredAt ?? undefined}
            >
              {formatTimestamp(turn.occurredAt)}
            </time>
            {waiting && waitMs != null ? (
              <>
                <span className="turn-timing-sep" aria-hidden="true">
                  |
                </span>
                <span className="turn-wait turn-wait-live" aria-live="polite">
                  {formatDuration(waitMs)}
                </span>
              </>
            ) : null}
            {!waiting && waitMs != null ? (
              <>
                <span className="turn-timing-sep" aria-hidden="true">
                  |
                </span>
                <span className="turn-wait" title={turn.repliedAt ?? undefined}>
                  {formatWaited(waitMs)}
                </span>
              </>
            ) : null}
          </p>
          <StatusBadge
            label={status.label}
            tone={status.tone}
            pulse={waiting || turn.status === "generating"}
          />
        </div>
      </div>
      {scientistGeneration && turn.status === "generating" ? (
        <div className="turn-working-progress" aria-hidden="true">
          <span />
        </div>
      ) : null}
      {evaluation ? (
        <div className="turn-messages turn-messages-single">
          <article
            className={`turn-message evaluation-message verdict-${evaluationResult?.className ?? "unknown"}`}
          >
            <p className="turn-speaker">
              <span aria-hidden="true">A</span>Case assessment
            </p>
            <dl className="evaluation-facts">
              <div>
                <dt>Objective</dt>
                <dd>{label(turn.objectiveStatus)}</dd>
              </div>
              <div>
                <dt>Execution</dt>
                <dd>{label(turn.outcome)}</dd>
              </div>
            </dl>
            <MarkdownMessage
              content={turn.assessmentSummary ?? turn.agentMessage}
            />
          </article>
        </div>
      ) : discoveryResult ? (
        <div className="turn-messages turn-messages-single">
          <article
            className={`turn-message discovery-message status-${turn.status}`}
          >
            <p className="turn-speaker">
              <span aria-hidden="true">D</span>Discovery
            </p>
            {discovered.length ? (
              <dl
                className="discovery-variable-list"
                aria-label="Discovered variables"
              >
                {discovered.map((field) => (
                  <div key={field.name} className="discovery-variable-row">
                    <dt className="mono">{field.name}</dt>
                    <dd className="mono">{field.value}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <MarkdownMessage content={turn.agentMessage} />
            )}
          </article>
        </div>
      ) : scientistGeneration ? (
        <div className="turn-messages turn-messages-single">
          <article
            className={`turn-message scientist-message status-${turn.status}`}
          >
            <p className="turn-speaker">
              <span aria-hidden="true">S</span>Scientist
            </p>
            <ScientistScenarioCard turn={turn} />
            {turn.historyCaseIds ? (
              <ScientistHistoryUsed
                cases={resolveHistoryCases(turn.historyCaseIds, {
                  origins: turn.historyCaseOrigins,
                  originByCaseId: caseOriginById,
                  taskCaseIds,
                })}
              />
            ) : null}
          </article>
        </div>
      ) : (
        <div className="turn-messages">
          <article className="turn-message agent-message">
            <p className="turn-speaker">
              <span aria-hidden="true">A</span>Agent
            </p>
            <MarkdownMessage content={turn.agentMessage} />
          </article>
          <article
            className={`turn-message tyr-message${waiting ? " tyr-waiting-panel" : ""}`}
          >
            <p className="turn-speaker">
              <span aria-hidden="true">T</span>Tyr network
            </p>
            {turn.tyrMessage ? (
              <MarkdownMessage content={turn.tyrMessage} />
            ) : waiting ? (
              <WaitingTyr />
            ) : (
              <p className="turn-placeholder">{label(turn.status)}</p>
            )}
          </article>
        </div>
      )}
    </li>
  );
}

function WaitingTyr() {
  return (
    <div className="tyr-waiting" role="status" aria-live="polite">
      <span className="tyr-waiting-spinner" aria-hidden="true" />
      <p className="turn-placeholder">
        Waiting for Tyr
        <span className="tyr-waiting-ellipsis" aria-hidden="true">
          <span>.</span>
          <span>.</span>
          <span>.</span>
        </span>
      </p>
    </div>
  );
}

function CaseList({
  cases,
  completedCount,
  totalCount,
}: {
  cases: CaseProgress[];
  completedCount?: number;
  totalCount?: number | null;
}) {
  if (!cases.length) return null;
  const ordered = [...cases].sort((left, right) => left.order - right.order);
  const done =
    completedCount ??
    ordered.filter((item) => item.state === "completed").length;
  const total = totalCount ?? ordered.length;
  return (
    <details className="case-list">
      <summary className="case-list-summary">
        <span>Test cases</span>
        <span className="case-list-count mono">
          {done}/{total}
        </span>
      </summary>
      <ul className="case-list-items" aria-label="Test cases">
        {ordered.map((item) => {
          const status = caseStatus(item);
          return (
            <li key={item.caseId} className="case-list-item">
              <span className="case-list-id mono" title={item.caseId}>
                {item.caseId}
              </span>
              <StatusBadge
                label={status.label}
                tone={status.tone}
                pulse={item.state === "active"}
              />
            </li>
          );
        })}
      </ul>
    </details>
  );
}

function PendingNextTurn() {
  return (
    <li className="turn turn-pending-next newest-turn">
      <div
        className="pending-next-turn"
        role="status"
        aria-live="polite"
        aria-label="Awaiting next update"
      >
        <span className="tyr-waiting-spinner" aria-hidden="true" />
        <div>
          <p className="pending-next-title">Agent working</p>
          <p className="pending-next-detail">
            Next update will appear when the agent sends a message.
          </p>
        </div>
      </div>
    </li>
  );
}
