from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from gamr_engine.ports import (
    MAX_OUTPUT_BYTES,
    ExecutionResult,
    SandboxInfrastructureError,
    execution_result,
)

_CHUNK_SIZE = 64 * 1024


class _Capture:
    def __init__(self) -> None:
        self.stdout = bytearray()
        self.stderr = bytearray()
        self.total = 0
        self.output_limited = False

    def add(self, target: bytearray, chunk: bytes) -> None:
        remaining = MAX_OUTPUT_BYTES - self.total
        if remaining > 0:
            target.extend(chunk[:remaining])
        self.total += len(chunk)
        self.output_limited = self.total > MAX_OUTPUT_BYTES


async def run_bounded_process(
    process: asyncio.subprocess.Process,
    source: bytes,
    *,
    timeout: float,
    terminate: Callable[[], Awaitable[None]],
) -> tuple[ExecutionResult, bool]:
    started = time.monotonic()
    capture = _Capture()
    try:
        if process.stdin is not None:
            try:
                process.stdin.write(source)
                await process.stdin.drain()
            except (BrokenPipeError, ConnectionError):
                pass
            finally:
                process.stdin.close()
        if process.stdout is None or process.stderr is None:
            raise SandboxInfrastructureError("sandbox process pipes were not created")
        readers = asyncio.gather(
            _read_stream(process.stdout, capture.stdout, capture),
            _read_stream(process.stderr, capture.stderr, capture),
        )
        timed_out = False
        while not readers.done():
            await asyncio.sleep(0.02)
            if capture.output_limited:
                await terminate()
                break
            if time.monotonic() - started > timeout:
                timed_out = True
                await terminate()
                break
        await readers
        if process.returncode is None:
            await process.wait()
        terminal = timed_out or capture.output_limited
        return (
            execution_result(
                None if terminal else process.returncode,
                bytes(capture.stdout),
                bytes(capture.stderr),
                time.monotonic() - started,
                timed_out=timed_out,
                output_limited=capture.output_limited,
            ),
            terminal,
        )
    except asyncio.CancelledError:
        await terminate()
        raise
    except SandboxInfrastructureError:
        await terminate()
        raise
    except Exception as error:
        await terminate()
        raise SandboxInfrastructureError("sandbox process failed") from error


async def _read_stream(
    stream: asyncio.StreamReader, target: bytearray, capture: _Capture
) -> None:
    while True:
        chunk = await stream.read(_CHUNK_SIZE)
        if not chunk:
            return
        capture.add(target, chunk)
        if capture.output_limited:
            return
