from __future__ import annotations

from datetime import date

from sqlalchemy import JSON, Boolean, Date, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.domain.knowledge import KnowledgeLayer, LegalUnitType, RelationType, ValidityStatus


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    layer: Mapped[KnowledgeLayer] = mapped_column(
        Enum(KnowledgeLayer, native_enum=False, length=32), index=True
    )
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    authority: Mapped[str | None] = mapped_column(String(250))
    source_reference: Mapped[str | None] = mapped_column(String(1000))
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    units: Mapped[list[LegalUnit]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )


class LegalUnit(Base):
    __tablename__ = "legal_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    unit_type: Mapped[LegalUnitType] = mapped_column(
        Enum(LegalUnitType, native_enum=False, length=32), index=True
    )
    identifier: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(500))
    text: Mapped[str | None] = mapped_column(Text)
    matter: Mapped[str | None] = mapped_column(String(200), index=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(50), index=True)
    parent_unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("legal_units.id", ondelete="SET NULL")
    )

    source: Mapped[KnowledgeSource] = relationship(back_populates="units")
    parent: Mapped[LegalUnit | None] = relationship(
        remote_side="LegalUnit.id",
        back_populates="children",
    )
    children: Mapped[list[LegalUnit]] = relationship(back_populates="parent")
    versions: Mapped[list[NormVersion]] = relationship(
        back_populates="legal_unit",
        cascade="all, delete-orphan",
    )


class NormVersion(Base):
    __tablename__ = "norm_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    legal_unit_id: Mapped[int] = mapped_column(
        ForeignKey("legal_units.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version_label: Mapped[str] = mapped_column(String(100), nullable=False)
    publication_date: Mapped[date | None] = mapped_column(Date)
    effective_from: Mapped[date | None] = mapped_column(Date, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, index=True)
    fiscal_year: Mapped[int | None] = mapped_column(Integer, index=True)
    validity_status: Mapped[ValidityStatus] = mapped_column(
        Enum(ValidityStatus, native_enum=False, length=32),
        default=ValidityStatus.UNKNOWN,
        index=True,
    )
    source_reference: Mapped[str | None] = mapped_column(String(1000))

    legal_unit: Mapped[LegalUnit] = relationship(back_populates="versions")


class KnowledgeRelation(Base):
    __tablename__ = "knowledge_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_unit_id: Mapped[int] = mapped_column(
        ForeignKey("legal_units.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    target_unit_id: Mapped[int] = mapped_column(
        ForeignKey("legal_units.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    relation_type: Mapped[RelationType] = mapped_column(
        Enum(RelationType, native_enum=False, length=40), index=True
    )
    rationale: Mapped[str | None] = mapped_column(String(1000))


class MasterMatrixEntry(Base):
    __tablename__ = "master_matrix_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_key: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    module_name: Mapped[str] = mapped_column(String(200), nullable=False)
    prodecon_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    unam_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    normative_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    jurisprudential_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    rule_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    calculation_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    cbr_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
