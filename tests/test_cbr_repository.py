from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.domain.cbr import CaseStatus, CBRCase
from app.repositories.cbr import CBRRepository


def make_case(case_id: str, status: CaseStatus) -> CBRCase:
    return CBRCase(
        case_id=case_id,
        status=status,
        taxpayer_type="individual",
        activity="servicios",
        tax="ISR",
        problem_type="obligaciones",
        fiscal_year=2026,
        resolution_summary="Caso.",
        source_refs=["SRC"],
    )


def test_repository_filters_non_retrievable_statuses() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repo = CBRRepository(session)
        repo.add_case(make_case("CASE-A", CaseStatus.ACTIVE))
        repo.add_case(make_case("CASE-B", CaseStatus.SUPERSEDED))
        assert [item.case_id for item in repo.list_retrievable_cases()] == ["CASE-A"]


def test_repository_updates_status() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repo = CBRRepository(session)
        repo.add_case(make_case("CASE-C", CaseStatus.ACTIVE))
        updated = repo.set_status("CASE-C", CaseStatus.INVALIDATED)
        assert updated.status == CaseStatus.INVALIDATED
