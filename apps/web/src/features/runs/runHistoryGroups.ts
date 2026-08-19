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
  resolveScientistIteration,
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

export function groupRunHistory(input: {
  turns: RunTurn[];
  cases: CaseProgress[];
  artifacts: CollectorArtifact[];
  phases?: ProgressItem[];
}): HistoryGroup[] {
  const { turns, cases, artifacts, phases = [] } = input;

  const scientistIterationByCaseId = new Map<string, number>();
  for (const turn of turns) {
    if (turn.stage === "scientist" && turn.caseId) {
      if (isScientistGeneration(turn)) {
        scientistIterationByCaseId.set(turn.caseId, turn.number);
      } else if (!scientistIterationByCaseId.has(turn.caseId)) {
        scientistIterationByCaseId.set(
          turn.caseId,
          resolveScientistIteration(turn, turns),
        );
      }
    }
  }

  const discoveryUpdates: HistoryUpdate[] = [];
  const baseCaseUpdatesByCaseId = new Map<string, HistoryUpdate[]>();
  const iterationUpdatesByIteration = new Map<number, HistoryUpdate[]>();
  const iterationCaseUpdates = new Map<number, Map<string, HistoryUpdate[]>>();
  const otherUpdates: HistoryUpdate[] = [];

  for (const turn of turns) {
    const ts = parseTimestamp(turn.occurredAt);
    const update: HistoryUpdate = {
      kind: "turn",
      sequence: turn.sequence,
      timestamp: ts,
      turn,
    };

    if (turn.updateType === "discovery" || turn.stage === "discovery") {
      discoveryUpdates.push(update);
    } else if (turn.stage === "scientist") {
      let iter = 1;
      if (turn.caseId && scientistIterationByCaseId.has(turn.caseId)) {
        iter = scientistIterationByCaseId.get(turn.caseId)!;
      } else if (turn.updateType === "scientist_generation" && turn.number) {
        iter = turn.number;
      } else {
        iter = resolveScientistIteration(turn, turns);
      }

      if (isScientistGeneration(turn)) {
        if (!iterationUpdatesByIteration.has(iter))
          iterationUpdatesByIteration.set(iter, []);
        iterationUpdatesByIteration.get(iter)!.push(update);
      } else if (turn.caseId) {
        if (!iterationCaseUpdates.has(iter))
          iterationCaseUpdates.set(iter, new Map());
        const caseMap = iterationCaseUpdates.get(iter)!;
        if (!caseMap.has(turn.caseId)) caseMap.set(turn.caseId, []);
        caseMap.get(turn.caseId)!.push(update);
      } else {
        if (!iterationUpdatesByIteration.has(iter))
          iterationUpdatesByIteration.set(iter, []);
        iterationUpdatesByIteration.get(iter)!.push(update);
      }
    } else if (turn.caseId) {
      if (!baseCaseUpdatesByCaseId.has(turn.caseId))
        baseCaseUpdatesByCaseId.set(turn.caseId, []);
      baseCaseUpdatesByCaseId.get(turn.caseId)!.push(update);
    } else {
      otherUpdates.push(update);
    }
  }

  for (const artifact of artifacts) {
    const ts = parseTimestamp(artifact.verifiedAt);
    const update: HistoryUpdate = {
      kind: "artifact",
      sequence: 0,
      timestamp: ts,
      artifact,
    };

    if (artifact.caseId) {
      if (scientistIterationByCaseId.has(artifact.caseId)) {
        const iter = scientistIterationByCaseId.get(artifact.caseId)!;
        if (!iterationCaseUpdates.has(iter)) {
          iterationCaseUpdates.set(iter, new Map());
        }
        const caseMap = iterationCaseUpdates.get(iter)!;
        if (!caseMap.has(artifact.caseId)) {
          caseMap.set(artifact.caseId, []);
        }
        caseMap.get(artifact.caseId)!.push(update);
      } else {
        if (!baseCaseUpdatesByCaseId.has(artifact.caseId)) {
          baseCaseUpdatesByCaseId.set(artifact.caseId, []);
        }
        baseCaseUpdatesByCaseId.get(artifact.caseId)!.push(update);
      }
    } else {
      otherUpdates.push(update);
    }
  }

  const result: HistoryGroup[] = [];

  if (discoveryUpdates.length > 0) {
    const sorted = sortUpdates(discoveryUpdates);
    const phaseState = phases.find(
      (phase) => phase.id === "discovering",
    )?.state;
    const hasBusyTurn = sorted.some(
      (update) => update.kind === "turn" && isTurnBusy(update.turn),
    );
    const resultTurn = sorted.find(
      (update) =>
        update.kind === "turn" && update.turn.updateType === "discovery",
    );
    const resultState =
      resultTurn?.kind === "turn" ? resultTurn.turn.status : "active";
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
  for (const c of cases) {
    const id = c.caseId ?? (c as { id?: string }).id;
    if (id) {
      knownCaseMap.set(id, c);
    }
  }

  const sortedCases = cases
    .filter((item) => {
      const id = item.caseId ?? (item as { id?: string }).id;
      return !id || !scientistIterationByCaseId.has(id);
    })
    .sort((a, b) => a.order - b.order);
  const baseCaseEntries: HistoryCaseEntry[] = [];
  const processedCaseIds = new Set<string>();

  for (const c of sortedCases) {
    const id = c.caseId ?? (c as { id?: string }).id;
    if (!id) continue;
    processedCaseIds.add(id);
    const rawUpdates = baseCaseUpdatesByCaseId.get(id) ?? [];
    baseCaseEntries.push({
      caseId: id,
      progress: c,
      updates: sortUpdates(rawUpdates),
    });
  }

  for (const [caseId, rawUpdates] of baseCaseUpdatesByCaseId.entries()) {
    if (!processedCaseIds.has(caseId)) {
      baseCaseEntries.push({
        caseId,
        progress: undefined,
        updates: sortUpdates(rawUpdates),
      });
    }
  }

  if (baseCaseEntries.length > 0) {
    let anyBusy = false;
    let allTerminal = true;
    for (const entry of baseCaseEntries) {
      const state = entry.progress?.state;
      const isCaseTerminal = state ? terminalCaseStates.has(state) : false;
      if (!isCaseTerminal && entry.progress) {
        allTerminal = false;
      }
      if (entry.updates.some((u) => u.kind === "turn" && isTurnBusy(u.turn))) {
        anyBusy = true;
      }
    }
    const states = baseCaseEntries.map(
      (entry) => entry.progress?.state ?? "pending",
    );
    const state =
      anyBusy ||
      states.some((caseState) => ["active", "assessing"].includes(caseState))
        ? "active"
        : allTerminal
          ? "completed"
          : states.some((caseState) => caseState === "queued")
            ? "queued"
            : "pending";
    result.push({
      id: "cases",
      label: "Test cases",
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
    const groupUpdates = sortUpdates(
      iterationUpdatesByIteration.get(iter) ?? [],
    );
    const caseMap = iterationCaseUpdates.get(iter) ?? new Map();
    const caseEntries: HistoryCaseEntry[] = [];

    for (const [caseId, rawUpdates] of caseMap.entries()) {
      caseEntries.push({
        caseId,
        progress: knownCaseMap.get(caseId),
        updates: sortUpdates(rawUpdates),
      });
    }

    const isBusy =
      groupUpdates.some((u) => u.kind === "turn" && isTurnBusy(u.turn)) ||
      caseEntries.some((c) =>
        c.updates.some((u) => u.kind === "turn" && isTurnBusy(u.turn)),
      );

    const isTerminal =
      (groupUpdates.length > 0 || caseEntries.length > 0) && !isBusy;

    result.push({
      id: `iteration-${iter}`,
      label: `Iteration ${iter}`,
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
