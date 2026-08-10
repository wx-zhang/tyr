from __future__ import annotations

from pathlib import Path


def main() -> None:
    Path(".gamr/runs").mkdir(parents=True, exist_ok=True)
    print("Created .gamr/runs")


if __name__ == "__main__":
    main()
