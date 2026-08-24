import { useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Prism from "prismjs";
import "prismjs/components/prism-python";
import type { components } from "../../api/generated";
import { formatBytes, formatDuration, formatHash, label, tone } from "./runTurnHelpers";
import { MarkdownMessage } from "./MarkdownMessage";

type Preview = components["schemas"]["SandboxOperationPreview"];
type Attempt = components["schemas"]["SandboxOperationAttempt"];
type OutputFile = components["schemas"]["SandboxOutputFile"];
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
function SandboxFilePreviewModal({
  file,
  onClose,
}: {
  file: OutputFile;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();

  useEffect(() => {
    closeRef.current?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const isMarkdown =
    file.contentType === "text/markdown" ||
    file.path.toLowerCase().endsWith(".md") ||
    file.path.toLowerCase().endsWith(".markdown");
  const content = file.content;

  return (
    <div className="collector-preview-backdrop" onMouseDown={onClose}>
      <section
        ref={dialogRef}
        className="collector-preview-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <p className="eyebrow">Sandbox output artifact</p>
            <h2 id={titleId}>Preview {file.path}</h2>
          </div>
          <button ref={closeRef} className="button button-secondary" type="button" onClick={onClose}>
            Close preview
          </button>
        </header>
        <div className="collector-preview-content">
          {!content || content.state === "empty" ? (
            <p className="secondary">Empty file</p>
          ) : content.state === "captured" && content.value ? (
            isMarkdown ? <MarkdownMessage content={content.value} /> : <pre>{content.value}</pre>
          ) : (
            <p className="callout callout-warning" role="alert">Preview is {content.state}.</p>
          )}
        </div>
      </section>
    </div>
  );
}

function AttemptPanel({
  attempt,
  onPreviewFile,
}: {
  attempt: Attempt;
  onPreviewFile: (file: OutputFile) => void;
}) {
  const source =
    attempt.source?.state === "captured" ? attempt.source.value : null;
  const highlighted = useMemo(
    () =>
      source ? Prism.highlight(source, Prism.languages.python, "python") : "",
    [source],
  );
  const execution = attempt.execution;
  const outputFiles = attempt.outputFiles ?? [];
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
      {outputFiles.length ? (
        <div className="sandbox-output-artifacts">
          <p className="sandbox-subheading">Output artifacts ({outputFiles.length})</p>
          <ul className="sandbox-file-list" aria-label="Output artifacts">
            {outputFiles.map((file) => {
              const canPreview =
                file.content &&
                (file.content.state === "captured" || file.content.state === "empty");
              return (
                <li key={`${file.path}-${file.sha256}`}>
                  <div className="sandbox-file-info">
                    <span className="sandbox-file-path mono">{file.path}</span>
                    <span className="secondary">
                      {file.contentType} · {formatBytes(file.size)}
                    </span>
                    <code title={file.sha256}>SHA-256 {formatHash(file.sha256, 12)}</code>
                  </div>
                  <div className="sandbox-file-actions">
                    {canPreview ? (
                      <button
                        className="button button-secondary"
                        type="button"
                        aria-label={`Preview ${file.path}`}
                        onClick={() => onPreviewFile(file)}
                      >
                        Preview
                      </button>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ) : attempt.outputCount != null ? (
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
  const [previewFile, setPreviewFile] = useState<OutputFile | null>(null);
  const attempts = preview.attempts ?? [];
  const active = !["completed", "failed", "cancelled", "closed"].includes(
    preview.state,
  );
  return (
    <>
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
                onPreviewFile={setPreviewFile}
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
      {previewFile
        ? createPortal(
            <SandboxFilePreviewModal
              file={previewFile}
              onClose={() => setPreviewFile(null)}
            />,
            document.body,
          )
        : null}
    </>
  );
}
