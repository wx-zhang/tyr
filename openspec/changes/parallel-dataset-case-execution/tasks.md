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

## 6. Grouped Run History Presentation

Read the design's "Group run history by stage and case in the web view" and "Fix the markup, class names, and tokens for the grouped history" decisions before starting. The DOM contract, class names, group IDs, accessible names, and CSS token values are fixed there; do not invent alternatives.

- [x] 6.1 Add failing unit tests for `apps/web/src/features/runs/runHistoryGroups.ts` covering the four bucketing rules: discovery by `updateType`/`stage`, scientist turns to their resolved iteration group, remaining `caseId` turns to the base-case group, and `unknown`-stage turns to a trailing "Other updates" group. Assert case entries follow `visualization.cases` `order` including not-yet-started pending cases, that an unrecognized `caseId` appends an entry instead of being dropped, that collector artifacts attach by `caseId`, and that updates within a case are in descending `sequence` order.
- [x] 6.2 Write `runHistoryGroups.ts` as a pure function with no JSX and no hooks; make the 6.1 tests pass.
- [x] 6.3 Add failing `RunHistory` component tests asserting the design's DOM contract by role and accessible name: a `Discovery` toggle with `aria-expanded="true"` during discovery while each pending case toggle is `aria-expanded="false"` and renders no update DOM; two concurrently active cases each exposing their own `Updates for <caseId>` list, badge, and count; an `Iteration 1` group containing its generation update and generated case entries with the base-case group unchanged; a terminal case collapsed to its summary row with outcome badge and count while active cases stay expanded; a `.tyr-waiting-spinner` in the owning group or case header and none at section level; and clicking a toggle overriding the derived default so later prop updates do not reverse it.
- [x] 6.4 Create `RunHistory.tsx`, `RunHistoryGroup.tsx`, and `RunHistoryCase.tsx` using the design's button-based disclosure (`aria-expanded` plus `aria-controls`, no `<details>`), reusing `.turn` cards, `StatusBadge`, `caseStatus`, `.turn-count`, `.section-heading`, and the existing empty state and pagination control; make the 6.3 tests pass.
- [x] 6.5 Move the existing `Turn` component and its helpers unchanged into `RunTurnCard.tsx`, delete the flat `Run updates` list and the now-duplicate `CaseList` from the Stage panel, and split `RunPage.tsx` and `RunPage.test.tsx` so every touched source file is below 300 lines.
- [x] 6.6 Add the `.run-history`, `.history-group`, `.history-toggle`, `.history-case`, and related rules to `src/styles/runs.css` using only the token values listed in the design, plus the `max-width: 720px` rules in `src/styles/responsive.css`; add no new hex, pixel, radius, or font-size values beyond the existing 3px rail.
- [x] 6.7 Update the `apps/web` `AGENTS.md` file map with the new run-feature files, and correct `docs/architecture.md` and any run-visualization documentation that still describes a flat update list.
- [x] 6.8 Run the focused web tests, then `uv run poe check` and the complete deterministic web suite.
- [x] 6.9 Verify in a browser at desktop and 375px-wide mobile viewports, against both a live run and a completed run: expand and collapse discovery, a case, and an iteration group; confirm updates appear under the owning case, that a live run auto-expands active work, that an operator toggle survives incoming updates, and that the empty and pagination states still render. Fix and re-verify anything broken.

## 7. Case Progress and Activity Timeline Refinement

- [x] 7.1 Add failing grouping and component tests for oldest-to-newest case activity, explicit completed and total case progress, latest activity summaries in collapsed case rows, compact older activities, an expanded latest or current activity, activity-level operator overrides, and empty activity states.
- [x] 7.2 Change grouped case updates to ascending historical order and derive safe latest-activity presentation data without changing persisted sequence or timestamps; make the focused grouping tests pass.
- [x] 7.3 Refine the test-case progress header, case summary rows, and turn activity disclosures using existing design tokens, button disclosure semantics, bounded evidence rendering, and responsive layouts; make the focused component tests pass.
- [x] 7.4 Update the web module instructions and run-visualization documentation for chronological case timelines and activity disclosure, then run formatting, focused web tests, lint, build, `uv run poe check`, and the complete deterministic web suite.

## 8. Precise Lifecycle Progress

- [x] 8.1 Add failing engine, API, grouping, and component regressions for queued capacity, lifecycle-preserving intermediate activity, discovery phase completion, and explicit case labels.
- [x] 8.2 Emit queued case activity and reduce live and bundle case progress only from lifecycle-bearing case and finding events.
- [x] 8.3 Derive group status from lifecycle phases and owned case states, and present not-started, queued, running, assessing, and unavailable cases clearly in collapsed rows.
- [x] 8.4 Update the OpenSpec behavior, design contract, architecture, module instructions, and UI content guidance, then run focused and full verification.

## 9. Collapsed Case Defaults

- [x] 9.1 Add failing component regressions proving active and assessing cases enter collapsed while operator expansion survives incoming updates.
- [x] 9.2 Default every case disclosure to collapsed, preserve the open test-case group and summary-row progress, and update the behavior and design documentation.
- [x] 9.3 Add a failing collapsed-header regression for separate lifecycle and vulnerability-result badges.
- [x] 9.4 Show `Vulnerability Exposed` or `No breach` beside the lifecycle status when a verdict is available.

## 10. Conservative Web Concurrency Default

- [x] 10.1 Add a failing web form regression for an initial `maxConcurrentCases` value of 1 and its submitted request payload.
- [x] 10.2 Initialize the web concurrency control to 1 while retaining the shared configuration compatibility default of 5.

## 11. Scientist Ownership and Live Verdicts

- [x] 11.1 Add failing grouping and component regressions for scientist-only iteration ownership and evaluation-verdict fallback in collapsed headers.
- [x] 11.2 Exclude scientist-generated case IDs from the base test-case group and derive result badges from the latest evaluation update until visualization catches up.
