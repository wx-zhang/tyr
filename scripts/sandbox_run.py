from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from gamr_adapters.config import Settings
from gamr_adapters.sandbox.attachments import snapshot_attachments
from gamr_adapters.sandbox.factory import create_sandbox
from gamr_engine.ports import SandboxError, validate_source


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except (OSError, UnicodeError, SandboxError) as error:
        print(str(error), file=sys.stderr)
        return 2


async def _run(args: argparse.Namespace) -> int:
    source = _source(args)
    entries = snapshot_attachments(args.attach)
    settings = Settings()
    if settings.sandbox_backend == "host-unsafe":
        print(
            "WARNING: host-unsafe sandboxing is not a security boundary; "
            "generated code can access the host as the current user",
            file=sys.stderr,
        )
    sandbox = create_sandbox(settings)
    sandbox_id = None
    exit_code = 2
    try:
        sandbox_id = await sandbox.start(entries)
        result = await sandbox.execute(sandbox_id, source)
        print(
            json.dumps(
                {"sandboxId": str(sandbox_id), "result": result.as_dict()},
                ensure_ascii=False,
            )
        )
        exit_code = (
            0
            if result.exit_code == 0 and not result.timed_out and not result.output_limited
            else 1
        )
    except (SandboxError, OSError, UnicodeError) as error:
        print(str(error), file=sys.stderr)
    finally:
        if sandbox_id is not None:
            try:
                await sandbox.close(sandbox_id)
            except SandboxError as error:
                print(str(error), file=sys.stderr)
                exit_code = 2
    return exit_code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one Python fragment in a GAMR sandbox.")
    parser.add_argument("--attach", action="append", type=Path, default=[])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--code")
    source.add_argument("--source-file", type=Path)
    return parser


def _source(args: argparse.Namespace) -> str | bytes:
    if args.code is not None:
        validate_source(args.code)
        return args.code
    content = args.source_file.read_bytes()
    validate_source(content)
    return content


if __name__ == "__main__":
    raise SystemExit(main())
