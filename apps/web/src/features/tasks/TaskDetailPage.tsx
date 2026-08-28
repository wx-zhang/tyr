import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTask, fetchTaskScenarios, fetchTaskPlans } from "../../api/client";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";
import { ScenarioDetail } from "./TaskCaseDetail";
import { TaskPlansSection } from "./TaskPlansSection";
import { TaskReferenceCard } from "./TaskReferenceCard";
import { ScientistScenarioPage } from "../scientist-scenarios/ScientistScenarioPage";

function modeLabel(mode: string | undefined): string {
  if (mode === "approval_required") return "Approval-gated";
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

export function TaskDetailPage() {
  const { taskId, scenarioId: canonicalScenarioId, caseId } = useParams();
  const scenarioId = canonicalScenarioId ?? caseId;
  const [scenarioTab, setScenarioTab] = useState<"scenarios" | "research">("scenarios");

  const task = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => fetchTask(taskId!),
    enabled: Boolean(taskId),
  });

  const scenariosQuery = useQuery({
    queryKey: ["task-scenarios", taskId],
    queryFn: () => fetchTaskScenarios(taskId!),
    enabled: Boolean(taskId),
  });

  const plans = useQuery({
    queryKey: ["task-plans", taskId],
    queryFn: () => fetchTaskPlans(taskId!),
    enabled: Boolean(taskId),
  });
  const scenarios = scenariosQuery.data ?? [];
  const defaultScenarioIds = new Set(
    task.data?.spec.defaults.defaultScenarioIds ?? task.data?.spec.defaults.defaultCaseIds ?? [],
  );
  const selected =
    scenarios.find((item) => item.metadata.id === scenarioId) ??
    scenarios.find((item) => defaultScenarioIds.has(item.metadata.id)) ??
    scenarios[0];
  const actionMode = task.data?.spec.defaults.actionMode;
  const variableEntries = Object.entries(task.data?.spec.variables ?? {});

  return (
    <section className="section-stack">
      <PageHeader
        eyebrow="Task"
        title={task.data?.metadata.title ?? taskId ?? "Task"}
        description={
          task.data
            ? `${task.data.metadata.id} · v${task.data.metadata.version}`
            : "Review Task metadata and Scenarios."
        }
        actions={
          <div className="button-row">
            <Link className="button button-secondary" to="/tasks">All Tasks</Link>
            <Link className="button button-primary" to="/experiments/new">Run Experiment</Link>
          </div>
        }
      />

      {task.isLoading ? (
        <div className="card empty-state" role="status">
          <div><h2>Loading Task</h2><p>Reading the Task manifest…</p></div>
        </div>
      ) : task.isError ? (
        <div className="card empty-state" role="alert">
          <div>
            <h2>Unable to load Task</h2>
            <p>Check the Task ID and API connection, then try again.</p>
            <Link className="button button-secondary" to="/tasks">Back to Tasks</Link>
          </div>
        </div>
      ) : (
        <>
          <article className="card">
            <div className="card-header">
              <div>
                <p className="eyebrow">Overview</p>
                <h2>Task details</h2>
              </div>
              <StatusBadge
                label={modeLabel(actionMode)}
                tone={actionMode === "approval_required" ? "warning" : "neutral"}
              />
            </div>
            <dl className="detail-list">
              <div className="detail-row">
                <dt>Task ID</dt>
                <dd className="mono">{task.data?.metadata.id ?? "—"}</dd>
              </div>
              <div className="detail-row">
                <dt>Version</dt>
                <dd className="mono">{task.data?.metadata.version ?? "—"}</dd>
              </div>
              <div className="detail-row">
                <dt>Scenarios</dt>
                <dd className="mono tabular">{task.data?.spec.scenarios.length ?? scenarios.length}</dd>
              </div>
              <div className="detail-row">
                <dt>Default mode</dt>
                <dd>{modeLabel(actionMode)}</dd>
              </div>
              <div className="detail-row">
                <dt>Max turns</dt>
                <dd className="mono tabular">{task.data?.spec.defaults.maxTurns ?? "—"}</dd>
              </div>
              <div className="detail-row">
                <dt>Default Scenarios</dt>
                <dd className="mono">
                  {(task.data?.spec.defaults.defaultScenarioIds ?? []).length > 0
                    ? (task.data?.spec.defaults.defaultScenarioIds ?? []).join(", ")
                    : "None"}
                </dd>
              </div>
            </dl>

            {variableEntries.length > 0 ? (
              <div className="task-variables">
                <h3>Variables</h3>
                <div className="table-scroll">
                  <table>
                    <caption className="sr-only">Task template variables</caption>
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
                          <td className="mono cell-wrap">{variableSummary(variable)}</td>
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
            <TaskPlansSection
              plans={plans.data}
              isLoading={plans.isLoading}
              isError={plans.isError}
            />
          </article>

          <TaskReferenceCard reference={plans.data?.reference} />

          <article className="card">
            <div className="card-header">
              <div><p className="eyebrow">Scenarios</p><h2>Task Scenarios</h2></div>
              <span className="secondary mono tabular">{scenarios.length} Scenario{scenarios.length === 1 ? "" : "s"}</span>
            </div>
            <div className="task-scenario-tabs" role="tablist" aria-label="Scenario source">
              <button className="catalog-tab" type="button" role="tab" aria-selected={scenarioTab === "scenarios"} onClick={() => setScenarioTab("scenarios")}>Task Scenarios</button>
              <button className="catalog-tab" type="button" role="tab" aria-selected={scenarioTab === "research"} onClick={() => setScenarioTab("research")}>Adversarial Researcher Scenarios</button>
            </div>
            {scenarioTab === "research" ? (
              <ScientistScenarioPage taskId={taskId!} />
            ) : scenariosQuery.isLoading ? (
              <p className="secondary" role="status">Loading Scenarios…</p>
            ) : scenariosQuery.isError ? (
              <p className="secondary" role="alert">Could not load Scenarios for this Task.</p>
            ) : scenarios.length === 0 ? (
              <p className="secondary">No Scenarios in this Task.</p>
            ) : (
              <div className="task-case-layout">
                <nav className="case-nav" aria-label="Task Scenarios">
                  <ul className="case-nav-list">
                    {scenarios.map((scenario) => {
                      const id = scenario.metadata.id;
                      const isActive = selected?.metadata.id === id;
                      const isDefault = defaultScenarioIds.has(id);
                      return (
                        <li key={id}>
                          <Link to={`/tasks/${encodeURIComponent(taskId!)}/scenarios/${encodeURIComponent(id)}`} className={`case-nav-link${isActive ? " is-active" : ""}`} aria-current={isActive ? "page" : undefined}>
                            <span className="choice-title">{scenario.metadata.title}</span>
                            <span className="choice-description mono">{id}</span>
                            <span className="session-meta">
                              {scenario.metadata.category ? <span>{scenario.metadata.category}</span> : null}
                              {isDefault ? <StatusBadge label="Default" tone="info" /> : null}
                            </span>
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                </nav>
                <div className="case-panel">
                  {selected ? <ScenarioDetail scenario={selected} /> : scenarioId ? <p className="secondary" role="alert">Scenario <span className="mono">{scenarioId}</span> was not found in this Task.</p> : <p className="secondary">Select a Scenario to review its details.</p>}
                </div>
              </div>
            )}
          </article>
        </>
      )}
    </section>
  );
}
