import type { components } from "../../api/generated";
import { formatBytes, formatHash, label } from "./runTurnHelpers";

export type DecodingProvenanceProps = {
  decoding?: components["schemas"]["DecodingProvenance"] | null;
};

export function DecodingProvenance({ decoding }: DecodingProvenanceProps) {
  if (!decoding) {
    return null;
  }

  const { status, attemptCount, failureCode, limitFlags, derivedFiles } = decoding;

  return (
    <section
      className="decoding-provenance"
      aria-label="Trajectory decoding provenance"
    >
      <h4>Trajectory decoding</h4>
      <dl className="evaluation-facts">
        <div>
          <dt>Status</dt>
          <dd>{label(status)}</dd>
        </div>
        <div>
          <dt>Attempts</dt>
          <dd>{attemptCount}</dd>
        </div>
        {failureCode ? (
          <div>
            <dt>Failure code</dt>
            <dd>{label(failureCode)}</dd>
          </div>
        ) : null}
        {limitFlags?.timedOut ? (
          <div>
            <dt>Limit</dt>
            <dd>Timed out</dd>
          </div>
        ) : null}
        {limitFlags?.outputLimited ? (
          <div>
            <dt>Limit</dt>
            <dd>Output limited</dd>
          </div>
        ) : null}
      </dl>

      {status === "succeeded" && derivedFiles && derivedFiles.length > 0 ? (
        <div className="decoding-derived-files">
          <p className="muted">Derived files</p>
          <ul
            className="decoding-lineage-list"
            aria-label="Decoded derived files lineage"
          >
            {derivedFiles.map((file) => (
              <li
                key={`${file.sourceFileId}-${file.uploadedItemId}-${file.sha256}`}
                className="decoding-lineage-item"
              >
                <div className="decoding-lineage-row">
                  <span className="decoding-item-id mono">{file.uploadedItemId}</span>
                  <span className="decoding-type mono">{file.detectedContentType}</span>
                  <span className="decoding-size">{formatBytes(file.size)}</span>
                </div>
                <div className="decoding-lineage-meta">
                  <span className="decoding-source">
                    Source: <span className="mono">{file.sourceFileId}</span>
                  </span>
                  <span className="decoding-digest mono" title={file.sha256}>
                    {formatHash(file.sha256, 8)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
