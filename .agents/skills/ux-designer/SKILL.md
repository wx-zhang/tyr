---
name: ux-designer
description: Design and iterate a runnable UI mock from an OpenSpec change, then document the accepted UX/UI and retained mock in the change's design.md. Use when the user asks to "design the UI for" an OpenSpec, "mock this OpenSpec", create a UX prototype from a change, or revise that prototype from feedback.
---

# Design an OpenSpec UI

## Resolve the change

1. Accept a change name, a change directory, or a file inside a change directory.
2. Infer the change from the conversation when exactly one change is named.
3. Run `openspec list --json` when no change can be inferred.
4. Stop and report a missing `openspec` executable without editing files.
5. Ask the user to select a change only when several candidates remain.
6. Run `openspec status --change "[change-name]" --json`.
7. Use `changeRoot` and `artifactPaths` from the status output.
8. Append `--store "[store-id]"` to OpenSpec commands when the user selected a registered store.
9. Stop when the change does not exist.
10. Record the artifact ID whose output path ends in `design.md`.
11. Stop and report the missing change or design artifact without editing files.

## Analyze the specification

1. Read every existing artifact path reported by `artifactPaths`.
2. Read proposal, requirement, design, and task artifacts before choosing a screen structure.
3. Re-read the artifacts at the start of each later feedback round.
4. Extract the target users, primary jobs, required states, safety constraints, content, and acceptance criteria.
5. Separate specified behavior from design choices.
6. Record contradictions that affect the UI.
7. Read the repository instructions that govern the target frontend.
8. Read the frontend's design tokens and visual standards.
9. Inspect its package scripts, routes, shell, nearby features, shared components, and styling conventions.
10. Reuse the existing frontend stack when one exists.
11. Follow one established component styling pattern.
12. Do not introduce a second design system.
13. Identify a browser URL that can display the mock without a live backend.
14. Keep `uv run poe dev:watch` as a user-run command.
15. Treat a missing frontend as one material clarification question.
16. Do not add a frontend framework without the user's explicit selection.

## Clarify material choices

1. Ask zero to five clarifying questions before the first mock.
2. Ask all initial questions in one batch.
3. Use the Ask tool when it is available.
4. Give two to five concrete options for each closed-choice question.
5. Mark the safest option that fits the specification as recommended.
6. Ask only when the answer changes navigation, information hierarchy, interaction flow, visual direction, accessibility, or fidelity.
7. Do not ask for facts available in the OpenSpec artifacts or repository.
8. Make a conservative choice for minor gaps.
9. State each material assumption with the first mock.
10. Wait for answers when a question blocks the screen structure or primary flow.

## Shape the experience

1. State the page's single primary user goal.
2. Map the primary flow from entry through completion.
3. Group information by the decisions the user makes.
4. Establish hierarchy with the frontend's typography, spacing, and color tokens.
5. Keep secondary actions visually subordinate.
6. Reveal infrequent detail through progressive disclosure.
7. Keep critical status and safety information visible.
8. Pair status colors with text or icons.
9. Place validation messages beside the affected control.
10. Confirm destructive or irreversible actions.
11. Match content density to the user's task.
12. Use plain labels that match the OpenSpec vocabulary.

## Build the first mock

1. Implement a runnable frontend mock after resolving all blocking questions.
2. Limit edits to presentation code, local mock data, styles, assets, and route registration.
3. Keep all data in deterministic frontend fixtures or local component state.
4. Make the primary flow interactive without network access.
5. Represent every required success, empty, error, disabled, loading, and permission state that changes the design.
6. Add a local state switcher only when the states cannot be reached through the primary flow.
7. Reuse the real application shell when it can run without a backend.
8. Create a standalone HTML, CSS, and JavaScript mock under `[changeRoot]/mock/` only when no frontend exists and the user selected that option.
9. Add no framework to a standalone mock.
10. Use an isolated prototype route for a new surface unless the repository has another prototype convention.
11. Use the intended route only when the OpenSpec changes an existing surface and mock data can be isolated safely.
12. Use a route shaped like `/__mocks/[change-name]` when no repository convention applies.
13. Name mock-only modules so their status is clear from the file path or exported symbol.
14. Keep mock data beside the mock feature.
15. Preserve visible keyboard focus.
16. Use semantic controls and labels.
17. Make the mock usable at narrow and wide viewport widths.
18. Honor reduced-motion and contrast rules from the frontend standards.
19. Match the repository's content vocabulary.
20. Do not implement an API, server handler, database, authentication flow, generated client, or production data adapter.
21. Leave test code and test commands untouched.
22. Do not edit `design.md` before the user accepts the mock.

## Verify the mock

1. Run the narrowest compile, typecheck, or build command that covers the changed frontend.
2. Fix every error caused by the mock.
3. NEVER start, restart, or stop the application.
4. Open the mock route in a browser.
5. Ask the user to run `uv run poe dev:watch` when the application is unavailable.
6. Wait for the user after requesting that command.
7. Reopen the mock route after the user confirms the application is running.
8. Report that visual verification is unavailable when no browser tool can open the mock.
9. Keep the mock URL available for the user's manual review in that case.
10. Exercise the primary flow with pointer input.
11. Exercise the primary flow with keyboard input.
12. Inspect every required state represented by the mock.
13. Inspect one narrow viewport.
14. Inspect one wide viewport.
15. Fix visible overflow, overlap, clipping, unreadable text, missing focus, and broken state transitions.

## Request feedback

1. Return the mock route or file URL.
2. List the mock source files.
3. List the flows and states available for review.
4. List material assumptions.
5. State the mocked data boundary.
6. State the compile or build result.
7. State the browser checks performed.
8. Ask the user for feedback or explicit acceptance.
9. Treat `accept`, `approved`, and an unqualified `looks good` as acceptance.
10. Treat requested changes and qualified approval as feedback.
11. Do not infer acceptance from silence.

Use this response shape:

```text
Mock: [route or URL]
Files: [paths]
Flows and states: [reviewable behavior]
Assumptions: [material assumptions or "None"]
Mock boundary: [fixture and local-state paths]
Verification: [build and browser checks]
Review: Reply with feedback or "accept design".
```

## Iterate on feedback

1. Translate each feedback item into a visible behavior or presentation change.
2. Check feedback against the OpenSpec before editing.
3. Ask a question only when feedback has materially different interpretations.
4. Ask no question when the requested adjustment is concrete.
5. Flag feedback that contradicts a requirement.
6. Ask the user which source wins before implementing a contradiction.
7. Keep accepted parts stable unless the new feedback depends on changing them.
8. Update the existing mock instead of creating another prototype.
9. Preserve the mocked backend boundary.
10. Repeat the mock verification steps.
11. Return the feedback response shape again.
12. Continue until the user explicitly accepts the design.

## Record the accepted design

1. Re-read every OpenSpec artifact after acceptance.
2. Re-read the accepted mock source.
3. Run `openspec instructions "[design-artifact-id]" --change "[change-name]" --json`.
4. Use the design artifact ID and output path reported by OpenSpec.
5. Preserve the design template and every unrelated existing decision.
6. Create `design.md` from the reported template when the artifact is ready but missing.
7. Add or update one `UX/UI Design` section.
8. Describe the user goal and primary flow.
9. Describe the information architecture, routes, screens, and component hierarchy.
10. Describe important interactions and state transitions.
11. Describe responsive behavior, keyboard behavior, focus behavior, content rules, and accessibility constraints.
12. Record material decisions made during feedback.
13. Record the exact mock source paths.
14. Record the command and route used to view the mock.
15. State that the mock remains in place as the accepted design reference.
16. Identify the fixture and local-state boundary that makes the mock non-production.
17. List only remaining work supported by the OpenSpec and mock.
18. Include production API integration, persistence, authorization, generated contracts, error handling, tests, telemetry, or migration work only when each item applies.
19. Distinguish finished UI presentation from remaining production wiring.
20. Keep the accepted mock at its existing path and in its mocked form.
21. Do not implement any remaining production work.
22. Run `openspec validate "[change-name]" --type change --strict --no-interactive`.
23. Fix design artifact validation errors without changing the accepted UI.

Use this section shape unless the design artifact instructions require different headings:

```markdown
## UX/UI Design

### Experience
[Users, goal, primary flow, and information hierarchy]

### Screens and interactions
[Routes, screens, components, states, and transitions]

### Responsive and accessible behavior
[Viewport behavior, keyboard flow, focus, semantics, contrast, motion, and content]

### Accepted mock
- Source: `[path]`
- Mock data: `[path]`
- View: `[command]`, then `[route]`
- Status: Retained as the accepted design reference. It uses frontend fixtures and local state instead of production services.

### Remaining implementation
- [Only work still required for production]
```

## Report acceptance

Return:

- The updated `design.md` path.
- The retained mock paths and review route.
- The accepted UX/UI decisions.
- The remaining production work recorded in `design.md`.
- The OpenSpec validation command and result.
