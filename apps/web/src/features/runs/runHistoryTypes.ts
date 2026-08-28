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
  return turn.stage === "scientist" && (turn.updateType === "scientist_generation" || (!turn.tyrMessage && ["generating", "failed", "ready", "completed"].includes(turn.status)));
}

export const isScientistGeneration = isResearchGeneration;

export function resolveResearchIteration(turn: RunTurn, turns: RunTurn[]): number {
  const executionId = turn.scenarioExecutionId ?? turn.caseId;
  if (turn.updateType === "scientist_generation" || turn.stage === "scientist") {
    if (turn.number && (turn.updateType === "scientist_generation" || !executionId)) return turn.number;
    if (executionId) {
      const generations = turns.filter((candidate) => candidate.updateType === "scientist_generation" && candidate.number != null);
      if (generations.length > 0) return generations[generations.length - 1].number;
    }
  }
  return 1;
}

export const resolveScientistIteration = resolveResearchIteration;
