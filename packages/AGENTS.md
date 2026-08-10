# Package scope

## Purpose

Own reusable Python packages under `packages/`.

## Standards

Use typed public interfaces, imports at module top, and the inward dependency direction: core, engine, then adapters. Keep I/O out of domain code and prefer async external interfaces.

## Commands

`uv run pytest packages` and `uv run mypy packages`.
