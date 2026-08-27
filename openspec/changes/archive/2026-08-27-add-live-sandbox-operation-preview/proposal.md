## Why

Judge-owned Python execution is currently visible only after evaluation finishes, so an operator cannot tell whether a sandbox is being prepared, code is running, or evidence collection is stalled. GAMR needs a safe live preview that remains useful as postmortem evidence and can be reused by other predefined judge pipelines without coupling presentation to the current decoder.

## What Changes

- Add a canonical, case-scoped sandbox-operation lifecycle with append-only progress records for request, readiness, execution, collection, cleanup, and terminal outcomes.
- Add one browser-visible terminal-style session that updates in semi-real-time, shows highlighted Python, and becomes the completed postmortem view.
- Keep source and process output bounded and subject to configured-secret redaction, path redaction, and uploaded or decoded content suppression before browser delivery.
- Integrate trajectory decoding with the generic sandbox observer while preserving decoder route and terminal provenance and legacy-run presentation.
- Add an opt-in Caesar-shift upload scenario to the existing exfiltration task so the execution preview and decoder can be exercised through the normal interface.
- Improve live activity discovery latency while retaining the existing SSE replay, heartbeat, and resynchronization behavior.

## Capabilities

### New Capabilities

- `sandbox-operation-preview`: Canonical sandbox progress capture, safe normalization, live API delivery, and terminal-style web presentation for judge-owned execution.

### Modified Capabilities

- `trajectory-content-decoding`: Route decoder sandbox work through the reusable operation observer and avoid duplicate postmortem presentation while retaining legacy compatibility.
- `dataset-case-execution`: Add a reviewed Caesar-encryption upload case to the task catalog without changing the default case selection.

## Impact

The change affects core activity contracts, engine sandbox orchestration, artifact redaction and normalization, API run activity and turn responses, SSE polling, generated OpenAPI and browser types, the run-history UI, task data, tests, and related architecture and UI documentation. Python syntax highlighting adds one focused web dependency and matching theme tokens. The low-level sandbox protocol and backend containment requirements remain unchanged.
