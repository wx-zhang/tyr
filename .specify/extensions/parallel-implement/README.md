# spec-kit-parallel-implement

Copyright (c) 2026 SoftServe, Inc.

A Spec Kit extension that implements feature tasks in parallel using git worktrees and delegated AI subagents, while keeping the orchestrator context thin.

## Problem

`$speckit-implement` runs everything serially in one branch and loads merge noise, conflict dumps, and validation logs into a single agent session. Large features with independent user stories are slow to implement and hard to review as monolithic diffs.

## Solution

`$speckit-parallel-implement` orchestrates a tech-lead workflow:

1. Run **Setup** and **Foundational** phases sequentially on the integration branch
2. Fan out **user stories** into parallel git worktrees (one branch per story)
3. **Merge sequentially** back onto the integration branch with scripted gates
4. Run **Polish** and repo-wide **validation**

Implementation, merges, and heavy validation run in **delegated subagents**. The orchestrator handles parsing, risk analysis, worktree scripting, and reporting.

## Requirements

- Spec Kit project with `/speckit.tasks` already run (`tasks.md` must exist)
- `git >= 2.5` (worktrees)
- AI agent with `Task` subagent support (Claude Code recommended)
- Optional: `uv`, `pnpm` when project tasks reference Python/Node stacks

## Installation

From a spec-kit project root:

```bash
specify extension add --dev /path/to/spec-kit/extensions/parallel-implement
```

Or from a release ZIP once published:

```bash
specify extension add parallel-implement --from https://github.com/your-org/spec-kit-parallel-implement/archive/refs/tags/v1.1.0.zip
```

`specify extension add` registers **five commands** with your detected AI agents (no manual copy step):

| Command | Role |
|---------|------|
| `$speckit-parallel-implement` | User entry — orchestrator |
| `$speckit-parallel-implement-phase` | Internal delegate — Setup / Foundational / Polish |
| `$speckit-parallel-implement-story` | Internal delegate — one user story per worktree |
| `$speckit-parallel-implement-merge` | Internal delegate — sequential merge + gates |
| `$speckit-parallel-implement-validate` | Internal delegate — repo-wide final validation |

Delegate commands are invoked by the orchestrator via `Task`; users normally run only `$speckit-parallel-implement`.

## Usage

From your AI agent:

```
$speckit-parallel-implement
```

### Arguments

| Token / pattern | Effect |
|-----------------|--------|
| `dry-run` | Stop after manifest / routing printout (outline step 6) |
| `serial` | Delegate entire run to `$speckit-implement` |
| `US1,US4` | Restrict parallel stories (case-preserving) |
| Remaining prose | `EXTRA_GUIDANCE` forwarded into every delegate payload |

### Example

```
$speckit-parallel-implement dry-run
```

Prints manifest, branch/SHA, worktree paths, merge order, and shared-file risks before asking to proceed.

## Bundled scripts

Installed to `.specify/extensions/parallel-implement/scripts/bash/speckit-impl-parallel/`:

| Script | Invoked by | Role |
|--------|------------|------|
| `prepare-worktrees.sh` | Orchestrator | Create per-story worktrees from integration HEAD |
| `cleanup-worktrees.sh` | Orchestrator | Tear down worktrees; `--keep` for blocked story IDs |
| `merge-story.sh` | Merge delegate | Scripted merge + gates; `--gate-only` after fixes |
| `final-validate.sh` | Validate delegate | Aggregate repo-wide validation |

## Hooks

When enabled, offers parallel implementation after `/speckit.tasks` completes (`after_tasks` hook).

## License

MIT License — Copyright (c) 2026 SoftServe, Inc. See [LICENSE](LICENSE).

## Related

- [`phase-implement`](../phase-implement/) — phase-by-phase implementation with one PR per phase
- Core `$speckit-implement` — serial fallback when passing `serial` or when `tasks.md` is ambiguous
