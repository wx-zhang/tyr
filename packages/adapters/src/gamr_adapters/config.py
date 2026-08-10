from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    environment: str = Field(default="development", validation_alias="GAMR_ENVIRONMENT")
    artifact_root: str = Field(default=".gamr", validation_alias="GAMR_ARTIFACT_ROOT")
    dataset_root: str = Field(default="datasets", validation_alias="GAMR_DATASET_ROOT")
    api_origin: str = Field(default="http://127.0.0.1:6687", validation_alias="GAMR_API_ORIGIN")
    web_origin: str = Field(default="http://127.0.0.1:6688", validation_alias="GAMR_WEB_ORIGIN")
    tyr_mcp_url: str = Field(
        default="https://www.tyr.ai/tyrcli/mcp",
        validation_alias="TYR_MCP_URL",
    )
    tyr_mcp_token: str = Field(default="", validation_alias="TYR_MCP_TOKEN")
    model_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        validation_alias="OPENROUTER_BASE_URL",
    )
    model_api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    model_name: str = Field(default="", validation_alias="TYR_LOOP_MODEL")
    scientist_model_name: str = Field(default="", validation_alias="TYR_LOOP_SCIENTIST_MODEL")
    max_concurrent_runs: int = Field(
        default=3,
        ge=1,
        validation_alias="GAMR_MAX_CONCURRENT_RUNS",
    )
