export type NetworkParticipant = {
  id: string;
  kind: string;
  displayLabel: string;
  firstObservedSequence: number;
};

export type NetworkRelationship = {
  id: string;
  sourceParticipantId: string;
  targetParticipantId: string;
  relationshipTypes: string[];
  activityCount: number;
  statusCounts: Record<string, number>;
  firstSequence: number;
  lastSequence: number;
};

export type LayoutNode = NetworkParticipant & {
  x: number;
  y: number;
  lane: number;
  width: number;
  height: number;
};

export type LayoutEdge = NetworkRelationship & {
  path: string;
  labelX: number;
  labelY: number;
  labelText: string;
  primaryType: string;
  strokeWidth: number;
};

export type NetworkLayout = {
  width: number;
  height: number;
  nodes: LayoutNode[];
  edges: LayoutEdge[];
  laneLabels: Array<{ lane: number; label: string; x: number }>;
};

const LANE_ORDER = [
  "gamr",
  "model_agent",
  "tyr_agent",
  "bridge",
  "delegated_agent",
  "tool",
  "human",
  "unknown",
] as const;

const LANE_LABELS: Record<string, string> = {
  gamr: "GAMR",
  model_agent: "Model",
  tyr_agent: "Tyr",
  bridge: "Bridge",
  delegated_agent: "Agent",
  tool: "Tool",
  human: "Human",
  unknown: "Other",
};

const SHORT_TYPE: Record<string, string> = {
  communication: "comm",
  operation: "op",
  execution: "exec",
  delegation: "deleg",
  bridge: "bridge",
  tool: "tool",
  approval: "approval",
};

const NODE_W = 140;
const NODE_H = 48;
const LANE_GAP = 240;
const ROW_GAP = 96;
const PAD_X = 40;
const PAD_Y = 56;
const EDGE_PAD = 10;
const EDGE_STACK = 18;

function laneIndex(kind: string): number {
  const index = LANE_ORDER.indexOf(kind as (typeof LANE_ORDER)[number]);
  return index >= 0 ? index : LANE_ORDER.length - 1;
}

function primaryType(types: string[]): string {
  const priority = [
    "approval",
    "bridge",
    "execution",
    "delegation",
    "tool",
    "operation",
    "communication",
  ];
  for (const item of priority) {
    if (types.includes(item)) return item;
  }
  return types[0] ?? "communication";
}

function strokeForCount(count: number): number {
  return Math.min(4.5, 1.25 + Math.log1p(count));
}

function pairKey(source: string, target: string): string {
  return source < target ? `${source}::${target}` : `${target}::${source}`;
}

export function layoutNetwork(
  participants: NetworkParticipant[],
  relationships: NetworkRelationship[],
): NetworkLayout {
  const byLane = new Map<number, NetworkParticipant[]>();
  for (const participant of [...participants].sort((left, right) => {
    if (left.firstObservedSequence !== right.firstObservedSequence) {
      return left.firstObservedSequence - right.firstObservedSequence;
    }
    return left.id.localeCompare(right.id);
  })) {
    const lane = laneIndex(participant.kind);
    const list = byLane.get(lane) ?? [];
    list.push(participant);
    byLane.set(lane, list);
  }

  const usedLanes = [...byLane.keys()].sort((a, b) => a - b);
  const laneToColumn = new Map(usedLanes.map((lane, column) => [lane, column]));
  const nodes: LayoutNode[] = [];
  let maxRows = 1;
  for (const lane of usedLanes) {
    const column = laneToColumn.get(lane) ?? 0;
    const list = byLane.get(lane) ?? [];
    maxRows = Math.max(maxRows, list.length);
    list.forEach((participant, row) => {
      nodes.push({
        ...participant,
        lane,
        x: PAD_X + column * LANE_GAP,
        y: PAD_Y + row * ROW_GAP,
        width: NODE_W,
        height: NODE_H,
      });
    });
  }

  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const pairIndex = new Map<string, number>();
  const pairTotals = new Map<string, number>();
  for (const edge of relationships) {
    if (!nodeById.has(edge.sourceParticipantId) || !nodeById.has(edge.targetParticipantId)) {
      continue;
    }
    const key = pairKey(edge.sourceParticipantId, edge.targetParticipantId);
    pairTotals.set(key, (pairTotals.get(key) ?? 0) + 1);
  }

  const edges: LayoutEdge[] = relationships
    .filter(
      (edge) => nodeById.has(edge.sourceParticipantId) && nodeById.has(edge.targetParticipantId),
    )
    .map((edge) => {
      const source = nodeById.get(edge.sourceParticipantId)!;
      const target = nodeById.get(edge.targetParticipantId)!;
      const key = pairKey(edge.sourceParticipantId, edge.targetParticipantId);
      const index = pairIndex.get(key) ?? 0;
      pairIndex.set(key, index + 1);
      const total = pairTotals.get(key) ?? 1;
      const stackOffset = (index - (total - 1) / 2) * EDGE_STACK;

      const leftToRight = source.x <= target.x;
      const from = leftToRight ? source : target;
      const to = leftToRight ? target : source;
      const forward = leftToRight
        ? edge.sourceParticipantId === source.id
        : edge.sourceParticipantId === target.id;

      const x1 = from.x + from.width + EDGE_PAD;
      const x2 = to.x - EDGE_PAD;
      const y1 = from.y + from.height / 2 + stackOffset;
      const y2 = to.y + to.height / 2 + stackOffset;
      const midX = (x1 + x2) / 2;
      const path = forward
        ? Math.abs(y1 - y2) < 2
          ? `M ${x1} ${y1} L ${x2} ${y2}`
          : `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`
        : Math.abs(y1 - y2) < 2
          ? `M ${x2} ${y2} L ${x1} ${y1}`
          : `M ${x2} ${y2} C ${midX} ${y2}, ${midX} ${y1}, ${x1} ${y1}`;

      const type = primaryType(edge.relationshipTypes);
      return {
        ...edge,
        path,
        labelX: midX,
        labelY: Math.min(y1, y2) - 12,
        labelText: `${SHORT_TYPE[type] ?? type} · ${edge.activityCount}`,
        primaryType: type,
        strokeWidth: strokeForCount(edge.activityCount),
      };
    });

  const width = PAD_X * 2 + Math.max(usedLanes.length, 1) * LANE_GAP - (LANE_GAP - NODE_W);
  const height = PAD_Y * 2 + Math.max(maxRows - 1, 0) * ROW_GAP + NODE_H + EDGE_STACK * 2;
  const laneLabels = usedLanes.map((lane) => ({
    lane,
    label: LANE_LABELS[LANE_ORDER[lane] ?? "unknown"] ?? "Other",
    x: PAD_X + (laneToColumn.get(lane) ?? 0) * LANE_GAP + NODE_W / 2,
  }));

  return { width: Math.max(width, 320), height: Math.max(height, 140), nodes, edges, laneLabels };
}

export function typeLabel(value: string): string {
  return value.replaceAll("_", " ");
}

export function statusSummary(counts: Record<string, number>): string {
  return Object.entries(counts)
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .map(([status, count]) => `${status.replaceAll("_", " ")} ${count}`)
    .join(" · ");
}
