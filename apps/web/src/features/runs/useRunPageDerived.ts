import { useMemo, useState } from "react";
import type { RunTurn } from "../../api/client";
import { buildCaseOriginMap } from "./ScientistHistoryUsed";

export function useRunPageDerived({
  turnsData,
  olderTurns,
  visibleLatestTurns,
  datasetCasesData,
  runRecordData,
  isLive,
}: {
  turnsData?: { latestSequence?: number };
  olderTurns: RunTurn[];
  visibleLatestTurns: RunTurn[];
  datasetCasesData?: Array<{ metadata: { id: string } }>;
  runRecordData?: { configuration?: { caseIds?: string[] | null } };
  isLive: boolean;
}) {
  const allTurns = useMemo(() => {
    const byId = new Map(
      [...olderTurns, ...visibleLatestTurns].map((turn) => [turn.id, turn]),
    );
    return [...byId.values()].sort(
      (left, right) => right.sequence - left.sequence,
    );
  }, [olderTurns, visibleLatestTurns]);

  const datasetCaseIds = useMemo(
    () =>
      (Array.isArray(datasetCasesData) ? datasetCasesData : []).map(
        (item) => item.metadata.id,
      ),
    [datasetCasesData],
  );

  const caseOriginById = useMemo(
    () =>
      buildCaseOriginMap(
        allTurns,
        runRecordData?.configuration?.caseIds?.length
          ? runRecordData.configuration.caseIds
          : datasetCaseIds,
      ),
    [allTurns, runRecordData?.configuration?.caseIds, datasetCaseIds],
  );

  const hasOpenTurnWork = Boolean(
    visibleLatestTurns.some(
      (t) => (t.status === "waiting_for_tyr" && !t.tyrMessage) || t.status === "generating",
    ),
  );
  const hasPersistedTurns = Boolean(
    allTurns.length || (turnsData?.latestSequence ?? 0) > 0,
  );
  const hasGeneratingTurn = Boolean(
    visibleLatestTurns.some((turn) => turn.status === "generating"),
  );
  const agentWorking = Boolean(
    isLive && hasPersistedTurns && (hasGeneratingTurn || !hasOpenTurnWork),
  );

  return {
    allTurns,
    datasetCaseIds,
    caseOriginById,
    agentWorking,
  };
}
