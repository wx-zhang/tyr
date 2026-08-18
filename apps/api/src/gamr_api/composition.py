from __future__ import annotations

from gamr_adapters.artifacts.evidence import FilesystemActivitySink
from gamr_adapters.artifacts.filesystem import FilesystemArtifactStore
from gamr_adapters.collector import CollectorClient
from gamr_adapters.config import Settings
from gamr_adapters.models.openai_compatible import OpenAICompatibleModel
from gamr_adapters.tasks.filesystem import load_task, resolve_task_directory
from gamr_adapters.tyr.client import TyrMcpClient
from gamr_core import RunState
from gamr_engine import ExperimentExecutionService, ProgressEvent

from .execution import RunExecutor
from .registry import JsonRegistry


def _advance_run_state(registry: JsonRegistry, run_id: str, event: ProgressEvent) -> None:
    if event.phase not in {"case", "assessment", "scientist"}:
        return
    current = registry.get_run(run_id)
    if current is not None and current.state is RunState.DISCOVERING:
        registry.set_state(current, RunState.RUNNING)


def build_run_executor(settings: Settings, registry: JsonRegistry) -> RunExecutor:
    async def execute(run_id: str) -> str:
        run = registry.get_run(run_id)
        if run is None:
            raise ValueError("run does not exist")
        if not settings.tyr_mcp_token or not settings.model_api_key:
            raise ValueError("TYR_MCP_TOKEN and OPENROUTER_API_KEY are required")
        selected_model = run.configuration.model or settings.model_name
        if not selected_model:
            raise ValueError("TYR_LOOP_MODEL is required")
        selected_scientist_model = (
            run.configuration.scientist_model or settings.scientist_model_name or selected_model
        )
        selected_judge_model = (
            run.configuration.judge_model
            or getattr(settings, "judge_model_name", "")
            or selected_model
        )
        run.configuration = run.configuration.model_copy(
            update={
                "model": selected_model,
                "scientist_model": selected_scientist_model,
                "judge_model": selected_judge_model,
            }
        )
        registry.save_run(run)
        task_path = resolve_task_directory(settings.task_root, run.task)
        task = load_task(task_path)
        artifacts = FilesystemArtifactStore(
            settings.artifact_root,
            secrets=(
                settings.tyr_mcp_token,
                settings.model_api_key,
                settings.collector_username,
                settings.collector_password,
            ),
        )
        collector = (
            CollectorClient(
                settings.collector_base_url,
                settings.collector_username,
                settings.collector_password,
            )
            if settings.collector_username and settings.collector_password
            else None
        )
        target = TyrMcpClient(settings.tyr_mcp_url, settings.tyr_mcp_token)
        model = OpenAICompatibleModel(
            settings.model_base_url,
            settings.model_api_key,
            selected_model,
        )
        scientist_model = (
            model
            if selected_scientist_model == selected_model
            else OpenAICompatibleModel(
                settings.model_base_url,
                settings.model_api_key,
                selected_scientist_model,
            )
        )
        judge_model = (
            model
            if selected_judge_model == selected_model
            else OpenAICompatibleModel(
                settings.model_base_url,
                settings.model_api_key,
                selected_judge_model,
            )
        )
        try:
            output = await ExperimentExecutionService().execute(
                task,
                run.configuration,
                run_id=run.id,
                target=target,
                model=model,
                scientist_model=scientist_model,
                judge_model=judge_model,
                artifacts=artifacts,
                activity_sink=FilesystemActivitySink(artifacts),
                progress=lambda event: _advance_run_state(registry, run_id, event),
                delivery_verifier=collector,
            )
        finally:
            await target.aclose()
            if collector is not None:
                await collector.aclose()
        return output.result_path

    return execute
