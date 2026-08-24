import { useMemo } from "react";
import Prism from "prismjs";
import "prismjs/components/prism-python";
import type { components } from "../../api/generated";
import { formatDuration, label, tone } from "./runTurnHelpers";

type Preview = components["schemas"]["SandboxOperationPreview"];
type Attempt = components["schemas"]["SandboxOperationAttempt"];

function streamText(
  stream: components["schemas"]["SandboxPreviewText"] | null | undefined,
) {
  if (!stream || stream.state !== "captured" || !stream.value) {
    return (
      <span className="sandbox-stream-state">
        {label(stream?.state ?? "unavailable")}
      </span>
    );
  }
  return <code className="sandbox-stream-value">{stream.value}</code>;
}

function AttemptPanel({ attempt }: { attempt: Attempt }) {
  const source =
    attempt.source?.state === "captured" ? attempt.source.value : null;
  const highlighted = useMemo(
    () =>
      source ? Prism.highlight(source, Prism.languages.python, "python") : "",
    [source],
  );
  const execution = attempt.execution;
  return (
    <details className="sandbox-attempt" open={attempt.state === "running"}>
      <summary>
        <span>Attempt {attempt.attempt}</span>
        <span
          className={`sandbox-attempt-state sandbox-tone-${tone(attempt.state)}`}
        >
          {label(attempt.state)}
        </span>
        <span className="mono">Generation {attempt.generation}</span>
      </summary>
      {source ? (
        <div className="sandbox-source">
          <p className="sandbox-subheading">Python source preview</p>
          <pre
            aria-label={`Python source for sandbox attempt ${attempt.attempt}`}
          >
            <code dangerouslySetInnerHTML={{ __html: highlighted }} />
          </pre>
        </div>
      ) : null}
      {execution ? (
        <div className="sandbox-execution">
          <dl className="sandbox-facts">
            <div>
              <dt>Exit code</dt>
              <dd>{execution.exitCode ?? "Unavailable"}</dd>
            </div>
            <div>
              <dt>Elapsed</dt>
              <dd>{formatDuration(execution.elapsedSeconds * 1000)}</dd>
            </div>
            {execution.timedOut ? (
              <div>
                <dt>Limit</dt>
                <dd>Timed out</dd>
              </div>
            ) : null}
            {execution.outputLimited ? (
              <div>
                <dt>Limit</dt>
                <dd>Output limited</dd>
              </div>
            ) : null}
          </dl>
          <div className="sandbox-streams">
            <div>
              <p className="sandbox-subheading">stdout</p>
              <pre>{streamText(execution.stdout)}</pre>
            </div>
            <div>
              <p className="sandbox-subheading">stderr</p>
              <pre>{streamText(execution.stderr)}</pre>
            </div>
          </div>
        </div>
      ) : null}
      {attempt.outputCount != null ? (
        <p className="sandbox-output-count">
          Collected {attempt.outputCount} output files.
        </p>
      ) : null}
      {attempt.failureCode ? (
        <p className="sandbox-failure">Failure: {label(attempt.failureCode)}</p>
      ) : null}
    </details>
  );
}

export function SandboxOperationSession({ preview }: { preview: Preview }) {
  const attempts = preview.attempts ?? [];
  const active = !["completed", "failed", "cancelled", "closed"].includes(
    preview.state,
  );
  return (
    <section
      className={`sandbox-operation sandbox-operation-${preview.state}`}
      aria-label="Sandbox operation preview"
    >
      <header className="sandbox-operation-header">
        <div>
          <p className="turn-speaker">
            <span aria-hidden="true">⌘</span>Sandbox operation
          </p>
          <p className="sandbox-operation-owner">
            Owner: <span className="mono">{preview.owner}</span>
          </p>
        </div>
        <span
          className={`sandbox-operation-state sandbox-tone-${tone(preview.state)}`}
          role="status"
          aria-live="polite"
          aria-label={`${active ? "Active: " : ""}${label(preview.state)}`}
        >
          {active ? "Active: " : ""}
          {label(preview.state)}
        </span>
      </header>
      <p className="sandbox-operation-id mono">
        Operation {preview.operationId} · Generation {preview.generation}
      </p>
      {attempts.length ? (
        <div className="sandbox-attempts">
          {attempts.map((attempt) => (
            <AttemptPanel
              key={`${attempt.attempt}-${attempt.generation}`}
              attempt={attempt}
            />
          ))}
        </div>
      ) : (
        <p className="sandbox-empty" role="status">
          Sandbox is initializing. No code has run yet.
        </p>
      )}
      {active ? (
        <p className="sandbox-live-note" role="status">
          Live sandbox activity is being captured.
        </p>
      ) : null}
    </section>
  );
}
