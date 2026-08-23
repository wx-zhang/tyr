import type { components } from "../../api/generated";
import { formatBytes, formatHash, label } from "./runTurnHelpers";

export type DecodingProvenanceProps = {
  decoding?: components["schemas"]["DecodingProvenance"] | null;
};

export function DecodingProvenance({ decoding }: DecodingProvenanceProps) {
  if (!decoding) {
    return null;
  }

  const {
    status,
    action,
    rationale,
    attemptCount,
    failureCode,
    failureStage,
    programSha256,
    limitFlags,
    derivedFiles,
    attempts,
  } = decoding;

  const streamValue = (stream: components["schemas"]["DecodingStream"]) => {
    if (stream.state === "captured" && stream.value) {
      return <code className="decoding-stream-value">{stream.value}</code>;
    }
    return <span>{label(stream.state)}</span>;
  };

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
        <div>
          <dt>Route</dt>
          <dd>{action ? label(action) : "Unavailable"}</dd>
        </div>
        {failureStage ? (
          <div>
            <dt>Failure stage</dt>
            <dd>{label(failureStage)}</dd>
          </div>
        ) : null}
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

      {rationale ? (
        <div className="decoding-rationale">
          <p className="muted">Why this route</p>
          <p>{rationale}</p>
        </div>
      ) : null}

      {programSha256?.length ? (
        <div className="decoding-program-hashes">
          <p className="muted">Program SHA-256</p>
          <ul aria-label="Decoder program hashes">
            {programSha256.map((hash, index) => (
              <li key={`${hash}-${index}`} className="mono">
                Attempt {index + 1}: {hash}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {attempts?.length ? (
        <div className="decoding-attempts">
          <p className="muted">Decoder attempts</p>
          <ol aria-label="Decoder attempts">
            {attempts.map((attempt) => (
              <li key={`${attempt.attempt}-${attempt.programSha256}`}>
                <details>
                  <summary>
                    Attempt {attempt.attempt}: {label(attempt.stage)}
                  </summary>
                  {attempt.source ? (
                    <div className="decoding-source">
                      <p className="muted">Executed code</p>
                      <pre>{attempt.source}</pre>
                    </div>
                  ) : null}
                  {attempt.execution ? (
                    <dl className="evaluation-facts decoding-execution-result">
                      <div>
                        <dt>Result</dt>
                        <dd>
                          {attempt.execution.exitCode === null
                            ? "Unavailable"
                            : `Exit ${attempt.execution.exitCode}`}
                        </dd>
                      </div>
                      <div>
                        <dt>Elapsed</dt>
                        <dd>{attempt.execution.elapsedSeconds.toFixed(3)}s</dd>
                      </div>
                      <div>
                        <dt>stdout</dt>
                        <dd>{streamValue(attempt.execution.stdout)}</dd>
                      </div>
                      <div>
                        <dt>stderr</dt>
                        <dd>{streamValue(attempt.execution.stderr)}</dd>
                      </div>
                    </dl>
                  ) : (
                    <p className="muted">Execution result unavailable.</p>
                  )}
                  {attempt.failureCode ? (
                    <p className="decoding-attempt-failure">
                      Failure: {label(attempt.failureCode)}
                    </p>
                  ) : null}
                </details>
              </li>
            ))}
          </ol>
        </div>
      ) : null}

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
