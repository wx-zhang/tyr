from __future__ import annotations

import argparse
import signal
import subprocess
from collections.abc import Sequence


def _commands(watch: bool) -> Sequence[Sequence[str]]:
    api = (
        ("python", "-m", "gamr_api")
        if not watch
        else (
            "python",
            "-m",
            "uvicorn",
            "gamr_api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "6687",
            "--reload",
            "--reload-dir",
            "apps/api/src",
            "--reload-dir",
            "packages",
        )
    )
    return api, ("pnpm", "--dir", "apps/web", "dev"), (
        "python", "-m", "gamr_cli.benign", "worker",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the local GAMR for Tyr API and web app.")
    parser.add_argument("--watch", action="store_true", help="Reload the API on Python changes.")
    args = parser.parse_args()
    processes: list[subprocess.Popen[bytes]] = []

    def stop_all(*_: object) -> None:
        for process in processes:
            process.terminate()

    signal.signal(signal.SIGINT, stop_all)
    signal.signal(signal.SIGTERM, stop_all)
    try:
        processes.extend(subprocess.Popen(command) for command in _commands(args.watch))
        print("Visit http://localhost:6688 (API on http://127.0.0.1:6687)", flush=True)
        for process in processes:
            process.wait()
    finally:
        stop_all()


if __name__ == "__main__":
    main()
