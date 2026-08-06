#!/usr/bin/env python3
"""Executable entry point for the interactive Tyr CLI."""

from .cli.agent import main as run_cli


def main() -> int:
    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
