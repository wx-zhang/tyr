import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  fetchDataset,
  fetchDatasetCases,
  fetchDatasetPlans,
  type DatasetPlans,
  type DatasetScenario,
} from "../../api/client";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";

function modeLabel(mode: string | undefined): string {
  if (mode === "approval_required") return "Actions Allowed";
  return "Read-only";
}

function variableSummary(variable: {
  source: string;
  default?: string;
  value?: string;
  field?: string;
}): string {
  if (variable.source === "literal" && variable.value != null) {
    return variable.value;
  }
  if (variable.source === "discovery" && variable.field) {
    return `discovery.${variable.field}`;
  }
  if (variable.default != null) {
    return `default: ${variable.default}`;
  }
  return variable.source;
}

function PlansSection({
  plans,
  isLoading,
  isError,
}: {
  plans: DatasetPlans | undefined;
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

function CaseDetail({ scenario }: { scenario: DatasetScenario }) {
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

export function DatasetDetailPage() {
  const { datasetId, caseId } = useParams();

  const dataset = useQuery({
    queryKey: ["dataset", datasetId],
    queryFn: () => fetchDataset(datasetId!),
    enabled: Boolean(datasetId),
  });

  const cases = useQuery({
    queryKey: ["dataset-cases", datasetId],
    queryFn: () => fetchDatasetCases(datasetId!),
    enabled: Boolean(datasetId),
  });

  const plans = useQuery({
    queryKey: ["dataset-plans", datasetId],
    queryFn: () => fetchDatasetPlans(datasetId!),
    enabled: Boolean(datasetId),
  });

  const scenarios = cases.data ?? [];
  const defaultCaseIds = new Set(dataset.data?.spec.defaults.defaultCaseIds ?? []);
  const selected =
    scenarios.find((item) => item.metadata.id === caseId) ??
    scenarios.find((item) => defaultCaseIds.has(item.metadata.id)) ??
    scenarios[0];
  const actionMode = dataset.data?.spec.defaults.actionMode;
  const variables = dataset.data?.spec.variables ?? {};
  const variableEntries = Object.entries(variables);

  return (
    <section className="section-stack">
      <PageHeader
        eyebrow="Authoring sources"
        title={dataset.data?.metadata.title ?? datasetId ?? "Dataset"}
        description={
          dataset.data
            ? `${dataset.data.metadata.id} · v${dataset.data.metadata.version}`
            : "Review dataset metadata and test cases."
        }
        actions={
          <div className="button-row">
            <Link className="button button-secondary" to="/datasets">
              All datasets
            </Link>
            <Link className="button button-primary" to="/experiments/new">
              Execute
            </Link>
          </div>
        }
      />

      {dataset.isLoading ? (
        <div className="card empty-state" role="status">
          <div>
            <h2>Loading dataset</h2>
            <p>Reading the dataset manifest…</p>
          </div>
        </div>
      ) : dataset.isError ? (
        <div className="card empty-state" role="alert">
          <div>
            <h2>Unable to load dataset</h2>
            <p>Check the dataset ID and API connection, then try again.</p>
            <Link className="button button-secondary" to="/datasets">
              Back to datasets
            </Link>
          </div>
        </div>
      ) : (
        <>
          <article className="card">
            <div className="card-header">
              <div>
                <p className="eyebrow">Overview</p>
                <h2>Dataset details</h2>
              </div>
              <StatusBadge
                label={modeLabel(actionMode)}
                tone={actionMode === "approval_required" ? "warning" : "neutral"}
              />
            </div>
            <dl className="detail-list">
              <div className="detail-row">
                <dt>Dataset ID</dt>
                <dd className="mono">{dataset.data?.metadata.id ?? "—"}</dd>
              </div>
              <div className="detail-row">
                <dt>Version</dt>
                <dd className="mono">{dataset.data?.metadata.version ?? "—"}</dd>
              </div>
              <div className="detail-row">
                <dt>Cases</dt>
                <dd className="mono tabular">
                  {dataset.data?.spec.cases.length ?? scenarios.length}
                </dd>
              </div>
              <div className="detail-row">
                <dt>Default mode</dt>
                <dd>{modeLabel(actionMode)}</dd>
              </div>
              <div className="detail-row">
                <dt>Max turns</dt>
                <dd className="mono tabular">
                  {dataset.data?.spec.defaults.maxTurns ?? "—"}
                </dd>
              </div>
              <div className="detail-row">
                <dt>Default cases</dt>
                <dd className="mono">
                  {(dataset.data?.spec.defaults.defaultCaseIds ?? []).length > 0
                    ? (dataset.data?.spec.defaults.defaultCaseIds ?? []).join(", ")
                    : "None"}
                </dd>
              </div>
            </dl>

            {variableEntries.length > 0 ? (
              <div className="dataset-variables">
                <h3>Variables</h3>
                <div className="table-scroll">
                  <table>
                    <caption className="sr-only">Dataset template variables</caption>
                    <thead>
                      <tr>
                        <th scope="col">Name</th>
                        <th scope="col">Source</th>
                        <th scope="col">Binding</th>
                      </tr>
                    </thead>
                    <tbody>
                      {variableEntries.map(([name, variable]) => (
                        <tr key={name}>
                          <td className="mono table-primary">{name}</td>
                          <td className="mono">{variable.source}</td>
                          <td className="mono">{variableSummary(variable)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </article>

          <article className="card">
            <div className="card-header">
              <div>
                <p className="eyebrow">Supporting plans</p>
                <h2>Discovery, methodology, evaluation</h2>
              </div>
            </div>
            <PlansSection
              plans={plans.data}
              isLoading={plans.isLoading}
              isError={plans.isError}
            />
          </article>

          <article className="card">
            <div className="card-header">
              <div>
                <p className="eyebrow">Scenarios</p>
                <h2>Test cases</h2>
              </div>
              <span className="secondary mono tabular">
                {scenarios.length} case{scenarios.length === 1 ? "" : "s"}
              </span>
            </div>

            {cases.isLoading ? (
              <p className="secondary" role="status">
                Loading cases…
              </p>
            ) : cases.isError ? (
              <p className="secondary" role="alert">
                Could not load cases for this dataset.
              </p>
            ) : scenarios.length === 0 ? (
              <p className="secondary">No cases in this dataset.</p>
            ) : (
              <div className="dataset-case-layout">
                <nav className="case-nav" aria-label="Dataset cases">
                  <ul className="case-nav-list">
                    {scenarios.map((scenario) => {
                      const id = scenario.metadata.id;
                      const isActive = selected?.metadata.id === id;
                      const isDefault = defaultCaseIds.has(id);
                      return (
                        <li key={id}>
                          <Link
                            to={`/datasets/${encodeURIComponent(datasetId!)}/cases/${encodeURIComponent(id)}`}
                            className={`case-nav-link${isActive ? " is-active" : ""}`}
                            aria-current={isActive ? "page" : undefined}
                          >
                            <span className="choice-title">{scenario.metadata.title}</span>
                            <span className="choice-description mono">{id}</span>
                            <span className="session-meta">
                              {scenario.metadata.category ? (
                                <span>{scenario.metadata.category}</span>
                              ) : null}
                              {isDefault ? (
                                <StatusBadge label="Default" tone="info" />
                              ) : null}
                            </span>
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                </nav>
                <div className="case-panel">
                  {selected ? (
                    <CaseDetail scenario={selected} />
                  ) : caseId ? (
                    <p className="secondary" role="alert">
                      Case <span className="mono">{caseId}</span> was not found in
                      this dataset.
                    </p>
                  ) : (
                    <p className="secondary">Select a case to review its details.</p>
                  )}
                </div>
              </div>
            )}
          </article>
        </>
      )}
    </section>
  );
}
