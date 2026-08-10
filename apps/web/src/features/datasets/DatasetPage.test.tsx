import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { DatasetPage } from "./DatasetPage";

const datasets = [
  {
    metadata: { id: "first-plan", title: "First Plan", version: "2.0.0" },
    spec: {
      cases: ["cases/a.json"],
      defaults: {
        maxTurns: 40,
        actionMode: "approval_required",
        defaultCaseIds: [],
      },
    },
  },
];

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => datasets }),
  );
});

it("renders the dataset heading", async () => {
  render(
    <MemoryRouter>
      <QueryClientProvider client={new QueryClient()}>
        <DatasetPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
  expect(
    await screen.findByRole("heading", { name: "Datasets" }),
  ).toBeInTheDocument();
});

it("links each dataset to its detail page", async () => {
  render(
    <MemoryRouter>
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <DatasetPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );

  const link = await screen.findByRole("link", { name: "first-plan" });
  expect(link).toHaveAttribute("href", "/datasets/first-plan");
  expect(screen.getByRole("link", { name: "First Plan" })).toHaveAttribute(
    "href",
    "/datasets/first-plan",
  );
});
