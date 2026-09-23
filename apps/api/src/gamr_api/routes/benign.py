from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from gamr_adapters.benign_config import BenignSettings
from gamr_adapters.benign_model import BenignGenerationError, BenignModel
from gamr_adapters.benign_store import BenignStore
from gamr_adapters.benign_worker import BenignWorker
from gamr_adapters.config import Settings
from gamr_core.benign import BenignRun, BenignScenario, Contract, Submission
from pydantic import Field

router = APIRouter(prefix="/api/v1/benign", tags=["benign"])


def get_benign_settings() -> BenignSettings:
    return BenignSettings()


Configuration = Annotated[BenignSettings, Depends(get_benign_settings)]


class DraftRequest(Contract):
    text: str = Field(min_length=1, max_length=20000)
    workspace: str
    timezone: str


class WorkspaceOption(Contract):
    alias: str
    configured: bool


def public_run(run: BenignRun, settings: BenignSettings) -> BenignRun:
    text = run.model_dump_json()
    secrets = [Settings().model_api_key]
    for binding in settings.bindings().values():
        try:
            secrets.append(settings.token(binding))
        except ValueError:
            pass
    for secret in secrets:
        if secret:
            text = text.replace(json.dumps(secret)[1:-1], "[credential omitted]")
    return BenignRun.model_validate_json(text)


@router.get("/workspaces")
def workspaces(settings: Configuration) -> list[WorkspaceOption]:
    result = []
    for alias, binding in settings.bindings().items():
        try:
            settings.token(binding)
            configured = True
        except ValueError:
            configured = False
        result.append(WorkspaceOption(alias=alias, configured=configured))
    return result


@router.post("/drafts")
async def draft(body: DraftRequest, settings: Configuration) -> BenignScenario:
    try:
        return await BenignModel(BenignStore(settings.root)).draft(
            body.text,
            body.workspace,
            body.timezone,
        )
    except BenignGenerationError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/runs", status_code=202)
def submit(body: Submission, settings: Configuration) -> list[BenignRun]:
    try:
        settings.validate_submission(body)
        return BenignStore(settings.root).enqueue(body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/runs")
def list_runs(
    settings: Configuration,
    limit: int = Query(100, ge=1, le=1000),
    batch_id: str | None = None,
) -> list[BenignRun]:
    runs = BenignStore(settings.root).list_runs()
    selected = [run for run in reversed(runs) if batch_id is None or run.batch_id == batch_id]
    return [
        public_run(run.model_copy(update={"observations": {}, "checkpoints": {}}), settings)
        for run in selected[:limit]
    ]


@router.get("/runs/{run_id}")
def read_run(run_id: str, settings: Configuration) -> BenignRun:
    try:
        return public_run(BenignStore(settings.root).read(run_id), settings)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(404, "Run not found") from exc


@router.post("/runs/{run_id}/resume", status_code=202)
def resume(run_id: str, settings: Configuration) -> dict[str, str]:
    try:
        BenignWorker(settings).resume(run_id)
        return {"status": "queued"}
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(409, "Run must be pending and inactive") from exc
