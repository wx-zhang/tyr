import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";
import { RunPage } from "./RunPage";

export const visualizationFixture = {
  run: {
    id: "run-1",
    state: "running",
    actionMode: "read_only",
    task: "exfiltrate-important-txt",
    startedAt: "2026-08-08T10:00:00Z",
    latestUpdateAt: "2026-08-08T10:03:00Z",
    finishedAt: null,
    outcome: null,
    currentPhase: "running",
    currentScenarioExecutionIds: ["case-alpha"],
  },
  phases: [
    { id: "queued", label: "Queued", state: "completed", latestSequence: 1 },
    {
      id: "preparing",
      label: "Preparing",
      state: "completed",
      latestSequence: 2,
    },
    {
      id: "discovering",
      label: "Discovering",
      state: "completed",
      latestSequence: 3,
    },
    { id: "running", label: "Running", state: "active", latestSequence: 5 },
    {
      id: "scientist",
      label: "Adversarial Researcher",
      state: "pending",
      latestSequence: null,
    },
    {
      id: "evaluating",
      label: "Evaluating",
      state: "pending",
      latestSequence: null,
    },
    {
      id: "reporting",
      label: "Reporting",
      state: "pending",
      latestSequence: null,
    },
  ],
  scenarioExecutions: [
    {
      scenarioId: "scenario-alpha",
      scenarioExecutionId: "case-alpha",
      order: 1,
      state: "active",
      verdict: null,
      latestSequence: 5,
    },
    {
      scenarioId: "scenario-beta",
      scenarioExecutionId: "case-beta",
      order: 2,
      state: "pending",
      verdict: null,
      latestSequence: null,
    },
  ],
  attention: { pendingApprovalCount: 0, blockers: [], unsettledTyrWork: false },
  counts: { totalKnown: true, totalScenarioExecutions: 2, completedScenarioExecutions: 0 },
  latestSequence: 5,
  latestActivity: null,
};

export const turnsFixture = {
  items: [
    {
      id: "turn-1",
      sequence: 1,
      number: 1,
      stage: "discovery",
      caseId: null,
      status: "completed",
      agentMessage: "**Inspect** the workspace.",
      tyrMessage: "- Alice\n- Bob",
      occurredAt: "2026-08-08T10:01:00Z",
      repliedAt: "2026-08-08T10:01:12Z",
    },
    {
      id: "turn-2",
      sequence: 2,
      number: 1,
      stage: "case",
      caseId: "case-alpha",
      status: "waiting_for_tyr",
      agentMessage: "Call `read_file`.",
      tyrMessage: null,
      occurredAt: "2026-08-08T10:02:00Z",
      repliedAt: null,
    },
  ],
  omittedBefore: 0,
  nextCursor: null,
  latestSequence: 2,
};

export const relationshipsFixture = {
  participants: [
    {
      id: "tyr",
      kind: "tyr_agent",
      displayLabel: "Tyr",
      firstObservedSequence: 1,
    },
    {
      id: "alice",
      kind: "model_agent",
      displayLabel: "Alice",
      firstObservedSequence: 1,
    },
    {
      id: "joe-workspace",
      kind: "tool",
      displayLabel: "Joe workspace",
      firstObservedSequence: 2,
    },
  ],
  relationships: [
    {
      id: "tyr-alice",
      sourceParticipantId: "tyr",
      targetParticipantId: "alice",
      relationshipTypes: ["bridge"],
      activityCount: 11,
      statusCounts: { completed: 11 },
      firstSequence: 1,
      lastSequence: 11,
    },
    {
      id: "alice-workspace",
      sourceParticipantId: "alice",
      targetParticipantId: "joe-workspace",
      relationshipTypes: ["tool_call"],
      activityCount: 4,
      statusCounts: { completed: 4 },
      firstSequence: 2,
      lastSequence: 9,
    },
  ],
};

class EventSourceStub {
  addEventListener = vi.fn();
  removeEventListener = vi.fn();
  close = vi.fn();
}

export function setupRunMocks() {
  vi.stubGlobal("EventSource", EventSourceStub);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/runs/run-1/visualization")) {
        return { ok: true, json: async () => visualizationFixture };
      }
      if (url.includes("/api/v1/runs/run-1/turns")) {
        return { ok: true, json: async () => turnsFixture };
      }
      if (url.includes("/api/v1/runs/run-1/collector-verifications")) {
        return { ok: true, json: async () => [] };
      }
      if (url.includes("/api/v1/runs/run-1/relationships")) {
        return { ok: true, json: async () => relationshipsFixture };
      }
      if (url.includes("/api/v1/runs/run-1")) {
        return {
          ok: true,
          json: async () => ({
            id: "run-1",
            configuration: {
              scenarioIds: ["scenario-alpha", "scenario-beta"],
              researchIterations: 0,
            },
          }),
        };
      }
      if (url.includes("/api/v1/tasks/") && url.endsWith("/scenarios")) {
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
}

export function renderRunPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <MemoryRouter initialEntries={["/runs/run-1"]}>
      <QueryClientProvider client={queryClient}>
        <Routes>
          <Route path="/runs/:id" element={<RunPage />} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}
