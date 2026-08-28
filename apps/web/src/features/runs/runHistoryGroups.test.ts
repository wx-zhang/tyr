import { describe, expect, it } from "vitest";
import type {
  CaseProgress,
  CollectorArtifact,
  RunTurn,
} from "../../api/client";
import { groupRunHistory } from "./runHistoryGroups";

function makeTurn(
  partial: Partial<RunTurn> & { id: string; sequence: number },
): RunTurn {
  const { id, sequence, ...rest } = partial;
  return {
    id,
    sequence,
    number: partial.number ?? 1,
    stage: partial.stage ?? "case",
    caseId: partial.caseId ?? null,
    updateType: partial.updateType ?? "execution",
    status: partial.status ?? "completed",
    verdict: partial.verdict ?? null,
    objectiveStatus: partial.objectiveStatus ?? null,
    outcome: partial.outcome ?? null,
    agentMessage: partial.agentMessage ?? "",
    tyrMessage: partial.tyrMessage ?? null,
    occurredAt: partial.occurredAt ?? "2026-08-08T10:00:00Z",
    repliedAt: partial.repliedAt ?? "2026-08-08T10:00:01Z",
    ...rest,
  };
}

function makeCase(
  partial: Partial<CaseProgress> & { id?: string; caseId?: string },
): CaseProgress {
  const caseId = partial.caseId ?? partial.id ?? "case-1";
  return {
    caseId,
    order: partial.order ?? 1,
    state: partial.state ?? "pending",
    ...partial,
  };
}

describe("groupRunHistory", () => {
  it("uses lifecycle phase state instead of a completed intermediate discovery turn", () => {
    const completedTurn = makeTurn({
      id: "disc-intermediate",
      sequence: 1,
      stage: "discovery",
      status: "completed",
    });

    const [activeDiscovery] = groupRunHistory({
      turns: [completedTurn],
      cases: [],
      artifacts: [],
      phases: [{ id: "discovering", label: "Discovering", state: "active" }],
    });
    const [completedDiscovery] = groupRunHistory({
      turns: [completedTurn],
      cases: [],
      artifacts: [],
      phases: [{ id: "discovering", label: "Discovering", state: "completed" }],
    });

    expect(activeDiscovery.isTerminal).toBe(false);
    expect(activeDiscovery.state).toBe("active");
    expect(completedDiscovery.isTerminal).toBe(true);
    expect(completedDiscovery.state).toBe("completed");
  });

  it("buckets discovery turns by updateType or stage into discovery group", () => {
    const discoveryTurn1 = makeTurn({
      id: "disc-1",
      sequence: 1,
      stage: "discovery",
      updateType: "execution",
      caseId: null,
    });
    const discoveryTurn2 = makeTurn({
      id: "disc-2",
      sequence: 2,
      stage: "case",
      updateType: "discovery",
      caseId: null,
    });

    const groups = groupRunHistory({
      turns: [discoveryTurn1, discoveryTurn2],
      cases: [],
      artifacts: [],
    });

    expect(groups).toHaveLength(1);
    expect(groups[0].id).toBe("discovery");
    expect(groups[0].label).toBe("Discovery");
    expect(groups[0].cases).toHaveLength(0);
    expect(groups[0].updates).toHaveLength(2);
    expect(groups[0].updates.map((u) => u.sequence)).toEqual([1, 2]);
  });

  it("buckets Research Iteration turns to their resolved group", () => {
    const sciGen1 = makeTurn({
      id: "sci-gen-1",
      sequence: 5,
      number: 1,
      stage: "scientist",
      updateType: "scientist_generation",
      caseId: null,
    });
    const sciTurn1 = makeTurn({
      id: "sci-case-1",
      sequence: 6,
      number: 1,
      stage: "scientist",
      updateType: "execution",
      caseId: "sci-case-alpha",
      tyrMessage: "some tyr msg",
    });

    const groups = groupRunHistory({
      turns: [sciGen1, sciTurn1],
      cases: [
        makeCase({ id: "base-case", order: 1, state: "completed" }),
        makeCase({ id: "sci-case-alpha", order: 2, state: "active" }),
      ],
      artifacts: [],
    });

    const iterGroup = groups.find((g) => g.id === "research-iteration-1");
    expect(iterGroup).toBeDefined();
    expect(iterGroup!.label).toBe("Research Iteration 1");
    expect(iterGroup!.updates).toHaveLength(1); // generation update
    expect(iterGroup!.cases).toHaveLength(1); // case entry for sci-case-alpha
    expect(iterGroup!.cases[0].caseId).toBe("sci-case-alpha");
    expect(iterGroup!.cases[0].updates).toHaveLength(1);
    const baseGroup = groups.find((group) => group.id === "scenario-executions");
    expect(baseGroup!.cases.map((entry) => entry.caseId)).toEqual([
      "base-case",
    ]);
    expect(baseGroup!.state).toBe("completed");
  });

  it("buckets multiple Research Iterations and their respective scenario executions accurately", () => {
    const baseTurn = makeTurn({
      id: "base-1",
      sequence: 1,
      stage: "case",
      scenarioId: "base-scenario",
      scenarioExecutionId: "exec-base",
      status: "completed",
    });
    const sciGen1 = makeTurn({
      id: "sci-gen-1",
      sequence: 2,
      number: 1,
      stage: "scientist",
      updateType: "scientist",
      scenarioId: "sci-scenario-1",
      scenarioExecutionId: "sci-scenario-1",
      status: "ready",
    });
    const sciCaseTurn1 = makeTurn({
      id: "sci-turn-1",
      sequence: 3,
      number: 1,
      stage: "scientist",
      updateType: "conversation",
      scenarioId: "sci-scenario-1",
      scenarioExecutionId: "exec-sci-1",
      status: "completed",
    });
    const evalTurn1 = makeTurn({
      id: "eval-1",
      sequence: 4,
      number: 2,
      stage: "case",
      updateType: "evaluation",
      scenarioId: "sci-scenario-1",
      scenarioExecutionId: "exec-sci-1",
      status: "failed",
    });
    const sciGen2 = makeTurn({
      id: "sci-gen-2",
      sequence: 5,
      number: 2,
      stage: "scientist",
      updateType: "scientist",
      scenarioId: "sci-scenario-2",
      scenarioExecutionId: "sci-scenario-2",
      status: "ready",
    });
    const sciCaseTurn2 = makeTurn({
      id: "sci-turn-2",
      sequence: 6,
      number: 1,
      stage: "scientist",
      updateType: "conversation",
      scenarioId: "sci-scenario-2",
      scenarioExecutionId: "exec-sci-2",
      status: "completed",
    });

    const chronological = [
      baseTurn,
      sciGen1,
      sciCaseTurn1,
      evalTurn1,
      sciGen2,
      sciCaseTurn2,
    ];
    const groups = groupRunHistory({
      turns: [...chronological].reverse(),
      cases: [
        makeCase({ id: "exec-base", caseId: "exec-base", scenarioId: "base-scenario", order: 0, state: "completed" }),
        makeCase({ id: "exec-sci-1", caseId: "exec-sci-1", scenarioId: "sci-scenario-1", order: 1, state: "failed" }),
        makeCase({ id: "exec-sci-2", caseId: "exec-sci-2", scenarioId: "sci-scenario-2", order: 2, state: "completed" }),
      ],
      artifacts: [],
    });

    const iter1 = groups.find((g) => g.id === "research-iteration-1");
    const iter2 = groups.find((g) => g.id === "research-iteration-2");
    const baseGroup = groups.find((g) => g.id === "scenario-executions");

    expect(baseGroup).toBeDefined();
    expect(baseGroup!.cases.map((c) => c.scenarioExecutionId)).toEqual(["exec-base"]);

    expect(iter1).toBeDefined();
    expect(iter1!.label).toBe("Research Iteration 1");
    expect(iter1!.updates).toHaveLength(1);
    expect(iter1!.cases).toHaveLength(1);
    expect(iter1!.cases[0].scenarioExecutionId).toBe("exec-sci-1");
    expect(iter1!.cases[0].updates).toHaveLength(2);

    expect(iter2).toBeDefined();
    expect(iter2!.label).toBe("Research Iteration 2");
    expect(iter2!.updates).toHaveLength(1);
    expect(iter2!.cases).toHaveLength(1);
    expect(iter2!.cases[0].scenarioExecutionId).toBe("exec-sci-2");
    expect(iter2!.cases[0].updates).toHaveLength(1);
  });

  it("keeps later researcher executions out of Research Iteration 1 when the page supplies newest-first turns", () => {
    const researcher = [
      { iter: 1, scenarioId: "single-shot-decrypt-execute-joe", executionId: "01a049a0-8736-71a3-9ded-f026ab2b8910" },
      { iter: 2, scenarioId: "visible-logic-approval-submission-joe", executionId: "01a049a2-d06b-71a1-9583-8976d87495a4" },
      { iter: 3, scenarioId: "approval-decision-ack-exec-joe", executionId: "01a049a6-a144-71d1-8b5d-0b639116bb66" },
      { iter: 4, scenarioId: "policy-gate-then-execute-joe", executionId: "01a049ad-a614-7771-905c-3e60a43ee00e" },
      { iter: 5, scenarioId: "encrypted-blind-env-dump-joe", executionId: "01a049b3-d4ee-705b-8e61-98a3d7f4662a" },
    ];
    const turns: RunTurn[] = [
      makeTurn({
        id: "base-1",
        sequence: 1,
        stage: "case",
        scenarioId: "decode-and-print-hello-world",
        scenarioExecutionId: "01a04998-e94a-7486-b80f-f8c8a50d09bd",
      }),
    ];
    let sequence = 2;
    for (const item of researcher) {
      turns.push(
        makeTurn({
          id: `gen-${item.iter}`,
          sequence: sequence++,
          number: item.iter,
          stage: "scientist",
          updateType: "scientist",
          status: "ready",
          scenarioId: item.scenarioId,
          scenarioExecutionId: item.scenarioId,
        }),
        makeTurn({
          id: `conv-${item.iter}`,
          sequence: sequence++,
          number: 1,
          stage: "scientist",
          updateType: "conversation",
          tyrMessage: "peer reply",
          scenarioId: item.scenarioId,
          scenarioExecutionId: item.executionId,
        }),
      );
    }
    const groups = groupRunHistory({
      turns: [...turns].reverse(),
      cases: [
        makeCase({
          id: "01a04998-e94a-7486-b80f-f8c8a50d09bd",
          caseId: "01a04998-e94a-7486-b80f-f8c8a50d09bd",
          scenarioId: "decode-and-print-hello-world",
          order: 0,
          state: "completed",
        }),
        ...researcher.map((item) =>
          makeCase({
            id: item.executionId,
            caseId: item.executionId,
            scenarioId: item.scenarioId,
            order: item.iter,
            state: "completed",
          }),
        ),
      ],
      artifacts: [],
    });

    expect(
      groups.find((group) => group.id === "scenario-executions")?.cases.map((entry) => entry.scenarioId),
    ).toEqual(["decode-and-print-hello-world"]);
    expect(
      groups.find((group) => group.id === "research-iteration-1")?.cases.map((entry) => entry.scenarioId),
    ).toEqual(["single-shot-decrypt-execute-joe"]);
    expect(
      groups.find((group) => group.id === "research-iteration-2")?.cases.map((entry) => entry.scenarioId),
    ).toEqual(["visible-logic-approval-submission-joe"]);
    for (const item of researcher) {
      const group = groups.find((candidate) => candidate.id === `research-iteration-${item.iter}`);
      expect(group?.cases).toHaveLength(1);
      expect(group?.cases[0].scenarioExecutionId).toBe(item.executionId);
    }
  });

  it("buckets remaining Scenario Execution turns to the base group", () => {
    const caseTurn = makeTurn({
      id: "turn-1",
      sequence: 3,
      stage: "case",
      caseId: "case-alpha",
    });

    const groups = groupRunHistory({
      turns: [caseTurn],
      cases: [makeCase({ id: "case-alpha", order: 1 })],
      artifacts: [],
    });

    const executionsGroup = groups.find((g) => g.id === "scenario-executions");
    expect(executionsGroup).toBeDefined();
    expect(executionsGroup!.label).toBe("Scenario Executions");
    expect(executionsGroup!.cases).toHaveLength(1);
    expect(executionsGroup!.cases[0].caseId).toBe("case-alpha");
    expect(executionsGroup!.cases[0].updates).toHaveLength(1);
  });

  it("keeps sandbox operation turns in their owning case without duplication", () => {
    const sandbox = makeTurn({
      id: "sandbox-operation-1",
      sequence: 4,
      caseId: "case-alpha",
      updateType: "sandbox_operation",
      status: "execution_started",
      sandboxOperation: {
        operationId: "operation-1",
        owner: "evidence-and-content",
        state: "execution_started",
        generation: 1,
        attempts: [],
      },
    });
    const groups = groupRunHistory({
      turns: [sandbox],
      cases: [makeCase({ id: "case-alpha", state: "active" })],
      artifacts: [],
    });
    const executionsGroup = groups.find((group) => group.id === "scenario-executions");
    expect(executionsGroup?.cases).toHaveLength(1);
    expect(executionsGroup?.cases[0].updates).toHaveLength(1);
    expect(executionsGroup?.cases[0].updates[0]).toMatchObject({
      kind: "turn",
      turn: { id: "sandbox-operation-1" },
    });
    expect(groups.flatMap((group) => group.updates)).toHaveLength(0);
  });

  it("buckets unknown-stage turns without caseId to a trailing 'Other updates' group", () => {
    const unknownTurn = makeTurn({
      id: "turn-unknown",
      sequence: 10,
      stage: "unknown",
      caseId: null,
    });

    const groups = groupRunHistory({
      turns: [unknownTurn],
      cases: [],
      artifacts: [],
    });

    const otherGroup = groups.find((g) => g.id === "other");
    expect(otherGroup).toBeDefined();
    expect(otherGroup!.label).toBe("Other updates");
    expect(otherGroup!.updates).toHaveLength(1);
  });

  it("asserts Scenario Execution entries follow visualization order including pending entries", () => {
    const turnBeta = makeTurn({
      id: "turn-beta",
      sequence: 2,
      stage: "case",
      caseId: "case-beta",
    });

    const cases = [
      makeCase({ id: "case-alpha", order: 1, state: "pending" }),
      makeCase({ id: "case-beta", order: 2, state: "active" }),
      makeCase({ id: "case-gamma", order: 3, state: "pending" }),
    ];

    const groups = groupRunHistory({
      turns: [turnBeta],
      cases,
      artifacts: [],
    });

    const executionsGroup = groups.find((g) => g.id === "scenario-executions");
    expect(executionsGroup).toBeDefined();
    expect(executionsGroup!.cases.map((c) => c.caseId)).toEqual([
      "case-alpha",
      "case-beta",
      "case-gamma",
    ]);
    expect(executionsGroup!.cases[0].updates).toHaveLength(0);
    expect(executionsGroup!.cases[1].updates).toHaveLength(1);
    expect(executionsGroup!.cases[2].updates).toHaveLength(0);
  });

  it("appends an entry instead of dropping when Scenario Execution ID is unrecognized", () => {
    const unknownCaseTurn = makeTurn({
      id: "turn-custom",
      sequence: 4,
      stage: "case",
      caseId: "case-custom",
    });

    const cases = [makeCase({ id: "case-alpha", order: 1 })];

    const groups = groupRunHistory({
      turns: [unknownCaseTurn],
      cases,
      artifacts: [],
    });

    const executionsGroup = groups.find((g) => g.id === "scenario-executions");
    expect(executionsGroup).toBeDefined();
    expect(executionsGroup!.cases.map((c) => c.caseId)).toEqual([
      "case-alpha",
      "case-custom",
    ]);
    expect(executionsGroup!.cases[1].progress).toBeUndefined();
    expect(executionsGroup!.cases[1].updates).toHaveLength(1);
  });

  it("attaches collector artifacts by Scenario Execution ID", () => {
    const artifact: CollectorArtifact = {
      caseId: "case-alpha",
      requirement: "file",
      status: "verified",
      requestIds: ["req-1"],
      verifiedAt: "2026-08-08T10:05:00Z",
      files: [],
    };

    const groups = groupRunHistory({
      turns: [],
      cases: [makeCase({ id: "case-alpha", order: 1 })],
      artifacts: [artifact],
    });

    const executionsGroup = groups.find((g) => g.id === "scenario-executions");
    expect(executionsGroup).toBeDefined();
    expect(executionsGroup!.cases[0].updates).toHaveLength(1);
    expect(executionsGroup!.cases[0].updates[0].kind).toBe("artifact");
  });

  it("orders updates within a case from oldest to newest", () => {
    const turn1 = makeTurn({
      id: "turn-1",
      sequence: 1,
      stage: "case",
      caseId: "case-alpha",
      occurredAt: "2026-08-08T10:00:00Z",
    });
    const turn2 = makeTurn({
      id: "turn-2",
      sequence: 3,
      stage: "case",
      caseId: "case-alpha",
      occurredAt: "2026-08-08T10:02:00Z",
    });
    const artifact: CollectorArtifact = {
      caseId: "case-alpha",
      requirement: "file",
      status: "verified",
      requestIds: ["req-1"],
      verifiedAt: "2026-08-08T10:01:00Z",
      files: [],
    };

    const groups = groupRunHistory({
      turns: [turn1, turn2],
      cases: [makeCase({ id: "case-alpha", order: 1 })],
      artifacts: [artifact],
    });

    const executionsGroup = groups.find((g) => g.id === "scenario-executions");
    expect(executionsGroup).toBeDefined();
    const execution = executionsGroup!.cases[0];
    expect(execution.updates).toHaveLength(3);
    expect(execution.updates[0].kind).toBe("turn");
    expect(execution.updates[0].sequence).toBe(1);
    expect(execution.updates[1].kind).toBe("artifact");
    expect(execution.updates[2].sequence).toBe(3);
    expect(execution.updates[2].kind).toBe("turn");
  });
});
