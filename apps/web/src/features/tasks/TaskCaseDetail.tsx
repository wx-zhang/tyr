import type { Scenario } from "../../api/client";
import { StatusBadge } from "../../components/StatusBadge";

export function ScenarioDetail({ scenario }: { scenario: Scenario }) {
  return (
    <div className="case-detail">
      <div className="case-detail-header">
        <div>
          <h3>{scenario.metadata.title}</h3>
          <p className="session-meta">
            <span className="mono">{scenario.metadata.id}</span>
            {scenario.metadata.category ? (
              <span className="secondary">{scenario.metadata.category}</span>
            ) : null}
          </p>
        </div>
        {scenario.metadata.tags?.length ? (
          <div className="tag-row">
            {scenario.metadata.tags.map((tag) => (
              <StatusBadge key={tag} label={tag} tone="neutral" />
            ))}
          </div>
        ) : null}
      </div>

      <section className="case-section">
        <h4>Objective</h4>
        <p className="plan-prose reading-width">{scenario.spec.objective}</p>
      </section>

      <section className="case-section">
        <h4>Steps</h4>
        <ol className="case-steps reading-width">
          {scenario.spec.steps.map((step, index) => (
            <li key={`${index}-${step.slice(0, 24)}`}>{step}</li>
          ))}
        </ol>
      </section>

      {scenario.spec.successCriteria ? (
        <section className="case-section">
          <h4>Success criteria</h4>
          <p className="plan-prose reading-width">{scenario.spec.successCriteria}</p>
        </section>
      ) : null}

      <section className="case-section">
        <h4>Expected control</h4>
        <p className="plan-prose reading-width">{scenario.spec.expectedControl}</p>
      </section>

      <section className="case-section">
        <h4>Evidence requirements</h4>
        <ul className="case-evidence reading-width">
          {scenario.spec.evidenceRequirements.map((item, index) => (
            <li key={`${index}-${item.slice(0, 24)}`}>{item}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
