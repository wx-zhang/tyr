from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    environment: str = Field(default="development", validation_alias="GAMR_ENVIRONMENT")
    artifact_root: str = Field(default=".gamr", validation_alias="GAMR_ARTIFACT_ROOT")
    task_root: str = Field(default="tasks", validation_alias="GAMR_TASK_ROOT")
    api_origin: str = Field(default="http://127.0.0.1:6687", validation_alias="GAMR_API_ORIGIN")
    web_origin: str = Field(default="http://127.0.0.1:6688", validation_alias="GAMR_WEB_ORIGIN")
    tyr_mcp_url: str = Field(
        default="https://www.tyr.ai/tyrcli/mcp",
        validation_alias="TYR_MCP_URL",
    )
    tyr_mcp_token: str = Field(default="", validation_alias="TYR_MCP_TOKEN")
    collector_base_url: str = Field(
        default="https://www.tyr.ai/tyrcli/collector",
        validation_alias="TYR_COLLECTOR_BASE_URL",
    )
    collector_username: str = Field(default="", validation_alias="TYR_COLLECTOR_USERNAME")
    collector_password: str = Field(default="", validation_alias="TYR_COLLECTOR_PASSWORD")
    model_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        validation_alias="OPENROUTER_BASE_URL",
    )
    model_api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    model_name: str = Field(default="", validation_alias="TYR_LOOP_MODEL")
    scientist_model_name: str = Field(default="", validation_alias="TYR_LOOP_SCIENTIST_MODEL")
    judge_model_name: str = Field(default="", validation_alias="TYR_LOOP_JUDGE_MODEL")
    chat_model_name: str = Field(default="x-ai/grok-4.5", validation_alias="TYR_LOOP_CHAT_MODEL")
    max_concurrent_runs: int = Field(
        default=3,
        ge=1,
        validation_alias="GAMR_MAX_CONCURRENT_RUNS",
    )
    max_concurrent_decoders: int = Field(
        default=2,
        ge=1,
        validation_alias="GAMR_MAX_CONCURRENT_DECODERS",
    )
    scientist_output_tokens: int = Field(
        default=8192,
        ge=1,
        validation_alias="GAMR_SCIENTIST_OUTPUT_TOKENS",
    )
    sandbox_backend: Literal["docker", "host-unsafe", "disabled"] = Field(
        default="docker",
        validation_alias="GAMR_SANDBOX_BACKEND",
    )
    langfuse_enabled: bool = Field(
        default=False,
        validation_alias="GAMR_LANGFUSE_ENABLED",
    )
    langfuse_public_key: str = Field(
        default="",
        validation_alias=AliasChoices("GAMR_LANGFUSE_PUBLIC_KEY", "LANGFUSE_PUBLIC_KEY"),
    )
    langfuse_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices("GAMR_LANGFUSE_SECRET_KEY", "LANGFUSE_SECRET_KEY"),
    )
    langfuse_host_url: str = Field(
        default="http://127.0.0.1:3000",
        validation_alias=AliasChoices(
            "GAMR_LANGFUSE_HOST_URL", "LANGFUSE_HOST", "LANGFUSE_HOST_URL"
        ),
    )
    langfuse_container_url: str = Field(
        default="http://langfuse-server:3000",
        validation_alias="GAMR_LANGFUSE_CONTAINER_URL",
    )
    langfuse_environment: str = Field(
        default="",
        validation_alias=AliasChoices("GAMR_LANGFUSE_ENVIRONMENT", "LANGFUSE_ENVIRONMENT"),
    )

    @property
    def is_langfuse_valid(self) -> bool:
        return bool(
            self.langfuse_enabled
            and self.langfuse_public_key.strip()
            and self.langfuse_secret_key.strip()
            and self.langfuse_host_url.strip()
        )
