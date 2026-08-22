from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class DecoderCapacityGate:
    def __init__(self, capacity: int) -> None:
        if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 1:
            raise ValueError(f"capacity must be a positive integer, got {capacity!r}")
        self._capacity = capacity
        self._active = 0
        self._waiters: deque[asyncio.Future[None]] = deque()

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def active_count(self) -> int:
        return self._active

    @property
    def waiting_count(self) -> int:
        return len(self._waiters)

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[None]:
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[None] | None = None

        if self._active >= self._capacity:
            waiter = loop.create_future()
            self._waiters.append(waiter)
            try:
                await waiter
            except BaseException:
                if waiter in self._waiters:
                    self._waiters.remove(waiter)
                elif waiter.done() and not waiter.cancelled():
                    self._release()
                raise
        else:
            self._active += 1

        try:
            yield
        finally:
            self._release()

    def _release(self) -> None:
        while self._waiters:
            next_waiter = self._waiters.popleft()
            if not next_waiter.done():
                next_waiter.set_result(None)
                return
        self._active = max(0, self._active - 1)
