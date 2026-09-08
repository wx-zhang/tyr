import { useState } from "react";
import type { DiscoveryInputDocument } from "../../api/client";
import { StatusBadge } from "../../components/StatusBadge";
import { readDiscoveryInputFile } from "./discoveryInput";

type DiscoveryInputPanelProps = {
  taskId: string;
  discoveryDocument: DiscoveryInputDocument | null;
  setDiscoveryDocument: (document: DiscoveryInputDocument | null) => void;
  fallbackToDiscovery: boolean;
  setFallbackToDiscovery: (enabled: boolean) => void;
};

export function DiscoveryInputPanel({ taskId, discoveryDocument, setDiscoveryDocument, fallbackToDiscovery, setFallbackToDiscovery }: DiscoveryInputPanelProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [discoveryFileName, setDiscoveryFileName] = useState("");
  const [discoveryError, setDiscoveryError] = useState<string | null>(null);
  const [discoveryInputKey, setDiscoveryInputKey] = useState(0);
  const [fileDragOver, setFileDragOver] = useState(false);
  const handleDiscoveryFile = async (file: File | undefined) => {
    if (!file) return;
    const result = await readDiscoveryInputFile(file);
    if (result.ok) {
      setDiscoveryDocument(result.document);
      setDiscoveryFileName(file.name);
      setDiscoveryError(null);
    } else {
      setDiscoveryDocument(null);
      setDiscoveryFileName(file.name);
      setDiscoveryError(result.error);
      setFallbackToDiscovery(false);
    }
  };

  const clearDiscoveryInput = () => {
    setDiscoveryDocument(null);
    setDiscoveryFileName("");
    setDiscoveryError(null);
    setFallbackToDiscovery(false);
    setDiscoveryInputKey((key) => key + 1);
  };
  return (
          <div className="advanced-panel">
            <button
              type="button"
              className="form-disclosure-toggle"
              aria-expanded={advancedOpen}
              aria-controls="advanced-panel-body"
              onClick={() => setAdvancedOpen((open) => !open)}
            >
              Advanced
              <span className="form-disclosure-hint">
                {discoveryError
                  ? "Discovery input: invalid file"
                  : discoveryDocument
                    ? `Discovery input: ${discoveryFileName}`
                    : "Discovery input: not provided"}
              </span>
            </button>
            {advancedOpen ? (
              <div id="advanced-panel-body" className="advanced-body">
                <div className="advanced-item">
                  <div className="field-label-row">
                    <span className="field-label">Skip discovery · provide target</span>
                    <button type="button" className="info-tip" aria-label="What providing a discovery target means" aria-describedby="discovery-input-tip">
                      <span aria-hidden="true">i</span>
                      <span id="discovery-input-tip" role="tooltip" className="info-tip-bubble">
                        Provide a validated discovery-input JSON document to skip live discovery and start
                        Scenarios with the supplied target. The document is stored with the Preset; the file
                        path is not kept. Its Task ID is informational and is never matched against the
                        selected Task.
                      </span>
                    </button>
                  </div>
                  <label
                    className={`file-drop${fileDragOver ? " is-dragover" : ""}${discoveryError ? " has-error" : ""}`}
                    onDragOver={(event) => {
                      event.preventDefault();
                      setFileDragOver(true);
                    }}
                    onDragLeave={() => setFileDragOver(false)}
                    onDrop={(event) => {
                      event.preventDefault();
                      setFileDragOver(false);
                      void handleDiscoveryFile(event.dataTransfer.files?.[0]);
                    }}
                  >
                    <input
                      className="file-drop-input"
                      name="discoveryInputFile"
                      key={discoveryInputKey}
                      type="file"
                      accept="application/json,.json"
                      onChange={(event) => {
                        void handleDiscoveryFile(event.target.files?.[0]);
                      }}
                    />
                    <span className="file-drop-title">
                      {discoveryFileName || "Choose a JSON file or drop it here"}
                    </span>
                    <span className="file-drop-hint">
                      {discoveryFileName
                        ? "Choose a different file or drop it here"
                        : "Discovery-input JSON document · .json"}
                    </span>
                  </label>
                  {discoveryError ? (
                    <p className="form-status form-status-error" role="alert">{discoveryError}</p>
                  ) : null}
                  {discoveryDocument ? (
                    <div className="discovery-preview">
                      <div className="discovery-preview-status">
                        <StatusBadge label="Valid discovery input" tone="success" />
                        <button type="button" className="button button-ghost" onClick={clearDiscoveryInput}>
                          Remove
                        </button>
                      </div>
                      <dl className="detail-list">
                        <div className="detail-row"><dt>Task ID in document</dt><dd className="mono">{discoveryDocument.taskId}</dd></div>
                        <div className="detail-row"><dt>path</dt><dd className="mono">{discoveryDocument.candidate.path}</dd></div>
                        <div className="detail-row"><dt>workspace</dt><dd className="mono">{discoveryDocument.candidate.workspace}</dd></div>
                        <div className="detail-row"><dt>agent</dt><dd className="mono">{discoveryDocument.candidate.agent}</dd></div>
                        <div className="detail-row"><dt>bridgeId</dt><dd className="mono">{discoveryDocument.candidate.bridgeId}</dd></div>
                      </dl>
                      {taskId && discoveryDocument.taskId !== taskId ? (
                        <p className="field-help">
                          The document Task ID ({discoveryDocument.taskId}) differs from the selected Task
                          ({taskId}). It is kept for reference; the selected Task is unchanged.
                        </p>
                      ) : null}
                      <label className="choice-card choice-card-compact">
                        <input
                          type="checkbox"
                          checked={fallbackToDiscovery}
                          onChange={(event) => setFallbackToDiscovery(event.target.checked)}
                          aria-label="Fall back to live discovery"
                        />
                        <span className="choice-inline-content">
                          <span className="choice-title" aria-hidden="true">Fall back to live discovery</span>
                          <span className="choice-description">
                            Runs a bounded preflight in the selected execution mode before any
                            Scenario Execution; if the provided target is unavailable, normal
                            discovery runs. Off by default: an unavailable target fails the Experiment.
                          </span>
                        </span>
                      </label>
                    </div>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>
  );
}
