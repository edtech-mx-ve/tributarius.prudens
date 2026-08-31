from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel, Field

from app.domain.chunks import LegalChunkType
from app.domain.documents import SourceType


def _normalize_legal_identifier(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return " ".join(re.findall(r"[a-z0-9-]+", without_marks))


class RetrievalFilters(BaseModel):
    source_types: set[SourceType] = Field(default_factory=set)
    chunk_types: set[LegalChunkType] = Field(default_factory=set)
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    version_label: str | None = Field(default=None, min_length=1, max_length=100)
    document_ids: set[str] = Field(default_factory=set)
    legal_identifier: str | None = Field(default=None, min_length=1, max_length=300)

    def matches(
        self,
        *,
        source_type: SourceType,
        chunk_type: LegalChunkType,
        fiscal_year: int | None,
        version_label: str | None,
        document_id: str,
        legal_identifier: str | None = None,
    ) -> bool:
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
        if self.legal_identifier is not None:
            if legal_identifier is None:
                return False
            if _normalize_legal_identifier(legal_identifier) != _normalize_legal_identifier(
                self.legal_identifier
            ):
                return False
        return True
