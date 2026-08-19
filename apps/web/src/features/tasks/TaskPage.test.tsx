import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { TaskPage } from "./TaskPage";

const datasets = [
  {
    metadata: { id: "exfiltrate-important-txt", title: "Exfiltrate important.txt", version: "2.0.0" },
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

it("renders the task heading", async () => {
  render(
    <MemoryRouter>
      <QueryClientProvider client={new QueryClient()}>
        <TaskPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
  expect(
    await screen.findByRole("heading", { name: "Tasks" }),
  ).toBeInTheDocument();
});

it("links each task to its detail page", async () => {
  render(
    <MemoryRouter>
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <TaskPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );

  const link = await screen.findByRole("link", { name: "exfiltrate-important-txt" });
  expect(link).toHaveAttribute("href", "/tasks/exfiltrate-important-txt");
  expect(screen.getByRole("link", { name: "Exfiltrate important.txt" })).toHaveAttribute(
    "href",
    "/tasks/exfiltrate-important-txt",
  );
});
