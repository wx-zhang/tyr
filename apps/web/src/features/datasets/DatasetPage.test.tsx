import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { DatasetPage } from "./DatasetPage";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => [] }),
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
