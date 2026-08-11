import type { RunTurn } from "../../api/client";
import { MarkdownMessage } from "./MarkdownMessage";

type ScientistScenarioCardProps = {
  turn: RunTurn;
};

function statusCopy(status: string): { label: string; detail: string } {
  if (status === "generating") {
    return {
      label: "Designing",
      detail: "The scientist is designing a new scenario from seed history.",
    };
  }
  if (status === "failed") {
    return {
      label: "Generation failed",
      detail: "The scientist could not produce a valid scenario.",
    };
  }
  if (status === "ready" || status === "completed") {
    return {
      label: "New scenario",
      detail: "Ready for execution against Tyr.",
    };
  }
  return {
    label: status,
    detail: "Scientist scenario update.",
  };
}

function isHistorySummary(message: string): boolean {
  return (
    /^Iteration \d+ uses \d+ prior test/.test(message) ||
    /^Iteration \d+ has no prior tests/.test(message) ||
    message === "No prior tests were available."
  );
}

export function ScientistScenarioCard({ turn }: ScientistScenarioCardProps) {
  const copy = statusCopy(turn.status);
  const message = turn.agentMessage?.trim() ?? "";
  const title =
    (turn.status === "ready" || turn.status === "completed") && message
      ? message
      : null;
  const showError = turn.status === "failed" && Boolean(message);
  const showWorkingDetail =
    turn.status === "generating" && Boolean(message) && !isHistorySummary(message);

  return (
    <section
      className={`scientist-scenario status-${turn.status}`}
      aria-label="New scientist scenario"
    >
      <header className="scientist-scenario-header">
        <div className="scientist-scenario-heading">
          <p className="scientist-scenario-kicker">
            <span className="scientist-scenario-kicker-dot" aria-hidden="true" />
            {copy.label}
          </p>
          <p className="scientist-scenario-detail">{copy.detail}</p>
        </div>
        {turn.caseId ? (
          <p className="scientist-scenario-id mono" title={turn.caseId}>
            {turn.caseId}
          </p>
        ) : null}
      </header>

      {title ? (
        <div className="scientist-scenario-title">
          <p className="scientist-scenario-title-label">Scenario title</p>
          <p className="scientist-scenario-title-text">{title}</p>
        </div>
      ) : null}

      {showError ? (
        <div className="scientist-scenario-body">
          <MarkdownMessage content={turn.agentMessage} />
        </div>
      ) : null}

      {showWorkingDetail ? (
        <div className="scientist-scenario-body">
          <MarkdownMessage content={turn.agentMessage} />
        </div>
      ) : null}

      {turn.status === "generating" && !showWorkingDetail ? (
        <p className="scientist-scenario-pending">
          Waiting for the model to return a scenario definition…
        </p>
      ) : null}
    </section>
  );
}
