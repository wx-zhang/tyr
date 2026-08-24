# Web scope

## Purpose

Own the optional React, TypeScript, and Vite interface for tasks (catalog and read-only detail review), experiment execution starts, run visualization, transcripts, and artifacts.

## Standards

Use React Router for navigation and TanStack Query for server state. Keep transient state local. Use the generated API contract and the SSE hook; the browser talks only to the API.

`UI-DESGIN-TOKEN.md` is the canonical visual, interaction, accessibility, and content standard for this application. Read it before frontend work and follow it for every new UI or material UI change. If implementation requires adding, removing, or changing a design token or design-system rule, update `UI-DESGIN-TOKEN.md` in the same change so documentation and code never diverge. Keep design values in the shared CSS tokens described there; do not introduce hard-coded component colors, a second token layer, or a UI/CSS framework without an explicit architecture decision.

## Commands

`pnpm --dir apps/web install`, `pnpm --dir apps/web dev`, `pnpm --dir apps/web build`, and `pnpm --dir apps/web test`.
Use `pnpm --dir apps/web generate:api` to regenerate `src/api/generated.ts` from
`schemas/openapi.json`; `uv run poe schemas` runs this after exporting the server schemas.
Do not hand-edit the generated browser contract.

## Safety/accessibility

The web is a trusted test-operator surface and displays evidence verbatim, including secrets. Maintain labels, keyboard navigation, visible focus, reduced-motion behavior, and restrained status announcements. Display run state, action mode, approval state, and finding severity with text rather than color alone. The web may start action-enabled runs when the operator opts in (Actions Allowed); it may display approval evidence but never decides Tyr approvals.

Task review uses `GET /api/v1/tasks/{id}`, `…/cases` (full scenarios), and
`…/plans` (discovery/methodology/evaluation plus the live evaluation reference).
The detail page renders that synthetic reference file when present. Routes:
`/tasks`, `/tasks/:taskId`, `/tasks/:taskId/cases/:caseId`.

The run review screens consume API run, case, activity, and artifact endpoints;
Tyr and model calls remain server-side.
New web experiment forms initialize max concurrent cases to 1; operators may raise it through 5.
`features/runs/RunHistory.tsx`, `RunHistoryGroup.tsx`, and `RunHistoryCase.tsx` render
grouped run history partitioned into discovery, test cases, scientist iterations, and other updates.
`features/runs/runHistoryGroups.ts` performs the grouping, while `runHistoryTypes.ts` owns its
shared presentation types and chronological sorting helpers.
Test cases expose aggregate completion progress and summary-first rows. Their activity timelines
read oldest to newest; older completed activity is compact, while the latest or current activity
opens by default. Collapsed rows distinguish not started, queued, running, assessing, and terminal
work; group completion follows lifecycle progress rather than a nested activity status.
Completed discovery groups start collapsed when the run history loads; active discovery stays open.
Every case row starts collapsed when entering the page; operator expansion persists across updates.
Verdict-bearing case headers show lifecycle and vulnerability outcome as separate text badges.
Evaluation updates supply the result badge until visualization catches up. Scientist-generated
cases belong only to their iteration group and never contribute to base test-case progress.
`features/runs/runHistoryPresentation.ts` derives run summaries, and
`RunTurnCard.tsx` plus `RunTurnDetail.tsx` render the activity disclosure and bounded evidence.
`SandboxOperationSession.tsx` renders one bounded Prism-highlighted terminal preview per
case-owned sandbox operation, including active lifecycle status, attempts, generations, and
safe stream states. It is the postmortem surface for new runs; legacy decoding provenance
remains the fallback.
Evaluation details show judge status, Prism-highlighted exact Markdown comparison diffs, checked
files, and missing evidence when the API supplies them.
`features/runs/DecodingProvenance.tsx` renders structured trajectory decoding provenance (status,
route rationale, source, attempt hashes, bounded execution result states, streams, and derived files)
without exposing secrets, decoded bytes, sandbox identity, or unsafe streams. Decoder lifecycle activity
rows remain compact and reference the canonical provenance instead of duplicating source or process output.
`features/runs/CollectorArtifacts.tsx` renders verified collector files as
Updates entries with bounded text, Markdown, XML, and image previews plus run-scoped downloads,
without receiving collector credentials.

Run-evidence behavior tests are split across `RunPage.test.tsx`,
`RunPageScientist.test.tsx`, `RunPageUpdates.test.tsx`, `RunPageCancel.test.tsx`,
`RunPageNetwork.test.tsx`, `RunPageSettings.test.tsx`, `RunHistory.test.tsx`,
`RunHistoryInteraction.test.tsx`, `RunHistoryActivity.test.tsx`, `SandboxOperationSession.test.tsx`, `DecodingProvenance.test.tsx`, and `useRunEvents.test.ts`. Run
`pnpm --dir apps/web test -- --run` for the complete deterministic web suite and
regenerate `src/api/generated.ts` with
`pnpm --dir apps/web generate:api`.
