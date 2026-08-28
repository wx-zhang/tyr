import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
    vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/v1/runs") && method === "GET") {
        return Promise.resolve({ ok: true, json: async () => runs } as Response);
      }
      if (url.includes("/api/v1/runs/") && url.endsWith("/cancel") && method === "POST") {
        const id = url.split("/").slice(-2)[0];
        const target = runs.find((item) => item.id === id);
        if (target) target.state = "cancelled";
        return Promise.resolve({ ok: true, json: async () => target ?? {} } as Response);
      }
      if (url.includes("/api/v1/runs/") && method === "DELETE") {
        const id = url.split("/").pop();
        runs = runs.filter((item) => item.id !== id);
        return Promise.resolve({ ok: true, status: 204, json: async () => ({}) } as Response);
      }
      return Promise.resolve({ ok: true, json: async () => ({}) } as Response);
    }),
  );
});

function renderPage() {
  const queryClient = new QueryClient();
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <DashboardPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

function findRow(text: string): HTMLElement {
  const row = screen.getByText(text).closest("tr");
  expect(row).not.toBeNull();
  return row as HTMLElement;
}

it("shows the run's own name instead of the task when one was set", async () => {
  runs = [
    run({ id: "run-5555", task: "tasks/exfiltrate-important-txt", name: "Nightly red team" }),
  ];
  renderPage();

  await screen.findByText("Nightly red team");
  expect(screen.queryByText("exfiltrate-important-txt")).not.toBeInTheDocument();
});

it("falls back to the task label when the run has no name", async () => {
  runs = [run({ id: "run-6666", task: "tasks/exfiltrate-important-txt", name: null })];
  renderPage();

  await screen.findByText("exfiltrate-important-txt");
});

it("deletes a single finished session after confirmation", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderPage();

  await screen.findByText("exfiltrate-important-txt");
  const row = findRow("exfiltrate-important-txt");
  fireEvent.click(within(row).getByRole("button", { name: "Delete" }));

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
  const liveRow = findRow("second-plan");

  expect(within(liveRow).getByRole("button", { name: "Delete" })).toBeDisabled();
  expect(within(liveRow).getByRole("button", { name: "Stop" })).toBeEnabled();
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
});

it("stops a live run from the dashboard after confirmation", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderPage();

  await screen.findByText("exfiltrate-important-txt");
  const liveRow = findRow("second-plan");
  fireEvent.click(within(liveRow).getByRole("button", { name: "Stop" }));

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
  runs = [run({ id: "run-4444", task: "tasks/fourth-plan", state: "queued", finishedAt: null })];
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderPage();

  await screen.findByText("fourth-plan");
  const row = findRow("fourth-plan");
  expect(within(row).getByRole("button", { name: "Delete" })).toBeEnabled();
  fireEvent.click(within(row).getByRole("button", { name: "Delete" }));

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
  fireEvent.click(screen.getByRole("button", { name: "Select" }));

  expect(
    screen.getByRole("checkbox", { name: "Select all deletable Experiments" }),
  ).toBeInTheDocument();
  expect(screen.getAllByRole("checkbox", { name: /Select Experiment/ }).length).toBeGreaterThan(0);
  expect(screen.getByRole("button", { name: "Delete selected" })).toBeDisabled();

  const liveRow = findRow("second-plan");
  expect(
    within(liveRow).getByRole("checkbox", { name: /Select Experiment/ }),
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
  const selectAll = screen.getByRole("checkbox", { name: "Select all deletable Experiments" });
  fireEvent.click(selectAll);

  const bulkButton = await screen.findByRole("button", { name: "Delete 2 selected" });
  fireEvent.click(bulkButton);

  expect(confirm).toHaveBeenCalled();
  await waitFor(() => {
    expect(
      screen.queryByRole("button", { name: /Delete \d+ selected|Delete selected/ }),
    ).not.toBeInTheDocument();
  });
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  const deleteCalls = vi.mocked(fetch).mock.calls.filter(([, init]) => {
    return (init as RequestInit | undefined)?.method === "DELETE";
  });
  expect(deleteCalls).toHaveLength(2);
  confirm.mockRestore();
});
