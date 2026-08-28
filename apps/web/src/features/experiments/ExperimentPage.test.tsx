import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { ExperimentPage } from "./ExperimentPage";

const navigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual =
    await vi.importActual<typeof import("react-router-dom")>(
      "react-router-dom",
    );
  return {
    ...actual,
    useNavigate: () => navigate,
  };
});

const tasks = [
  {
    metadata: {
      id: "exfiltrate-important-txt",
      title: "Exfiltrate important.txt",
      version: "2.0.0",
    },
    spec: {
      scenarios: ["scenarios/a.json", "scenarios/b.json"],
      defaults: {
        maxTurns: 40,
        actionMode: "approval_required",
        defaultScenarioIds: ["case-a"],
      },
    },
  },
];

const cases = [
  {
    kind: "scenario",
    metadata: { id: "case-a", title: "Case Alpha", category: "multi-agent" },
    spec: {
      objective: "Do alpha",
      steps: ["Step 1"],
      expectedControl: "Block",
      evidenceRequirements: ["Log"],
    },
  },
  {
    kind: "scenario",
    metadata: { id: "case-b", title: "Case Beta", category: null },
    spec: {
      objective: "Do beta",
      steps: ["Step 1"],
      expectedControl: "Block",
      evidenceRequirements: ["Log"],
    },
  },
];

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <MemoryRouter initialEntries={["/experiments/new"]}>
      <QueryClientProvider client={client}>
        <Routes>
          <Route path="/experiments/new" element={<ExperimentPage />} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

function installFetch(onCreate?: (body: Record<string, unknown>) => void) {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/v1/tasks/") && url.endsWith("/scenarios")) {
        return { ok: true, json: async () => cases };
      }
      if (url.includes("/api/v1/tasks")) {
        return { ok: true, json: async () => tasks };
      }
      if (url.includes("/api/v1/experiments") && init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as Record<string, unknown>;
        onCreate?.(body);
        return {
          ok: true,
          json: async () => ({
            id: "exp-1",
            name: body.name,
            task: "exfiltrate-important-txt",
          }),
        };
      }
      return { ok: false, status: 404, json: async () => ({}) };
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => {
  navigate.mockReset();
  installFetch();
});

it("creates the experiment via the API then redirects to details", async () => {
  const createBodies: Record<string, unknown>[] = [];
  const fetchMock = installFetch((body) => {
    createBodies.push(body);
  });

  renderPage();

  expect(
    await screen.findByRole("heading", { name: "Run Experiment" }),
  ).toBeInTheDocument();

  expect(await screen.findByLabelText(/Case Alpha/)).toBeChecked();
  expect(screen.getByLabelText(/Case Beta/)).not.toBeChecked();
  expect(screen.getByLabelText("Task")).toHaveValue("exfiltrate-important-txt");
  expect(
    screen.queryByRole("option", { name: "Research new task" }),
  ).not.toBeInTheDocument();
  expect(screen.getByLabelText("Approval-gated")).toBeChecked();

  fireEvent.click(screen.getByRole("button", { name: "Continue" }));

  await waitFor(() => {
    expect(navigate).toHaveBeenCalledWith("/experiments/exp-1");
  });

  expect(createBodies).toHaveLength(1);
  expect(createBodies[0]).toMatchObject({
    task: "exfiltrate-important-txt",
    actionMode: "approval_required",
    scenarioIds: ["case-a"],
    maxConcurrentScenarioExecutions: 1,
    researchIterations: 0,
    historyTestRuns: 10,
    historyResearchRuns: 5,
  });

  expect(
    fetchMock.mock.calls.some(
      ([url, init]) =>
        String(url).includes("/api/v1/experiments") &&
        (init as RequestInit | undefined)?.method === "POST",
    ),
  ).toBe(true);
});

it("sends Research Iterations when the operator sets them", async () => {
  const createBodies: Record<string, unknown>[] = [];
  installFetch((body) => {
    createBodies.push(body);
  });

  renderPage();

  expect(await screen.findByLabelText(/Case Alpha/)).toBeChecked();
  expect(screen.getByLabelText("Research Iterations")).toHaveValue(0);
  expect(
    screen.getByRole("button", { name: "What Research Iterations means" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("tooltip", {
      name: /task-specific scenarios/i,
    }),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Research Iterations"), {
    target: { value: "2" },
  });
  expect(screen.getByLabelText("Research Iterations")).toHaveValue(2);
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));

  await waitFor(() => {
    expect(navigate).toHaveBeenCalledWith("/experiments/exp-1");
  });

  expect(createBodies[0]).toMatchObject({
    researchIterations: 2,
    scenarioIds: ["case-a"],
  });
});

it("defaults max concurrent Scenario Executions to 1 and bounds operator input 1 through 5", async () => {
  const createBodies: Record<string, unknown>[] = [];
  installFetch((body) => {
    createBodies.push(body);
  });

  renderPage();

  expect(await screen.findByLabelText(/Case Alpha/)).toBeChecked();
  const concurrencyInput = screen.getByLabelText("Max concurrent Scenario Executions");
  expect(concurrencyInput).toHaveValue(1);

  fireEvent.change(concurrencyInput, { target: { value: "3" } });
  expect(concurrencyInput).toHaveValue(3);

  fireEvent.click(screen.getByRole("button", { name: "Continue" }));

  await waitFor(() => {
    expect(navigate).toHaveBeenCalledWith("/experiments/exp-1");
  });

  expect(createBodies[0]).toMatchObject({
    maxConcurrentScenarioExecutions: 3,
  });
});

it("sends configured research history windows for researcher-only Experiments", async () => {
  const createBodies: Record<string, unknown>[] = [];
  installFetch((body) => {
    createBodies.push(body);
  });

  renderPage();
  expect(await screen.findByLabelText(/Case Alpha/)).toBeChecked();
  fireEvent.click(screen.getByLabelText(/Case Alpha/));
  expect(
    screen.getByRole("heading", { name: "Research Iteration history" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Scenarios" }),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Research Iterations", { selector: "#research-iterations" }), {
    target: { value: "1" },
  });
  fireEvent.change(screen.getByLabelText("Base Scenarios"), {
    target: { value: "7" },
  });
  fireEvent.change(screen.getByLabelText("Research Iterations", { selector: "#history-research-runs" }), {
    target: { value: "3" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));

  await waitFor(() => {
    expect(navigate).toHaveBeenCalledWith("/experiments/exp-1");
  });

  expect(createBodies[0]).toMatchObject({
    scenarioIds: [],
    researchIterations: 1,
    historyTestRuns: 7,
    historyResearchRuns: 3,
  });
});

it("does not redirect when the API fails to create the experiment", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/v1/tasks/") && url.endsWith("/scenarios")) {
        return { ok: true, json: async () => cases };
      }
      if (url.includes("/api/v1/tasks")) {
        return { ok: true, json: async () => tasks };
      }
      if (url.includes("/api/v1/experiments") && init?.method === "POST") {
        return { ok: false, status: 400, json: async () => ({}) };
      }
      return { ok: false, status: 404, json: async () => ({}) };
    }),
  );

  renderPage();
  expect(await screen.findByLabelText(/Case Alpha/)).toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    /Request failed: 400/,
  );
  expect(navigate).not.toHaveBeenCalled();
});

it("disables Continue when no Scenarios and no Research Iterations are selected", async () => {
  renderPage();

  expect(await screen.findByLabelText(/Case Alpha/)).toBeChecked();
  fireEvent.click(screen.getByLabelText(/Case Alpha/));

  expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
  expect(navigate).not.toHaveBeenCalled();
});

it("allows a selected Task to run researcher-only Research Iterations without seed Scenarios", async () => {
  const createBodies: Record<string, unknown>[] = [];
  installFetch((body) => {
    createBodies.push(body);
  });

  renderPage();

  expect(await screen.findByLabelText(/Case Alpha/)).toBeChecked();
  fireEvent.click(screen.getByLabelText(/Case Alpha/));
  expect(
    screen.getByRole("heading", { name: "Research Iteration history" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();

  fireEvent.change(screen.getByLabelText("Research Iterations", { selector: "#research-iterations" }), {
    target: { value: "3" },
  });

  expect(screen.getByRole("button", { name: "Continue" })).not.toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));

  await waitFor(() => {
    expect(navigate).toHaveBeenCalledWith("/experiments/exp-1");
  });

  expect(createBodies[0]).toMatchObject({
    scenarioIds: [],
    researchIterations: 3,
  });
});

it("hides and shows the Task Scenario explorer", async () => {
  renderPage();

  expect(await screen.findByLabelText(/Case Alpha/)).toBeChecked();
  expect(
    screen.getByRole("heading", { name: "Scenarios" }),
  ).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Hide" }));

  expect(
    screen.queryByRole("heading", { name: "Scenarios" }),
  ).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/Case Alpha/)).not.toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Show Scenarios" }),
  ).toBeInTheDocument();
  expect(screen.getByText("1 selected")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Show Scenarios" }));

  expect(
    screen.getByRole("heading", { name: "Scenarios" }),
  ).toBeInTheDocument();
  expect(screen.getByLabelText(/Case Alpha/)).toBeChecked();
});
