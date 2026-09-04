## 1. Core discovery-input contract

- [x] 1.1 Add failing core tests for valid discovery-input documents, missing and extra fields, unsupported versions and kinds, unsafe paths, informational Task ID mismatches, and fallback-without-input rejection.
- [x] 1.2 Add strict public discovery-input candidate and document models, expose them from `gamr_core`, and extend `ExperimentPresetConfig` with optional `discoveryInput` and default-false `fallbackToDiscovery` fields.
- [x] 1.3 Export a canonical discovery-input JSON Schema and update generated Experiment, run, and OpenAPI schemas without changing existing configuration defaults.

## 2. Shared engine target selection

- [x] 2.1 Add failing engine tests proving provided input bypasses discovery turns, absent input preserves live discovery, supplied values render into Scenarios, and provided facts are not described as live-discovered.
- [x] 2.2 Add explicit target-origin handling and a provided-target selection branch that converts only the four public candidate fields, creates no evidence turn IDs, and completes before Scenario tasks are scheduled.
- [x] 2.3 Add failing engine tests for fallback-disabled failures and fallback-enabled preflight success, mismatch, refusal, malformed output, timeout, and full-discovery failure, including the invariant that no Scenario starts before selection completes.
- [x] 2.4 Implement the bounded read-only preflight through existing target/model, idempotency, transcript, and artifact plumbing; use a fresh conversation for live discovery after any unavailable or uncertain result.
- [x] 2.5 Extend discovery result writing, activity evidence, normalized turns, API visualization, and Scenario prompt construction to preserve `provided`, `live`, and `fallback-live` provenance without fabricated interactions.

## 3. CLI input boundary

- [x] 3.1 Add failing CLI tests for `--discovery-input`, unreadable and malformed files, strict schema failures, persisted resolved content, the fallback option, and fallback rejection without input.
- [x] 3.2 Add the CLI discovery-input path and fallback options, validate the local file before creating the Experiment, and pass the resolved document through the shared configuration.
- [x] 3.3 Update CLI progress rendering to distinguish a directly provided target, preflight activity, and fallback to live discovery.

## 4. API and Preset persistence

- [x] 4.1 Add failing API and registry tests for creating, listing, retrieving, reloading, and starting Presets with discovery input; verify each run receives the stored document and unsupported server-path fields are rejected.
- [x] 4.2 Extend Experiment Preset request, response, run override, and persisted registry handling with discovery input and fallback while retaining compatibility with existing records.
- [x] 4.3 Extend run visualization response models and evidence loading so clients receive target origin and provided fields consistently for active and completed Experiments.

## 5. Web configuration and review

- [x] 5.1 Add failing web behavior tests for local JSON selection, malformed and schema-invalid feedback, candidate preview, fallback visibility and default, Preset request content, and stored-input review on the detail page.
- [x] 5.2 Add the optional discovery-input file picker and local preview to the Experiment Preset form, send parsed document content through the JSON API, and expose fallback only when valid input is selected.
- [x] 5.3 Display stored discovery input and fallback policy on the Experiment Preset detail page, and display provided versus live discovery provenance in Experiment history.
- [x] 5.4 Regenerate the TypeScript OpenAPI client and replace any temporary handwritten contract types with the generated definitions.

## 6. Documentation and verification

- [x] 6.1 Document the discovery-input format, CLI flags, web Preset behavior, informational Task ID semantics, trusted-operator storage boundary, and fallback limitation in the existing task-format and user-facing documentation.
- [x] 6.2 Run schema generation and the focused core, engine, CLI, API, and web test commands covering the changed contract; fix any generated-file or behavior mismatch.
- [x] 6.3 Start the API and web application, browser-drive Preset creation with a discovery-input file, review the stored target, start an Experiment with controlled fake dependencies, and verify the provided-target history path.
- [x] 6.4 Run `uv run poe check` and resolve all repository-wide lint, type, test, schema, and build failures before handoff.
