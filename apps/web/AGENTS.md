# Web scope

## Purpose

Own the optional React, TypeScript, and Vite interface for datasets (catalog and read-only detail review), experiment execution starts, run visualization, transcripts, and artifacts.

## Standards

Use React Router for navigation and TanStack Query for server state. Keep transient state local. Use the generated API contract and the SSE hook; the browser talks only to the API.

`UI-DESGIN-TOKEN.md` is the canonical visual, interaction, accessibility, and content standard for this application. Read it before frontend work and follow it for every new UI or material UI change. If implementation requires adding, removing, or changing a design token or design-system rule, update `UI-DESGIN-TOKEN.md` in the same change so documentation and code never diverge. Keep design values in the shared CSS tokens described there; do not introduce hard-coded component colors, a second token layer, or a UI/CSS framework without an explicit architecture decision.

## Commands

`pnpm --dir apps/web install`, `pnpm --dir apps/web dev`, `pnpm --dir apps/web build`, and `pnpm --dir apps/web test`.
Use `pnpm --dir apps/web generate:api` to regenerate `src/api/generated.ts` from
`schemas/openapi.json`; `uv run poe schemas` runs this after exporting the server schemas.
Do not hand-edit the generated browser contract.

## Safety/accessibility

Never ship secrets to the browser. Preserve redaction in visible, collapsed, copied, and accessible content. Maintain labels, keyboard navigation, visible focus, reduced-motion behavior, and restrained status announcements. Display run state, action mode, approval state, and finding severity with text rather than color alone. The web may start action-enabled runs when the operator opts in (Actions Allowed); it may display approval evidence but never decides Tyr approvals.

Dataset review uses `GET /api/v1/datasets/{id}`, `…/cases` (full scenarios), and
`…/plans` (discovery/methodology/evaluation). Routes: `/datasets`,
`/datasets/:datasetId`, `/datasets/:datasetId/cases/:caseId`.

The run review screens consume API run, case, activity, and artifact endpoints;
Tyr and model calls remain server-side.
`features/runs/CollectorArtifacts.tsx` renders verified collector files as chronological
Updates entries with bounded text, Markdown, and image previews plus run-scoped downloads,
without receiving collector credentials.

Run-evidence behavior tests are split across `RunEvidence.test.tsx`,
`RelationshipGraph.test.tsx`, `RunBusyEvidence.test.tsx`, and
`useRunEvents.test.ts`. Run `pnpm --dir apps/web test -- --run` for the complete
deterministic web suite and regenerate `src/api/generated.ts` with
`pnpm --dir apps/web generate:api`.
