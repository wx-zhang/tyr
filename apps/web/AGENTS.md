# Web scope

## Purpose

Own the optional React, TypeScript, and Vite interface for tasks (catalog and read-only detail review), experiment execution starts, run visualization, transcripts, and artifacts.

## Standards

Use React Router for navigation and TanStack Query for server state. Keep transient state local. Use the generated API contract and the SSE hook; the browser talks only to the API.

`UI-DESGIN-TOKEN.md` is the canonical visual, interaction, accessibility, and content standard for this application. Read it before frontend work and follow it for every new UI or material UI change. If implementation requires adding, removing, or changing a design token or design-system rule, update `UI-DESGIN-TOKEN.md` in the same change so documentation and code never diverge. Keep design values in the shared CSS tokens described there; do not introduce hard-coded component colors, a second token layer, or a UI/CSS framework without an explicit architecture decision.

When implementation of an OpenSpec change is complete, archive every mock-only source file, fixture, style, and asset in `<change-root>/mocks/` inside that OpenSpec change directory. Remove the frontend mock route and mock-only imports after archiving. Preserve the archived mock as the accepted design reference.

## UI styleguide

Aim for a calm, compact operator workspace. Use the rules below as the working
summary of `UI-DESGIN-TOKEN.md`, not a separate design system.

### Hierarchy and density

- Start with one page title and a quiet secondary action. Add an eyebrow or description only when it supplies information the title and controls don't already convey.
- Put useful controls near the top. Avoid tall introductory panels, repeated headings, decorative step numbers, and empty vertical space.
- Use visible field labels instead of another section heading when a short form row explains itself. Simple selectors and optional names can sit in a borderless row.
- Group by the decisions the operator makes. Use headings and dividers first; add a card only for a distinct work area. Avoid nested cards.
- Give the main content more width than supporting settings. Align columns at the top and stack them in reading order on narrow screens.
- Keep spacing on the shared 4px token grid. Use compact gaps within a group and larger gaps between groups. Don't shrink text or pointer targets to make a page fit.

### Controls and content

- Keep one primary action. Use secondary or ghost styling for navigation, selection tools, and disclosures.
- Make the next action's consequence clear beside the button, especially the difference between saving settings, reviewing, and starting an Experiment.
- Keep common settings visible. Put infrequent configuration behind a labeled disclosure that reports meaningful configured or error state.
- Keep permissions, approval warnings, and blocking errors visible. Compact layouts must never hide safety information.
- Use short, concrete labels and mark optional fields. Helper text must explain a constraint or consequence, not repeat the label.
- Size controls to their content: short numeric inputs stay short; Task selectors and names receive room to read.
- Use readable list rows with quiet separators rather than a separate heavy card for every item. Show selection counts, preserve full titles, and use text alongside selection or status color.
- Prefer page scrolling for short configuration lists. Use bounded scrolling or pagination for large datasets, with a clear indication that more items exist.

### Visual consistency

- Reuse the shell, shared components, and CSS tokens before adding page-specific rules. Scope page-specific CSS so neighboring screens don't change.
- Use neutral surfaces and thin borders. Blue identifies interaction, amber approval or caution, and red failure or danger. Avoid decorative color, gradients, and shadows on static panels.
- Use sans-serif for human-readable content and monospace for identifiers and numeric data. Let typography and spacing establish hierarchy.
- Preserve visible focus, semantic labels, readable contrast, and reduced-motion support in both themes. Long identifiers must wrap without widening the page.

### Design verification

- Inspect the actual page before editing. Use `/experiments/new` as a reference for compact setup forms, not a template to copy onto unrelated workflows.
- Check the finished page at desktop and narrow mobile widths in light and dark themes. Look for unnecessary height as well as overflow, clipping, and cramped controls.
- Exercise pointer and keyboard interactions, disclosures, selection, disabled actions, and relevant empty/error states. Never start a live Experiment just to verify presentation.
- Run the relevant frontend build and behavior tests. Keep tests about user-visible behavior, not exact headings or markup shape.

## Commands

`pnpm --dir apps/web install`, `pnpm --dir apps/web dev`, `pnpm --dir apps/web build`, and `pnpm --dir apps/web test`.
Use `pnpm --dir apps/web generate:api` to regenerate `src/api/generated.ts` from
`schemas/openapi.json`; `uv run poe schemas` runs this after exporting the server schemas.
Do not hand-edit the generated browser contract.

## Safety/accessibility

The web is a trusted test-operator surface and displays evidence verbatim, including secrets. Maintain labels, keyboard navigation, visible focus, reduced-motion behavior, and restrained status announcements. Display Experiment State, action mode, approval state, and finding severity with text rather than color alone. The web may start Approval-gated Experiments when the operator opts in; it may display approval evidence but never decides Tyr approvals.

Task review uses `GET /api/v1/tasks/{id}`, `…/scenarios` (full Scenarios; `…/cases` remains a compatibility path), and
`…/plans` (discovery/methodology/evaluation plus the live evaluation reference).
The detail page renders that synthetic reference file when present. Routes:
`/tasks`, `/tasks/:taskId`, `/tasks/:taskId/scenarios/:scenarioId`.
Legacy `/tasks/:taskId/cases/:caseId` links normalize at the route boundary.

The Experiment review screens consume API Experiment, Scenario Execution, activity, and artifact
endpoints; Tyr and model calls remain server-side.
`/runs` lists Experiments newest first with search, state filters, and 25-row progressive loading;
`/` remains an entry point to that list. Bulk selection applies only to visible, deletable rows
and clears when filters change. Outcome accents distinguish breach and no-breach results.
`/runs/:id` leads with the Experiment name, full ID, permissions, and a labeled refresh selector.
Results and activity appear before lifecycle and Tyr network details, with section links for navigation.
Summary, activity, and collector evidence load independently with shared, labeled `LoadingStatus`
indicators. Completed content remains visible during refresh; collector list failures show an
inline error and a collector-only retry. Tyr relationships are requested only while their
persisted disclosure is open, so the default collapsed network does not delay review.
Scenario rows use red, green, or amber outcome accents while retaining separate lifecycle badges.
Review layout styles live in `run-review.css`, `run-review-header.css`, and `run-review-history.css`;
list controls and layout live in `experiment-browser.css` and the scoped dashboard rules in `data.css`.
New web Experiment Preset forms initialize max concurrent Scenario Executions to 1; operators may raise it through 5.
`features/experiments/ExperimentPage.tsx` keeps Task and optional Preset name in a compact, borderless row.
Execution settings and the full Scenario checklist sit below, followed by the review footer.
`ExecutionLimits.tsx` owns the limit controls; `DiscoveryInputPanel.tsx` owns the Advanced file-input presentation.
Page-scoped layout lives in `src/styles/experiment-setup.css` and stacks on narrow screens.
`features/runs/RunHistory.tsx`, `RunHistoryGroup.tsx`, and `RunHistoryCase.tsx` render
grouped Experiment history partitioned into discovery, Scenario Executions, Research Iterations, and other updates.
`features/runs/runHistoryGroups.ts` performs the grouping, while `runHistoryTypes.ts` owns its
shared presentation types and chronological sorting helpers.
Scenario Executions expose aggregate completion progress and summary-first rows. Their activity timelines
read oldest to newest; older completed activity is compact, while the latest or current activity
opens by default. Collapsed rows distinguish not started, queued, running, assessing, and terminal
work; group completion follows lifecycle progress rather than a nested activity status.
Completed discovery groups start collapsed when the Experiment history loads; active discovery stays open.
Every Scenario Execution row starts collapsed when entering the page; operator expansion persists across updates.
Verdict-bearing Scenario Execution headers show lifecycle and vulnerability outcome as separate text badges.
Evaluation updates supply the result badge until visualization catches up. Researcher-generated
Scenarios belong only to their Research Iteration group and never contribute to base Scenario Execution progress.
`features/runs/runHistoryPresentation.ts` derives Experiment summaries, and
`RunTurnCard.tsx` plus `RunTurnDetail.tsx` render the activity disclosure and bounded evidence.
`SandboxOperationSession.tsx` renders one bounded Prism-highlighted terminal preview per
Scenario Execution-owned sandbox operation, including active lifecycle status, attempts, generations, and
safe stream states. It is the postmortem surface for new Experiments; legacy decoding provenance
remains the fallback.
Evaluation details show judge status, Prism-highlighted exact Markdown comparison diffs, checked
files, and missing evidence when the API supplies them.
`features/runs/DecodingProvenance.tsx` renders structured trajectory decoding provenance (status,
route rationale, source, attempt hashes, bounded execution result states, streams, and derived files)
without exposing secrets, decoded bytes, sandbox identity, or unsafe streams. Decoder lifecycle activity
rows remain compact and reference the canonical provenance instead of duplicating source or process output.
`features/runs/CollectorArtifacts.tsx` renders verified collector files as
Updates entries with bounded text, Markdown, XML, and image previews plus run-scoped downloads,
without receiving collector credentials. `CollectorPreview.tsx` owns the focus-contained preview
dialog: its labeled spinner identifies the pending file; Close, Escape, and download remain
available while loading. Closing aborts the request, ignores late bodies, releases image URLs,
and restores focus to the invoking Preview button.

`features/runs/NetworkGraph.tsx` renders network nodes and edges; `TyrNetworkMap.tsx`
owns the disclosure, deferred query, selection state, and relationship list.

Run-evidence behavior tests are split across `RunPage.test.tsx`,
`RunPageScientist.test.tsx`, `RunPageUpdates.test.tsx`, `RunPageCancel.test.tsx`,
`RunPageNetwork.test.tsx`, `RunPageSettings.test.tsx`, `RunHistory.test.tsx`,
`RunHistoryInteraction.test.tsx`, `RunHistoryActivity.test.tsx`, `RunPageLoading.test.tsx`,
`CollectorArtifacts.test.tsx`, `CollectorPreviewLoading.test.tsx`, `SandboxOperationSession.test.tsx`, `DecodingProvenance.test.tsx`, and `useRunEvents.test.ts`. Run
`pnpm --dir apps/web test -- --run` for the complete deterministic web suite and
regenerate `src/api/generated.ts` with
`pnpm --dir apps/web generate:api`.
The Task-details Scenario tab reuses `features/scientist-scenarios/ScientistScenarioPage.tsx`
for the Active/Archived Adversarial Researcher catalog, list-and-detail Scenario review, result
filters, reversible archive actions, and origin-Experiment navigation. Its API calls are typed in
`src/api/client.ts`, catalog styles live in `src/styles/scientist-scenarios.css`,
and behavior coverage is in `ScientistScenarioPage.test.tsx` and
`features/tasks/TaskDetailPage.test.tsx`. There is no standalone Adversarial Researcher route.
