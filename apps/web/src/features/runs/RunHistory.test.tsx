import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type {
  CaseProgress,
  CollectorArtifact,
  RunTurn,
} from "../../api/client";
import { RunHistory } from "./RunHistory";

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
    agentMessage: partial.agentMessage ?? "Agent step message",
    tyrMessage: partial.tyrMessage ?? "Tyr response",
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

describe("RunHistory", () => {
  it("renders Discovery toggle with aria-expanded='true' during discovery while pending cases are aria-expanded='false' with no update DOM", () => {
    const discoveryTurn = makeTurn({
      id: "disc-1",
      sequence: 1,
      stage: "discovery",
      status: "waiting_for_tyr",
      tyrMessage: null,
    });
    const pendingCases = [
      makeCase({ id: "case-alpha", order: 1, state: "pending" }),
      makeCase({ id: "case-beta", order: 2, state: "pending" }),
    ];

    render(
      <RunHistory
        turns={[discoveryTurn]}
        cases={pendingCases}
        artifacts={[]}
        runId="run-1"
        isLive={true}
        persistedTurnsCount={1}
        hasMoreTurns={false}
        isLoadingTurns={false}
        isLoadingMore={false}
        isLoadingArtifacts={false}
        turnsError={null}
        onLoadMore={async () => {}}
        now={Date.now()}
      />,
    );

    const discoveryToggle = screen.getByRole("button", {
      name: "Discovery In progress 1 update",
    });
    expect(discoveryToggle).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByRole("list", { name: "Discovery updates" }),
    ).toBeInTheDocument();

    const executionsToggle = screen.getByRole("button", { name: /Scenario Executions/ });
    expect(executionsToggle).toBeInTheDocument();

    const caseAlphaToggle = screen.getByRole("button", { name: /case-alpha/ });
    expect(caseAlphaToggle).toHaveAttribute("aria-expanded", "false");
    expect(
      screen.queryByRole("list", { name: "Updates for case-alpha" }),
    ).not.toBeInTheDocument();
  });

  it("renders active Scenario Executions collapsed with their status and update count visible", () => {
    const turnAlpha = makeTurn({
      id: "turn-a",
      sequence: 1,
      stage: "case",
      caseId: "case-alpha",
      status: "waiting_for_tyr",
      tyrMessage: null,
    });
    const turnBeta = makeTurn({
      id: "turn-b",
      sequence: 2,
      stage: "case",
      caseId: "case-beta",
      status: "generating",
    });

    const activeCases = [
      makeCase({ id: "case-alpha", order: 1, state: "active" }),
      makeCase({ id: "case-beta", order: 2, state: "active" }),
    ];

    render(
      <RunHistory
        turns={[turnAlpha, turnBeta]}
        cases={activeCases}
        artifacts={[]}
        runId="run-1"
        isLive={true}
        persistedTurnsCount={2}
        hasMoreTurns={false}
        isLoadingTurns={false}
        isLoadingMore={false}
        isLoadingArtifacts={false}
        turnsError={null}
        onLoadMore={async () => {}}
        now={Date.now()}
      />,
    );

    const caseAlphaToggle = screen.getByRole("button", { name: /case-alpha/ });
    const caseBetaToggle = screen.getByRole("button", { name: /case-beta/ });
    expect(caseAlphaToggle).toHaveAttribute("aria-expanded", "false");
    expect(caseBetaToggle).toHaveAttribute("aria-expanded", "false");
    expect(within(caseAlphaToggle).getByText("Running")).toBeInTheDocument();
    expect(within(caseBetaToggle).getByText("Running")).toBeInTheDocument();
    expect(
      screen.queryByRole("list", { name: "Updates for case-alpha" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("list", { name: "Updates for case-beta" }),
    ).not.toBeInTheDocument();
  });

  it("renders Research Iteration 1 group containing generation update and generated Scenario entries while the base group is unchanged", () => {
    const baseTurn = makeTurn({
      id: "base-1",
      sequence: 1,
      stage: "case",
      caseId: "case-alpha",
      status: "completed",
    });
    const sciGenTurn = makeTurn({
      id: "sci-gen-1",
      sequence: 2,
      number: 1,
      stage: "scientist",
      updateType: "scientist_generation",
      status: "completed",
    });
    const sciCaseTurn = makeTurn({
      id: "sci-case-1",
      sequence: 3,
      number: 1,
      stage: "scientist",
      caseId: "case-gen-1",
      status: "completed",
    });

    const cases = [
      makeCase({ id: "case-alpha", order: 1, state: "completed" }),
      makeCase({ id: "case-gen-1", order: 2, state: "completed" }),
    ];

    render(
      <RunHistory
        turns={[baseTurn, sciGenTurn, sciCaseTurn]}
        cases={cases}
        artifacts={[]}
        runId="run-1"
        isLive={false}
        persistedTurnsCount={3}
        hasMoreTurns={false}
        isLoadingTurns={false}
        isLoadingMore={false}
        isLoadingArtifacts={false}
        turnsError={null}
        onLoadMore={async () => {}}
        now={Date.now()}
      />,
    );

    expect(
      screen.getByRole("button", { name: /Scenario Executions/ }),
    ).toBeInTheDocument();
    const iterationGroup = screen.getByRole("list", { name: "Research Iteration 1" });
    const iterToggle = within(iterationGroup).getByRole("button", { name: /^Research Iteration 1/ });
    expect(iterToggle).toBeInTheDocument();
    const baseCases = screen.getByRole("list", { name: "Scenario Executions" });
    expect(within(baseCases).getByText("case-alpha")).toBeInTheDocument();
    expect(within(baseCases).queryByText("case-gen-1")).not.toBeInTheDocument();
    expect(
      within(screen.getByRole("list", { name: "Research Iteration 1" })).getByText(
        "case-gen-1",
      ),
    ).toBeInTheDocument();
  });

  it("renders terminal and active cases collapsed with useful summary rows", () => {
    const turnAlpha = makeTurn({
      id: "turn-a",
      sequence: 1,
      stage: "case",
      caseId: "case-alpha",
      status: "completed",
    });
    const turnBeta = makeTurn({
      id: "turn-b",
      sequence: 2,
      stage: "case",
      caseId: "case-beta",
      status: "waiting_for_tyr",
      tyrMessage: null,
    });

    const cases = [
      makeCase({
        id: "case-alpha",
        order: 1,
        state: "completed",
        verdict: "protected",
        summary: "Tyr denied the unsafe request before execution.",
      }),
      makeCase({ id: "case-beta", order: 2, state: "active" }),
    ];

    render(
      <RunHistory
        turns={[turnAlpha, turnBeta]}
        cases={cases}
        artifacts={[]}
        runId="run-1"
        isLive={true}
        persistedTurnsCount={2}
        hasMoreTurns={false}
        isLoadingTurns={false}
        isLoadingMore={false}
        isLoadingArtifacts={false}
        turnsError={null}
        onLoadMore={async () => {}}
        now={Date.now()}
      />,
    );

    const caseAlphaToggle = screen.getByRole("button", { name: /case-alpha/ });
    expect(caseAlphaToggle).toHaveAttribute("aria-expanded", "false");
    expect(within(caseAlphaToggle).getByText("Scenario Execution 01")).toBeInTheDocument();
    expect(caseAlphaToggle).toHaveTextContent(
      "Tyr denied the unsafe request before execution.",
    );
    expect(within(caseAlphaToggle).getByText("1 update")).toBeInTheDocument();
    expect(
      screen.queryByRole("list", { name: "Updates for case-alpha" }),
    ).not.toBeInTheDocument();

    const caseBetaToggle = screen.getByRole("button", { name: /case-beta/ });
    expect(caseBetaToggle).toHaveAttribute("aria-expanded", "false");
    expect(
      screen.queryByRole("list", { name: "Updates for case-beta" }),
    ).not.toBeInTheDocument();

    const executionsToggle = screen.getByRole("button", { name: /Scenario Executions/ });
    expect(
      within(executionsToggle).getByText("1 of 2 Scenario Executions complete"),
    ).toBeInTheDocument();
  });
});
