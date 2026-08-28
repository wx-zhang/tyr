import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { ExperimentDetailPage } from "./ExperimentDetailPage";

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

const experiment = {
  id: "exp-1",
  name: "Exfiltrate important.txt · test",
  task: "exfiltrate-important-txt",
  configuration: {
    actionMode: "approval_required" as const,
    model: "test-model",
    adversarialResearcherModel: "researcher-model",
    judgeModel: "judge-model",
    maxTurns: 40,
    discoveryTurns: 20,
    scenarioIds: ["case-a"],
    maxConcurrentScenarioExecutions: 5,
    researchIterations: 3,
    historyTestRuns: 10,
    historyResearchRuns: 5,
  },
};

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <MemoryRouter initialEntries={["/experiments/exp-1"]}>
      <QueryClientProvider client={client}>
        <Routes>
          <Route path="/experiments/:id" element={<ExperimentDetailPage />} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

function installFetch(options?: {
  startOk?: boolean;
  scenarioIds?: string[];
  researchIterations?: number;
}) {
  const startOk = options?.startOk ?? true;
  const scenarioIds = options?.scenarioIds ?? experiment.configuration.scenarioIds;
  const researchIterations =
    options?.researchIterations ??
    experiment.configuration.researchIterations;
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/v1/experiments/exp-1") && !url.endsWith("/runs")) {
        return {
          ok: true,
          json: async () => ({
            ...experiment,
            configuration: {
              ...experiment.configuration,
              scenarioIds,
              researchIterations,
            },
          }),
        };
      }
      if (url.endsWith("/runs") && init?.method === "POST") {
        if (!startOk) {
          return { ok: false, status: 500, json: async () => ({}) };
        }
        return {
          ok: true,
          json: async () => ({
            id: "run-9",
            state: "queued",
            statusUrl: "/api/v1/runs/run-9",
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

it("shows stored Max concurrent Scenario Executions on the configuration snapshot", async () => {
  renderPage();

  const concurrencyLabel = await screen.findByText("Max concurrent Scenario Executions");
  const row = concurrencyLabel.closest(".detail-row");
  expect(row).not.toBeNull();
  expect(row).toHaveTextContent("5");
});

it("shows stored Research Iterations on the configuration snapshot", async () => {
  renderPage();

  expect(await screen.findByText("Research Iterations")).toBeInTheDocument();
  expect(screen.getByText("3")).toBeInTheDocument();
});

it("shows off when Research Iterations are zero", async () => {
  installFetch({ researchIterations: 0 });
  renderPage();

  expect(await screen.findByText("Research Iterations")).toBeInTheDocument();
  expect(screen.getByText("0 (off)")).toBeInTheDocument();
});

it("shows no Scenarios for researcher-only Experiments", async () => {
  installFetch({ scenarioIds: [], researchIterations: 3 });
  renderPage();

  expect(await screen.findByText("None (Adversarial Researcher only)")).toBeInTheDocument();
});

it("starts an Experiment and navigates to the execution page", async () => {
  const fetchMock = installFetch();
  renderPage();

  expect(
    await screen.findByRole("button", { name: "Start Experiment" }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Start Experiment" }));

  await waitFor(() => {
    expect(navigate).toHaveBeenCalledWith("/runs/run-9");
  });

  expect(
    fetchMock.mock.calls.some(
      ([url, init]) =>
        String(url).endsWith("/experiments/exp-1/runs") &&
        (init as RequestInit | undefined)?.method === "POST",
    ),
  ).toBe(true);
});
