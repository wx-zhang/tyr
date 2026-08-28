from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from gamr_adapters.artifacts.scientist_scenarios import (
    AdversarialResearcherCatalog,
    AdversarialResearcherScenarioEntry,
    AdversarialResearcherScenarioNotFound,
    CatalogResult,
    CatalogState,
)
from gamr_adapters.config import Settings
from gamr_core import ExperimentState, Scenario, ScenarioExecutionResult
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from ..dependencies import get_settings
from ..errors import invalid_query, not_found

router = APIRouter(prefix="/api/v1/scientist-scenarios", tags=["adversarial-researcher"])


class AdversarialResearcherScenarioResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    artifact_id: str = Field(alias="artifactId")
    scenario: Scenario
    task: str
    experiment_id: str = Field(
        alias="experimentId", validation_alias=AliasChoices("experimentId", "runId")
    )
    experiment_state: ExperimentState = Field(
        alias="experimentState", validation_alias=AliasChoices("experimentState", "runState")
    )
    experiment_created_at: datetime = Field(
        alias="experimentCreatedAt",
        validation_alias=AliasChoices("experimentCreatedAt", "runCreatedAt"),
    )
    experiment_updated_at: datetime = Field(
        alias="experimentUpdatedAt",
        validation_alias=AliasChoices("experimentUpdatedAt", "runUpdatedAt"),
    )
    experiment_finished_at: datetime | None = Field(
        default=None,
        alias="experimentFinishedAt",
        validation_alias=AliasChoices("experimentFinishedAt", "runFinishedAt"),
    )
    archived_at: datetime | None = Field(default=None, alias="archivedAt")
    result_state: CatalogResult = Field(alias="resultState")
    result: ScenarioExecutionResult | None = None


ScientistScenarioResponse = AdversarialResearcherScenarioResponse


def _response(entry: AdversarialResearcherScenarioEntry) -> AdversarialResearcherScenarioResponse:
    return AdversarialResearcherScenarioResponse(
        artifactId=entry.artifact_id,
        scenario=entry.scenario,
        task=entry.task,
        experimentId=entry.run_id,
        experimentState=entry.run_state,
        experimentCreatedAt=entry.run_created_at,
        experimentUpdatedAt=entry.run_updated_at,
        experimentFinishedAt=entry.run_finished_at,
        archivedAt=entry.archived_at,
        resultState=entry.result_state,
        result=entry.result,
    )


def _catalog(settings: Settings) -> AdversarialResearcherCatalog:
    return AdversarialResearcherCatalog(settings.artifact_root)


@router.get("", response_model=list[AdversarialResearcherScenarioResponse])
def list_adversarial_researcher_scenarios(
    state: CatalogState = Query(default="active"),
    result: Literal[
        "vulnerable", "protected", "inconclusive", "not_applicable", "pending", "unavailable"
    ]
    | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> list[AdversarialResearcherScenarioResponse]:
    try:
        return [_response(item) for item in _catalog(settings).list(state=state, result=result)]
    except ValueError as error:
        raise invalid_query(str(error)) from error


@router.put("/{run_id}/{artifact_id}/archive", response_model=AdversarialResearcherScenarioResponse)
def archive_adversarial_researcher_scenario(
    run_id: str, artifact_id: str, settings: Settings = Depends(get_settings)
) -> AdversarialResearcherScenarioResponse:
    try:
        return _response(_catalog(settings).archive(run_id, artifact_id))
    except AdversarialResearcherScenarioNotFound as error:
        raise not_found("Adversarial Researcher Scenario") from error


@router.delete(
    "/{run_id}/{artifact_id}/archive",
    response_model=AdversarialResearcherScenarioResponse,
)
def restore_adversarial_researcher_scenario(
    run_id: str, artifact_id: str, settings: Settings = Depends(get_settings)
) -> AdversarialResearcherScenarioResponse:
    try:
        return _response(_catalog(settings).restore(run_id, artifact_id))
    except AdversarialResearcherScenarioNotFound as error:
        raise not_found("Adversarial Researcher Scenario") from error


@router.get("/{run_id}/{artifact_id}/export")
def export_adversarial_researcher_scenario(
    run_id: str, artifact_id: str, settings: Settings = Depends(get_settings)
) -> Response:
    try:
        filename, content = _catalog(settings).export(run_id, artifact_id)
    except AdversarialResearcherScenarioNotFound as error:
        raise not_found("Adversarial Researcher Scenario") from error
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


list_scientist_scenarios = list_adversarial_researcher_scenarios
archive_scientist_scenario = archive_adversarial_researcher_scenario
restore_scientist_scenario = restore_adversarial_researcher_scenario
export_scientist_scenario = export_adversarial_researcher_scenario
