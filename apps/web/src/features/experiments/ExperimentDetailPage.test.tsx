import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { ExperimentDetailPage } from "./ExperimentDetailPage";

const navigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
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
    maxTurns: 40,
    discoveryTurns: 20,
    caseIds: ["case-a"],
    scientistIterations: 3,
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
  scientistIterations?: number;
}) {
  const startOk = options?.startOk ?? true;
  const scientistIterations =
    options?.scientistIterations ?? experiment.configuration.scientistIterations;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/api/v1/experiments/exp-1") && !url.endsWith("/runs")) {
      return {
        ok: true,
        json: async () => ({
          ...experiment,
          configuration: {
            ...experiment.configuration,
            scientistIterations,
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
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => {
  navigate.mockReset();
  installFetch();
});

it("shows stored max concurrent cases on the configuration snapshot", async () => {
  renderPage();

  const concurrencyLabel = await screen.findByText("Max concurrent cases");
  const row = concurrencyLabel.closest(".detail-row");
  expect(row).not.toBeNull();
  expect(row).toHaveTextContent("5");
});

it("shows stored scientist iterations on the configuration snapshot", async () => {
  renderPage();

  expect(await screen.findByText("Number of new task research")).toBeInTheDocument();
  expect(screen.getByText("3")).toBeInTheDocument();
});

it("shows off when scientist iterations are zero", async () => {
  installFetch({ scientistIterations: 0 });
  renderPage();

  expect(await screen.findByText("Number of new task research")).toBeInTheDocument();
  expect(screen.getByText("0 (off)")).toBeInTheDocument();
});

it("starts a run and navigates to the run page", async () => {
  const fetchMock = installFetch();
  renderPage();

  expect(await screen.findByRole("button", { name: "Execute" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Execute" }));

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
