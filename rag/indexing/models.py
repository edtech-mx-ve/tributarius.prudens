from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IndexManifest(BaseModel):
    schema_version: str = "1.0"
    created_at_utc: datetime
    model_name: str = Field(min_length=3, max_length=200)
    vector_dimension: int = Field(gt=0)
    metric: str = "cosine_via_inner_product"
    normalized: bool = True
    chunk_count: int = Field(gt=0)
    source_chunk_files: list[str]
    index_filename: str = "index.faiss"
    chunks_filename: str = "chunks.jsonl"
    index_sha256: str = Field(min_length=64, max_length=64)
    chunks_sha256: str = Field(min_length=64, max_length=64)


class VectorSearchHit(BaseModel):
    rank: int = Field(ge=1)
    chunk_id: str
    score: float
