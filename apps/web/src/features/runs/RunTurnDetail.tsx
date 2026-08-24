import { useId, useState } from "react";
import type { RunTurn } from "../../api/client";
import { ExpandableMarkdownMessage, MarkdownMessage } from "./MarkdownMessage";
import {
  resolveHistoryCases,
  ScientistHistoryUsed,
  type HistoryCaseOrigin,
} from "./ScientistHistoryUsed";
import { ScientistScenarioCard } from "./ScientistScenarioCard";
import { DecodingProvenance } from "./DecodingProvenance";
import { SandboxOperationSession } from "./SandboxOperationSession";
import {
  contentOverlapLabel,
  discoveryFields,
  label,
  resultDisplay,
} from "./runTurnHelpers";
import { turnActivityPresentation } from "./runHistoryPresentation";

function WaitingTyr() {
  return (
    <div className="tyr-waiting" role="status" aria-live="polite">
      <span className="tyr-waiting-spinner" aria-hidden="true" />
      <p className="turn-placeholder">
        Waiting for Tyr
        <span className="tyr-waiting-ellipsis" aria-hidden="true">
          <span>.</span>
          <span>.</span>
          <span>.</span>
        </span>
      </p>
    </div>
  );
}

export function RunTurnDetail({
  turn,
  scientistIteration,
  caseOriginById,
  datasetCaseIds,
}: {
  turn: RunTurn;
  scientistIteration?: number;
  caseOriginById?: Map<string, HistoryCaseOrigin>;
  datasetCaseIds?: string[];
}) {
  const [contentComparisonOpen, setContentComparisonOpen] = useState(false);
  const contentComparisonId = useId();
  const presentation = turnActivityPresentation(turn, scientistIteration);
  const evaluationResult = presentation.evaluation
    ? resultDisplay(turn.verdict, turn.objectiveStatus, turn.outcome)
    : null;
  const discovered = presentation.discovery
    ? discoveryFields(turn.agentMessage ?? "")
    : [];
  const contentOverlap = turn.contentOverlap;

  if (presentation.sandboxOperation && turn.sandboxOperation) {
    return (
      <div className="turn-messages turn-messages-single">
        <SandboxOperationSession preview={turn.sandboxOperation} />
      </div>
    );
  }

  if (presentation.evaluation) {
    return (
      <div className="turn-messages turn-messages-single">
        <article
          className={`turn-message evaluation-message verdict-${evaluationResult?.className ?? "unknown"}`}
        >
          <p className="turn-speaker">
            <span aria-hidden="true">A</span>Case assessment
          </p>
          <dl className="evaluation-facts">
            <div>
              <dt>Objective</dt>
              <dd>{label(turn.objectiveStatus)}</dd>
            </div>
            <div>
              <dt>Execution</dt>
              <dd>{label(turn.outcome)}</dd>
            </div>
            {turn.assessmentStatus ? (
              <div>
                <dt>Judge</dt>
                <dd>
                  {turn.assessmentStatus === "failed"
                    ? label(turn.assessmentFailure ?? "needs_review")
                    : label(turn.assessmentStatus)}
                </dd>
              </div>
            ) : null}
            {turn.judgePipeline ? (
              <div>
                <dt>Pipeline</dt>
                <dd>{label(turn.judgePipeline)}</dd>
              </div>
            ) : null}
          </dl>
          {contentOverlap ? (
            <section
              className="content-comparison"
              aria-label="Sensitive content comparison"
            >
              <h4>
                <button
                  type="button"
                  className="content-comparison-toggle"
                  aria-expanded={contentComparisonOpen}
                  aria-controls={contentComparisonId}
                  onClick={() =>
                    setContentComparisonOpen((current) => !current)
                  }
                >
                  <span>Sensitive content comparison</span>
                  <span className="content-comparison-toggle-meta">
                    {contentComparisonOpen ? "Hide details" : "Show details"}
                    <span aria-hidden="true">
                      {contentComparisonOpen ? "−" : "+"}
                    </span>
                  </span>
                </button>
              </h4>
              {contentComparisonOpen ? (
                <div
                  id={contentComparisonId}
                  className="content-comparison-details"
                >
                  <dl className="evaluation-facts">
                    <div>
                      <dt>Result</dt>
                      <dd>{contentOverlapLabel(contentOverlap.status)}</dd>
                    </div>
                    <div>
                      <dt>Files checked</dt>
                      <dd>{contentOverlap.checkedFiles?.length ?? 0}</dd>
                    </div>
                    <div>
                      <dt>Match types</dt>
                      <dd>
                        {contentOverlap.matches?.length
                          ? [
                              ...new Set(
                                contentOverlap.matches.map(
                                  (match) => match.matchType,
                                ),
                              ),
                            ]
                              .map(label)
                              .join(", ")
                          : "—"}
                      </dd>
                    </div>
                  </dl>
                  {contentOverlap.summary ? (
                    <div className="content-comparison-assessment">
                      <p className="muted">Comparison assessment</p>
                      <MarkdownMessage
                        content={
                          contentOverlap.fullSummary ?? contentOverlap.summary
                        }
                      />
                    </div>
                  ) : null}
                  {contentOverlap.checkedFiles?.length ? (
                    <ul
                      className="content-comparison-files"
                      aria-label="Files checked for sensitive content"
                    >
                      {contentOverlap.checkedFiles.map((file) => (
                        <li key={`${file.fileId}-${file.sha256}`}>
                          <span className="mono">{file.filename}</span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  <DecodingProvenance
                    decoding={contentOverlap.decoding}
                    hideAttempts={Boolean(turn.sandboxOperation)}
                  />
                </div>
              ) : null}
            </section>
          ) : null}
          <section className="judge-assessment" aria-label="Judge assessment">
            <h4>Judge assessment</h4>
            <ExpandableMarkdownMessage
              content={turn.assessmentSummary ?? turn.agentMessage ?? ""}
            />
            {turn.missingEvidence?.length ? (
              <div>
                <p className="muted">Missing evidence</p>
                <ul aria-label="Missing evidence">
                  {turn.missingEvidence.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>
        </article>
      </div>
    );
  }

  if (presentation.discovery) {
    return (
      <div className="turn-messages turn-messages-single">
        <article
          className={`turn-message discovery-message status-${turn.status}`}
        >
          <p className="turn-speaker">
            <span aria-hidden="true">D</span>Discovery
          </p>
          {discovered.length ? (
            <dl
              className="discovery-variable-list"
              aria-label="Discovered variables"
            >
              {discovered.map((field) => (
                <div key={field.name} className="discovery-variable-row">
                  <dt className="mono">{field.name}</dt>
                  <dd className="mono">{field.value}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <MarkdownMessage content={turn.agentMessage ?? ""} />
          )}
        </article>
      </div>
    );
  }

  if (presentation.scientistGeneration) {
    return (
      <div className="turn-messages turn-messages-single">
        <article
          className={`turn-message scientist-message status-${turn.status}`}
        >
          <p className="turn-speaker">
            <span aria-hidden="true">S</span>Scientist
          </p>
          <ScientistScenarioCard turn={turn} />
          {turn.historyCaseIds ? (
            <ScientistHistoryUsed
              cases={resolveHistoryCases(turn.historyCaseIds, {
                origins: turn.historyCaseOrigins,
                originByCaseId: caseOriginById,
                taskCaseIds: datasetCaseIds,
              })}
            />
          ) : null}
        </article>
      </div>
    );
  }

  return (
    <div className="turn-messages">
      <article className="turn-message agent-message">
        <p className="turn-speaker">
          <span aria-hidden="true">A</span>Agent
        </p>
        <MarkdownMessage content={turn.agentMessage ?? ""} />
      </article>
      <article
        className={`turn-message tyr-message${presentation.waiting ? " tyr-waiting-panel" : ""}`}
      >
        <p className="turn-speaker">
          <span aria-hidden="true">T</span>Tyr network
        </p>
        {turn.tyrMessage ? (
          <MarkdownMessage content={turn.tyrMessage} />
        ) : presentation.waiting ? (
          <WaitingTyr />
        ) : (
          <p className="turn-placeholder">{label(turn.status)}</p>
        )}
      </article>
    </div>
  );
}
