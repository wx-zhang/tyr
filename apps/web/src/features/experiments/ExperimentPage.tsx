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

export function ExperimentPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([]);
  const [allowActions, setAllowActions] = useState(true);
  const [scientistIterations, setScientistIterations] = useState(0);
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
    enabled: Boolean(datasetId),
  });

  useEffect(() => {
    if (!cases.data) return;
    setSelectedCaseIds(
      defaultCaseSelection(
        selectedDataset,
        cases.data.map((item) => item.metadata.id),
      ),
    );
  }, [cases.data, selectedDataset]);

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
    if (selectedCaseIds.length === 0) {
      setError("Select at least one case.");
      return;
    }
    const datasetTitle = selectedDataset?.metadata.title ?? datasetId;
    const experimentName = name.trim() || defaultExperimentName(datasetTitle);
    setSubmitting(true);
    try {
      const iterations = Number.isFinite(scientistIterations)
        ? Math.max(0, Math.floor(scientistIterations))
        : 0;
      const experiment = await createExperiment({
        name: experimentName,
        dataset: datasetId,
        actionMode: allowActions ? "approval_required" : "read_only",
        caseIds: selectedCaseIds,
        scientistIterations: iterations,
      });
      if (!experiment.id) throw new Error("Experiment was not created");
      navigate(`/experiments/${experiment.id}`);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not create experiment",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const caseList = (cases.data ?? []).map(scenarioToCase);
  const canSubmit =
    Boolean(datasetId) &&
    selectedCaseIds.length > 0 &&
    !submitting &&
    !cases.isLoading;

  return (
    <section className="section-stack">
      <PageHeader
        eyebrow="Experiment execution"
        title="Execute experiment"
        description="Choose a dataset and cases, then start a live run."
        actions={
          <Link className="button button-secondary" to="/datasets">
            Browse datasets
          </Link>
        }
      />

      <div
        className={`execute-layout${casesOpen ? "" : " execute-layout-collapsed"}`}
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

          {!casesOpen ? (
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

          <label className="choice-card case-choice">
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

          {allowActions ? (
            <div className="callout callout-warning">
              <p>
                <strong>Actions Allowed.</strong> Approvals happen in Tyr, not
                automatically in GAMR.
              </p>
            </div>
          ) : (
            <div className="callout">
              <p>
                <strong>Read-only.</strong> Query-only Tyr access.
              </p>
            </div>
          )}

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
                  After selected cases finish, the scientist stage asks the model
                  to invent new follow-up scenarios and runs each one. The number
                  is how many generate-and-run cycles to allow. Zero skips the
                  scientist stage.
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
              value={scientistIterations}
              onChange={(event) => {
                const next = Number(event.target.value);
                if (!Number.isFinite(next)) {
                  setScientistIterations(0);
                  return;
                }
                setScientistIterations(Math.max(0, Math.floor(next)));
              }}
            />
            <p className="field-help">
              {scientistIterations > 0
                ? `After selected cases finish, generate and run up to ${scientistIterations} follow-up scenario${scientistIterations === 1 ? "" : "s"}.`
                : "Off. Selected cases run only."}
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

        {casesOpen ? (
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
