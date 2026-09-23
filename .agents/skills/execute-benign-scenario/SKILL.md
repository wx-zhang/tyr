---
name: execute-benign-scenario
description: Execute saved benign Tyr functional scenarios through scenario-test or the Benign tests UI, including repetitions and real peer replies. Exclude GAMR attack experiments.
---

# Execute a benign scenario

Read `docs/benign-scenarios.md` before execution.
Validate the saved plan and server-side workspace aliases.
Record explicit operator authorization before an action-enabled run.
Queue with `uv run scenario-test run [scenario.json]` for read-only execution.
Add `--approval-gated --confirm-actions` only within the user's authorized scope.
Use `--repeat [count] --concurrency [count]` for an authorized batch.
Run the worker through `uv run poe dev:watch` or `uv run scenario-test worker`.
Use one worker per storage root.
Read results with `uv run scenario-test show [run-id]`.
Report pending approvals or owner input as pending. Do not impersonate acceptance.
Resume with `uv run scenario-test resume [run-id]` after the real input arrives in Tyr.
Keep shared participants serialized while a run is pending.
Preserve saved state. Do not reset records, alter prompts or repair missing actions during verification.
Report unavailable fresh-bridge evidence as inconclusive.
