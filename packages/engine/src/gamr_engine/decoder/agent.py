from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from ..content_source import VerifiedContentSnapshot
from ..ports.models import ChatModelGateway
from ..ports.sandbox import Sandbox
from .loop import DecoderExecutionLoop, DecoderLoopResult


class DecoderAgent:
    def __init__(
        self,
        *,
        model: ChatModelGateway,
        sandbox: Sandbox,
        snapshots: Sequence[VerifiedContentSnapshot],
        task_context: str,
        case_fields: dict[str, object],
        evaluation_criteria: str,
        transcript: list[dict[str, object]],
        max_attempts: int = 3,
        activity_sink: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._loop = DecoderExecutionLoop(
            model=model,
            sandbox=sandbox,
            snapshots=snapshots,
            task_context=task_context,
            case_fields=case_fields,
            evaluation_criteria=evaluation_criteria,
            transcript=transcript,
            max_attempts=max_attempts,
            activity_sink=activity_sink,
        )

    async def run(self) -> DecoderLoopResult:
        return await self._loop.run()
