# Adapter scope

## Purpose

Own Tyr MCP, model, dataset JSON, run-bundle, query, and artifact implementations.

## Standards

External I/O is async where practical. Redact credentials before persistence. Tyr operation settling remains distinct from outer terminal status, and artifact paths stay below the configured root.

## Source map

`tyr/` owns MCP transport and settling, `models/` owns OpenAI-compatible
providers, `datasets/` owns confined JSON loading, and `artifacts/` owns
redacted run bundles, canonical activity writes, and legacy normalization.
`collector.py` owns authenticated exact and timestamp/filename collector lookup,
file parsing, and bounded digest-verified downloads.
`artifacts/query.py` owns bounded in-memory activity and relationship projections derived from bundles.

Canonical artifact and configured-secret regressions live in
`packages/adapters/tests/test_artifacts.py`; normalization, projection recovery,
relationship, and history behavior remain in the neighboring evidence tests.

## Commands

`uv run pytest packages/adapters/tests`.
