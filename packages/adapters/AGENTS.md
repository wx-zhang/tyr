# Adapter scope

## Purpose

Own Tyr MCP, model, task JSON, run-bundle, query, and artifact implementations.

## Standards

External I/O is async where practical. Redact credentials before persistence. Tyr operation settling remains distinct from outer terminal status, and artifact paths stay below the configured root.

## Source map

`tyr/` owns MCP transport and settling, `models/` owns OpenAI-compatible
providers, `tasks/` owns confined JSON loading, and `artifacts/` owns
redacted run bundles, atomic run-level and per-case checkpoint operations
(`checkpoints/cases/<case-id>.json`), canonical activity writes, and legacy
normalization.
`collector.py` owns authenticated exact and timestamp/filename collector lookup,
bounded retries, and digest-verified file and retained request-body downloads;
`collector_content.py` prepares bounded text, image, and safe archive content
for the in-memory reference judge without writing an artifact copy;
`collector_html.py` parses the admin HTML without retaining credentials or headers.
`artifacts/query.py` owns bounded in-memory activity and relationship projections derived from bundles.
`sandbox/` owns attachment snapshots, the disabled and explicitly unsafe host backends,
the fixed Docker CLI backend, its Python 3.14 image, and bounded process support.

Canonical artifact and configured-secret regressions live in
`packages/adapters/tests/test_artifacts.py`; normalization, projection recovery,
relationship, and history behavior remain in the neighboring evidence tests.

## Commands

`uv run pytest packages/adapters/tests` (Docker runtime checks: `uv run pytest -m sandbox_docker`).
