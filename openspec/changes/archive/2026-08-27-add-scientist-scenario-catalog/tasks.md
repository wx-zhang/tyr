## 1. Catalog and Archive Adapter

- [x] 1.1 Add failing adapter tests for scenario discovery, canonical model validation, origin/result joins, pending and unavailable states, verdict filtering, newest-run ordering, and duplicate scenario IDs across runs.
- [x] 1.2 Add failing security tests for invalid identifiers, path escapes, malformed source and marker JSON, exact export bytes, and proof that catalog reads never modify run bundles.
- [x] 1.3 Add failing archive tests for atomic idempotent archive and restore, per-run identity, restart persistence, and marker cleanup during explicit run deletion.
- [x] 1.4 Implement the confined scientist-scenario catalog and per-entry archive marker store with the smallest interfaces needed to pass the adapter tests.
- [x] 1.5 Run the focused adapter suite and keep new source files below 300 lines.

## 2. Scientist History Integration

- [x] 2.1 Add failing engine tests proving archived generated scenarios are excluded from configured prior-run history and explicit scientist resume while authored base cases remain eligible.
- [x] 2.2 Add failing engine tests for archive and restore between active-run iterations, preservation of duplicate-prevention IDs, and `scientist.history_used` containing only effective prompt history.
- [x] 2.3 Extend the artifact port and scientist case-record origin data, then filter archive state immediately before each scientist prompt without cancelling current execution or model work.
- [x] 2.4 Update relevant fake artifact stores and run the focused engine and resume-scientist suites.

## 3. API Contract

- [x] 3.1 Add failing API tests for active and archived listing, every supported result filter, full scenario and origin/result fields, deterministic ordering, and safe not-found responses.
- [x] 3.2 Add failing API tests for idempotent archive and restore, immutable source bundles, canonical active and archived exports, content type, and safe attachment filenames.
- [x] 3.3 Implement thin scientist-scenario routes and response models over the adapter, register the router, and wire the shared artifact root and secrets consistently with existing run evidence.
- [x] 3.4 Regenerate `schemas/openapi.json` and the generated web API contract, then run the focused API suite.

## 4. Web Catalog

- [x] 4.1 Read `apps/web/UI-DESGIN-TOKEN.md`, then add failing user-behavior tests for opening task details, selecting the Scientist scenarios tab, absence of a standalone menu entry, the normal list-and-detail view, default Active and separate Archived views, result filtering, loading/error/empty states, and origin-run navigation.
- [x] 4.2 Add failing user-behavior tests for expanding the complete scenario definition, task-scoped entries, clear Active/Archived state, archive/restore query refresh, and export availability in both views.
- [x] 4.3 Implement the typed API client calls and task-details Scenarios tab or equivalent selection using the existing scientist-scenario catalog component, remove the standalone route and primary-navigation entry, and preserve the list-and-detail view, actions, and token-based responsive styling.
- [x] 4.4 Run the complete deterministic web suite and production web build, keeping the tab integration and style seams documented and source files below 300 lines.

## 5. Documentation and Verification

- [x] 5.1 Update `docs/task-format.md` with the single-file export workflow and the requirement to add the exported path to the destination `task.json`.
- [x] 5.2 Update the API, web, adapter, and engine scoped `AGENTS.md` source maps for the new API routes, catalog seam, archive behavior, task-details Scenarios tab, and tests.
- [x] 5.3 Run schema validation, lint, type checking, focused package/API/web tests, and finally `uv run poe check`; fix every regression without running live Tyr, model-provider, approval, or Docker tests.
