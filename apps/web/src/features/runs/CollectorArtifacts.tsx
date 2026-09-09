import { useCallback, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  collectorFileDownloadUrl,
  type CollectorArtifact,
} from "../../api/client";
import { StatusBadge } from "../../components/StatusBadge";
import { CollectorPreview, previewKind } from "./CollectorPreview";

const MAX_PREVIEW_BYTES = 5 * 1024 * 1024;
type CollectorFile = CollectorArtifact["files"][number];

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function statusTone(status: string): "success" | "warning" | "danger" {
  if (status === "verified") return "success";
  if (status === "failed") return "danger";
  return "warning";
}

function statusLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(date);
}

export function CollectorArtifactUpdate({
  runId,
  artifact,
}: {
  runId: string;
  artifact: CollectorArtifact;
}) {
  const [previewFile, setPreviewFile] = useState<CollectorFile | null>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const closePreview = useCallback(() => {
    setPreviewFile(null);
    queueMicrotask(() => openerRef.current?.focus());
  }, []);
  return (
    <>
      <CollectorArtifactUpdateContent
        runId={runId}
        artifact={artifact}
        onPreview={(file, opener) => {
          openerRef.current = opener;
          setPreviewFile(file);
        }}
      />
      {previewFile
        ? createPortal(
            <CollectorPreview
              runId={runId}
              file={previewFile}
              onClose={closePreview}
            />,
            document.body,
          )
        : null}
    </>
  );
}

function CollectorArtifactUpdateContent({
  runId,
  artifact,
  onPreview,
}: {
  runId: string;
  artifact: CollectorArtifact;
  onPreview: (file: CollectorFile, opener: HTMLElement) => void;
}) {
  const scenarioId = artifact.scenarioId ?? artifact.caseId ?? "—";
  const scenarioExecutionId =
    artifact.scenarioExecutionId ?? artifact.caseId ?? scenarioId;
  return (
    <li
      className="turn turn-artifact"
      data-collector-scenario-execution-id={scenarioExecutionId}
    >
      <div className="turn-header">
        <div>
          <h3>
            {artifact.files.length ? "File received" : "Collector verification"}{" "}
            - Scenario Execution {scenarioExecutionId}
          </h3>
          <span className="muted">
            Scenario <span className="mono">{scenarioId}</span> · Execution{" "}
            <span className="mono">{scenarioExecutionId}</span>
          </span>
        </div>
        <div className="turn-header-side">
          <p className="turn-timing mono">
            <time
              dateTime={artifact.verifiedAt ?? undefined}
              title={artifact.verifiedAt ?? undefined}
            >
              {formatTimestamp(artifact.verifiedAt)}
            </time>
          </p>
          <StatusBadge
            label={statusLabel(artifact.status)}
            tone={statusTone(artifact.status)}
          />
        </div>
      </div>
      <div className="turn-messages turn-messages-single">
        <article className="turn-message collector-message">
          <p className="turn-speaker">
            <span aria-hidden="true">C</span>Collector
          </p>
          <p className="collector-request-id mono">
            {artifact.requestIds.join(", ") || "No request ID"}
          </p>
          {artifact.files.length ? (
            <ul className="collector-file-list">
              {artifact.files.map((file) => (
                <li key={file.fileId}>
                  <div>
                    <strong>{file.filename}</strong>
                    <span className="secondary">
                      {file.contentType} · {formatBytes(file.size)}
                    </span>
                    <code>SHA-256 {file.sha256}</code>
                  </div>
                  {file.downloadAvailable ? (
                    <div className="collector-file-actions">
                      {previewKind(file) && file.size <= MAX_PREVIEW_BYTES ? (
                        <button
                          className="button button-secondary"
                          type="button"
                          aria-label={`Preview ${file.filename}`}
                          onClick={(event) =>
                            onPreview(file, event.currentTarget)
                          }
                        >
                          Preview
                        </button>
                      ) : null}
                      <a
                        className="button button-secondary"
                        href={collectorFileDownloadUrl(runId, file.fileId)}
                        aria-label={`Download ${file.filename}`}
                      >
                        Download
                      </a>
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="secondary">No downloadable file was verified.</p>
          )}
        </article>
      </div>
    </li>
  );
}
