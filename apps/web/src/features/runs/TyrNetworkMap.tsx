import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  fetchRunRelationships,
  type RelationshipEdge,
  type RelationshipParticipant,
} from "../../api/client";
import {
  layoutNetwork,
  statusSummary,
  typeLabel,
  type LayoutEdge,
  type LayoutNode,
} from "./networkLayout";

type Selection =
  | { kind: "participant"; id: string }
  | { kind: "relationship"; id: string }
  | null;

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

function participantLabel(
  id: string,
  participants: Map<string, RelationshipParticipant>,
): string {
  return participants.get(id)?.displayLabel ?? id;
}

function edgeMatchesSelection(edge: RelationshipEdge, selection: Selection): boolean {
  if (!selection) return true;
  if (selection.kind === "relationship") return edge.id === selection.id;
  return (
    edge.sourceParticipantId === selection.id || edge.targetParticipantId === selection.id
  );
}

function nodeMatchesSelection(node: LayoutNode, selection: Selection, edges: LayoutEdge[]): boolean {
  if (!selection) return true;
  if (selection.kind === "participant") return node.id === selection.id;
  const edge = edges.find((item) => item.id === selection.id);
  if (!edge) return false;
  return node.id === edge.sourceParticipantId || node.id === edge.targetParticipantId;
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

export function TyrNetworkMap({ runId, isLive = false, refreshMs = false }: Props) {
  const relationships = useQuery({
    queryKey: ["run-relationships", runId],
    queryFn: () => fetchRunRelationships(runId),
    refetchInterval: isLive ? refreshMs : false,
  });
  const [selection, setSelection] = useState<Selection>(null);
  const [open, setOpen] = useState(() => readNetworkOpen());

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

  const visibleEdges = edges.filter((edge) => edgeMatchesSelection(edge, selection));
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
    body = <p className="secondary">Loading Tyr network…</p>;
  } else if (relationships.error) {
    body = (
      <p className="callout callout-warning" role="alert">
        {relationships.error.message}
      </p>
    );
  } else if (!participants.length || !edges.length) {
    body = <p className="empty-state run-empty">No Tyr network activity observed yet.</p>;
  } else {
    body = (
      <>
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
            <svg
              className="network-graph"
              viewBox={`0 0 ${layout.width} ${layout.height}`}
              role="img"
              aria-label="Observed Tyr network graph"
            >
              <title>Observed Tyr network</title>
              {layout.laneLabels.map((lane) => (
                <text
                  key={lane.lane}
                  className="network-lane-label"
                  x={lane.x}
                  y={22}
                  textAnchor="middle"
                >
                  {lane.label}
                </text>
              ))}
              <defs>
                <marker
                  id="network-arrow"
                  viewBox="0 0 10 10"
                  refX="9"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" className="network-arrow-head" />
                </marker>
              </defs>
              {layout.edges.map((edge) => {
                const active = edgeMatchesSelection(edge, selection) && Boolean(selection);
                const dimmed = Boolean(selection) && !active;
                const labelWidth = Math.max(44, edge.labelText.length * 6.2);
                return (
                  <g
                    key={edge.id}
                    className={[
                      "network-edge",
                      `edge-${edge.primaryType}`,
                      active ? "is-selected" : "",
                      dimmed ? "is-dimmed" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    <path
                      d={edge.path}
                      fill="none"
                      strokeWidth={edge.strokeWidth}
                      markerEnd="url(#network-arrow)"
                      tabIndex={0}
                      role="button"
                      aria-label={`${participantLabel(edge.sourceParticipantId, participantById)} to ${participantLabel(edge.targetParticipantId, participantById)}: ${edge.relationshipTypes.join(", ")} ${edge.activityCount}`}
                      aria-pressed={selection?.kind === "relationship" && selection.id === edge.id}
                      onClick={() => setSelection({ kind: "relationship", id: edge.id })}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelection({ kind: "relationship", id: edge.id });
                        }
                      }}
                    />
                    <rect
                      className="network-edge-label-bg"
                      x={edge.labelX - labelWidth / 2}
                      y={edge.labelY - 11}
                      width={labelWidth}
                      height={16}
                      rx={4}
                    />
                    <text
                      x={edge.labelX}
                      y={edge.labelY}
                      textAnchor="middle"
                      className="network-edge-label"
                    >
                      {edge.labelText}
                    </text>
                  </g>
                );
              })}
              {layout.nodes.map((node) => {
                const active =
                  nodeMatchesSelection(node, selection, layout.edges) && Boolean(selection);
                const dimmed = Boolean(selection) && !active;
                return (
                  <g
                    key={node.id}
                    className={[
                      "network-node",
                      `kind-${node.kind}`,
                      active ? "is-selected" : "",
                      dimmed ? "is-dimmed" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    transform={`translate(${node.x} ${node.y})`}
                  >
                    <rect
                      width={node.width}
                      height={node.height}
                      rx={node.kind === "delegated_agent" ? 22 : 8}
                      tabIndex={0}
                      role="button"
                      aria-label={`${node.displayLabel} (${node.kind.replaceAll("_", " ")})`}
                      aria-pressed={selection?.kind === "participant" && selection.id === node.id}
                      onClick={() => setSelection({ kind: "participant", id: node.id })}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelection({ kind: "participant", id: node.id });
                        }
                      }}
                    >
                      <title>{`${node.displayLabel} (${node.id})`}</title>
                    </rect>
                    <text x={node.width / 2} y={node.height / 2 + 4} textAnchor="middle">
                      {node.displayLabel}
                    </text>
                  </g>
                );
              })}
            </svg>
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
      {body}
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
    return <p className="empty-state run-empty">No connections match the current selection.</p>;
  }
  return (
    <ul className="relationship-list" aria-label="Relationship list">
      {edges.map((edge) => {
        const selected = selection?.kind === "relationship" && selection.id === edge.id;
        return (
          <li key={edge.id}>
            <button
              type="button"
              className={selected ? "relationship-item is-selected" : "relationship-item"}
              aria-pressed={selected}
              onClick={() => onSelect(edge.id)}
            >
              <strong>
                {participantLabel(edge.sourceParticipantId, participants)}
                {" → "}
                {participantLabel(edge.targetParticipantId, participants)}
              </strong>
              <span>
                {edge.relationshipTypes.map(typeLabel).join(", ")} · {edge.activityCount}
              </span>
              <span className="muted">{statusSummary(edge.statusCounts)}</span>
              <span className="mono muted">
                #{edge.firstSequence}
                {edge.lastSequence !== edge.firstSequence ? `–#${edge.lastSequence}` : ""}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
