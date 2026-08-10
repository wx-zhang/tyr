import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchDatasets } from "../../api/client";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";

export function DatasetPage() {
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: fetchDatasets });
  return (
    <section className="section-stack">
      <PageHeader
        eyebrow="Authoring sources"
        title="Datasets"
        description="Versioned Tyr red-team scenarios used to create reproducible experiment snapshots."
        actions={
          <Link className="button button-primary" to="/experiments/new">
            Execute
          </Link>
        }
      />

      {datasets.isLoading ? (
        <div className="card empty-state" role="status">
          <div>
            <h2>Loading datasets</h2>
            <p>Reading the configured dataset catalog…</p>
          </div>
        </div>
      ) : datasets.isError ? (
        <div className="card empty-state" role="alert">
          <div>
            <h2>Unable to load datasets</h2>
            <p>Check the API connection and try again.</p>
          </div>
        </div>
      ) : datasets.data?.length === 0 ? (
        <div className="card empty-state">
          <div>
            <h2>No datasets available</h2>
            <p>
              Add a validated dataset to the repository before starting an
              experiment.
            </p>
          </div>
        </div>
      ) : (
        <div className="table-card">
          <div className="table-scroll">
            <table>
              <caption className="sr-only">Available GAMR datasets</caption>
              <thead>
                <tr>
                  <th scope="col">Dataset ID</th>
                  <th scope="col">Title</th>
                  <th scope="col">Version</th>
                  <th scope="col">Cases</th>
                  <th scope="col">Default mode</th>
                </tr>
              </thead>
              <tbody>
                {(datasets.data ?? []).map((dataset) => (
                  <tr key={dataset.metadata.id}>
                    <td className="mono table-primary">
                      <Link
                        className="session-title"
                        to={`/datasets/${encodeURIComponent(dataset.metadata.id)}`}
                      >
                        {dataset.metadata.id}
                      </Link>
                    </td>
                    <td className="table-primary">
                      <Link
                        className="session-title"
                        to={`/datasets/${encodeURIComponent(dataset.metadata.id)}`}
                      >
                        {dataset.metadata.title}
                      </Link>
                    </td>
                    <td className="mono">{dataset.metadata.version}</td>
                    <td className="mono tabular">
                      {dataset.spec.cases.length}
                    </td>
                    <td>
                      <StatusBadge
                        label={
                          dataset.spec.defaults.actionMode ===
                          "approval_required"
                            ? "Actions Allowed"
                            : "Read-only"
                        }
                        tone={
                          dataset.spec.defaults.actionMode ===
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
