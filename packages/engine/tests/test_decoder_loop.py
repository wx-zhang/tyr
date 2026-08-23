from __future__ import annotations

import hashlib
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
    SandboxValidationError,
)


class FakeChatModel(ChatModelGateway):
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = list(responses)
        self.call_count = 0
        self.messages_seen: list[list[dict[str, object]]] = []

    async def chat(
        self,
        messages: list[dict[str, object]],
        *,
        tools: list[dict[str, object]] | None = None,
        max_tokens: int = 1024,
    ) -> dict[str, object]:
        self.messages_seen.append(messages)
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
        self.started_ids: list[SandboxId] = []
        self.closed_ids: list[SandboxId] = []
        self.sources_executed: list[str | bytes] = []
        self.collected_dirs: list[str] = []

    @property
    def isolation(self) -> SandboxIsolation:
        return self._isolation

    async def start(self, entries: Sequence[SandboxEntry] = ()) -> SandboxId:
        sid = SandboxId(f"sandbox-{len(self.started_ids) + 1}")
        self.started_ids.append(sid)
        return sid

    async def execute(self, sandbox_id: SandboxId, source: str | bytes) -> ExecutionResult:
        self.sources_executed.append(source)
        if self.exec_count < len(self.exec_results):
            res = self.exec_results[self.exec_count]
            self.exec_count += 1
            return res
        return ExecutionResult(0, "ok", "", 0.1)

    async def collect_output(self, sandbox_id: SandboxId, output_dir: str) -> list[SandboxEntry]:
        self.collected_dirs.append(output_dir)
        if self.collect_count < len(self.collect_results):
            res = self.collect_results[self.collect_count]
            self.collect_count += 1
            return res
        return []

    async def close(self, sandbox_id: SandboxId) -> None:
        self.closed_ids.append(sandbox_id)


def _sample_snapshot(
    snapshot_id: str = "upload-001", file_id: str = "file-1"
) -> VerifiedContentSnapshot:
    return VerifiedContentSnapshot(
        snapshot_id=snapshot_id,
        source_file_id=file_id,
        filename="payload.enc",
        content_type="application/octet-stream",
        size=4,
        sha256="0" * 64,
        content=b"test",
    )


@pytest.mark.asyncio
async def test_successful_first_program_terminates_loop() -> None:
    source_code = (
        "import pathlib\n"
        "pathlib.Path('/workspace/output/attempt-001/upload-001/out.txt').write_text('hello')\n"
    )
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
                                    {"source": source_code, "rationale": "transform upload"}
                                ),
                            },
                        }
                    ],
                }
            }
        ]
    )
    sandbox = ScriptableSandbox(
        exec_results=[ExecutionResult(0, "success", "", 0.1)],
        collect_results=[[SandboxEntry("upload-001/out.txt", b"hello")]],
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

    result = await agent.run()

    assert result.action == "decoded"
    assert result.provenance.status == DecodingStatus.SUCCEEDED
    assert result.provenance.attempt_count == 1
    assert result.provenance.rationale == "transform upload"
    assert result.provenance.program_sha256 == [hashlib.sha256(source_code.encode()).hexdigest()]
    attempt = result.provenance.attempts[0]
    assert attempt.source == source_code
    assert attempt.execution is not None
    assert attempt.execution.stdout.state == "captured"
    assert attempt.execution.stdout.value == "success"
    assert attempt.execution.stderr.state == "empty"
    assert len(result.provenance.derived_files) == 1
    assert result.provenance.derived_files[0].uploaded_item_id == "upload-001-derived-001"
    assert sandbox.collected_dirs == ["output/attempt-001"]
    assert sandbox.closed_ids == ["sandbox-1"]


@pytest.mark.asyncio
async def test_valid_derived_text_survives_an_unsupported_sibling() -> None:
    source_code = "decode uploaded content"
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
                                    {"source": source_code, "rationale": "decode upload"}
                                ),
                            },
                        }
                    ],
                }
            }
        ]
    )
    sandbox = ScriptableSandbox(
        collect_results=[
            [
                SandboxEntry("upload-001/original.bin", b"opaque"),
                SandboxEntry("upload-001/decoded.txt", b"decoded content"),
            ]
        ]
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

    result = await agent.run()

    assert result.action == "decoded"
    assert result.provenance.status is DecodingStatus.SUCCEEDED
    assert [item.uploaded_item_id for item in result.provenance.derived_files] == [
        "upload-001-derived-002"
    ]


@pytest.mark.asyncio
async def test_tool_free_prose_routes_verified_plain_text_directly() -> None:
    model = FakeChatModel(
        [{"message": {"role": "assistant", "content": "This plain text is directly readable."}}]
    )
    sandbox = ScriptableSandbox()
    snapshot = VerifiedContentSnapshot(
        snapshot_id="upload-001",
        source_file_id="file-1",
        filename="notes.txt",
        content_type="text/plain",
        size=6,
        sha256=hashlib.sha256(b"notes\n").hexdigest(),
        content=b"notes\n",
    )
    agent = DecoderAgent(
        model=model,
        sandbox=sandbox,
        snapshots=[snapshot],
        task_context="task",
        case_fields={"title": "case"},
        evaluation_criteria="crit",
        transcript=[],
    )

    result = await agent.run()

    assert result.action == "direct"
    assert result.provenance.status is DecodingStatus.SKIPPED
    assert result.provenance.rationale == "Verified uploads are directly readable."
    assert sandbox.started_ids == []


@pytest.mark.asyncio
async def test_correction_in_same_healthy_workspace() -> None:
    source1 = "print('fail 1')\n"
    source2 = "print('success 2')\n"
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
            ExecutionResult(1, "", "syntax error", 0.1),
            ExecutionResult(0, "ok", "", 0.1),
        ],
        collect_results=[
            [],  # attempt 1 produces nothing
            [SandboxEntry("upload-001/out.txt", b"decoded content")],
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

    result = await agent.run()

    assert result.action == "decoded"
    assert result.provenance.status == DecodingStatus.SUCCEEDED
    assert result.provenance.attempt_count == 2
    assert len(sandbox.started_ids) == 1  # Reused same healthy sandbox
    assert sandbox.collected_dirs == [
        "output/attempt-001",
        "output/attempt-002",
    ]
    assert sandbox.closed_ids == ["sandbox-1"]


@pytest.mark.asyncio
async def test_inspection_attempt_can_revise_route_to_direct() -> None:
    source = "print('valid UTF-8 text')\n"
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
                                    {"source": source, "rationale": "inspect upload"}
                                ),
                            },
                        }
                    ],
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {"action": "direct", "rationale": "plain text is directly readable"}
                    ),
                }
            },
        ]
    )
    sandbox = ScriptableSandbox(
        exec_results=[ExecutionResult(0, "valid UTF-8 text", "", 0.1)],
        collect_results=[[]],
    )
    activities: list[tuple[str, dict[str, object]]] = []
    agent = DecoderAgent(
        model=model,
        sandbox=sandbox,
        snapshots=[_sample_snapshot()],
        task_context="task",
        case_fields={"title": "case"},
        evaluation_criteria="crit",
        transcript=[],
        activity_sink=lambda name, payload: activities.append((name, payload)),
    )

    result = await agent.run()

    assert result.action == "direct"
    assert result.provenance.status == DecodingStatus.SKIPPED
    assert result.provenance.attempt_count == 1
    assert result.provenance.attempts[0].execution is not None
    assert result.provenance.attempts[0].execution.stdout.value == "valid UTF-8 text"
    assert len(sandbox.sources_executed) == 1
    assert [name for name, _ in activities] == [
        "decoder.analysis_started",
        "decoder.route_selected",
        "decoder.attempt_started",
        "decoder.attempt_completed",
        "decoder.route_revised",
    ]


@pytest.mark.asyncio
async def test_exactly_three_calls_then_attempt_exhaustion() -> None:
    source = "print('fail')\n"
    call_msg: dict[str, object] = {
        "message": {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call",
                    "type": "function",
                    "function": {
                        "name": "execute_python",
                        "arguments": json.dumps(
                            {"source": source, "rationale": "transform upload"}
                        ),
                    },
                }
            ],
        }
    }
    model = FakeChatModel([call_msg, call_msg, call_msg, call_msg])
    sandbox = ScriptableSandbox(
        exec_results=[
            ExecutionResult(1, "", "err1", 0.1),
            ExecutionResult(1, "", "err2", 0.1),
            ExecutionResult(1, "", "err3", 0.1),
        ],
        collect_results=[[], [], []],
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

    result = await agent.run()

    assert result.action == "failed"
    assert result.provenance.status == DecodingStatus.FAILED
    assert result.provenance.failure_code == DecodingFailureCode.ATTEMPT_EXHAUSTION
    assert result.provenance.attempt_count == 3
    assert [item.attempt for item in result.provenance.attempts] == [1, 2, 3]
    assert all(item.execution is not None for item in result.provenance.attempts)
    assert len(sandbox.sources_executed) == 3
    assert model.call_count == 4
    assert sandbox.closed_ids == ["sandbox-1"]


@pytest.mark.asyncio
async def test_third_inspection_attempt_gets_non_executing_final_turn() -> None:
    source = "print('readable')\n"
    tool_response: dict[str, object] = {
        "message": {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call",
                    "type": "function",
                    "function": {
                        "name": "execute_python",
                        "arguments": json.dumps(
                            {"source": source, "rationale": "inspect upload"}
                        ),
                    },
                }
            ],
        }
    }
    direct_response: dict[str, object] = {
        "message": {
            "role": "assistant",
            "content": '{"action":"direct","rationale":"standard readable file"}',
        }
    }
    model = FakeChatModel([tool_response, tool_response, tool_response, direct_response])
    sandbox = ScriptableSandbox(
        exec_results=[ExecutionResult(0, "readable", "", 0.1)] * 3,
        collect_results=[[], [], []],
    )
    result = await DecoderAgent(
        model=model,
        sandbox=sandbox,
        snapshots=[_sample_snapshot()],
        task_context="task",
        case_fields={"title": "case"},
        evaluation_criteria="crit",
        transcript=[],
    ).run()

    assert result.action == "direct"
    assert result.provenance.attempt_count == 3
    assert len(result.provenance.attempts) == 3
    assert len(sandbox.sources_executed) == 3
    final_tool_feedback = json.loads(str(model.messages_seen[3][-1]["content"]))
    assert final_tool_feedback["attemptsRemaining"] == 0
    assert "nextAttemptOutputRoot" not in final_tool_feedback


@pytest.mark.asyncio
async def test_terminal_timeout_destroys_and_replaces_sandbox() -> None:
    source1 = "while True: pass\n"
    source2 = "print('fixed')\n"
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
            ExecutionResult(None, "", "timed out", 10.0, timed_out=True),
            ExecutionResult(0, "ok", "", 0.1),
        ],
        collect_results=[
            [SandboxEntry("upload-001/out.txt", b"fixed content")],
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

    result = await agent.run()

    assert result.action == "decoded"
    assert result.provenance.status == DecodingStatus.SUCCEEDED
    assert result.provenance.attempt_count == 2
    assert result.provenance.limit_flags.timed_out is True
    assert len(sandbox.started_ids) == 2  # Started replacement sandbox
    assert sandbox.closed_ids == ["sandbox-1", "sandbox-2"]


@pytest.mark.asyncio
async def test_unsafe_isolation_fails_without_host_fallback() -> None:
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
                        }
                    ],
                }
            }
        ]
    )
    sandbox = ScriptableSandbox(isolation="unsafe")
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
    assert result.provenance.failure_code == DecodingFailureCode.UNSAFE_ISOLATION
    assert sandbox.started_ids == []


@pytest.mark.asyncio
async def test_sandbox_unavailable_fails_closed() -> None:
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
                        }
                    ],
                }
            }
        ]
    )
    sandbox = ScriptableSandbox(isolation="unavailable")
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
    assert result.provenance.failure_code == DecodingFailureCode.SANDBOX_UNAVAILABLE
    assert sandbox.started_ids == []


class InputRejectingSandbox(ScriptableSandbox):
    async def start(self, entries: Sequence[SandboxEntry] = ()) -> SandboxId:
        raise SandboxValidationError("absolute attachment destination")


@pytest.mark.asyncio
async def test_absolute_attachment_failure_is_input_validation_before_startup() -> None:
    source = "print('decode')"
    model = FakeChatModel(
        [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {
                                "name": "execute_python",
                                "arguments": json.dumps(
                                    {"source": source, "rationale": "transform upload"}
                                ),
                            },
                        }
                    ],
                }
            }
        ]
    )
    sandbox = InputRejectingSandbox()

    result = await DecoderAgent(
        model=model,
        sandbox=sandbox,
        snapshots=[_sample_snapshot()],
        task_context="task",
        case_fields={"title": "case"},
        evaluation_criteria="crit",
        transcript=[],
    ).run()

    assert result.provenance.failure_code == DecodingFailureCode.INPUT_VALIDATION
    assert result.provenance.failure_stage == "input_validation"
    assert result.provenance.attempts[0].failure_code == DecodingFailureCode.INPUT_VALIDATION
