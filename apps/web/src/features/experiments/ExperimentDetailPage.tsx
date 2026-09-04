import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchExperimentPreset, startExperiment } from "../../api/client";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";

function modeLabel(mode: string | undefined): string {
  return mode === "approval_required" ? "Approval-gated" : "Read-only";
}

export function ExperimentDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const experimentPreset = useQuery({
    queryKey: ["experiment-preset", id],
    queryFn: () => fetchExperimentPreset(id!),
    enabled: Boolean(id),
  });
  const config = experimentPreset.data?.configuration;
  const actionMode = config?.actionMode ?? "read_only";
  const configuredScenarioIds = config?.scenarioIds;
  const scenarioIds = configuredScenarioIds ?? [];
  const maxConcurrentScenarioExecutions = config?.maxConcurrentScenarioExecutions ?? 5;
  const researchIterations = config?.researchIterations ?? 0;
  const historyTestRuns = config?.historyTestRuns ?? 10;
  const historyResearchRuns = config?.historyResearchRuns ?? 5;
  const discoveryInput = config?.discoveryInput ?? null;
  const researcherOnly = configuredScenarioIds?.length === 0 && researchIterations > 0;

  return (
    <section className="section-stack">
      <PageHeader
        eyebrow="Experiment Preset"
        title={experimentPreset.data?.name ?? `Experiment Preset ${id ?? "unknown"}`}
        description="Review Preset settings and start an Experiment from them."
        actions={<Link className="button button-primary" to="/experiments/new">Run Experiment</Link>}
      />
      <div className="form-layout">
        <article className="card">
          <div className="card-header">
            <div><p className="eyebrow">Preset settings</p><h2>Experiment Preset</h2></div>
            <StatusBadge label={modeLabel(actionMode)} tone={actionMode === "approval_required" ? "warning" : "neutral"} />
          </div>
          {experimentPreset.isLoading ? <p className="secondary" role="status">Loading Experiment Preset…</p> : experimentPreset.isError ? <p className="secondary" role="alert">Could not load this Experiment Preset.</p> : (
            <>
            <dl className="detail-list">
              <div className="detail-row"><dt>Experiment Preset ID</dt><dd className="mono">{id ?? "—"}</dd></div>
              <div className="detail-row"><dt>Task</dt><dd className="mono">{experimentPreset.data?.task ?? "—"}</dd></div>
              <div className="detail-row"><dt>Approval mode</dt><dd>{modeLabel(actionMode)}</dd></div>
              <div className="detail-row"><dt>Execution mode</dt><dd>{researcherOnly ? "Adversarial Researcher only" : "Selected Scenarios"}</dd></div>
              <div className="detail-row"><dt>Scenarios</dt><dd className="mono">{scenarioIds.length > 0 ? scenarioIds.join(", ") : researcherOnly ? "None (Adversarial Researcher only)" : "Task defaults"}</dd></div>
              <div className="detail-row"><dt>Max concurrent Scenario Executions</dt><dd className="mono tabular">{maxConcurrentScenarioExecutions}</dd></div>
              <div className="detail-row"><dt>Research Iterations</dt><dd className="mono tabular">{researchIterations > 0 ? researchIterations : "0 (off)"}</dd></div>
              <div className="detail-row"><dt>Base Scenario history</dt><dd className="mono tabular">{historyTestRuns}</dd></div>
              <div className="detail-row"><dt>Research Iteration history</dt><dd className="mono tabular">{historyResearchRuns}</dd></div>
              <div className="detail-row"><dt>Discovery input</dt><dd>{discoveryInput ? "Provided target" : "None (live discovery)"}</dd></div>
              {discoveryInput ? <div className="detail-row"><dt>Fallback to live discovery</dt><dd>{config?.fallbackToDiscovery ? "Enabled (bounded read-only preflight)" : "Disabled (an unavailable target fails the Experiment)"}</dd></div> : null}
            </dl>
            {discoveryInput ? (
              <div className="discovery-review">
                <p className="eyebrow">Provided discovery input</p>
                <dl className="detail-list">
                  <div className="detail-row"><dt>Task ID in document</dt><dd className="mono">{discoveryInput.taskId}</dd></div>
                  <div className="detail-row"><dt>path</dt><dd className="mono">{discoveryInput.candidate.path}</dd></div>
                  <div className="detail-row"><dt>workspace</dt><dd className="mono">{discoveryInput.candidate.workspace}</dd></div>
                  <div className="detail-row"><dt>agent</dt><dd className="mono">{discoveryInput.candidate.agent}</dd></div>
                  <div className="detail-row"><dt>bridgeId</dt><dd className="mono">{discoveryInput.candidate.bridgeId}</dd></div>
                </dl>
                <p className="field-help">The document Task ID is informational and is not matched against the selected Task.</p>
              </div>
            ) : null}
            </>
          )}
        </article>
        <aside className="card">
          <div className="card-header"><div><p className="eyebrow">Experiment</p><h2>Start from this Preset</h2></div></div>
          <div className="empty-state"><div>
            <h3>Start an Experiment</h3>
            <p>Uses the stored Task, Scenarios, approval mode, and Research Iterations. Tyr records each human approval decision.</p>
            <button className="button button-primary" type="button" disabled={!id || starting || experimentPreset.isError} onClick={() => {
              if (!id) return;
              setStarting(true);
              setError(null);
              startExperiment(id).then((experiment) => navigate(`/runs/${experiment.id}`)).catch((reason: Error) => setError(reason.message)).finally(() => setStarting(false));
            }}>{starting ? "Starting…" : "Start Experiment"}</button>
            {error ? <p role="alert">{error}</p> : null}
          </div></div>
        </aside>
      </div>
    </section>
  );
}
