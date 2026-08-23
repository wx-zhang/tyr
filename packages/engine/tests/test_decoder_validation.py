from __future__ import annotations

import json
from collections.abc import Sequence

import pytest
from gamr_core import DecodingFailureCode, DecodingStatus
from gamr_engine.content_source import VerifiedContentSnapshot
from gamr_engine.decoder.agent import DecoderAgent
from gamr_engine.ports.models import ChatModelGateway
from gamr_engine.ports.sandbox import (
    ExecutionResult,
    Sandbox,
    SandboxEntry,
    SandboxId,
    SandboxIsolation,
)


class FakeChatModel(ChatModelGateway):
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = list(responses)
        self.call_count = 0
        self.messages_seen: list[list[dict[str, object]]] = []
        self.tools_seen: list[list[dict[str, object]] | None] = []

    async def chat(
        self,
        messages: list[dict[str, object]],
        *,
        tools: list[dict[str, object]] | None = None,
        max_tokens: int = 1024,
    ) -> dict[str, object]:
        self.messages_seen.append(messages)
        self.tools_seen.append(tools)
        if self.call_count < len(self.responses):
            res = self.responses[self.call_count]
            self.call_count += 1
            return res
        return {
            "message": {
                "role": "assistant",
                "content": '{"action":"direct","rationale":"already readable"}',
            }
        }


class FakeSandbox(Sandbox):
    def __init__(self, isolation: SandboxIsolation = "contained") -> None:
        self._isolation: SandboxIsolation = isolation
        self.started_count = 0
        self.closed_count = 0

    @property
    def isolation(self) -> SandboxIsolation:
        return self._isolation

    async def start(self, entries: Sequence[SandboxEntry] = ()) -> SandboxId:
        self.started_count += 1
        return SandboxId("fake-sandbox-1")

    async def execute(self, sandbox_id: SandboxId, source: str | bytes) -> ExecutionResult:
        return ExecutionResult(0, "stdout", "stderr", 0.1)

    async def collect_output(self, sandbox_id: SandboxId, output_dir: str) -> list[SandboxEntry]:
        return []

    async def close(self, sandbox_id: SandboxId) -> None:
        self.closed_count += 1


def _sample_snapshot() -> VerifiedContentSnapshot:
    return VerifiedContentSnapshot(
        snapshot_id="upload-001",
        source_file_id="file-1",
        filename="data.txt",
        content_type="text/plain",
        size=4,
        sha256="0" * 64,
        content=b"test",
    )


@pytest.mark.asyncio
async def test_direct_decision_skips_sandbox() -> None:
    model = FakeChatModel(
        [
            {
                "message": {
                    "role": "assistant",
                    "content": '{"action":"direct","rationale":"already readable"}',
                }
            }
        ]
    )
    sandbox = FakeSandbox()
    agent = DecoderAgent(
        model=model,
        sandbox=sandbox,
        snapshots=[_sample_snapshot()],
        task_context="task",
        case_fields={"title": "case"},
        evaluation_criteria="crit",
        transcript=[],
    )

    result = await agent.run()

    assert result.action == "direct"
    assert result.provenance.status == DecodingStatus.SKIPPED
    assert sandbox.started_count == 0


@pytest.mark.asyncio
async def test_malformed_arguments_fails_closed_without_sandbox() -> None:
    model = FakeChatModel(
        [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "execute_python",
                                "arguments": "{bad_json",
                            },
                        }
                    ],
                }
            }
        ]
    )
    sandbox = FakeSandbox()
    agent = DecoderAgent(
        model=model,
        sandbox=sandbox,
        snapshots=[_sample_snapshot()],
        task_context="task",
        case_fields={"title": "case"},
        evaluation_criteria="crit",
        transcript=[],
    )

    result = await agent.run()

    assert result.action == "failed"
    assert result.provenance.status == DecodingStatus.FAILED
    assert result.provenance.failure_code == DecodingFailureCode.INVALID_AGENT_RESPONSE
    assert sandbox.started_count == 0


@pytest.mark.asyncio
async def test_oversized_source_fails_closed_without_sandbox() -> None:
    huge_source = "x = 1\n" * 20000  # > 64 KB
    model = FakeChatModel(
        [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "execute_python",
                                "arguments": json.dumps(
                                    {"source": huge_source, "rationale": "transform upload"}
                                ),
                            },
                        }
                    ],
                }
            }
        ]
    )
    sandbox = FakeSandbox()
    agent = DecoderAgent(
        model=model,
        sandbox=sandbox,
        snapshots=[_sample_snapshot()],
        task_context="task",
        case_fields={"title": "case"},
        evaluation_criteria="crit",
        transcript=[],
    )

    result = await agent.run()

    assert result.action == "failed"
    assert result.provenance.status == DecodingStatus.FAILED
    assert result.provenance.failure_code == DecodingFailureCode.INVALID_AGENT_RESPONSE
    assert sandbox.started_count == 0


@pytest.mark.asyncio
async def test_unknown_tool_fails_closed_without_sandbox() -> None:
    model = FakeChatModel(
        [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "execute_bash",
                                "arguments": json.dumps({"cmd": "ls"}),
                            },
                        }
                    ],
                }
            }
        ]
    )
    sandbox = FakeSandbox()
    agent = DecoderAgent(
        model=model,
        sandbox=sandbox,
        snapshots=[_sample_snapshot()],
        task_context="task",
        case_fields={"title": "case"},
        evaluation_criteria="crit",
        transcript=[],
    )

    result = await agent.run()

    assert result.action == "failed"
    assert result.provenance.status == DecodingStatus.FAILED
    assert result.provenance.failure_code == DecodingFailureCode.UNKNOWN_TOOL_OR_INPUT
    assert sandbox.started_count == 0


@pytest.mark.asyncio
async def test_parallel_tool_calls_rejected_without_sandbox() -> None:
    model = FakeChatModel(
        [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "execute_python",
                                "arguments": json.dumps(
                                    {"source": "print(1)", "rationale": "transform upload"}
                                ),
                            },
                        },
                        {
                            "id": "call_2",
                            "type": "function",
                            "function": {
                                "name": "execute_python",
                                "arguments": json.dumps(
                                    {"source": "print(2)", "rationale": "transform upload"}
                                ),
                            },
                        },
                    ],
                }
            }
        ]
    )
    sandbox = FakeSandbox()
    agent = DecoderAgent(
        model=model,
        sandbox=sandbox,
        snapshots=[_sample_snapshot()],
        task_context="task",
        case_fields={"title": "case"},
        evaluation_criteria="crit",
        transcript=[],
    )

    result = await agent.run()

    assert result.action == "failed"
    assert result.provenance.status == DecodingStatus.FAILED
    assert result.provenance.failure_code == DecodingFailureCode.INVALID_AGENT_RESPONSE
    assert sandbox.started_count == 0


@pytest.mark.asyncio
async def test_model_refusal_or_empty_response_fails_closed() -> None:
    model = FakeChatModel(
        [{"message": {"role": "assistant", "content": ""}, "refusal": "Cannot assist with coding"}]
    )
    sandbox = FakeSandbox()
    agent = DecoderAgent(
        model=model,
        sandbox=sandbox,
        snapshots=[_sample_snapshot()],
        task_context="task",
        case_fields={"title": "case"},
        evaluation_criteria="crit",
        transcript=[],
    )

    result = await agent.run()

    assert result.action == "failed"
    assert result.provenance.status == DecodingStatus.FAILED
    assert result.provenance.failure_code == DecodingFailureCode.INVALID_AGENT_RESPONSE
    assert sandbox.started_count == 0


@pytest.mark.asyncio
async def test_invalid_final_response_json_fails_closed() -> None:
    model = FakeChatModel(
        [{"message": {"role": "assistant", "content": "I am done, no files needed."}}]
    )
    sandbox = FakeSandbox()
    agent = DecoderAgent(
        model=model,
        sandbox=sandbox,
        snapshots=[_sample_snapshot()],
        task_context="task",
        case_fields={"title": "case"},
        evaluation_criteria="crit",
        transcript=[],
    )

    result = await agent.run()

    assert result.action == "failed"
    assert result.provenance.status == DecodingStatus.FAILED
    assert result.provenance.failure_code == DecodingFailureCode.INVALID_AGENT_RESPONSE
    assert sandbox.started_count == 0
