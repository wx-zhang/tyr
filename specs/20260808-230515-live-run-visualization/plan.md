# Run Evidence Visualization Plan

Normalize engine and Tyr observations into ordered, redacted JSONL activity inside each run bundle.
Derive bounded search, filters, relationship aggregation, progress, SSE replay, and evidence views
directly from the selected bundle.

The CLI and optional API use one execution service. The web app only calls the API. The API may
start read-only runs through its bounded in-process queue; it never decides approvals. Historical
and live CLI runs are discovered from the same artifact root.

Validation uses deterministic bundle fixtures, 10,000-item query budgets, generated OpenAPI types,
and accessible graph/list equivalents. Viewing never mutates a bundle.
