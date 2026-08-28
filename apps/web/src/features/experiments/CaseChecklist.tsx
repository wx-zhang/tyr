import type { Scenario } from "../../api/client";

type ScenarioChecklistProps = {
  scenarios: Scenario[];
  selectedScenarioIds: string[];
  onToggle: (scenarioId: string) => void;
  onSelectDefaults: () => void;
  onSelectAll: () => void;
  onClear: () => void;
};

export function ScenarioChecklist({
  scenarios,
  selectedScenarioIds,
  onToggle,
  onSelectDefaults,
  onSelectAll,
  onClear,
}: ScenarioChecklistProps) {
  return (
    <>
      <div className="button-row">
        <button type="button" className="button button-ghost" onClick={onSelectDefaults}>Select defaults</button>
        <button type="button" className="button button-ghost" onClick={onSelectAll}>Select all</button>
        <button type="button" className="button button-ghost" onClick={onClear}>Clear</button>
      </div>
      <div className="case-checklist" role="group" aria-label="Scenarios">
        {scenarios.map((scenario) => {
          const scenarioId = scenario.metadata.id;
          const checked = selectedScenarioIds.includes(scenarioId);
          return (
            <label key={scenarioId} className="choice-card case-choice">
              <input
                type="checkbox"
                checked={checked}
                onChange={() => onToggle(scenarioId)}
                aria-label={`${scenario.metadata.title} (${scenarioId})`}
              />
              <span>
                <span className="choice-title">{scenario.metadata.title}</span>
                <span className="choice-description mono">{scenarioId}</span>
              </span>
            </label>
          );
        })}
      </div>
    </>
  );
}

export const CaseChecklist = ScenarioChecklist;
