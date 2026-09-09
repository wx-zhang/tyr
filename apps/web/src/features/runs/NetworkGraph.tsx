import type {
  RelationshipEdge,
  RelationshipParticipant,
} from "../../api/client";
import type { layoutNetwork, LayoutEdge, LayoutNode } from "./networkLayout";

export type Selection =
  | { kind: "participant"; id: string }
  | { kind: "relationship"; id: string }
  | null;

export function participantLabel(
  id: string,
  participants: Map<string, RelationshipParticipant>,
): string {
  return participants.get(id)?.displayLabel ?? id;
}

export function edgeMatchesSelection(
  edge: RelationshipEdge,
  selection: Selection,
): boolean {
  if (!selection) return true;
  if (selection.kind === "relationship") return edge.id === selection.id;
  return (
    edge.sourceParticipantId === selection.id ||
    edge.targetParticipantId === selection.id
  );
}

function nodeMatchesSelection(
  node: LayoutNode,
  selection: Selection,
  edges: LayoutEdge[],
): boolean {
  if (!selection) return true;
  if (selection.kind === "participant") return node.id === selection.id;
  const edge = edges.find((item) => item.id === selection.id);
  if (!edge) return false;
  return (
    node.id === edge.sourceParticipantId || node.id === edge.targetParticipantId
  );
}

export function NetworkGraph({
  layout,
  participantById,
  selection,
  setSelection,
}: {
  layout: ReturnType<typeof layoutNetwork>;
  participantById: Map<string, RelationshipParticipant>;
  selection: Selection;
  setSelection: (selection: Selection) => void;
}) {
  return (
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
        const active =
          edgeMatchesSelection(edge, selection) && Boolean(selection);
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
              aria-pressed={
                selection?.kind === "relationship" && selection.id === edge.id
              }
              onClick={() =>
                setSelection({ kind: "relationship", id: edge.id })
              }
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
          nodeMatchesSelection(node, selection, layout.edges) &&
          Boolean(selection);
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
              aria-pressed={
                selection?.kind === "participant" && selection.id === node.id
              }
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
            <text
              x={node.width / 2}
              y={node.height / 2 + 4}
              textAnchor="middle"
            >
              {node.displayLabel}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
