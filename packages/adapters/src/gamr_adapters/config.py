from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GAMR_", env_nested_delimiter="__", env_file=".env", extra="ignore"
    )

    environment: str = "development"
    artifact_root: str = ".gamr"
    dataset_root: str = "datasets"
    api_origin: str = "http://127.0.0.1:6687"
    web_origin: str = "http://127.0.0.1:6688"
    tyr_mcp_url: str = "https://www.tyr.ai/tyrcli/mcp"
    tyr_mcp_token: str = ""
    model_base_url: str = "https://openrouter.ai/api/v1"
    model_api_key: str = ""
    model_name: str = ""
    max_concurrent_runs: int = Field(default=3, ge=1)
