import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  archiveScientistScenario,
  fetchScientistScenarios,
  restoreScientistScenario,
  type ScientistScenario,
  type ScientistScenarioResult,
  type ScientistScenarioState,
} from "../../api/client";
import { StatusBadge } from "../../components/StatusBadge";
import { ScientistScenarioDetail } from "./ScientistScenarioDetail";

const results: Array<{ value: ScientistScenarioResult | ""; label: string }> = [
  { value: "", label: "All results" },
  { value: "vulnerable", label: "Vulnerable" },
  { value: "protected", label: "Protected" },
  { value: "inconclusive", label: "Inconclusive" },
  { value: "not_applicable", label: "Not applicable" },
  { value: "pending", label: "Pending" },
  { value: "unavailable", label: "Unavailable" },
];

function resultTone(
  value: ScientistScenarioResult,
): "danger" | "success" | "warning" | "neutral" {
  if (value === "vulnerable") return "danger";
  if (value === "protected") return "success";
  if (value === "pending") return "warning";
  return "neutral";
}

function resultLabel(value: ScientistScenarioResult): string {
  return results.find((item) => item.value === value)?.label ?? value;
}

function belongsToTask(entry: ScientistScenario, taskId: string): boolean {
  const task = entry.task.replaceAll("\\", "/");
  return task === taskId || task === `tasks/${taskId}` || task.endsWith(`/${taskId}`);
}

export function ScientistScenarioPage({ taskId }: { taskId: string }) {
  const [state, setState] = useState<ScientistScenarioState>("active");
  const [result, setResult] = useState<ScientistScenarioResult | undefined>();
  const queryClient = useQueryClient();
  const scenarios = useQuery({
    queryKey: ["scientist-scenarios", state, result],
    queryFn: () => fetchScientistScenarios(state, result),
  });
  const archive = useMutation({
    mutationFn: (entry: ScientistScenario) =>
      state === "active"
        ? archiveScientistScenario(entry.runId, entry.artifactId)
        : restoreScientistScenario(entry.runId, entry.artifactId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["scientist-scenarios"] }),
  });

  const selectState = (next: ScientistScenarioState) => {
    setState(next);
    setResult(undefined);
  };
  const entries = (scenarios.data ?? []).filter((entry) =>
    belongsToTask(entry, taskId),
  );
  const [selectedKey, setSelectedKey] = useState<string>();
  const selected = entries.find(
    (entry) => `${entry.runId}:${entry.artifactId}` === selectedKey,
  );

  useEffect(() => {
    if (!selected || selectedKey === undefined) {
      setSelectedKey(
        entries[0] ? `${entries[0].runId}:${entries[0].artifactId}` : undefined,
      );
    }
  }, [entries, selected, selectedKey]);

  return (
    <section className="scientist-catalog">
      <div className="scientist-catalog-toolbar">
        <div
          className="scientist-catalog-tabs"
          role="tablist"
          aria-label="Scenario archive state"
        >
          {(["active", "archived"] as const).map((value) => (
            <button
              className="catalog-tab"
              key={value}
              type="button"
              role="tab"
              aria-selected={state === value}
              onClick={() => selectState(value)}
            >
              {value === "active" ? "Active" : "Archived"}
            </button>
          ))}
        </div>
        <label className="catalog-filter">
          <span>Result</span>
          <select
            value={result ?? ""}
            onChange={(event) =>
              setResult(
                (event.target.value || undefined) as
                  ScientistScenarioResult | undefined,
              )
            }
          >
            {results.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {scenarios.isLoading ? (
        <div className="card empty-state" role="status">
          <div>
            <h2>Loading scientist scenarios</h2>
            <p>Reading retained run evidence…</p>
          </div>
        </div>
      ) : scenarios.isError ? (
        <div className="card empty-state" role="alert">
          <div>
            <h2>Unable to load scientist scenarios</h2>
            <p>Check the API connection and try again.</p>
          </div>
        </div>
      ) : entries.length === 0 ? (
        <div className="card empty-state">
          <div>
            <h2>No scientist scenarios</h2>
            <p>
              {state === "active"
                ? "No active generated scenarios match this view."
                : "No archived generated scenarios match this view."}
            </p>
          </div>
        </div>
      ) : (
        <div className="scientist-catalog-layout">
          <nav className="scientist-catalog-nav" aria-label="Scientist scenarios">
            <ul className="case-nav-list">
              {entries.map((entry) => {
                const key = `${entry.runId}:${entry.artifactId}`;
                const scenario = entry.scenario;
                return (
                  <li key={key}>
                    <button
                      className={`scientist-catalog-nav-link${selectedKey === key ? " is-active" : ""}`}
                      type="button"
                      aria-current={selectedKey === key ? "true" : undefined}
                      onClick={() => setSelectedKey(key)}
                    >
                      <span className="choice-title">{scenario.metadata.title}</span>
                      <span className="choice-description mono">
                        {scenario.metadata.id}
                      </span>
                      <StatusBadge
                        label={resultLabel(entry.resultState)}
                        tone={resultTone(entry.resultState)}
                      />
                    </button>
                  </li>
                );
              })}
            </ul>
          </nav>
          <div className="scientist-catalog-detail">
            {selected ? (
              <ScientistScenarioDetail
                entry={selected}
                state={state}
                pending={archive.isPending}
                onArchive={() => archive.mutate(selected)}
              />
            ) : null}
          </div>
        </div>
      )}
    </section>
  );
}
