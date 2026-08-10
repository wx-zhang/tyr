from __future__ import annotations

import json
from pathlib import Path

from gamr_core import RunResult


def main() -> None:
    output = Path("schemas/run-result.schema.json")
    schema = RunResult.model_json_schema(by_alias=True)
    schema["$id"] = "https://gamr.local/schemas/run-result.schema.json"
    output.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
