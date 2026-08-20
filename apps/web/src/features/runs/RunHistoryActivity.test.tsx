import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { CaseProgress, RunTurn } from "../../api/client";
import { RunHistory } from "./RunHistory";

function makeTurn(
  partial: Partial<RunTurn> & { id: string; sequence: number },
): RunTurn {
  return {
    number: partial.sequence,
    stage: "case",
    caseId: "case-alpha",
    updateType: "execution",
    status: "completed",
    verdict: null,
    objectiveStatus: null,
    outcome: null,
    agentMessage: `Agent activity ${partial.sequence}`,
    tyrMessage: `Tyr activity ${partial.sequence}`,
    occurredAt: `2026-08-08T10:0${partial.sequence}:00Z`,
    repliedAt: `2026-08-08T10:0${partial.sequence}:01Z`,
    ...partial,
  };
}

function history(
  turns: RunTurn[],
  cases: CaseProgress[],
  phases: Array<{ id: string; label: string; state: string }> = [],
) {
  return (
    <RunHistory
      turns={turns}
      cases={cases}
      phases={phases}
      artifacts={[]}
      runId="run-1"
      isLive={true}
      persistedTurnsCount={turns.length}
      hasMoreTurns={false}
      isLoadingTurns={false}
      isLoadingMore={false}
      isLoadingArtifacts={false}
      turnsError={null}
      onLoadMore={async () => {}}
      now={Date.now()}
    />
  );
}

const activeCase: CaseProgress = {
  caseId: "case-alpha",
  order: 1,
  state: "active",
};

describe("RunHistory activity presentation", () => {
  it("shows lifecycle and security outcome together in collapsed case headers", () => {
    render(
      history(
        [],
        [
          {
            caseId: "case-vulnerable",
            order: 1,
            state: "completed",
            verdict: "vulnerable",
            outcome: "completed",
          },
          {
            caseId: "case-protected",
            order: 2,
            state: "completed",
            verdict: "protected",
            outcome: "completed",
          },
        ],
      ),
    );

    const vulnerable = screen.getByRole("button", { name: /case-vulnerable/ });
    expect(within(vulnerable).getByText("Completed")).toBeInTheDocument();
    expect(
      within(vulnerable).getByText("Vulnerability Exposed"),
    ).toBeInTheDocument();

    const protectedCase = screen.getByRole("button", {
      name: /case-protected/,
    });
    expect(within(protectedCase).getByText("Completed")).toBeInTheDocument();
    expect(within(protectedCase).getByText("No breach")).toBeInTheDocument();
  });

  it("uses an evaluation update verdict before visualization progress catches up", () => {
    const evaluation = makeTurn({
      id: "evaluation-vulnerable",
      sequence: 1,
      caseId: "case-vulnerable",
      updateType: "evaluation",
      verdict: "vulnerable",
      objectiveStatus: "achieved",
      outcome: "completed",
      assessmentSummary: "The protected action was executed.",
    });

    render(
      history(
        [evaluation],
        [{ caseId: "case-vulnerable", order: 1, state: "completed" }],
      ),
    );

    const header = screen.getByRole("button", { name: /case-vulnerable/ });
    expect(within(header).getByText("Completed")).toBeInTheDocument();
    expect(
      within(header).getByText("Vulnerability Exposed"),
    ).toBeInTheDocument();
  });

  it("distinguishes not started, queued, running, assessing, and unavailable cases", () => {
    render(
      history(
        [],
        [
          { caseId: "case-pending", order: 1, state: "pending" },
          { caseId: "case-queued", order: 2, state: "queued" },
          { caseId: "case-running", order: 3, state: "active" },
          { caseId: "case-assessing", order: 4, state: "assessing" },
          { caseId: "case-unknown", order: 5, state: "unknown" },
        ],
      ),
    );

    expect(
      within(screen.getByRole("button", { name: /case-pending/ })).getByText(
        "Not started",
      ),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("button", { name: /case-queued/ })).getByText(
        "Queued",
      ),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("button", { name: /case-running/ })).getByText(
        "Running",
      ),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("button", { name: /case-assessing/ })).getByText(
        "Assessing",
      ),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("button", { name: /case-unknown/ })).getByText(
        "Status unavailable",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Waiting for an execution slot"),
    ).toBeInTheDocument();
  });

  it("does not mark discovery complete while its lifecycle phase is active", () => {
    const discoveryTurn = makeTurn({
      id: "discovery-turn",
      sequence: 1,
      stage: "discovery",
      caseId: null,
      status: "completed",
    });

    render(
      history(
        [discoveryTurn],
        [],
        [{ id: "discovering", label: "Discovering", state: "active" }],
      ),
    );

    const toggle = screen.getByRole("button", {
      name: "Discovery In progress 1 update",
    });
    expect(within(toggle).getByText("In progress")).toBeInTheDocument();
    expect(within(toggle).queryByText("Completed")).not.toBeInTheDocument();
  });

  it("shows explicit aggregate progress and the latest activity in a collapsed case", () => {
    const completedCase: CaseProgress = {
      caseId: "case-alpha",
      order: 1,
      state: "completed",
      verdict: "protected",
      summary: "Older case summary",
    };
    const latest = makeTurn({
      id: "turn-2",
      sequence: 2,
      updateType: "evaluation",
      assessmentSummary: "Latest evaluation summary",
    });

    render(
      history(
        [latest],
        [completedCase, { caseId: "case-beta", order: 2, state: "pending" }],
      ),
    );

    const groupToggle = screen.getByRole("button", { name: /Test cases/ });
    const progress = screen.getByRole("progressbar", {
      name: "Test case progress",
    });
    expect(progress).toHaveAttribute("aria-valuenow", "1");
    expect(progress).toHaveAttribute("aria-valuemax", "2");
    expect(
      within(groupToggle).getByText("1 of 2 cases complete"),
    ).toBeInTheDocument();

    const caseToggle = screen.getByRole("button", { name: /case-alpha/ });
    expect(caseToggle).toHaveAttribute("aria-expanded", "false");
    expect(
      within(caseToggle).getByText("Latest evaluation summary"),
    ).toBeInTheDocument();
  });

  it("keeps older activity compact and expands the latest activity", () => {
    render(
      history(
        [
          makeTurn({ id: "turn-1", sequence: 1 }),
          makeTurn({ id: "turn-2", sequence: 2 }),
        ],
        [activeCase],
      ),
    );

    fireEvent.click(screen.getByRole("button", { name: /case-alpha/ }));

    const updates = screen.getByRole("list", {
      name: "Updates for case-alpha",
    });
    const activityToggles = within(updates).getAllByRole("button");
    expect(activityToggles).toHaveLength(2);
    expect(activityToggles[0]).toHaveAttribute("aria-expanded", "false");
    expect(activityToggles[1]).toHaveAttribute("aria-expanded", "true");
    expect(within(activityToggles[1]).getByText("Latest")).toBeInTheDocument();
    expect(screen.queryByText("Agent activity 1")).not.toBeInTheDocument();
    expect(screen.getByText("Agent activity 2")).toBeInTheDocument();
  });

  it("preserves an activity override when a newer activity arrives", () => {
    const first = makeTurn({ id: "turn-1", sequence: 1 });
    const second = makeTurn({ id: "turn-2", sequence: 2 });
    const { rerender } = render(history([first, second], [activeCase]));
    fireEvent.click(screen.getByRole("button", { name: /case-alpha/ }));
    const updates = screen.getByRole("list", {
      name: "Updates for case-alpha",
    });
    const firstToggle = within(updates).getAllByRole("button")[0];

    fireEvent.click(firstToggle);
    expect(firstToggle).toHaveAttribute("aria-expanded", "true");

    rerender(
      history(
        [first, second, makeTurn({ id: "turn-3", sequence: 3 })],
        [activeCase],
      ),
    );

    expect(firstToggle).toHaveAttribute("aria-expanded", "true");
  });

  it("shows an empty activity state for an active case with no updates", () => {
    render(history([], [activeCase]));

    fireEvent.click(screen.getByRole("button", { name: /case-alpha/ }));

    expect(
      screen.getByText("No updates recorded for this case yet."),
    ).toBeInTheDocument();
  });
});
