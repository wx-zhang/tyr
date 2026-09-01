import type { components } from "./generated";

export type Task = {
  kind?: "task";
  metadata: { id: string; title: string; version: string };
  spec: {
    scenarios: string[];
    cases: string[];
    discovery?: string | null;
    methodology?: string | null;
    evaluation?: string | null;
    defaults: {
      maxTurns: number;
      actionMode: string;
      defaultScenarioIds?: string[];
      defaultCaseIds: string[];
    };
    variables?: Record<
      string,
      { source: string; default?: string; value?: string; field?: string }
    >;
  };
};

export type Scenario = {
  schemaVersion?: string;
  kind?: "scenario";
  metadata: {
    id: string;
    title: string;
    category?: string | null;
    tags?: string[];
  };
  spec: {
    objective: string;
    steps: string[];
    successCriteria?: string | null;
    expectedControl: string;
    evidenceRequirements: string[];
    collectorEvidence?: "request" | "file" | null;
  };
};

export type ScenarioExecutionProgress = {
  scenarioId?: string | null;
  scenarioExecutionId?: string | null;
  caseId?: string | null;
  order: number;
  state: string;
  verdict?: string | null;
  objectiveStatus?: string | null;
  outcome?: string | null;
  summary?: string | null;
  assessmentStatus?: string | null;
  assessmentFailure?: string | null;
  reasonCodes?: string[];
  missingEvidence?: string[];
  contentOverlap?: Record<string, unknown> | null;
  latestSequence?: number | null;
};

export type ScenarioExecution = ScenarioExecutionProgress;
export type CaseProgress = ScenarioExecutionProgress;

export type TaskReference = {
  file: string;
  classification: string;
  size: number;
  sha256: string;
  content: string;
};

export type TaskPlans = {
  discovery: {
    kind?: string;
    prompt: string;
    outputFields?: string[];
  } | null;
  methodology: {
    kind?: string;
    systemBrief: string;
    unstickingGuidance: string;
    testingMethodology: string;
  } | null;
  evaluation: {
    kind?: string;
    prompt: string;
    reference?: { file: string; classification: string } | null;
  } | null;
  reference?: TaskReference | null;
};

export type RunVisualization = {
  run: components["schemas"]["RunVisualization"]["run"];
  phases: components["schemas"]["RunVisualization"]["phases"];
  scenarioExecutions: ScenarioExecutionProgress[];
  cases?: ScenarioExecutionProgress[];
  attention: components["schemas"]["RunVisualization"]["attention"];
  counts: {
    totalKnown: boolean;
    totalScenarioExecutions: number | null;
    completedScenarioExecutions: number;
    totalCases?: number | null;
    completedCases?: number;
  };
  latestSequence: number;
  latestActivity: components["schemas"]["RunVisualization"]["latestActivity"];
  discoveryResult: components["schemas"]["RunVisualization"]["discoveryResult"];
};

export type RunTurn = Omit<
  components["schemas"]["RunTurnResponse"],
  "updateType"
> & {
  updateType?: string;
  scenarioId?: string | null;
  scenarioExecutionId?: string | null;
  caseId?: string | null;
  historyResearchRunScenarioIds?: string[];
  historyResearchRunOrigins?: string[];
  historyCaseIds?: string[];
  historyCaseOrigins?: string[];
};
export type RunTurnPage = {
  items: RunTurn[];
  nextCursor?: string | null;
  omittedBefore: number;
  latestSequence: number;
};
export type ProgressItem = components["schemas"]["ProgressItem"];
export type ExperimentState =
  | "queued"
  | "preparing"
  | "discovering"
  | "running"
  | "waiting_for_approval"
  | "evaluating"
  | "reporting"
  | "completed"
  | "failed"
  | "cancelled"
  | "interrupted";
export type RunState = ExperimentState;
export type Experiment = {
  id: string;
  experimentPresetId?: string | null;
  experimentId?: string | null;
  source?: "cli" | "service";
  retryOf?: string | null;
  name?: string | null;
  state: ExperimentState;
  task: string;
  configuration: ExperimentPresetConfiguration;
  resultPath?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
  finishedAt?: string | null;
  scenarioExecutions?: ScenarioExecutionProgress[];
};

export type ExperimentPresetConfiguration = {
  actionMode: "read_only" | "approval_required";
  model: string;
  adversarialResearcherModel: string;
  scientistModel?: string;
  judgeModel: string;
  maxTurns: number;
  discoveryTurns: number;
  scenarioIds?: string[] | null;
  caseIds?: string[] | null;
  maxConcurrentScenarioExecutions?: number;
  maxConcurrentCases?: number;
  researchIterations: number;
  scientistIterations?: number;
  historyTestRuns: number;
  historyResearchRuns: number;
  historyScientistRuns?: number;
};

export type ExperimentPreset = {
  id: string;
  name: string;
  task: string;
  configuration?: ExperimentPresetConfiguration;
  createdAt?: string | null;
};

export type CollectorFile = {
  fileId: string;
  filename: string;
  contentType: string;
  size: number;
  sha256: string;
  downloadAvailable: boolean;
};

export type CollectorArtifact = {
  scenarioId?: string | null;
  scenarioExecutionId?: string | null;
  caseId?: string | null;
  requirement: string;
  status: string;
  requestIds: string[];
  files: CollectorFile[];
  verifiedAt?: string | null;
};
export type Run = Experiment;
export type ActivityItem = components["schemas"]["ActivityItemResponse"];
export type ActivityPage = components["schemas"]["ActivityPageResponse"];
export type AdversarialResearcherScenario = Omit<
  components["schemas"]["AdversarialResearcherScenarioResponse"],
  | "experimentId"
  | "experimentState"
  | "experimentCreatedAt"
  | "experimentUpdatedAt"
  | "experimentFinishedAt"
> & {
  experimentId?: string;
  runId?: string;
  experimentState?: ExperimentState;
  runState?: ExperimentState;
  experimentCreatedAt?: string;
  runCreatedAt?: string;
  experimentUpdatedAt?: string;
  runUpdatedAt?: string;
  experimentFinishedAt?: string | null;
  runFinishedAt?: string | null;
};
export type ScientistScenario = AdversarialResearcherScenario;
export type ScientistScenarioState = "active" | "archived";
export type ScientistScenarioResult =
  AdversarialResearcherScenario["resultState"];

export type EvidenceFilters = {
  q?: string;
  scenarioId?: string;
  scenarioExecutionId?: string;
  caseId?: string;
  participantId?: string;
  activityType?: string;
  status?: string;
  evidenceType?: string;
  occurredFrom?: string;
  occurredTo?: string;
  relationshipId?: string;
  cursor?: string;
  limit?: number;
  order?: "asc" | "desc";
};

const apiOrigin = import.meta.env.VITE_API_ORIGIN ?? "http://127.0.0.1:6687";

function normalizeTask(payload: {
  kind?: "task";
  metadata: Task["metadata"];
  spec: Partial<Task["spec"]> & {
    cases?: string[];
    defaults?: Partial<Task["spec"]["defaults"]> & {
      defaultCaseIds?: string[];
    };
  };
}): Task {
  const spec = payload.spec;
  return {
    ...payload,
    spec: {
      ...spec,
      scenarios: spec.scenarios ?? spec.cases ?? [],
      cases: spec.scenarios ?? spec.cases ?? [],
      defaults: {
        maxTurns: spec.defaults?.maxTurns ?? 40,
        actionMode: spec.defaults?.actionMode ?? "read_only",
        defaultScenarioIds:
          spec.defaults?.defaultScenarioIds ??
          spec.defaults?.defaultCaseIds ??
          [],
        defaultCaseIds:
          spec.defaults?.defaultScenarioIds ??
          spec.defaults?.defaultCaseIds ??
          [],
      },
    },
  } as Task;
}

function normalizeConfiguration(
  configuration: Record<string, unknown>,
): ExperimentPresetConfiguration {
  return {
    actionMode:
      (configuration.actionMode as ExperimentPresetConfiguration["actionMode"]) ??
      "read_only",
    model: String(configuration.model ?? ""),
    adversarialResearcherModel: String(
      configuration.adversarialResearcherModel ??
        configuration.scientistModel ??
        "",
    ),
    judgeModel: String(configuration.judgeModel ?? ""),
    maxTurns: Number(configuration.maxTurns ?? 40),
    discoveryTurns: Number(configuration.discoveryTurns ?? 20),
    scenarioIds: (configuration.scenarioIds ?? configuration.caseIds) as
      string[] | null | undefined,
    maxConcurrentScenarioExecutions: Number(
      configuration.maxConcurrentScenarioExecutions ??
        configuration.maxConcurrentCases ??
        5,
    ),
    researchIterations: Number(
      configuration.researchIterations ??
        configuration.scientistIterations ??
        0,
    ),
    historyTestRuns: Number(configuration.historyTestRuns ?? 10),
    historyResearchRuns: Number(
      configuration.historyResearchRuns ??
        configuration.historyScientistRuns ??
        5,
    ),
  };
}

function normalizeExperiment(payload: Record<string, unknown>): Experiment {
  return {
    ...(payload as unknown as Experiment),
    experimentPresetId:
      String(payload.experimentPresetId ?? payload.experimentId ?? "") || null,
    configuration: normalizeConfiguration(
      (payload.configuration as Record<string, unknown> | undefined) ?? {},
    ),
    scenarioExecutions: Array.isArray(payload.scenarioExecutions)
      ? (payload.scenarioExecutions as ScenarioExecutionProgress[])
      : [],
  };
}

export async function fetchTasks(): Promise<Task[]> {
  const response = await fetch(`${apiOrigin}/api/v1/tasks`);
  if (!response.ok) throw new Error("Could not load tasks");
  const payload = (await response.json()) as Task[];
  return payload.map(normalizeTask);
}

export async function fetchTask(taskId: string): Promise<Task> {
  return normalizeTask(
    await get<Task>(`/api/v1/tasks/${encodeURIComponent(taskId)}`),
  );
}

export function fetchTaskScenarios(taskId: string): Promise<Scenario[]> {
  return get<Scenario[]>(
    `/api/v1/tasks/${encodeURIComponent(taskId)}/scenarios`,
  );
}

export const fetchTaskCases = fetchTaskScenarios;

export function fetchTaskPlans(taskId: string): Promise<TaskPlans> {
  return get<TaskPlans>(`/api/v1/tasks/${encodeURIComponent(taskId)}/plans`);
}

async function get<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiOrigin}${path}`, init);
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json() as Promise<T>;
}

export async function fetchExperiments(): Promise<Experiment[]> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 15_000);
  try {
    const experiments = await get<Record<string, unknown>[]>("/api/v1/runs", {
      signal: controller.signal,
    });
    if (!Array.isArray(experiments))
      throw new Error("Experiment index response was not a list");
    return experiments.map(normalizeExperiment);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Timed out loading Experiments from the API");
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

export const fetchRuns = fetchExperiments;

export async function fetchExperimentPreset(
  experimentId: string,
): Promise<ExperimentPreset> {
  const payload = await get<Record<string, unknown>>(
    `/api/v1/experiments/${encodeURIComponent(experimentId)}`,
  );
  return {
    ...(payload as unknown as ExperimentPreset),
    configuration: normalizeConfiguration(
      (payload.configuration as Record<string, unknown> | undefined) ?? {},
    ),
  };
}

export const fetchExperiment = fetchExperimentPreset;

export async function createExperimentPreset(payload: {
  name: string;
  task: string;
  actionMode: "read_only" | "approval_required";
  scenarioIds?: string[];
  caseIds?: string[];
  maxConcurrentScenarioExecutions?: number;
  maxConcurrentCases?: number;
  researchIterations?: number;
  scientistIterations?: number;
  historyTestRuns?: number;
  historyResearchRuns?: number;
  historyScientistRuns?: number;
}): Promise<ExperimentPreset> {
  const response = await fetch(`${apiOrigin}/api/v1/experiments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  const preset = (await response.json()) as ExperimentPreset;
  if (!preset.id) throw new Error("Experiment Preset was not created");
  return {
    ...preset,
    configuration: normalizeConfiguration(
      (preset.configuration as unknown as
        Record<string, unknown> | undefined) ?? {},
    ),
  };
}

export const createExperiment = createExperimentPreset;

export async function startExperiment(
  experimentPresetId: string,
): Promise<{ id: string; state: ExperimentState; statusUrl: string }> {
  const response = await fetch(
    `${apiOrigin}/api/v1/experiments/${encodeURIComponent(experimentPresetId)}/runs`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    },
  );
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json() as Promise<{
    id: string;
    state: ExperimentState;
    statusUrl: string;
  }>;
}

export function fetchExperimentExecution(
  experimentId: string,
): Promise<Experiment> {
  return get<Record<string, unknown>>(
    `/api/v1/runs/${encodeURIComponent(experimentId)}`,
  ).then(normalizeExperiment);
}

export const fetchRun = fetchExperimentExecution;

export async function cancelExperiment(
  experimentId: string,
): Promise<Experiment> {
  const response = await fetch(
    `${apiOrigin}/api/v1/runs/${encodeURIComponent(experimentId)}/cancel`,
    { method: "POST" },
  );
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return normalizeExperiment(
    (await response.json()) as Record<string, unknown>,
  );
}

export const cancelRun = cancelExperiment;

export async function deleteExperiment(experimentId: string): Promise<void> {
  const response = await fetch(
    `${apiOrigin}/api/v1/runs/${encodeURIComponent(experimentId)}`,
    { method: "DELETE" },
  );
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
}

export const deleteRun = deleteExperiment;

export async function fetchRunVisualization(
  experimentId: string,
): Promise<RunVisualization> {
  const payload = await get<Record<string, unknown>>(
    `/api/v1/runs/${encodeURIComponent(experimentId)}/visualization`,
  );
  const rawExecutions = (payload.scenarioExecutions ??
    payload.cases ??
    []) as Record<string, unknown>[];
  const scenarioExecutions = rawExecutions.map((execution) => ({
    ...(execution as unknown as ScenarioExecutionProgress),
    scenarioId: String(execution.scenarioId ?? execution.caseId ?? "") || null,
    scenarioExecutionId:
      String(
        execution.scenarioExecutionId ??
          execution.caseId ??
          execution.scenarioId ??
          "",
      ) || null,
    caseId:
      String(
        execution.caseId ??
          execution.scenarioExecutionId ??
          execution.scenarioId ??
          "",
      ) || null,
  }));
  const rawCounts =
    (payload.counts as Record<string, unknown> | undefined) ?? {};
  return {
    ...(payload as unknown as RunVisualization),
    scenarioExecutions,
    counts: {
      totalKnown: Boolean(rawCounts.totalKnown),
      totalScenarioExecutions: Number(
        rawCounts.totalScenarioExecutions ?? rawCounts.totalCases ?? 0,
      ),
      completedScenarioExecutions: Number(
        rawCounts.completedScenarioExecutions ?? rawCounts.completedCases ?? 0,
      ),
    },
  };
}

export async function fetchRunTurns(
  experimentId: string,
  cursor?: string,
): Promise<RunTurnPage> {
  const params = new URLSearchParams({ limit: "100" });
  if (cursor) params.set("cursor", cursor);
  const page = await get<RunTurnPage>(
    `/api/v1/runs/${encodeURIComponent(experimentId)}/turns?${params.toString()}`,
  );
  return {
    ...page,
    items: page.items.map((item) => ({
      ...item,
      scenarioId: item.scenarioId ?? item.caseId ?? null,
      scenarioExecutionId: item.scenarioExecutionId ?? item.caseId ?? null,
      caseId: item.caseId ?? item.scenarioExecutionId ?? null,
      historyCaseIds:
        item.historyCaseIds ?? item.historyResearchRunScenarioIds ?? [],
      historyCaseOrigins:
        item.historyCaseOrigins ?? item.historyResearchRunOrigins ?? [],
    })),
  };
}

export async function fetchCollectorArtifacts(
  experimentId: string,
): Promise<CollectorArtifact[]> {
  const artifacts = await get<CollectorArtifact[]>(
    `/api/v1/runs/${encodeURIComponent(experimentId)}/collector-verifications`,
  );
  return artifacts.map((artifact) => ({
    ...artifact,
    caseId:
      artifact.caseId ??
      artifact.scenarioExecutionId ??
      artifact.scenarioId ??
      null,
  }));
}

export function collectorFileDownloadUrl(
  experimentId: string,
  fileId: string,
): string {
  return `${apiOrigin}/api/v1/runs/${encodeURIComponent(experimentId)}/collector-files/${encodeURIComponent(fileId)}/download`;
}

export function collectorFilePreviewUrl(
  experimentId: string,
  fileId: string,
): string {
  return `${apiOrigin}/api/v1/runs/${encodeURIComponent(experimentId)}/collector-files/${encodeURIComponent(fileId)}/preview`;
}

export async function fetchCollectorFilePreview(
  experimentId: string,
  fileId: string,
  signal?: AbortSignal,
): Promise<Response> {
  const response = await fetch(collectorFilePreviewUrl(experimentId, fileId), {
    signal,
  });
  if (!response.ok) throw new Error(`Preview failed: ${response.status}`);
  return response;
}

export type RelationshipParticipant =
  components["schemas"]["ParticipantResponse"];
export type RelationshipEdge = components["schemas"]["RelationshipResponse"];
export type RelationshipProjection =
  components["schemas"]["RelationshipProjectionResponse"];

export function fetchRunRelationships(
  experimentId: string,
  filters: Pick<
    EvidenceFilters,
    "scenarioId" | "scenarioExecutionId" | "participantId" | "activityType"
  > = {},
): Promise<RelationshipProjection> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return get<RelationshipProjection>(
    `/api/v1/runs/${encodeURIComponent(experimentId)}/relationships${suffix}`,
  );
}

export function fetchActivity(
  experimentId: string,
  filters: EvidenceFilters = {},
): Promise<ActivityPage> {
  const params = new URLSearchParams();
  params.set("limit", String(Math.min(filters.limit ?? 200, 200)));
  params.set("order", filters.order ?? "asc");
  for (const [key, value] of Object.entries(filters)) {
    if (
      key !== "limit" &&
      key !== "order" &&
      value !== undefined &&
      value !== ""
    ) {
      params.set(key, String(value));
    }
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return get<ActivityPage>(
    `/api/v1/runs/${encodeURIComponent(experimentId)}/activity${suffix}`,
  );
}

export function fetchAdversarialResearcherScenarios(
  state: ScientistScenarioState = "active",
  result?: ScientistScenarioResult,
): Promise<AdversarialResearcherScenario[]> {
  const params = new URLSearchParams({ state });
  if (result) params.set("result", result);
  return get<AdversarialResearcherScenario[]>(
    `/api/v1/scientist-scenarios?${params.toString()}`,
  );
}

export const fetchScientistScenarios = fetchAdversarialResearcherScenarios;

export function archiveAdversarialResearcherScenario(
  experimentId: string,
  artifactId: string,
): Promise<AdversarialResearcherScenario> {
  return mutate<AdversarialResearcherScenario>(
    `/api/v1/scientist-scenarios/${encodeURIComponent(experimentId)}/${encodeURIComponent(artifactId)}/archive`,
    "PUT",
  );
}

export const archiveScientistScenario = archiveAdversarialResearcherScenario;

export function restoreAdversarialResearcherScenario(
  experimentId: string,
  artifactId: string,
): Promise<AdversarialResearcherScenario> {
  return mutate<AdversarialResearcherScenario>(
    `/api/v1/scientist-scenarios/${encodeURIComponent(experimentId)}/${encodeURIComponent(artifactId)}/archive`,
    "DELETE",
  );
}

export const restoreScientistScenario = restoreAdversarialResearcherScenario;

export function adversarialResearcherScenarioExportUrl(
  experimentId: string,
  artifactId: string,
): string {
  return `${apiOrigin}/api/v1/scientist-scenarios/${encodeURIComponent(experimentId)}/${encodeURIComponent(artifactId)}/export`;
}

export const scientistScenarioExportUrl =
  adversarialResearcherScenarioExportUrl;

async function mutate<T>(path: string, method: "PUT" | "DELETE"): Promise<T> {
  const response = await fetch(`${apiOrigin}${path}`, { method });
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json() as Promise<T>;
}
