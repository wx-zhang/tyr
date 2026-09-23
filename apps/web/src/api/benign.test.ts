import { afterEach, expect, it, vi } from "vitest";
import { draft } from "./benign";

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

it("turns non-JSON server failures into a useful HTTP error", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Internal Server Error", { status: 500 })));
  await expect(draft("invite", "mira", "UTC")).rejects.toThrow("HTTP 500");
});

it("bounds the browser wait even if the server never responds", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("fetch", vi.fn((_url: string, init: RequestInit) => new Promise((_, reject) => {
    init.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
  })));
  const assertion = expect(draft("invite", "mira", "UTC")).rejects.toThrow("timed out");
  await vi.advanceTimersByTimeAsync(75000);
  await assertion;
});
