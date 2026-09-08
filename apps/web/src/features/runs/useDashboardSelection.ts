import { useState } from "react";
import type { Run } from "../../api/client";

export function useDashboardSelection(deletableRuns: Run[]) {
  const [selecting, setSelecting] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const allDeletableSelected =
    deletableRuns.length > 0 &&
    deletableRuns.every((run) => selectedIds.has(run.id));
  const exitSelecting = () => {
    setSelecting(false);
    setSelectedIds(new Set());
  };
  const toggleSelected = (runId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(runId)) next.delete(runId);
      else next.add(runId);
      return next;
    });
  };
  const toggleSelectAll = () => {
    setSelectedIds((current) => {
      const next = new Set(current);
      for (const run of deletableRuns) {
        if (allDeletableSelected) next.delete(run.id);
        else next.add(run.id);
      }
      return next;
    });
  };
  return {
    selecting,
    setSelecting,
    selectedIds,
    setSelectedIds,
    allDeletableSelected,
    exitSelecting,
    toggleSelected,
    toggleSelectAll,
  };
}
