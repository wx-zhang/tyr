# Tyr agent tester migration

Status: implemented
Updated: 2026-08-09

The legacy loop script has been migrated into GAMR's typed shared engine and JSON task/run
contracts.

## Final shape

- `gamr experiment run` is the primary execution path.
- API execution calls the same service for read-only and action-enabled runs (no auto-approval).
- The web app is an optional launcher and evidence viewer.
- CLI and service runs share `.gamr/runs/<run-id>` bundles.
- Task snapshots, checkpoints, events, transcripts, raw diagnostics, results, and reports remain
  portable without a database export.
- Explicit state, structured model output, redaction, idempotency, and Tyr settling replace legacy
  transcript control tokens and optimistic terminal-state handling.

The earlier PostgreSQL queue, leases, SQL projections, and worker process were intentionally
removed. One API instance now uses a bounded in-process queue; restart interrupts unfinished work
without automatic replay. Approval-required execution remains in the CLI.

Future distributed execution is permitted only when deployment evidence justifies it and must
reuse the same engine and bundle contract.
