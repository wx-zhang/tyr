import type { CaseProgress, CollectorArtifact, RunTurn } from "../../api/client";

export type HistoryUpdate =
  | { kind: "turn"; sequence: number; timestamp: number; turn: RunTurn }
  | { kind: "artifact"; sequence: number; timestamp: number; artifact: CollectorArtifact };

export type HistoryCaseEntry = {
  scenarioId?: string;
  scenarioExecutionId?: string;
  caseId: string;
  progress: CaseProgress | undefined;
  updates: HistoryUpdate[];
};

export type HistoryGroup = {
  id:
    | "discovery"
    | "scenario-executions"
    | "cases"
    | "other"
    | `research-iteration-${number}`
    | `iteration-${number}`;
  label: string;
  updates: HistoryUpdate[];
  cases: HistoryCaseEntry[];
  state: string;
  isTerminal: boolean;
  isBusy: boolean;
};

export const terminalCaseStates = new Set(["completed", "failed", "cancelled", "blocked"]);

export function isTurnBusy(turn: RunTurn): boolean {
  return turn.status === "waiting_for_tyr" || turn.status === "generating";
}

export function parseTimestamp(value: string | null | undefined): number {
  if (!value) return 0;
  const time = new Date(value).valueOf();
  return Number.isNaN(time) ? 0 : time;
}

export function sortUpdates(updates: HistoryUpdate[]): HistoryUpdate[] {
  return [...updates].sort((a, b) => a.timestamp !== b.timestamp ? a.timestamp - b.timestamp : a.sequence - b.sequence);
}

export function isResearchGeneration(turn: RunTurn): boolean {
  if (turn.stage !== "scientist") return false;
  if (turn.updateType === "scientist_generation" || turn.updateType === "scientist") return true;
  if (
    turn.updateType === "conversation" ||
    turn.updateType === "evaluation" ||
    turn.updateType === "sandbox_operation" ||
    turn.updateType === "discovery"
  ) {
    return false;
  }
  return !turn.tyrMessage && ["generating", "failed", "ready"].includes(turn.status);
}

export const isScientistGeneration = isResearchGeneration;

function executionIdOf(item: {
  scenarioExecutionId?: string | null;
  caseId?: string | null;
}): string | undefined {
  return item.scenarioExecutionId ?? item.caseId ?? undefined;
}

function progressIdOf(progress: CaseProgress): string | undefined {
  const executionId = executionIdOf(progress);
  if (executionId) return executionId;
  return "id" in progress && typeof progress.id === "string" ? progress.id : undefined;
}

export function researchIterationMaps(
  turns: RunTurn[],
  cases: CaseProgress[] = [],
): {
  byExecutionId: Map<string, number>;
  byScenarioId: Map<string, number>;
} {
  const byExecutionId = new Map<string, number>();
  const byScenarioId = new Map<string, number>();
  const generations = turns
    .filter(isResearchGeneration)
    .slice()
    .sort((left, right) => left.sequence - right.sequence);

  for (const [index, turn] of generations.entries()) {
    const iter = typeof turn.number === "number" ? turn.number : index + 1;
    if (turn.scenarioId) byScenarioId.set(turn.scenarioId, iter);
    const executionId = executionIdOf(turn);
    if (executionId) byExecutionId.set(executionId, iter);
  }

  const assignFromScenario = (
    scenarioId: string | null | undefined,
    executionId: string | undefined,
  ) => {
    if (!executionId || byExecutionId.has(executionId)) return;
    if (!scenarioId) return;
    const iter = byScenarioId.get(scenarioId);
    if (iter !== undefined) byExecutionId.set(executionId, iter);
  };

  const assignCases = () => {
    for (const progress of cases) {
      assignFromScenario(progress.scenarioId, progressIdOf(progress));
    }
  };

  for (const turn of turns) {
    assignFromScenario(turn.scenarioId, executionIdOf(turn));
  }
  assignCases();

  const pending = turns
    .filter((turn) => turn.stage === "scientist" && !isResearchGeneration(turn))
    .slice()
    .sort((left, right) => left.sequence - right.sequence);
  for (const turn of pending) {
    const executionId = executionIdOf(turn);
    if (executionId && byExecutionId.has(executionId)) continue;
    const prior = generations.filter((generation) => generation.sequence < turn.sequence);
    const last = prior[prior.length - 1];
    const iter = typeof last?.number === "number" ? last.number : 1;
    if (executionId) byExecutionId.set(executionId, iter);
    if (turn.scenarioId && !byScenarioId.has(turn.scenarioId)) {
      byScenarioId.set(turn.scenarioId, iter);
    }
  }

  assignCases();

  return { byExecutionId, byScenarioId };
}

export function resolveResearchIteration(turn: RunTurn, turns: RunTurn[]): number {
  if (isResearchGeneration(turn) && typeof turn.number === "number") return turn.number;
  const { byExecutionId, byScenarioId } = researchIterationMaps(turns);
  const executionId = executionIdOf(turn);
  if (executionId && byExecutionId.has(executionId)) return byExecutionId.get(executionId)!;
  if (turn.scenarioId && byScenarioId.has(turn.scenarioId)) {
    return byScenarioId.get(turn.scenarioId)!;
  }
  return 1;
}

export const resolveScientistIteration = resolveResearchIteration;
