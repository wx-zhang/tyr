from collections.abc import Iterator

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
