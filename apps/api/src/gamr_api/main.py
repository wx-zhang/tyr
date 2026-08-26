from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .composition import build_run_executor
from .dependencies import get_registry, get_settings
from .execution import RunTaskManager
from .registry import JsonRegistry
from .routes import (
    collector_artifacts,
    experiments,
    health,
    run_evidence,
    runs,
    scientist_scenarios,
    tasks,
)


def _web_origins(origin: str) -> list[str]:
    origins = [origin]
    for hostname in ("127.0.0.1", "localhost"):
        if hostname in origin:
            alternate = "localhost" if hostname == "127.0.0.1" else "127.0.0.1"
            origins.append(origin.replace(hostname, alternate, 1))
            break
    return origins


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    registry = get_registry()
    if not isinstance(registry, JsonRegistry):
        yield
        return
    manager = RunTaskManager(
        registry,
        build_run_executor(settings, registry),
        max_concurrent_runs=settings.max_concurrent_runs,
    )
    application.state.run_task_manager = manager
    await manager.start()
    try:
        yield
    finally:
        await manager.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="GAMR",
        description="Tyr's final opponent. Red-team experiment API for Tyr (https://tyr.ai/).",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_web_origins(settings.web_origin),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health.router)
    application.include_router(tasks.router)
    application.include_router(experiments.router)
    application.include_router(runs.router)
    application.include_router(run_evidence.router)
    application.include_router(collector_artifacts.router)
    application.include_router(scientist_scenarios.router)
    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("gamr_api.main:app", host="127.0.0.1", port=6687, reload=False)
