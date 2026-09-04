from collections.abc import Iterator

import gamr_adapters.tyr.operations as operations
import pytest
from gamr_adapters.tyr.operations import settle_operation


@pytest.mark.asyncio
async def test_settle_waits_for_child_execution_and_quiet_window() -> None:
    responses: Iterator[dict[str, object]] = iter(
        [
            {
                "state": "completed",
                "updatedAt": "1",
                "executions": [{"state": "running", "agentName": "Alice"}],
            },
            {"state": "completed", "updatedAt": "2", "executions": [{"state": "completed"}]},
            {"state": "completed", "updatedAt": "2", "executions": [{"state": "completed"}]},
        ]
    )
    waits: list[int] = []

    async def read_status(wait_seconds: int) -> dict[str, object]:
        waits.append(wait_seconds)
        return next(responses)

    result = await settle_operation(
        read_status,
        initial=next(responses),
        poll_wait_seconds=0,
        settle_wait_seconds=0,
    )
    assert result.local_state == "settled"
    assert result.payload["updatedAt"] == "2"
    assert waits == [0, 0]


@pytest.mark.asyncio
async def test_settle_stops_for_input_and_approval_without_polling_forever() -> None:
    async def read_status(_: int) -> dict[str, object]:
        raise AssertionError("should not poll")

    input_result = await settle_operation(
        read_status,
        initial={"state": "input_required", "response": "Which file?"},
    )
    approval_result = await settle_operation(
        read_status,
        initial={"state": "running", "pendingApprovals": [{"id": "approval-1"}]},
    )
    assert input_result.local_state == "input_required"
    assert approval_result.local_state == "waiting_for_approval"


@pytest.mark.asyncio
async def test_settle_reports_timeout_when_operation_never_finishes() -> None:
    async def read_status(_: int) -> dict[str, object]:
        return {"state": "running", "updatedAt": "1"}

    result = await settle_operation(
        read_status,
        initial={"state": "running", "updatedAt": "1"},
        attempts=2,
        poll_wait_seconds=0,
    )
    assert result.local_state == "timeout"


@pytest.mark.asyncio
async def test_settle_distinguishes_peer_side_approval() -> None:
    async def read_status(_: int) -> dict[str, object]:
        raise AssertionError("should not poll")

    result = await settle_operation(
        read_status,
        initial={"state": "completed", "bridges": [{"state": "waiting_for_approval"}]},
    )
    assert result.local_state == "peer_approval_blocked"


@pytest.mark.asyncio
async def test_settle_recognizes_tyr_blocked_on_peer_approval_state() -> None:
    async def read_status(_: int) -> dict[str, object]:
        raise AssertionError("should not poll")

    result = await settle_operation(
        read_status,
        initial={
            "state": "blocked_on_peer_approval",
            "bridges": [{"state": "blocked_on_peer_approval"}],
        },
    )
    assert result.local_state == "peer_approval_blocked"


@pytest.mark.asyncio
async def test_settle_uses_current_bridge_from_cumulative_ledger() -> None:
    current_reply = "AGENT_NAME: Carol\nWORKING_DIRECTORY: /home/agent"
    historical_bridges: list[dict[str, object]] = [
        {
            "state": "blocked_on_peer_approval",
            "createdAt": "2026-09-03T23:00:00Z",
            "bridgeRequestId": "historical-blocked",
        },
        {
            "state": "running",
            "createdAt": "2026-09-03T23:30:00Z",
            "bridgeRequestId": "historical-running",
        },
    ]
    initial: dict[str, object] = {
        "operationId": "operation-1",
        "state": "completed",
        "updatedAt": "1",
        "response": "Sent the request to Joe workspace. The peer TYR is still working.",
        "bridges": [
            *historical_bridges,
            {
                "state": "delivered",
                "createdAt": "2026-09-04T00:00:00Z",
                "bridgeRequestId": "current",
            },
        ],
    }
    responses: Iterator[dict[str, object]] = iter(
        [
            {
                **initial,
                "updatedAt": "2",
                "bridges": [
                    *historical_bridges,
                    {
                        "state": "completed",
                        "createdAt": "2026-09-04T00:00:00Z",
                        "bridgeRequestId": "current",
                        "response": current_reply,
                    },
                ],
            },
            {
                **initial,
                "updatedAt": "2",
                "bridges": [
                    *historical_bridges,
                    {
                        "state": "completed",
                        "createdAt": "2026-09-04T00:00:00Z",
                        "bridgeRequestId": "current",
                        "response": current_reply,
                    },
                ],
            },
        ]
    )
    waits: list[int] = []

    async def read_status(wait_seconds: int) -> dict[str, object]:
        waits.append(wait_seconds)
        return next(responses)

    result = await settle_operation(
        read_status,
        initial=initial,
        poll_wait_seconds=0,
        settle_wait_seconds=0,
    )

    assert result.local_state == "settled"
    assert result.reply == current_reply
    assert result.payload["response"] == initial["response"]
    assert waits == [0, 0]
    assert not any(
        "historical" in note or "blocked_on_peer_approval" in note for note in result.notes
    )
    assert not any("historical-running" in note or "running" in note for note in result.notes)


def test_current_bridge_selection_uses_latest_timestamps_and_append_fallback() -> None:
    result: dict[str, object] = {
        "bridges": [
            {"id": "historical", "createdAt": "2026-09-03T23:00:00Z"},
            {"id": "current-a", "createdAt": "2026-09-04T01:00:00Z"},
            "ignored",
            {"id": "current-b", "createdAt": "2026-09-04T02:00:00+01:00"},
            {"id": "trailing", "createdAt": "not-a-time"},
        ]
    }

    assert [entry["id"] for entry in operations._current_bridge_entries(result)] == [
        "current-a",
        "current-b",
        "trailing",
    ]
    assert [
        entry["id"]
        for entry in operations._current_bridge_entries(
            {"bridges": ["ignored", {"id": "first", "createdAt": "bad"}, {"id": "last"}]}
        )
    ] == ["last"]
