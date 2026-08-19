from __future__ import annotations

from gamr_adapters.config import Settings
from gamr_adapters.models.openai_compatible import OpenAICompatibleModel
from gamr_adapters.tyr.client import TyrMcpClient
from gamr_engine.chat import ApprovalCallback, ChatSession


def configured_secrets(settings: Settings) -> tuple[str, ...]:
    return tuple(
        value
        for value in (
            settings.tyr_mcp_token,
            settings.model_api_key,
            getattr(settings, "collector_username", ""),
            getattr(settings, "collector_password", ""),
        )
        if value
    )


def build_chat_session(
    settings: Settings,
    *,
    action_mode: str = "read_only",
    approve: ApprovalCallback | None = None,
    model_name: str | None = None,
    base_url: str | None = None,
) -> tuple[ChatSession, TyrMcpClient]:
    if not settings.tyr_mcp_token:
        raise ValueError("TYR_MCP_TOKEN is required for live chat")
    if not settings.model_api_key:
        raise ValueError("OPENROUTER_API_KEY is required for live chat")
    selected_model = model_name or settings.chat_model_name
    if not selected_model:
        raise ValueError("TYR_LOOP_CHAT_MODEL is required for live chat")
    target = TyrMcpClient(settings.tyr_mcp_url, settings.tyr_mcp_token)
    model = OpenAICompatibleModel(
        base_url=base_url or settings.model_base_url,
        api_key=settings.model_api_key,
        model=selected_model,
    )
    return ChatSession(model, target, action_mode=action_mode, approve=approve), target
