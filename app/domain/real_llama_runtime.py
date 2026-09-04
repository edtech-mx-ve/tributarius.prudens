from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RealLlamaRuntimeDescriptor(BaseModel):
    """Descriptor F.11 del proveedor Llama real activado en runtime."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    provider_name: Literal["llama-cpp-python"] = "llama-cpp-python"
    model_name: str = Field(min_length=1, max_length=200)
    model_path: str = Field(min_length=1, max_length=1000)
    model_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    n_ctx: int = Field(ge=512, le=131072)
    max_tokens: int = Field(ge=32, le=8192)
    n_threads: int = Field(ge=1, le=256)
    n_batch: int = Field(ge=8, le=4096)

    real_llama_active: Literal[True] = True
    h1_uses_real_llama: Literal[True] = True
    h2_uses_real_llama: Literal[True] = True
    semantic_verifier_uses_real_llama: Literal[True] = True
    explanation_uses_real_llama: Literal[True] = True
    external_llm_api_used: Literal[False] = False
    mock_runtime_allowed: Literal[False] = False
