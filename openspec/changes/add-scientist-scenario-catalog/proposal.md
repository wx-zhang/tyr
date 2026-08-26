## Why

Scientist-generated scenarios are retained inside individual run bundles, but operators cannot review them as a collection, remove unsuitable scenarios from future scientist history, or export useful scenarios into the task repository. A catalog turns that retained output into a manageable, reusable scenario library without mutating canonical run evidence.

## What Changes

- Add a Scientist scenarios tab or equivalent selection inside the Scenarios section on task details for browsing generated scenarios belonging to that task.
- Show each scenario's originating task, run, canonical definition, and security verdict or pending/unavailable result state.
- Add security-verdict filtering and links back to the run case where each scenario was invented.
- Export one scenario at a time as canonical schema-valid JSON suitable for adding to a task's `cases/` directory.
- Archive and restore scenario catalog entries without deleting their source run evidence.
- Exclude archived scientist scenarios from later scientist prompts, including later iterations of an active run and history loaded from previous runs.

## Capabilities

### New Capabilities

- `scientist-scenario-catalog`: Browse, filter, export, archive, and restore scientist-generated scenarios while preserving their originating evidence.

### Modified Capabilities

- `dataset-case-execution`: Exclude archived scientist-generated scenarios from history supplied to subsequent scientist iterations.

## Impact

- Adds API endpoints and generated web contract types for the scenario catalog, archive state, and JSON export.
- Adds a confined operational archive index alongside `.gamr` run bundles while leaving completed bundles unchanged.
- Extends artifact access used by the shared engine so CLI and API execution honor the same archive decisions.
- Adds the task-details Scenarios tab, catalog UI, and focused adapter, engine, API, and browser tests; it does not add a separate primary-navigation entry.
- Updates task-format and scoped architecture documentation; no new external dependencies are required.
