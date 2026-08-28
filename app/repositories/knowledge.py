from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.knowledge import (
    KnowledgeRelationCreate,
    LegalUnitCreate,
    MasterMatrixEntryCreate,
    NormVersionCreate,
    SourceCreate,
)
from app.models.knowledge import (
    KnowledgeRelation,
    KnowledgeSource,
    LegalUnit,
    MasterMatrixEntry,
    NormVersion,
)


class KnowledgeRepository:
    """Repositorio de persistencia del modelo de conocimiento."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add_source(self, data: SourceCreate) -> KnowledgeSource:
        entity = KnowledgeSource(**data.model_dump())
        self._session.add(entity)
        self._session.flush()
        return entity

    def add_legal_unit(self, data: LegalUnitCreate) -> LegalUnit:
        self._require_source(data.source_id)
        if data.parent_unit_id is not None:
            self._require_unit(data.parent_unit_id)
        entity = LegalUnit(**data.model_dump())
        self._session.add(entity)
        self._session.flush()
        return entity

    def add_norm_version(self, data: NormVersionCreate) -> NormVersion:
        self._require_unit(data.legal_unit_id)
        entity = NormVersion(**data.model_dump())
        self._session.add(entity)
        self._session.flush()
        return entity

    def add_relation(self, data: KnowledgeRelationCreate) -> KnowledgeRelation:
        if data.source_unit_id == data.target_unit_id:
            raise ValueError("Una unidad no puede relacionarse consigo misma.")
        self._require_unit(data.source_unit_id)
        self._require_unit(data.target_unit_id)
        entity = KnowledgeRelation(**data.model_dump())
        self._session.add(entity)
        self._session.flush()
        return entity

    def upsert_matrix_entry(self, data: MasterMatrixEntryCreate) -> MasterMatrixEntry:
        entity = self._session.scalar(
            select(MasterMatrixEntry).where(MasterMatrixEntry.module_key == data.module_key)
        )
        payload = data.model_dump()
        if entity is None:
            entity = MasterMatrixEntry(**payload)
            self._session.add(entity)
        else:
            for field, value in payload.items():
                setattr(entity, field, value)
        self._session.flush()
        return entity

    def list_matrix_entries(self) -> list[MasterMatrixEntry]:
        statement = select(MasterMatrixEntry).order_by(MasterMatrixEntry.module_key)
        return list(self._session.scalars(statement).all())

    def _require_source(self, source_id: int) -> KnowledgeSource:
        entity = self._session.get(KnowledgeSource, source_id)
        if entity is None:
            raise ValueError(f"No existe knowledge_source con id={source_id}.")
        return entity

    def _require_unit(self, unit_id: int) -> LegalUnit:
        entity = self._session.get(LegalUnit, unit_id)
        if entity is None:
            raise ValueError(f"No existe legal_unit con id={unit_id}.")
        return entity
