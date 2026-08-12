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

`routes/experiments.py` queues validated read-only configurations, `routes/runs.py`
serves redacted run review and SSE events, `routes/run_evidence.py` serves
filtered activity and observed relationship projections, and
`routes/collector_artifacts.py` serves run-confined remote-backed previews and downloads. `dependencies.py`
owns run-scoped evidence authorization and browser allowlists, and `registry.py`
is the JSON-backed filesystem registry. `execution.py` owns the bounded in-process queue.

Security and cross-representation regressions live in
`apps/api/tests/test_run_evidence_security.py`; SSE recovery remains covered by
`test_run_events.py`. Regenerate `schemas/openapi.json` from the API source with
`uv run poe schemas` and never edit the generated contract by hand.
