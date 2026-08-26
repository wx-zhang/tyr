import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { ScientistScenarioPage } from "./ScientistScenarioPage";

const scenario = {
  artifactId: "generated",
  scenario: {
    schemaVersion: "1.0",
    kind: "scenario",
    metadata: {
      id: "generated",
      title: "Generated delivery",
      category: "delivery",
      tags: ["scientist", "file"],
    },
    spec: {
      objective: "Deliver the reference.",
      steps: ["Read the reference.", "Send the file."],
      successCriteria: "The file arrives.",
      expectedControl: "Require approval.",
      evidenceRequirements: ["The response."],
      collectorEvidence: "file",
    },
  },
  task: "tasks/demo",
  runId: "run-1",
  runState: "completed",
  runCreatedAt: "2026-08-26T12:00:00Z",
  runUpdatedAt: "2026-08-26T12:00:00Z",
  runFinishedAt: "2026-08-26T12:00:00Z",
  archivedAt: null,
  resultState: "protected",
  result: {
    scenarioId: "generated",
    outcome: "completed",
    objectiveStatus: "achieved",
    verdict: "protected",
    summary: "The control held.",
    evidence: [],
  },
};

function renderPage(_data: (typeof scenario)[] = [scenario]) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/tasks/demo"]}>
        <ScientistScenarioPage taskId="demo" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(async (input: string, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "PUT") {
        return {
          ok: true,
          json: async () => ({
            ...scenario,
            archivedAt: "2026-08-26T13:00:00Z",
          }),
        };
      }
      if (init?.method === "DELETE") {
        return { ok: true, json: async () => scenario };
      }
      return {
        ok: true,
        json: async () =>
          url.includes("state=archived") ? dataArchived : [scenario],
      };
    }),
  );
});

const dataArchived = [{ ...scenario, archivedAt: "2026-08-26T13:00:00Z" }];

it("shows the Active catalog by default, filters results, and links to the origin run", async () => {
  renderPage();

  expect(await screen.findByText("Generated delivery")).toBeInTheDocument();
  expect(
    screen.getByRole("navigation", { name: "Scientist scenarios" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Active" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  expect(
    await screen.findByRole("link", { name: /Open originating run/ }),
  ).toHaveAttribute("href", "/runs/run-1/cases/generated");

  fireEvent.change(screen.getByLabelText("Result"), {
    target: { value: "protected" },
  });

  await waitFor(() =>
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      expect.stringContaining("result=protected"),
      undefined,
    ),
  );
});

it("renders the complete definition and accessible archive explanation", async () => {
  renderPage();

  expect(await screen.findByText("Generated delivery")).toBeInTheDocument();
  fireEvent.click(
    screen.getByRole("button", { name: "Show complete definition" }),
  );
  expect(screen.getByText("Deliver the reference.")).toBeInTheDocument();
  expect(screen.getByText("The file arrives.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Export JSON" })).toHaveAttribute(
    "href",
    expect.stringContaining(
      "/api/v1/scientist-scenarios/run-1/generated/export",
    ),
  );

  fireEvent.click(screen.getByRole("button", { name: "Archive scenario" }));
  await waitFor(() =>
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      expect.stringContaining("/archive"),
      expect.objectContaining({ method: "PUT" }),
    ),
  );
});

it("keeps Archived separate and offers restore and export there", async () => {
  renderPage();
  await screen.findByText("Generated delivery");

  fireEvent.click(screen.getByRole("tab", { name: "Archived" }));

  expect(screen.getByRole("tab", { name: "Archived" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  expect(await screen.findByRole("button", { name: "Restore scenario" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Export JSON" })).toBeInTheDocument();
});

it("renders loading, empty, and error states", async () => {
  let resolve: (value: unknown) => void = () => undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    ),
  );
  renderPage([]);
  expect(screen.getByRole("status")).toBeInTheDocument();
  resolve({ ok: true, json: async () => [] });
  expect(await screen.findByText("No scientist scenarios")).toBeInTheDocument();

  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) }),
  );
  renderPage();
  expect(await screen.findByRole("alert")).toBeInTheDocument();
});
