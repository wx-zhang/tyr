import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchExperiment, startExperiment } from "../../api/client";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";

function modeLabel(mode: string | undefined): string {
  if (mode === "approval_required") return "Actions Allowed";
  return "Read-only";
}

export function ExperimentDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const experiment = useQuery({
    queryKey: ["experiment", id],
    queryFn: () => fetchExperiment(id!),
    enabled: Boolean(id),
  });

  const config = experiment.data?.configuration;
  const actionMode = config?.actionMode ?? "read_only";
  const caseIds = config?.caseIds ?? [];
  const scientistIterations = config?.scientistIterations ?? 0;

  return (
    <section className="section-stack">
      <PageHeader
        eyebrow="Saved configuration"
        title={experiment.data?.name ?? `Experiment ${id ?? "unknown"}`}
        description="Review the configuration snapshot and start a run from it."
        actions={
          <Link className="button button-primary" to="/experiments/new">
            Execute experiment
          </Link>
        }
      />
      <div className="form-layout">
        <article className="card">
          <div className="card-header">
            <div>
              <p className="eyebrow">Configuration</p>
              <h2>Run settings</h2>
            </div>
            <StatusBadge
              label={modeLabel(actionMode)}
              tone={actionMode === "approval_required" ? "warning" : "neutral"}
            />
          </div>
          {experiment.isLoading ? (
            <p className="secondary" role="status">
              Loading experiment…
            </p>
          ) : experiment.isError ? (
            <p className="secondary" role="alert">
              Could not load this experiment.
            </p>
          ) : (
            <dl className="detail-list">
              <div className="detail-row">
                <dt>Experiment ID</dt>
                <dd className="mono">{id ?? "—"}</dd>
              </div>
              <div className="detail-row">
                <dt>Dataset</dt>
                <dd className="mono">{experiment.data?.dataset ?? "—"}</dd>
              </div>
              <div className="detail-row">
                <dt>Action mode</dt>
                <dd>{modeLabel(actionMode)}</dd>
              </div>
              <div className="detail-row">
                <dt>Cases</dt>
                <dd className="mono">
                  {caseIds.length > 0 ? caseIds.join(", ") : "Dataset defaults"}
                </dd>
              </div>
              <div className="detail-row">
                <dt>Scientist iterations</dt>
                <dd className="mono tabular">
                  {scientistIterations > 0 ? scientistIterations : "0 (off)"}
                </dd>
              </div>
            </dl>
          )}
        </article>
        <aside className="card">
          <div className="card-header">
            <div>
              <p className="eyebrow">Execution</p>
              <h2>Start from this config</h2>
            </div>
          </div>
          <div className="empty-state">
            <div>
              <h3>Queue a run</h3>
              <p>
                Starts with the stored dataset, cases, action mode, and scientist
                iterations. Live progress opens on the run page.
              </p>
              <button
                className="button button-primary"
                type="button"
                disabled={!id || starting || experiment.isError}
                onClick={() => {
                  if (!id) return;
                  setStarting(true);
                  setError(null);
                  startExperiment(id)
                    .then((run) => navigate(`/runs/${run.id}`))
                    .catch((reason: Error) => setError(reason.message))
                    .finally(() => setStarting(false));
                }}
              >
                {starting ? "Starting…" : "Execute"}
              </button>
              {error ? <p role="alert">{error}</p> : null}
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}
