from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ReadinessState(StrEnum):
    READY = "ready"
    DEGRADED = "degraded"
    NOT_READY = "not_ready"


class RuntimeCapability(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    available: bool
    detail: str = Field(min_length=1, max_length=500)


class ReadinessReport(BaseModel):
    state: ReadinessState
    service: str = "tributarius-prudens"
    platform: str
    runtime_profile: str
    capabilities: list[RuntimeCapability]
