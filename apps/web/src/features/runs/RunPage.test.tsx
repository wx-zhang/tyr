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
  cases: [
    {
      caseId: "case-alpha",
      order: 1,
      state: "active",
      verdict: null,
      latestSequence: 5,
    },
    {
      caseId: "case-beta",
      order: 2,
      state: "pending",
      verdict: null,
      latestSequence: null,
    },
  ],
  attention: { pendingApprovalCount: 0, blockers: [], unsettledTyrWork: false },
  counts: { totalKnown: true, totalCases: 2, completedCases: 0 },
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
  expect(screen.getAllByText("case-alpha").length).toBeGreaterThan(0);
  expect(screen.getByText(/Evaluation name/)).toBeInTheDocument();
  const caseDetails = screen.getByText("Test cases").closest("details");
  expect(caseDetails).not.toBeNull();
  expect(caseDetails).not.toHaveAttribute("open");
  expect(screen.getByText("0/2")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Test cases"));
  expect(caseDetails).toHaveAttribute("open");
  expect(screen.getByRole("list", { name: "Test cases" })).toBeInTheDocument();
  expect(screen.getByText("case-beta")).toBeInTheDocument();
  expect(screen.getByText("Pending")).toBeInTheDocument();
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

it("shows ready scientist generation turns as iteration cards", async () => {
  vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/visualization")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          ...visualization,
          run: {
            ...visualization.run,
            currentPhase: "scientist",
          },
          phases: visualization.phases.map((phase) => ({
            ...phase,
            state:
              phase.id === "scientist"
                ? "active"
                : phase.id === "evaluating" || phase.id === "reporting"
                  ? "pending"
                  : "completed",
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
              id: "sci-ready",
              sequence: 4,
              number: 2,
              stage: "scientist",
              caseId: "scientist-2",
              status: "ready",
              agentMessage: "New delivery path scenario ready",
              tyrMessage: null,
              occurredAt: "2026-08-08T10:06:00Z",
              repliedAt: null,
            },
            ...turns.items,
          ],
          omittedBefore: 0,
          nextCursor: null,
          latestSequence: 4,
        }),
      } as Response);
    }
    if (url.match(/\/api\/v1\/runs\/run-1$/) || url.endsWith("/runs/run-1")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          id: "run-1",
          experimentId: "exp-1",
          source: "service",
          state: "running",
          dataset: "first-plan",
          configuration: {
            actionMode: "read_only",
            model: "test",
            maxTurns: 10,
            discoveryTurns: 1,
            scientistIterations: 2,
          },
        }),
      } as Response);
    }
    return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
  });

  const { container } = renderPage();

  expect(await screen.findByRole("heading", { name: "Scientist - Iteration 2" })).toBeInTheDocument();
  expect(screen.getByText("New delivery path scenario ready")).toBeInTheDocument();
  expect(screen.getByText("Ready")).toBeInTheDocument();
  expect(container.querySelector(".turn-scientist")).not.toBeNull();
  expect(container.querySelector(".turn-messages-single")).not.toBeNull();
  expect(await screen.findByText("Scientist iterations")).toBeInTheDocument();
  expect(screen.getByText("2")).toBeInTheDocument();
});

it("removes the previous evidence navigation and controls", async () => {
  renderPage();
  await screen.findByRole("heading", { name: "Turns" });

  expect(screen.queryByRole("link", { name: "Cases" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Artifacts" })).not.toBeInTheDocument();
  expect(screen.queryByText("Relationship graph")).not.toBeInTheDocument();
});

it("shows Cancel run while the run is live", async () => {
  renderPage();
  expect(await screen.findByRole("button", { name: "Cancel run" })).toBeInTheDocument();
});

it("hides Cancel run after the run ends", async () => {
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
          phases: visualization.phases.map((phase) => ({ ...phase, state: "completed" })),
        }),
      } as Response);
    }
    if (url.includes("/turns")) {
      return Promise.resolve({ ok: true, json: async () => turns } as Response);
    }
    return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
  });

  renderPage();
  await screen.findByRole("heading", { name: "Run run-1" });
  expect(screen.queryByRole("button", { name: "Cancel run" })).not.toBeInTheDocument();
});

it("cancels a live run after confirmation", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  let cancelled = false;
  vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/cancel") && init?.method === "POST") {
      cancelled = true;
      return Promise.resolve({
        ok: true,
        json: async () => ({
          id: "run-1",
          state: "cancelled",
          source: "service",
          experimentId: null,
          dataset: "first-plan",
          configuration: {
            actionMode: "read_only",
            model: "test",
            maxTurns: 10,
            discoveryTurns: 1,
            scientistIterations: 0,
          },
        }),
      } as Response);
    }
    if (url.includes("/visualization")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          ...visualization,
          run: {
            ...visualization.run,
            state: cancelled ? "cancelled" : "running",
            finishedAt: cancelled ? "2026-08-08T10:05:00Z" : null,
            outcome: cancelled ? "cancelled" : null,
            currentPhase: cancelled ? null : "running",
          },
          phases: visualization.phases.map((phase) => ({
            ...phase,
            state: cancelled
              ? phase.id === "running"
                ? "cancelled"
                : phase.state === "active"
                  ? "cancelled"
                  : phase.state
              : phase.state,
          })),
        }),
      } as Response);
    }
    if (url.includes("/turns")) {
      return Promise.resolve({ ok: true, json: async () => turns } as Response);
    }
    return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
  });

  renderPage();
  fireEvent.click(await screen.findByRole("button", { name: "Cancel run" }));
  expect(confirm).toHaveBeenCalled();
  await waitFor(() => {
    expect(screen.queryByRole("button", { name: "Cancel run" })).not.toBeInTheDocument();
  });
  expect(screen.getAllByText("Cancelled").length).toBeGreaterThan(0);
  confirm.mockRestore();
});

it("does not cancel when the operator dismisses confirmation", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  renderPage();
  fireEvent.click(await screen.findByRole("button", { name: "Cancel run" }));
  expect(confirm).toHaveBeenCalled();
  await waitFor(() => {
    const cancelCalls = vi.mocked(fetch).mock.calls.filter(([input, init]) => {
      return String(input).includes("/cancel") && (init as RequestInit | undefined)?.method === "POST";
    });
    expect(cancelCalls).toHaveLength(0);
  });
  expect(screen.getByRole("button", { name: "Cancel run" })).toBeInTheDocument();
  confirm.mockRestore();
});

it("shows an error when cancel fails", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/cancel") && init?.method === "POST") {
      return Promise.resolve({ ok: false, status: 500, json: async () => ({}) } as Response);
    }
    if (url.includes("/visualization")) {
      return Promise.resolve({ ok: true, json: async () => visualization } as Response);
    }
    if (url.includes("/turns")) {
      return Promise.resolve({ ok: true, json: async () => turns } as Response);
    }
    return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
  });

  renderPage();
  fireEvent.click(await screen.findByRole("button", { name: "Cancel run" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Request failed: 500");
  expect(screen.getByRole("button", { name: "Cancel run" })).toBeEnabled();
  confirm.mockRestore();
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

it("shows agent working when the run is live and the latest turn is complete", async () => {
  vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/visualization")) {
      return Promise.resolve({ ok: true, json: async () => visualization } as Response);
    }
    if (url.includes("/turns")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          items: [
            {
              id: "turn-done",
              sequence: 1,
              number: 1,
              stage: "case",
              caseId: "case-alpha",
              status: "completed",
              agentMessage: "Upload the file.",
              tyrMessage: "The exact HTTP status code was 201.",
              occurredAt: "2026-08-08T10:01:00Z",
              repliedAt: "2026-08-08T10:01:28Z",
            },
          ],
          omittedBefore: 0,
          nextCursor: null,
          latestSequence: 1,
        }),
      } as Response);
    }
    return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
  });

  const { container } = renderPage();
  expect(
    await screen.findByText("Next turn will appear when the agent sends a message."),
  ).toBeInTheDocument();
  expect(screen.getByRole("status", { name: "Awaiting next turn" })).toBeInTheDocument();
  expect(screen.getAllByText("Agent working").length).toBeGreaterThan(0);
  expect(container.querySelector(".pending-next-turn")).not.toBeNull();
  expect(container.querySelector(".stage-working")).not.toBeNull();
  expect(screen.queryByText("Waiting for Tyr")).not.toBeInTheDocument();
});
it("does not show agent working while waiting for Tyr", async () => {
  renderPage();
  await screen.findByText("read_file");
  expect(screen.getAllByText("Waiting for Tyr").length).toBeGreaterThan(0);
  expect(screen.queryByText("Agent working")).not.toBeInTheDocument();
});

it("does not show agent working after the run ends", async () => {
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
          phases: visualization.phases.map((phase) => ({ ...phase, state: "completed" })),
        }),
      } as Response);
    }
    if (url.includes("/turns")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          items: [
            {
              ...turns.items[0],
              status: "completed",
              tyrMessage: "Done",
              repliedAt: "2026-08-08T10:01:12Z",
            },
          ],
          omittedBefore: 0,
          nextCursor: null,
          latestSequence: 1,
        }),
      } as Response);
    }
    return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
  });

  renderPage();
  await screen.findByText("Done");
  expect(screen.queryByText("Agent working")).not.toBeInTheDocument();
});
