import type { TaskCase } from "../../api/client";

type CaseChecklistProps = {
  cases: TaskCase[];
  selectedCaseIds: string[];
  onToggle: (caseId: string) => void;
  onSelectDefaults: () => void;
  onSelectAll: () => void;
  onClear: () => void;
};

export function CaseChecklist({
  cases,
  selectedCaseIds,
  onToggle,
  onSelectDefaults,
  onSelectAll,
  onClear,
}: CaseChecklistProps) {
  return (
    <>
      <div className="button-row">
        <button
          type="button"
          className="button button-ghost"
          onClick={onSelectDefaults}
        >
          Select defaults
        </button>
        <button
          type="button"
          className="button button-ghost"
          onClick={onSelectAll}
        >
          Select all
        </button>
        <button type="button" className="button button-ghost" onClick={onClear}>
          Clear
        </button>
      </div>
      <div className="case-checklist" role="group" aria-label="Cases">
        {cases.map((item) => {
          const checked = selectedCaseIds.includes(item.id);
          return (
            <label key={item.id} className="choice-card case-choice">
              <input
                type="checkbox"
                checked={checked}
                onChange={() => onToggle(item.id)}
                aria-label={`${item.title} (${item.id})`}
              />
              <span>
                <span className="choice-title">{item.title}</span>
                <span className="choice-description mono">{item.id}</span>
              </span>
            </label>
          );
        })}
      </div>
    </>
  );
}
