# Documentation scope

## Purpose

Own architecture, data-format, development, and scaffold documentation under `docs/`.

## Standards

- Keep the scaffold specification authoritative for repository boundaries.
- Update diagrams and links when public interfaces change.
- Prefer concise Markdown and examples that can be copied directly.
- Store deterministic judge graph topology assets under `docs/assets/judges/`, generated via `uv run poe judge-graph <judge-directory>`.

## Commands

Run `uv run poe check` for repository checks. Documentation-only changes need no Python test beyond the relevant check.

## Safety

Never place credentials, real transcripts, or unredacted provider payloads in documentation.
