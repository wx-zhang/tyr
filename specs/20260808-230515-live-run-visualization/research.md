# Research: Run Evidence Visualization

## Canonical activity

**Decision**: Store one normalized, ordered, redacted activity stream in each JSON bundle.

**Rationale**: CLI and service runs then share stable evidence without a second persistence system.

## Query and relationships

**Decision**: Derive bounded literal search, structured filters, cursor pages, participants, and
signed run-scoped relationships in memory from the selected bundle.

**Rationale**: The 10,000-item budget passes comfortably and avoids synchronization or recovery
logic. A future measured scale requirement can replace the query adapter without changing evidence.

## Live delivery

**Decision**: Use SSE sequence replay from JSONL with bounded resync behavior.

**Rationale**: Delivery stays one-way, reconnectable, and consistent with historical review.
