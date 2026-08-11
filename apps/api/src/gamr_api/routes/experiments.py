from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from gamr_adapters.config import Settings
from gamr_adapters.datasets.filesystem import (
    FilesystemDatasetRepository,
    resolve_dataset_directory,
)
from gamr_core import ExperimentConfig
from pydantic import BaseModel, Field

from ..dependencies import get_registry, get_settings, get_task_manager
from ..errors import not_found
from ..execution import RunTaskManager
from ..registry import InMemoryRegistry

router = APIRouter(prefix="/api/v1/experiments", tags=["experiments"])


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1)
    dataset: str = "first-plan"
    action_mode: str = Field(
        default="read_only",
        alias="actionMode",
        pattern=r"^(read_only|approval_required)$",
    )
    model: str = ""
    max_turns: int = Field(default=40, alias="maxTurns", ge=1)
    discovery_turns: int = Field(default=20, alias="discoveryTurns", ge=1)
    case_ids: list[str] | None = Field(default=None, alias="caseIds")
    scientist_iterations: int = Field(default=0, alias="scientistIterations", ge=0)

    model_config = {"populate_by_name": True, "extra": "forbid"}

    def configuration(self) -> ExperimentConfig:
        return ExperimentConfig(
            actionMode=self.action_mode,
            model=self.model,
            maxTurns=self.max_turns,
            discoveryTurns=self.discovery_turns,
            caseIds=self.case_ids,
            scientistIterations=self.scientist_iterations,
        )


def _normalize_dataset_reference(settings: Settings, reference: str) -> str:
    directory = resolve_dataset_directory(settings.dataset_root, reference)
    root = Path(settings.dataset_root).resolve()
    return directory.relative_to(root).as_posix()


@router.get("")
def list_experiments(registry: InMemoryRegistry = Depends(get_registry)) -> list[dict[str, object]]:
    return [
        {
            "id": item.id,
            "name": item.name,
            "dataset": item.dataset,
            "configuration": item.configuration.model_dump(by_alias=True),
            "createdAt": item.created_at,
        }
        for item in registry.experiments.values()
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_experiment(
    payload: ExperimentCreate,
    registry: InMemoryRegistry = Depends(get_registry),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        dataset_ref = _normalize_dataset_reference(settings, payload.dataset)
        directory = resolve_dataset_directory(settings.dataset_root, dataset_ref)
        _, scenarios = FilesystemDatasetRepository(settings.dataset_root).load(directory)
        if payload.case_ids is not None:
            known = {scenario.metadata.id for scenario in scenarios}
            missing = sorted(set(payload.case_ids) - known)
            if missing:
                raise ValueError(f"unknown case ids: {missing}")
        configuration = payload.configuration()
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_dataset", "detail": str(error)},
        ) from error
    item = registry.create_experiment(payload.name, dataset_ref, configuration)
    return {
        "id": item.id,
        "name": item.name,
        "dataset": item.dataset,
        "configuration": item.configuration.model_dump(by_alias=True),
        "createdAt": item.created_at,
    }


@router.get("/{experiment_id}")
def get_experiment(
    experiment_id: str, registry: InMemoryRegistry = Depends(get_registry)
) -> dict[str, object]:
    item = registry.experiments.get(experiment_id)
    if item is None:
        raise not_found("experiment")
    return {
        "id": item.id,
        "name": item.name,
        "dataset": item.dataset,
        "configuration": item.configuration.model_dump(by_alias=True),
        "createdAt": item.created_at,
    }


class RunCreate(BaseModel):
    case_ids: list[str] | None = Field(default=None, alias="caseIds")
    scientist_iterations: int | None = Field(default=None, alias="scientistIterations", ge=0)

    model_config = {"populate_by_name": True, "extra": "forbid"}


@router.post("/{experiment_id}/runs", status_code=status.HTTP_202_ACCEPTED)
async def start_run(
    experiment_id: str,
    payload: RunCreate | None = None,
    registry: InMemoryRegistry = Depends(get_registry),
    manager: RunTaskManager | None = Depends(get_task_manager),
) -> dict[str, object]:
    item = registry.experiments.get(experiment_id)
    if item is None:
        raise not_found("experiment")
    configuration = item.configuration.model_copy(
        update={
            "case_ids": (
                payload.case_ids
                if payload and payload.case_ids is not None
                else item.configuration.case_ids
            ),
            "scientist_iterations": (
                payload.scientist_iterations
                if payload and payload.scientist_iterations is not None
                else item.configuration.scientist_iterations
            ),
        }
    )
    run = registry.create_run(item.id, item.dataset, configuration, name=item.name)
    if manager is not None:
        await manager.submit(run.id)
    return {"id": run.id, "state": run.state, "statusUrl": f"/api/v1/runs/{run.id}"}
