# Script scope

## Purpose

Own deterministic schema export, local seed utilities, and the interactive Oh My Pi installer.

## Standards

Python utilities must be importable, fail clearly, avoid network calls, and write only their documented generated targets.

`install-omp.sh` is an interactive macOS/Linux setup command. It may download official installers only after explicit consent. `--dry` must never write files, request keys, launch applications, or make network requests. Keep credentials out of output and repository backups; test with isolated home directories and fake external commands.

`export_operational_schemas.py` exports the JSON-only experiment and live-run contracts.
`render_judge_graph.py` provides offline, deterministic PIL-based topology rendering for registered judge pipelines via `uv run poe judge-graph <judge-directory>`, writing PNG images to `docs/assets/judges/`.
`sandbox_run.py` exercises the shared sandbox lifecycle via `uv run poe sandbox-run`.
`sandbox_build.py` builds the fixed sandbox image via `uv run poe sandbox-build` with a confined adapter-package context.

Run `./scripts/install-omp.sh --dry` to preview setup and `uv run pytest tests/test_install_omp.py` for installer regressions. User instructions live in `docs/oh-my-pi/how-to.md`.
