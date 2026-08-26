# GAMR UI Design Tokens and System

This document is the visual and interaction contract for GAMR's optional web interface: tasks, experiment execution starts, run visualization, case transcripts, findings, and evidence artifacts.

GAMR is the red-team product **for Tyr** ([tyr.ai](https://tyr.ai/)). Branding should always make that relationship clear: the product name is **GAMR**, the logo tagline is **Tyr's final opponent**, and the shell links out to Tyr. Reuse the Tyr spear monogram as a co-brand mark, not as a replacement for the GAMR identity.

The intended character is a **calm evidence console**: precise enough for operators, readable enough for reviewers, and restrained enough that live state, risk, and approval requests receive attention when they matter.

## 1. Authority and scope

- This file is the canonical UI standard for `apps/web`.
- It governs new UI and material changes to existing UI. Do not restyle unrelated screens as a side effect of a focused change.
- Product safety rules in the root instructions and `docs/SCAFFOLD_SPEC.md` take precedence over visual guidance.
- The generated API contract remains the source of truth for data shapes and enums. UI labels may clarify a value but must not invent workflow state.
- Keep tokens in plain CSS custom properties. GAMR currently uses plain CSS; do not add a CSS framework, CSS-in-JS library, or duplicate theme mapping just to implement these tokens.

## 2. Design principles

1. **Evidence comes first.** Optimize for scanning run state, case progress, approvals, findings, transcripts, and raw evidence. Decoration must not compete with evidence.
2. **Safety is explicit.** Read-only and `approval_required` modes, pending human decisions, destructive actions, and the presence of sensitive test evidence must be stated in words. Color is supporting information only.
3. **Color has one job at a time.** Most of the UI is neutral. Blue identifies interaction or live progress, amber identifies attention or approval, red identifies failure or danger, and green identifies a completed successful state.
4. **Borders before shadows.** Separate regions with spacing, surface steps, and one-pixel borders. Use shadows only for floating elements such as dialogs and menus.
5. **Sans is human; mono is machine.** Use sans-serif for navigation, prose, labels, and decisions. Use monospace for IDs, timestamps, metrics, enum values, tool names, arguments, logs, diffs, and artifact paths.
6. **Dense, never cramped.** Use a 4px spacing grid, compact controls, and generous line height for transcripts and long descriptions.
7. **Motion communicates state.** Motion may indicate streaming, polling, or a state transition. It must be brief, subtle, and removable.
8. **Both themes are complete.** Follow the operating-system theme on first visit and persist an explicit user choice. Neither theme is a secondary implementation.
9. **Accessibility is part of the component contract.** Meet WCAG 2.2 AA, preserve native semantics, expose focus, support keyboard use, announce asynchronous state, and honor reduced motion.
10. **A transcript is not chat.** Run and case history is an audit-oriented, chronological record. Do not use speech bubbles, avatars, or conversational decoration.

## 3. Information architecture and layout

### Application shell

The shell supports the routes defined by the scaffold:

- Run dashboard
- Tasks
- New and saved experiments
- Run overview
- Case transcript and evidence
- Artifacts and reports

Use a persistent left navigation rail for product identity, workspace routes, local API health, current context, Tyr attribution, and theme control. Product identity is **GAMR** with the secondary line **Tyr's final opponent**; the rail footer links to [tyr.ai](https://tyr.ai/) with the Tyr monogram. The expanded rail is 192px; its hide control collapses it to a 56px icon rail and persists that choice in `localStorage`. On narrow screens it becomes a compact top rail with horizontally scrollable navigation. The contextual header belongs to the content frame, stays quiet, and may use “Red team for Tyr” as the eyebrow. A run page may add local tabs for Overview, Cases, and Artifacts. Approval observations from CLI runs remain visible in the activity view.

### Width and density

```css
:root {
  --shell-header-h: 52px;
  --content-max: 1200px;
  --reading-max: 840px;
  --inspector-w: 320px;
  --sidebar-w: 192px;
  --sidebar-collapsed-w: 56px;
  --row-h: 36px;
  --control-h: 36px;

  --space-0-5: 2px;
  --space-1: 4px;
  --space-1-5: 6px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;
}
```

- Standard pages use `--content-max`; tables and timelines may use the full available width inside it.
- Long machine strings (IDs, hashes, encoded payloads, paths) wrap inside their container. Tables may scroll horizontally inside the card; they must not widen the page.
- Transcript prose and long evidence descriptions use `--reading-max` for readable line length.
- Keep the primary task and its supporting context visible together on wide screens. An optional inspector is `--inspector-w`.
- Below 720px, move the left rail into a compact top rail, use one column, allow tables to scroll horizontally, and keep actions close to the content they affect. Never reduce important data to icon-only controls.
- Compact choice cards (`.choice-card-compact`) may be used for inline risk flags or secondary approvals where a smaller visual footprint is preferred.
- Compact table rows may be 36–40px. Transcript entries and approval cards grow to fit their content.
- Prefer section dividers and headings to wrapping every section in a card.

## 4. Typography

GAMR must not depend on a remote font request. Use system fonts now. A future self-hosted font may be placed first in these stacks without changing component styles.

```css
:root {
  --font-sans:
    ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono:
    ui-monospace, "SFMono-Regular", Consolas, "Liberation Mono", monospace;

  --text-2xs: 0.6875rem;
  --leading-2xs: 1rem;
  --text-xs: 0.75rem;
  --leading-xs: 1rem;
  --text-sm: 0.8125rem;
  --leading-sm: 1.125rem;
  --text-base: 0.875rem;
  --leading-base: 1.25rem;
  --text-md: 0.9375rem;
  --leading-md: 1.375rem;
  --text-lg: 1.0625rem;
  --leading-lg: 1.5rem;
  --text-xl: 1.25rem;
  --leading-xl: 1.75rem;
  --text-2xl: 1.5rem;
  --leading-2xl: 2rem;
  --text-display: 1.875rem;
  --leading-display: 2.25rem;
  --text-code: 0.78125rem;
  --leading-code: 1.25rem;
}
```

- Use weight 400 for body text, 500 for labels and buttons, and 600 for headings. Reserve 700 for the GAMR wordmark or a rare key metric.
- Page titles normally use `--text-xl`; `--text-2xl` is for a run summary or dashboard count, not every screen.
- Uppercase micro-labels use `letter-spacing: 0.06em`. Do not uppercase sentences, button labels, findings, or approval text.
- IDs, counts, latencies, token counts, and timestamps use `font-variant-numeric: tabular-nums`.
- Never reduce essential metadata below 12px. `--text-2xs` is only for short badges and eyebrow labels.

## 5. Color tokens

The palette is deliberately neutral. Signal blue is the interaction accent so red remains unambiguous for dangerous or failed states.

### Light theme

```css
:root,
[data-theme="light"] {
  color-scheme: light;

  --bg: #f6f8fa;
  --bg-subtle: #eef2f6;
  --surface: #ffffff;
  --surface-hover: #f2f5f8;
  --surface-elevated: #ffffff;
  --backdrop: rgb(23 32 42 / 56%);

  --border: #d8e0e8;
  --border-strong: #b9c5d1;
  --border-focus: #1d4ed8;

  --text: #17202a;
  --text-secondary: #455465;
  --text-muted: #607184;
  --text-disabled: #9aa7b4;

  --accent: #1d4ed8;
  --accent-hover: #1e40af;
  --accent-active: #1e3a8a;
  --accent-tint: rgb(29 78 216 / 10%);
  --accent-on: #ffffff;

  --success: #157a3d;
  --success-tint: rgb(21 122 61 / 10%);
  --info: #1d4ed8;
  --info-tint: rgb(29 78 216 / 10%);
  --warning: #b54708;
  --warning-tint: rgb(181 71 8 / 12%);
  --danger: #b42334;
  --danger-tint: rgb(180 35 52 / 10%);
  --neutral-status: #607184;
  --neutral-status-tint: rgb(96 113 132 / 11%);

  --shadow-sm: 0 1px 2px rgb(23 32 42 / 8%);
  --shadow-md: 0 8px 24px rgb(23 32 42 / 14%);
}
```

### Dark theme

```css
[data-theme="dark"] {
  color-scheme: dark;

  --bg: #0b0f14;
  --bg-subtle: #10161d;
  --surface: #151c24;
  --surface-hover: #1b2530;
  --surface-elevated: #202a36;
  --backdrop: rgb(0 0 0 / 72%);

  --border: #2a3542;
  --border-strong: #3a4858;
  --border-focus: #60a5fa;

  --text: #edf2f7;
  --text-secondary: #aab6c4;
  --text-muted: #8491a1;
  --text-disabled: #5f6d7b;

  --accent: #60a5fa;
  --accent-hover: #93c5fd;
  --accent-active: #3b82f6;
  --accent-tint: rgb(96 165 250 / 14%);
  --accent-on: #07111f;

  --success: #4ade80;
  --success-tint: rgb(74 222 128 / 14%);
  --info: #60a5fa;
  --info-tint: rgb(96 165 250 / 14%);
  --warning: #fb923c;
  --warning-tint: rgb(251 146 60 / 14%);
  --danger: #fb7185;
  --danger-tint: rgb(251 113 133 / 14%);
  --neutral-status: #8491a1;
  --neutral-status-tint: rgb(132 145 161 / 14%);

  --shadow-sm: 0 1px 2px rgb(0 0 0 / 38%);
  --shadow-md: 0 8px 24px rgb(0 0 0 / 46%);
}
```

### Color rules

- Body copy uses `--text`; secondary copy may use `--text-secondary`. `--text-muted` is for non-essential metadata, not long prose or form labels.
- The main action on a screen may be filled with `--accent`. Other actions are secondary or ghost styles.
- Amber is for waiting, caution, and human approval. Do not use it as decoration.
- Red is for failed states, invalid data, high-risk findings, denied destructive confirmation, and destructive actions. Never use red for GAMR branding or routine navigation.
- Green means a state has completed successfully or a decision was recorded. It never means an action-enabled experiment is inherently safe.
- Every status combines color with a visible text label and, where useful, an icon or shape.
- Do not hard-code hexadecimal, RGB, HSL, or named colors in components. Add a semantic token here when a real new role is needed.
- Do not use gradients, translucent glass panels, neon glows, or multicolor icons in the product UI.

## 6. Run, approval, and finding semantics

Use API enum values as data and the following presentation mapping as the visual contract:

| Domain state                                           | Token              | Presentation                                              |
| ------------------------------------------------------ | ------------------ | --------------------------------------------------------- |
| Queued                                                 | `--info`           | Blue dot plus “Queued”                                    |
| Preparing, discovering, running, evaluating, reporting | `--info`           | Blue activity mark plus exact phase label                 |
| Waiting for approval                                   | `--warning`        | Amber attention mark plus “Waiting for approval”          |
| Completed                                              | `--success`        | Green check plus “Completed”                              |
| Failed                                                 | `--danger`         | Red error mark plus “Failed” and a readable error summary |
| Cancelled                                              | `--neutral-status` | Neutral stop mark plus “Cancelled”                        |
| Unknown or disconnected                                | `--neutral-status` | Neutral question/offline mark plus explicit text          |

Action mode and approval evidence require special care:

- Show `Read-only` as a persistent neutral badge on experiment and run summaries.
- Show `Actions Allowed` as an amber badge when reviewing a CLI-created bundle.
- Display approval observations verbatim with their run and case context. The web never renders approval decision controls.
- Secret and authorization fields render verbatim for trusted test operators. Warn that copied or downloaded evidence can contain credentials.

Finding severity uses label plus token: Critical/High use `--danger`, Medium uses `--warning`, Low uses `--info`, and Informational uses `--neutral-status`. Critical and High must remain distinguishable by their written labels, sorting, and accessible names rather than different shades of red alone.

## 7. Shape, borders, elevation, and motion

```css
:root {
  --radius-xs: 3px;
  --radius-sm: 5px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-full: 9999px;

  --border-w: 1px;
  --focus-ring: 0 0 0 2px var(--bg), 0 0 0 4px var(--border-focus);

  --duration-fast: 120ms;
  --duration-base: 160ms;
  --duration-slow: 240ms;
  --ease-out: cubic-bezier(0.2, 0, 0, 1);
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
}
```

- Inputs and compact controls use `--radius-sm`; cards and evidence blocks use `--radius-md`; dialogs use `--radius-lg`.
- Pills are reserved for statuses, filters, and compact categorical values. Buttons, tabs, cards, and inputs are not pill-shaped.
- Static panels use border and surface contrast, not shadows. `--shadow-md` is for dialogs, menus, and popovers.
- Hover and focus transitions use `--duration-fast` or `--duration-base`. Do not animate layout, large background washes, or evidence text.
- A subtle opacity pulse may indicate a live phase. Streaming text may use a blinking caret. Never use bouncing dots, spinners without labels, or decorative entrance animations.
- Under `prefers-reduced-motion: reduce`, disable pulses, caret animation, smooth scrolling, and non-essential transitions. Replace live animation with a static outlined indicator and text.

## 8. Component contracts

### Buttons and links

- **Primary:** one principal action, filled `--accent`, `--accent-on`, height `--control-h`, weight 500.
- **Secondary:** transparent or `--surface`, one-pixel `--border-strong`, text `--text`.
- **Ghost:** transparent with a visible hover surface. Use for compact toolbars and low-priority actions.
- **Danger:** danger text and border by default; filled danger only inside a destructive confirmation.
- Use links for navigation and buttons for actions. Never make a clickable `div`.
- Icon-only buttons are allowed only for universally understood, reversible controls and require an accessible name and tooltip. Approval, run, and artifact actions always retain text labels.

### Forms

- Labels are visible and placed immediately above their controls. Placeholder text is an example, never the only label.
- Inputs use `--surface`, `--border`, `--control-h`, and the shared focus ring. Errors appear near the field and in an error summary when submission fails.
- Group related experiment settings with `fieldset` and `legend`, particularly target/model configuration, limits, and action mode.
- Explain the read-only default in plain language. Selecting `approval_required` reveals a warning and requires explicit confirmation before starting a run.
- Preserve user input after validation or server errors unless retaining it would expose a secret.

### Tables and lists

- Use semantic tables for tasks, experiments, cases, and artifacts when columns align across rows.
- Keep headers visible on long tables where practical. IDs, versions, counts, and timestamps use monospace/tabular numerals.
- Provide meaningful empty, loading, and error states; an empty `<tbody>` is not an empty state.
- Row actions must work by keyboard and must not rely on hover to become discoverable.
- On narrow screens, preserve columns through horizontal scrolling or offer a deliberate stacked representation with the same labels.

### Run timeline and live state

- The run header always shows exact status, action mode, task, start time, and the latest persisted update.
- Display the ordered phase timeline without implying completion for a phase that is only active.
- Show aggregate completed and total progress above test-case rows. A collapsed case row shows its
  latest meaningful activity or terminal outcome, status text, and update count without rendering
  hidden evidence.
- Start every individual case row collapsed, including running and assessing cases. Keep the
  test-case group open so the progress overview remains visible, and preserve operator expansion
  while updates arrive.
- When a case has a verdict, keep its lifecycle badge and add `Vulnerability Exposed` or `No breach`
  as a separate result badge in the collapsed header. Completion and security outcome are distinct.
  Use the latest evaluation result during live refresh gaps. Never duplicate scientist-generated
  cases in the base test-case group; their iteration is their sole visible owner.
- Distinguish `Not started`, `Queued`, `Running`, `Assessing`, and terminal case states in text.
  Queued means the case is waiting for an execution slot. Use `Status unavailable` for missing
  legacy state, and never infer group completion from a completed nested activity.
- Within an expanded case, display activity oldest to newest. Keep older completed activity compact
  and open the latest or current activity by default. Label that live edge in text. Disclosure uses
  a button with `aria-expanded` and `aria-controls`; an operator's choice survives incoming updates.
- SSE reconnecting or stale data is explicit: use text such as “Reconnecting to live updates” or “Last update …”. Do not replace known persisted state with a spinner.
- Announce important asynchronous changes through a restrained `aria-live` region. Do not announce every streamed token or polling tick.
- Cancellation is a destructive action with confirmation and clear scope. A cancelled run remains reviewable evidence.

### Transcript, tool calls, and evidence

- The transcript is a chronological, left-aligned record inside `--reading-max`; no avatars or message bubbles.
- Human prompt, model response, tool call, approval event, and system event each have a visible type label.
- Prose uses sans-serif. Tool names, normalized arguments, output, JSON, timestamps, model names, IDs, and artifact paths use monospace.
- Tool calls use a bordered block with a header containing tool name, status label, and duration. Collapse verbose arguments and output by default; errors open by default.
- Keep the invoked command visible for shell-like calls. Render stdout/stderr verbatim with wrapping controls that do not force the whole page wider.
- Diffs use `--success-tint` for additions and `--danger-tint` for removals, plus `+`/`−` gutters and accessible text.
- Autoscroll only when the reader is already near the bottom. Never pull a reviewer away from earlier evidence.
- Large transcripts and SSE backlogs must be bounded or virtualized as required by the scaffold. Truncation states link to the complete permitted artifact and state what was omitted.

Sandbox operation previews use one bordered terminal-style session per case-owned
operation. Show the exact textual lifecycle state, opaque operation ID, logical
generation, and bounded attempt disclosures. Python source uses Prism tokens with
the semantic accent, success, warning, danger, and muted roles already defined
above; stdout and stderr use monospace blocks and explicit safe-state labels.
Never render backend sandbox/container IDs. Active previews use a restrained
polite status announcement and become static under `prefers-reduced-motion`.

### Approvals

- Pending approvals are prominent in the run navigation and page heading, including a text count.
- The decision panel prioritizes readable arguments and consequence over decorative severity.
- Keyboard focus moves to the confirmation dialog when opened and returns to the invoking control when closed.
- While a decision is submitting, disable both decision controls, show a labeled progress state, and retain the idempotent outcome returned by the API.

### Artifacts

- Show artifact name, type, size when available, creation time, and source run/case.
- Downloads are links when they resolve a safe API resource. Preview and download must never expose server filesystem paths or credentials.
- Raw JSON is secondary to a readable summary but remains discoverable for audit work.

### Run evidence interactions

- The relationship view is a native SVG projection paired with a complete semantic list. Every
  aggregate appears in both representations with the same participant labels, count, status text,
  sequence bounds, keyboard activation, visible focus, and selected state. The SVG is explanatory;
  the list is the authoritative accessible interaction surface.
- Evidence search is literal, exact, run-scoped, and reflected in the URL. Filter changes reset the
  cursor and selection to the bounded result window. Do not imply that omitted history was loaded;
  state the omitted count and provide older/newer navigation.
- Follow mode advances only when the reviewer is at the live edge. Pausing follow preserves focus,
  the selected activity, and scroll position while showing a text count of newer items. Resync after
  reconnect merges by stable activity ID and sequence and never duplicates rows.
- Timeline and relationship selections open a summary-first inspector. Detail is requested on
  explicit reveal or download, remains available in the collapsed and revealed DOM, accessible names,
  clipboard output, and downloaded bytes, and never exposes server paths. Missing, omitted,
  malformed, oversized, and redacted states remain distinct text states.
- Do not render the complete history into the DOM. Keep activity pages at the server limit, keep one
  selected detail request in flight, and honor reduced motion by removing non-essential live
  animation while retaining text connection and follow states.

### Notifications and dialogs

- Inline feedback is preferred when it belongs to a form or run state.
- Toasts are for brief, non-critical confirmation and never contain the only copy of an error or approval request.
- Dialogs require a visible heading, clear scope, initial focus, focus containment, Escape handling when safe, and focus restoration.

### Icons and data visualization

- Text is sufficient for the initial functional UI. Do not add an icon package solely for decoration.
- If an icon set is introduced for a real interaction need, use one outline family consistently at 16–20px and pair status icons with text.
- Charts require an accessible table or summary, direct labels where possible, and patterns/shapes in addition to color. Use semantic colors only for semantic series; neutral comparison series should stay neutral.

## 9. Focus, accessibility, and content

- Every interactive element uses `--focus-ring` with `:focus-visible`; never remove the browser outline without a visible replacement.
- Minimum pointer target is 24×24 CSS pixels; prefer 36px for primary controls and dense table actions.
- Body text and essential icons meet 4.5:1 contrast; large text and non-text UI meet their applicable AA thresholds. Test both themes.
- Maintain logical heading order, landmarks, skip navigation, table captions, form labels, and explicit button names.
- Loading uses `role="status"`; blocking errors use `role="alert"` sparingly. Live run updates use a dedicated polite region with summarized messages.
- Use sentence case and concrete verbs: “Start run”, “Approve tool action”, “Download result JSON”. Avoid vague labels such as “Submit”, “Yes”, and “Continue” when the consequence matters.
- Write timestamps with the user's timezone and expose an exact ISO/UTC value where audit precision is useful.
- Never communicate “safe” when the system only knows “approved”, “completed”, or “no finding recorded”.

## 10. Implementation contract

When the token system is implemented:

1. Create `src/tokens.css` as the single source of truth for the custom properties in this document and import it before application styles.
2. Keep structural component rules in plain CSS, using semantic class names and the tokens above.
3. Set `data-theme` on `<html>`. On first visit, follow `prefers-color-scheme`; after an explicit selection, persist `light` or `dark` in `localStorage`.
4. Persist the sidebar collapse choice under a dedicated key. The toggle must retain an accessible name in both expanded and collapsed states; mobile may force the full top rail.
5. Add a small initialization path that avoids a theme flash without putting secrets or configuration in HTML.
6. Use native HTML before creating abstractions. Extract a shared React component only when behavior, accessibility, and styling genuinely repeat.
7. Do not create local aliases such as `--button-blue` or `--card-gray`. Use role-based tokens or add a justified semantic token to this file and `tokens.css` together.
8. Do not add hard-coded colors, spacing, radii, shadows, or transition durations inside TSX.

Tests for material frontend work must cover the relevant visible states and behavior, especially:

- Loading, empty, error, stale/reconnecting, and successful data states
- Keyboard navigation and visible focus
- Run phase and approval labels independent of color
- Read-only versus `approval_required` confirmation
- Approval confirmation and duplicate-submission prevention
- Sensitive-value preservation in summaries and expanded evidence
- Reduced-motion behavior for live indicators
- Responsive access to tables, transcripts, and decision controls

Run the narrowest web test while iterating and the repository checks required by the root instructions before handoff.

## 11. Review checklist

Before merging a UI change, confirm:

- The screen makes the current task, experiment, run, or case context clear.
- Read-only/action mode and approval state are explicit where relevant.
- Status is conveyed with text, not color alone.
- The principal action is obvious and competing filled actions are absent.
- Evidence remains readable at long lengths and does not leak secrets.
- Loading, empty, error, reconnecting, and disabled states are designed.
- Keyboard, focus, announcements, contrast, and reduced motion were checked.
- Both themes use tokens and remain usable.
- The expanded rail is 192px, the collapsed rail is 56px, and its toggle remains keyboard-accessible.
- No unapproved framework, remote font, decorative icon set, gradient, glass effect, or hard-coded color was added.
