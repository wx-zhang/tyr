import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  collectorFileDownloadUrl,
  fetchCollectorFilePreview,
  fetchCollectorArtifacts,
  type CollectorArtifact,
} from "../../api/client";
import { StatusBadge } from "../../components/StatusBadge";
import { MarkdownMessage } from "./MarkdownMessage";

const MAX_PREVIEW_BYTES = 5 * 1024 * 1024;
const IMAGE_TYPES = new Set(["image/gif", "image/jpeg", "image/png", "image/webp"]);
type CollectorFile = CollectorArtifact["files"][number];
type PreviewState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; kind: "image"; content: string }
  | { status: "ready"; kind: "markdown" | "text"; content: string };

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

function previewKind(file: CollectorFile): "image" | "markdown" | "text" | null {
  const contentType = file.contentType.split(";", 1)[0].toLowerCase();
  const extension = file.filename.split(".").at(-1)?.toLowerCase();
  if (IMAGE_TYPES.has(contentType)) return "image";
  if (contentType === "text/markdown" || extension === "md" || extension === "markdown") {
    return "markdown";
  }
  if (
    contentType === "text/plain" ||
    contentType === "text/csv" ||
    contentType === "application/json" ||
    extension === "txt"
  ) {
    return "text";
  }
  return null;
}

function CollectorPreview({
  runId,
  file,
  onClose,
}: {
  runId: string;
  file: CollectorFile;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const [preview, setPreview] = useState<PreviewState>({ status: "loading" });
  const kind = previewKind(file);

  useEffect(() => {
    closeRef.current?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const controls = [...dialogRef.current.querySelectorAll<HTMLElement>("button, a[href]")];
      if (!controls.length) return;
      const first = controls[0];
      const last = controls.at(-1)!;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  useEffect(() => {
    const controller = new AbortController();
    let imageUrl: string | null = null;
    setPreview({ status: "loading" });
    void fetchCollectorFilePreview(runId, file.fileId, controller.signal)
      .then(async (response) => {
        if (kind === "image") {
          imageUrl = URL.createObjectURL(await response.blob());
          setPreview({ status: "ready", kind, content: imageUrl });
          return;
        }
        setPreview({ status: "ready", kind: kind ?? "text", content: await response.text() });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setPreview({
            status: "error",
            message: error instanceof Error ? error.message : "Preview could not be loaded",
          });
        }
      });
    return () => {
      controller.abort();
      if (imageUrl) URL.revokeObjectURL(imageUrl);
    };
  }, [file.fileId, kind, runId]);

  return (
    <div className="collector-preview-backdrop" onMouseDown={onClose}>
      <section
        ref={dialogRef}
        className="collector-preview-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="collector-preview-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <p className="eyebrow">Remote-backed evidence</p>
            <h2 id="collector-preview-title">Preview {file.filename}</h2>
          </div>
          <button ref={closeRef} className="button button-secondary" type="button" onClick={onClose}>
            Close preview
          </button>
        </header>
        <div className="collector-preview-content">
          {preview.status === "loading" ? <p role="status">Loading preview…</p> : null}
          {preview.status === "error" ? (
            <p className="callout callout-warning" role="alert">{preview.message}</p>
          ) : null}
          {preview.status === "ready" && preview.kind === "image" ? (
            <img src={preview.content} alt={`Preview of ${file.filename}`} />
          ) : null}
          {preview.status === "ready" && preview.kind === "markdown" ? (
            <MarkdownMessage content={preview.content} />
          ) : null}
          {preview.status === "ready" && preview.kind === "text" ? (
            <pre>{preview.content}</pre>
          ) : null}
        </div>
        <footer>
          <a className="button button-secondary" href={collectorFileDownloadUrl(runId, file.fileId)}>
            Download original
          </a>
        </footer>
      </section>
    </div>
  );
}

export function CollectorArtifacts({
  runId,
  isLive = false,
  refreshMs = 30_000,
}: {
  runId: string;
  isLive?: boolean;
  refreshMs?: number;
}) {
  const [previewFile, setPreviewFile] = useState<CollectorFile | null>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const query = useQuery({
    queryKey: ["collector-artifacts", runId],
    queryFn: () => fetchCollectorArtifacts(runId),
    refetchInterval: isLive ? refreshMs : false,
  });
  const closePreview = () => {
    setPreviewFile(null);
    queueMicrotask(() => openerRef.current?.focus());
  };
  const artifacts = Array.isArray(query.data) ? query.data : [];
  if (!query.isLoading && !query.error && artifacts.length === 0) return null;

  return (
    <section className="collector-artifacts" aria-labelledby="collector-artifacts-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Remote-backed evidence</p>
          <h2 id="collector-artifacts-title">Collector artifacts</h2>
        </div>
      </div>
      {query.isLoading ? <p className="secondary">Loading collector artifacts…</p> : null}
      {query.error ? (
        <p className="callout callout-warning" role="alert">
          Collector artifacts could not be loaded.
        </p>
      ) : null}
      <div className="collector-artifact-list">
        {artifacts.map((artifact) => (
          <article className="collector-artifact-card" key={artifact.caseId}>
            <header>
              <div>
                <h3 className="mono">{artifact.caseId}</h3>
                <p className="secondary mono">
                  {artifact.requestIds.join(", ") || "No request ID"}
                </p>
              </div>
              <StatusBadge
                label={statusLabel(artifact.status)}
                tone={statusTone(artifact.status)}
              />
            </header>
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
                            onClick={(event) => {
                              openerRef.current = event.currentTarget;
                              setPreviewFile(file);
                            }}
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
        ))}
      </div>
      {previewFile ? (
        <CollectorPreview runId={runId} file={previewFile} onClose={closePreview} />
      ) : null}
    </section>
  );
}
