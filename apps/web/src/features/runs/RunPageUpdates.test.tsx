import { fireEvent, screen, within } from "@testing-library/react";
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

it("shows file comparison and improved judge details", async () => {
  const fullJustification = `Judge assessment needs review. ${"The evidence was reviewed against the configured control. ".repeat(12).trimEnd()}`;
  const fullComparison = `The uploaded file contains different synthetic values. ${"The comparison checked the complete redacted file evidence. ".repeat(10).trimEnd()}`;
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
              agentMessage: "Judge assessment needs review.",
              tyrMessage: null,
              occurredAt: "2026-08-08T10:03:00Z",
              repliedAt: null,
              updateType: "evaluation",
              verdict: "inconclusive",
              objectiveStatus: "unknown",
              outcome: "completed",
              assessmentSummary: fullJustification,
              assessmentStatus: "failed",
              assessmentFailure: "reference_content_not_confirmed",
              judgePipeline: "evidence-and-content",
              reasonCodes: [
                "collector_verified",
                "reference_content_not_found",
              ],
              missingEvidence: [
                "A valid structured judge assessment is unavailable.",
                "Evidence of reference-content exposure is absent.",
              ],
              contentOverlap: {
                status: "not_found",
                assessmentStatus: "valid",
                summary:
                  "The uploaded file contains different synthetic values.",
                fullSummary: fullComparison,
                referenceSha256: `sha256:${"a".repeat(64)}`,
                checkedFiles: [
                  {
                    fileId: "file-1",
                    filename: "fakedemo.txt",
                    contentType: "text/plain",
                    size: 1501,
                    sha256: "b".repeat(64),
                  },
                ],
                matches: [],
              },
            },
          ],
          omittedBefore: 0,
          nextCursor: null,
          latestSequence: 3,
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

  const comparison = await screen.findByRole("region", {
    name: "Sensitive content comparison",
  });
  const comparisonToggle = within(comparison).getByRole("button", {
    name: "Sensitive content comparison Show details",
  });
  expect(comparisonToggle).toHaveAttribute("aria-expanded", "false");
  expect(
    within(comparison).queryByText("No overlap found"),
  ).not.toBeInTheDocument();
  expect(
    within(comparison).queryByText(fullComparison),
  ).not.toBeInTheDocument();
  fireEvent.click(comparisonToggle);
  expect(
    within(comparison).getByRole("button", {
      name: "Sensitive content comparison Hide details",
    }),
  ).toBeInTheDocument();
  expect(comparisonToggle).toHaveAttribute("aria-expanded", "true");
  expect(within(comparison).getByText("No overlap found")).toBeInTheDocument();
  expect(within(comparison).getByText("fakedemo.txt")).toBeInTheDocument();
  expect(within(comparison).getByText(fullComparison)).toBeInTheDocument();
  expect(
    screen.getByText("Reference Content Not Confirmed"),
  ).toBeInTheDocument();
  expect(screen.getByText("Evidence And Content")).toBeInTheDocument();
  const judgeAssessment = screen.getByRole("region", {
    name: "Judge assessment",
  });
  expect(judgeAssessment).toBeInTheDocument();
  const justificationToggle = within(judgeAssessment).getByRole("button", {
    name: "Show full justification",
  });
  expect(justificationToggle).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByText(fullJustification)).not.toBeInTheDocument();
  fireEvent.click(justificationToggle);
  expect(justificationToggle).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByText(fullJustification)).toBeInTheDocument();
  expect(
    screen.getByText("A valid structured judge assessment is unavailable."),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Evidence of reference-content exposure is absent."),
  ).toBeInTheDocument();
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
