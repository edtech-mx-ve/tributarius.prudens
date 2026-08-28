from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.chunks import LegalChunkType
from app.domain.documents import SourceType


class RetrievalFilters(BaseModel):
    source_types: set[SourceType] = Field(default_factory=set)
    chunk_types: set[LegalChunkType] = Field(default_factory=set)
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    version_label: str | None = Field(default=None, min_length=1, max_length=100)
    document_ids: set[str] = Field(default_factory=set)

    def matches(self, *, source_type: SourceType, chunk_type: LegalChunkType,
                fiscal_year: int | None, version_label: str | None,
                document_id: str) -> bool:
        if self.source_types and source_type not in self.source_types:
            return False
        if self.chunk_types and chunk_type not in self.chunk_types:
            return False
        if self.fiscal_year is not None and fiscal_year != self.fiscal_year:
            return False
        if self.version_label is not None and version_label != self.version_label:
            return False
        if self.document_ids and document_id not in self.document_ids:
            return False
        return True
