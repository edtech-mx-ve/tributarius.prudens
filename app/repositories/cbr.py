from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.cbr import CaseStatus, CBRCase
from app.models.cbr import CBRCaseRecord


class CBRRepository:
    """Persistencia portable SQLite/PostgreSQL para casos validados."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_domain(record: CBRCaseRecord) -> CBRCase:
        return CBRCase(
            case_id=record.case_id,
            status=record.status,
            taxpayer_type=record.taxpayer_type,
            activity=record.activity,
            tax=record.tax,
            problem_type=record.problem_type,
            authority_act=record.authority_act,
            procedural_stage=record.procedural_stage,
            fiscal_year=record.fiscal_year,
            resolution_summary=record.resolution_summary,
            normative_refs=record.normative_refs,
            source_refs=record.source_refs,
            anonymized=record.anonymized,
            validated=record.validated,
        )

    def add_case(self, case: CBRCase) -> CBRCase:
        if self._session.scalar(
            select(CBRCaseRecord).where(CBRCaseRecord.case_id == case.case_id)
        ) is not None:
            raise ValueError(f"Ya existe el caso {case.case_id}.")
        record = CBRCaseRecord(**case.model_dump())
        self._session.add(record)
        self._session.flush()
        return self._to_domain(record)

    def list_retrievable_cases(self) -> list[CBRCase]:
        statement = (
            select(CBRCaseRecord)
            .where(
                CBRCaseRecord.status.in_(
                    [CaseStatus.ACTIVE, CaseStatus.HISTORICAL]
                )
            )
            .order_by(CBRCaseRecord.case_id)
        )
        return [self._to_domain(item) for item in self._session.scalars(statement).all()]

    def set_status(self, case_id: str, status: CaseStatus) -> CBRCase:
        record = self._session.scalar(
            select(CBRCaseRecord).where(CBRCaseRecord.case_id == case_id)
        )
        if record is None:
            raise ValueError(f"No existe el caso {case_id}.")
        record.status = status
        self._session.flush()
        return self._to_domain(record)
