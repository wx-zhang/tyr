# GAMR - Generative Adversarial Risk Mapper for Tyr

The following repository contains a red teaming agent for Tyr.

## About Tyr

Tyr is a security and governance layer for AI agents. It sits between an AI agent and the tools, APIs, or company systems the agent can access, checking whether each action is authenticated, authorized, and compliant with defined policies before it is executed. In simple terms, Tyr acts like a firewall and access-control system for AI agents, helping prevent unsafe actions, prompt-injection abuse, unauthorized data access, and providing logs of what agents do.

## Core Standards & Syntax

- `docs/SCAFFOLD_SPEC.md` is the canonical architecture and scaffold contract.
- Use Python 3.14 with one root uv workspace and `uv.lock`. Use Node.js 24 LTS with pnpm only for `apps/web` and one root `pnpm-lock.yaml`.
- Apps depend on shared packages; packages never depend on apps. CLI and API execution share the same engine.
- Tasks and canonical run results are schema-validated JSON files. Databases contain rebuildable operational state only.
- Read-only is the default. Real actions always require explicit, recorded human approval. Test evidence is retained verbatim, including credentials and other sensitive values.
- Put module-specific architecture, commands, conventions, and tests in the nearest child `AGENTS.md`; do not duplicate them here.
- Keep every `AGENTS.md` below 300 lines and follow the root file's general pattern: purpose, scoped standards, layout or ownership, working commands, safety/testing rules, and coding standards. Omit sections that do not apply.
- Avoid using lazy-import. Imports should be placed on top, unless it's required by the circurral dependency.

## Traceability

- Any interaction with LLM or Tyr must be traceable from the execution log.
- Any code executed in sandbox should be stored with inputs and outputs in the logs.

## Repository Layout

The intended monorepo layout is:

```text
apps/
  cli/       Typer/Rich `gamr` command: standalone experiments, task/result validation, doctor, and interactive chat
  api/       FastAPI HTTP API, dependency composition, error mapping, routes, and SSE delivery
  web/       Optional React/TypeScript/Vite interface for experiment starts and run visualization

packages/
  core/      Domain models, JSON schemas, identifiers, findings, events, enums, and state-transition validation
  engine/    Experiment/chat orchestration, approval coordination, reporting, services, and abstract ports
  adapters/  Tyr MCP, OpenAI-compatible models, JSON filesystem stores, artifact storage, and sandbox backends

tasks/
  <task>/ Versioned task.json, optional discovery.json, and cases/*.json

schemas/     Generated task, run-result, and OpenAPI schemas
docs/        Architecture, data-format, development, and scaffold specifications
scripts/     Schema export, local development data utilities, and sandbox developer commands
tests/       Cross-package fixtures, integration tests, smoke tests, and sandbox runner tests
evaluations/ Small, reviewed, run-derived datasets for opt-in live judge regression
.gamr/       Gitignored local run bundles and standalone operational state
```

Scoped instruction files belong in `apps/`, every `apps/*` module, `packages/`, every `packages/*` module, `tasks/`, `schemas/`, `docs/`, `scripts/`, `tests/`, and `evaluations/`. A scoped file adds only subtree-specific rules and may tighten, but never weaken, this file's safety requirements. See `docs/SCAFFOLD_SPEC.md` for the ownership of each instruction file.

### Module dependency rules

- `gamr-core` is the innermost package. It has no FastAPI, Typer, terminal, filesystem, or vendor SDK concerns.
- `gamr-engine` depends on `gamr-core` and ports. It owns workflow decisions but not concrete network, filesystem, or UI behavior.
- `gamr-adapters` implements engine ports. Tyr operation polling and settling belong in `gamr_adapters.tyr`, not in apps.
- `gamr-cli` is the primary composition root. `gamr-api` is an optional read-only service adapter; packages must never depend on apps.
- `apps/web` communicates only with the API. Tyr and model-provider credentials must never be sent to the browser.
- Keep CLI and API experiment execution on the same engine path. Do not fork business logic for local and service modes.

### Setup and common checks

Run commands from the repository root:

```bash
uv sync --all-packages --dev
corepack enable
uv run poe web-install
uv run poe lint --fix
uv run poe typecheck
uv run poe test
uv run poe schemas
uv run poe sandbox-build
uv run poe sandbox-run --attach <path> --code "<source>"
uv run poe evaluate:judges
uv run poe check
```

Use `uv run poe dev` for the local API and Vite stack. Use the narrowest relevant check while iterating, then run `uv run poe check` before handoff. If the repository is still being scaffolded and a command does not exist yet, implement it only when it belongs to the requested scaffold step; do not create placeholder commands that falsely report success.

Expected CLI surface:

```text
gamr doctor
gamr task list
gamr task validate <task-directory>
gamr experiment run <task-directory>
gamr experiment show <run-id>
gamr result validate <result.json>
gamr evaluate judges
gamr chat
```

### Agent safety invariants

- CLI experiments and chat default to read-only. The web Execute form defaults to Actions Allowed (`approval_required`) with a visible warning; operators can uncheck for read-only.
- `approval_required` is the only action-enabled mode. Never implement or use automatic approval.
- Starting an action-enabled run requires an explicit CLI flag or web confirmation, and each Tyr action still requires a recorded human decision (Tyr-side; GAMR does not approve).
- Live Tyr/OpenRouter tests are opt-in and marker-gated. Never run them in default tests or enable real actions merely to verify a change.
- Sandbox Docker runtime tests are opt-in and marker-gated. Default tests use fake Docker processes or controlled host snippets.
- Use an idempotency key for every Tyr request and approval resolution. Retry an interrupted external step only when its idempotency and checkpoint state make the retry safe.
- Preserve model, Tyr, tool, sandbox, and artifact evidence verbatim. Treat run bundles and API access as trusted-operator data because they can contain credentials and authorization values.
- Never trust an outer Tyr terminal state alone: delegated executions, bridge work, or a late user-visible response may still be pending. Preserve the settle-window behavior and raw diagnostic evidence.
- Never overwrite canonical task files or completed run bundles as a side effect of viewing or evaluating them.

### Testing expectations

- Validate task and result JSON against generated schemas in tests and CI.
- Default tests use fake ports and fixtures; they must not require live Tyr, a model provider, or action approval.
- Any bug fix adds a regression test at the lowest layer that can reproduce it.
- Always prefer TDD when implementing a functionality: first write test, check they fail and then write working implementation.

## Coding standards

- HARD GATE: Keep source files under 300 lines. This does not apply to dependency files, generated files, vendored code, migrations, snapshots, or other files that are better kept as one file.

### Occam Razor

* Solve only the current problem.
* Do not add features “just in case” or “for the future.”
* Avoid extra abstractions, layers, or clever patterns.
* Use the fewest lines and fewest moving parts.
* Skip unnecessary error handling or configuration unless required.
* If two solutions work, pick the simpler and shorter one.

### No comments policy

* The code must be self-explanatory: Use clear and descriptive names for variables, functions, and files. Keep logic simple and obvious so the code explains itself. Structure code so a reader understands it without extra notes.
* Don't write comments unless workaround or hard to explain logic is used.

### Writing style

Simple, direct English. Short sentences. One idea at a time. Clear headings,
small lists, no jargon. Lead with the practical answer.

### Tests first, weighted by risk

Default loop: **failing test → watch it fail → smallest code that passes →
refactor.**

Scale the effort to the risk. Tests must be meaningful. Do not chase 100%
coverage, and never write a test that only restates the implementation.

| Tier | Code | Rule |
|---|---|---|
| **Critical** | auth, tokens, command execution, workdir allowlist, protocol parsing | Test first, no exceptions. Cover the happy path **and every rejection path** — bad input, expired or forged token, path escape, missing permission. |
| **Core** | domain logic, node selection, API handlers, data access | Test first. Happy path plus the corner cases that realistically break: empty, boundary, duplicate, out-of-order, failure mid-flight. |
| **Surface** | UI components, formatters, glue | Test the behaviour a user depends on. Skip tests that assert markup shape. |
| **Skip** | types, config objects, constants, thin passthrough | No tests. |

Prefer a few sharp tests over many shallow ones. Covering *most* relevant corner
cases is the goal; covering *all* of them is not. If you knowingly leave a
Critical or Core path untested, say so in your summary.

Full guide — layout, commands, patterns: `tests/CLAUDE.md`.

### Keep docs current

Docs ship **in the same commit** as the code, never as a follow-up. These
triggers are not optional:

| You changed | Update, same commit |
|---|---|
| Added, removed, or renamed a package or app | layout tree + nested-instructions table below, `README.md`, and a new `AGENTS.md` for the module |
| A script in any `package.json` | Commands table below (root scripts) or the module's `AGENTS.md` (package scripts) |
| A version in the `catalog:` block | Stack table below |
| A dependency edge between packages | both dependency diagrams (below and in `README.md`) |
| A new directory or seam under a module's `src/` | that module's `AGENTS.md` file map |
| A `ROOST_*` env var | that app's `.env.example` + the table in `README.md` |
| Behaviour a spec describes | the spec, plus its line in `specs/INDEX.md` |
| Where tests live or how they run | `tests/AGENTS.md` |

A new module needs three things before it is done: `AGENTS.md`, a `CLAUDE.md`
symlink (`ln -s AGENTS.md CLAUDE.md`), and a row in the nested-instructions
table.

- Every `CLAUDE.md` is a **symlink** to the `AGENTS.md` beside it. Edit
  `AGENTS.md`. Never overwrite the symlink with a real file.
- Fix any doc you find that contradicts the code. A doc that lies is worse than
  no doc.
- Keep this file under 200 lines. If it grows past that, move the detail into a
  nested `AGENTS.md` and leave a one-line pointer here.
