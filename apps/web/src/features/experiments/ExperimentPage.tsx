import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  createExperimentPreset,
  fetchTaskScenarios,
  fetchTasks,
  type Task,
} from "../../api/client";
import { PageHeader } from "../../components/PageHeader";
import { ScenarioChecklist } from "./CaseChecklist";
import { ResearchHistoryPanel } from "./ScientistHistoryPanel";

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
