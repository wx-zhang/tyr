from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4
from zoneinfo import ZoneInfo

from gamr_core.benign import Assessment, BenignRun, BenignScenario
from gamr_engine.benign_prompts import ASSESS_SYSTEM, DRAFT_SYSTEM
from openai import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import ValidationError

from .benign_config import BenignSettings
from .benign_store import BenignStore
from .config import Settings
from .models.openai_compatible import OpenAICompatibleModel

MODEL_TIMEOUT_SECONDS = 60


class BenignGenerationError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class RecordedModel(OpenAICompatibleModel):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        store: BenignStore,
        evidence_id: str,
        *,
        disable_reasoning: bool = False,
    ) -> None:
        super().__init__(base_url, api_key, model)
        self.client.max_retries = 0
        self.store = store
        self.evidence_id = evidence_id
        self.disable_reasoning = disable_reasoning

    async def _response(self, request: dict[str, Any], method: str) -> Any:
        if self.disable_reasoning:
            if urlparse(str(self.client.base_url)).hostname == "openrouter.ai":
                request["extra_body"] = {"reasoning": {"effort": "none"}}
            else:
                request["reasoning_effort"] = "none"
        reference = self.store.evidence(
            self.evidence_id,
            {
                "type": "provider.request",
                "method": method,
                "payload": request,
            },
        )
        try:
            response = await super()._response(request, method)
        except BaseException as exc:
            self.store.evidence(self.evidence_id, {"request": reference, "error": str(exc)})
            raise
        self.store.evidence(
            self.evidence_id,
            {
                "type": "provider.response",
                "request": reference,
                "payload": response.model_dump(),
            },
        )
        choice = response.choices[0] if response.choices else None
        if choice is not None and choice.finish_reason == "length":
            raise BenignGenerationError("Model reached its token limit before finishing the JSON.")
        if choice is None or not choice.message.content or not choice.message.content.strip():
            raise BenignGenerationError("Model returned no final answer. Reasoning is not a plan.")
        if choice.finish_reason != "stop" or getattr(choice.message, "refusal", None):
            raise BenignGenerationError("Model did not return a completed JSON answer.")
        return response


class BenignModel:
    def __init__(self, store: BenignStore) -> None:
        self.store = store

    async def complete(
        self,
        evidence_id: str,
        system: str,
        data: Any,
        schema: dict[str, Any],
        *,
        disable_reasoning: bool = False,
    ) -> dict[str, Any]:
        settings = Settings()
        if not settings.model_api_key:
            raise ValueError("OPENROUTER_API_KEY is not configured")
        model = RecordedModel(
            settings.model_base_url,
            settings.model_api_key,
            settings.model_name,
            self.store,
            evidence_id,
            disable_reasoning=disable_reasoning,
        )
        prompt = json.dumps(
            {"input": data, "output_schema": schema}, ensure_ascii=False, default=str
        )
        self.store.evidence(
            evidence_id,
            {
                "type": "model.request",
                "system": system,
                "prompt": prompt,
                "schema": schema,
                "model": settings.model_name,
            },
        )
        try:
            async with asyncio.timeout(MODEL_TIMEOUT_SECONDS):
                result = await model.complete_structured(
                    prompt, system=system, json_schema=schema, schema_name="benign_contract"
                )
            self.store.evidence(evidence_id, {"type": "model.response", "payload": result})
            payload: Any = json.loads(str(result["content"]))
            if not isinstance(payload, dict):
                raise ValueError("Model did not return a JSON object")
            return payload
        except Exception as exc:
            self.store.evidence(evidence_id, {"type": "model.error", "error": str(exc)})
            if isinstance(exc, (TimeoutError, APITimeoutError)):
                raise BenignGenerationError(
                    f"Model generation timed out after {MODEL_TIMEOUT_SECONDS:g} seconds. "
                    "No Tyr action was started by generation.",
                    504,
                ) from exc
            if isinstance(exc, APIConnectionError):
                raise BenignGenerationError("Could not connect to the model provider.") from exc
            if isinstance(exc, APIStatusError):
                raise BenignGenerationError(
                    f"Model provider returned HTTP {exc.status_code}. "
                    "Check provider credentials, quota and model availability."
                ) from exc
            if isinstance(exc, (json.JSONDecodeError, KeyError)):
                raise BenignGenerationError(
                    "Model returned invalid JSON. No plan was saved."
                ) from exc
            raise
        finally:
            await model.client.close()

    async def draft(self, text: str, workspace: str, timezone: str) -> BenignScenario:
        bindings = BenignSettings().bindings()
        if workspace not in bindings:
            raise ValueError("Select a configured workspace")
        reference = datetime.now(ZoneInfo(timezone))
        draft_id = str(uuid4())
        data = {
            "input": text,
            "workspace": workspace,
            "timezone": timezone,
            "reference_time": reference.isoformat(),
            "aliases": list(bindings),
        }
        payload = await self.complete(
            draft_id,
            DRAFT_SYSTEM,
            data,
            BenignScenario.model_json_schema(),
            disable_reasoning=True,
        )
        payload.update(
            id=draft_id,
            original_input=text,
            workspace=workspace,
            timezone=timezone,
            reference_time=reference,
        )
        try:
            scenario = BenignScenario.model_validate(payload)
        except ValidationError as exc:
            self.store.evidence(draft_id, {"type": "validation.error", "error": str(exc)})
            raise BenignGenerationError(
                "Model output does not match the scenario schema. No plan was saved."
            ) from exc
        if not set(scenario.participants).issubset(bindings):
            raise ValueError("Model selected an unknown workspace")
        self.store.atomic(
            self.store.directory(draft_id) / "scenario.json", scenario.model_dump(mode="json")
        )
        return scenario

    async def assess(self, run: BenignRun) -> dict[str, Any]:
        return await self.complete(
            run.id,
            ASSESS_SYSTEM,
            {
                "scenario": run.scenario.model_dump(mode="json"),
                "observations": run.observations,
            },
            Assessment.model_json_schema(),
        )
