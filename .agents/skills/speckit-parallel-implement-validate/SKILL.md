---
name: speckit-parallel-implement-validate
description: 'Internal delegate: repo-wide final validation via final-validate.sh after Polish'
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: github-spec-kit
  source: parallel-implement:commands/parallel-implement-validate.md
---

**Internal delegate** — invoked by `$speckit-parallel-implement` orchestrator via Task; not intended for direct user invocation.

## User Input

```text
$ARGUMENTS
```

The orchestrator injects a `VALIDATION_PAYLOAD:` structured block (YAML-style is fine).

## Incoming contract

Minimum keys:

- `REPO_ROOT`
- `FEATURE_DIR` (for documentation cross-check)

Optional hints:

- `QUICKSTART_PATH` — override relative path (`$FEATURE_DIR/quickstart.md`)
- `NOTES_FROM_OPERATOR`

## Automated gate

Always run:

```
./.specify/extensions/parallel-implement/scripts/bash/speckit-impl-parallel/final-validate.sh
```

from `$REPO_ROOT`. Treat non-zero exits as failures; capture succinct stderr tails but **do not** modify source to fix regressions unless operator explicitly commanded in `NOTES_FROM_OPERATOR`.

### Success response

```
STATUS: DONE
final-validate exit: 0

MANUAL QA REMINDERS:
- ...
```

(or `(none)` if quickstart lacks browser/manual steps.)

### Failure response

```
STATUS: BLOCKED: <phase-from-final-validate-script>

Captured log excerpt:
<<< paste condensed stderr tail (<=35 lines) >>>

Suggested manual follow-ups:
- bullet list referencing failing stage + human owner
```

## Manual quickstart skim

After script success/failure:

1. If quickstart absent: note `(no quickstart)`.
2. Else read headings beneath top-level milestones and map them to actionable manual checks referencing FR bullets when identifiable (e.g. markdown safety). These are reminders for humans; do **not** mark tasks `[X]` here.

## Safety

No git writes, merges, pushes, dependency installs (`pnpm install`, `uv sync`) unless spelled out explicitly in payload notes—the validation lane is diagnostics-only.