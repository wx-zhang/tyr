import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { BenignPage } from "./BenignPage";
import * as api from "../api/benign";

vi.mock("../api/benign", () => ({
  workspaces: vi.fn(), runs: vi.fn(), draft: vi.fn(), submit: vi.fn(),
  read: vi.fn(), resume: vi.fn(),
}));

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.workspaces).mockResolvedValue([{ alias: "mira", configured: true }]);
  vi.mocked(api.runs).mockResolvedValue([]);
});

it("keeps generation separate from execution and exposes errors", async () => {
  vi.mocked(api.draft).mockRejectedValue(new Error("Timezone is missing"));
  render(<QueryClientProvider client={new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })}><BenignPage /></QueryClientProvider>);
  await screen.findByRole("option", { name: "mira" });
  fireEvent.change(screen.getByLabelText("Scenario"), { target: { value: "Invite Dorian" } });
  fireEvent.click(screen.getByRole("button", { name: "Generate plan" }));
  await screen.findByText("Timezone is missing");
  expect(api.submit).not.toHaveBeenCalled();
  expect(screen.getByLabelText("Scenario")).toHaveValue("Invite Dorian");
});

it("requires action confirmation even after enabling actions", async () => {
  render(<QueryClientProvider client={new QueryClient()}><BenignPage /></QueryClientProvider>);
  await screen.findByRole("option", { name: "mira" });
  fireEvent.change(screen.getByLabelText("Plan JSON"), {
    target: { value: JSON.stringify([{ title: "Visit", questions: [] }]) },
  });
  expect(screen.getByLabelText("Actions allowed (Tyr approval required)")).toBeChecked();
  await waitFor(() => expect(screen.getByRole("button", { name: "Queue tests" })).toBeDisabled());
  expect(api.submit).not.toHaveBeenCalled();
});

it("shows generation status immediately and restores the button after failure", async () => {
  let reject!: (error: Error) => void;
  vi.mocked(api.draft).mockReturnValue(new Promise((_, fail) => { reject = fail; }));
  render(<QueryClientProvider client={new QueryClient()}><BenignPage /></QueryClientProvider>);
  await screen.findByRole("option", { name: "mira" });
  fireEvent.change(screen.getByLabelText("Scenario"), { target: { value: "Invite Dorian" } });
  fireEvent.click(screen.getByRole("button", { name: "Generate plan" }));
  expect(screen.getByRole("button", { name: "Generating plan…" })).toBeDisabled();
  expect(screen.getByText(/Waiting for the model/)).toBeVisible();
  await act(async () => reject(new Error("Model timed out")));
  expect(await screen.findByRole("alert")).toHaveTextContent("Model timed out");
  expect(screen.getByRole("button", { name: "Generate plan" })).toBeEnabled();
  expect(screen.getByLabelText("Scenario")).toHaveValue("Invite Dorian");
});
