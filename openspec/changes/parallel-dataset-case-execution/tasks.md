## 1. Configuration Contract

- [x] 1.1 Add failing core tests for the `maxConcurrentCases` default, accepted values 1 through 5, rejected boundary and non-integer values, serialization, and loading old configuration documents without the field; run them and confirm the expected failures.
- [x] 1.2 Add `max_concurrent_cases` to the experiment configuration model with the `maxConcurrentCases` alias, default 5, and inclusive 1-through-5 validation; make the focused core tests pass.

## 2. Engine Concurrency and Isolation

- [x] 2.1 Add failing engine tests using controlled async gates to prove the configured concurrency bound, five-case overlap by default, serial behavior at 1, manifest-order results after out-of-order completion, case-level failure isolation, and cancellation of active and pending cases.
- [x] 2.2 Add failing engine tests proving each concurrent case starts an independent Tyr operation and replay state, while scientist generation waits for every base case and scientist scenarios remain serial.
- [x] 2.3 Extract the related discovery, conversation, base-case, and scientist orchestration from the oversized runner into focused engine modules, update the engine source map, keep source files below 300 lines, and preserve existing behavior under the current tests.
- [x] 2.4 Implement structured base-case tasks with a semaphore bounded by `maxConcurrentCases`, per-case conversation state, indexed result slots, handled case-error collection, and cancellation propagation; make the concurrency and isolation tests pass.
- [x] 2.5 Aggregate base records in selected dataset order before summaries, reporting, and scientist history, and keep resumed and normal scientist execution on the serial path.

## 3. Checkpoints and Evidence

- [x] 3.1 Add failing adapter tests for simultaneous per-case checkpoint updates, safe case-path confinement, legacy singleton checkpoint reads, monotonic unique activities, and parseable interleaved transcript and event JSONL.
- [x] 3.2 Add run-level and per-case checkpoint operations to the artifact port and filesystem adapter using atomic case-specific paths and existing redaction, splitting touched adapter source as needed to keep source files below 300 lines.
- [x] 3.3 Add failing API tests for multiple active case IDs, pending, active, assessing, and terminal case states, state preservation during unrelated case events, and browser redaction of protected checkpoint and operation metadata.
- [x] 3.4 Update live and bundle-backed case-state reduction and visualization DTOs so concurrent cases retain independent states and counts, splitting touched API route modules as needed to keep source files below 300 lines.

## 4. Operator Surfaces

- [x] 4.1 Add failing API tests for experiment creation and run overrides that default, preserve, and reject `maxConcurrentCases` values correctly.
- [x] 4.2 Add `maxConcurrentCases` to API experiment and run request models and configuration mapping; make the focused API tests pass.
- [x] 4.3 Add failing CLI tests for the default and `--max-concurrent-cases` values 1 through 5, including rejection outside the range.
- [x] 4.4 Add the bounded CLI option and pass it into the shared configuration, extracting touched command composition as needed to keep source files below 300 lines.
- [x] 4.5 Add failing web behavior tests for the default value, bounded operator input, request payload, stored experiment display, and simultaneous active and assessing case badges without a misleading single-case busy indicator.
- [x] 4.6 Add the web concurrency control and multi-case progress presentation, extracting touched components as needed to keep source files below 300 lines; make the focused web tests pass.

## 5. Contracts, Documentation, and Verification

- [x] 5.1 Add an opt-in, marker-gated live Tyr test that starts independent operations concurrently within one initialized MCP session; do not include it in default test execution or enable actions.
- [x] 5.2 Update architecture, scaffold, development, configuration, checkpoint-layout, and relevant module `AGENTS.md` documentation for bounded case concurrency and the new source seams.
- [x] 5.3 Regenerate experiment, run-result, and OpenAPI schemas plus the generated web client, and validate representative old and new JSON documents.
- [x] 5.4 Run the narrow core, engine, adapter, API, CLI, and web tests while iterating, then run `uv run poe check` and the complete deterministic web suite before handoff.
