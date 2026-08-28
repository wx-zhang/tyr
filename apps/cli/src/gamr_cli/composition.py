from __future__ import annotations

from gamr_adapters.config import Settings
from gamr_adapters.models.openai_compatible import OpenAICompatibleModel
from gamr_adapters.sandbox.factory import create_sandbox
from gamr_adapters.tracing import create_trace_port
from gamr_adapters.tyr.client import TyrMcpClient
from gamr_engine.capacity_sandbox import CapacitySandbox
from gamr_engine.chat import ApprovalCallback, ChatSession
from gamr_engine.decoder_capacity import DecoderCapacityGate
from gamr_engine.ports.sandbox import Sandbox
from gamr_engine.ports.tracing import TracePort

_PROCESS_DECODER_GATE: DecoderCapacityGate | None = None


def get_decoder_capacity_gate(settings: Settings) -> DecoderCapacityGate:
    global _PROCESS_DECODER_GATE
    if _PROCESS_DECODER_GATE is None:
        _PROCESS_DECODER_GATE = DecoderCapacityGate(settings.max_concurrent_decoders)
    return _PROCESS_DECODER_GATE


def build_sandbox(settings: Settings) -> Sandbox:
    gate = get_decoder_capacity_gate(settings)
    raw_sandbox = create_sandbox(settings)
    return CapacitySandbox(raw_sandbox, gate)


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
    trace_port: TracePort | None = None,
) -> tuple[ChatSession, TyrMcpClient]:
    if not settings.tyr_mcp_token:
        raise ValueError("TYR_MCP_TOKEN is required for live chat")
    if not settings.model_api_key:
        raise ValueError("OPENROUTER_API_KEY is required for live chat")
    selected_model = model_name or settings.chat_model_name
    if not selected_model:
        raise ValueError("GAMR_CHAT_MODEL_NAME is required for live chat")
    if trace_port is None:
        trace_port = create_trace_port(settings)
    target = TyrMcpClient(settings.tyr_mcp_url, settings.tyr_mcp_token)
    model = OpenAICompatibleModel(
        base_url=base_url or settings.model_base_url,
        api_key=settings.model_api_key,
        model=selected_model,
        trace_port=trace_port,
    )
    return ChatSession(
        model, target, action_mode=action_mode, approve=approve, trace_port=trace_port
    ), target
