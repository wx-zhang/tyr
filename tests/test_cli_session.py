from __future__ import annotations

import json
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tyr_agent_tester.cli.session import run_turn, tool_definitions
from tyr_agent_tester.mcp_client import TyrMCPClient


class ModelMessage(SimpleNamespace):
    def model_dump(self, exclude_none: bool = True) -> dict:
        result = {"role": self.role, "content": self.content}
        if getattr(self, "tool_calls", None):
            result["tool_calls"] = self.tool_calls
        if exclude_none:
            return {key: value for key, value in result.items() if value is not None}
        return result


def tool_response(name: str, arguments: dict, call_id: str = "call-1") -> SimpleNamespace:
    call = SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )
    message = ModelMessage(role="assistant", content=None, tool_calls=[call])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def text_response(content: str) -> SimpleNamespace:
    message = ModelMessage(role="assistant", content=content, tool_calls=[])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeCompletions:
    def __init__(self, responses: list[SimpleNamespace]):
        self.responses = responses

    def create(self, **_kwargs) -> SimpleNamespace:
        return self.responses.pop(0)


class FakeUI:
    def __init__(self, approve_upgrade: bool):
        self.approve_upgrade = approve_upgrade
        self.upgrade_confirmations: list[tuple[str, dict]] = []
        self.tool_calls: list[str] = []

    @contextmanager
    def status(self, _message: str):
        yield

    def confirm_action(self, _name: str, _arguments: dict) -> bool:
        raise AssertionError("ordinary Action confirmation was not expected")

    def confirm_action_upgrade(self, name: str, arguments: dict) -> bool:
        self.upgrade_confirmations.append((name, arguments))
        return self.approve_upgrade

    def tool_call(self, name: str) -> None:
        self.tool_calls.append(name)


class FakeTyr:
    def __init__(self, query_result: dict):
        self.query_result = query_result
        self.calls: list[tuple[str, dict]] = []
        self.requests: list[tuple[str, str | None]] = []

    def call_tool(self, name: str, arguments: dict) -> dict:
        self.calls.append((name, arguments))
        return self.query_result

    def request(self, message: str, operation_id: str | None = None) -> dict:
        self.requests.append((message, operation_id))
        return {"operationId": "action-operation", "state": "completed"}


def run_query_turn(
    query_result: dict,
    approve_upgrade: bool,
    arguments: dict,
) -> tuple[str, FakeTyr, FakeUI]:
    model = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions([
        tool_response("tyr_assistant_query", arguments),
        text_response("finished"),
    ])))
    tyr = FakeTyr(query_result)
    ui = FakeUI(approve_upgrade)
    answer = run_turn(
        model,
        "test-model",
        tyr,
        [{"role": "system", "content": "test"}],
        [],
        {"tyr_assistant_query"},
        {"tyr_assistant_query": True, "tyr_assistant_request": False},
        False,
        ui,
    )
    return answer, tyr, ui


class CliSessionTests(unittest.TestCase):
    def test_ordinary_read_only_query_does_not_request_action_confirmation(self) -> None:
        answer, tyr, ui = run_query_turn(
            {"operationId": "query-operation", "state": "completed"},
            approve_upgrade=True,
            arguments={"message": "List my agents", "idempotencyKey": "query-key"},
        )

        self.assertEqual(answer, "finished")
        self.assertEqual(tyr.requests, [])
        self.assertEqual(ui.upgrade_confirmations, [])

    def test_blocked_query_upgrades_once_after_operator_confirmation(self) -> None:
        original_message = "Ask the peer workspace to have an Agent find important.txt."
        answer, tyr, ui = run_query_turn(
            {
                "operationId": "query-operation",
                "state": "failed",
                "error": {
                    "code": "operation_not_allowed",
                    "actionModeRequired": True,
                    "newOperationRequired": True,
                    "requiredTool": "tyr_assistant_request",
                },
            },
            approve_upgrade=True,
            arguments={
                "message": original_message,
                "operationId": "query-operation",
                "idempotencyKey": "query-key",
            },
        )

        self.assertEqual(answer, "finished")
        self.assertEqual(ui.upgrade_confirmations, [
            ("tyr_assistant_request", {"message": original_message})
        ])
        self.assertEqual(tyr.requests, [(original_message, None)])
        self.assertEqual(ui.tool_calls, ["tyr_assistant_query", "tyr_assistant_request"])

    def test_declined_upgrade_creates_no_action(self) -> None:
        _, tyr, ui = run_query_turn(
            {
                "state": "failed",
                "error": {
                    "actionModeRequired": True,
                    "newOperationRequired": True,
                    "requiredTool": "tyr_assistant_request",
                },
            },
            approve_upgrade=False,
            arguments={"message": "Run peer work", "operationId": "query-operation"},
        )

        self.assertEqual(len(ui.upgrade_confirmations), 1)
        self.assertEqual(tyr.requests, [])
        self.assertEqual(ui.tool_calls, ["tyr_assistant_query"])

    def test_incomplete_upgrade_signal_does_not_prompt_or_create_action(self) -> None:
        _, tyr, ui = run_query_turn(
            {
                "state": "failed",
                "error": {
                    "actionModeRequired": True,
                    "requiredTool": "tyr_assistant_request",
                },
            },
            approve_upgrade=True,
            arguments={"message": "Run peer work", "operationId": "query-operation"},
        )

        self.assertEqual(ui.upgrade_confirmations, [])
        self.assertEqual(tyr.requests, [])

    def test_action_request_uses_fresh_idempotency_key_and_no_query_operation_id(self) -> None:
        client = object.__new__(TyrMCPClient)
        client.call_tool = Mock(return_value={})
        with patch("tyr_agent_tester.mcp_client.uuid.uuid4", side_effect=["query-key", "action-key"]):
            client.query("same message", operation_id="query-operation")
            client.request("same message")

        self.assertEqual(client.call_tool.call_args_list[0].args, (
            "tyr_assistant_query",
            {
                "message": "same message",
                "idempotencyKey": "query-key",
                "operationId": "query-operation",
            },
        ))
        self.assertEqual(client.call_tool.call_args_list[1].args, (
            "tyr_assistant_request",
            {"message": "same message", "idempotencyKey": "action-key"},
        ))

    def test_tool_annotations_take_priority_and_unknown_tools_fail_closed(self) -> None:
        tools = [
            {
                "name": "custom_inventory",
                "inputSchema": {"type": "object"},
                "annotations": {"readOnlyHint": True},
            },
            {
                "name": "tyr_operation_status",
                "inputSchema": {"type": "object"},
                "annotations": {"readOnlyHint": False},
            },
            {"name": "legacy_unknown", "inputSchema": {"type": "object"}},
            {"name": "tyr_assistant_query", "inputSchema": {"type": "object"}},
        ]

        definitions, names, read_only_by_name = tool_definitions(tools, allow_actions=False)

        self.assertEqual(names, {"custom_inventory", "tyr_assistant_query"})
        self.assertEqual(
            {item["function"]["name"] for item in definitions},
            {"custom_inventory", "tyr_assistant_query"},
        )
        self.assertEqual(read_only_by_name, {
            "custom_inventory": True,
            "tyr_operation_status": False,
            "legacy_unknown": False,
            "tyr_assistant_query": True,
        })


if __name__ == "__main__":
    unittest.main()
