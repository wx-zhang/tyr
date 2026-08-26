from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from gamr_adapters.artifacts.scientist_scenarios import (
    CatalogResult,
    CatalogState,
    ScientistScenarioCatalog,
    ScientistScenarioEntry,
    ScientistScenarioNotFound,
)
from gamr_adapters.config import Settings
from gamr_core import CaseResult, RunState, Scenario
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import get_settings
from ..errors import invalid_query, not_found

router = APIRouter(prefix="/api/v1/scientist-scenarios", tags=["scientist-scenarios"])


class ScientistScenarioResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    artifact_id: str = Field(alias="artifactId")
    scenario: Scenario
    task: str
    run_id: str = Field(alias="runId")
    run_state: RunState = Field(alias="runState")
    run_created_at: datetime = Field(alias="runCreatedAt")
    run_updated_at: datetime = Field(alias="runUpdatedAt")
    run_finished_at: datetime | None = Field(default=None, alias="runFinishedAt")
    archived_at: datetime | None = Field(default=None, alias="archivedAt")
    result_state: CatalogResult = Field(alias="resultState")
    result: CaseResult | None = None


def _response(entry: ScientistScenarioEntry) -> ScientistScenarioResponse:
    return ScientistScenarioResponse(
        artifactId=entry.artifact_id,
        scenario=entry.scenario,
        task=entry.task,
        runId=entry.run_id,
        runState=entry.run_state,
        runCreatedAt=entry.run_created_at,
        runUpdatedAt=entry.run_updated_at,
        runFinishedAt=entry.run_finished_at,
        archivedAt=entry.archived_at,
        resultState=entry.result_state,
        result=entry.result,
    )


def _catalog(settings: Settings) -> ScientistScenarioCatalog:
    return ScientistScenarioCatalog(settings.artifact_root)


@router.get("", response_model=list[ScientistScenarioResponse])
def list_scientist_scenarios(
    state: CatalogState = Query(default="active"),
    result: Literal[
        "vulnerable",
        "protected",
        "inconclusive",
        "not_applicable",
        "pending",
        "unavailable",
    ]
    | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> list[ScientistScenarioResponse]:
    try:
        return [_response(item) for item in _catalog(settings).list(state=state, result=result)]
    except ValueError as error:
        raise invalid_query(str(error)) from error


@router.put("/{run_id}/{artifact_id}/archive", response_model=ScientistScenarioResponse)
def archive_scientist_scenario(
    run_id: str,
    artifact_id: str,
    settings: Settings = Depends(get_settings),
) -> ScientistScenarioResponse:
    try:
        return _response(_catalog(settings).archive(run_id, artifact_id))
    except ScientistScenarioNotFound as error:
        raise not_found("scientist scenario") from error


@router.delete("/{run_id}/{artifact_id}/archive", response_model=ScientistScenarioResponse)
def restore_scientist_scenario(
    run_id: str,
    artifact_id: str,
    settings: Settings = Depends(get_settings),
) -> ScientistScenarioResponse:
    try:
        return _response(_catalog(settings).restore(run_id, artifact_id))
    except ScientistScenarioNotFound as error:
        raise not_found("scientist scenario") from error


@router.get("/{run_id}/{artifact_id}/export")
def export_scientist_scenario(
    run_id: str,
    artifact_id: str,
    settings: Settings = Depends(get_settings),
) -> Response:
    try:
        filename, content = _catalog(settings).export(run_id, artifact_id)
    except ScientistScenarioNotFound as error:
        raise not_found("scientist scenario") from error
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
