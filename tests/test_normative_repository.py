from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.domain.knowledge import (
    KnowledgeLayer,
    LegalUnitType,
    ValidityStatus,
)
from app.models.knowledge import KnowledgeSource, LegalUnit, NormVersion
from app.repositories.normative import NormativeRepository
from app.services.normative_service import NormativeService


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed(session: Session) -> int:
    source = KnowledgeSource(
        layer=KnowledgeLayer.NORMATIVA,
        name="Fuente normativa de prueba",
        verified=True,
    )
    session.add(source)
    session.flush()

    unit = LegalUnit(
        source_id=source.id,
        unit_type=LegalUnitType.ARTICLE,
        identifier="Artículo de prueba",
        jurisdiction="MX",
    )
    session.add(unit)
    session.flush()

    session.add_all(
        [
            NormVersion(
                legal_unit_id=unit.id,
                version_label="2025",
                publication_date=date(2024, 12, 31),
                effective_from=date(2025, 1, 1),
                effective_to=date(2025, 12, 31),
                fiscal_year=2025,
                validity_status=ValidityStatus.HISTORICAL,
            ),
            NormVersion(
                legal_unit_id=unit.id,
                version_label="2026",
                publication_date=date(2025, 12, 31),
                effective_from=date(2026, 1, 1),
                effective_to=date(2026, 12, 31),
                fiscal_year=2026,
                validity_status=ValidityStatus.CURRENT,
            ),
        ]
    )
    session.commit()
    return unit.id


def test_repository_lists_versions() -> None:
    with _session() as session:
        unit_id = _seed(session)
        versions = NormativeRepository(session).list_versions_for_legal_unit(unit_id)

    assert [version.version_label for version in versions] == ["2025", "2026"]


def test_service_resolves_only_applicable_version() -> None:
    with _session() as session:
        unit_id = _seed(session)
        results = NormativeService(session).resolve_applicable_versions(
            legal_unit_id=unit_id,
            query_date=date(2026, 8, 27),
            query_fiscal_year=2026,
        )

    assert [result.version_label for result in results] == ["2026"]
