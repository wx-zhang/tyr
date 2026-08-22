## Context

See `proposal.md` for motivation and `specs/dataset-case-execution/spec.md` for the behavior contract. The engine currently performs discovery, every base case, and the scientist through one runner and one mutable Tyr conversation. Activity and transcript records already carry case IDs, and the visualization contract already exposes plural current case IDs, but the run has one overwrite-style checkpoint and its case-state reducer assumes mostly serial updates. The filesystem bundle remains the source of truth and must keep one process writing each run.

The affected orchestration currently lives in an oversized runner module. This change must use the new concurrency seam to separate related orchestration into focused source files that satisfy the repository's 300-line source-file limit instead of adding more logic to that module.

## Goals / Non-Goals

**Goals:**

- Bound active base-case tasks without limiting discovery or changing scientist iteration semantics.
- Make concurrent case execution independent at the Tyr conversation, transcript, evidence, progress, and checkpoint boundaries.
- Preserve deterministic aggregation and cancellation behavior.
- Keep CLI and API execution on the same engine path.
- Preserve compatibility when reading configurations and bundles created before this field existed.

**Non-Goals:**

- Parallelizing discovery or scientist-generated scenarios.
- Adding a distributed scheduler, process pool, broker, or database.
- Automatically approving actions or weakening per-action Tyr approval.
- Adding dataset-level dependency graphs or resource-lock declarations between cases.
- Resuming interrupted external calls automatically.

## Decisions

### Use bounded asynchronous tasks inside the shared engine

After discovery returns an immutable candidate, the engine creates one task per selected base case under a structured task group. A semaphore initialized from `maxConcurrentCases` bounds active case bodies. Each task writes its `CaseRecord` into a result slot matching the selected dataset order. The task group provides cancellation propagation, while handled case-level failures remain returned case outcomes rather than task exceptions.

This keeps the concurrency decision in the engine and makes CLI and service runs behave identically. A worker queue was considered, but it adds queue lifecycle and result-index bookkeeping without improving a per-run limit of five. Threads and processes were rejected because the workload is asynchronous I/O and they would violate the bundle's single-writer assumption.

### Start each base case with an independent Tyr conversation

Discovery continues through its existing conversation. Every base case receives a new conversation state with no inherited operation identifier or replay prefix. The discovered candidate is supplied through the rendered known-facts block, so a base case does not need to mutate the discovery operation. The initialized target gateway is shared, and the target port's behavioral contract permits concurrent requests that create separate Tyr operations.

Cloning the discovery operation identifier was rejected because simultaneous mutations of one Tyr operation would mix replies and operation continuity. Creating and initializing a separate MCP client per case was rejected as unnecessary connection overhead; it remains a fallback adapter strategy if live Tyr verification shows that one MCP session cannot host independent concurrent operations.

The scientist retains one serial conversation. For normal runs it may continue the discovery conversation, but it never receives a base case's operation or replay state. Resumed scientist runs keep their existing serial discovery and scientist flow.

### Store the concurrency limit in experiment configuration

`ExperimentConfig.max_concurrent_cases`, serialized as `maxConcurrentCases`, defaults to 5 and validates from 1 through 5 inclusive. CLI exposes `--max-concurrent-cases`; API experiment creation and run override DTOs accept the same field. The web form uses a bounded integer control initialized to 1 so new UI-created experiments begin serially unless the operator raises the limit. The value is persisted in experiment records, run records, and results through the existing configuration snapshot.

This is run configuration rather than a dataset default because it controls operator resource use, not scenario meaning. A global environment-only limit was rejected because operators need reproducible per-experiment settings. The hard maximum of five prevents a run configuration from bypassing the agreed resource bound.

### Separate run-level and per-case checkpoint state

The run-level `checkpoint.json` records the current coarse phase and terminal status. During the base-case phase, each case writes atomically to `checkpoints/cases/<safe-case-id>.json`. Discovery and scientist remain serial and may use phase-specific checkpoint files or the run-level checkpoint. Unique case paths prevent overlapping turns from replacing another case's state.

Checkpoint payloads identify the case, phase, turn, pending-call state, and safe operation continuity needed for diagnostics. Existing redaction rules continue to remove idempotency keys, credentials, and configured secrets. No browser endpoint returns protected checkpoint fields. Existing singleton checkpoints remain readable as legacy evidence.

A single map rewritten into `checkpoint.json` was rejected because every case completion would require locked read-modify-write behavior and one damaged update could obscure all active lanes.

### Reduce case state from case-aware activities

The activity log remains the canonical live history. The engine emits `case.queued` for selected cases waiting on the semaphore, then `case.started` after a slot is acquired. The API reducer seeds selected cases as pending and maps case and finding events to stable states: pending, queued, active, assessing, completed, failed, blocked, or cancelled. Communication and Tyr-operation events retain the current lifecycle state rather than replacing it with an incidental status. `currentCaseIds` continues to list every active or assessing case.

The web case list becomes the primary overview for parallel work and displays each active case's state independently. The run history is grouped by stage and case rather than presented as one flat list, so a busy indicator belongs to the group that owns the pending work; no global indicator may imply that only one case is active.

### Group run history by stage and case in the web view

The run page derives the grouping on the client from the existing turns, visualization, and collector-artifact responses; no new API shape is added. Grouping keys come from fields that already exist on `RunTurnResponse`: `stage` (one of `discovery`, `case`, `assessment`, `scientist`, or `unknown`), `caseId`, `updateType`, and `sequence`.

Bucketing rules, in this order:

1. `updateType === "discovery"` or `stage === "discovery"` → the discovery group, which owns no case entries.
2. `stage === "scientist"` → the iteration group. The iteration number comes from the existing scientist-generation turn (`isScientistGeneration`, whose `number` is the iteration); the existing `scientistIterationByCaseId` map already resolves a scientist case turn to its iteration. A scientist turn whose iteration cannot be resolved goes to the highest known iteration group, or to iteration 1 if none exists yet.
3. Any remaining turn with a `caseId` → the base-case group, under the entry for that `caseId`.
4. Anything left, including `stage === "unknown"` → an "Other updates" group rendered last, so no update is ever dropped.

Case entries in the base-case group come from `visualization.cases` sorted by `order`, which already includes not-yet-started cases as `pending`; turns attach to an existing entry by ID. A turn whose `caseId` is absent from that list appends an entry after the known ones rather than being discarded. Collector artifacts attach to the case entry matching `artifact.caseId`. Within a case, updates use ascending timestamp and sequence order so the expanded content reads as a historical audit timeline. Every entry keeps its original sequence and timestamp so the canonical global order remains reconstructible. The final entry is the latest activity for presentation purposes.

Groups remain open by default so phase progress and the case overview are visible. Every individual case starts collapsed, regardless of lifecycle state, because its summary row already exposes the current state, latest meaningful activity, busy indicator, and update count. Operator toggles live in one `Map<string, boolean>` in the history component keyed by group ID and `caseId`, and take precedence until the run view unmounts; incoming updates never overwrite an entry that the map already holds.

Lifecycle and security outcome remain separate header signals. A case with a verdict keeps its lifecycle badge and adds a result badge: `Vulnerability Exposed` for a vulnerable result or `No breach` for a protected result. The header uses the case visualization verdict when available and otherwise the latest evaluation update, avoiding a live-refresh gap. This lets a reviewer scan collapsed cases without confusing execution completion with the assessment outcome.

The base-case overview filters out every case ID resolved to a scientist iteration before deriving entries, counts, or aggregate state. Scientist cases use the same visualization progress record only inside their iteration group. This prevents a generated case from appearing twice or keeping the base `Test cases` stage in progress.

Because the base-case group now shows every selected case with its state and count, the duplicate `CaseList` inside the Stage panel is removed; the Stage strip itself is unchanged. The test-case group header adds a token-based progress track beside explicit completed and total case text. The pagination control (`Load N earlier updates`) and the persisted-count line stay in the section header, and grouping applies to whatever turns are currently loaded.

Each case summary row carries the case order, identifier, state badge, update count, and the latest meaningful activity summary. This makes a collapsed terminal case useful without rendering its history. Pending cases say they are waiting to be initialized, queued cases say they are waiting for an execution slot, and active or assessing cases retain a labeled live indicator. Missing legacy state is presented as `Status unavailable`, never `Unknown`.

Group status comes from lifecycle progress, not the terminal-looking status of the latest nested turn. In particular, the discovery group consumes the `discovering` phase state and remains `In progress` until that phase is terminal. The test-case group derives its state from all owned case states, so one completed case or activity cannot mark the whole group complete.

Expanded case activity uses one chronological timeline rather than a stack of equally prominent cards. Each turn remains a semantic list item and gains a button-based activity header containing its activity label, status, timestamp or duration, a one-line redacted summary, and `Latest` or `Current` text when applicable. The current or final activity opens by default. Older completed turns default closed and render no detail DOM until opened. Each activity keeps local operator-controlled disclosure state so incoming updates do not reopen an older item. Collector artifacts remain chronological evidence entries and use their existing bounded preview disclosure.

A newest-first activity list was rejected because it makes multi-step evidence read backward and duplicates the role of the collapsed latest-activity summary. Expanding every activity was rejected because parallel runs become visually noisy and render evidence the reviewer has not requested. A chronological/grouped mode switch remains unnecessary because the run-level evidence views preserve global interleaving while each case timeline optimizes for causal reading.

The grouping function's shape, so the component does no bucketing of its own:

```ts
type HistoryUpdate =
  | { kind: "turn"; sequence: number; turn: RunTurn }
  | { kind: "artifact"; sequence: number; artifact: CollectorArtifact };

type HistoryCaseEntry = {
  caseId: string;
  progress: CaseProgress | undefined;
  updates: HistoryUpdate[];
};

type HistoryGroup = {
  id: "discovery" | "cases" | "other" | `iteration-${number}`;
  label: string;
  updates: HistoryUpdate[];
  cases: HistoryCaseEntry[];
  state: string;
  isTerminal: boolean;
  isBusy: boolean;
};

function groupRunHistory(input: {
  turns: RunTurn[];
  cases: CaseProgress[];
  artifacts: CollectorArtifact[];
  phases?: ProgressItem[];
}): HistoryGroup[];
```

Groups are returned in render order: discovery, cases, each iteration ascending, then other. A group is omitted when it has no updates and no cases, so a run without scientist iterations shows no iteration group. Each group exposes an explicit lifecycle `state`; `isBusy` and `isTerminal` are derived from that state and its owned work.

Deriving the tree server-side into a new grouped DTO was rejected: the grouping is presentation, the activity log stays canonical, and a client-side reduction avoids a second source of truth for case state. Keeping a chronological/grouped toggle was rejected as redundant once every entry still shows its sequence.

### Fix the markup, class names, and tokens for the grouped history

The run page module is far above the 300-line limit, so this work splits it. Files under `apps/web/src/features/runs/`:

| File                  | Responsibility                                                                            |
| --------------------- | ----------------------------------------------------------------------------------------- |
| `runHistoryGroups.ts` | Pure grouping function and its types. No JSX, no hooks.                                   |
| `RunHistory.tsx`      | The `<section>`, heading, pagination, empty state, and group loop.                        |
| `RunHistoryGroup.tsx` | One collapsible group: header row plus children.                                          |
| `RunHistoryCase.tsx`  | One collapsible case entry: summary row plus its updates.                                 |
| `RunTurnCard.tsx`     | One turn disclosure: compact activity header plus conditionally rendered evidence detail. |

Disclosure uses an explicit `<button aria-expanded aria-controls>` plus conditionally rendered content, not `<details>`. Expansion is derived state with an operator override, and a controlled `<details open>` in React fights its own native toggle; the button form keeps expansion in one place and is directly assertable. The existing `<details>` usages elsewhere on the page are left alone.

DOM contract, which the tests assert against:

```html
<section class="run-history" aria-labelledby="history-title">
  <div class="section-heading">
    <h2 id="history-title">Run history</h2>
    <span class="turn-count mono">42 updates persisted</span>
  </div>

  <div class="history-group history-group-discovery is-open">
    <h3 class="history-group-heading">
      <button
        class="history-toggle"
        aria-expanded="true"
        aria-controls="history-discovery"
      >
        <span class="history-toggle-label">Discovery</span>
        <span class="history-toggle-status"><!-- StatusBadge --></span>
        <span class="history-toggle-count mono">4</span>
      </button>
    </h3>
    <div class="history-group-body" id="history-discovery">
      <ol class="turn-list" aria-label="Discovery updates">
        <!-- .turn cards -->
      </ol>
    </div>
  </div>

  <div class="history-group history-group-cases is-open">
    <h3 class="history-group-heading">
      <button
        class="history-toggle"
        aria-expanded="true"
        aria-controls="history-cases"
      >
        <span class="history-toggle-label">Test cases</span>
        <span class="history-toggle-count">2 of 5 cases complete</span>
      </button>
    </h3>
    <div class="history-group-body" id="history-cases">
      <ul class="history-case-list" aria-label="Test cases">
        <li class="history-case is-open">
          <h4 class="history-case-heading">
            <button
              class="history-toggle history-case-toggle"
              aria-expanded="true"
              aria-controls="history-case-case-alpha"
            >
              <span class="history-case-number">Case 01</span>
              <span class="history-case-summary">
                <span class="history-case-id mono">case-alpha</span>
                <span class="history-case-description"
                  >Latest activity summary</span
                >
              </span>
              <span class="history-case-status"><!-- StatusBadge --></span>
              <span class="history-toggle-count">6 updates</span>
            </button>
          </h4>
          <div class="history-case-body" id="history-case-case-alpha">
            <ol class="turn-list" aria-label="Updates for case-alpha">
              <li class="turn history-activity is-latest is-open">
                <button
                  class="history-activity-toggle"
                  aria-expanded="true"
                  aria-controls="history-activity-turn-6"
                >
                  <span class="history-activity-title">Evaluation result</span>
                  <span class="history-activity-summary"
                    >No breach recorded</span
                  >
                  <span class="history-activity-latest">Latest</span>
                  <span class="history-activity-time mono">12:03:00</span>
                </button>
                <div id="history-activity-turn-6">
                  <!-- existing evidence detail -->
                </div>
              </li>
            </ol>
          </div>
        </li>
      </ul>
    </div>
  </div>
</section>
```

Rules that bind the markup:

- `StatusBadge`, `.turn-count`, `.section-heading`, `.empty-state run-empty`, and the pagination button are reused. Existing turn evidence content remains intact inside the new activity disclosure.
- Group IDs are `discovery`, `cases`, `iteration-<n>`, `other`. `aria-controls` values are `history-<groupId>` and `history-case-<caseId>`, with the case ID passed through the same safe-slug helper used for DOM IDs.
- Group labels remain `Discovery`, `Test cases`, `Iteration <n>`, and `Other updates`; case update lists are named `Updates for <caseId>`.
- A collapsed group or case renders no update DOM at all, which is what keeps a long run cheap to render.
- A collapsed activity renders its summary header but no evidence-detail DOM. Its button exposes `aria-expanded` and `aria-controls`.
- The pending, active, assessing, and terminal case badge comes from the existing `caseStatus` helper, so badge labels and tones stay identical to the current case list.
- The busy spinner (`.tyr-waiting-spinner`) appears in the header of the group or case that owns the pending work. No global working indicator remains in this section.

Styling contract, all values from `src/tokens.css`, added to `src/styles/runs.css`:

| Element                         | Style                                                                                                                                                                                                                                                                       |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.run-history`                  | `display: grid; gap: var(--space-3)`                                                                                                                                                                                                                                        |
| `.history-group`                | `border: var(--border-w) solid var(--border); border-radius: var(--radius-md); background: var(--surface); overflow: hidden`                                                                                                                                                |
| `.history-toggle`               | full-width flex row, `gap: var(--space-2)`, `min-height: var(--row-h)`, `padding: var(--space-2) var(--space-3)`, `border: 0`, `background: var(--bg-subtle)`, `color: var(--text)`, `font-size: var(--text-sm)`, `font-weight: 600`, `cursor: pointer`, `text-align: left` |
| `.history-toggle:hover`         | `background: var(--surface-hover)`                                                                                                                                                                                                                                          |
| `.history-toggle:focus-visible` | `outline: none; box-shadow: var(--focus-ring)`                                                                                                                                                                                                                              |
| `.history-toggle::before`       | `content: "▸"`, `width: 0.55em`, `font-size: var(--text-2xs)`, `color: var(--text-muted)`, `transition: transform var(--duration-fast) var(--ease-out)`; the open state rotates it 90deg, matching `.case-list-summary::before`                                             |
| `.history-toggle-count`         | `margin-left: auto`, `font-size: var(--text-xs)`, `color: var(--text-muted)`, `font-variant-numeric: tabular-nums`                                                                                                                                                          |
| `.history-group-body`           | one top border; group updates receive `var(--space-4)` padding while the case list stays edge-to-edge                                                                                                                                                                       |
| `.history-case-list`            | `display: grid; gap: 0; margin: 0; padding: 0; list-style: none`                                                                                                                                                                                                            |
| `.history-case`                 | `border-top: var(--border-w) solid var(--border)`; first child has none                                                                                                                                                                                                     |
| `.history-case-toggle`          | full-width summary grid with case number, identifier and summary, state, busy indicator, and labeled update count                                                                                                                                                           |
| `.history-case-body`            | a subtle secondary surface with an activity label and token-based spacing around the chronological list                                                                                                                                                                     |
| `.history-activity`             | compact bordered timeline row; the latest or current item uses a semantic status rail and visible text label                                                                                                                                                                |
| `.history-activity-toggle`      | full-width grid with activity title, one-line summary, status, and time; it keeps the shared focus ring and minimum target height                                                                                                                                           |
| `.history-activity-body`        | existing evidence layout, separated from the summary by one token border and rendered only while expanded                                                                                                                                                                   |

Nesting stops at the activity disclosure (group → case → activity). The activity rail is visual alignment, not additional content indentation. No new colors, shadows, radii, font sizes, or spacing values are introduced, and no hard-coded hex or pixel value is added.

Responsive rules go in `src/styles/responsive.css` under the existing `max-width: 720px` block: case and activity grids stack their metadata below the primary summary, secondary summaries ellipsize without hiding status text, and every toggle keeps at least the design system's preferred control height. The existing global `prefers-reduced-motion` block neutralizes disclosure transitions, so no extra motion handling is needed.

### Preserve deterministic scientist history and results

Concurrent completion order affects activity sequence and timestamps only. Base `CaseRecord` and `CaseResult` collections are reconstructed in selected dataset order before summary calculation, result writing, reporting, and scientist history construction. Scientist generation starts only after the task group exits successfully and then proceeds one iteration at a time.

Sorting terminal results by completion time was rejected because it would make repeated runs nondeterministic and would change the manifest-order contract used by history and reporting.

### Keep concurrency safe across adapters

The model, Tyr, and collector adapters use their existing asynchronous clients. Concurrent calls may share those clients, but no mutable case conversation state lives in an adapter singleton. Artifact JSONL appends and activity sequence assignment remain synchronous operations on the event-loop thread; per-case checkpoint and result artifacts use unique atomic paths. Tests will verify unique, monotonic activity sequences and parseable JSONL under deliberately interleaved cases.

## Risks / Trade-offs

- [Tyr may serialize or reject concurrent operations within one MCP session] → Add an opt-in live integration check for independent operations and retain a gateway-pool fallback without changing the engine contract.
- [Parallel action-enabled cases can present several approvals and mutate the same remote workspace concurrently] → Keep the limit at five, display every active case, preserve independent approvals, and document that datasets are responsible for using non-conflicting artifact names.
- [Shared provider rate limits may increase transient failures] → Bound concurrency at five and preserve existing retry and case-level error behavior; operators can select a lower value down to one.
- [Interleaved evidence is harder to read] → Retain global chronological sequence while attaching case IDs to every case-scoped record and showing per-case state in the overview.
- [An unexpected task exception cancels sibling work] → Treat expected provider and assessment failures as case results; reserve structured cancellation for invariant violations and explicit run cancellation.
- [Old binaries reject new persisted configuration fields because models forbid extras] → Avoid eager rewrites and use the migration and rollback sequence below.
- [Grouping hides cross-case interleaving that helps diagnose contention] → Keep activity sequence and timestamp on every entry, order groups by first activity, and keep the run-level evidence views unchanged for raw chronological review.

## Migration Plan

1. Add the optional-defaulted configuration field and reader compatibility before any surface writes it.
2. Add engine scheduling, isolated conversations, per-case checkpoints, and concurrent evidence tests.
3. Add API and CLI surfaces, regenerate JSON and OpenAPI schemas, then add the web control and regenerated client.
4. Update run visualization and documentation before enabling the new default in released entry points.
5. Validate old fixtures without `maxConcurrentCases`; they resolve to the default value of 5 without rewriting canonical bundles.

Rollback must use a compatibility build that accepts and ignores `maxConcurrentCases` before deploying an older binary. Completed run bundles remain immutable; mutable experiment and unfinished run documents must not be rewritten solely for rollback.
