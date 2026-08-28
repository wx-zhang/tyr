import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import {
  renderRunPage,
  setupRunMocks,
  turnsFixture,
  visualizationFixture,
} from "./runPageTestUtils";

beforeEach(() => {
  setupRunMocks();
});

it("cancels a live Experiment after confirmation", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  let cancelled = false;
  vi.mocked(fetch).mockImplementation(
    (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/cancel") && init?.method === "POST") {
        cancelled = true;
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "run-1",
            state: "cancelled",
            source: "service",
            experimentId: null,
            task: "exfiltrate-important-txt",
            configuration: {
              actionMode: "read_only",
              model: "test",
              adversarialResearcherModel: "researcher",
              judgeModel: "judge",
              maxTurns: 10,
              discoveryTurns: 1,
              researchIterations: 0,
              historyTestRuns: 10,
              historyResearchRuns: 5,
            },
          }),
        } as Response);
      }
      if (url.includes("/visualization")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            ...visualizationFixture,
            run: {
              ...visualizationFixture.run,
              state: cancelled ? "cancelled" : "running",
              finishedAt: cancelled ? "2026-08-08T10:05:00Z" : null,
              outcome: cancelled ? "cancelled" : null,
              currentPhase: cancelled ? null : "running",
            },
            phases: visualizationFixture.phases.map((phase) => ({
              ...phase,
              state: cancelled
                ? phase.id === "running"
                  ? "cancelled"
                  : phase.state === "active"
                    ? "cancelled"
                    : phase.state
                : phase.state,
            })),
          }),
        } as Response);
      }
      if (url.includes("/turns")) {
        return Promise.resolve({
          ok: true,
          json: async () => turnsFixture,
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ items: [] }),
      } as Response);
    },
  );

  renderRunPage();
  fireEvent.click(await screen.findByRole("button", { name: "Cancel Experiment" }));
  expect(confirm).toHaveBeenCalled();
  await waitFor(() => {
    expect(
      screen.queryByRole("button", { name: "Cancel Experiment" }),
    ).not.toBeInTheDocument();
  });
  expect(screen.getAllByText("Cancelled").length).toBeGreaterThan(0);
  confirm.mockRestore();
});

it("does not cancel when the operator dismisses Experiment confirmation", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  renderRunPage();
  fireEvent.click(await screen.findByRole("button", { name: "Cancel Experiment" }));
  expect(confirm).toHaveBeenCalled();
  await waitFor(() => {
    const cancelCalls = vi.mocked(fetch).mock.calls.filter(([input, init]) => {
      return (
        String(input).includes("/cancel") &&
        (init as RequestInit | undefined)?.method === "POST"
      );
    });
    expect(cancelCalls).toHaveLength(0);
  });
  expect(
    screen.getByRole("button", { name: "Cancel Experiment" }),
  ).toBeInTheDocument();
  confirm.mockRestore();
});

it("shows an error when Experiment cancellation fails", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  vi.mocked(fetch).mockImplementation(
    (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/cancel") && init?.method === "POST") {
        return Promise.resolve({
          ok: false,
          status: 500,
          json: async () => ({}),
        } as Response);
      }
      if (url.includes("/visualization")) {
        return Promise.resolve({
          ok: true,
          json: async () => visualizationFixture,
        } as Response);
      }
      if (url.includes("/turns")) {
        return Promise.resolve({
          ok: true,
          json: async () => turnsFixture,
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ items: [] }),
      } as Response);
    },
  );

  renderRunPage();
  fireEvent.click(await screen.findByRole("button", { name: "Cancel Experiment" }));
  expect(await screen.findByText(/^Could not cancel Experiment:/)).toBeInTheDocument();
  confirm.mockRestore();
});
