import { Link } from "react-router-dom";
import type { Run } from "../../api/client";
import { StatusBadge } from "../../components/StatusBadge";
import { dashboardRunPresentation } from "./dashboardRunPresentation";
import { resultDisplay } from "./runTurnHelpers";

type DashboardRunCardProps = {
  run: Run;
  now: number;
  selecting: boolean;
  selected: boolean;
  deletable: boolean;
  deletePending: boolean;
  deleting: boolean;
  stopPending: boolean;
  stopping: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onStop: () => void;
};

export function DashboardRunCard({
  run,
  now,
  selecting,
  selected,
  deletable,
  deletePending,
  deleting,
  stopPending,
  stopping,
  onSelect,
  onDelete,
  onStop,
}: DashboardRunCardProps) {
  const {
    shortId,
    title,
    source,
    stateLabel,
    stateTone,
    actionModeLabel,
    actionModeTone,
    when,
    relativeWhen,
    absoluteWhen,
    live,
    executions,
    counts,
    resultClass,
  } = dashboardRunPresentation(run, now);
  const titleId = `experiment-${run.id}-title`;
  const resultsId = `experiment-${run.id}-scenario-results`;

  return (
    <li>
      <article
        className={`experiment-card ${resultClass}${selected ? " is-selected" : ""}`}
        aria-labelledby={titleId}
      >

        <header className="experiment-card-header">
          <div className="experiment-card-heading">
            {selecting ? (
              <div className="experiment-card-selection">
                <input
                  type="checkbox"
                  className="session-checkbox"
                  aria-label={`Select Experiment ${shortId}`}
                  checked={selected}
                  disabled={!deletable || deletePending}
                  onChange={onSelect}
                />
              </div>
            ) : null}
            <div className="experiment-card-identity">
              <Link
                id={titleId}
                to={`/runs/${run.id}`}
                className="experiment-card-title"
                title={run.id}
              >
                {title}
              </Link>
              <p className="experiment-card-meta muted">
                <span className="mono" title={run.id}>
                  {shortId}
                </span>
                <span aria-hidden="true">·</span>
                <span>{source}</span>
                {run.configuration?.model ? (
                  <>
                    <span aria-hidden="true">·</span>
                    <span className="mono" title={run.configuration.model}>
                      {run.configuration.model}
                    </span>
                  </>
                ) : null}
              </p>
            </div>
          </div>
          <div className="experiment-card-facts">
            <StatusBadge label={stateLabel} tone={stateTone} pulse={live} />
            <StatusBadge label={actionModeLabel} tone={actionModeTone} />
            <time className="tabular" dateTime={when ?? undefined}>
              {relativeWhen}
              <span className="muted mono tabular">{absoluteWhen}</span>
            </time>
          </div>
        </header>

        {executions.length > 0 ? (
          <details
            className="experiment-results"
            aria-labelledby={`${titleId} ${resultsId}`}
          >
            <summary>
              <span
                id={resultsId}
                className="experiment-results-heading"
                role="heading"
                aria-level={3}
              >
                Scenario results
              </span>
              <div className="experiment-result-metrics">
                <div>
                  <span>Breach</span>
                  <strong>{counts.breach}</strong>
                </div>
                <div>
                  <span>No breach</span>
                  <strong>{counts.protected}</strong>
                </div>
                <div>
                  <span>Inconclusive</span>
                  <strong>{counts.inconclusive}</strong>
                </div>
              </div>
              <span className="experiment-results-toggle experiment-results-toggle-closed">
                View details
              </span>
              <span className="experiment-results-toggle experiment-results-toggle-open">
                Hide details
              </span>
            </summary>
            <ul className="experiment-result-list">
              {executions.map((execution) => {
                const display = resultDisplay(
                  execution.verdict,
                  execution.objectiveStatus,
                  execution.outcome,
                );
                const scenarioId = execution.scenarioId ?? "Unknown Scenario";
                return (
                  <li
                    key={`${execution.scenarioExecutionId ?? scenarioId}-${execution.order}`}
                    className={`experiment-result-chip result-${display.className}`}
                  >
                    <span className="experiment-result-scenario mono">
                      {scenarioId}
                    </span>
                    <StatusBadge label={display.label} tone={display.tone} />
                  </li>
                );
              })}
            </ul>
          </details>
        ) : (
          <section
            className="experiment-results experiment-results-empty"
            aria-labelledby={`${titleId} ${resultsId}`}
          >
            <h3 id={resultsId}>Scenario results</h3>
            <p className="muted">
              {live
                ? "Scenario results will appear as executions finish."
                : "No Scenario results were recorded."}
            </p>
          </section>
        )}

        {!selecting ? (
          <div className="button-row experiment-card-actions">
            {live ? (
              <button
                type="button"
                className="button button-ghost run-action"
                disabled={stopPending}
                title="Stop this Experiment"
                onClick={onStop}
              >
                {stopping ? "Stopping…" : "Stop"}
              </button>
            ) : null}
            <button
              type="button"
              className="button button-ghost run-action run-action-danger"
              disabled={!deletable || deletePending}
              title={
                deletable
                  ? "Delete this Experiment"
                  : "Stop the Experiment before deleting it"
              }
              onClick={onDelete}
            >
              {deleting ? "Deleting…" : "Delete"}
            </button>
          </div>
        ) : null}
      </article>
    </li>
  );
}
