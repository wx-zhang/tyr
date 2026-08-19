import { fireEvent, screen } from "@testing-library/react";
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

it("removes the previous evidence navigation and controls", async () => {
  renderRunPage();
  await screen.findByRole("heading", { name: "Run history" });

  expect(screen.queryByRole("link", { name: "Cases" })).not.toBeInTheDocument();
  expect(
    screen.queryByRole("link", { name: "Artifacts" }),
  ).not.toBeInTheDocument();
});

it("shows the Tyr network map with observed participants and connections", async () => {
  window.localStorage.setItem("gamr-tyr-network-open", "1");
  renderRunPage();

  expect(
    await screen.findByRole("heading", { name: "Tyr network" }),
  ).toBeInTheDocument();
  expect(await screen.findByText("Joe workspace")).toBeInTheDocument();
  expect(screen.getAllByText("Alice").length).toBeGreaterThan(0);
  expect(screen.getByLabelText("Relationship list")).toBeInTheDocument();
  expect(screen.getAllByText(/bridge · 11/i).length).toBeGreaterThan(0);

  fireEvent.click(screen.getByRole("button", { name: /Tyr → Alice/i }));
  expect(screen.getByRole("button", { name: /Tyr → Alice/i })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});

it("keeps the Tyr network panel closed by default and expands on demand", async () => {
  window.localStorage.removeItem("gamr-tyr-network-open");
  const { container } = renderRunPage();

  expect(
    await screen.findByRole("heading", { name: "Tyr network" }),
  ).toBeInTheDocument();
  const panel = container.querySelector("details.network-panel");
  expect(panel).not.toBeNull();
  expect(panel).not.toHaveAttribute("open");
  expect(screen.queryByText("Joe workspace")).not.toBeInTheDocument();

  const summary = panel!.querySelector("summary");
  expect(summary).not.toBeNull();
  fireEvent.click(summary!);
  expect(panel).toHaveAttribute("open");
  expect(await screen.findByText("Joe workspace")).toBeInTheDocument();
  expect(window.localStorage.getItem("gamr-tyr-network-open")).toBe("1");

  fireEvent.click(summary!);
  expect(panel).not.toHaveAttribute("open");
  expect(window.localStorage.getItem("gamr-tyr-network-open")).toBe("0");
});

it("shows Cancel run while the run is live", async () => {
  renderRunPage();
  expect(
    await screen.findByRole("button", { name: "Cancel run" }),
  ).toBeInTheDocument();
});

it("hides Cancel run after the run ends", async () => {
  vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/visualization")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          ...visualizationFixture,
          run: {
            ...visualizationFixture.run,
            state: "completed",
            currentPhase: null,
            finishedAt: "2026-08-08T10:10:00Z",
            outcome: "completed",
          },
          phases: visualizationFixture.phases.map((phase) => ({
            ...phase,
            state: "completed",
          })),
        }),
      } as Response);
    }
    if (url.includes("/turns")) {
      return Promise.resolve({ ok: true, json: async () => turnsFixture } as Response);
    }
    return Promise.resolve({
      ok: true,
      json: async () => ({ items: [] }),
    } as Response);
  });

  renderRunPage();
  await screen.findByRole("heading", { name: "Run history" });
  expect(screen.queryByRole("button", { name: "Cancel run" })).not.toBeInTheDocument();
});
