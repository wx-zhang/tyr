import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchRuns, type Run, type RunState } from "../../api/client";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";

const terminalStates = new Set<RunState>([
  "completed",
  "failed",
  "cancelled",
  "interrupted",
]);

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

export function DashboardPage() {
  const [now] = useState(() => Date.now());
  const runsQuery = useQuery({
    queryKey: ["runs"],
    queryFn: fetchRuns,
    refetchOnWindowFocus: true,
    staleTime: 5_000,
  });

  const recentRuns = useMemo(
    () => [...(runsQuery.data ?? [])].sort(compareRunsNewestFirst),
    [runsQuery.data],
  );

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
          <table className="data-table session-table">
            <thead>
              <tr>
                <th scope="col">Session</th>
                <th scope="col">Status</th>
                <th scope="col">Mode</th>
                <th scope="col">When</th>
              </tr>
            </thead>
            <tbody>
              {recentRuns.map((run) => {
                const when = runWhen(run);
                const actionMode = run.configuration?.actionMode;
                const isLive = !terminalStates.has(run.state as RunState);
                return (
                  <tr key={run.id}>
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
