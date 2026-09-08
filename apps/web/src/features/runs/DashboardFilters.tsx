import { useMemo, useState } from "react";
import type { Run } from "../../api/client";

export function useDashboardFilters(runs: Run[]) {
  const [filters, setFilters] = useState({ search: "", state: "all" });
  const [limit, setLimit] = useState(25);
  const matches = useMemo(() => {
    const search = filters.search.trim().toLowerCase();
    return runs.filter((run) => {
      const stateMatches =
        filters.state === "all" ||
        (filters.state === "active"
          ? [
              "queued",
              "preparing",
              "discovering",
              "running",
              "waiting_for_approval",
              "evaluating",
              "reporting",
            ].includes(run.state ?? "")
          : run.state === filters.state);
      return (
        stateMatches &&
        [run.id, run.name, run.task, run.configuration?.model].some((value) =>
          value?.toLowerCase().includes(search),
        )
      );
    });
  }, [runs, filters]);
  return {
    filters,
    changeFilters: (next: typeof filters) => {
      setFilters(next);
      setLimit(25);
    },
    visibleRuns: matches.slice(0, limit),
    matchingCount: matches.length,
    showMore: () => setLimit((current) => current + 25),
  };
}

type Props = {
  filters: { search: string; state: string };
  onChange: (filters: Props["filters"]) => void;
  visibleCount: number;
  matchingCount: number;
  totalCount: number;
  disabled: boolean;
};

export function DashboardFilters({
  filters,
  onChange,
  visibleCount,
  matchingCount,
  totalCount,
  disabled,
}: Props) {
  const filtered = filters.search !== "" || filters.state !== "all";
  return (
    <div className="experiment-browser">
      <div className="experiment-filters">
        <div className="field-group">
          <label htmlFor="experiment-search">Search Experiments</label>
          <input
            id="experiment-search"
            type="search"
            placeholder="Name, Task, ID, or model"
            value={filters.search}
            disabled={disabled}
            onChange={(event) =>
              onChange({ ...filters, search: event.target.value })
            }
          />
        </div>
        <div className="field-group">
          <label htmlFor="experiment-state">Experiment state</label>
          <select
            id="experiment-state"
            value={filters.state}
            disabled={disabled}
            onChange={(event) =>
              onChange({ ...filters, state: event.target.value })
            }
          >
            <option value="all">All states</option>
            <option value="active">Active</option>
            <option value="waiting_for_approval">Waiting for approval</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="cancelled">Cancelled</option>
            <option value="interrupted">Interrupted</option>
          </select>
        </div>
        {filtered ? (
          <button
            className="button button-ghost"
            disabled={disabled}
            onClick={() => onChange({ search: "", state: "all" })}
          >
            Clear filters
          </button>
        ) : null}
      </div>
      <div className="experiment-list-caption">
        <span role="status">
          <span className="mono">{visibleCount}</span> of{" "}
          <span className="mono">{matchingCount}</span> Experiments
          {filtered ? ` (${totalCount} total)` : ""}
        </span>
        <span>Newest first</span>
      </div>
      {matchingCount === 0 ? (
        <div className="empty-state">
          <div>
            <h2>No matching Experiments</h2>
            <p>
              Try another search or clear the filters to see all Experiments.
            </p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
