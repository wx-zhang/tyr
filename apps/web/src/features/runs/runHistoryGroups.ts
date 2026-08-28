import type {
  CaseProgress,
  CollectorArtifact,
  ProgressItem,
  RunTurn,
} from "../../api/client";
import {
  isTurnBusy,
  isScientistGeneration,
  parseTimestamp,
  researchIterationMaps,
  sortUpdates,
  terminalCaseStates,
  type HistoryCaseEntry,
  type HistoryGroup,
  type HistoryUpdate,
} from "./runHistoryTypes";

export type {
  HistoryCaseEntry,
  HistoryGroup,
  HistoryUpdate,
} from "./runHistoryTypes";

function turnExecutionId(turn: RunTurn): string | undefined {
  return turn.scenarioExecutionId ?? turn.caseId ?? undefined;
}

function progressExecutionId(progress: CaseProgress): string | undefined {
  const executionId = progress.scenarioExecutionId ?? progress.caseId;
  if (executionId) return executionId;
  return "id" in progress && typeof progress.id === "string" ? progress.id : undefined;
}

function historyEntry(
  executionId: string,
  progress: CaseProgress | undefined,
  updates: HistoryUpdate[],
): HistoryCaseEntry {
  return {
    scenarioId: progress?.scenarioId ?? executionId,
    scenarioExecutionId: progress ? progressExecutionId(progress) ?? executionId : executionId,
    caseId: executionId,
    progress,
    updates: sortUpdates(updates),
  };
}

export function groupRunHistory(input: {
  turns: RunTurn[];
  cases: CaseProgress[];
  artifacts: CollectorArtifact[];
  phases?: ProgressItem[];
}): HistoryGroup[] {
  const { turns, cases, artifacts, phases = [] } = input;
  const {
    byExecutionId: scientistIterationByCaseId,
    byScenarioId: scientistIterationByScenarioId,
  } = researchIterationMaps(turns, cases);

  const discoveryUpdates: HistoryUpdate[] = [];
  const baseCaseUpdatesByCaseId = new Map<string, HistoryUpdate[]>();
  const iterationUpdatesByIteration = new Map<number, HistoryUpdate[]>();
  const iterationCaseUpdates = new Map<number, Map<string, HistoryUpdate[]>>();
  const otherUpdates: HistoryUpdate[] = [];

  for (const turn of turns) {
    const executionId = turnExecutionId(turn);
    const ts = parseTimestamp(turn.occurredAt);
    const update: HistoryUpdate = {
      kind: "turn",
      sequence: turn.sequence,
      timestamp: ts,
      turn,
    };

    if (turn.updateType === "discovery" || turn.stage === "discovery") {
      discoveryUpdates.push(update);
    } else if (
      turn.stage === "scientist" ||
      (executionId && scientistIterationByCaseId.has(executionId)) ||
      (turn.scenarioId && scientistIterationByScenarioId.has(turn.scenarioId))
    ) {
      const iter =
        (executionId ? scientistIterationByCaseId.get(executionId) : undefined) ??
        (turn.scenarioId ? scientistIterationByScenarioId.get(turn.scenarioId) : undefined) ??
        (isScientistGeneration(turn) && typeof turn.number === "number" ? turn.number : 1);

      if (isScientistGeneration(turn)) {
        if (!iterationUpdatesByIteration.has(iter)) iterationUpdatesByIteration.set(iter, []);
        iterationUpdatesByIteration.get(iter)!.push(update);
      } else if (executionId) {
        if (!iterationCaseUpdates.has(iter)) iterationCaseUpdates.set(iter, new Map());
        const caseMap = iterationCaseUpdates.get(iter)!;
        if (!caseMap.has(executionId)) caseMap.set(executionId, []);
        caseMap.get(executionId)!.push(update);
      } else {
        if (!iterationUpdatesByIteration.has(iter)) iterationUpdatesByIteration.set(iter, []);
        iterationUpdatesByIteration.get(iter)!.push(update);
      }
    } else if (executionId) {
      if (!baseCaseUpdatesByCaseId.has(executionId)) baseCaseUpdatesByCaseId.set(executionId, []);
      baseCaseUpdatesByCaseId.get(executionId)!.push(update);
    } else {
      otherUpdates.push(update);
    }
  }

  for (const artifact of artifacts) {
    const executionId = artifact.scenarioExecutionId ?? artifact.caseId;
    const ts = parseTimestamp(artifact.verifiedAt);
    const update: HistoryUpdate = {
      kind: "artifact",
      sequence: 0,
      timestamp: ts,
      artifact,
    };

    if (executionId) {
      if (scientistIterationByCaseId.has(executionId)) {
        const iter = scientistIterationByCaseId.get(executionId)!;
        if (!iterationCaseUpdates.has(iter)) iterationCaseUpdates.set(iter, new Map());
        const caseMap = iterationCaseUpdates.get(iter)!;
        if (!caseMap.has(executionId)) caseMap.set(executionId, []);
        caseMap.get(executionId)!.push(update);
      } else {
        if (!baseCaseUpdatesByCaseId.has(executionId)) baseCaseUpdatesByCaseId.set(executionId, []);
        baseCaseUpdatesByCaseId.get(executionId)!.push(update);
      }
    } else {
      otherUpdates.push(update);
    }
  }

  const result: HistoryGroup[] = [];

  if (discoveryUpdates.length > 0) {
    const sorted = sortUpdates(discoveryUpdates);
    const phaseState = phases.find((phase) => phase.id === "discovering")?.state;
    const hasBusyTurn = sorted.some((update) => update.kind === "turn" && isTurnBusy(update.turn));
    const resultTurn = sorted.find((update) => update.kind === "turn" && update.turn.updateType === "discovery");
    const resultState = resultTurn?.kind === "turn" ? resultTurn.turn.status : "active";
    const state = phaseState ?? (hasBusyTurn ? "active" : resultState);
    const isTerminal = terminalCaseStates.has(state);
    result.push({
      id: "discovery",
      label: "Discovery",
      updates: sorted,
      cases: [],
      state,
      isTerminal,
      isBusy: state === "active" || hasBusyTurn,
    });
  }

  const knownCaseMap = new Map<string, CaseProgress>();
  for (const progress of cases) {
    const executionId = progressExecutionId(progress);
    if (executionId) knownCaseMap.set(executionId, progress);
  }

  const sortedCases = cases
    .filter((item) => {
      const executionId = progressExecutionId(item);
      return !executionId || !scientistIterationByCaseId.has(executionId);
    })
    .sort((a, b) => a.order - b.order);
  const baseCaseEntries: HistoryCaseEntry[] = [];
  const processedCaseIds = new Set<string>();

  for (const progress of sortedCases) {
    const executionId = progressExecutionId(progress);
    if (!executionId) continue;
    processedCaseIds.add(executionId);
    const rawUpdates = baseCaseUpdatesByCaseId.get(executionId) ?? [];
    baseCaseEntries.push(historyEntry(executionId, progress, rawUpdates));
  }

  for (const [executionId, rawUpdates] of baseCaseUpdatesByCaseId.entries()) {
    if (!processedCaseIds.has(executionId)) {
      baseCaseEntries.push(historyEntry(executionId, undefined, rawUpdates));
    }
  }

  if (baseCaseEntries.length > 0) {
    let anyBusy = false;
    let allTerminal = true;
    for (const entry of baseCaseEntries) {
      const state = entry.progress?.state;
      const isCaseTerminal = state ? terminalCaseStates.has(state) : false;
      if (!isCaseTerminal && entry.progress) allTerminal = false;
      if (entry.updates.some((u) => u.kind === "turn" && isTurnBusy(u.turn))) anyBusy = true;
    }
    const states = baseCaseEntries.map((entry) => entry.progress?.state ?? "pending");
    const state = anyBusy || states.some((caseState) => ["active", "assessing"].includes(caseState))
      ? "active"
      : allTerminal
        ? "completed"
        : states.some((caseState) => caseState === "queued")
          ? "queued"
          : "pending";
    result.push({
      id: "scenario-executions",
      label: "Scenario Executions",
      updates: [],
      cases: baseCaseEntries,
      state,
      isTerminal: allTerminal && !anyBusy,
      isBusy: anyBusy,
    });
  }

  const allIterations = new Set<number>([
    ...iterationUpdatesByIteration.keys(),
    ...iterationCaseUpdates.keys(),
  ]);
  const sortedIterations = [...allIterations].sort((a, b) => a - b);

  for (const iter of sortedIterations) {
    const groupUpdates = sortUpdates(iterationUpdatesByIteration.get(iter) ?? []);
    const caseMap = iterationCaseUpdates.get(iter) ?? new Map();
    const caseEntries: HistoryCaseEntry[] = [];
    const processedExecutionIds = new Set<string>();

    for (const [executionId, progress] of knownCaseMap.entries()) {
      if (scientistIterationByCaseId.get(executionId) === iter) {
        processedExecutionIds.add(executionId);
        const rawUpdates = caseMap.get(executionId) ?? [];
        caseEntries.push(historyEntry(executionId, progress, rawUpdates));
      }
    }

    for (const [executionId, rawUpdates] of caseMap.entries()) {
      if (!processedExecutionIds.has(executionId)) {
        caseEntries.push(historyEntry(executionId, knownCaseMap.get(executionId), rawUpdates));
      }
    }

    const isBusy = groupUpdates.some((u) => u.kind === "turn" && isTurnBusy(u.turn)) ||
      caseEntries.some((c) => c.updates.some((u) => u.kind === "turn" && isTurnBusy(u.turn)));

    const isTerminal = (groupUpdates.length > 0 || caseEntries.length > 0) && !isBusy;

    result.push({
      id: `research-iteration-${iter}`,
      label: `Research Iteration ${iter}`,
      updates: groupUpdates,
      cases: caseEntries,
      state: isBusy ? "active" : isTerminal ? "completed" : "pending",
      isTerminal,
      isBusy,
    });
  }

  if (otherUpdates.length > 0) {
    const sorted = sortUpdates(otherUpdates);
    const isBusy = sorted.some((u) => u.kind === "turn" && isTurnBusy(u.turn));
    result.push({
      id: "other",
      label: "Other updates",
      updates: sorted,
      cases: [],
      state: isBusy ? "active" : "completed",
      isTerminal: !isBusy,
      isBusy,
    });
  }

  return result;
}
