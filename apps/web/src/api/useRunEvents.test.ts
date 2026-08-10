import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, act } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { useRunEvents } from "./useRunEvents";

class EventSourceStub {
  static instances: EventSourceStub[] = [];
  addEventListener = vi.fn();
  close = vi.fn();
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor() {
    EventSourceStub.instances.push(this);
  }
}

beforeEach(() => {
  EventSourceStub.instances = [];
  vi.stubGlobal("EventSource", EventSourceStub);
});

function wrapper({ children }: { children: ReactNode }) {
  return createElement(QueryClientProvider, { client: new QueryClient() }, children);
}

it("subscribes to named run-activity events and reports connection text state", () => {
  const { result } = renderHook(() => useRunEvents("run-1"), { wrapper });
  const source = EventSourceStub.instances[0];
  expect(source.addEventListener).toHaveBeenCalledWith("run-activity", expect.any(Function));
  expect(result.current.connectionState).toBe("connecting");
  act(() => source.onopen?.());
  expect(result.current.connectionState).toBe("connected");
  act(() => source.onerror?.());
  expect(result.current.connectionState).toBe("reconnecting");
});

it("deduplicates sequence notifications and batches query invalidation", async () => {
  const client = new QueryClient();
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const { result } = renderHook(() => useRunEvents("run-1"), {
    wrapper: ({ children }) =>
      createElement(QueryClientProvider, { client }, children),
  });
  const handler = EventSourceStub.instances[0].addEventListener.mock.calls.find(
    ([name]) => name === "run-activity",
  )?.[1] as (event: MessageEvent<string>) => void;

  act(() => {
    handler(new MessageEvent("run-activity", { data: JSON.stringify({ sequence: 2 }) }));
    handler(new MessageEvent("run-activity", { data: JSON.stringify({ sequence: 2 }) }));
    handler(new MessageEvent("run-activity", { data: JSON.stringify({ sequence: 3 }) }));
  });
  expect(result.current.lastSequence).toBe(3);
  await act(async () => Promise.resolve());
  expect(invalidate).toHaveBeenCalledTimes(1);
});
