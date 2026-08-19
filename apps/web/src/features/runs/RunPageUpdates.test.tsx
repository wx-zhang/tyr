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

it("shows configured and scientist evaluation outcomes as updates", async () => {
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
          },
          cases: [
            {
              caseId: "case-alpha",
              order: 1,
              state: "completed",
              verdict: "protected",
              objectiveStatus: "not_achieved",
              outcome: "completed",
              summary: "The risky action was rejected.",
              latestSequence: 5,
            },
          ],
        }),
      } as Response);
    }
    if (url.includes("/turns")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          items: [
            {
              id: "evaluation-case-alpha",
              sequence: 3,
              number: 1,
              stage: "case",
              caseId: "case-alpha",
              status: "completed",
              agentMessage: "The risky action was rejected.",
              tyrMessage: null,
              occurredAt: "2026-08-08T10:03:00Z",
              repliedAt: null,
              updateType: "evaluation",
              verdict: "protected",
              objectiveStatus: "not_achieved",
              outcome: "completed",
              assessmentSummary: "The risky action was rejected.",
            },
            {
              id: "evaluation-scientist-alpha",
              sequence: 4,
              number: 2,
              stage: "scientist",
              caseId: "scientist-alpha",
              status: "failed",
              agentMessage: "The control was bypassed.",
              tyrMessage: null,
              occurredAt: "2026-08-08T10:04:00Z",
              repliedAt: null,
              updateType: "evaluation",
              verdict: "inconclusive",
              objectiveStatus: "partial",
              outcome: "failed",
              assessmentSummary: "The request was refused and never attempted.",
            },
          ],
          omittedBefore: 0,
          nextCursor: null,
          latestSequence: 4,
        }),
      } as Response);
    }
    return Promise.resolve({
      ok: true,
      json: async () => ({ items: [] }),
    } as Response);
  });

  const { container } = renderRunPage();

  expect(
    await screen.findByRole("heading", { name: "Run history" }),
  ).toBeInTheDocument();
  const caseAlphaToggle = await screen.findByRole("button", {
    name: /case-alpha/,
  });
  fireEvent.click(caseAlphaToggle);
  expect(
    await screen.findByRole("heading", {
      name: "Evaluation result - case-alpha",
    }),
  ).toBeInTheDocument();
  expect(
    await screen.findByRole("heading", {
      name: "Scientist evaluation - scientist-alpha",
    }),
  ).toBeInTheDocument();
  expect(screen.getAllByText("No breach").length).toBeGreaterThan(0);
  expect(
    screen.queryByText("Vulnerability Exposed (partial)"),
  ).not.toBeInTheDocument();
  expect(screen.getByText("Not Achieved")).toBeInTheDocument();
  expect(screen.getByText("Partial")).toBeInTheDocument();
  expect(
    screen.getAllByText("The request was refused and never attempted.")[0],
  ).toBeInTheDocument();
  expect(
    container.querySelector('[data-turn-id="evaluation-scientist-alpha"]'),
  ).not.toHaveClass("turn-failed");
  expect(screen.getAllByText("Case assessment")).toHaveLength(2);
  expect(screen.queryByText("LLM evaluation")).not.toBeInTheDocument();
});

it("shows newer turns while reviewing older content", async () => {
  renderRunPage();
  fireEvent.click(await screen.findByRole("button", { name: /case-alpha/ }));
  await screen.findByText("read_file");
  Object.defineProperty(window, "scrollY", { configurable: true, value: 600 });
  fireEvent.scroll(window);
  vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/visualization")) {
      return Promise.resolve({
        ok: true,
        json: async () => visualizationFixture,
      } as Response);
    }
    if (url.includes("/turns")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          ...turnsFixture,
          latestSequence: 3,
          items: [
            ...turnsFixture.items,
            {
              ...turnsFixture.items[1],
              id: "turn-3",
              sequence: 3,
              number: 2,
              agentMessage: "Newest request",
            },
          ],
        }),
      } as Response);
    }
    return Promise.resolve({
      ok: true,
      json: async () => ({ items: [] }),
    } as Response);
  });
});

it("shows agent working when the run is live and the latest turn is complete", async () => {
  vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/visualization")) {
      return Promise.resolve({
        ok: true,
        json: async () => visualizationFixture,
      } as Response);
    }
    if (url.includes("/turns")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          items: [
            {
              id: "turn-done",
              sequence: 1,
              number: 1,
              stage: "case",
              caseId: "case-alpha",
              status: "completed",
              agentMessage: "Upload the file.",
              tyrMessage: "The exact HTTP status code was 201.",
              occurredAt: "2026-08-08T10:01:00Z",
              repliedAt: "2026-08-08T10:01:28Z",
            },
          ],
          omittedBefore: 0,
          nextCursor: null,
          latestSequence: 1,
        }),
      } as Response);
    }
    return Promise.resolve({
      ok: true,
      json: async () => ({ items: [] }),
    } as Response);
  });

  const { container } = renderRunPage();
  fireEvent.click(await screen.findByRole("button", { name: /case-alpha/ }));
  expect(
    await screen.findByRole("heading", {
      name: "Executing evaluation - Turn 1",
    }),
  ).toBeInTheDocument();
  expect(screen.getAllByText("Agent working").length).toBeGreaterThan(0);
  expect(container.querySelector(".stage-working")).not.toBeNull();
  expect(screen.queryByText("Waiting for Tyr")).not.toBeInTheDocument();
});

it("does not show agent working while waiting for Tyr", async () => {
  renderRunPage();
  fireEvent.click(await screen.findByRole("button", { name: /case-alpha/ }));
  await screen.findByText("read_file");
  expect(screen.getAllByText("Waiting for Tyr").length).toBeGreaterThan(0);
  expect(screen.queryByText("Agent working")).not.toBeInTheDocument();
});

it("does not show agent working after the run ends", async () => {
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
            finishedAt: "2026-08-08T10:05:00Z",
            outcome: "completed",
          },
        }),
      } as Response);
    }
    if (url.includes("/turns")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          items: [
            {
              id: "turn-done",
              sequence: 1,
              number: 1,
              stage: "case",
              caseId: "case-alpha",
              status: "completed",
              agentMessage: "Upload the file.",
              tyrMessage: "The exact HTTP status code was 201.",
              occurredAt: "2026-08-08T10:01:00Z",
              repliedAt: "2026-08-08T10:01:28Z",
            },
          ],
          omittedBefore: 0,
          nextCursor: null,
          latestSequence: 1,
        }),
      } as Response);
    }
    return Promise.resolve({
      ok: true,
      json: async () => ({ items: [] }),
    } as Response);
  });

  renderRunPage();
  fireEvent.click(await screen.findByRole("button", { name: /case-alpha/ }));
  await screen.findByText("Upload the file.");
  expect(screen.queryByText("Agent working")).not.toBeInTheDocument();
});
