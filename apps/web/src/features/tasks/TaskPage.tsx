import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTasks } from "../../api/client";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";

export function TaskPage() {
  const tasks = useQuery({ queryKey: ["tasks"], queryFn: fetchTasks });
  return (
    <section className="section-stack">
      <PageHeader
        eyebrow="Task catalog"
        title="Tasks"
        description="Versioned Tyr red-team Scenarios used to create reproducible Experiment Presets."
        actions={
          <Link className="button button-primary" to="/experiments/new">
            Run Experiment
          </Link>
        }
      />

      {tasks.isLoading ? (
        <div className="card empty-state" role="status">
          <div>
            <h2>Loading Tasks</h2>
            <p>Reading the configured Task catalog…</p>
          </div>
        </div>
      ) : tasks.isError ? (
        <div className="card empty-state" role="alert">
          <div>
            <h2>Unable to load Tasks</h2>
            <p>Check the API connection and try again.</p>
          </div>
        </div>
      ) : tasks.data?.length === 0 ? (
        <div className="card empty-state">
          <div>
            <h2>No Tasks available</h2>
            <p>Add a validated Task before starting an Experiment.</p>
          </div>
        </div>
      ) : (
        <div className="table-card">
          <div className="table-scroll">
            <table>
              <caption className="sr-only">Available GAMR tasks</caption>
              <thead>
                <tr>
                  <th scope="col">Task ID</th>
                  <th scope="col">Title</th>
                  <th scope="col">Version</th>
                  <th scope="col">Scenarios</th>
                  <th scope="col">Default mode</th>
                </tr>
              </thead>
              <tbody>
                {(tasks.data ?? []).map((task) => (
                  <tr key={task.metadata.id}>
                    <td className="mono table-primary">
                      <Link
                        className="session-title"
                        to={`/tasks/${encodeURIComponent(task.metadata.id)}`}
                      >
                        {task.metadata.id}
                      </Link>
                    </td>
                    <td className="table-primary">
                      <Link
                        className="session-title"
                        to={`/tasks/${encodeURIComponent(task.metadata.id)}`}
                      >
                        {task.metadata.title}
                      </Link>
                    </td>
                    <td className="mono">{task.metadata.version}</td>
                    <td className="mono tabular">
                      {task.spec.scenarios.length}
                    </td>
                    <td>
                      <StatusBadge
                        label={
                          task.spec.defaults.actionMode ===
                          "approval_required"
                            ? "Approval-gated"
                            : "Read-only"
                        }
                        tone={
                          task.spec.defaults.actionMode ===
                          "approval_required"
                            ? "warning"
                            : "neutral"
                        }
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
