import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { cancelRun, deleteRun, fetchRuns, type Run, type RunState } from "../../api/client";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";

const terminalStates = new Set<RunState>([
  "completed",
  "failed",
  "cancelled",
  "interrupted",
]);

const deletableLiveStates = new Set<RunState>(["queued"]);

function shortRunId(id: string): string {
  return id.replaceAll("-", "").slice(0, 8);
}

function runWhen(run: Run): string | null {
  return run.createdAt ?? run.updatedAt ?? run.finishedAt ?? null;
}

function label(value: string | null | undefined): string {
  if (!value) return "—";
  if (value === "read_only") return "Read-only";
  if (value === "approval_required") return "Actions Allowed";
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function stateTone(
  state: string | undefined,
): "info" | "success" | "warning" | "danger" | "neutral" {
  if (state === "completed") return "success";
  if (state === "failed") return "danger";
  if (state === "waiting_for_approval") return "warning";
  if (state === "cancelled" || state === "interrupted") return "neutral";
  return "info";
}

function formatAbsolute(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatRelative(value: string | null, now: number): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const deltaSeconds = Math.round((date.getTime() - now) / 1000);
  const absolute = Math.abs(deltaSeconds);
  if (absolute < 5) return "just now";
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  if (absolute < 60) return formatter.format(deltaSeconds, "second");
  if (absolute < 3600) {
    return formatter.format(Math.round(deltaSeconds / 60), "minute");
  }
  if (absolute < 86_400) {
    return formatter.format(Math.round(deltaSeconds / 3600), "hour");
  }
  if (absolute < 86_400 * 30) {
    return formatter.format(Math.round(deltaSeconds / 86_400), "day");
  }
  return formatAbsolute(value);
}

function compareRunsNewestFirst(left: Run, right: Run): number {
  const leftTime = Date.parse(left.createdAt ?? left.updatedAt ?? "") || 0;
  const rightTime = Date.parse(right.createdAt ?? right.updatedAt ?? "") || 0;
  if (rightTime !== leftTime) return rightTime - leftTime;
  return right.id.localeCompare(left.id);
}

function datasetLabel(dataset: string): string {
  const parts = dataset.split("/").filter(Boolean);
  return parts[parts.length - 1] ?? dataset;
}

function sourceLabel(source: Run["source"] | undefined): string {
  if (source === "cli") return "CLI";
  if (source === "service") return "Service";
  return "—";
}

async function deleteRuns(ids: string[]): Promise<void> {
  const results = await Promise.allSettled(ids.map((id) => deleteRun(id)));
  const failed = results.filter((result) => result.status === "rejected").length;
  if (failed > 0) {
    throw new Error(
      failed === ids.length
        ? `Could not delete ${failed === 1 ? "the session" : `${failed} sessions`}`
        : `Deleted ${ids.length - failed} of ${ids.length} sessions; ${failed} failed`,
    );
  }
}

export function DashboardPage() {
  const [now] = useState(() => Date.now());
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [stopError, setStopError] = useState<string | null>(null);
  const [selecting, setSelecting] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const queryClient = useQueryClient();
  const runsQuery = useQuery({
    queryKey: ["runs"],
    queryFn: fetchRuns,
    refetchOnWindowFocus: true,
    staleTime: 5_000,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteRuns,
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
    onSuccess: (_data, ids) => {
      setDeleteError(null);
      if (selecting) {
        setSelecting(false);
        setSelectedIds(new Set());
        return;
      }
      setSelectedIds((current) => {
        const next = new Set(current);
        for (const id of ids) next.delete(id);
        return next;
      });
    },
    onError: (error: unknown) => {
      setDeleteError(
        error instanceof Error ? error.message : "Could not delete session",
      );
    },
  });

  const stopMutation = useMutation({
    mutationFn: (runId: string) => cancelRun(runId),
    onSuccess: () => {
      setStopError(null);
      void queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
    onError: (error: unknown) => {
      setStopError(error instanceof Error ? error.message : "Could not stop session");
    },
  });

  const recentRuns = useMemo(
    () => [...(runsQuery.data ?? [])].sort(compareRunsNewestFirst),
    [runsQuery.data],
  );

  const deletableRuns = useMemo(
    () =>
      recentRuns.filter(
        (run) =>
          terminalStates.has(run.state as RunState)
          || deletableLiveStates.has(run.state as RunState),
      ),
    [recentRuns],
  );
  const deletableIds = useMemo(
    () => new Set(deletableRuns.map((run) => run.id)),
    [deletableRuns],
  );
  const selectedCount = selectedIds.size;
  const allDeletableSelected =
    deletableRuns.length > 0 && deletableRuns.every((run) => selectedIds.has(run.id));

  const enterSelecting = () => {
    setDeleteError(null);
    setSelecting(true);
  };

  const exitSelecting = () => {
    setSelecting(false);
    setSelectedIds(new Set());
  };

  const requestDelete = (run: Run) => {
    const confirmed = window.confirm(
      `Delete session ${shortRunId(run.id)}? This permanently removes its evidence and cannot be undone.`,
    );
    if (!confirmed) return;
    deleteMutation.mutate([run.id]);
  };

  const requestBulkDelete = () => {
    const ids = deletableRuns
      .filter((run) => selectedIds.has(run.id))
      .map((run) => run.id);
    if (ids.length === 0) return;
    const confirmed = window.confirm(
      `Delete ${ids.length} selected session${ids.length === 1 ? "" : "s"}? This permanently removes their evidence and cannot be undone.`,
    );
    if (!confirmed) return;
    deleteMutation.mutate(ids);
  };

  const requestStop = (run: Run) => {
    const confirmed = window.confirm(
      `Stop session ${shortRunId(run.id)}? The run will stop. Existing evidence remains reviewable.`,
    );
    if (!confirmed) return;
    stopMutation.mutate(run.id);
  };

  const toggleSelected = (runId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(runId)) next.delete(runId);
      else next.add(runId);
      return next;
    });
  };

  const toggleSelectAll = () => {
    setSelectedIds((current) => {
      if (allDeletableSelected) {
        const next = new Set(current);
        for (const run of deletableRuns) next.delete(run.id);
        return next;
      }
      const next = new Set(current);
      for (const run of deletableRuns) next.add(run.id);
      return next;
    });
  };

  return (
    <section className="section-stack">
      <section className="product-overview" aria-label="About GAMR">
        <h2 className="product-overview-name">
          GAMR{" "}
          <span className="product-overview-acronym">
            Generative Adversarial Risk Mapper
          </span>
        </h2>
        <p>
          Red team for Tyr. Runs attack scenarios against it and saves the
          evidence so you can see what held and what failed.
        </p>
      </section>

      <PageHeader
        title="Recent sessions"
        description="Red-team runs against Tyr, newest first. Open a session to review state and evidence."
        actions={
          <Link className="button button-primary" to="/experiments/new">
            Execute
          </Link>
        }
      />

      {runsQuery.isError ? (
        <div className="callout callout-warning" role="alert">
          {runsQuery.error instanceof Error
            ? runsQuery.error.message
            : "Could not load sessions"}
          . Check that the API is running, then refresh.
        </div>
      ) : null}

      {deleteError ? (
        <div className="callout callout-warning" role="alert">
          {deleteError}
        </div>
      ) : null}

      {stopError ? (
        <div className="callout callout-warning" role="alert">
          {stopError}
        </div>
      ) : null}

      {runsQuery.isLoading ? (
        <div className="card empty-state" role="status">
          <div>
            <h3>Loading sessions</h3>
            <p>Reading the persisted run index…</p>
          </div>
        </div>
      ) : null}

      {!runsQuery.isLoading && !runsQuery.isError && recentRuns.length === 0 ? (
        <div className="card empty-state">
          <div>
            <h3>No sessions yet</h3>
            <p>
              When an experiment run is queued, it will appear here with its
              current state and evidence links.
            </p>
            <Link className="button button-secondary" to="/experiments/new">
              Execute the first experiment
            </Link>
          </div>
        </div>
      ) : null}

      {recentRuns.length > 0 ? (
        <div className="card table-wrap">
          {deletableRuns.length > 0 || selecting ? (
            <div className="session-table-toolbar" aria-label="Session selection">
              {selecting ? (
                <>
                  <p className="session-table-toolbar-status muted">
                    {selectedCount === 0
                      ? "Select sessions to delete"
                      : `${selectedCount} selected`}
                  </p>
                  <div className="button-row">
                    <button
                      type="button"
                      className="button button-ghost run-action"
                      disabled={deleteMutation.isPending}
                      onClick={exitSelecting}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      className="button button-danger run-action"
                      disabled={selectedCount === 0 || deleteMutation.isPending}
                      onClick={requestBulkDelete}
                    >
                      {deleteMutation.isPending
                        ? "Deleting…"
                        : selectedCount === 0
                          ? "Delete selected"
                          : `Delete ${selectedCount} selected`}
                    </button>
                  </div>
                </>
              ) : (
                <button
                  type="button"
                  className="button button-ghost run-action"
                  onClick={enterSelecting}
                >
                  Select
                </button>
              )}
            </div>
          ) : null}
          <table
            className={`data-table session-table${selecting ? " is-selecting" : ""}`}
          >
            <thead>
              <tr>
                {selecting ? (
                  <th scope="col" className="session-select-col">
                    <input
                      type="checkbox"
                      className="session-checkbox"
                      aria-label="Select all deletable sessions"
                      checked={allDeletableSelected}
                      disabled={deletableRuns.length === 0 || deleteMutation.isPending}
                      onChange={toggleSelectAll}
                    />
                  </th>
                ) : null}
                <th scope="col">Session</th>
                <th scope="col">Status</th>
                <th scope="col">Mode</th>
                <th scope="col">When</th>
                {!selecting ? <th scope="col">Actions</th> : null}
              </tr>
            </thead>
            <tbody>
              {recentRuns.map((run) => {
                const when = runWhen(run);
                const actionMode = run.configuration?.actionMode;
                const isLive = !terminalStates.has(run.state as RunState);
                const isDeletable = deletableIds.has(run.id);
                const isSelected = selectedIds.has(run.id);
                const isDeleting =
                  deleteMutation.isPending
                  && (deleteMutation.variables?.includes(run.id) ?? false);
                const isStopping =
                  stopMutation.isPending && stopMutation.variables === run.id;
                return (
                  <tr
                    key={run.id}
                    className={isSelected ? "is-selected" : undefined}
                  >
                    {selecting ? (
                      <td className="session-select-col">
                        <input
                          type="checkbox"
                          className="session-checkbox"
                          aria-label={`Select session ${shortRunId(run.id)}`}
                          checked={isSelected}
                          disabled={!isDeletable || deleteMutation.isPending}
                          onChange={() => toggleSelected(run.id)}
                        />
                      </td>
                    ) : null}
                    <td>
                      <div className="cell-stack">
                        <Link
                          to={`/runs/${run.id}`}
                          className="table-primary session-title"
                          title={run.id}
                        >
                          {datasetLabel(run.dataset)}
                        </Link>
                        <p className="session-meta muted">
                          <span className="mono" title={run.id}>
                            {shortRunId(run.id)}
                          </span>
                          <span aria-hidden="true">·</span>
                          <span>{sourceLabel(run.source)}</span>
                          {run.configuration?.model ? (
                            <>
                              <span aria-hidden="true">·</span>
                              <span
                                className="mono"
                                title={run.configuration.model}
                              >
                                {run.configuration.model}
                              </span>
                            </>
                          ) : null}
                        </p>
                      </div>
                    </td>
                    <td>
                      <StatusBadge
                        label={label(run.state)}
                        tone={stateTone(run.state)}
                        pulse={isLive}
                      />
                    </td>
                    <td>
                      <StatusBadge
                        label={label(actionMode)}
                        tone={
                          actionMode === "approval_required"
                            ? "warning"
                            : "neutral"
                        }
                      />
                    </td>
                    <td>
                      <div className="cell-stack">
                        <time
                          className="table-primary tabular"
                          dateTime={when ?? undefined}
                        >
                          {formatRelative(when, now)}
                        </time>
                        <span className="muted mono tabular">
                          {formatAbsolute(when)}
                        </span>
                      </div>
                    </td>
                    {!selecting ? (
                      <td>
                        <div className="button-row session-actions">
                          {isLive ? (
                            <button
                              type="button"
                              className="button button-ghost run-action"
                              disabled={stopMutation.isPending}
                              title="Stop this session"
                              onClick={() => requestStop(run)}
                            >
                              {isStopping ? "Stopping…" : "Stop"}
                            </button>
                          ) : null}
                          <button
                            type="button"
                            className="button button-ghost run-action run-action-danger"
                            disabled={!isDeletable || deleteMutation.isPending}
                            title={
                              isDeletable
                                ? "Delete this session"
                                : "Stop the run before deleting it"
                            }
                            onClick={() => requestDelete(run)}
                          >
                            {isDeleting ? "Deleting…" : "Delete"}
                          </button>
                        </div>
                      </td>
                    ) : null}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
