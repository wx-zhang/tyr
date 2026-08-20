import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { CaseProgress, RunTurn } from "../../api/client";
import { RunHistory } from "./RunHistory";

function makeTurn(id: string, sequence: number): RunTurn {
  return {
    id,
    sequence,
    number: 1,
    stage: "case",
    caseId: "case-alpha",
    updateType: "execution",
    status: "waiting_for_tyr",
    verdict: null,
    objectiveStatus: null,
    outcome: null,
    agentMessage: "Agent step message",
    tyrMessage: null,
    occurredAt: "2026-08-08T10:00:00Z",
    repliedAt: null,
  };
}

const activeCase: CaseProgress = {
  caseId: "case-alpha",
  order: 1,
  state: "active",
};

function history(turns: RunTurn[]) {
  return (
    <RunHistory
      turns={turns}
      cases={[activeCase]}
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

describe("RunHistory interactions", () => {
  it("shows the busy indicator in its case header and not the section header", () => {
    const { container } = render(history([makeTurn("turn-a", 1)]));

    const sectionHeading = container.querySelector(
      ".run-history .section-heading",
    );
    expect(sectionHeading?.querySelector(".tyr-waiting-spinner")).toBeNull();

    const caseToggle = screen.getByRole("button", { name: /case-alpha/ });
    expect(caseToggle.querySelector(".tyr-waiting-spinner")).not.toBeNull();
  });

  it("starts collapsed and preserves an operator's expanded state when updates arrive", () => {
    const turn = makeTurn("turn-a", 1);
    const { rerender } = render(history([turn]));
    const caseToggle = screen.getByRole("button", { name: /case-alpha/ });

    expect(caseToggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(caseToggle);
    expect(caseToggle).toHaveAttribute("aria-expanded", "true");

    rerender(history([turn, makeTurn("turn-a2", 2)]));

    expect(caseToggle).toHaveAttribute("aria-expanded", "true");
  });
});
