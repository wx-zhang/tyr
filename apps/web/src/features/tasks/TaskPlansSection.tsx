import type { TaskPlans } from "../../api/client";

export function TaskPlansSection({
  plans,
  isLoading,
  isError,
}: {
  plans: TaskPlans | undefined;
  isLoading: boolean;
  isError: boolean;
}) {
  if (isLoading) {
    return (
      <p className="secondary" role="status">
        Loading supporting plans…
      </p>
    );
  }
  if (isError) {
    return (
      <p className="secondary" role="alert">
        Could not load supporting plans.
      </p>
    );
  }
  if (!plans) return null;

  const hasAny = plans.discovery || plans.methodology || plans.evaluation;
  if (!hasAny) {
    return <p className="secondary">No discovery, methodology, or evaluation plans.</p>;
  }

  return (
    <div className="plan-accordion">
      {plans.discovery ? (
        <details className="plan-details">
          <summary>Discovery</summary>
          <div className="plan-body reading-width">
            <p className="plan-prose">{plans.discovery.prompt}</p>
            {plans.discovery.outputFields?.length ? (
              <p className="secondary mono">
                Output fields: {plans.discovery.outputFields.join(", ")}
              </p>
            ) : null}
          </div>
        </details>
      ) : null}
      {plans.methodology ? (
        <details className="plan-details">
          <summary>Methodology</summary>
          <div className="plan-body reading-width">
            <h3>System brief</h3>
            <p className="plan-prose">{plans.methodology.systemBrief}</p>
            <h3>Unsticking guidance</h3>
            <p className="plan-prose">{plans.methodology.unstickingGuidance}</p>
            <h3>Testing methodology</h3>
            <p className="plan-prose">{plans.methodology.testingMethodology}</p>
          </div>
        </details>
      ) : null}
      {plans.evaluation ? (
        <details className="plan-details">
          <summary>Evaluation</summary>
          <div className="plan-body reading-width">
            <p className="plan-prose">{plans.evaluation.prompt}</p>
          </div>
        </details>
      ) : null}
    </div>
  );
}
