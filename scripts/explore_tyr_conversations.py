from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

from gamr_adapters.config import Settings
from gamr_adapters.tyr.client import TyrMcpClient

_ROOT = Path(__file__).resolve().parents[1]
_TOOL_NAMES = {
    "tyr_assistant_start_conversation",
    "tyr_assistant_query",
    "tyr_assistant_request",
}


def _conversation_id(result: dict[str, Any]) -> str:
    conversation_id = result.get("conversationId")
    if not isinstance(conversation_id, str) or not conversation_id:
        raise RuntimeError(f"start conversation returned no conversationId: {result}")
    return conversation_id


def _response(result: dict[str, object]) -> str:
    value = result.get("response") or result.get("message") or ""
    return value if isinstance(value, str) else json.dumps(value, sort_keys=True)


def _write_trace(path: Path, trace: dict[str, object]) -> None:
    path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")


async def _query(
    client: TyrMcpClient,
    conversation_id: str,
    message: str,
) -> dict[str, object]:
    result = await client.call_tool(
        "tyr_assistant_query",
        {
            "conversationId": conversation_id,
            "idempotencyKey": str(uuid4()),
            "message": message,
        },
        timeout=300,
    )
    return await client.settle(result)


async def explore() -> Path:
    settings = Settings()
    if not settings.tyr_mcp_token:
        raise RuntimeError("TYR_MCP_TOKEN is required")
    output_dir = _ROOT / ".gamr" / "explorations"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"tyr-conversations-{uuid4()}.json"

    trace: dict[str, object] = {
        "startedAt": datetime.now(UTC).isoformat(),
        "mcpUrl": settings.tyr_mcp_url,
    }
    async with TyrMcpClient(settings.tyr_mcp_url, settings.tyr_mcp_token) as client:
        trace["initialize"] = await client.initialize()
        tools = await client.list_tools()
        selected_tools = [tool for tool in tools if tool.get("name") in _TOOL_NAMES]
        trace["tools"] = selected_tools
        _write_trace(output_path, trace)

        starts = [await client.start_conversation() for _ in range(2)]
        conversation_ids = [_conversation_id(result) for result in starts]
        if len(set(conversation_ids)) != 2:
            raise RuntimeError(f"conversation IDs are not unique: {conversation_ids}")
        trace["starts"] = starts

        markers = [f"GAMR-{uuid4().hex}", f"GAMR-{uuid4().hex}"]
        first_messages = [
            f"Remember this exact marker for a later turn: {marker}. Reply only ACK."
            for marker in markers
        ]
        trace["conversations"] = [
            {
                "conversationId": conversation_id,
                "firstMessage": first_message,
            }
            for conversation_id, first_message in zip(conversation_ids, first_messages, strict=True)
        ]
        _write_trace(output_path, trace)
        started = monotonic()
        first_results = await asyncio.gather(
            *(
                _query(client, conversation_id, message)
                for conversation_id, message in zip(conversation_ids, first_messages, strict=True)
            )
        )
        parallel_seconds = monotonic() - started

        followup_message = "Return only the exact marker I asked you to remember earlier."
        followup_results = await asyncio.gather(
            *(
                _query(client, conversation_id, followup_message)
                for conversation_id in conversation_ids
            )
        )
        responses = [_response(result) for result in followup_results]
        for index, response in enumerate(responses):
            other_index = 1 - index
            if markers[index] not in response:
                raise RuntimeError(
                    f"conversation {index + 1} did not recall its marker: {response}"
                )
            if markers[other_index] in response:
                raise RuntimeError(f"conversation {index + 1} leaked the other marker: {response}")

        trace["parallelFirstTurnsSeconds"] = parallel_seconds
        trace["conversations"] = [
            {
                "conversationId": conversation_id,
                "firstMessage": first_message,
                "firstResult": first_result,
                "followupMessage": followup_message,
                "followupResult": followup_result,
            }
            for conversation_id, first_message, first_result, followup_result in zip(
                conversation_ids,
                first_messages,
                first_results,
                followup_results,
                strict=True,
            )
        ]
        trace["validated"] = True

    trace["completedAt"] = datetime.now(UTC).isoformat()
    _write_trace(output_path, trace)
    return output_path


def main() -> int:
    output_path = asyncio.run(explore())
    print(f"Validated isolated Tyr MCP conversations. Trace: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
