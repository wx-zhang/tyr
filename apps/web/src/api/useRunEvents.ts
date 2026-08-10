import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { fetchActivity, type ActivityItem, type ActivityPage } from "./client";

export const RUN_EVENT_HEARTBEAT_SECONDS = 15;
export const RUN_EVENT_STALE_MS = RUN_EVENT_HEARTBEAT_SECONDS * 2 * 1000;
export const RUN_EVENT_DISCONNECTED_MS = RUN_EVENT_STALE_MS * 2;

export type RunConnectionState =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "stale"
  | "disconnected";

export type RunEventNotification = {
  sequence: number;
  latestSequence?: number;
  eventType?: string;
  runId?: string;
  activity?: ActivityItem;
};

export type RunEventResync = {
  reason?: string;
  latestSequence?: number;
};

type EventSourceFactory = (url: string) => EventSource;

const defaultEventSourceFactory: EventSourceFactory = (url) => new EventSource(url);

type UseRunEventsOptions = {
  enabled?: boolean;
  eventSourceFactory?: EventSourceFactory;
  onNotification?: (event: RunEventNotification) => void;
  onResync?: (page: ActivityPage) => void;
};

type RunEventsState = {
  connectionState: RunConnectionState;
  lastSequence: number;
  resyncRequired: boolean;
  error: string | null;
};

const apiOrigin = import.meta.env.VITE_API_ORIGIN ?? "http://127.0.0.1:6687";

export function mergeActivityItems(
  current: ActivityItem[],
  incoming: ActivityItem[],
): ActivityItem[] {
  const byId = new Map(current.map((item) => [item.id, item]));
  const bySequence = new Map(current.map((item) => [item.sequence, item.id]));
  for (const item of incoming) {
    const sequenceOwner = bySequence.get(item.sequence);
    if (sequenceOwner && sequenceOwner !== item.id) continue;
    byId.set(item.id, item);
    bySequence.set(item.sequence, item.id);
  }
  return [...byId.values()].sort((left, right) => left.sequence - right.sequence);
}

function parseNotification(data: string): RunEventNotification | null {
  try {
    const payload = JSON.parse(data) as Record<string, unknown>;
    const sequence = Number(payload.sequence);
    return Number.isInteger(sequence) && sequence > 0
      ? {
          sequence,
          latestSequence:
            typeof payload.latestSequence === "number" ? payload.latestSequence : undefined,
          eventType: typeof payload.eventType === "string" ? payload.eventType : undefined,
          runId: typeof payload.runId === "string" ? payload.runId : undefined,
          activity:
            payload.activity && typeof payload.activity === "object"
              ? (payload.activity as ActivityItem)
              : undefined,
        }
      : null;
  } catch {
    return null;
  }
}

function parseResync(data: string): RunEventResync {
  try {
    const payload = JSON.parse(data) as Record<string, unknown>;
    return {
      reason: typeof payload.reason === "string" ? payload.reason : undefined,
      latestSequence:
        typeof payload.latestSequence === "number" ? payload.latestSequence : undefined,
    };
  } catch {
    return {};
  }
}

export function useRunEvents(
  runId: string,
  options: UseRunEventsOptions = {},
): RunEventsState & { resync: () => Promise<void> } {
  const queryClient = useQueryClient();
  const {
    enabled = true,
    eventSourceFactory = defaultEventSourceFactory,
    onNotification,
    onResync,
  } = options;
  const lastSequenceRef = useRef(0);
  const onNotificationRef = useRef(onNotification);
  const onResyncRef = useRef(onResync);
  const invalidationQueued = useRef(false);
  const [state, setState] = useState<RunEventsState>({
    connectionState: "connecting",
    lastSequence: 0,
    resyncRequired: false,
    error: null,
  });

  useEffect(() => {
    onNotificationRef.current = onNotification;
    onResyncRef.current = onResync;
  }, [onNotification, onResync]);

  const invalidate = useCallback(() => {
    if (invalidationQueued.current) return;
    invalidationQueued.current = true;
    queueMicrotask(() => {
      invalidationQueued.current = false;
      void queryClient.invalidateQueries({
        predicate: (query) => {
          const [key, keyRunId] = query.queryKey;
          return (
            keyRunId === runId &&
            [
              "run",
              "run-approvals",
              "run-cases",
              "run-visualization",
              "run-turns",
              "run-relationships",
            ].includes(String(key))
          );
        },
      });
    });
  }, [queryClient, runId]);

  const resync = useCallback(async () => {
    setState((current) => ({ ...current, connectionState: "reconnecting" }));
    try {
      const page = await fetchActivity(runId, { limit: 200 });
      const latestSequence = page.latestSequence || page.items.at(-1)?.sequence || 0;
      lastSequenceRef.current = Math.max(lastSequenceRef.current, latestSequence);
      setState((current) => ({
        ...current,
        connectionState: "connected",
        lastSequence: lastSequenceRef.current,
        resyncRequired: false,
        error: null,
      }));
      onResyncRef.current?.(page);
      invalidate();
    } catch (reason) {
      setState((current) => ({
        ...current,
        connectionState: "disconnected",
        error: reason instanceof Error ? reason.message : "Could not resync run activity",
      }));
    }
  }, [invalidate, runId]);

  useEffect(() => {
    if (!enabled) return undefined;
    const source = eventSourceFactory(
      `${apiOrigin}/api/v1/runs/${encodeURIComponent(runId)}/events`,
    );
    let staleTimer: ReturnType<typeof setTimeout> | undefined;
    let disconnectedTimer: ReturnType<typeof setTimeout> | undefined;

    const clearConnectionTimers = () => {
      if (staleTimer) clearTimeout(staleTimer);
      if (disconnectedTimer) clearTimeout(disconnectedTimer);
    };
    const markStale = () => {
      setState((current) => ({ ...current, connectionState: "stale" }));
      disconnectedTimer = setTimeout(
        () => setState((current) => ({ ...current, connectionState: "disconnected" })),
        RUN_EVENT_DISCONNECTED_MS,
      );
    };
    const armStaleTimer = () => {
      clearConnectionTimers();
      staleTimer = setTimeout(markStale, RUN_EVENT_STALE_MS);
    };
    const markLive = () => {
      setState((current) =>
        current.connectionState === "connected" && current.error === null
          ? current
          : { ...current, connectionState: "connected", error: null },
      );
      armStaleTimer();
    };
    const handleOpen = () => markLive();
    const handleError = () => {
      setState((current) => ({ ...current, connectionState: "reconnecting" }));
      armStaleTimer();
    };
    const handleActivity = (event: Event) => {
      const notification = parseNotification((event as MessageEvent).data);
      if (!notification || notification.sequence <= lastSequenceRef.current) return;
      lastSequenceRef.current = notification.sequence;
      setState((current) => ({
        ...current,
        connectionState: "connected",
        lastSequence: notification.sequence,
        error: null,
      }));
      onNotificationRef.current?.(notification);
      invalidate();
      armStaleTimer();
    };
    const handleResync = (event: Event) => {
      const detail = parseResync((event as MessageEvent).data);
      setState((current) => ({
        ...current,
        connectionState: "stale",
        resyncRequired: true,
        lastSequence: Math.max(current.lastSequence, detail.latestSequence ?? 0),
      }));
      void resync();
    };
    const handleHeartbeat = () => markLive();

    source.addEventListener("run-activity", handleActivity);
    source.addEventListener("resync-required", handleResync);
    source.addEventListener("heartbeat", handleHeartbeat);
    source.onopen = handleOpen;
    source.onerror = handleError;
    armStaleTimer();
    return () => {
      clearConnectionTimers();
      source.removeEventListener?.("run-activity", handleActivity);
      source.removeEventListener?.("resync-required", handleResync);
      source.removeEventListener?.("heartbeat", handleHeartbeat);
      source.close();
    };
  }, [enabled, eventSourceFactory, invalidate, resync, runId]);

  return { ...state, resync };
}
