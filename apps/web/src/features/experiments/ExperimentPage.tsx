import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  createExperiment,
  fetchDatasetCases,
  fetchDatasets,
  scenarioToCase,
  type Dataset,
} from "../../api/client";
import { PageHeader } from "../../components/PageHeader";
import { CaseChecklist } from "./CaseChecklist";
import { ScientistHistoryPanel } from "./ScientistHistoryPanel";

function defaultCaseSelection(
  dataset: Dataset | undefined,
  caseIds: string[],
): string[] {
  if (!dataset) return [];
  const defaults = dataset.spec.defaults.defaultCaseIds ?? [];
  const known = new Set(caseIds);
  const fromDefaults = defaults.filter((id) => known.has(id));
  if (fromDefaults.length > 0) return fromDefaults;
  return caseIds;
}

function defaultExperimentName(datasetTitle: string): string {
  const stamp = new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date());
  return `${datasetTitle} · ${stamp}`;
}

function boundedCount(value: string): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 0;
  return Math.min(100, Math.max(0, Math.floor(parsed)));
}

export function ExperimentPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [executeTestCases, setExecuteTestCases] = useState(true);
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([]);
  const [allowActions, setAllowActions] = useState(true);
  const [scientistIterationsInput, setScientistIterationsInput] = useState("0");
  const [historyTestRunsInput, setHistoryTestRunsInput] = useState("10");
  const [historyScientistRunsInput, setHistoryScientistRunsInput] =
    useState("5");
  const scientistIterations = useMemo(() => {
    const parsed = Number(scientistIterationsInput);
    return Number.isFinite(parsed) ? Math.max(0, Math.floor(parsed)) : 0;
  }, [scientistIterationsInput]);
  const historyTestRuns = useMemo(
    () => boundedCount(historyTestRunsInput),
    [historyTestRunsInput],
  );
  const historyScientistRuns = useMemo(
    () => boundedCount(historyScientistRunsInput),
    [historyScientistRunsInput],
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [casesOpen, setCasesOpen] = useState(true);

  const datasets = useQuery({
    queryKey: ["datasets"],
    queryFn: fetchDatasets,
  });

  useEffect(() => {
    if (datasetId || !datasets.data?.length) return;
    if (datasets.data.length === 1) {
      setDatasetId(datasets.data[0].metadata.id);
    }
  }, [datasets.data, datasetId]);

  const selectedDataset = useMemo(
    () => datasets.data?.find((item) => item.metadata.id === datasetId),
    [datasets.data, datasetId],
  );

  const cases = useQuery({
    queryKey: ["dataset-cases", datasetId],
    queryFn: () => fetchDatasetCases(datasetId),
    enabled: Boolean(datasetId) && executeTestCases,
  });

  useEffect(() => {
    if (!cases.data || !executeTestCases) return;
    setSelectedCaseIds(
      defaultCaseSelection(
        selectedDataset,
        cases.data.map((item) => item.metadata.id),
      ),
    );
  }, [cases.data, executeTestCases, selectedDataset]);

  const toggleCase = (caseId: string) => {
    setSelectedCaseIds((current) =>
      current.includes(caseId)
        ? current.filter((id) => id !== caseId)
        : [...current, caseId],
    );
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!datasetId) {
      setError("Select a dataset.");
      return;
    }
    if (executeTestCases && selectedCaseIds.length === 0) {
      setError("Select at least one test case or turn off Execute Test Cases.");
      return;
    }
    if (!executeTestCases && scientistIterations === 0) {
      setError(
        "Set scientist iterations above 0 for scientist-only execution.",
      );
      return;
    }
    const datasetTitle = selectedDataset?.metadata.title ?? datasetId;
    const experimentName = name.trim() || defaultExperimentName(datasetTitle);
    setSubmitting(true);
    try {
      const experiment = await createExperiment({
        name: experimentName,
        dataset: datasetId,
        actionMode: allowActions ? "approval_required" : "read_only",
        caseIds: executeTestCases ? selectedCaseIds : [],
        scientistIterations,
        historyTestRuns,
        historyScientistRuns,
      });
      if (!experiment.id) throw new Error("Experiment was not created");
      navigate(`/experiments/${experiment.id}`);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not create experiment",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const caseList = (cases.data ?? []).map(scenarioToCase);
  const canSubmit =
    Boolean(datasetId) &&
    (executeTestCases ? selectedCaseIds.length > 0 : scientistIterations > 0) &&
    !submitting &&
    !cases.isLoading;

  return (
    <section className="section-stack">
      <PageHeader
        eyebrow="Experiment execution"
        title="Execute experiment"
        description="Choose a dataset and execution mode, then start a live red-team run against Tyr."
        actions={
          <Link className="button button-secondary" to="/datasets">
            Browse datasets
          </Link>
        }
      />

      <div
        className={`execute-layout${executeTestCases && !casesOpen ? " execute-layout-collapsed" : ""}`}
      >
        <form className="card form-card" onSubmit={submit}>
          <div className="field-group">
            <label htmlFor="experiment-name">Name</label>
            <input
              id="experiment-name"
              name="name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Optional · defaults to dataset and time"
            />
          </div>

          <label className="choice-card case-choice">
            <input
              type="checkbox"
              checked={executeTestCases}
              onChange={(event) => {
                const next = event.target.checked;
                setExecuteTestCases(next);
                setError(null);
                setCasesOpen(true);
                if (!next) {
                  setSelectedCaseIds([]);
                } else if (cases.data) {
                  setSelectedCaseIds(
                    defaultCaseSelection(
                      selectedDataset,
                      cases.data.map((item) => item.metadata.id),
                    ),
                  );
                }
              }}
              aria-label="Execute Test Cases"
            />
            <span>
              <span className="choice-title" aria-hidden="true">
                Execute Test Cases
              </span>
              <span className="choice-description">
                Run the selected dataset cases before the scientist stage.
              </span>
            </span>
          </label>

          {executeTestCases ? (
            <div className="field-group">
              <label htmlFor="experiment-dataset">Dataset</label>
              <select
                id="experiment-dataset"
                name="dataset"
                value={datasetId}
                onChange={(event) => {
                  setDatasetId(event.target.value);
                  setSelectedCaseIds([]);
                  setError(null);
                }}
                required
                disabled={datasets.isLoading}
              >
                <option value="" disabled>
                  {datasets.isLoading
                    ? "Loading datasets…"
                    : "Select a validated dataset"}
                </option>
                {(datasets.data ?? []).map((dataset) => (
                  <option key={dataset.metadata.id} value={dataset.metadata.id}>
                    {dataset.metadata.title} ({dataset.metadata.id})
                  </option>
                ))}
              </select>
              {datasets.isError ? (
                <p className="field-help" role="alert">
                  Could not load datasets. Check the API connection.
                </p>
              ) : null}
            </div>
          ) : null}

          {executeTestCases && !casesOpen ? (
            <div className="field-group">
              <span className="field-label">Test cases</span>
              <div className="case-explorer-actions">
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() => setCasesOpen(true)}
                  aria-expanded={false}
                  aria-controls="test-cases-panel"
                >
                  Show test cases
                </button>
                <span className="field-help mono tabular">
                  {selectedCaseIds.length} selected
                </span>
              </div>
            </div>
          ) : null}

          <label className="choice-card case-choice choice-card-risk">
            <input
              type="checkbox"
              checked={allowActions}
              onChange={(event) => setAllowActions(event.target.checked)}
              aria-label="Actions Allowed"
            />
            <span>
              <span className="choice-title" aria-hidden="true">
                Actions Allowed
              </span>
              <span className="choice-description">
                Tyr still requires a human decision per action. Uncheck for
                read-only.
              </span>
            </span>
          </label>

          <div className="field-group">
            <div className="field-label-row">
              <label htmlFor="scientist-iterations">Scientist iterations</label>
              <button
                type="button"
                className="info-tip"
                aria-label="What scientist iterations mean"
                aria-describedby="scientist-iterations-tip"
              >
                <span aria-hidden="true">i</span>
                <span
                  id="scientist-iterations-tip"
                  role="tooltip"
                  className="info-tip-bubble"
                >
                  The number of generate-and-run cycles for the scientist stage.
                  In scientist-only mode, recent runs from history provide the
                  seed scenarios.
                </span>
              </button>
            </div>
            <input
              id="scientist-iterations"
              name="scientistIterations"
              type="number"
              min={0}
              step={1}
              inputMode="numeric"
              value={scientistIterationsInput}
              onChange={(event) => {
                setScientistIterationsInput(event.target.value);
              }}
              onBlur={() => {
                setScientistIterationsInput(String(scientistIterations));
              }}
            />
            <p className="field-help">
              {!executeTestCases && scientistIterations === 0
                ? "Set iterations above 0 for scientist-only execution."
                : scientistIterations === 0
                  ? "Off. Selected cases run only."
                  : !executeTestCases
                    ? `Scientist-only: use recent history to generate and run up to ${scientistIterations} scenario${scientistIterations === 1 ? "" : "s"}.`
                    : selectedCaseIds.length > 0
                      ? `After selected cases finish, generate and run up to ${scientistIterations} follow-up scenario${scientistIterations === 1 ? "" : "s"}.`
                      : "Select test cases or switch to scientist-only mode."}
            </p>
          </div>

          <div className="form-actions">
            {error ? (
              <p className="form-status form-status-error" role="alert">
                {error}
              </p>
            ) : null}
            <button
              className="button button-primary"
              type="submit"
              disabled={!canSubmit}
            >
              {submitting ? "Creating…" : "Continue"}
            </button>
          </div>
        </form>

        {!executeTestCases ? (
          <ScientistHistoryPanel
            testRunsInput={historyTestRunsInput}
            scientistRunsInput={historyScientistRunsInput}
            testRuns={historyTestRuns}
            scientistRuns={historyScientistRuns}
            onTestRunsChange={setHistoryTestRunsInput}
            onTestRunsBlur={() =>
              setHistoryTestRunsInput(String(historyTestRuns))
            }
            onScientistRunsChange={setHistoryScientistRunsInput}
            onScientistRunsBlur={() =>
              setHistoryScientistRunsInput(String(historyScientistRuns))
            }
          />
        ) : casesOpen ? (
          <aside
            id="test-cases-panel"
            className="card form-card"
            aria-labelledby="test-cases-title"
          >
            <div className="card-header">
              <div>
                <p className="eyebrow">Dataset cases</p>
                <h2 id="test-cases-title">Test cases</h2>
              </div>
              <div className="case-explorer-actions">
                {datasetId && selectedCaseIds.length > 0 ? (
                  <span className="secondary mono tabular">
                    {selectedCaseIds.length} selected
                  </span>
                ) : null}
                <button
                  type="button"
                  className="button button-ghost"
                  onClick={() => setCasesOpen(false)}
                  aria-expanded={true}
                  aria-controls="test-cases-panel"
                >
                  Hide
                </button>
              </div>
            </div>
            {!datasetId ? (
              <p className="field-help">Select a dataset to load cases.</p>
            ) : cases.isLoading ? (
              <p className="field-help" role="status">
                Loading cases…
              </p>
            ) : cases.isError ? (
              <p className="field-help" role="alert">
                Could not load cases for this dataset.
              </p>
            ) : caseList.length === 0 ? (
              <p className="field-help">No cases in this dataset.</p>
            ) : (
              <CaseChecklist
                cases={caseList}
                selectedCaseIds={selectedCaseIds}
                onToggle={toggleCase}
                onSelectDefaults={() =>
                  setSelectedCaseIds(
                    defaultCaseSelection(
                      selectedDataset,
                      caseList.map((item) => item.id),
                    ),
                  )
                }
                onSelectAll={() =>
                  setSelectedCaseIds(caseList.map((item) => item.id))
                }
                onClear={() => setSelectedCaseIds([])}
              />
            )}
          </aside>
        ) : null}
      </div>
    </section>
  );
}
