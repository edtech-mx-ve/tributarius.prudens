from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domain.normative import NormativeApplicabilityResult
from app.services.normative_service import NormativeService

router = APIRouter(prefix="/normative", tags=["normative"])


@router.get(
    "/legal-units/{legal_unit_id}/applicable",
    response_model=list[NormativeApplicabilityResult],
)
def get_applicable_normative_versions(
    legal_unit_id: int,
    session: Annotated[Session, Depends(get_db)],
    query_date: Annotated[date, Query()],
    fiscal_year: Annotated[int | None, Query(ge=1900, le=2200)] = None,
) -> list[NormativeApplicabilityResult]:
    return NormativeService(session).resolve_applicable_versions(
        legal_unit_id=legal_unit_id,
        query_date=query_date,
        query_fiscal_year=fiscal_year,
    )
