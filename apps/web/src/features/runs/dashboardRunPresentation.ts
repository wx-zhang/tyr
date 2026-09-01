import type {
  Run,
  RunState,
  ScenarioExecutionProgress,
} from "../../api/client";
import { resultDisplay } from "./runTurnHelpers";

const terminalStates: Partial<Record<RunState, true>> = {
  completed: true,
  failed: true,
  cancelled: true,
  interrupted: true,
};

export function compareRunsNewestFirst(left: Run, right: Run): number {
  const leftTime = Date.parse(left.createdAt ?? left.updatedAt ?? "") || 0;
  const rightTime = Date.parse(right.createdAt ?? right.updatedAt ?? "") || 0;
  if (rightTime !== leftTime) return rightTime - leftTime;
  return right.id.localeCompare(left.id);
}

function label(value: string | null | undefined): string {
  if (!value) return "—";
  if (value === "approval_required") return "Approval-gated";
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function stateTone(
  state: string | undefined,
): "info" | "success" | "warning" | "danger" | "neutral" {
  if (state === "completed") return "neutral";
  if (state === "failed") return "danger";
  if (state === "waiting_for_approval") return "warning";
  if (state === "cancelled" || state === "interrupted") return "neutral";
  return "info";
}

function formatAbsolute(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatRelative(value: string | null, now: number): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const deltaSeconds = Math.round((date.getTime() - now) / 1000);
  const absolute = Math.abs(deltaSeconds);
  if (absolute < 5) return "just now";
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  if (absolute < 60) return formatter.format(deltaSeconds, "second");
  if (absolute < 3600)
    return formatter.format(Math.round(deltaSeconds / 60), "minute");
  if (absolute < 86_400)
    return formatter.format(Math.round(deltaSeconds / 3600), "hour");
  if (absolute < 86_400 * 30) {
    return formatter.format(Math.round(deltaSeconds / 86_400), "day");
  }
  return formatAbsolute(value);
}

function resultCounts(executions: ScenarioExecutionProgress[]) {
  return executions.reduce(
    (counts, execution) => {
      const display = resultDisplay(
        execution.verdict,
        execution.objectiveStatus,
        execution.outcome,
      );
      if (display.className === "vulnerable") counts.breach += 1;
      else if (display.className === "protected") counts.protected += 1;
      else counts.inconclusive += 1;
      return counts;
    },
    { breach: 0, protected: 0, inconclusive: 0 },
  );
}

export function dashboardRunPresentation(run: Run, now: number) {
  const when = run.createdAt ?? run.updatedAt ?? run.finishedAt ?? null;
  const taskParts = run.task.split("/").filter(Boolean);
  const executions = run.scenarioExecutions ?? [];
  const counts = resultCounts(executions);
  const live = !terminalStates[run.state as RunState];
  return {
    shortId: run.id.replaceAll("-", "").slice(0, 8),
    title: run.name?.trim() || taskParts[taskParts.length - 1] || run.task,
    source:
      run.source === "cli" ? "CLI" : run.source === "service" ? "Service" : "—",
    stateLabel: label(run.state),
    stateTone: stateTone(run.state),
    actionModeLabel: label(run.configuration?.actionMode),
    actionModeTone: "neutral",
    when,
    relativeWhen: formatRelative(when, now),
    absoluteWhen: formatAbsolute(when),
    live,
    executions,
    counts,
    resultClass:
      counts.breach > 0
        ? "has-breach"
        : executions.length > 0 && counts.protected > 0
          ? "has-no-breach"
          : "has-inconclusive-results",
  } as const;
}
