# API scope

## Purpose

Own FastAPI routes, DTOs, health/readiness, problem details, and SSE delivery.

## Standards

Keep routes thin: validate input, call the shared execution service, and map the result. Read-only runs use the bounded in-process scheduler. All routes use `/api/v1` except health endpoints.

## Commands

`uv run uvicorn gamr_api.main:app --reload` and `pytest apps/api/tests`.

## Safety

Use local development auth only in the scaffold. Never expose Tyr/model credentials or unredacted artifacts to the browser.

## Source map

`routes/tasks.py` lists manifests and serves cases plus `/plans`, including
live evaluation-reference metadata and content for task review. That content
is read from the task tree and is not a run artifact.
`routes/experiments.py` queues validated read-only configurations, `routes/runs.py`
serves redacted run review and one-second-polled SSE events, `routes/run_evidence.py` serves
filtered activity and observed relationship projections, including decoder lifecycle rows linked to
`result.json#contentOverlap.decoding`; decoder source and streams remain in the redacted provenance
projection, never activity payloads. The run review route carries rationale, attempt hashes, bounded
execution result states, failure stage, and derived-file lineage without rewriting historical bundles, and
`routes/collector_artifacts.py` serves run-confined remote-backed previews and downloads. `composition.py`
wires the shared execution service with global decoder capacity gating (`GAMR_MAX_CONCURRENT_DECODERS`). `dependencies.py`
owns run-scoped evidence authorization and browser allowlists, and `registry.py`
is the JSON-backed filesystem registry. `case_progress.py` reduces case and finding
activities into stable lifecycle states. `execution.py` owns the bounded in-process queue.
Verified request-only manifests may hydrate immutable collector request-body metadata in memory;
failed manifests with exact request IDs may recover verified remote files the same way. The route
never rewrites historical run bundles.

Security and cross-representation regressions live in
`apps/api/tests/test_run_evidence_security.py`; SSE recovery remains covered by
`test_run_events.py`. Regenerate `schemas/openapi.json` from the API source with
`uv run poe schemas` and never edit the generated contract by hand.
