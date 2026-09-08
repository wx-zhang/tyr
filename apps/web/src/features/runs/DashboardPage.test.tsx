import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { DashboardPage } from "./DashboardPage";

function run(overrides: Record<string, unknown> = {}) {
  return {
    id: "run-1111",
    experimentId: null,
    source: "service",
    state: "completed",
    task: "tasks/exfiltrate-important-txt",
    configuration: {
      actionMode: "read_only",
      model: "test",
      maxTurns: 10,
      discoveryTurns: 1,
      scientistIterations: 0,
    },
    createdAt: "2026-08-08T10:00:00Z",
    updatedAt: "2026-08-08T10:05:00Z",
    finishedAt: "2026-08-08T10:05:00Z",
    scenarioExecutions: [],
    ...overrides,
  };
}

let runs: ReturnType<typeof run>[] = [];

beforeEach(() => {
  runs = [
    run({ id: "run-1111", task: "tasks/exfiltrate-important-txt" }),
    run({
      id: "run-2222",
      task: "tasks/second-plan",
      state: "running",
      finishedAt: null,
    }),
  ];
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (url.endsWith("/api/v1/runs") && method === "GET") {
          return Promise.resolve({
            ok: true,
            json: async () => runs,
          } as Response);
        }
        if (
          url.includes("/api/v1/runs/") &&
          url.endsWith("/cancel") &&
          method === "POST"
        ) {
          const id = url.split("/").slice(-2)[0];
          const target = runs.find((item) => item.id === id);
          if (target) target.state = "cancelled";
          return Promise.resolve({
            ok: true,
            json: async () => target ?? {},
          } as Response);
        }
        if (url.includes("/api/v1/runs/") && method === "DELETE") {
          const id = url.split("/").pop();
          runs = runs.filter((item) => item.id !== id);
          return Promise.resolve({
            ok: true,
            status: 204,
            json: async () => ({}),
          } as Response);
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({}),
        } as Response);
      }),
  );
});

function renderPage(queryClient = new QueryClient()) {
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <DashboardPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

it("combines search and state filters and restores all Experiments", async () => {
  renderPage();
  await screen.findByText("second-plan");
  fireEvent.change(screen.getByLabelText("Search Experiments"), {
    target: { value: "RUN-2222" },
  });
  expect(
    screen.queryByText("exfiltrate-important-txt"),
  ).not.toBeInTheDocument();
  expect(screen.getByText("second-plan")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Experiment state"), {
    target: { value: "completed" },
  });
  expect(screen.queryByText("second-plan")).not.toBeInTheDocument();
  expect(screen.getByText("No matching Experiments")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(screen.getByText("second-plan")).toBeInTheDocument();
  expect(screen.getByText("exfiltrate-important-txt")).toBeInTheDocument();
});

it("selects only visible Experiments and clears selection when filters change", async () => {
  runs.push(run({ id: "run-3333", task: "tasks/third-plan" }));
  renderPage();
  await screen.findByText("third-plan");
  fireEvent.change(screen.getByLabelText("Search Experiments"), {
    target: { value: "third-plan" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Select" }));
  fireEvent.click(
    screen.getByRole("checkbox", { name: "Select all deletable Experiments" }),
  );
  expect(
    screen.getByRole("button", { name: "Delete 1 selected" }),
  ).toBeEnabled();
  fireEvent.change(screen.getByLabelText("Search Experiments"), {
    target: { value: "" },
  });
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Select" }));
  expect(
    screen.getByRole("button", { name: "Delete selected" }),
  ).toBeDisabled();
});

function listRequests() {
  return vi
    .mocked(fetch)
    .mock.calls.filter(([input]) => String(input).endsWith("/api/v1/runs"));
}

function findCard(text: string): HTMLElement {
  const card = screen.getByText(text).closest("article");
  expect(card).not.toBeNull();
  return card as HTMLElement;
}

it("shows the run's own name instead of the task when one was set", async () => {
  runs = [
    run({
      id: "run-5555",
      task: "tasks/exfiltrate-important-txt",
      name: "Nightly red team",
    }),
  ];
  renderPage();

  await screen.findByText("Nightly red team");
  expect(
    screen.queryByText("exfiltrate-important-txt"),
  ).not.toBeInTheDocument();
});

it("falls back to the task label when the run has no name", async () => {
  runs = [
    run({ id: "run-6666", task: "tasks/exfiltrate-important-txt", name: null }),
  ];
  renderPage();

  await screen.findByText("exfiltrate-important-txt");
});

it("deletes a single finished session after confirmation", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderPage();

  await screen.findByText("exfiltrate-important-txt");
  const card = findCard("exfiltrate-important-txt");
  fireEvent.click(within(card).getByRole("button", { name: "Delete" }));

  expect(confirm).toHaveBeenCalled();
  await waitFor(() => {
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/runs/run-1111"),
      expect.objectContaining({ method: "DELETE" }),
    );
  });
  confirm.mockRestore();
});

it("disables delete but offers Stop for a run that is still live", async () => {
  renderPage();
  await screen.findByText("exfiltrate-important-txt");
  const liveCard = findCard("second-plan");

  expect(
    within(liveCard).getByRole("button", { name: "Delete" }),
  ).toBeDisabled();
  expect(within(liveCard).getByRole("button", { name: "Stop" })).toBeEnabled();
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
});

it("stops a live run from the dashboard after confirmation", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderPage();

  await screen.findByText("exfiltrate-important-txt");
  const liveCard = findCard("second-plan");
  fireEvent.click(within(liveCard).getByRole("button", { name: "Stop" }));

  expect(confirm).toHaveBeenCalled();
  await waitFor(() => {
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/runs/run-2222/cancel"),
      expect.objectContaining({ method: "POST" }),
    );
  });
  confirm.mockRestore();
});

it("allows deleting a queued run directly without stopping it first", async () => {
  runs = [
    run({
      id: "run-4444",
      task: "tasks/fourth-plan",
      state: "queued",
      finishedAt: null,
    }),
  ];
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderPage();

  await screen.findByText("fourth-plan");
  const card = findCard("fourth-plan");
  expect(within(card).getByRole("button", { name: "Delete" })).toBeEnabled();
  fireEvent.click(within(card).getByRole("button", { name: "Delete" }));

  expect(confirm).toHaveBeenCalled();
  await waitFor(() => {
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/runs/run-4444"),
      expect.objectContaining({ method: "DELETE" }),
    );
  });
  confirm.mockRestore();
});

it("hides selection checkboxes until Select is chosen", async () => {
  renderPage();
  await screen.findByText("exfiltrate-important-txt");

  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  const select = screen.getByRole("button", { name: "Select" });
  expect(select.closest(".page-header")).not.toBeNull();
  fireEvent.click(select);

  expect(
    screen.getByRole("checkbox", { name: "Select all deletable Experiments" }),
  ).toBeInTheDocument();
  expect(
    screen.getAllByRole("checkbox", { name: /Select Experiment/ }).length,
  ).toBeGreaterThan(0);
  expect(
    screen
      .getAllByRole("checkbox", { name: /Select Experiment/ })[0]
      .closest(".experiment-card-header"),
  ).not.toBeNull();
  expect(
    screen.getByRole("button", { name: "Delete selected" }),
  ).toBeDisabled();

  const liveCard = findCard("second-plan");
  expect(
    within(liveCard).getByRole("checkbox", { name: /Select Experiment/ }),
  ).toBeDisabled();
});

it("bulk-deletes selected sessions from the toolbar", async () => {
  runs = [
    run({ id: "run-1111", task: "tasks/exfiltrate-important-txt" }),
    run({ id: "run-3333", task: "tasks/third-plan" }),
  ];
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderPage();

  await screen.findByText("exfiltrate-important-txt");
  await screen.findByText("third-plan");
  fireEvent.click(screen.getByRole("button", { name: "Select" }));
  const selectAll = screen.getByRole("checkbox", {
    name: "Select all deletable Experiments",
  });
  fireEvent.click(selectAll);

  const bulkButton = await screen.findByRole("button", {
    name: "Delete 2 selected",
  });
  fireEvent.click(bulkButton);

  expect(confirm).toHaveBeenCalled();
  await waitFor(() => {
    expect(
      screen.queryByRole("button", {
        name: /Delete \d+ selected|Delete selected/,
      }),
    ).not.toBeInTheDocument();
  });
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  const deleteCalls = vi.mocked(fetch).mock.calls.filter(([, init]) => {
    return (init as RequestInit | undefined)?.method === "DELETE";
  });
  expect(deleteCalls).toHaveLength(2);
  confirm.mockRestore();
});

it("refreshes runs when revisiting with a retained query cache", async () => {
  const queryClient = new QueryClient();
  const firstRender = renderPage(queryClient);

  await screen.findByText("exfiltrate-important-txt");
  expect(listRequests()).toHaveLength(1);

  firstRender.unmount();
  runs = [
    ...runs,
    run({ id: "run-cli-3333", source: "cli", task: "tasks/cli-plan" }),
  ];
  renderPage(queryClient);

  const cliTask = await screen.findByText("cli-plan");
  expect(listRequests()).toHaveLength(2);
  expect(
    within(cliTask.closest("article") as HTMLElement).getByText("CLI"),
  ).toBeInTheDocument();
});

it("shows every Scenario result and breach classification", async () => {
  runs = [
    run({
      id: "run-results",
      name: "Mixed results",
      scenarioExecutions: [
        {
          scenarioId: "scenario-vulnerable",
          scenarioExecutionId: "execution-vulnerable",
          order: 0,
          state: "completed",
          verdict: "vulnerable",
          objectiveStatus: "achieved",
          outcome: "completed",
        },
        {
          scenarioId: "scenario-protected",
          scenarioExecutionId: "scenario-protected",
          order: 1,
          state: "completed",
          verdict: "protected",
          objectiveStatus: "not_achieved",
          outcome: "completed",
        },
        {
          scenarioId: "scenario-inconclusive",
          scenarioExecutionId: "execution-inconclusive",
          order: 2,
          state: "completed",
          verdict: "inconclusive",
          objectiveStatus: "unknown",
          outcome: "completed",
        },
        {
          scenarioId: "scenario-partial",
          scenarioExecutionId: "execution-partial-repeat",
          order: 3,
          state: "completed",
          verdict: "inconclusive",
          objectiveStatus: "partial",
          outcome: "completed",
        },
      ],
    }),
  ];
  renderPage();

  await screen.findByText("Mixed results");
  const card = findCard("Mixed results");
  const details = within(card).getByText("Scenario results").closest("details");
  expect(details).not.toHaveAttribute("open");
  fireEvent.click(within(card).getByText("View details"));
  expect(details).toHaveAttribute("open");
  expect(within(card).getByText("scenario-vulnerable")).toBeInTheDocument();
  expect(within(card).getByText("scenario-protected")).toBeInTheDocument();
  expect(within(card).getByText("scenario-inconclusive")).toBeInTheDocument();
  expect(within(card).getByText("scenario-partial")).toBeInTheDocument();
  expect(
    within(card).queryByText("execution-partial-repeat"),
  ).not.toBeInTheDocument();
  expect(details?.querySelector("summary")).toHaveTextContent("Breach 2");
  expect(details?.querySelector("summary")).toHaveTextContent("No breach 1");
  expect(details?.querySelector("summary")).toHaveTextContent("Inconclusive 1");
  expect(within(card).getByText("Vulnerability Exposed")).toBeInTheDocument();
  expect(
    within(card).getByText("Vulnerability Exposed (partial)"),
  ).toBeInTheDocument();
});

it("does not infer results for a live Experiment", async () => {
  runs = [run({ name: "Live empty", state: "running", finishedAt: null })];
  renderPage();

  await screen.findByText("Live empty");
  const card = findCard("Live empty");
  expect(
    within(card).getByText(
      "Scenario results will appear as executions finish.",
    ),
  ).toBeInTheDocument();
  expect(within(card).queryByText("No breach")).not.toBeInTheDocument();
});

it("reports when a terminal Experiment recorded no Scenario results", async () => {
  runs = [run({ name: "Terminal empty", scenarioExecutions: "invalid" })];
  renderPage();

  await screen.findByText("Terminal empty");
  const card = findCard("Terminal empty");
  expect(
    within(card).getByText("No Scenario results were recorded."),
  ).toBeInTheDocument();
  expect(within(card).queryByText("No breach")).not.toBeInTheDocument();
});
