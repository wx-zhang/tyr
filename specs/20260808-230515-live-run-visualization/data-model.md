# Data Model: Run Evidence Visualization

`RunActivity` and `EvidenceItem` are canonical redacted bundle records. `ExperimentRecord` and
`RunRecord` validate reusable experiment JSON and live lifecycle metadata. `RunParticipant`,
relationship aggregates, progress snapshots, and activity pages are derived in memory for one
selected run.

Stable run IDs, activity IDs, UTC timestamps, monotonic sequences, participant endpoints, evidence
references, and availability states preserve identity across CLI, API, SSE, and web views. Derived
queries never write to the source bundle.
