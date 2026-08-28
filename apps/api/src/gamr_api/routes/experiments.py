from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from gamr_adapters.config import Settings
from gamr_adapters.tasks.filesystem import FilesystemTaskRepository, resolve_task_directory
from gamr_core import ExperimentPresetConfig
from pydantic import AliasChoices, BaseModel, Field

from ..dependencies import get_registry, get_settings, get_task_manager
from ..errors import not_found
from ..execution import RunTaskManager
from ..registry import ExperimentPresetRecord, InMemoryRegistry

router = APIRouter(prefix="/api/v1/experiments", tags=["experiments"])


class ExperimentPresetCreate(BaseModel):
    name: str = Field(min_length=1)
    task: str = "exfiltrate-important-txt"
    action_mode: str = Field(
        default="read_only",
        alias="actionMode",
        pattern=r"^(read_only|approval_required)$",
    )
    model: str = ""
    adversarial_researcher_model: str = Field(
        default="",
        alias="adversarialResearcherModel",
        validation_alias=AliasChoices("adversarialResearcherModel", "scientistModel"),
    )
    judge_model: str = Field(default="", alias="judgeModel")
    max_turns: int = Field(default=40, alias="maxTurns", ge=1)
    discovery_turns: int = Field(default=20, alias="discoveryTurns", ge=1)
    scenario_ids: list[str] | None = Field(
        default=None,
        alias="scenarioIds",
        validation_alias=AliasChoices("scenarioIds", "caseIds"),
    )
    research_iterations: int = Field(
        default=0,
        alias="researchIterations",
        validation_alias=AliasChoices("researchIterations", "scientistIterations"),
        ge=0,
    )
    max_concurrent_scenario_executions: int = Field(
        default=5,
        alias="maxConcurrentScenarioExecutions",
        validation_alias=AliasChoices("maxConcurrentScenarioExecutions", "maxConcurrentCases"),
        ge=1,
        le=5,
    )
    history_test_runs: int = Field(default=10, alias="historyTestRuns", ge=0, le=100)
    history_research_runs: int = Field(
        default=5,
        alias="historyResearchRuns",
        validation_alias=AliasChoices("historyResearchRuns", "historyScientistRuns"),
        ge=0,
        le=100,
    )

    model_config = {"populate_by_name": True, "extra": "forbid"}

    def configuration(self) -> ExperimentPresetConfig:
        return ExperimentPresetConfig(
            actionMode=self.action_mode,
            model=self.model,
            adversarialResearcherModel=self.adversarial_researcher_model,
            judgeModel=self.judge_model,
            maxTurns=self.max_turns,
            discoveryTurns=self.discovery_turns,
            scenarioIds=self.scenario_ids,
            maxConcurrentScenarioExecutions=self.max_concurrent_scenario_executions,
            researchIterations=self.research_iterations,
            historyTestRuns=self.history_test_runs,
            historyResearchRuns=self.history_research_runs,
        )


ExperimentCreate = ExperimentPresetCreate


def _normalize_task_reference(settings: Settings, reference: str) -> str:
    directory = resolve_task_directory(settings.task_root, reference)
    root = Path(settings.task_root).resolve()
    return directory.relative_to(root).as_posix()


def _preset_payload(item: ExperimentPresetRecord) -> dict[str, object]:
    return {
        "id": item.id,
        "name": item.name,
        "task": item.task,
        "configuration": item.configuration.model_dump(by_alias=True),
        "createdAt": item.created_at,
    }


@router.get("")
def list_experiment_presets(
    registry: InMemoryRegistry = Depends(get_registry),
) -> list[dict[str, object]]:
    return [_preset_payload(item) for item in registry.experiment_presets.values()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_experiment_preset(
    payload: ExperimentPresetCreate,
    registry: InMemoryRegistry = Depends(get_registry),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        task_ref = _normalize_task_reference(settings, payload.task)
        directory = resolve_task_directory(settings.task_root, task_ref)
        _, scenarios = FilesystemTaskRepository(settings.task_root).load(directory)
        if payload.scenario_ids is not None:
            known = {scenario.metadata.id for scenario in scenarios}
            missing = sorted(set(payload.scenario_ids) - known)
            if missing:
                raise ValueError(f"unknown scenario IDs: {missing}")
        configuration = payload.configuration()
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_task", "detail": str(error)},
        ) from error
    item = registry.create_experiment(payload.name, task_ref, configuration)
    return _preset_payload(item)


@router.get("/{experiment_id}")
def get_experiment_preset(
    experiment_id: str, registry: InMemoryRegistry = Depends(get_registry)
) -> dict[str, object]:
    item = registry.experiment_presets.get(experiment_id)
    if item is None:
        raise not_found("experiment preset")
    return _preset_payload(item)


class ExperimentStart(BaseModel):
    scenario_ids: list[str] | None = Field(
        default=None,
        alias="scenarioIds",
        validation_alias=AliasChoices("scenarioIds", "caseIds"),
    )
    max_concurrent_scenario_executions: int | None = Field(
        default=None,
        alias="maxConcurrentScenarioExecutions",
        validation_alias=AliasChoices("maxConcurrentScenarioExecutions", "maxConcurrentCases"),
        ge=1,
        le=5,
    )
    research_iterations: int | None = Field(
        default=None,
        alias="researchIterations",
        validation_alias=AliasChoices("researchIterations", "scientistIterations"),
        ge=0,
    )
    history_test_runs: int | None = Field(default=None, alias="historyTestRuns", ge=0, le=100)
    history_research_runs: int | None = Field(
        default=None,
        alias="historyResearchRuns",
        validation_alias=AliasChoices("historyResearchRuns", "historyScientistRuns"),
        ge=0,
        le=100,
    )

    model_config = {"populate_by_name": True, "extra": "forbid"}


RunCreate = ExperimentStart


@router.post("/{experiment_id}/runs", status_code=status.HTTP_202_ACCEPTED)
async def start_experiment(
    experiment_id: str,
    payload: ExperimentStart | None = None,
    registry: InMemoryRegistry = Depends(get_registry),
    manager: RunTaskManager | None = Depends(get_task_manager),
) -> dict[str, object]:
    item = registry.experiment_presets.get(experiment_id)
    if item is None:
        raise not_found("experiment preset")
    values = item.configuration.model_dump()
    if payload is not None:
        overrides = payload.model_dump(exclude_none=True)
        values.update(overrides)
    try:
        configuration = ExperimentPresetConfig.model_validate(values)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_configuration", "detail": str(error)},
        ) from error
    experiment = registry.create_run(item.id, item.task, configuration, name=item.name)
    if manager is not None:
        await manager.submit(experiment.id)
    return {
        "id": experiment.id,
        "state": experiment.state,
        "statusUrl": f"/api/v1/runs/{experiment.id}",
    }


start_run = start_experiment
