from __future__ import annotations

import json
from collections.abc import Sequence

import pytest
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


class SecrecyTrackingChatModel(ChatModelGateway):
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = list(responses)
        self.call_count = 0
        self.history_records: list[list[dict[str, object]]] = []
        self.tools_seen: list[list[dict[str, object]] | None] = []

    async def chat(
        self,
        messages: list[dict[str, object]],
        *,
        tools: list[dict[str, object]] | None = None,
        max_tokens: int = 1024,
    ) -> dict[str, object]:
        self.history_records.append(messages)
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


class ScriptableSandbox(Sandbox):
    def __init__(
        self,
        isolation: SandboxIsolation = "contained",
        exec_results: list[ExecutionResult] | None = None,
        collect_results: list[list[SandboxEntry]] | None = None,
    ) -> None:
        self._isolation = isolation
        self.exec_results = list(exec_results or [])
        self.collect_results = list(collect_results or [])
        self.exec_count = 0
        self.collect_count = 0

    @property
    def isolation(self) -> SandboxIsolation:
        return self._isolation

    async def start(self, entries: Sequence[SandboxEntry] = ()) -> SandboxId:
        return SandboxId("sandbox-secret-internal-id-12345")

    async def execute(self, sandbox_id: SandboxId, source: str | bytes) -> ExecutionResult:
        if self.exec_count < len(self.exec_results):
            res = self.exec_results[self.exec_count]
            self.exec_count += 1
            return res
        return ExecutionResult(0, "ok", "", 0.1)

    async def collect_output(self, sandbox_id: SandboxId, output_dir: str) -> list[SandboxEntry]:
        if self.collect_count < len(self.collect_results):
            res = self.collect_results[self.collect_count]
            self.collect_count += 1
            return res
        return []

    async def close(self, sandbox_id: SandboxId) -> None:
        pass


def _sample_snapshot() -> VerifiedContentSnapshot:
    return VerifiedContentSnapshot(
        snapshot_id="upload-001",
        source_file_id="file-1",
        filename="payload.enc",
        content_type="application/octet-stream",
        size=4,
        sha256="0" * 64,
        content=b"test",
    )


@pytest.mark.asyncio
async def test_feedback_excludes_secrets_stdout_stderr_and_internals() -> None:
    # Attempt 1 outputs secret stdout, stderr, exception, decoded bytes
    secret_stdout = "CRITICAL_SECRET_STDOUT_DATA"
    secret_stderr = "Traceback: ZeroDivisionError with SECRET_EXCEPTION_DETAIL"
    secret_decoded = b"SECRET_DECODED_BYTES_12345"

    source1 = "import non_existent_package\nprint('do something')\n"
    source2 = "print('second attempt')\n"

    model = SecrecyTrackingChatModel(
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
                                    {"source": source1, "rationale": "transform upload"}
                                ),
                            },
                        }
                    ],
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_2",
                            "type": "function",
                            "function": {
                                "name": "execute_python",
                                "arguments": json.dumps(
                                    {"source": source2, "rationale": "correct transform"}
                                ),
                            },
                        }
                    ],
                }
            },
        ]
    )

    sandbox = ScriptableSandbox(
        exec_results=[
            ExecutionResult(1, secret_stdout, secret_stderr, 0.1),
            ExecutionResult(0, "ok", "", 0.1),
        ],
        collect_results=[
            [SandboxEntry("upload-001/out.txt", secret_decoded)],
            [SandboxEntry("upload-001/final.txt", b"clean content")],
        ],
    )

    agent = DecoderAgent(
        model=model,
        sandbox=sandbox,
        snapshots=[_sample_snapshot()],
        task_context="task",
        case_fields={"title": "case"},
        evaluation_criteria="crit",
        transcript=[],
    )

    await agent.run()

    # Verify that in turn 2, the model messages sent NEVER contain the secret
    # stdout, stderr, exception text, or sandbox id
    assert len(model.history_records) >= 2
    second_call_messages = model.history_records[1]
    serialized = json.dumps(second_call_messages)

    assert secret_stdout not in serialized
    assert "SECRET_EXCEPTION_DETAIL" not in serialized
    assert "ZeroDivisionError" not in serialized
    assert "sandbox-secret-internal-id-12345" not in serialized
    assert "SECRET_DECODED_BYTES" not in serialized
    # Check that feedback is coarse: attempt, outcome, output count, hashes/sizes, limit flags
    tool_msg = next((m for m in second_call_messages if m.get("role") == "tool"), None)
    assert tool_msg is not None
    tool_content = json.loads(str(tool_msg.get("content")))
    assert tool_content["attempt"] == 1
    assert "exitCode" not in tool_content or isinstance(tool_content["exitCode"], int)
    assert "outputs" in tool_content or "outputCount" in tool_content
    assert tool_content["stdoutAvailableToModel"] is False
    assert tool_content["stderrAvailableToModel"] is False
    assert tool_content["nextAttemptOutputRoot"] == "/workspace/output/attempt-002"
    assert "direct" in tool_content["guidance"]


@pytest.mark.asyncio
async def test_unavailable_import_maps_to_coarse_failure_without_installer() -> None:
    source1 = "import custom_crypto_tool\n"
    model = SecrecyTrackingChatModel(
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
                                    {"source": source1, "rationale": "transform upload"}
                                ),
                            },
                        }
                    ],
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": '{"action":"direct","rationale":"already readable"}',
                }
            },
        ]
    )

    err_msg = "ModuleNotFoundError: No module named 'custom_crypto_tool'"
    sandbox = ScriptableSandbox(
        exec_results=[
            ExecutionResult(1, "", err_msg, 0.1),
        ],
        collect_results=[[]],
    )

    agent = DecoderAgent(
        model=model,
        sandbox=sandbox,
        snapshots=[_sample_snapshot()],
        task_context="task",
        case_fields={"title": "case"},
        evaluation_criteria="crit",
        transcript=[],
    )

    await agent.run()

    # Tools seen should only be execute_python, no pip or installer tool
    tools = model.tools_seen[0]
    assert tools is not None
    assert len(tools) == 1
    tool_0 = tools[0]
    assert isinstance(tool_0, dict)
    fn = tool_0.get("function")
    assert isinstance(fn, dict)
    assert fn.get("name") == "execute_python"
