from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from gamr_adapters.benign_model import RecordedModel
from gamr_adapters.benign_store import BenignStore
from gamr_adapters.models.openai_compatible import OpenAICompatibleModel


@pytest.mark.asyncio
async def test_provider_calls_record_exact_payloads_and_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def reply(*args: Any) -> Any:
        return SimpleNamespace(
            choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="{}"))],
            model_dump=lambda: {"choices": [{"message": {"content": "{}"}}], "model": "test"},
        )

    monkeypatch.setattr(OpenAICompatibleModel, "_response", reply)
    store = BenignStore(tmp_path)
    model = RecordedModel("https://example.test/v1", "placeholder", "test", store, "run")
    try:
        await model._response({"messages": [{"content": "original"}]}, "structured")
        assert model.client.max_retries == 0
        evidence = list((tmp_path / "run" / "evidence").glob("*.json"))
        assert len(evidence) == 2
        assert any('"original"' in path.read_text() for path in evidence)

        async def fail(*args: Any) -> Any:
            raise ValueError("provider failure")

        monkeypatch.setattr(OpenAICompatibleModel, "_response", fail)
        with pytest.raises(ValueError, match="provider failure"):
            await model._response({"messages": []}, "structured")
        assert len(list((tmp_path / "run" / "evidence").glob("*.json"))) == 4
    finally:
        await model.client.close()
