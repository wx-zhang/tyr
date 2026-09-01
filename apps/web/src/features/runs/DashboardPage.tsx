import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  cancelRun,
  deleteRun,
  fetchRuns,
  type Run,
  type RunState,
} from "../../api/client";
import { PageHeader } from "../../components/PageHeader";
import { DashboardRunCard } from "./DashboardRunCard";
import { DashboardSelectionToolbar } from "./DashboardSelectionToolbar";
import { compareRunsNewestFirst } from "./dashboardRunPresentation";

const terminalStates: Partial<Record<RunState, true>> = {
  completed: true,
  failed: true,
  cancelled: true,
  interrupted: true,
};

const deletableLiveStates: Partial<Record<RunState, true>> = { queued: true };

function shortRunId(id: string): string {
  return id.replaceAll("-", "").slice(0, 8);
}

async function deleteRuns(ids: string[]): Promise<void> {
  const results = await Promise.allSettled(ids.map((id) => deleteRun(id)));
  const failed = results.filter(
    (result) => result.status === "rejected",
  ).length;
  if (failed > 0) {
    throw new Error(
      failed === ids.length
        ? `Could not delete ${failed === 1 ? "the Experiment" : `${failed} Experiments`}`
        : `Deleted ${ids.length - failed} of ${ids.length} Experiments; ${failed} failed`,
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
    refetchOnMount: "always",
    refetchOnWindowFocus: "always",
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
        error instanceof Error ? error.message : "Could not delete Experiment",
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
      setStopError(
        error instanceof Error ? error.message : "Could not stop Experiment",
      );
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
          terminalStates[run.state as RunState] ||
          deletableLiveStates[run.state as RunState],
      ),
    [recentRuns],
  );
  const deletableIds = useMemo(
    () => new Set(deletableRuns.map((run) => run.id)),
    [deletableRuns],
  );
  const selectedCount = selectedIds.size;
  const allDeletableSelected =
    deletableRuns.length > 0 &&
    deletableRuns.every((run) => selectedIds.has(run.id));

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
      `Delete Experiment ${shortRunId(run.id)}? This permanently removes its evidence and cannot be undone.`,
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
      `Delete ${ids.length} selected Experiment${ids.length === 1 ? "" : "s"}? This permanently removes their evidence and cannot be undone.`,
    );
    if (!confirmed) return;
    deleteMutation.mutate(ids);
  };

  const requestStop = (run: Run) => {
    const confirmed = window.confirm(
      `Stop Experiment ${shortRunId(run.id)}? The Experiment will stop. Existing evidence remains reviewable.`,
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
          Red team for Tyr. Experiments run attack Scenarios against it and save
          the evidence so you can see what held and what failed.
        </p>
      </section>

      <PageHeader
        title="Recent Experiments"
        description="Red-team Experiments against Tyr, newest first. Open an Experiment to review its state and evidence."
        actions={
          <div className="button-row">
            {deletableRuns.length > 0 && !selecting ? (
              <button
                type="button"
                className="button button-ghost"
                onClick={enterSelecting}
              >
                Select
              </button>
            ) : null}
            <Link className="button button-primary" to="/experiments/new">
              Run Experiment
            </Link>
          </div>
        }
      />

      {runsQuery.isError ? (
        <div className="callout callout-warning" role="alert">
          {runsQuery.error instanceof Error
            ? runsQuery.error.message
            : "Could not load Experiments"}
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
            <h3>Loading Experiments</h3>
            <p>Reading the persisted Experiment index…</p>
          </div>
        </div>
      ) : null}

      {!runsQuery.isLoading && !runsQuery.isError && recentRuns.length === 0 ? (
        <div className="card empty-state">
          <div>
            <h3>No Experiments yet</h3>
            <p>
              When an Experiment is queued, it will appear here with its current
              state and evidence links.
            </p>
            <Link className="button button-secondary" to="/experiments/new">
              Run Experiment
            </Link>
          </div>
        </div>
      ) : null}

      {recentRuns.length > 0 ? (
        <div className="experiment-card-collection">
          {selecting ? (
            <DashboardSelectionToolbar
              selectedCount={selectedCount}
              allDeletableSelected={allDeletableSelected}
              deletableCount={deletableRuns.length}
              deletePending={deleteMutation.isPending}
              onSelectAll={toggleSelectAll}
              onCancel={exitSelecting}
              onDelete={requestBulkDelete}
            />
          ) : null}
          <ol className="experiment-card-list" aria-label="Recent Experiments">
            {recentRuns.map((run) => {
              const isDeletable = deletableIds.has(run.id);
              const isDeleting =
                deleteMutation.isPending &&
                (deleteMutation.variables?.includes(run.id) ?? false);
              const isStopping =
                stopMutation.isPending && stopMutation.variables === run.id;
              return (
                <DashboardRunCard
                  key={run.id}
                  run={run}
                  now={now}
                  selecting={selecting}
                  selected={selectedIds.has(run.id)}
                  deletable={isDeletable}
                  deletePending={deleteMutation.isPending}
                  deleting={isDeleting}
                  stopPending={stopMutation.isPending}
                  stopping={isStopping}
                  onSelect={() => toggleSelected(run.id)}
                  onDelete={() => requestDelete(run)}
                  onStop={() => requestStop(run)}
                />
              );
            })}
          </ol>
        </div>
      ) : null}
    </section>
  );
}
