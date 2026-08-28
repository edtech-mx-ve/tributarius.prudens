from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.normative import NormativeVersionView
from app.models.knowledge import NormVersion


class NormativeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_versions_for_legal_unit(
        self,
        legal_unit_id: int,
    ) -> list[NormativeVersionView]:
        statement = (
            select(NormVersion)
            .where(NormVersion.legal_unit_id == legal_unit_id)
            .order_by(
                NormVersion.effective_from.asc(),
                NormVersion.publication_date.asc(),
                NormVersion.id.asc(),
            )
        )
        rows = self._session.scalars(statement).all()
        return [
            NormativeVersionView(
                version_label=row.version_label,
                effective_from=row.effective_from,
                effective_to=row.effective_to,
                fiscal_year=row.fiscal_year,
                publication_date=row.publication_date,
                source_reference=row.source_reference,
            )
            for row in rows
        ]
