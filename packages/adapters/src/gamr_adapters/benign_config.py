from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values
from gamr_core.benign import Contract, Submission
from pydantic import Field, TypeAdapter
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkspaceBinding(Contract):
    workspace_id: str = Field(min_length=1)
    url: str = Field(pattern=r"^https://[^\s]+/mcp$")
    token_env: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,100}$")


class BenignSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)
    root: Path = Field(default=Path(".gamr/benign"), validation_alias="BENIGN_ROOT")
    workspaces_file: Path = Field(
        default=Path(".gamr/benign/workspaces.json"), validation_alias="BENIGN_WORKSPACES_FILE"
    )
    workers: int = Field(default=3, ge=1, le=8, validation_alias="BENIGN_WORKERS")

    def bindings(self) -> dict[str, WorkspaceBinding]:
        if not self.workspaces_file.exists():
            return {}
        bindings = TypeAdapter(dict[str, WorkspaceBinding]).validate_json(
            self.workspaces_file.read_text(encoding="utf-8")
        )
        if len({b.workspace_id for b in bindings.values()}) != len(bindings):
            raise ValueError("Use one alias per workspace so participant locks remain effective")
        return bindings

    def token(self, binding: WorkspaceBinding) -> str:
        value = os.environ.get(binding.token_env) or dotenv_values(".env").get(binding.token_env)
        if not value:
            raise ValueError(f"Missing server-side credential: {binding.token_env}")
        return value

    def validate_submission(self, submission: Submission) -> None:
        bindings = self.bindings()
        for scenario in submission.scenarios:
            if not set(scenario.participants).issubset(bindings):
                raise ValueError("Scenario contains unconfigured workspace aliases")
            self.token(bindings[scenario.workspace])
