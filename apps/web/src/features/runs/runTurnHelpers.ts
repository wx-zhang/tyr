import type { CaseProgress, RunTurn } from "../../api/client";

export function label(value: string | null | undefined): string {
  if (!value) return "—";
  if (value === "read_only") return "Read-only";
  if (value === "approval_required") return "Actions Allowed";
  if (value === "scientist_only") return "Scientist only";
  if (value === "cases") return "Test cases";
  if (value === "waiting_for_tyr") return "Waiting for Tyr";
  if (value === "case") return "Executing evaluation";
  if (value === "scientist") return "Scientist";
  if (value === "generating") return "Generating";
  if (value === "ready") return "Ready";
  if (value === "skipped") return "Skipped";
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function tone(
  state: string | null | undefined,
): "info" | "success" | "warning" | "danger" | "neutral" {
  if (
    state === "completed" ||
    state === "ready" ||
    state === "protected" ||
    state === "pass" ||
    state === "passed"
  ) {
    return "success";
  }
  if (state === "failed" || state === "vulnerable" || state === "fail") {
    return "danger";
  }
  if (
    state === "waiting_for_approval" ||
    state === "generating" ||
    state === "inconclusive" ||
    state === "partial"
  ) {
    return "warning";
  }
  if (state === "waiting_for_tyr") return "info";
  if (
    state === "cancelled" ||
    state === "interrupted" ||
    state === "blocked" ||
    state === "unknown"
  ) {
    return "danger";
  }
  return "neutral";
}

export type ResultDisplay = {
  label: string;
  tone: ReturnType<typeof tone>;
  className: string;
};

export function resultDisplay(
  verdict: string | null | undefined,
  objectiveStatus: string | null | undefined,
  outcome: string | null | undefined,
): ResultDisplay {
  if (
    verdict === "protected" ||
    (verdict !== "vulnerable" && outcome === "failed")
  ) {
    return { label: "No breach", tone: "success", className: "protected" };
  }
  if (
    verdict === "vulnerable" ||
    (verdict === "inconclusive" && objectiveStatus === "partial")
  ) {
    return {
      label: `Vulnerability Exposed${objectiveStatus === "partial" ? " (partial)" : ""}`,
      tone: "danger",
      className: "vulnerable",
    };
  }
  return {
    label: label(verdict),
    tone: tone(verdict),
    className: verdict ?? "unknown",
  };
}

export function caseStatus(item: CaseProgress): {
  label: string;
  tone: ReturnType<typeof tone>;
} {
  if (item.verdict) {
    return resultDisplay(item.verdict, item.objectiveStatus, item.outcome);
  }
  return caseLifecycleStatus(item);
}

export function caseLifecycleStatus(item: CaseProgress): {
  label: string;
  tone: ReturnType<typeof tone>;
} {
  if (item.state === "pending")
    return { label: "Not started", tone: "neutral" };
  if (item.state === "queued") return { label: "Queued", tone: "neutral" };
  if (item.state === "active" || item.state === "running") {
    return { label: "Running", tone: "info" };
  }
  if (item.state === "assessing")
    return { label: "Assessing", tone: "warning" };
  if (item.state === "unknown") {
    return { label: "Status unavailable", tone: "neutral" };
  }
  return { label: label(item.state), tone: tone(item.state) };
}

export function isScientistGeneration(turn: RunTurn): boolean {
  return (
    turn.stage === "scientist" &&
    (turn.updateType === "scientist_generation" ||
      (!turn.tyrMessage &&
        ["generating", "failed", "ready", "completed"].includes(turn.status)))
  );
}

export function contentOverlapLabel(status: string): string {
  if (status === "confirmed") return "Confirmed overlap";
  if (status === "not_found") return "No overlap found";
  if (status === "inconclusive") return "Needs review";
  return "Not checked";
}

export function isEvaluation(turn: RunTurn): boolean {
  return turn.updateType === "evaluation";
}

export function isDiscoveryResult(turn: RunTurn): boolean {
  return turn.updateType === "discovery";
}

export function discoveryFields(
  message: string,
): Array<{ name: string; value: string }> {
  return message
    .split("\n")
    .map((line) => {
      const match = line.match(/^([^:]+):\s*(.+)$/);
      if (!match) return null;
      return { name: match[1].trim(), value: match[2].trim() };
    })
    .filter(
      (field): field is { name: string; value: string } => field !== null,
    );
}

export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(date);
}

export function elapsedMs(
  start: string | null | undefined,
  end: number,
): number | null {
  if (!start) return null;
  const date = new Date(start);
  if (Number.isNaN(date.valueOf())) return null;
  return Math.max(0, end - date.valueOf());
}

export function formatDuration(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function formatWaited(ms: number): string {
  if (ms < 1000) return "Waited <1s";
  const totalSeconds = Math.round(ms / 1000);
  if (totalSeconds < 60) return `Waited ${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes < 60) {
    return seconds ? `Waited ${minutes}m ${seconds}s` : `Waited ${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  const remainMinutes = minutes % 60;
  return remainMinutes
    ? `Waited ${hours}h ${remainMinutes}m`
    : `Waited ${hours}h`;
}

export function turnWaitMs(turn: RunTurn, now: number): number | null {
  if (!turn.occurredAt) return null;
  if (turn.repliedAt) {
    const start = new Date(turn.occurredAt).valueOf();
    const end = new Date(turn.repliedAt).valueOf();
    if (Number.isNaN(start) || Number.isNaN(end)) return null;
    return Math.max(0, end - start);
  }
  if (turn.status === "waiting_for_tyr" && !turn.tyrMessage) {
    return elapsedMs(turn.occurredAt, now);
  }
  return null;
}
