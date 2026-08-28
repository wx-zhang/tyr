import { useState } from "react";
import { Link } from "react-router-dom";
import {
  adversarialResearcherScenarioExportUrl,
  type AdversarialResearcherScenario,
  type ScientistScenarioResult,
  type ScientistScenarioState,
} from "../../api/client";
import { StatusBadge } from "../../components/StatusBadge";

const resultLabels: Record<ScientistScenarioResult, string> = {
  vulnerable: "Vulnerable",
  protected: "Protected",
  inconclusive: "Inconclusive",
  not_applicable: "Not applicable",
  pending: "Pending",
  unavailable: "Unavailable",
};

function resultTone(
  value: ScientistScenarioResult,
): "danger" | "success" | "warning" | "neutral" {
  if (value === "vulnerable") return "danger";
  if (value === "protected") return "success";
  if (value === "pending") return "warning";
  return "neutral";
}

export function ScientistScenarioDetail({
  entry,
  state,
  pending,
  onArchive,
}: {
  entry: AdversarialResearcherScenario;
  state: ScientistScenarioState;
  pending: boolean;
  onArchive: () => void;
}) {
  const experimentId = entry.experimentId ?? entry.runId ?? "";
  const scenario = entry.scenario;
  const [expanded, setExpanded] = useState(false);
  const scenarioExecutionId = entry.result?.scenarioExecutionId ?? scenario.metadata.id;
  const definitionId = `adversarial-researcher-scenario-definition-${experimentId}-${entry.artifactId}`;
  const tags = scenario.metadata.tags ?? [];

  return (
    <article className="card scientist-catalog-card">
      <header className="scientist-catalog-card-header">
        <div>
          <p className="eyebrow">
            {scenario.metadata.category ?? "Adversarial Researcher Scenario"}
          </p>
          <h2>{scenario.metadata.title}</h2>
          <p className="mono scientist-catalog-id">{scenario.metadata.id}</p>
        </div>
        <StatusBadge
          label={resultLabels[entry.resultState]}
          tone={resultTone(entry.resultState)}
        />
      </header>
      <dl className="scientist-catalog-meta">
        <div>
          <dt>Task</dt>
          <dd className="mono">{entry.task}</dd>
        </div>
        <div>
          <dt>Origin Experiment</dt>
          <dd>
            <Link to={`/runs/${encodeURIComponent(experimentId)}/scenario-executions/${encodeURIComponent(scenarioExecutionId)}`}>
              Open originating Experiment
            </Link>
          </dd>
        </div>
        <div>
          <dt>Tags</dt>
          <dd>{tags.length ? tags.join(", ") : "None"}</dd>
        </div>
      </dl>
      {entry.result ? (
        <p className="secondary">{entry.result.summary}</p>
      ) : null}
      <div className="button-row scientist-catalog-actions">
        <button
          className="button button-secondary"
          type="button"
          aria-expanded={expanded}
          aria-controls={definitionId}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? "Hide complete Scenario definition" : "Show complete Scenario definition"}
        </button>
        <a
          className="button button-ghost"
          href={adversarialResearcherScenarioExportUrl(experimentId, entry.artifactId)}
        >
          Export JSON
        </a>
        <button
          className={`button ${state === "active" ? "button-danger" : "button-secondary"}`}
          type="button"
          disabled={pending}
          onClick={onArchive}
        >
          {state === "active" ? "Archive Scenario" : "Restore Scenario"}
        </button>
      </div>
      {expanded ? (
        <div className="scientist-catalog-definition" id={definitionId}>
          <dl>
            <div>
              <dt>Objective</dt>
              <dd>{scenario.spec.objective}</dd>
            </div>
            <div>
              <dt>Steps</dt>
              <dd>
                <ol>
                  {scenario.spec.steps.map((step, index) => (
                    <li key={`${index}-${step}`}>{step}</li>
                  ))}
                </ol>
              </dd>
            </div>
            <div>
              <dt>Success criteria</dt>
              <dd>{scenario.spec.successCriteria ?? "Not provided"}</dd>
            </div>
            <div>
              <dt>Expected control</dt>
              <dd>{scenario.spec.expectedControl}</dd>
            </div>
            <div>
              <dt>Evidence requirements</dt>
              <dd>
                <ul>
                  {scenario.spec.evidenceRequirements.map((item, index) => (
                    <li key={`${index}-${item}`}>{item}</li>
                  ))}
                </ul>
              </dd>
            </div>
            {scenario.spec.collectorEvidence ? (
              <div>
                <dt>Collector evidence</dt>
                <dd>{scenario.spec.collectorEvidence}</dd>
              </div>
            ) : null}
          </dl>
        </div>
      ) : null}
    </article>
  );
}
