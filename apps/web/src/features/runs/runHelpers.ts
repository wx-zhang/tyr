import type { RunConnectionState } from "../../api/useRunEvents";

export const terminalStates = new Set([
  "completed",
  "failed",
  "cancelled",
  "interrupted",
]);

export const REFRESH_RATES_MS = [1000, 5000, 10_000, 30_000] as const;
export const DEFAULT_REFRESH_MS = 30_000;
export const REFRESH_STORAGE_KEY = "gamr-run-refresh-ms";

export type RefreshRateMs = (typeof REFRESH_RATES_MS)[number];

export function isRefreshRateMs(value: number): value is RefreshRateMs {
  return (REFRESH_RATES_MS as readonly number[]).includes(value);
}

export function readStoredRefreshMs(): RefreshRateMs {
  try {
    const raw = window.localStorage.getItem(REFRESH_STORAGE_KEY);
    if (!raw) return DEFAULT_REFRESH_MS;
    const parsed = Number(raw);
    return isRefreshRateMs(parsed) ? parsed : DEFAULT_REFRESH_MS;
  } catch {
    return DEFAULT_REFRESH_MS;
  }
}

export function formatRefreshRate(ms: RefreshRateMs): string {
  return `${ms / 1000}s`;
}

export function currentPhaseLabel(
  run: { state?: string; currentPhase?: string | null } | undefined,
  phases: Array<{ id: string; label: string; state: string }> | undefined,
): string {
  if (run?.currentPhase) return run.currentPhase;
  const active = phases?.find((phase) => phase.state === "active");
  if (active) return active.label;
  if (run?.state && terminalStates.has(run.state)) {
    const lastDone = [...(phases ?? [])]
      .reverse()
      .find((phase) => phase.state === "completed");
    if (lastDone) return lastDone.label;
    return run.state;
  }
  return "—";
}

export function connectionLabel(state: RunConnectionState): string {
  return {
    connecting: "Connecting",
    connected: "Live",
    reconnecting: "Reconnecting",
    stale: "Stale",
    disconnected: "Offline",
  }[state];
}

export function connectionDetail(state: RunConnectionState): string {
  return {
    connecting: "Connecting to live updates",
    connected: "Connected to live updates",
    reconnecting: "Reconnecting to live updates",
    stale: "Live updates are stale",
    disconnected: "Disconnected from live updates",
  }[state];
}

export function formatRelative(value: string | null | undefined, now: number): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  const deltaSeconds = Math.round((date.valueOf() - now) / 1000);
  const absolute = Math.abs(deltaSeconds);
  if (absolute < 5) return "just now";
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  if (absolute < 60) return formatter.format(deltaSeconds, "second");
  if (absolute < 3600) {
    return formatter.format(Math.round(deltaSeconds / 60), "minute");
  }
  if (absolute < 86_400) {
    return formatter.format(Math.round(deltaSeconds / 3600), "hour");
  }
  return formatter.format(Math.round(deltaSeconds / 86_400), "day");
}

export function stageStatusLabel(
  phaseState: string,
  waitingForTyr: boolean,
  agentWorking: boolean,
  isActive: boolean,
): string | null {
  if (isActive && waitingForTyr) return "Waiting for Tyr";
  if (isActive && agentWorking) return "Agent working";
  if (phaseState === "active") return "Active";
  if (phaseState === "failed") return "Failed";
  if (phaseState === "cancelled") return "Cancelled";
  if (phaseState === "interrupted") return "Interrupted";
  if (phaseState === "skipped") return "Off";
  return null;
}
