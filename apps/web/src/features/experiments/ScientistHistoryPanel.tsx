type ScientistHistoryPanelProps = {
  testRunsInput: string;
  scientistRunsInput: string;
  testRuns: number;
  scientistRuns: number;
  onTestRunsChange: (value: string) => void;
  onTestRunsBlur: () => void;
  onScientistRunsChange: (value: string) => void;
  onScientistRunsBlur: () => void;
};

export function ScientistHistoryPanel({
  testRunsInput,
  scientistRunsInput,
  testRuns,
  scientistRuns,
  onTestRunsChange,
  onTestRunsBlur,
  onScientistRunsChange,
  onScientistRunsBlur,
}: ScientistHistoryPanelProps) {
  return (
    <aside className="card form-card" aria-labelledby="scientist-history-title">
      <div className="card-header">
        <div>
          <p className="eyebrow">Scientist mode</p>
          <h2 id="scientist-history-title">Scientist history</h2>
        </div>
      </div>
      <div
        className="history-window-fields"
        role="group"
        aria-label="Scientist history window"
      >
        <p className="field-help">
          Recent test-case and scientist runs used to seed the scientist.
        </p>
        <div className="form-grid-two">
          <label className="history-window-control" htmlFor="history-test-runs">
            <span>Executed base scenarios</span>
            <input
              id="history-test-runs"
              name="historyTestRuns"
              type="number"
              min={0}
              max={100}
              step={1}
              value={testRunsInput}
              aria-label="Test-case runs"
              onChange={(event) => onTestRunsChange(event.target.value)}
              onBlur={onTestRunsBlur}
            />
          </label>
          <label
            className="history-window-control"
            htmlFor="history-scientist-runs"
          >
            <span>Executed scientist scenarios</span>
            <input
              id="history-scientist-runs"
              name="historyScientistRuns"
              type="number"
              min={0}
              max={100}
              step={1}
              value={scientistRunsInput}
              aria-label="Scientist runs"
              onChange={(event) => onScientistRunsChange(event.target.value)}
              onBlur={onScientistRunsBlur}
            />
          </label>
        </div>
      </div>
    </aside>
  );
}
