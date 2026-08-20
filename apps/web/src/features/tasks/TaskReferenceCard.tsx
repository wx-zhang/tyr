import type { TaskReference } from "../../api/client";
import { StatusBadge } from "../../components/StatusBadge";

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function fileName(path: string): string {
  return path.split("/").at(-1) || path;
}

export function TaskReferenceCard({
  reference,
}: {
  reference: TaskReference | null | undefined;
}) {
  if (!reference) return null;

  const classification =
    reference.classification === "synthetic" ? "Synthetic" : reference.classification;

  return (
    <article className="card">
      <div className="card-header">
        <div>
          <p className="eyebrow">Judge comparison source</p>
          <h2>Evaluation reference</h2>
        </div>
        <StatusBadge label={classification} tone="info" />
      </div>
      <dl className="detail-list">
        <div className="detail-row">
          <dt>File</dt>
          <dd className="mono">{fileName(reference.file)}</dd>
        </div>
        <div className="detail-row">
          <dt>Path</dt>
          <dd className="mono">{reference.file}</dd>
        </div>
        <div className="detail-row">
          <dt>Size</dt>
          <dd className="mono tabular">{formatBytes(reference.size)}</dd>
        </div>
        <div className="detail-row">
          <dt>SHA-256</dt>
          <dd className="mono">{reference.sha256}</dd>
        </div>
      </dl>
      <pre className="task-reference-content">{reference.content}</pre>
    </article>
  );
}
