from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.domain.normative import (
    NormativeApplicabilityResult,
    NormativeSelectionRequest,
)
from app.repositories.normative import NormativeRepository
from app.services.normative_engine import select_applicable_versions


class NormativeService:
    def __init__(self, session: Session) -> None:
        self._repository = NormativeRepository(session)

    def resolve_applicable_versions(
        self,
        *,
        legal_unit_id: int,
        query_date: date,
        query_fiscal_year: int | None,
    ) -> list[NormativeApplicabilityResult]:
        versions = self._repository.list_versions_for_legal_unit(legal_unit_id)
        request = NormativeSelectionRequest(
            legal_unit_id=legal_unit_id,
            query_date=query_date,
            query_fiscal_year=query_fiscal_year,
        )
        return select_applicable_versions(request, versions)
