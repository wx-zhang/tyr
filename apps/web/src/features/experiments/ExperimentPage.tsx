import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  createExperimentPreset,
  fetchTaskScenarios,
  fetchTasks,
  type DiscoveryInputDocument,
  type Task,
} from "../../api/client";
import { PageHeader } from "../../components/PageHeader";
import { ScenarioChecklist } from "./CaseChecklist";
import { ResearchHistoryPanel } from "./ScientistHistoryPanel";
import { StatusBadge } from "../../components/StatusBadge";
import {
  readDiscoveryInputFile,
} from "./discoveryInput";

function defaultScenarioSelection(task: Task | undefined, scenarioIds: string[]): string[] {
  if (!task) return [];
  const defaults = task.spec.defaults.defaultScenarioIds ?? task.spec.defaults.defaultCaseIds ?? [];
  const known = new Set(scenarioIds);
  const fromDefaults = defaults.filter((id: string) => known.has(id));
  return fromDefaults.length > 0 ? fromDefaults : scenarioIds;
}

function defaultPresetName(taskTitle: string): string {
  const stamp = new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date());
  return `${taskTitle} · ${stamp}`;
}

function boundedCount(value: string): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 0;
  return Math.min(100, Math.max(0, Math.floor(parsed)));
}

function boundedConcurrency(value: string): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 1;
  return Math.min(5, Math.max(1, Math.floor(parsed)));
}

export function ExperimentPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [taskId, setTaskId] = useState("");
  const [selectedScenarioIds, setSelectedScenarioIds] = useState<string[]>([]);
  const [approvalGated, setApprovalGated] = useState(true);
  const [maxConcurrentScenarioExecutionsInput, setMaxConcurrentScenarioExecutionsInput] = useState("1");
  const [researchIterationsInput, setResearchIterationsInput] = useState("0");
  const [historyTestRunsInput, setHistoryTestRunsInput] = useState("10");
  const [historyResearchRunsInput, setHistoryResearchRunsInput] = useState("5");
  const maxConcurrentScenarioExecutions = useMemo(
    () => boundedConcurrency(maxConcurrentScenarioExecutionsInput),
    [maxConcurrentScenarioExecutionsInput],
  );
  const researchIterations = useMemo(() => {
    const parsed = Number(researchIterationsInput);
    return Number.isFinite(parsed) ? Math.max(0, Math.floor(parsed)) : 0;
  }, [researchIterationsInput]);
  const historyTestRuns = useMemo(() => boundedCount(historyTestRunsInput), [historyTestRunsInput]);
  const historyResearchRuns = useMemo(
    () => boundedCount(historyResearchRunsInput),
    [historyResearchRunsInput],
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scenariosOpen, setScenariosOpen] = useState(true);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [discoveryFileName, setDiscoveryFileName] = useState("");
  const [discoveryDocument, setDiscoveryDocument] = useState<DiscoveryInputDocument | null>(null);
  const [discoveryError, setDiscoveryError] = useState<string | null>(null);
  const [fallbackToDiscovery, setFallbackToDiscovery] = useState(false);
  const [discoveryInputKey, setDiscoveryInputKey] = useState(0);
  const [fileDragOver, setFileDragOver] = useState(false);

  const tasks = useQuery({ queryKey: ["tasks"], queryFn: fetchTasks });

  useEffect(() => {
    if (taskId || !tasks.data?.length) return;
    const preferred =
      tasks.data.find((item) => item.metadata.id === "exfiltrate-important-txt") ?? tasks.data[0];
    if (preferred) setTaskId(preferred.metadata.id);
  }, [tasks.data, taskId]);

  const selectedTask = useMemo(
    () => tasks.data?.find((item) => item.metadata.id === taskId),
    [tasks.data, taskId],
  );
  const scenarios = useQuery({
    queryKey: ["task-scenarios", taskId],
    queryFn: () => fetchTaskScenarios(taskId),
    enabled: Boolean(taskId),
  });

  useEffect(() => {
    if (!scenarios.data) return;
    setSelectedScenarioIds(
      defaultScenarioSelection(
        selectedTask,
        scenarios.data.map((item) => item.metadata.id),
      ),
    );
  }, [scenarios.data, selectedTask]);

  const toggleScenario = (scenarioId: string) => {
    setSelectedScenarioIds((current) =>
      current.includes(scenarioId)
        ? current.filter((id) => id !== scenarioId)
        : [...current, scenarioId],
    );
  };
  const handleDiscoveryFile = async (file: File | undefined) => {
    if (!file) return;
    const result = await readDiscoveryInputFile(file);
    if (result.ok) {
      setDiscoveryDocument(result.document);
      setDiscoveryFileName(file.name);
      setDiscoveryError(null);
    } else {
      setDiscoveryDocument(null);
      setDiscoveryFileName(file.name);
      setDiscoveryError(result.error);
      setFallbackToDiscovery(false);
    }
  };

  const clearDiscoveryInput = () => {
    setDiscoveryDocument(null);
    setDiscoveryFileName("");
    setDiscoveryError(null);
    setFallbackToDiscovery(false);
    setDiscoveryInputKey((key) => key + 1);
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!taskId) {
      setError("Select a Task.");
      return;
    }
    if (selectedScenarioIds.length === 0 && researchIterations === 0) {
      setError("Select at least one Scenario or set Research Iterations above 0.");
      return;
    }
    const taskTitle = selectedTask?.metadata.title ?? taskId;
    const presetName = name.trim() || defaultPresetName(taskTitle);
    setSubmitting(true);
    try {
      const preset = await createExperimentPreset({
        name: presetName,
        task: taskId,
        actionMode: approvalGated ? "approval_required" : "read_only",
        scenarioIds: selectedScenarioIds,
        maxConcurrentScenarioExecutions,
        researchIterations,
        historyTestRuns,
        historyResearchRuns,
        discoveryInput: discoveryDocument,
        fallbackToDiscovery,
      });
      if (!preset.id) throw new Error("Experiment Preset was not created");
      navigate(`/experiments/${preset.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create Experiment Preset");
    } finally {
      setSubmitting(false);
    }
  };

  const scenarioList = scenarios.data ?? [];
  const researcherOnly = Boolean(taskId) && selectedScenarioIds.length === 0;
  const canSubmit =
    Boolean(taskId) &&
    (selectedScenarioIds.length > 0 || researchIterations > 0) &&
    !submitting &&
    !scenarios.isLoading;

  return (
    <section className="section-stack">
      <PageHeader
        eyebrow="Experiment Preset"
        title="Run Experiment"
        description="Choose a Task and execution settings, then start an Experiment against Tyr."
        actions={
          <Link className="button button-secondary" to="/tasks">
            Browse Tasks
          </Link>
        }
      />
      <div className={`execute-layout${!scenariosOpen ? " execute-layout-collapsed" : ""}`}>
        <form className="card form-card" onSubmit={submit}>
          <div className="field-group">
            <label htmlFor="experiment-name">Preset name</label>
            <input
              id="experiment-name"
              name="name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Optional · defaults to Task and time"
            />
          </div>
          <div className="field-group">
            <label htmlFor="experiment-task">Task</label>
            <select
              id="experiment-task"
              name="task"
              value={taskId}
              onChange={(event) => {
                setTaskId(event.target.value);
                setSelectedScenarioIds([]);
                setError(null);
                setScenariosOpen(true);
              }}
              required
              disabled={tasks.isLoading}
            >
              <option value="" disabled>
                {tasks.isLoading ? "Loading Tasks…" : "Select a Task"}
              </option>
              {(tasks.data ?? []).map((task) => (
                <option key={task.metadata.id} value={task.metadata.id}>
                  {task.metadata.title} ({task.metadata.id})
                </option>
              ))}
            </select>
            {tasks.isError ? <p className="field-help" role="alert">Could not load Tasks. Check the API connection.</p> : null}
          </div>
          {!scenariosOpen ? (
            <div className="field-group">
              <span className="field-label">Scenarios</span>
              <div className="case-explorer-actions">
                <button type="button" className="button button-secondary" onClick={() => setScenariosOpen(true)} aria-expanded={false} aria-controls="scenarios-panel">
                  Show Scenarios
                </button>
                <span className="field-help mono tabular">{selectedScenarioIds.length} selected</span>
              </div>
            </div>
          ) : null}
          <label className="choice-card choice-card-compact choice-card-risk">
            <input
              type="checkbox"
              checked={approvalGated}
              onChange={(event) => setApprovalGated(event.target.checked)}
              aria-label="Approval-gated"
            />
            <span className="choice-inline-content">
              <span className="choice-title" aria-hidden="true">Approval-gated</span>
              <span className="choice-description">GAMR requests actions; Tyr requires an explicit human decision for every action.</span>
            </span>
          </label>
          <div className="field-group">
            <label htmlFor="max-concurrent-scenarios">Max concurrent Scenario Executions</label>
            <input
              id="max-concurrent-scenarios"
              name="maxConcurrentScenarioExecutions"
              type="number"
              min={1}
              max={5}
              step={1}
              inputMode="numeric"
              value={maxConcurrentScenarioExecutionsInput}
              onChange={(event) => setMaxConcurrentScenarioExecutionsInput(event.target.value)}
              onBlur={() => setMaxConcurrentScenarioExecutionsInput(String(maxConcurrentScenarioExecutions))}
            />
            <p className="field-help">Number of base Scenario Executions to run simultaneously (1 to 5, default 1).</p>
          </div>
          <div className="field-group">
            <div className="field-label-row">
              <label htmlFor="research-iterations">Research Iterations</label>
              <button type="button" className="info-tip" aria-label="What Research Iterations means" aria-describedby="research-iterations-tip">
                <span aria-hidden="true">i</span>
                <span id="research-iterations-tip" role="tooltip" className="info-tip-bubble">The maximum number of new Task-specific Scenarios the Adversarial Researcher generates and runs after discovery.</span>
              </button>
            </div>
            <input
              id="research-iterations"
              name="researchIterations"
              type="number"
              min={0}
              step={1}
              inputMode="numeric"
              value={researchIterationsInput}
              onChange={(event) => setResearchIterationsInput(event.target.value)}
              onBlur={() => setResearchIterationsInput(String(researchIterations))}
            />
            <p className="field-help">
              {researchIterations === 0
                ? researcherOnly
                  ? "Select Scenarios or set Research Iterations above 0."
                  : "Off. Selected Scenarios run only."
                : researcherOnly
                  ? `Adversarial Researcher only: use recent history to generate and run up to ${researchIterations} Scenario${researchIterations === 1 ? "" : "s"}.`
                  : `After selected Scenarios finish, generate and run up to ${researchIterations} Task-specific follow-up Scenario${researchIterations === 1 ? "" : "s"}.`}
            </p>
          </div>
          <div className="advanced-panel">
            <button
              type="button"
              className="form-disclosure-toggle"
              aria-expanded={advancedOpen}
              aria-controls="advanced-panel-body"
              onClick={() => setAdvancedOpen((open) => !open)}
            >
              Advanced
              <span className="form-disclosure-hint">
                {discoveryError
                  ? "Discovery input: invalid file"
                  : discoveryDocument
                    ? `Discovery input: ${discoveryFileName}`
                    : "Discovery input: not provided"}
              </span>
            </button>
            {advancedOpen ? (
              <div id="advanced-panel-body" className="advanced-body">
                <div className="advanced-item">
                  <div className="field-label-row">
                    <span className="field-label">Skip discovery · provide target</span>
                    <button type="button" className="info-tip" aria-label="What providing a discovery target means" aria-describedby="discovery-input-tip">
                      <span aria-hidden="true">i</span>
                      <span id="discovery-input-tip" role="tooltip" className="info-tip-bubble">
                        Provide a validated discovery-input JSON document to skip live discovery and start
                        Scenarios with the supplied target. The document is stored with the Preset; the file
                        path is not kept. Its Task ID is informational and is never matched against the
                        selected Task.
                      </span>
                    </button>
                  </div>
                  <label
                    className={`file-drop${fileDragOver ? " is-dragover" : ""}${discoveryError ? " has-error" : ""}`}
                    onDragOver={(event) => {
                      event.preventDefault();
                      setFileDragOver(true);
                    }}
                    onDragLeave={() => setFileDragOver(false)}
                    onDrop={(event) => {
                      event.preventDefault();
                      setFileDragOver(false);
                      void handleDiscoveryFile(event.dataTransfer.files?.[0]);
                    }}
                  >
                    <input
                      className="file-drop-input"
                      name="discoveryInputFile"
                      key={discoveryInputKey}
                      type="file"
                      accept="application/json,.json"
                      onChange={(event) => {
                        void handleDiscoveryFile(event.target.files?.[0]);
                      }}
                    />
                    <span className="file-drop-title">
                      {discoveryFileName || "Choose a JSON file or drop it here"}
                    </span>
                    <span className="file-drop-hint">
                      {discoveryFileName
                        ? "Choose a different file or drop it here"
                        : "Discovery-input JSON document · .json"}
                    </span>
                  </label>
                  {discoveryError ? (
                    <p className="form-status form-status-error" role="alert">{discoveryError}</p>
                  ) : null}
                  {discoveryDocument ? (
                    <div className="discovery-preview">
                      <div className="discovery-preview-status">
                        <StatusBadge label="Valid discovery input" tone="success" />
                        <button type="button" className="button button-ghost" onClick={clearDiscoveryInput}>
                          Remove
                        </button>
                      </div>
                      <dl className="detail-list">
                        <div className="detail-row"><dt>Task ID in document</dt><dd className="mono">{discoveryDocument.taskId}</dd></div>
                        <div className="detail-row"><dt>path</dt><dd className="mono">{discoveryDocument.candidate.path}</dd></div>
                        <div className="detail-row"><dt>workspace</dt><dd className="mono">{discoveryDocument.candidate.workspace}</dd></div>
                        <div className="detail-row"><dt>agent</dt><dd className="mono">{discoveryDocument.candidate.agent}</dd></div>
                        <div className="detail-row"><dt>bridgeId</dt><dd className="mono">{discoveryDocument.candidate.bridgeId}</dd></div>
                      </dl>
                      {taskId && discoveryDocument.taskId !== taskId ? (
                        <p className="field-help">
                          The document Task ID ({discoveryDocument.taskId}) differs from the selected Task
                          ({taskId}). It is kept for reference; the selected Task is unchanged.
                        </p>
                      ) : null}
                      <label className="choice-card choice-card-compact">
                        <input
                          type="checkbox"
                          checked={fallbackToDiscovery}
                          onChange={(event) => setFallbackToDiscovery(event.target.checked)}
                          aria-label="Fall back to live discovery"
                        />
                        <span className="choice-inline-content">
                          <span className="choice-title" aria-hidden="true">Fall back to live discovery</span>
                          <span className="choice-description">
                            Runs a bounded read-only preflight before any Scenario Execution; if the
                            provided target is unavailable, normal discovery runs. Off by default: an
                            unavailable target fails the Experiment.
                          </span>
                        </span>
                      </label>
                    </div>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>
          <div className="form-actions">
            {error ? <p className="form-status form-status-error" role="alert">{error}</p> : null}
            <button className="button button-primary" type="submit" disabled={!canSubmit}>{submitting ? "Creating…" : "Continue"}</button>
          </div>
        </form>
        <div className="execute-side-stack">
          {scenariosOpen ? (
            <aside id="scenarios-panel" className="card form-card" aria-labelledby="scenarios-title">
              <div className="card-header">
                <div><p className="eyebrow">Task Scenarios</p><h2 id="scenarios-title">Scenarios</h2></div>
                <div className="case-explorer-actions">
                  {taskId && selectedScenarioIds.length > 0 ? <span className="secondary mono tabular">{selectedScenarioIds.length} selected</span> : null}
                  <button type="button" className="button button-ghost" onClick={() => setScenariosOpen(false)} aria-expanded={true} aria-controls="scenarios-panel">Hide</button>
                </div>
              </div>
              {!taskId ? <p className="field-help">Select a Task to load Scenarios.</p> : scenarios.isLoading ? <p className="field-help" role="status">Loading Scenarios…</p> : scenarios.isError ? <p className="field-help" role="alert">Could not load Scenarios for this Task.</p> : scenarioList.length === 0 ? <p className="field-help">No Scenarios in this Task.</p> : (
                <ScenarioChecklist
                  scenarios={scenarioList}
                  selectedScenarioIds={selectedScenarioIds}
                  onToggle={toggleScenario}
                  onSelectDefaults={() => setSelectedScenarioIds(defaultScenarioSelection(selectedTask, scenarioList.map((item) => item.metadata.id)))}
                  onSelectAll={() => setSelectedScenarioIds(scenarioList.map((item) => item.metadata.id))}
                  onClear={() => setSelectedScenarioIds([])}
                />
              )}
            </aside>
          ) : null}
          {researcherOnly ? <ResearchHistoryPanel testRunsInput={historyTestRunsInput} scientistRunsInput={historyResearchRunsInput} testRuns={historyTestRuns} scientistRuns={historyResearchRuns} onTestRunsChange={setHistoryTestRunsInput} onTestRunsBlur={() => setHistoryTestRunsInput(String(historyTestRuns))} onScientistRunsChange={setHistoryResearchRunsInput} onScientistRunsBlur={() => setHistoryResearchRunsInput(String(historyResearchRuns))} /> : null}
        </div>
      </div>
    </section>
  );
}
