from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CloudflareWorkersAIRuntimeDescriptor(BaseModel):
    """Descriptor del Llama real remoto usado mediante Cloudflare Workers AI."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    provider_name: Literal["cloudflare_workers_ai"] = "cloudflare_workers_ai"
    model_name: str = Field(min_length=1, max_length=300)
    base_url: str = Field(min_length=1, max_length=1000)
    max_tokens: int = Field(ge=32, le=8192)
    timeout_seconds: float = Field(gt=0, le=600)

    real_llama_active: Literal[True] = True
    h1_uses_real_llama: Literal[True] = True
    h2_uses_real_llama: Literal[True] = True
    semantic_verifier_uses_real_llama: Literal[True] = True
    explanation_uses_real_llama: Literal[True] = True
    external_llm_api_used: Literal[True] = True
    mock_runtime_allowed: Literal[False] = False
