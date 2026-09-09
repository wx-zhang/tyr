import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  fetchRunRelationships,
  type RelationshipEdge,
  type RelationshipParticipant,
} from "../../api/client";
import { LoadingStatus } from "../../components/LoadingStatus";
import { layoutNetwork, statusSummary, typeLabel } from "./networkLayout";
import {
  NetworkGraph,
  edgeMatchesSelection,
  participantLabel,
  type Selection,
} from "./NetworkGraph";

type Props = {
  runId: string;
  isLive?: boolean;
  refreshMs?: number | false;
};

const NETWORK_OPEN_KEY = "gamr-tyr-network-open";

function readNetworkOpen(): boolean {
  try {
    const raw = window.localStorage.getItem(NETWORK_OPEN_KEY);
    if (raw === null) return false;
    return raw === "1";
  } catch {
    return false;
  }
}

function NetworkHeading({ meta }: { meta?: string }) {
  return (
    <div className="network-summary-main">
      <div>
        <p className="eyebrow">Observed relationships</p>
        <h2 id="network-title">Tyr network</h2>
      </div>
      {meta ? (
        <div className="network-heading-meta">
          <span className="muted">{meta}</span>
        </div>
      ) : null}
    </div>
  );
}

export function TyrNetworkMap({
  runId,
  isLive = false,
  refreshMs = false,
}: Props) {
  const [open, setOpen] = useState(() => readNetworkOpen());
  const relationships = useQuery({
    queryKey: ["run-relationships", runId],
    queryFn: () => fetchRunRelationships(runId),
    enabled: open,
    refetchInterval: isLive ? refreshMs : false,
  });
  const [selection, setSelection] = useState<Selection>(null);

  const participants = relationships.data?.participants ?? [];
  const edges = relationships.data?.relationships ?? [];
  const participantById = useMemo(
    () => new Map(participants.map((item) => [item.id, item])),
    [participants],
  );
  const layout = useMemo(
    () => layoutNetwork(participants, edges),
    [participants, edges],
  );

  const visibleEdges = edges.filter((edge) =>
    edgeMatchesSelection(edge, selection),
  );
  const countMeta =
    participants.length || edges.length
      ? `${participants.length} participants · ${edges.length} connections`
      : undefined;

  const setOpenPersist = (next: boolean) => {
    setOpen(next);
    try {
      window.localStorage.setItem(NETWORK_OPEN_KEY, next ? "1" : "0");
    } catch {
      /* ignore quota / private mode */
    }
  };

  let body: React.ReactNode;
  if (relationships.isLoading) {
    body = <LoadingStatus label="Loading Tyr network…" />;
  } else if (relationships.error && !relationships.data) {
    body = (
      <p className="callout callout-warning" role="alert">
        {relationships.error.message}
      </p>
    );
  } else if (!participants.length || !edges.length) {
    body = (
      <p className="empty-state run-empty">
        No Tyr network activity observed yet.
      </p>
    );
  } else {
    body = (
      <>
        {relationships.error ? (
          <p className="callout callout-warning" role="alert">
            Could not refresh Tyr network: {relationships.error.message}
          </p>
        ) : null}
        {selection ? (
          <div className="network-toolbar">
            <button
              type="button"
              className="button button-secondary"
              onClick={() => setSelection(null)}
            >
              Clear selection
            </button>
          </div>
        ) : null}

        <div className="network-body">
          <div className="network-graph-wrap">
            <NetworkGraph
              layout={layout}
              participantById={participantById}
              selection={selection}
              setSelection={setSelection}
            />
          </div>

          <RelationshipList
            edges={visibleEdges}
            participants={participantById}
            selection={selection}
            onSelect={(id) => setSelection({ kind: "relationship", id })}
          />
        </div>
      </>
    );
  }

  return (
    <details className="network-panel" open={open}>
      <summary
        className="network-summary"
        aria-labelledby="network-title"
        onClick={(event) => {
          event.preventDefault();
          setOpenPersist(!open);
        }}
      >
        <NetworkHeading meta={countMeta} />
      </summary>
      {open ? body : null}
    </details>
  );
}

function RelationshipList({
  edges,
  participants,
  selection,
  onSelect,
}: {
  edges: RelationshipEdge[];
  participants: Map<string, RelationshipParticipant>;
  selection: Selection;
  onSelect: (id: string) => void;
}) {
  if (!edges.length) {
    return (
      <p className="empty-state run-empty">
        No connections match the current selection.
      </p>
    );
  }
  return (
    <ul className="relationship-list" aria-label="Relationship list">
      {edges.map((edge) => {
        const selected =
          selection?.kind === "relationship" && selection.id === edge.id;
        return (
          <li key={edge.id}>
            <button
              type="button"
              className={
                selected ? "relationship-item is-selected" : "relationship-item"
              }
              aria-pressed={selected}
              onClick={() => onSelect(edge.id)}
            >
              <strong>
                {participantLabel(edge.sourceParticipantId, participants)}
                {" → "}
                {participantLabel(edge.targetParticipantId, participants)}
              </strong>
              <span>
                {edge.relationshipTypes.map(typeLabel).join(", ")} ·{" "}
                {edge.activityCount}
              </span>
              <span className="muted">{statusSummary(edge.statusCounts)}</span>
              <span className="mono muted">
                #{edge.firstSequence}
                {edge.lastSequence !== edge.firstSequence
                  ? `–#${edge.lastSequence}`
                  : ""}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
