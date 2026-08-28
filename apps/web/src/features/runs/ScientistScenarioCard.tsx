import { useId, useState } from "react";
import type { RunTurn } from "../../api/client";
import { MarkdownMessage } from "./MarkdownMessage";

type AdversarialResearcherScenarioCardProps = {
  turn: RunTurn;
};

function statusCopy(status: string): { label: string; detail: string } {
  if (status === "generating") {
    return {
      label: "Designing",
      detail: "The Adversarial Researcher is designing a new Scenario from seed history.",
    };
  }
  if (status === "failed") {
    return {
      label: "Generation failed",
      detail: "The Adversarial Researcher could not produce a valid Scenario.",
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
    detail: "Adversarial Researcher Scenario update.",
  };
}

function isHistorySummary(message: string): boolean {
  return (
    /^Iteration \d+ uses \d+ prior test/.test(message) ||
    /^Iteration \d+ has no prior tests/.test(message) ||
    message === "No prior tests were available."
  );
}

function ScenarioSpecBlock({
  spec,
  id,
}: {
  spec: NonNullable<RunTurn["scenario"]>["spec"];
  id: string;
}) {
  return (
    <div className="scientist-scenario-spec" id={id}>
      <section className="case-section">
        <h4>Objective</h4>
        <p className="plan-prose reading-width">{spec.objective}</p>
      </section>
      <section className="case-section">
        <h4>Steps</h4>
        <ol className="case-steps reading-width">
          {spec.steps.map((step, index) => (
            <li key={`${index}-${step.slice(0, 24)}`}>{step}</li>
          ))}
        </ol>
      </section>
      {spec.successCriteria ? (
        <section className="case-section">
          <h4>Success criteria</h4>
          <p className="plan-prose reading-width">{spec.successCriteria}</p>
        </section>
      ) : null}
      <section className="case-section">
        <h4>Expected control</h4>
        <p className="plan-prose reading-width">{spec.expectedControl}</p>
      </section>
      <section className="case-section">
        <h4>Evidence requirements</h4>
        <ul className="case-evidence reading-width">
          {spec.evidenceRequirements.map((item, index) => (
            <li key={`${index}-${item.slice(0, 24)}`}>{item}</li>
          ))}
        </ul>
      </section>
      {spec.collectorEvidence ? (
        <section className="case-section">
          <h4>Collector evidence</h4>
          <p className="plan-prose reading-width">{spec.collectorEvidence}</p>
        </section>
      ) : null}
    </div>
  );
}

export function AdversarialResearcherScenarioCard({ turn }: AdversarialResearcherScenarioCardProps) {
  const [expanded, setExpanded] = useState(false);
  const definitionId = useId();
  const copy = statusCopy(turn.status);
  const message = turn.agentMessage?.trim() ?? "";
  const title =
    (turn.status === "ready" || turn.status === "completed") && message
      ? message
      : null;
  const spec =
    (turn.status === "ready" || turn.status === "completed") && turn.scenario?.spec
      ? turn.scenario.spec
      : null;
  const showWorkingDetail =
    turn.status === "generating" && Boolean(message) && !isHistorySummary(message);
  const scenarioId = turn.scenarioId ?? turn.caseId;
  const scenarioExecutionId = turn.scenarioExecutionId ?? turn.caseId ?? scenarioId;
  const showError = turn.status === "failed" && Boolean(message);

  return (
    <section
      className={`scientist-scenario status-${turn.status}`}
      aria-label="New Adversarial Researcher Scenario"
    >
      <header className="scientist-scenario-header">
        <div className="scientist-scenario-heading">
          <p className="scientist-scenario-kicker">
            <span className="scientist-scenario-kicker-dot" aria-hidden="true" />
            {copy.label}
          </p>
          <p className="scientist-scenario-detail">{copy.detail}</p>
        </div>
        {scenarioId || scenarioExecutionId ? (
          <p className="scientist-scenario-id mono" title={scenarioId ?? undefined}>
            Scenario {scenarioId ?? "—"} · Execution {scenarioExecutionId ?? "—"}
          </p>
        ) : null}
      </header>

      {title ? (
        <div className="scientist-scenario-title">
          <p className="scientist-scenario-title-text">{title}</p>
        </div>
      ) : null}

      {spec ? (
        <>
          <button
            className="scientist-scenario-toggle"
            type="button"
            aria-expanded={expanded}
            aria-controls={definitionId}
            onClick={() => setExpanded((current) => !current)}
          >
            {expanded ? "Hide complete definition" : "Show complete definition"}
          </button>
          {expanded ? <ScenarioSpecBlock spec={spec} id={definitionId} /> : null}
        </>
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
export const ScientistScenarioCard = AdversarialResearcherScenarioCard;
