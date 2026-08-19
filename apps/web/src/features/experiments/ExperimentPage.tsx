import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  createExperiment,
  fetchTaskCases,
  fetchTasks,
  scenarioToCase,
  type Task,
} from "../../api/client";
import { PageHeader } from "../../components/PageHeader";
import { CaseChecklist } from "./CaseChecklist";
import { ScientistHistoryPanel } from "./ScientistHistoryPanel";

const RESEARCH_NEW_TASK = "__research_new_task__";

function defaultCaseSelection(
  task: Task | undefined,
  caseIds: string[],
): string[] {
  if (!task) return [];
  const defaults = task.spec.defaults.defaultCaseIds ?? [];
  const known = new Set(caseIds);
  const fromDefaults = defaults.filter((id: string) => known.has(id));
  if (fromDefaults.length > 0) return fromDefaults;
  return caseIds;
}

function defaultExperimentName(taskTitle: string): string {
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
  if (!Number.isFinite(parsed)) return 5;
  return Math.min(5, Math.max(1, Math.floor(parsed)));
}

export function ExperimentPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [taskId, setTaskId] = useState("");
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([]);
  const [allowActions, setAllowActions] = useState(true);
  const [maxConcurrentCasesInput, setMaxConcurrentCasesInput] = useState("5");
  const [scientistIterationsInput, setScientistIterationsInput] = useState("0");
  const [historyTestRunsInput, setHistoryTestRunsInput] = useState("10");
  const [historyScientistRunsInput, setHistoryScientistRunsInput] =
    useState("5");
  const isResearchMode = taskId === RESEARCH_NEW_TASK;
  const executeTestCases = Boolean(taskId) && !isResearchMode;
  const maxConcurrentCases = useMemo(
    () => boundedConcurrency(maxConcurrentCasesInput),
    [maxConcurrentCasesInput],
  );
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

  const tasks = useQuery({
    queryKey: ["tasks"],
    queryFn: fetchTasks,
  });

  useEffect(() => {
    if (taskId || !tasks.data?.length) return;
    const preferred =
      tasks.data.find((item) => item.metadata.id === "exfiltrate-important-txt") ??
      tasks.data[0];
    if (preferred) {
      setTaskId(preferred.metadata.id);
    }
  }, [tasks.data, taskId]);

  const selectedTask = useMemo(
    () => (isResearchMode ? undefined : tasks.data?.find((item) => item.metadata.id === taskId)),
    [tasks.data, taskId, isResearchMode],
  );

  const cases = useQuery({
    queryKey: ["task-cases", taskId],
    queryFn: () => fetchTaskCases(taskId),
    enabled: Boolean(taskId) && executeTestCases,
  });

  useEffect(() => {
    if (!cases.data || !executeTestCases) return;
    setSelectedCaseIds(
      defaultCaseSelection(
        selectedTask,
        cases.data.map((item) => item.metadata.id),
      ),
    );
  }, [cases.data, executeTestCases, selectedTask]);

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
    if (!taskId) {
      setError("Select a task.");
      return;
    }
    if (executeTestCases && selectedCaseIds.length === 0) {
      setError("Select at least one test case or choose Research new task.");
      return;
    }
    if (!executeTestCases && scientistIterations === 0) {
      setError(
        "Set number of new task research above 0 for scientist-only execution.",
      );
      return;
    }
    const defaultTask =
      tasks.data?.find((item) => item.metadata.id === "exfiltrate-important-txt") ??
      tasks.data?.[0];
    const effectiveTask = isResearchMode ? (defaultTask?.metadata.id ?? "exfiltrate-important-txt") : taskId;
    const taskTitle = isResearchMode
      ? "Research new task"
      : (selectedTask?.metadata.title ?? taskId);
    const experimentName = name.trim() || defaultExperimentName(taskTitle);
    setSubmitting(true);
    try {
      const experiment = await createExperiment({
        name: experimentName,
        task: effectiveTask,
        actionMode: allowActions ? "approval_required" : "read_only",
        caseIds: executeTestCases ? selectedCaseIds : [],
        maxConcurrentCases,
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
    Boolean(taskId) &&
    (executeTestCases ? selectedCaseIds.length > 0 : scientistIterations > 0) &&
    !submitting &&
    (!executeTestCases || !cases.isLoading);

  return (
    <section className="section-stack">
      <PageHeader
        eyebrow="Experiment execution"
        title="Execute experiment"
        description="Choose a task and execution mode, then start a live red-team run against Tyr."
        actions={
          <Link className="button button-secondary" to="/tasks">
            Browse tasks
          </Link>
        }
      />

      <div
        className={`execute-layout${executeTestCases && !casesOpen ? " execute-layout-collapsed" : !executeTestCases ? "" : ""}`}
      >
        <form className="card form-card" onSubmit={submit}>
          <div className="field-group">
            <label htmlFor="experiment-name">Name</label>
            <input
              id="experiment-name"
              name="name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Optional · defaults to task and time"
            />
          </div>

          <div className="field-group">
            <label htmlFor="experiment-task">Task</label>
            <select
              id="experiment-task"
              name="task"
              value={taskId}
              onChange={(event) => {
                const nextTaskId = event.target.value;
                setTaskId(nextTaskId);
                setSelectedCaseIds([]);
                setError(null);
                setCasesOpen(true);
              }}
              required
              disabled={tasks.isLoading}
            >
              <option value="" disabled>
                {tasks.isLoading
                  ? "Loading tasks…"
                  : "Select a task"}
              </option>
              <option value={RESEARCH_NEW_TASK}>
                Research new task
              </option>
              {(tasks.data ?? []).map((task) => (
                <option key={task.metadata.id} value={task.metadata.id}>
                  {task.metadata.title} ({task.metadata.id})
                </option>
              ))}
            </select>
            {tasks.isError ? (
              <p className="field-help" role="alert">
                Could not load tasks. Check the API connection.
              </p>
            ) : null}
          </div>

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

          <label className="choice-card choice-card-compact choice-card-risk">
            <input
              type="checkbox"
              checked={allowActions}
              onChange={(event) => setAllowActions(event.target.checked)}
              aria-label="Actions Allowed"
            />
            <span className="choice-inline-content">
              <span className="choice-title" aria-hidden="true">
                Actions Allowed
              </span>
              <span className="choice-description">
                (approval required per action)
              </span>
            </span>
          </label>

          <div className="field-group">
            <label htmlFor="max-concurrent-cases">Max concurrent cases</label>
            <input
              id="max-concurrent-cases"
              name="maxConcurrentCases"
              type="number"
              min={1}
              max={5}
              step={1}
              inputMode="numeric"
              value={maxConcurrentCasesInput}
              onChange={(event) => {
                setMaxConcurrentCasesInput(event.target.value);
              }}
              onBlur={() => {
                setMaxConcurrentCasesInput(String(maxConcurrentCases));
              }}
            />
            <p className="field-help">
              Number of base test cases to execute simultaneously (1 to 5, default 5).
            </p>
          </div>

          <div className="field-group">
            <div className="field-label-row">
              <label htmlFor="scientist-iterations">Number of new task research</label>
              <button
                type="button"
                className="info-tip"
                aria-label="What number of new task research means"
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
                ? "Set number of new task research above 0 for scientist-only execution."
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
                <p className="eyebrow">Task cases</p>
                <h2 id="test-cases-title">Test cases</h2>
              </div>
              <div className="case-explorer-actions">
                {taskId && selectedCaseIds.length > 0 ? (
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
            {!taskId ? (
              <p className="field-help">Select a task to load cases.</p>
            ) : cases.isLoading ? (
              <p className="field-help" role="status">
                Loading cases…
              </p>
            ) : cases.isError ? (
              <p className="field-help" role="alert">
                Could not load cases for this task.
              </p>
            ) : caseList.length === 0 ? (
              <p className="field-help">No cases in this task.</p>
            ) : (
              <CaseChecklist
                cases={caseList}
                selectedCaseIds={selectedCaseIds}
                onToggle={toggleCase}
                onSelectDefaults={() =>
                  setSelectedCaseIds(
                    defaultCaseSelection(
                      selectedTask,
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
