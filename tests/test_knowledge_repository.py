from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.domain.knowledge import (
    KnowledgeLayer,
    KnowledgeRelationCreate,
    LegalUnitCreate,
    LegalUnitType,
    MasterMatrixEntryCreate,
    NormVersionCreate,
    RelationType,
    SourceCreate,
)
from app.models import knowledge as knowledge_models  # noqa: F401
from app.repositories.knowledge import KnowledgeRepository


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_repository_persists_source_unit_version_and_relation() -> None:
    with make_session() as session:
        repo = KnowledgeRepository(session)
        source = repo.add_source(
            SourceCreate(layer=KnowledgeLayer.NORMATIVA, name="Ley de prueba", verified=True)
        )
        unit1 = repo.add_legal_unit(
            LegalUnitCreate(
                source_id=source.id,
                unit_type=LegalUnitType.ARTICLE,
                identifier="art-1",
                title="Artículo 1",
            )
        )
        unit2 = repo.add_legal_unit(
            LegalUnitCreate(
                source_id=source.id,
                unit_type=LegalUnitType.ARTICLE,
                identifier="art-2",
                title="Artículo 2",
            )
        )
        version = repo.add_norm_version(
            NormVersionCreate(legal_unit_id=unit1.id, version_label="2026")
        )
        relation = repo.add_relation(
            KnowledgeRelationCreate(
                source_unit_id=unit1.id,
                target_unit_id=unit2.id,
                relation_type=RelationType.RELATES_TO,
            )
        )
        session.commit()

        assert source.id > 0
        assert version.legal_unit_id == unit1.id
        assert relation.target_unit_id == unit2.id


def test_matrix_upsert_is_idempotent_by_module_key() -> None:
    with make_session() as session:
        repo = KnowledgeRepository(session)
        first = repo.upsert_matrix_entry(
            MasterMatrixEntryCreate(
                module_key="perfil_fiscal",
                module_name="Perfil fiscal",
                prodecon_refs=["P-1"],
            )
        )
        first_id = first.id
        repo.upsert_matrix_entry(
            MasterMatrixEntryCreate(
                module_key="perfil_fiscal",
                module_name="Perfil fiscal actualizado",
                prodecon_refs=["P-2"],
            )
        )
        session.commit()

        rows = repo.list_matrix_entries()
        assert len(rows) == 1
        assert rows[0].id == first_id
        assert rows[0].module_name == "Perfil fiscal actualizado"
        assert rows[0].prodecon_refs == ["P-2"]
