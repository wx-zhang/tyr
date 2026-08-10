import type { components } from "./generated";

export type Dataset = {
  kind?: "dataset";
  metadata: { id: string; title: string; version: string };
  spec: {
    cases: string[];
    discovery?: string | null;
    methodology?: string | null;
    evaluation?: string | null;
    defaults: {
      maxTurns: number;
      actionMode: string;
      defaultCaseIds?: string[];
    };
    variables?: Record<
      string,
      { source: string; default?: string; value?: string; field?: string }
    >;
  };
};

export type DatasetScenario = {
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
  };
};

/** Summary fields used by the experiment case checklist. */
export type DatasetCase = {
  id: string;
  title: string;
  category?: string | null;
};

export type DatasetPlans = {
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
  } | null;
};

export function scenarioToCase(scenario: DatasetScenario): DatasetCase {
  return {
    id: scenario.metadata.id,
    title: scenario.metadata.title,
    category: scenario.metadata.category,
  };
}
export type RunVisualization = components["schemas"]["RunVisualization"];
export type RunTurn = components["schemas"]["RunTurnResponse"];
export type RunTurnPage = components["schemas"]["RunTurnPageResponse"];
export type ProgressItem = components["schemas"]["ProgressItem"];
export type CaseProgress = components["schemas"]["CaseProgress"];
export type RunState =
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

export type Run = {
  id: string;
  experimentId: string | null;
  source: "cli" | "service";
  retryOf?: string | null;
  state: RunState;
  dataset: string;
  configuration: {
    actionMode: "read_only" | "approval_required";
    model: string;
    maxTurns: number;
    discoveryTurns: number;
    caseIds?: string[] | null;
    scientistIterations: number;
  };
  resultPath?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
  finishedAt?: string | null;
};

export type Experiment = {
  id: string;
  name: string;
  dataset: string;
  configuration?: Run["configuration"];
};

export type ActivityItem = components["schemas"]["ActivityItemResponse"];
export type ActivityPage = components["schemas"]["ActivityPageResponse"];

export type EvidenceFilters = {
  q?: string;
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

export async function fetchDatasets(): Promise<Dataset[]> {
  const response = await fetch(`${apiOrigin}/api/v1/datasets`);
  if (!response.ok) throw new Error("Could not load datasets");
  return response.json() as Promise<Dataset[]>;
}

export function fetchDataset(datasetId: string): Promise<Dataset> {
  return get<Dataset>(`/api/v1/datasets/${encodeURIComponent(datasetId)}`);
}

export function fetchDatasetCases(datasetId: string): Promise<DatasetScenario[]> {
  return get<DatasetScenario[]>(
    `/api/v1/datasets/${encodeURIComponent(datasetId)}/cases`,
  );
}

export function fetchDatasetPlans(datasetId: string): Promise<DatasetPlans> {
  return get<DatasetPlans>(
    `/api/v1/datasets/${encodeURIComponent(datasetId)}/plans`,
  );
}

async function get<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiOrigin}${path}`, init);
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json() as Promise<T>;
}

export async function fetchRuns(): Promise<Run[]> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 15_000);
  try {
    const runs = await get<Run[]>("/api/v1/runs", { signal: controller.signal });
    if (!Array.isArray(runs)) {
      throw new Error("Run index response was not a list");
    }
    return runs;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Timed out loading sessions from the API");
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

export function fetchExperiment(experimentId: string): Promise<Experiment> {
  return get<Experiment>(
    `/api/v1/experiments/${encodeURIComponent(experimentId)}`,
  );
}

export async function createExperiment(payload: {
  name: string;
  dataset: string;
  actionMode: "read_only" | "approval_required";
  caseIds: string[];
  scientistIterations?: number;
}): Promise<Experiment> {
  const response = await fetch(`${apiOrigin}/api/v1/experiments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  const experiment = (await response.json()) as Experiment;
  if (!experiment.id) {
    throw new Error("Experiment was not created");
  }
  return experiment;
}

export async function startExperiment(
  experimentId: string,
): Promise<{ id: string; state: RunState; statusUrl: string }> {
  const response = await fetch(
    `${apiOrigin}/api/v1/experiments/${encodeURIComponent(experimentId)}/runs`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    },
  );
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json() as Promise<{ id: string; state: RunState; statusUrl: string }>;
}

export function fetchRun(runId: string): Promise<Run> {
  return get<Run>(`/api/v1/runs/${encodeURIComponent(runId)}`);
}

export async function cancelRun(runId: string): Promise<Run> {
  const response = await fetch(
    `${apiOrigin}/api/v1/runs/${encodeURIComponent(runId)}/cancel`,
    { method: "POST" },
  );
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json() as Promise<Run>;
}

export function fetchRunVisualization(runId: string): Promise<RunVisualization> {
  return get<RunVisualization>(
    `/api/v1/runs/${encodeURIComponent(runId)}/visualization`,
  );
}

export function fetchRunTurns(runId: string, cursor?: string): Promise<RunTurnPage> {
  const params = new URLSearchParams({ limit: "100" });
  if (cursor) params.set("cursor", cursor);
  return get<RunTurnPage>(
    `/api/v1/runs/${encodeURIComponent(runId)}/turns?${params.toString()}`,
  );
}

export function fetchActivity(runId: string, filters: EvidenceFilters = {}): Promise<ActivityPage> {
  const params = new URLSearchParams();
  params.set("limit", String(Math.min(filters.limit ?? 200, 200)));
  params.set("order", filters.order ?? "asc");
  for (const [key, value] of Object.entries(filters)) {
    if (key !== "limit" && key !== "order" && value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return get<ActivityPage>(`/api/v1/runs/${encodeURIComponent(runId)}/activity${suffix}`);
}
