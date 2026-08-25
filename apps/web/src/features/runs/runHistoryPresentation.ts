import type { RunTurn } from "../../api/client";
import type { HistoryCaseEntry, HistoryUpdate } from "./runHistoryGroups";
import {
  isDiscoveryResult,
  isEvaluation,
  isScientistGeneration,
  isSandboxOperation,
  label,
  resultDisplay,
  tone,
} from "./runTurnHelpers";

const summaryLimit = 180;

function compactText(value: string | null | undefined): string {
  const text = (value ?? "")
    .replace(/```[\s\S]*?```/g, " Code evidence ")
    .replace(/[`*_>#\[\]]/g, "")
    .replace(/\s+/g, " ")
    .trim();
  if (text.length <= summaryLimit) return text;
  return `${text.slice(0, summaryLimit - 1).trimEnd()}…`;
}

export function turnActivityPresentation(
  turn: RunTurn,
  scientistIteration?: number,
) {
  const waiting = turn.status === "waiting_for_tyr" && !turn.tyrMessage;
  const scientistGeneration = isScientistGeneration(turn);
  const evaluation = isEvaluation(turn);
  const discovery = isDiscoveryResult(turn);
  const sandboxOperation = isSandboxOperation(turn);
  const result = evaluation
    ? resultDisplay(turn.verdict, turn.objectiveStatus, turn.outcome)
    : null;
  const title = sandboxOperation
    ? `Sandbox operation - ${turn.caseId ?? `Case ${turn.number}`}`
    : evaluation
      ? turn.stage === "scientist"
        ? `Scientist evaluation - ${turn.caseId ?? `Case ${turn.number}`}`
        : `Evaluation result - ${turn.caseId ?? `Case ${turn.number}`}`
      : discovery
        ? turn.status === "blocked"
          ? "Discovery blocked"
          : "Discovery complete"
        : scientistGeneration
          ? `Scientist - Iteration ${turn.number}`
          : turn.stage === "scientist"
            ? `Scientist Scenario ${scientistIteration ?? turn.number} - Turn ${turn.number}`
            : `${label(turn.stage)} - Turn ${turn.number}`;
  const source = sandboxOperation
    ? `Sandbox ${turn.status.replaceAll("_", " ")}`
    : evaluation
      ? (turn.assessmentSummary ?? turn.agentMessage ?? result?.label)
      : waiting
        ? "Waiting for Tyr response"
        : (turn.tyrMessage ?? turn.agentMessage ?? label(turn.status));

  return {
    title,
    summary: compactText(source),
    status: result ?? {
      label:
        scientistGeneration && turn.status === "generating"
          ? "Agent working"
          : label(turn.status),
      tone: tone(turn.status),
    },
    waiting,
    scientistGeneration,
    evaluation,
    discovery,
    sandboxOperation,
  };
}

export function historyUpdateSummary(update: HistoryUpdate): string {
  if (update.kind === "turn") {
    return turnActivityPresentation(update.turn).summary;
  }
  const requirement = compactText(update.artifact.requirement);
  return requirement
    ? `Collector evidence ${label(update.artifact.status)}: ${requirement}`
    : `Collector evidence ${label(update.artifact.status)}`;
}

export function caseLatestSummary(entry: HistoryCaseEntry): string {
  const latest = entry.updates.at(-1);
  const terminalSummary = entry.progress?.summary;
  if (
    terminalSummary &&
    latest?.kind === "turn" &&
    !isEvaluation(latest.turn) &&
    !isDiscoveryResult(latest.turn)
  ) {
    return compactText(terminalSummary);
  }
  if (latest) return historyUpdateSummary(latest);
  if (terminalSummary) return compactText(terminalSummary);
  if (entry.progress?.state === "active") return "Execution in progress";
  if (entry.progress?.state === "queued")
    return "Waiting for an execution slot";
  if (entry.progress?.state === "assessing") {
    return "Assessing the recorded evidence";
  }
  if (entry.progress?.state === "pending") return "Waiting to be initialized";
  if (entry.progress?.state === "unknown") {
    return "No lifecycle information was reported";
  }
  return "No outcome summary recorded";
}
