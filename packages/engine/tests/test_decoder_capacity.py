from __future__ import annotations

import asyncio

import pytest
from gamr_engine.decoder_capacity import DecoderCapacityGate


@pytest.mark.asyncio
async def test_decoder_capacity_gate_rejects_non_positive_and_non_integer() -> None:
    for invalid_capacity in (0, -1, -5):
        with pytest.raises(ValueError):
            DecoderCapacityGate(invalid_capacity)


@pytest.mark.asyncio
async def test_decoder_capacity_gate_admits_up_to_capacity() -> None:
    gate = DecoderCapacityGate(2)

    async with gate.acquire():
        async with gate.acquire():
            assert gate.active_count == 2


@pytest.mark.asyncio
async def test_decoder_capacity_gate_is_fifo() -> None:
    gate = DecoderCapacityGate(1)
    order: list[int] = []

    async def worker(worker_id: int) -> None:
        async with gate.acquire():
            order.append(worker_id)
            await asyncio.sleep(0.01)

    async with gate.acquire():
        t1 = asyncio.create_task(worker(1))
        await asyncio.sleep(0.001)
        t2 = asyncio.create_task(worker(2))
        await asyncio.sleep(0.001)
        t3 = asyncio.create_task(worker(3))
        await asyncio.sleep(0.001)

    await asyncio.gather(t1, t2, t3)
    assert order == [1, 2, 3]


@pytest.mark.asyncio
async def test_decoder_capacity_gate_cancellation_releases_waiter_or_slot() -> None:
    gate = DecoderCapacityGate(1)

    # 1. Cancel while waiting in FIFO queue
    async def waiter() -> None:
        async with gate.acquire():
            pass

    async with gate.acquire():
        wait_task = asyncio.create_task(waiter())
        await asyncio.sleep(0.005)
        assert gate.waiting_count == 1
        wait_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await wait_task
        assert gate.waiting_count == 0

    # 2. Cancel while holding slot
    async def holder(started_event: asyncio.Event) -> None:
        async with gate.acquire():
            started_event.set()
            await asyncio.sleep(10.0)

    started = asyncio.Event()
    holder_task = asyncio.create_task(holder(started))
    await started.wait()
    assert gate.active_count == 1

    holder_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await holder_task

    assert gate.active_count == 0

    # Next waiter can acquire
    acquired = False
    async with gate.acquire():
        acquired = True
    assert acquired


@pytest.mark.asyncio
async def test_decoder_capacity_gate_releases_on_exception_or_failure() -> None:
    gate = DecoderCapacityGate(1)

    with pytest.raises(RuntimeError):
        async with gate.acquire():
            raise RuntimeError("sandbox startup/execution/cleanup failure")

    assert gate.active_count == 0

    # Next acquire succeeds
    async with gate.acquire():
        assert gate.active_count == 1


@pytest.mark.asyncio
async def test_decoder_capacity_gate_cross_run_shared_instance() -> None:
    gate = DecoderCapacityGate(2)
    active_concurrent = 0
    max_observed_concurrent = 0

    async def simulate_case_sandbox_lifecycle() -> None:
        nonlocal active_concurrent, max_observed_concurrent
        async with gate.acquire():
            active_concurrent += 1
            max_observed_concurrent = max(max_observed_concurrent, active_concurrent)
            await asyncio.sleep(0.01)
            active_concurrent -= 1

    # Run multiple cases across concurrent simulated runs
    tasks = [asyncio.create_task(simulate_case_sandbox_lifecycle()) for _ in range(10)]
    await asyncio.gather(*tasks)

    assert max_observed_concurrent == 2
    assert gate.active_count == 0
    assert gate.waiting_count == 0
