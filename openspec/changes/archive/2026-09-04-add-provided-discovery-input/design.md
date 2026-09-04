## Context

See `proposal.md` for motivation and `specs/provided-discovery-input/spec.md` for observable behavior.

Experiment target selection currently always enters `ExperimentRunner._run_discovery`, asks the model to converse with Tyr, and selects the first `DiscoveryCandidate`. The candidate supplies `path`, `workspace`, `agent`, and `bridge_id` to template rendering and known-facts prompts. `ExperimentPresetConfig` is the shared persisted configuration used by CLI and API execution, and the web UI creates reusable Experiment Presets through the API.

The internal `DiscoveryCandidate` also carries bridge status and evidence turn identifiers. Those fields describe live discovery evidence and must not become operator-controlled input. Existing run bundles expose a presentation-oriented `discovery-result.json`, but that document is not a canonical input schema.

## Goals / Non-Goals

**Goals:**

- Keep CLI, API, and web execution on the existing shared engine path.
- Validate one complete provided target before execution and persist its resolved content.
- Make bypass, preflight, and fallback provenance explicit in events, prompts, and run evidence.
- Preserve existing behavior and stored records when no new configuration is present.
- Keep fallback bounded, read-only, and complete before any Scenario Execution starts.

**Non-Goals:**

- Partial discovery hints or merging provided and discovered fields.
- Multiple provided candidates or candidate selection policy.
- Verifying that the informational Task ID matches the selected Task.
- Accepting server filesystem paths through the API.
- Falling back after a Scenario has started or replaying Scenario operations.
- Reusing `discovery-result.json` as the input format.

## Decisions

### 1. Add a separate public discovery-input model

Add a strict core document model with `schemaVersion`, `kind`, `taskId`, and a nested candidate containing only `path`, `workspace`, `agent`, and `bridgeId`. Reuse the existing `/home` path confinement rule, require non-empty strings, and forbid extra fields at both document levels.

Add optional `discoveryInput` and `fallbackToDiscovery` fields to `ExperimentPresetConfig`. `fallbackToDiscovery` defaults to `false`, and model validation rejects it when `discoveryInput` is absent. The Task ID is validated only as a non-empty reference label; it is never compared with the loaded Task.

The engine converts the public candidate into its internal candidate representation with no evidence turn IDs. The provided document cannot set bridge status or claim live evidence.

Alternatives considered:

- Reusing `DiscoveryCandidate` would expose internal evidence and status fields to operators.
- Accepting a bare candidate would omit schema evolution and human Task context.
- Importing `discovery-result.json` would couple input to a lossy visualization artifact.

### 2. Persist content, not source locations

The CLI exposes `--discovery-input PATH`, reads the file before constructing the Experiment record, and stores the validated document in configuration. The CLI path is not persisted as an execution dependency.

The web form uses a local JSON file picker, parses the file in the browser, and sends the document in the existing JSON Experiment Preset request. The API remains authoritative for validation. No multipart endpoint or server-side path reader is added. The form keeps the selected filename only as transient presentation state and previews the Task ID and four candidate fields.

The Experiment Preset response and detail page expose the stored document so a researcher can verify what future runs will use. Starting a run copies the document through the existing configuration-copy path.

Alternatives considered:

- A multipart upload adds storage and cleanup without benefit for a small structured document.
- A server path supplied by the browser is deployment-dependent and creates a file-read boundary.
- Persisting only the CLI path makes runs depend on mutable external state.

### 3. Resolve a target before entering Scenario execution

Refactor target selection into three explicit paths while preserving the existing live-discovery implementation:

```text
no discoveryInput
    └─ live discovery ───────────────▶ selected target or blocked

discoveryInput + fallback disabled
    └─ provided target ──────────────▶ selected target

discoveryInput + fallback enabled
    └─ bounded read-only preflight
          ├─ confirmed ──────────────▶ provided target
          └─ unavailable/uncertain ──▶ fresh live discovery
```

Provided input without fallback performs no discovery model turn, Tyr discovery request, or preflight. It still follows normal Tyr initialization required by Scenario execution.

Fallback preflight uses the existing target, model, idempotency, transcript, and artifact plumbing with a dedicated prompt and a small fixed turn budget. It asks only whether the exact Bridge ID, workspace, agent, and path are reachable. Success requires an observed Tyr reply and an affirmative structured decision matching the supplied candidate. Timeout, malformed output, mismatch, refusal, or inability to confirm counts as unavailable and starts normal discovery in a fresh conversation. The preflight cannot execute a Scenario step or request an approval.

No Scenario task is created until target selection, including fallback, has completed. Fallback never occurs after Scenario execution begins because replay could duplicate actions and contaminate evidence.

Alternatives considered:

- Falling back on a Scenario failure is unsafe because operations may already have occurred.
- Silently validating every provided target defeats deterministic zero-discovery execution.
- Treating any preflight response as success would turn an unverified assertion into a confirmed fact.

### 4. Carry explicit target provenance

Represent target origin as a small closed value used by target selection, prompt construction, discovery-result writing, and presentation: `provided`, `live`, or `fallback-live`. Live discovery retains its current transcript-derived evidence. Provided targets use an empty evidence-turn list and are introduced to Scenario prompts as operator-provided facts rather than facts confirmed by discovery.

Keep the existing discovery lifecycle stage so run progress and grouped history remain compatible. Extend the persisted discovery result and API presentation with target origin and explicit details. A direct provided path emits a completed discovery-stage activity with the supplied fields but no conversation entries. Preflight activities and fallback transition are persisted in chronological order; only real model and Tyr interactions appear as turns.

Alternatives considered:

- Inferring provenance from an empty transcript is ambiguous for malformed or legacy bundles.
- Marking provided data as ordinary successful live discovery would fabricate confidence and evidence.

### 5. Preserve one authoritative validation path

Core models define document and configuration validity. The CLI may format validation errors and the web may provide immediate client feedback, but API and engine inputs are validated through the same core models. Generated JSON Schema, OpenAPI, and web API types derive from those models.

Tests should cover the observable contract at the lowest responsible layer: strict document validation in core; selection, bypass, preflight, fallback, prompt wording, and evidence provenance in engine; boundary loading in CLI/API; and file-selection and review behavior in web.

## Risks / Trade-offs

- [A supplied target can be stale when fallback is disabled] → Treat the document as the researcher's assertion, preserve deterministic behavior, and report the resulting Scenario failure without hidden discovery.
- [Fallback preflight adds model and Tyr latency] → Run it only behind the explicit option and keep its budget fixed and smaller than normal discovery.
- [A preflight can produce a false negative] → Treat uncertainty as unavailable and use the existing full discovery path, which is the safer opt-in behavior.
- [Provided paths and routing names may be sensitive] → Store and expose them under the repository's existing trusted-operator preset and run-bundle boundary; do not add browser-side persistence beyond form state.
- [Older binaries reject records containing new strict configuration fields] → Keep fields optional for forward migration and avoid rolling back to an older reader while new-format Presets or runs remain in its data root.

## Migration Plan

1. Add optional core models and readers before any surface writes the new fields.
2. Update engine selection and evidence handling while keeping absent-field behavior unchanged.
3. Add CLI and API writers, regenerate schemas and web API types, then expose the web form and review state.
4. Existing Presets and run bundles require no migration because both new configuration fields have compatible defaults.
5. Rollback is safe for data created without discovery input. Before reverting to an older strict reader, retain or export Presets and runs containing the new fields outside that reader's data root.
## UX/UI Design

### Experience

Researchers configuring an Experiment Preset who already know their target can skip live discovery. The primary flow: open the Run Experiment form, expand the Advanced panel, provide a discovery-input JSON document from the local machine, review the parsed candidate, optionally arm fallback, and continue to the Preset review page where the stored configuration is confirmed. Information hierarchy follows the existing form: Preset name, Task, Scenarios, action mode, limits, and a collapsed Advanced panel at the bottom so the optional provided-target configuration never competes with the primary path. The Advanced panel is extensible: each advanced option is an `.advanced-item` separated by a top divider, so future options slot in without new structure.

### Screens and interactions

- `/experiments/new` (ExperimentPage): bordered Advanced panel with a header disclosure ("Advanced" plus a live hint: "Discovery input: not provided / <filename> / invalid file"). The body holds the first advanced item, "Skip discovery · provide target", whose description lives in an (i) info-tip beside the section label. A compact dropzone accepts a local JSON file by click or drag-and-drop; the native input stays focusable inside the label. After a valid parse: success badge, candidate preview (Task ID in document, path, workspace, agent, bridgeId), the informational-Task-ID rule, a mismatch note when the document Task ID differs from the selected Task, and a "Fall back to live discovery" checkbox that only appears once a valid document is loaded (default off). Rejection states (unreadable, invalid JSON, missing/extra fields, unsupported version or kind, non-`/home` or traversing path) render beside the dropzone with a danger border. Remove resets all discovery-input state. On submit, Continue navigates to the Preset detail page.
- `/experiments/:id` (ExperimentDetailPage): Preset settings rows show "Discovery input: Provided target" or "None (live discovery)", a fallback-policy row ("Enabled (bounded read-only preflight)" / "Disabled (an unavailable target fails the Experiment)"), and a "Provided discovery input" review block with the stored candidate fields.
- `/runs/:id` (RunHistory via RunPage): the Discovery group header shows a neutral provenance text badge — "Provided target", "Discovered live", or "Provided target · fell back to discovery" — so origin never relies on color. Legacy runs without origin data show no badge.

### Responsive and accessible behavior

The panel and dropzone stack in one column below 720px following the shell's existing responsive rules. Keyboard flow: Advanced toggle (Enter/Space) → dropzone input (focusable, Enter/Space opens the file picker) → fallback checkbox → Continue; every control shows the shared `--focus-ring`. Semantics: disclosure uses `aria-expanded`/`aria-controls`, validation errors use `role="alert"`, the tooltip is the established `.info-tip` pattern, and the dropzone label is natively associated with its input. Colors use only design tokens (accent for the dragover state, danger for validation errors); no hard-coded values, no gradients. Transitions are brief and disabled under `prefers-reduced-motion`. Dropzone text is centered.

### Accepted mock

- Source: `apps/web/src/features/experiments/ExperimentPage.tsx`, `apps/web/src/features/experiments/ExperimentDetailPage.tsx`, `apps/web/src/features/runs/RunPage.tsx`, `apps/web/src/features/runs/RunHistory.tsx`, `apps/web/src/features/runs/RunHistoryGroup.tsx`
- Archived mock-only helpers: `openspec/changes/add-provided-discovery-input/mocks/web/mockDiscoveryInput.ts`, `mockTargetOrigin.ts`
- Styles retained in production because the Advanced panel, dropzone, review block, and provenance badge are real UI: `apps/web/src/styles/forms.css` (`.advanced-panel`, `.advanced-body`, `.advanced-item`, `.form-disclosure-toggle`, `.file-drop*`, `.discovery-preview*`, `.discovery-review`), `apps/web/src/styles/runs.css` (`.history-toggle-origin`)
- Archived fixtures: `openspec/changes/add-provided-discovery-input/mocks/web/mockDiscoveryInputFixtures/{valid-target,unsafe-path,incomplete,unsupported-version}.json`
- View: `uv run poe dev` (web on http://localhost:6688, API on 127.0.0.1:6687), then `/experiments/new`, `/experiments/<preset-id>` after Continue, and `/runs/<run-id>`
- Status: Accepted design retained. The production form parses and sends document content through the API, the detail page reads persisted configuration, and the history badge reads visualization provenance. Mock-only helpers and fixtures are archived under the change root.

## Implementation status

- Core, engine, CLI, API, and web behavior are implemented in the production paths above.
- Generated JSON Schema, OpenAPI, and TypeScript contracts are current.
- Focused tests cover strict validation, target selection, fallback behavior, persistence, evidence normalization, and web review.
- Repository-wide validation and browser smoke verification are complete.
