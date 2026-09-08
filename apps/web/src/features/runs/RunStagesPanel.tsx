import { currentPhaseLabel, stageStatusLabel } from "./runHelpers";
import { label } from "./runTurnHelpers";

export function RunStagesPanel({
  phases,
  run,
  isLive,
  waitingForTyr,
  agentWorking,
  isLoading,
}: {
  phases?: Array<{ id: string; label: string; state: string }>;
  run?: { state?: string; currentPhase?: string | null };
  isLive: boolean;
  waitingForTyr: boolean;
  agentWorking: boolean;
  isLoading: boolean;
}) {
  return (
    <section
      className={[
        "lifecycle-panel",
        isLive ? "lifecycle-live" : "",
        waitingForTyr ? "lifecycle-waiting" : "",
        agentWorking ? "lifecycle-working" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      aria-labelledby="stages-title"
    >
      <div className="section-heading">
        <h2 id="stages-title">Lifecycle</h2>
        <span className="muted" role="status" aria-live="polite">
          {!isLive && run?.state
            ? label(run.state)
            : waitingForTyr
              ? "Waiting for Tyr"
              : agentWorking
                ? "Agent working"
                : currentPhaseLabel(run, phases)}
        </span>
      </div>
      {isLoading ? (
        <p className="secondary">Loading Experiment stages…</p>
      ) : null}
      <ol className="run-stages" aria-label="Experiment State stages">
        {(phases ?? []).map((phase) => {
          const active = phase.state === "active";
          const statusText = stageStatusLabel(
            phase.state,
            waitingForTyr,
            agentWorking,
            active,
          );
          return (
            <li
              key={phase.id}
              className={[
                "run-stage",
                `stage-${phase.state}`,
                active && waitingForTyr ? "stage-waiting" : "",
                active && agentWorking ? "stage-working" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              aria-current={active ? "step" : undefined}
              title={statusText ? `${phase.label}: ${statusText}` : phase.label}
            >
              <span className="stage-marker" aria-hidden="true" />
              <strong>{phase.label}</strong>
              {statusText ? (
                <span className="stage-state">{statusText}</span>
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
