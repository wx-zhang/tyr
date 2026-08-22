## Why

Future GAMR agents and judge pipelines need to inspect attached files with generated Python without exposing the GAMR process, credentials, or host filesystem to that code. GAMR currently has no shared execution boundary or lifecycle contract for this work, so the containment capability must be established before a judge is allowed to use it.

## What Changes

- Add an engine-owned asynchronous sandbox lifecycle contract for starting an isolated instance with attached files or directory trees, executing Python fragments repeatedly, and closing the instance by opaque ID.
- Add a Docker backend as the default containment boundary, with a fixed Python 3.14 standard-library image, no network, no host mounts, no application secrets, a read-only input tree, a persistent ephemeral workspace, and fixed resource limits.
- Add an explicitly unsafe host subprocess backend with temporary storage and best-effort limits, plus a disabled backend that rejects sandbox creation without disabling unrelated GAMR features.
- Configure backend selection with `GAMR_SANDBOX_BACKEND=docker|host-unsafe|disabled`, defaulting to `docker`.
- Add `uv run poe sandbox-build` to build the Docker image and `uv run poe sandbox-run` to exercise a complete start, execute, and close flow before a production consumer is introduced.
- Add contract, rejection-path, lifecycle, and opt-in Docker integration tests without requiring Docker in the default test suite.
- Keep judge, task, API, web, and canonical run-result behavior unchanged; integration with an agent or judge is deferred to a later change.

## Capabilities

### New Capabilities

- `python-execution-sandbox`: Defines the sandbox lifecycle, attachment model, execution results, backend selection, containment controls, failure behavior, and developer commands.

### Modified Capabilities

None.

## Impact

- `gamr-engine` gains sandbox contracts and the port consumed by future workflows.
- `gamr-adapters` gains backend selection, Docker and host subprocess implementations, ephemeral storage, and the Docker image definition.
- Shared adapter settings gain one non-secret environment variable.
- Root poe tasks and a small developer runner compose the same sandbox adapter path future consumers will use.
- Repository, development, environment, and adapter ownership documentation must describe the new commands and configuration.
- Docker is required only for the default backend and opt-in integration checks; default tests continue to use controlled local or fake implementations.
