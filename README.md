# GAMR

**Tyr's final opponent**

![GAMR — Tyr's final opponent](docs/assets/gamr-hero.svg)

**GAMR** (Generative Adversarial Risk Mapper) is the red-team experiment runner for
[Tyr](https://tyr.ai/) — the security and governance layer for AI agents.

GAMR runs and reviews adversarial experiments against Tyr. The CLI is the primary interface. The
optional API and web app use the same engine to start read-only runs and visualize every run stored
under the shared `.gamr` root, including CLI runs.

## Quick start

```bash
uv sync --all-packages --dev
uv run gamr doctor
uv run gamr dataset validate datasets/first-plan
uv run gamr experiment run datasets/first-plan
uv run gamr experiment run datasets/first-plan --all-cases
uv run gamr result validate .gamr/runs/<run-id>/result.json
uv run gamr chat
```

Live commands require `GAMR_TYR_MCP_TOKEN`, `GAMR_MODEL_API_KEY`, and `GAMR_MODEL_NAME`.
Experiments may run read-only or with Actions Allowed (`approval_required`). Action-enabled runs require explicit
confirmation; GAMR never approves actions automatically.

## Optional web interface

Local hot-reload (requires host Python and Node toolchains):

```bash
uv run poe dev
```

Or run the production-style containers (API + static web):

```bash
cp .env.example .env
# set GAMR_TYR_MCP_TOKEN, GAMR_MODEL_API_KEY, and GAMR_MODEL_NAME for live runs
docker compose up -d --build
```

The API listens on `http://127.0.0.1:6687` and the web app on
`http://127.0.0.1:6688`. Compose loads `.env`, mounts `./.gamr` for run artifacts and
`./datasets` read-only, and does not scale the API (one in-process queue). Host CLI runs that
write to `./.gamr` appear in the UI.

The service runs up to `GAMR_MAX_CONCURRENT_RUNS` experiments, defaulting to three, and
queues the rest in process. Restarted service work becomes `interrupted` and requires an explicit
retry.

All experiment definitions, live state, evidence, and results are JSON or JSONL files. There is no
database, migration service, broker, or worker process.

See [the scaffold contract](docs/SCAFFOLD_SPEC.md), [architecture](docs/architecture.md), and
[development guide](docs/development.md).
