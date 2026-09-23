from __future__ import annotations

import json
from pathlib import Path

from gamr_core import DiscoveryInputDocument, ExperimentPresetRecord, ExperimentRecord
from gamr_core.benign import BenignRun, BenignScenario


def main() -> None:
    output = Path("schemas")
    for name, model in (
        ("discovery-input", DiscoveryInputDocument),
        ("experiment", ExperimentPresetRecord),
        ("run", ExperimentRecord),
        ("benign-scenario", BenignScenario),
        ("benign-run", BenignRun),
    ):
        schema = model.model_json_schema(by_alias=True)
        schema["$id"] = f"https://gamr.local/schemas/{name}.schema.json"
        (output / f"{name}.schema.json").write_text(
            json.dumps(schema, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
