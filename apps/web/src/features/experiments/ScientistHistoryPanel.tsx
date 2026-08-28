type ResearchHistoryPanelProps = {
  testRunsInput: string;
  scientistRunsInput: string;
  testRuns: number;
  scientistRuns: number;
  onTestRunsChange: (value: string) => void;
  onTestRunsBlur: () => void;
  onScientistRunsChange: (value: string) => void;
  onScientistRunsBlur: () => void;
};

export function ResearchHistoryPanel({
  testRunsInput,
  scientistRunsInput,
  testRuns,
  scientistRuns,
  onTestRunsChange,
  onTestRunsBlur,
  onScientistRunsChange,
  onScientistRunsBlur,
}: ResearchHistoryPanelProps) {
  return (
    <aside className="card form-card" aria-labelledby="research-history-title">
      <div className="card-header">
        <div><p className="eyebrow">Adversarial Researcher</p><h2 id="research-history-title">Research Iteration history</h2></div>
      </div>
      <div className="history-window-fields" role="group" aria-label="Research Iteration history window">
        <p className="field-help">Latest executed base Scenarios and Research Iterations seed the Adversarial Researcher.</p>
        <div className="form-grid-two">
          <label className="history-window-control" htmlFor="history-test-runs">
            <span>Executed base Scenarios</span>
            <input id="history-test-runs" name="historyTestRuns" type="number" min={0} max={100} step={1} value={testRunsInput} aria-label="Base Scenarios" onChange={(event) => onTestRunsChange(event.target.value)} onBlur={onTestRunsBlur} />
          </label>
          <label className="history-window-control" htmlFor="history-research-runs">
            <span>Executed Research Iterations</span>
            <input id="history-research-runs" name="historyResearchRuns" type="number" min={0} max={100} step={1} value={scientistRunsInput} aria-label="Research Iterations" onChange={(event) => onScientistRunsChange(event.target.value)} onBlur={onScientistRunsBlur} />
          </label>
        </div>
        <p className="field-help history-window-footnote">Each Scenario is included once, from its most recent completed Experiment.</p>
      </div>
    </aside>
  );
}

export const ScientistHistoryPanel = ResearchHistoryPanel;
