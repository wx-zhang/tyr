# Deck template

## Purpose and ownership

This directory is the reusable Tyr × GAMR presentation source. It is not a working deck for a specific talk.

- For a presentation request, copy the whole directory to a new location first, preferably `.gamr/decks/<topic>/`. Edit and serve the copy.
- Never overwrite an existing destination. Choose a new directory or deliberately continue its existing deck.
- Edit `docs/deck-template/` only when the user explicitly asks to update the template itself.
- These instructions travel with copies. In a copied deck, edit that copy freely for its presentation; don't propagate its talk-specific content back into the template.
- Keep template examples generic and clearly labeled. Do not include actual findings, Experiment IDs, credentials, raw transcripts, or provider payloads.

## Layout

- `deck.mjs`: the shared slide manifest consumed by the browser and server.
- `index.html`: branding, metadata, controls, and dialogs.
- `app.js`: rendering, navigation, theme persistence, and fullscreen.
- `styles.css`: the 1600 × 900 stage and shell.
- `slides.css`: reusable slide components and theme styles.
- `slides/`: one HTML fragment per slide, with a `template.notes` element.
- `assets/`: local branding assets.
- `server.mjs`: loopback-only Node server with explicit asset routes.
- `export-pdf.mjs`: local Chrome/Chromium PDF export; writes to `.gamr/` under the caller's working directory.
- `chromium-pdf.mjs`: isolated browser process, local debugging connection, and streamed PDF output.
- `previews/`: generic light/dark screenshots for documentation; update when their visible example changes.
- `README.md`: copy workflow, authoring, controls, and verification.
- `CLAUDE.md`: relative symlink to this file. Never replace it with a regular file.

## Standards

- Keep Node.js 24 LTS compatibility. No dependencies, build step, remote fonts, or external script libraries.
- PDF export may use an installed Chrome/Chromium executable without npm dependencies. Use an isolated temporary profile and direct process arguments, never a shell command or the user's browser session.
- Reuse existing layouts and controls. Avoid slide-ID-specific CSS and accumulating patches for one presentation.
- Keep each source file below 300 lines. Prefer readable, direct code with no needless comments or abstractions.
- Keep one main idea per slide. Shorten or split content before reducing font size.
- Give each visible section a unique heading ID and `aria-labelledby`. Put source details and caveats in notes, but keep decisive evidence limits visible.
- Dark remains the default. Every visual change must work in light mode too, including diagrams, links, badges, dialogs, and logos.
- Preserve keyboard navigation, visible focus, reduced-motion support, and new-tab link safety.
- Use simple slide filenames without directory components. Update `deck.mjs` when adding, removing, or reordering slides; keep at least one entry.
- Update the README whenever controls, setup, layout, serving behavior, or authoring conventions change.

## Evidence and safety

- A presentation is read-only. Do not run live Experiments, contact Tyr/model providers, or approve actions merely to prepare or verify slides.
- Evidence links may open saved Experiments in GAMR, using `target="_blank" rel="noopener noreferrer"`. They must never trigger actions.
- Distinguish Completion Outcome, Objective Status, and security verdict. Label inconclusive results and unavailable comparisons honestly.
- Do not claim a protected result from a timeout, missing target, or setup failure.
- Notes are shipped to the browser and aren't confidential. Keep sensitive evidence in the trusted operator interface rather than the deck files.
- Treat slide HTML as trusted author input, never untrusted runtime content.
- Preserve loopback binding, GET/HEAD-only serving, CSP, and explicit asset allowlisting. Never serve the repository root or run bundles.

## Working commands

From the repository root, use a fresh destination:

```bash
mkdir -p .gamr/decks
cp -R docs/deck-template .gamr/decks/template-check
PORT=4180 node .gamr/decks/template-check/server.mjs
```

Use a managed background process when running through an agent harness. Restart after manifest/server changes. Refresh for slide/CSS changes. Stop temporary verification servers when finished.

## Verification

- Verify template changes through a fresh copy, not by relying on files outside the template directory.
- Open the actual browser surface. Check all examples, both themes, footer clearance, notes, index, keyboard controls, theme persistence, and fullscreen.
- Check new-tab behavior for real evidence links in working decks. Template sample cards intentionally have no fake links.
- Check a smaller viewport and ensure controls remain usable.
- For PDF changes, export a copied deck and inspect page count, 16:9 page size, both themes, text, and link annotations. Verify that notes and controls are absent and existing output files aren't overwritten. Keep generated PDFs under `.gamr/`, out of commits.
- For server changes, check rejected paths and methods as well as allowed assets. Never broaden filesystem access to make a test pass.
- Don't add tests that pin markup or wording. Keep regression coverage only for a plausible behavioral failure.
