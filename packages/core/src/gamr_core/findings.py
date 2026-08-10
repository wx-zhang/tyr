from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str = Field(min_length=1)
    severity: str = "unknown"
    description: str = ""
    evidence: list[str] = []
