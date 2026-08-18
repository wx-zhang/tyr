import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTask, fetchTaskCases, fetchTaskPlans } from "../../api/client";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";
import { TaskCaseDetail } from "./TaskCaseDetail";
import { TaskPlansSection } from "./TaskPlansSection";
import { TaskReferenceCard } from "./TaskReferenceCard";

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

export function TaskDetailPage() {
  const { taskId, caseId } = useParams();

  const task = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => fetchTask(taskId!),
    enabled: Boolean(taskId),
  });

  const cases = useQuery({
    queryKey: ["task-cases", taskId],
    queryFn: () => fetchTaskCases(taskId!),
    enabled: Boolean(taskId),
  });

  const plans = useQuery({
    queryKey: ["task-plans", taskId],
    queryFn: () => fetchTaskPlans(taskId!),
    enabled: Boolean(taskId),
  });

  const scenarios = cases.data ?? [];
  const defaultCaseIds = new Set(task.data?.spec.defaults.defaultCaseIds ?? []);
  const selected =
    scenarios.find((item) => item.metadata.id === caseId) ??
    scenarios.find((item) => defaultCaseIds.has(item.metadata.id)) ??
    scenarios[0];
  const actionMode = task.data?.spec.defaults.actionMode;
  const variableEntries = Object.entries(task.data?.spec.variables ?? {});

  return (
    <section className="section-stack">
      <PageHeader
        eyebrow="Authoring sources"
        title={task.data?.metadata.title ?? taskId ?? "Task"}
        description={
          task.data
            ? `${task.data.metadata.id} · v${task.data.metadata.version}`
            : "Review task metadata and test cases."
        }
        actions={
          <div className="button-row">
            <Link className="button button-secondary" to="/tasks">
              All tasks
            </Link>
            <Link className="button button-primary" to="/experiments/new">
              Execute
            </Link>
          </div>
        }
      />

      {task.isLoading ? (
        <div className="card empty-state" role="status">
          <div>
            <h2>Loading task</h2>
            <p>Reading the task manifest…</p>
          </div>
        </div>
      ) : task.isError ? (
        <div className="card empty-state" role="alert">
          <div>
            <h2>Unable to load task</h2>
            <p>Check the task ID and API connection, then try again.</p>
            <Link className="button button-secondary" to="/tasks">
              Back to tasks
            </Link>
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
                <dt>Cases</dt>
                <dd className="mono tabular">
                  {task.data?.spec.cases.length ?? scenarios.length}
                </dd>
              </div>
              <div className="detail-row">
                <dt>Default mode</dt>
                <dd>{modeLabel(actionMode)}</dd>
              </div>
              <div className="detail-row">
                <dt>Max turns</dt>
                <dd className="mono tabular">
                  {task.data?.spec.defaults.maxTurns ?? "—"}
                </dd>
              </div>
              <div className="detail-row">
                <dt>Default cases</dt>
                <dd className="mono">
                  {(task.data?.spec.defaults.defaultCaseIds ?? []).length > 0
                    ? (task.data?.spec.defaults.defaultCaseIds ?? []).join(", ")
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
            <TaskPlansSection
              plans={plans.data}
              isLoading={plans.isLoading}
              isError={plans.isError}
            />
          </article>

          <TaskReferenceCard reference={plans.data?.reference} />

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
                Could not load cases for this task.
              </p>
            ) : scenarios.length === 0 ? (
              <p className="secondary">No cases in this task.</p>
            ) : (
              <div className="task-case-layout">
                <nav className="case-nav" aria-label="Task cases">
                  <ul className="case-nav-list">
                    {scenarios.map((scenario) => {
                      const id = scenario.metadata.id;
                      const isActive = selected?.metadata.id === id;
                      const isDefault = defaultCaseIds.has(id);
                      return (
                        <li key={id}>
                          <Link
                            to={`/tasks/${encodeURIComponent(taskId!)}/cases/${encodeURIComponent(id)}`}
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
                    <TaskCaseDetail scenario={selected} />
                  ) : caseId ? (
                    <p className="secondary" role="alert">
                      Case <span className="mono">{caseId}</span> was not found in
                      this task.
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
