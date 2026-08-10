from __future__ import annotations

import json
from pathlib import Path

from gamr_api.main import app


def main() -> None:
    Path("schemas/openapi.json").write_text(
        json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
