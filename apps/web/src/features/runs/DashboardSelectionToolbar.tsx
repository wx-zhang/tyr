type DashboardSelectionToolbarProps = {
  selectedCount: number;
  allDeletableSelected: boolean;
  deletableCount: number;
  deletePending: boolean;
  onSelectAll: () => void;
  onCancel: () => void;
  onDelete: () => void;
};

export function DashboardSelectionToolbar({
  selectedCount,
  allDeletableSelected,
  deletableCount,
  deletePending,
  onSelectAll,
  onCancel,
  onDelete,
}: DashboardSelectionToolbarProps) {
  return (
    <div
      className="dashboard-selection-controls"
      aria-label="Experiment selection"
    >
      <div className="dashboard-selection-status">
        <input
          type="checkbox"
          className="session-checkbox"
          aria-label="Select all deletable Experiments"
          checked={allDeletableSelected}
          disabled={deletableCount === 0 || deletePending}
          onChange={onSelectAll}
        />
        <p className="muted">
          {selectedCount === 0
            ? "Select Experiments to delete"
            : `${selectedCount} selected`}
        </p>
      </div>
      <div className="button-row">
        <button
          type="button"
          className="button button-ghost run-action"
          disabled={deletePending}
          onClick={onCancel}
        >
          Cancel
        </button>
        <button
          type="button"
          className="button button-danger run-action"
          disabled={selectedCount === 0 || deletePending}
          onClick={onDelete}
        >
          {deletePending
            ? "Deleting…"
            : selectedCount === 0
              ? "Delete selected"
              : `Delete ${selectedCount} selected`}
        </button>
      </div>
    </div>
  );
}
