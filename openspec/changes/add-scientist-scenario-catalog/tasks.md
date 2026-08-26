## 1. Catalog and Archive Adapter

- [ ] 1.1 Add failing adapter tests for scenario discovery, canonical model validation, origin/result joins, pending and unavailable states, verdict filtering, newest-run ordering, and duplicate scenario IDs across runs.
- [ ] 1.2 Add failing security tests for invalid identifiers, path escapes, malformed source and marker JSON, exact export bytes, and proof that catalog reads never modify run bundles.
- [ ] 1.3 Add failing archive tests for atomic idempotent archive and restore, per-run identity, restart persistence, and marker cleanup during explicit run deletion.
- [ ] 1.4 Implement the confined scientist-scenario catalog and per-entry archive marker store with the smallest interfaces needed to pass the adapter tests.
- [ ] 1.5 Run the focused adapter suite and keep new source files below 300 lines.

## 2. Scientist History Integration

- [ ] 2.1 Add failing engine tests proving archived generated scenarios are excluded from configured prior-run history and explicit scientist resume while authored base cases remain eligible.
- [ ] 2.2 Add failing engine tests for archive and restore between active-run iterations, preservation of duplicate-prevention IDs, and `scientist.history_used` containing only effective prompt history.
- [ ] 2.3 Extend the artifact port and scientist case-record origin data, then filter archive state immediately before each scientist prompt without cancelling current execution or model work.
- [ ] 2.4 Update relevant fake artifact stores and run the focused engine and resume-scientist suites.

## 3. API Contract

- [ ] 3.1 Add failing API tests for active and archived listing, every supported result filter, full scenario and origin/result fields, deterministic ordering, and safe not-found responses.
- [ ] 3.2 Add failing API tests for idempotent archive and restore, immutable source bundles, canonical active and archived exports, content type, and safe attachment filenames.
- [ ] 3.3 Implement thin scientist-scenario routes and response models over the adapter, register the router, and wire the shared artifact root and secrets consistently with existing run evidence.
- [ ] 3.4 Regenerate `schemas/openapi.json` and the generated web API contract, then run the focused API suite.

## 4. Web Catalog

- [ ] 4.1 Read `apps/web/UI-DESGIN-TOKEN.md`, then add failing user-behavior tests for navigation, default Active and separate Archived views, result filtering, loading/error/empty states, and origin-run navigation.
- [ ] 4.2 Add failing user-behavior tests for expanding the complete scenario definition, accessible archive explanation, archive/restore query refresh, and export availability in both views.
- [ ] 4.3 Implement the typed API client calls, `/scientist-scenarios` route, primary-navigation entry, catalog page, bounded scenario disclosures, actions, and token-based responsive styling.
- [ ] 4.4 Run the complete deterministic web suite and production web build, keeping component and style seams documented and source files below 300 lines.

## 5. Documentation and Verification

- [ ] 5.1 Update `docs/task-format.md` with the single-file export workflow and the requirement to add the exported path to the destination `task.json`.
- [ ] 5.2 Update the API, web, adapter, and engine scoped `AGENTS.md` source maps for the new routes, catalog seam, archive behavior, tests, and UI route.
- [ ] 5.3 Run schema validation, lint, type checking, focused package/API/web tests, and finally `uv run poe check`; fix every regression without running live Tyr, model-provider, approval, or Docker tests.
