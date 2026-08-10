# Development

```bash
uv sync --all-packages --dev
corepack enable
uv run poe web-install
uv run gamr doctor
uv run gamr experiment run datasets/first-plan
uv run poe dev
uv run poe dev:watch
uv run poe schemas
uv run poe check
```

`poe dev` starts the API and Vite with hot reload on the host. `poe dev:watch` also reloads Python
changes.

Docker Compose builds runtime images (uvicorn API + nginx static web), not the Vite dev server:

```bash
cp .env.example .env
docker compose up -d --build
```

Compose loads `.env` for Tyr/model settings, overrides artifact/dataset paths inside the containers,
bind-mounts `./.gamr` (read-write) and `./datasets` (read-only), and publishes `6687` (API) and
`6688` (web). Host CLI runs that write to `./.gamr` remain visible in the web app. Do not scale the
`api` service; the run queue is in-process on a single API container.

If the browser must reach the API at a non-default origin, set `VITE_API_ORIGIN` and rebuild web:

```bash
VITE_API_ORIGIN=http://127.0.0.1:6687 docker compose up -d --build web
```

Default tests use fake ports. Live Tyr and model tests remain explicit and opt-in.
