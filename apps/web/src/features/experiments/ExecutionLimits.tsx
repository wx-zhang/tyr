type ExecutionLimitsProps = {
  maxConcurrentScenarioExecutionsInput: string;
  maxConcurrentScenarioExecutions: number;
  setMaxConcurrentScenarioExecutionsInput: (value: string) => void;
  researchIterationsInput: string;
  researchIterations: number;
  setResearchIterationsInput: (value: string) => void;
  researcherOnly: boolean;
};

export function ExecutionLimits({ maxConcurrentScenarioExecutionsInput, maxConcurrentScenarioExecutions, setMaxConcurrentScenarioExecutionsInput, researchIterationsInput, researchIterations, setResearchIterationsInput, researcherOnly }: ExecutionLimitsProps) {
  return (
          <fieldset className="fieldset setup-limits">
          <legend>Execution limits</legend>
          <div className="field-group">
            <label htmlFor="max-concurrent-scenarios">Max concurrent Scenario Executions</label>
            <input
              id="max-concurrent-scenarios"
              name="maxConcurrentScenarioExecutions"
              type="number"
              min={1}
              max={5}
              step={1}
              inputMode="numeric"
              value={maxConcurrentScenarioExecutionsInput}
              onChange={(event) => setMaxConcurrentScenarioExecutionsInput(event.target.value)}
              onBlur={() => setMaxConcurrentScenarioExecutionsInput(String(maxConcurrentScenarioExecutions))}
            />
            <p className="field-help">Run 1–5 base Scenarios at the same time.</p>
          </div>
          <div className="field-group">
            <div className="field-label-row">
              <label htmlFor="research-iterations">Research Iterations</label>
              <button type="button" className="info-tip" aria-label="What Research Iterations means" aria-describedby="research-iterations-tip">
                <span aria-hidden="true">i</span>
                <span id="research-iterations-tip" role="tooltip" className="info-tip-bubble">The maximum number of new Task-specific Scenarios the Adversarial Researcher generates and runs after discovery.</span>
              </button>
            </div>
            <input
              id="research-iterations"
              name="researchIterations"
              type="number"
              min={0}
              step={1}
              inputMode="numeric"
              value={researchIterationsInput}
              onChange={(event) => setResearchIterationsInput(event.target.value)}
              onBlur={() => setResearchIterationsInput(String(researchIterations))}
            />
            <p className="field-help">
              {researchIterations === 0
                ? researcherOnly
                  ? "Select Scenarios or set Research Iterations above 0."
                  : "Off. Selected Scenarios run only."
                : researcherOnly
                  ? `Adversarial Researcher only: use recent history to generate and run up to ${researchIterations} Scenario${researchIterations === 1 ? "" : "s"}.`
                  : `After selected Scenarios finish, generate and run up to ${researchIterations} Task-specific follow-up Scenario${researchIterations === 1 ? "" : "s"}.`}
            </p>
          </div>
          </fieldset>
  );
}
