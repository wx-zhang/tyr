## Context

See `proposal.md` for motivation and the delta specs for the behavior contract. Generated scenarios already exist as validated JSON at `runs/<run-id>/scientist-scenarios/<artifact-id>.json`. Their case outcomes live in `result.json`, while run identity, task, lifecycle, and timestamps live in `run.json`.

Those files are canonical evidence. The engine also reloads them as scientist history for configured prior runs and explicit resume. Archive state must therefore be an independent operational overlay that both the API process and CLI execution can observe without rewriting a bundle.

## Goals / Non-Goals

**Goals:**

- Derive one catalog entry per retained generated-scenario artifact and join it with its origin and result.
- Keep archive state reversible, concurrency-safe for independent entries, and outside canonical bundles.
- Apply archive decisions at the latest safe boundary before every scientist prompt.
- Reuse the canonical task-scenario JSON as the export format.
- Keep filesystem access confined and generated browser types synchronized with OpenAPI.

**Non-Goals:**

- Copying exports into `tasks/`, editing `task.json`, or resolving task-level ID conflicts.
- Bulk export, catalog pagination, text search, editing generated scenarios, or deduplicating similar scenarios.
- Changing authored task-case selection or deleting any run evidence through scenario archive actions.
- Cancelling an executing case or recalling an in-flight model request.

## Decisions

### Derive the catalog from run bundles

Add an adapter-owned scientist scenario catalog that scans retained run directories, validates each generated scenario, and joins it to validated run and result documents. It returns entries ordered by run creation time descending and artifact identifier ascending within a run. Invalid or unconfined artifacts are not catalog resources.

Each entry carries a URL-safe artifact identifier from the persisted filename, the canonical scenario model, run ID and task, run timestamps and state, archive metadata, and an optional case-result summary. A missing case result maps to `pending` for nonterminal runs and `unavailable` for terminal runs.

This avoids a rebuildable database or a duplicated scenario copy. A separate indexed catalog was rejected because it could drift from run deletion and would need backfill and repair behavior.

### Store one archive marker per scenario occurrence

Persist markers below `.gamr/scientist-scenario-archive/<run-id>/<artifact-id>.json`. Each validated marker records a schema version, run ID, artifact ID, original scenario ID, and archive timestamp. Archive writes use atomic replacement; restore removes only the marker. Missing marker directories mean every retained scenario is active, so no migration is needed.

Per-entry markers avoid lost updates caused by rewriting one shared archive index. The archive identity includes the originating run, so equal scenario IDs in different runs are independent. Run deletion removes that run's marker directory as part of the already-authorized destructive operation; catalog reads never perform cleanup or other writes.

Deleting or moving the source scenario was rejected because it would violate evidence retention and break history loading. Copying scenarios to an active library was rejected because archive and restore would then have to reconcile duplicate canonical data.

### Resolve resources before reading or mutating them

Catalog operations accept a validated run ID and artifact ID. They resolve those identifiers through the confined generated-scenario directory, validate the scenario document, and only then read export bytes or write an archive marker. Unknown, malformed, or escaping identifiers map to the existing safe not-found response.

Exports return the retained scenario file bytes with `application/json` and an attachment filename safely derived from the scenario ID. Catalog and result metadata are never injected into the file.

### Filter history immediately before each prompt

Extend the engine artifact port with an archive-state query. Add origin-run identity to scientist `CaseRecord` values loaded from prior runs and produced by the active run. Keep all records in memory, including archived ones, then build each iteration's effective history by removing records whose origin marker currently exists.

Filtering at prompt construction gives archive and restore actions effect on the next not-yet-started iteration, including within an active run. It also preserves restored records for later reuse and keeps archived scenario IDs in duplicate-prevention state. Authored base records have no scientist origin and are never filtered.

The existing `scientist.history_used` activity is emitted from the effective history so the log remains an exact trace of what the model received. Filtering only while prior results are loaded was rejected because a restore during a multi-iteration run could not take effect without reloading the run.

### Expose a thin REST resource

Add these endpoints under `/api/v1/scientist-scenarios`:

- `GET /?state=active|archived&result=<result>` lists the selected archive view, with active as the default. `result` accepts the four security verdicts plus `pending` and `unavailable`.
- `PUT /{run_id}/{artifact_id}/archive` idempotently creates the marker.
- `DELETE /{run_id}/{artifact_id}/archive` idempotently removes the marker.
- `GET /{run_id}/{artifact_id}/export` returns the canonical JSON attachment.

The list response includes the full scenario because the documents are bounded by the existing task schema and browsing requires all fields. V1 intentionally returns the complete filtered collection; the local catalog is small and this avoids premature pagination.

### Add an Active/Archived catalog page

Add a primary-navigation entry and `/scientist-scenarios` route. The page uses TanStack Query with archive state and result filter in the query key. Active is the initial tab. Each summary row shows scenario identity, task, run, result, and tags; an accessible disclosure renders the complete definition. The run link targets `/runs/<run-id>/cases/<scenario-id>`.

Archive and Restore mutations invalidate all scientist-catalog queries. Export uses the attachment endpoint directly and remains available in both tabs. An adjacent accessible information disclosure explains preservation, history exclusion, and restoration. Archive is reversible, so it does not require a destructive confirmation dialog.

## Risks / Trade-offs

- [A catalog request scans retained runs] → Keep V1 unpaginated and deterministic, reuse existing bounded JSON models, and rely on query caching; add pagination only when measured run counts require it.
- [Archive can race with prompt construction] → Define the boundary as the archive-state read immediately before prompt construction; already-started requests continue as specified.
- [A run can disappear between listing and an action] → Resolve the source again for every archive, restore, or export request and return safe not-found when absent.
- [Historical or manually edited scenario JSON can be malformed] → Validate before exposing it and never use malformed content to construct paths or archive markers.
- [A scenario ID may be unsafe as a filename] → Address resources by the already-confined artifact identifier and sanitize only the download filename.
- [Archive markers are operational rather than canonical data] → Preserve them on normal restart and rollback; keep their schema versioned and their absence backward compatible.

## Migration Plan

1. Add archive marker and catalog support with absence meaning active; existing run bundles require no rewrite or backfill.
2. Add engine archive checks, API routes, OpenAPI output, and the generated web contract.
3. Add the catalog UI and documentation after the contract is generated.
4. Roll back by removing the UI, routes, and engine checks. Existing marker files may remain inert and can be recognized again on redeploy; canonical runs are unaffected.
