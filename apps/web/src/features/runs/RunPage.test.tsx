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

it("shows discovered variables in Updates after discovery completes", async () => {
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
          items: [
            {
              id: "run-1-discovery-result",
              sequence: 3,
              number: 1,
              stage: "discovery",
              caseId: null,
              status: "completed",
              agentMessage:
                "path: /home/alice/important.txt\nworkspace: peer\nagent: Alice\nbridgeId: bridge-1",
              tyrMessage: null,
              occurredAt: "2026-08-08T10:01:45Z",
              repliedAt: null,
              updateType: "discovery",
            },
            ...turnsFixture.items,
          ],
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

  const discoveryToggle = await screen.findByRole("button", {
    name: /Discovery Completed/,
  });
  expect(discoveryToggle).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(discoveryToggle);
  const list = screen.getByLabelText("Discovered variables");
  expect(list).toHaveTextContent("path");
  expect(list).toHaveTextContent("/home/alice/important.txt");
  expect(list).toHaveTextContent("workspace");
  expect(list).toHaveTextContent("peer");
  expect(list).toHaveTextContent("agent");
  expect(list).toHaveTextContent("Alice");
  expect(list).toHaveTextContent("bridgeId");
  expect(list).toHaveTextContent("bridge-1");
  const stages = screen.getByRole("list", { name: "Run stages" });
  expect(stages).not.toHaveTextContent("Discovered variables");
});

it("displays multiple simultaneous active and assessing cases without single-case busy indicator", async () => {
  const customVisualization = {
    ...visualizationFixture,
    cases: [
      {
        caseId: "case-alpha",
        state: "active",
        order: 0,
        verdict: null,
        objectiveStatus: null,
        outcome: null,
      },
      {
        caseId: "case-beta",
        state: "assessing",
        order: 1,
        verdict: null,
        objectiveStatus: null,
        outcome: null,
      },
    ],
    currentCaseIds: ["case-alpha", "case-beta"],
  };

  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/runs/run-1/visualization")) {
        return { ok: true, json: async () => customVisualization };
      }
      if (url.includes("/api/v1/runs/run-1/turns")) {
        return {
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
        };
      }
      if (url.includes("/api/v1/runs/run-1/collector-verifications")) {
        return { ok: true, json: async () => [] };
      }
      if (url.includes("/api/v1/runs/run-1")) {
        return {
          ok: true,
          json: async () => ({
            id: "run-1",
            configuration: {
              caseIds: ["case-alpha", "case-beta"],
              scientistIterations: 0,
            },
          }),
        };
      }
      if (url.includes("/api/v1/tasks/") && url.endsWith("/cases")) {
        return {
          ok: true,
          json: async () => [
            { metadata: { id: "case-alpha", title: "Alpha" } },
            { metadata: { id: "case-beta", title: "Beta" } },
          ],
        };
      }
      return { ok: false, status: 404, json: async () => ({}) };
    }),
  );

  renderRunPage();

  expect(
    await screen.findByRole("button", { name: /case-alpha/ }),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /case-beta/ })).toBeInTheDocument();
  const alphaToggle = screen.getByRole("button", { name: /case-alpha/ });
  const betaToggle = screen.getByRole("button", { name: /case-beta/ });
  expect(within(alphaToggle).getByText("Running")).toBeInTheDocument();
  expect(within(betaToggle).getByText("Assessing")).toBeInTheDocument();
  expect(
    within(alphaToggle).queryByText("Agent working"),
  ).not.toBeInTheDocument();
  expect(
    within(betaToggle).queryByText("Agent working"),
  ).not.toBeInTheDocument();
});

it("does not render a redundant selected test cases block below Updates", async () => {
  renderRunPage();

  expect(
    await screen.findByRole("heading", { name: "Run history" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByLabelText("Selected test cases"),
  ).not.toBeInTheDocument();
});

it("shows the run lifecycle and grouped Agent to Tyr turns chronologically", async () => {
  renderRunPage();

  expect(await screen.findByText("Preparing")).toBeInTheDocument();
  expect(screen.getByText("Read-only")).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "Run stages" })).toBeInTheDocument();
  expect(screen.getByText("Preparing")).toBeInTheDocument();
  expect(screen.getByText("Evaluating")).toBeInTheDocument();
  expect(screen.getAllByText("Waiting for Tyr").length).toBeGreaterThan(0);
  const discoveryToggle = screen.getByRole("button", {
    name: /Discovery Completed/,
  });
  expect(discoveryToggle).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(discoveryToggle);
  expect(
    screen.getByRole("heading", { name: "Discovery - Turn 1" }),
  ).toBeInTheDocument();
  expect(screen.getAllByText("case-alpha").length).toBeGreaterThan(0);
  const caseAlphaToggle = screen.getByRole("button", { name: /case-alpha/ });
  expect(caseAlphaToggle).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(caseAlphaToggle);
  expect(
    screen.getByRole("heading", { name: "Executing evaluation - Turn 1" }),
  ).toBeInTheDocument();
  const caseBetaToggle = screen.getByRole("button", { name: /case-beta/ });
  expect(caseBetaToggle).toHaveAttribute("aria-expanded", "false");
  expect(within(caseBetaToggle).getByText("Not started")).toBeInTheDocument();
  expect(screen.getByText("Inspect")).toHaveProperty("tagName", "STRONG");
  expect(
    screen.getByRole("list", { name: "Discovery updates" }).textContent,
  ).toContain("Alice");
  expect(
    screen.queryByText("Agent request sent · Tyr reply pending"),
  ).not.toBeInTheDocument();
  expect(document.querySelector(".stage-active")).not.toBeNull();
  expect(document.querySelector(".stage-waiting")).not.toBeNull();
  expect(screen.getByText("Waited 12s")).toBeInTheDocument();
  expect(
    document.querySelector(".turn-waiting .history-activity-duration")
      ?.textContent,
  ).toMatch(/\d+:\d{2}/);
  const turnTimes = screen.getAllByRole("time");
  expect(turnTimes.length).toBeGreaterThanOrEqual(2);
  expect(turnTimes[0]).toHaveAttribute("dateTime", "2026-08-08T10:01:00Z");
  expect(turnTimes[0].textContent).not.toBe("—");
  expect(turnTimes[0].closest(".history-activity-meta")).not.toBeNull();
  expect(screen.getByText("read_file")).toHaveProperty("tagName", "CODE");
  expect(document.querySelector(".turn-waiting")).not.toBeNull();
  expect(document.querySelector(".tyr-waiting")).not.toBeNull();
  expect(document.querySelector(".tyr-waiting-spinner")).not.toBeNull();
  expect(document.querySelector(".tyr-waiting-ellipsis")).not.toBeNull();
});
