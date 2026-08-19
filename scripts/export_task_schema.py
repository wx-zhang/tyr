from __future__ import annotations

import json
from pathlib import Path

from gamr_core import TaskDocument
from pydantic import TypeAdapter


def main() -> None:
    output = Path("schemas/task.schema.json")
    schema = TypeAdapter(TaskDocument).json_schema(by_alias=True)
    schema["$id"] = "https://gamr.local/schemas/task.schema.json"
    output.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
