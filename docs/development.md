# Development

```bash
uv sync --all-packages --dev
corepack enable
uv run poe web-install
uv run gamr doctor
uv run gamr experiment run tasks/exfiltrate-important-txt
uv run poe judge-graph packages/engine/src/gamr_engine/judges/evidence_and_content
uv run poe sandbox-build
uv run poe sandbox-run --attach <path> --code "<source>"
uv run poe dev
uv run poe dev:watch
uv run poe schemas
uv run poe check
```

`poe judge-graph <judge-directory>` renders a deterministic PNG topology image for the specified predefined judge pipeline to `docs/assets/judges/` via atomic file replacement.

`poe dev` starts the API and Vite with hot reload on the host. `poe dev:watch` also reloads Python
changes.

Docker Compose builds runtime images (uvicorn API + nginx static web), not the Vite dev server:

```bash
cp .env.example .env
docker compose up -d --build
```

Compose loads `.env` for Tyr/model settings, overrides artifact/task paths inside the containers,
bind-mounts `./.gamr` (read-write) and `./tasks` (read-only), and publishes `6687` (API) and
`6688` (web). Host CLI runs that write to `./.gamr` remain visible in the web app. Do not scale the
`api` service; the run queue is in-process on a single API container.

If the browser must reach the API at a non-default origin, set `VITE_API_ORIGIN` and rebuild web:

```bash
VITE_API_ORIGIN=http://127.0.0.1:6687 docker compose up -d --build web
```

Default tests use fake ports. Live Tyr and model tests remain explicit and opt-in.
Sandbox Docker runtime tests are also opt-in:

```bash
uv run pytest -m sandbox_docker
```

The default `docker` sandbox backend is not probed during settings composition. Build its fixed
Python 3.14 image before using `sandbox-run` or running reference-aware decoding cases; Docker
resources carry `com.tyr.gamr.sandbox=true` labels for orphan diagnosis. Trajectory decoding
invokes the sandbox under process-wide capacity control (`GAMR_MAX_CONCURRENT_DECODERS`, defaulting to 2).
The sandbox runs Python 3.14 with only the standard library, read-only `/input`, ephemeral `/workspace`,
no network access, and strict limits (64 KiB code, 256 files, 64 MiB attachments, 10s execution, 1 MiB output).
Decoder prompts advertise `/input/<opaque-id>/<filename>` and the sandbox receives the corresponding
relative logical attachment path. The decoder reuses one healthy sandbox instance across up to three
tool calls per case. If decoding fails, the pipeline fails closed to inconclusive. Sensitive reference
data, credentials, and raw tool transcripts are excluded from context and artifacts; the result and
report retain only redacted source, bounded execution states, route rationale, hashes, and lineage.
Remove only labeled resources owned by the current
GAMR process after an unexpected exit. The Docker backend has no restart policy and never adopts resources
from a previous process.

Use `GAMR_SANDBOX_BACKEND=host-unsafe` only for local controlled snippets. It is not containment:
the child runs with the current user's host permissions. Use `disabled` to keep unrelated GAMR
commands usable on a machine where sandbox execution is not wanted. Decoder workflows in the engine
require contained sandbox isolation and fail safely if sandbox execution is disabled or unsafe.
