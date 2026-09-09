import { useEffect, useRef, useState } from "react";
import {
  collectorFileDownloadUrl,
  fetchCollectorFilePreview,
  type CollectorArtifact,
} from "../../api/client";
import { LoadingStatus } from "../../components/LoadingStatus";
import { MarkdownMessage } from "./MarkdownMessage";

type CollectorFile = CollectorArtifact["files"][number];
type PreviewState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; kind: "image" | "markdown" | "text"; content: string };
const IMAGE_TYPES: Record<string, true> = {
  "image/gif": true,
  "image/jpeg": true,
  "image/png": true,
  "image/webp": true,
};

export function previewKind(
  file: CollectorFile,
): "image" | "markdown" | "text" | null {
  const contentType = file.contentType.split(";", 1)[0].toLowerCase();
  const extension = file.filename.split(".").at(-1)?.toLowerCase();
  if (Object.hasOwn(IMAGE_TYPES, contentType)) return "image";
  if (
    contentType === "text/markdown" ||
    extension === "md" ||
    extension === "markdown"
  ) {
    return "markdown";
  }
  if (
    contentType === "text/plain" ||
    contentType === "text/csv" ||
    contentType === "application/json" ||
    contentType === "application/xml" ||
    contentType === "text/xml" ||
    extension === "xml" ||
    extension === "txt"
  ) {
    return "text";
  }
  return null;
}

export function CollectorPreview({
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
      const controls = [
        ...dialogRef.current.querySelectorAll<HTMLElement>("button, a[href]"),
      ];
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
        if (controller.signal.aborted) return;
        if (kind === "image") {
          const blob = await response.blob();
          if (controller.signal.aborted) return;
          imageUrl = URL.createObjectURL(blob);
          setPreview({ status: "ready", kind, content: imageUrl });
          return;
        }
        const content = await response.text();
        if (!controller.signal.aborted) {
          setPreview({ status: "ready", kind: kind ?? "text", content });
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setPreview({
            status: "error",
            message:
              error instanceof Error
                ? error.message
                : "Preview could not be loaded",
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
          <button
            ref={closeRef}
            className="button button-secondary"
            type="button"
            onClick={onClose}
          >
            Close preview
          </button>
        </header>
        <div className="collector-preview-content">
          {preview.status === "loading" ? (
            <LoadingStatus label={`Loading preview for ${file.filename}…`} />
          ) : null}
          {preview.status === "error" ? (
            <p className="callout callout-warning" role="alert">
              {preview.message}
            </p>
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
          <a
            className="button button-secondary"
            href={collectorFileDownloadUrl(runId, file.fileId)}
          >
            Download original
          </a>
        </footer>
      </section>
    </div>
  );
}
