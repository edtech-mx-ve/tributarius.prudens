from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SessionJurisprudenceHit(BaseModel):
    """Resultado documental recuperado desde jurisprudencia temporal de sesión."""

    model_config = ConfigDict(extra="forbid")

    rank: int = Field(ge=1)
    score: float = Field(ge=0.0, le=1.0)
    document_id: str = Field(min_length=3, max_length=200)
    original_filename: str = Field(min_length=1, max_length=500)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    page_number: int = Field(ge=1)
    text: str = Field(min_length=1)


class SessionJurisprudenceRetrievalResult(BaseModel):
    """Recuperación previa a determinar aplicabilidad jurídica."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    candidate_count: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    hits: list[SessionJurisprudenceHit] = Field(default_factory=list)
