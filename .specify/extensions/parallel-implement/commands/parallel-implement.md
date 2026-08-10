---
description: Thin tech-lead parallel implementation — parse tasks.md, orchestrate worktrees and delegated subagents (phase/story/merge/validate) so merge and validation never pollute orchestrator context.
scripts:
  sh: ../../scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks
  ps: ../../scripts/powershell/check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). Supported arguments:

- `dry-run` — stop immediately after Outline step **6**
- `serial` — hand off wholesale to `$speckit-implement`
- Tokens like `US1,US4` constrain `STORIES` list (case-preserving identifiers)
- Residual prose becomes `EXTRA_GUIDANCE` echoed into every delegated Task payload

## Pre-Execution Checks

**Check for extension hooks (before implementation)**:

- Check if `.specify/extensions.yml` exists in the project root.
- If it exists, read it and look for entries under the `hooks.before_implement` key
- If the YAML cannot be parsed or is invalid, skip hook checking silently and continue normally
- Filter to only hooks where `enabled: true`
- For each remaining hook, do **not** attempt to interpret or evaluate hook `condition` expressions:
  - If the hook has no `condition` field, or it is null/empty, treat the hook as executable
  - If the hook defines a non-empty `condition`, skip the hook and leave condition evaluation to the HookExecutor implementation
- For each executable hook, output the following based on its `optional` flag:
  - **Optional hook** (`optional: true`):
    ```
    ## Extension Hooks

    **Optional Pre-Hook**: {extension}
    Command: `/{command}`
    Description: {description}

    Prompt: {prompt}
    To execute: `/{command}`
    ```
  - **Mandatory hook** (`optional: false`):
    ```
    ## Extension Hooks

    **Automatic Pre-Hook**: {extension}
    Executing: `/{command}`
    EXECUTE_COMMAND: {command}

    Wait for the result of the hook command before proceeding to the Outline.
    ```
- If no hooks are registered or `.specify/extensions.yml` does not exist, skip silently

## Thin-orchestrator contract

Never implement tasks yourself beyond manifest parsing, scaffolding prompts, scripted git maintenance, checklist verification, lightweight `tasks.md` checkbox auditing, reporting, hooks.

**Allowed tooling:** `READ/GREP/GLOB/Task`, plus `./.specify/extensions/parallel-implement/scripts/bash/speckit-impl-parallel/{prepare-worktrees,cleanup-worktrees}.sh`.

**Forbidden (orchestrator):** merges, feature commits, implementation edits, lint/test/fix loops, heavyweight context loads (plans, routers, specs, etc.). Narrow exception (step **16**) allow tiny checklist fixes in `$FEATURE_DIR/tasks.md` strictly to reconcile stray `[ ]` markers after agents report DONE.

Delegation map:

| Step | Responsibility |
|---|---|
| Sequential phases | `$speckit-parallel-implement-phase` |
| Story lanes | `$speckit-parallel-implement-story` |
| Ordered merges/gates/conflict repair | `$speckit-parallel-implement-merge` |
| Repo-wide finals | `$speckit-parallel-implement-validate` |
| Worktrees | `./.specify/extensions/parallel-implement/scripts/bash/speckit-impl-parallel/prepare-worktrees.sh` & `cleanup-worktrees.sh` |

Task prompts always begin:

```
Read and follow `$speckit-parallel-implement-<lane>` (or the registered command file for that delegate) verbatim first.
<PAYLOAD>:
```

Where `<lane>` is `phase`, `story`, `merge`, or `validate`.

## Outline

### 1. Prerequisites snapshot

Run `{SCRIPT}` from repo root and parse FEATURE_DIR and AVAILABLE_DOCS. Record:

```
INTEGRATION_BRANCH=$(git rev-parse --abbrev-ref HEAD)
INTEGRATION_HEAD=$(git rev-parse HEAD)
REPO_ROOT=$(git rev-parse --show-toplevel)
```

Abort if working tree dirty (non-empty porcelain) before story fan-out resumes after phase lane completes.

### 2. Checklist gate

Exactly as `$speckit-implement`.

### 3. Lightweight context capture

Orchestrator may read ONLY:

| Path | Scope |
|---|---|
| `$FEATURE_DIR/tasks.md` | Grepped headings + checklist lines sufficient for manifest assembly |
| `plan.md` | Technology stack preamble for forwarding to Setup phase agent |
| `.specify/memory/constitution.md` | Bullet any MUST/MUST NOT rules surfaced as `HARD_RULES` |

Record presence of ancillary docs purely from `AVAILABLE_DOCS`; do **not** load them centrally.

### 4. Manifest + parser

Classify headings `Phase N`:

- `Setup` ⇒ `phase-setup`
- `Foundational` ⇒ `phase-foundational`
- `Polish` ⇒ `phase-polish`
- `User Story` ⇒ `parallel-story`
- else ⇒ `phase-other` (still sequential lane)

Extract `[P]`, `[USx]`, tick lines, inline `` `path` `` tokens, dependency suffixes, `**Independent Test**:` line per story.

Derive `STORIES` ordered by spec + priority. Apply user filter; if none remain → fall back to `$speckit-implement`.

### 5. Tech-lead overlap / RISK blocks

Union of cross-story paths + forced `schemas/openapi.json` + explicit `Avoid touching` mentions. Emit `RISK_MITIGATION_<USx>` text ready to embed.

### 6. Dry-run + human confirm

Print manifest, branch/SHA, worktree paths, merge order, `SHARED_FILES`, and each risk block. If `dry-run`, halt. Else ask user "Proceed (yes/no)".

### 7. Phase · Setup

Task → `$speckit-parallel-implement-phase` with `PHASE_PAYLOAD`. Verify returned `STATUS: DONE`, clean tree, `HEAD` advanced.

### 8. Phase · Foundational

Same contract; new `INTEGRATION_HEAD` becomes fan-out anchor.

### 9. Prepare worktrees (scripted)

Build CSV `STORY_IDS_CSV` (preserve order for cleanup). Run:

```
./.specify/extensions/parallel-implement/scripts/bash/speckit-impl-parallel/prepare-worktrees.sh \
  "$INTEGRATION_BRANCH" "$INTEGRATION_HEAD" "$STORY_IDS_CSV"
```

Parse JSON lines for logging; abort on non-zero.

### 10. Story fan-out

For each story with returned JSON `worktree` path, launch **one Task** referencing `$speckit-parallel-implement-story` + `STORY_PAYLOAD` including `RISK_MITIGATION_BLOCK`. Fire all Tasks in a single assistant turn.

### 11. Story completion matrix

Track `STATUS` lines. `BLOCKED` lanes feed `BLOCKED_STORIES` list for cleanup `--keep`.

### 12. Merge orchestration (sequential)

For each `DONE` story sorted by priority:

1. Determine `OPENAPI_TOUCHED` true iff its `TASK_BLOCK` references `schemas/openapi.json`, `export-openapi`, `apps/api`, or API schema files.
2. Task → `$speckit-parallel-implement-merge` with `MERGE_PAYLOAD` including `OPENAPI_TOUCHED`, `STORY_BRANCH`, etc.
3. If merge delegate returns `STATUS: BLOCKED`, halt merge sequence and surface human instructions.

### 13. Cleanup worktrees

If `BLOCKED_STORIES` is empty:

```
./.specify/extensions/parallel-implement/scripts/bash/speckit-impl-parallel/cleanup-worktrees.sh \
  "$INTEGRATION_BRANCH" "$STORY_IDS_CSV"
```

If one or more lanes never merged:

```
./.specify/extensions/parallel-implement/scripts/bash/speckit-impl-parallel/cleanup-worktrees.sh \
  "$INTEGRATION_BRANCH" "$STORY_IDS_CSV" --keep "US2,US4"
```

### 14. Phase · Polish

Identical Task pattern as Setup/Foundational.

### 15. Final validation lane

Task → `$speckit-parallel-implement-validate` with `VALIDATION_PAYLOAD` (`REPO_ROOT`, `FEATURE_DIR`, optional quickstart path). Accept only `STATUS: DONE/BLOCKED` summary.

### 16. tasks.md hygiene

Grep-check every expected task id has `[X]` when subagents claimed completion; apply tiny `StrReplace` fixes if necessary; log discrepancies.

### 17. Executive report

Summaries per phase, per story, merges, scripts run, blocked assets, final SHA.

### 18. `hooks.after_implement`

Same rules as `$speckit-implement`.

## Edge cases

| Scenario | Handling |
|---|---|
| Merge lane returns `BLOCKED` | Stop funnel; leave integration branch + conflict state untouched; surface instructions |
| Gate failures | Owned by merge delegate / `merge-story.sh` exit `101` loop — orchestrator does not spawn auxiliary fix agents |
| Script failures | Hard stop with stderr tail; do not guess partial cleanup beyond retrying script after human intervention |
| No shared hotspots | Still inject uniform `RISK MITIGATION: (none…)` line for consistent prompts |

When uncertain about ambiguous tasks.md syntax, degrade to `$speckit-implement`.
