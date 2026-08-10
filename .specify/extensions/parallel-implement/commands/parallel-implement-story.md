---
description: "Internal delegate: implement exactly one tasks.md user story in a dedicated git worktree"
---

**Internal delegate** — invoked by `$speckit-parallel-implement` orchestrator via Task; not intended for direct user invocation.

## User Input

```text
$ARGUMENTS
```

The orchestrator injects a `STORY_PAYLOAD:` structured block (YAML-style is fine).

## Role

You implement **exactly one** user-story phase from `$FEATURE_DIR/tasks.md`, checked out inside the story worktree the orchestrator created.

### Required payload keys

- `FEATURE_DIR`
- `STORY_ID` / `STORY_TITLE` / `PRIORITY`
- `WORKTREE_ABS`
- `STORY_BRANCH`
- `INTEGRATION_BRANCH`
- `HEAD_AT_FANOUT`
- `TASK_BLOCK` (verbatim checklist subset for story)
- `INDEPENDENT_TEST`
- `DEP_GRAPH`
- `HARD_RULES` (constitution MUST bullets forwarded by orchestrator)
- `RISK_MITIGATION_BLOCK`
- `EXTRA_GUIDANCE`

## Rules

1. Always set shell `working_directory` to `WORKTREE_ABS`.
2. Never checkout `INTEGRATION_BRANCH`, never delete worktrees, never push/pull.
3. Honour `(depends on Txxx)` sequencing and `[P]` parallelism only when disjoint files permit it.
4. Regenerate committed OpenAPI artefacts only when your tasks touch API routes/schemas — then run `uv run poe export-openapi` and commit `"impl: <STORY_ID> regenerate openapi"` before finishing.

### Story template inside your answer stream

Reuse this skeleton when interpreting instructions:

```
You implement User Story <STORY_ID> ("<STORY_TITLE>", priority <PRIORITY>)

WORKTREE:           <WORKTREE_ABS>
BRANCH:             <STORY_BRANCH>
INTEGRATION BRANCH: <INTEGRATION_BRANCH>
HEAD SNAPSHOT:      <HEAD_AT_FANOUT>

TASKS:
<TASK_BLOCK>

INDEPENDENT TEST:
"<INDEPENDENT_TEST>"

DEPENDENCIES:
<DEP_GRAPH or "(none)">

<HARD_RULES>

<RISK_MITIGATION_BLOCK>

SHARED-FILE RULES EVEN IF NONE LISTED:

- Prefer append-only hunks touching shared hotspots (apps/api, packages, schemas/openapi.json, tasks.md).
- Do not refactor siblings' sections.
- For markdown task lists flip only boxes that belong to this story.

EXIT CONTRACT:

STATUS: DONE  (else STATUS: BLOCKED: … )

- TASK_BLOCK fully `[X]`.
- Narrowest feasible `uv run pytest` green for Python edits.
- `uv run ruff check .`, `pnpm run web:lint`, and `pnpm run web:test` when respective layers are touched.
- `git status` clean on `<STORY_BRANCH>`.
- Report `git log --oneline <HEAD_AT_FANOUT>..HEAD` + touched files + deviations.

EXTRA_GUIDANCE:
<EXTRA_GUIDANCE or "(none)">
```

## Notes

If `TASK_BLOCK` references artefacts under `FEATURE_DIR/contracts` or `.specify/memory/constitution.md`, read them locally — orchestrator purposely stays thin.

If blocked, preserve partial commits with clear rationale so sibling lanes can merge without guessing.
