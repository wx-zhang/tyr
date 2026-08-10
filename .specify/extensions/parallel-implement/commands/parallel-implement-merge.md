---
description: "Internal delegate: merge one story lane into the integration branch with gates and conflict resolution"
---

**Internal delegate** — invoked by `$speckit-parallel-implement` orchestrator via Task; not intended for direct user invocation.

## User Input

```text
$ARGUMENTS
```

The orchestrator injects a `MERGE_PAYLOAD:` structured block (YAML-style is fine).

## Incoming contract

Required payload keys:

- `REPO_ROOT`
- `INTEGRATION_BRANCH`
- `STORY_BRANCH`
- `STORY_ID`
- `OPENAPI_TOUCHED` (`true`|`false`)

Optional:

- `EARLIER_MERGED` recap for awareness
- `PRIOR_ATTEMPT_NOTES` (append internally on retries)

Operate with `working_directory = REPO_ROOT`.

## Scripted merge funnel

Canonical command (run from `$REPO_ROOT`):

```
./.specify/extensions/parallel-implement/scripts/bash/speckit-impl-parallel/merge-story.sh \
  "${INTEGRATION_BRANCH}" "${STORY_BRANCH}" "${STORY_ID}" "${OPENAPI_TOUCHED}"
```

Interpret exit statuses:

| code | behaviour |
|---|---|
| `0` | Announce `STATUS: DONE` + summarise commits/files touched (`git diff --name-only @{u}` unnecessary; use pre-merge anchor `git merge-base`). |
| `100` | Unmerged paths (`UU`). Resolve using resolver checklist below then rerun identical command adding `--gate-only`. |
| `101` | Tree merged but lint/tests/openapi drift failed — fix regressions directly on integration branch until clean, then rerun with `--gate-only`. |
| `!=0&&!=100&&!=101` | Treat as tooling failure ⇒ `STATUS: BLOCKED`. |

Record `ANCHOR_SHA=$(git rev-parse HEAD)` before first invocation for diff summaries.

### Resolver playbook (embedded)

1. Capture `git status --short` conflicts.
2. For each conflicting path `$p`, inspect three versions:

```bash
mb="$(git merge-base "$INTEGRATION_BRANCH" "$STORY_BRANCH")"
git show "$mb:$p"
git show "$INTEGRATION_BRANCH:$p"
git show "$STORY_BRANCH:$p"
```

Prefer union of additive hunks consistent with roadmap order (earlier merges first).

3. `schemas/openapi.json`: discard conflict markers, regenerate via `uv run poe export-openapi`, never merge JSON manually.
4. Markdown (`tasks.md`, etc.): keep `[X]` from both sides whenever safe.
5. After resolutions: `git add -A` respecting partial staging discipline; finalize merge (`git commit` if Git still awaits merge conclusion).

Immediately follow with gated rerun:

```
./.specify/extensions/parallel-implement/scripts/bash/speckit-impl-parallel/merge-story.sh \
  "${INTEGRATION_BRANCH}" "${STORY_BRANCH}" "${STORY_ID}" "${OPENAPI_TOUCHED}" --gate-only
```

### Retry budgets

Two full resolver cycles max per story invocation. Append `PRIOR_ATTEMPT NOTES` referencing stderr snippets before second attempt — if still failing, return `STATUS: BLOCKED`.

## Forbidden actions

Never remove story branches/worktrees (`cleanup-worktrees.sh` orchestrator step handles). Never checkout story worktrees unless resolving requires reading file (prefer `git show`).

## Reporting template

DONE:

```
STATUS: DONE
Anchor: <sha>
Commits: git log --oneline <ANCHOR_SHA>..HEAD
Files: git diff --name-only <ANCHOR_SHA> HEAD
```

BLOCKED:

```
STATUS: BLOCKED: headline
Evidence: summarized failing command stderr (trim)
Worktree/state instructions for humans
```
