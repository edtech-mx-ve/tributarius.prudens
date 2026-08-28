from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.chunks import ChunkMetadata


class RetrievalHit(BaseModel):
    rank: int = Field(ge=1)
    score: float
    chunk_id: str
    text: str
    metadata: ChunkMetadata


class RetrievalResult(BaseModel):
    query: str = Field(min_length=1)
    requested_top_k: int = Field(ge=1)
    candidate_count: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    hits: list[RetrievalHit]
