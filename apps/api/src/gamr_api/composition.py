from __future__ import annotations

from gamr_adapters.artifacts.evidence import FilesystemActivitySink
from gamr_adapters.artifacts.filesystem import FilesystemArtifactStore
from gamr_adapters.config import Settings
from gamr_adapters.datasets.filesystem import load_dataset, resolve_dataset_directory
from gamr_adapters.models.openai_compatible import OpenAICompatibleModel
from gamr_adapters.tyr.client import TyrMcpClient
from gamr_engine import ExperimentExecutionService

from .execution import RunExecutor
from .registry import JsonRegistry


def build_run_executor(settings: Settings, registry: JsonRegistry) -> RunExecutor:
    async def execute(run_id: str) -> str:
        run = registry.get_run(run_id)
        if run is None:
            raise ValueError("run does not exist")
        if not settings.tyr_mcp_token or not settings.model_api_key:
            raise ValueError("GAMR_TYR_MCP_TOKEN and GAMR_MODEL_API_KEY are required")
        selected_model = run.configuration.model or settings.model_name
        if not selected_model:
            raise ValueError("GAMR_MODEL_NAME is required")
        run.configuration = run.configuration.model_copy(update={"model": selected_model})
        registry.save_run(run)
        dataset_path = resolve_dataset_directory(settings.dataset_root, run.dataset)
        dataset = load_dataset(dataset_path)
        artifacts = FilesystemArtifactStore(
            settings.artifact_root,
            secrets=(settings.tyr_mcp_token, settings.model_api_key),
        )
        target = TyrMcpClient(settings.tyr_mcp_url, settings.tyr_mcp_token)
        model = OpenAICompatibleModel(
            settings.model_base_url,
            settings.model_api_key,
            selected_model,
        )
        try:
            output = await ExperimentExecutionService().execute(
                dataset,
                run.configuration,
                run_id=run.id,
                target=target,
                model=model,
                artifacts=artifacts,
                activity_sink=FilesystemActivitySink(artifacts),
            )
        finally:
            await target.aclose()
        return output.result_path

    return execute
