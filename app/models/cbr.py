from __future__ import annotations

from sqlalchemy import JSON, Boolean, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.domain.cbr import CaseStatus


class CBRCaseRecord(Base):
    __tablename__ = "cbr_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus, native_enum=False, length=32),
        index=True,
        nullable=False,
    )
    taxpayer_type: Mapped[str] = mapped_column(String(100), index=True)
    activity: Mapped[str] = mapped_column(String(200))
    tax: Mapped[str] = mapped_column(String(100), index=True)
    problem_type: Mapped[str] = mapped_column(String(200), index=True)
    authority_act: Mapped[str | None] = mapped_column(String(200))
    procedural_stage: Mapped[str | None] = mapped_column(String(200))
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True)
    resolution_summary: Mapped[str] = mapped_column(Text)
    normative_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    anonymized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    validated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
