import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { RunPage } from "./RunPage";

const visualization = {
  run: {
    id: "run-1",
    state: "running",
    actionMode: "read_only",
    dataset: "first-plan",
    startedAt: "2026-08-08T10:00:00Z",
    latestUpdateAt: "2026-08-08T10:03:00Z",
    finishedAt: null,
    outcome: null,
    currentPhase: "running",
    currentCaseIds: ["case-alpha"],
  },
  phases: [
    { id: "queued", label: "Queued", state: "completed", latestSequence: 1 },
    { id: "preparing", label: "Preparing", state: "completed", latestSequence: 2 },
    { id: "discovering", label: "Discovering", state: "completed", latestSequence: 3 },
    { id: "running", label: "Running", state: "active", latestSequence: 5 },
    { id: "scientist", label: "Scientist", state: "pending", latestSequence: null },
    { id: "evaluating", label: "Evaluating", state: "pending", latestSequence: null },
    { id: "reporting", label: "Reporting", state: "pending", latestSequence: null },
  ],
  cases: [],
  attention: { pendingApprovalCount: 0, blockers: [], unsettledTyrWork: false },
  counts: { totalKnown: true, totalCases: 1, completedCases: 0 },
  latestSequence: 5,
  latestActivity: null,
};

const turns = {
  items: [
    {
      id: "turn-1",
      sequence: 1,
      number: 1,
      stage: "discovery",
      caseId: null,
      status: "completed",
      agentMessage: "**Inspect** the workspace.",
      tyrMessage: "- Alice\n- Bob",
      occurredAt: "2026-08-08T10:01:00Z",
      repliedAt: "2026-08-08T10:01:12Z",
    },
    {
      id: "turn-2",
      sequence: 2,
      number: 1,
      stage: "case",
      caseId: "case-alpha",
      status: "waiting_for_tyr",
      agentMessage: "Run `read_file`.",
      tyrMessage: null,
      occurredAt: "2026-08-08T10:02:00Z",
      repliedAt: null,
    },
  ],
  omittedBefore: 0,
  nextCursor: null,
  latestSequence: 2,
};

class EventSourceStub {
  addEventListener = vi.fn();
  removeEventListener = vi.fn();
  close = vi.fn();
}

beforeEach(() => {
  vi.stubGlobal("EventSource", EventSourceStub);
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/visualization")) {
        return Promise.resolve({ ok: true, json: async () => visualization });
      }
      if (url.includes("/turns")) {
        return Promise.resolve({ ok: true, json: async () => turns });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ items: [], latestSequence: 0 }),
      });
    }),
  );
});

function renderPage() {
  const queryClient = new QueryClient();
  const result = render(
    <MemoryRouter initialEntries={["/runs/run-1"]}>
      <QueryClientProvider client={queryClient}>
        <Routes>
          <Route path="/runs/:id" element={<RunPage />} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  );
  return { ...result, queryClient };
}

function renderPageWithCachedTurns() {
  const queryClient = new QueryClient();
  queryClient.setQueryData(["run-turns", "run-1"], turns);
  return render(
    <MemoryRouter initialEntries={["/runs/run-1"]}>
      <QueryClientProvider client={queryClient}>
        <Routes>
          <Route path="/runs/:id" element={<RunPage />} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

it("shows the run lifecycle and grouped Agent to Tyr turns newest first", async () => {
  const { container } = renderPage();

  expect(await screen.findByRole("heading", { name: "Run run-1" })).toBeInTheDocument();
  expect(await screen.findByText("first-plan")).toBeInTheDocument();
  expect(screen.getByText("Read-only")).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "Run stages" })).toBeInTheDocument();
  expect(screen.getByText("Preparing")).toBeInTheDocument();
  expect(screen.getByText("Evaluating")).toBeInTheDocument();
  expect(screen.getAllByText("Waiting for Tyr").length).toBeGreaterThan(0);
  expect(screen.getByRole("heading", { name: "Discovery - Turn 1" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Executing evaluation - Turn 1" })).toBeInTheDocument();
  expect(screen.getByText("case-alpha")).toBeInTheDocument();
  expect(screen.getByText(/Evaluation name/)).toBeInTheDocument();
  expect(screen.getByText("Inspect")).toHaveProperty("tagName", "STRONG");
  expect(screen.getByText("Alice").closest("li")).toBeInTheDocument();
  expect(screen.queryByText("Agent request sent · Tyr reply pending")).not.toBeInTheDocument();
  expect(container.querySelector(".stage-active")).not.toBeNull();
  expect(container.querySelector(".stage-waiting")).not.toBeNull();
  expect(screen.getByText("Waited 12s")).toBeInTheDocument();
  expect(container.querySelector(".turn-wait-live")?.textContent).toMatch(/\d+:\d{2}/);
  const turnTimes = screen.getAllByRole("time");
  expect(turnTimes.length).toBeGreaterThanOrEqual(2);
  expect(turnTimes[0]).toHaveAttribute("dateTime", "2026-08-08T10:02:00Z");
  expect(turnTimes[0].textContent).not.toBe("—");
  expect(turnTimes[0].closest(".turn-timing")).not.toBeNull();
  expect(container.querySelector(".turn-timing-sep")?.textContent).toBe("|");
  expect(screen.getByText("read_file")).toHaveProperty("tagName", "CODE");
  expect(container.querySelector(".turn-waiting")).not.toBeNull();
  expect(container.querySelector(".tyr-waiting")).not.toBeNull();
  expect(container.querySelector(".tyr-waiting-spinner")).not.toBeNull();
  expect(container.querySelector(".tyr-waiting-ellipsis")).not.toBeNull();
  expect(
    [...container.querySelectorAll(".turn")].map((element) => element.getAttribute("data-turn-id")),
  ).toEqual(["turn-2", "turn-1"]);
});

it("shows cached turns immediately without marking the initial page as new", async () => {
  renderPageWithCachedTurns();

  expect(await screen.findByText("read_file")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Show \d+ new turns?/ })).not.toBeInTheDocument();
  expect(screen.queryByText("No turns have been persisted yet.")).not.toBeInTheDocument();
});

it("shows scientist generation failures on completed runs without Unknown stage", async () => {
  vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/visualization")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          ...visualization,
          run: {
            ...visualization.run,
            state: "completed",
            currentPhase: null,
            finishedAt: "2026-08-08T10:10:00Z",
            outcome: "completed",
          },
          phases: visualization.phases.map((phase) => ({
            ...phase,
            state: phase.id === "scientist" ? "completed" : "completed",
          })),
        }),
      } as Response);
    }
    if (url.includes("/turns")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          items: [
            {
              id: "sci-1",
              sequence: 3,
              number: 1,
              stage: "scientist",
              caseId: null,
              status: "failed",
              agentMessage: "scientist scenario 1 invalid: missing objective",
              tyrMessage: null,
              occurredAt: "2026-08-08T10:05:00Z",
              repliedAt: null,
            },
            ...turns.items,
          ],
          omittedBefore: 0,
          nextCursor: null,
          latestSequence: 3,
        }),
      } as Response);
    }
    return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
  });

  const { container } = renderPage();

  expect(await screen.findByRole("heading", { name: "Scientist - Iteration 1" })).toBeInTheDocument();
  expect(screen.getByText(/missing objective/)).toBeInTheDocument();
  expect(screen.getByText("Failed")).toBeInTheDocument();
  expect(container.querySelector(".turn-scientist")).not.toBeNull();
  expect(screen.queryByText("Unknown")).not.toBeInTheDocument();
  expect(screen.getAllByText("Scientist").length).toBeGreaterThan(0);
});

it("removes the previous evidence navigation and controls", async () => {
  renderPage();
  await screen.findByRole("heading", { name: "Turns" });

  expect(screen.queryByRole("link", { name: "Cases" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Artifacts" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Cancel run" })).not.toBeInTheDocument();
  expect(screen.queryByText("Relationship graph")).not.toBeInTheDocument();
});

it("does not render raw HTML from conversation markdown", async () => {
  vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/visualization")) {
      return Promise.resolve({ ok: true, json: async () => visualization } as Response);
    }
    if (url.includes("/turns")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          ...turns,
          items: [
            {
              ...turns.items[0],
              agentMessage: '<script>alert("unsafe")</script>Visible text',
              tyrMessage: "![remote](https://example.com/tracker.png)",
            },
          ],
        }),
      } as Response);
    }
    return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
  });

  const { container } = renderPage();
  await screen.findByRole("heading", { name: "Turns" });
  expect(container.querySelector("script")).toBeNull();
  expect(container.querySelector("img")).toBeNull();
});

it("holds newer turns behind a concise action while reviewing older content", async () => {
  const { queryClient } = renderPage();
  await screen.findByText("read_file");
  Object.defineProperty(window, "scrollY", { configurable: true, value: 600 });
  fireEvent.scroll(window);
  vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/visualization")) {
      return Promise.resolve({ ok: true, json: async () => visualization } as Response);
    }
    if (url.includes("/turns")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          ...turns,
          latestSequence: 3,
          items: [
            ...turns.items,
            {
              ...turns.items[1],
              id: "turn-3",
              sequence: 3,
              number: 2,
              agentMessage: "Newest request",
            },
          ],
        }),
      } as Response);
    }
    return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
  });

  await queryClient.invalidateQueries({ queryKey: ["run-turns", "run-1"] });
  expect(await screen.findByRole("button", { name: "Show 1 new turn" })).toBeInTheDocument();
  expect(screen.queryByText("Newest request")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Show 1 new turn" }));
  await waitFor(() => expect(screen.getByText("Newest request")).toBeInTheDocument());
});

it("holds a new Tyr reply behind the same action while reviewing older content", async () => {
  const { queryClient } = renderPage();
  await screen.findByText("read_file");
  Object.defineProperty(window, "scrollY", { configurable: true, value: 600 });
  fireEvent.scroll(window);
  vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/visualization")) {
      return Promise.resolve({ ok: true, json: async () => visualization } as Response);
    }
    if (url.includes("/turns")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          ...turns,
          items: turns.items.map((turn) => turn.id === "turn-2"
            ? { ...turn, status: "completed", tyrMessage: "Request allowed" }
            : turn),
        }),
      } as Response);
    }
    return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
  });

  await queryClient.invalidateQueries({ queryKey: ["run-turns", "run-1"] });
  expect(await screen.findByRole("button", { name: "Show 1 new turn" })).toBeInTheDocument();
  expect(screen.queryByText("Request allowed")).not.toBeInTheDocument();
});

it("defaults refresh rate to 30s and lets the operator change it", async () => {
  window.localStorage.removeItem("gamr-run-refresh-ms");
  renderPage();
  await screen.findByRole("heading", { name: "Run run-1" });

  const group = screen.getByRole("radiogroup", { name: "Refresh rate" });
  expect(group).toBeInTheDocument();
  expect(screen.getByRole("radio", { name: "1s" })).toHaveAttribute("aria-checked", "false");
  expect(screen.getByRole("radio", { name: "5s" })).toHaveAttribute("aria-checked", "false");
  expect(screen.getByRole("radio", { name: "10s" })).toHaveAttribute("aria-checked", "false");
  expect(screen.getByRole("radio", { name: "30s" })).toHaveAttribute("aria-checked", "true");

  fireEvent.click(screen.getByRole("radio", { name: "5s" }));
  expect(screen.getByRole("radio", { name: "5s" })).toHaveAttribute("aria-checked", "true");
  expect(screen.getByRole("radio", { name: "30s" })).toHaveAttribute("aria-checked", "false");
  expect(window.localStorage.getItem("gamr-run-refresh-ms")).toBe("5000");
});
