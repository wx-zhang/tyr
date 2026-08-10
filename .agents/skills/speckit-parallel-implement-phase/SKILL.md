---
name: speckit-parallel-implement-phase
description: 'Internal delegate: run one sequential tasks.md milestone (Setup, Foundational, or Polish) on the integration branch'
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: github-spec-kit
  source: parallel-implement:commands/parallel-implement-phase.md
---

**Internal delegate** — invoked by `$speckit-parallel-implement` orchestrator via Task; not intended for direct user invocation.

## User Input

```text
$ARGUMENTS
```

The orchestrator injects a `PHASE_PAYLOAD:` structured block (YAML-style is fine).

## Role

You are delegated by the **$speckit-parallel-implement** orchestrator. Read `$speckit-implement` only if you must compare behaviour against the serial fallback.

Required keys inside `PHASE_PAYLOAD`:

- `FEATURE_DIR` — absolute directory containing `tasks.md`.
- `PHASE_KIND` — one of `phase-setup`, `phase-foundational`, `phase-polish`, or `phase-other`.
- `PHASE_NUMBER` — numeric phase (`1`, `2`, `7`, …).
- `PHASE_SHORT_SLUG` — short token for git message (`setup`, `foundational`, `polish`, …).
- `TASK_BLOCK` — **verbatim copy** from `tasks.md`: every checkbox line in this phase (`- [ ] Ti …`).
- `HEAD_AT_START` — git SHA captured before you run.
- `INTEGRATION_BRANCH` — branch checked out (`git rev-parse --abbrev-ref`).
- `HARD_RULES` — bulleted constitution **MUST** / **MUST NOT** excerpts from the orchestrator.
- `EXTRA_GUIDANCE` — free-form guidance from orchestrator arguments (possibly empty).

All tooling runs against the repo root (`git rev-parse --show-toplevel`). Never confuse this with sibling story worktrees.

General execution:

1. Re-open `$FEATURE_DIR/tasks.md` for surrounding prose whenever `TASK_BLOCK` alone is ambiguous.
2. Execute tasks respecting `(depends on TXXX)` plus `[P]` markers (parallelise independent edits when safe).
3. Flip checklist lines to `[X]` as soon as individual tasks truly finish.

## Setup-only responsibilities (`phase-setup`)

Reuse the detection table from `$speckit-implement` §**Project Setup Verification**:

- Dockerfile / compose hints ⇒ `.dockerignore`.
- ESLint / Prettier / Terraform / Helm / NPM publish artefacts ⇒ companion ignore files mirroring `$speckit-implement`.

**Stacks** (abbreviated cheatsheet):

- JS/TS/Node: `node_modules/`, `dist/`, `build/`, `*.log`, `.env*`.
- Python: `__pycache__/`, `*.pyc`, `.venv/`, `venv/`, `dist/`, `*.egg-info/`.
- Java / .NET / Go / Ruby / PHP / Rust / Kotlin / C++/C / Swift / R — defer to `$speckit-implement` for the exhaustive catalogue if uncertain.

Append-only policy: extend existing ignores; never reorganise untouched sections.

## Foundational checkpoints (`phase-foundational`)

- Satisfy prose **Checkpoint:** gates before claiming completion.
- If tasks mention infra (Postgres compose, migrations), summarise what you verified/automated and what remains manual.

## Polish expectations (`phase-polish`)

- Execute every scripted lint/test bullet inside your task slice.
- If `quickstart.md` references browser-only QA, automate what you can (`curl`, scripted smoke) otherwise emit `MANUAL FOLLOW-UPS:` for the orchestrator.

## Exit contract

Return:

```
STATUS: DONE | STATUS: BLOCKED: <reason>
```

Plus:

- `git status --short` (must be empty when DONE except ignored noise).
- `git log --oneline <HEAD_AT_START>^..HEAD` (or `HEAD~n..HEAD` if reflog lacks marker).
- `git diff --name-only <HEAD_AT_START> HEAD`.

When DONE, last commit MUST be `impl: phase <PHASE_NUMBER> <PHASE_SHORT_SLUG>` and **every task** from `TASK_BLOCK` must display `[X]`.

## Guard rails

Never merge/rebase/delete story branches, never mutate `.worktrees/`, never push/pull unless explicitly requested in `EXTRA_GUIDANCE`.