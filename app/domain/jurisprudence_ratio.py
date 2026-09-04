from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.jurisprudence import JurisprudenceCriterionType


class JurisprudenceRatioSourceSection(StrEnum):
    JUSTIFICATION = "justification"
    UNKNOWN = "unknown"


class JurisprudenceRatioRecord(BaseModel):
    """E.5: estructura oficial usada para localizar la ratio decidendi."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=3, max_length=200)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    criterion_type: JurisprudenceCriterionType
    facts_text: str | None = Field(default=None, max_length=12000)
    legal_criterion_text: str | None = Field(default=None, max_length=12000)
    justification_text: str | None = Field(default=None, max_length=24000)
    facts_source_pages: list[int] = Field(default_factory=list, max_length=100)
    legal_criterion_source_pages: list[int] = Field(default_factory=list, max_length=100)
    justification_source_pages: list[int] = Field(default_factory=list, max_length=100)
    ratio_source_section: JurisprudenceRatioSourceSection
    ratio_source_text: str | None = Field(default=None, max_length=24000)
    structured_thesis_sections_established: bool
    ratio_source_established: bool
    source_scope: Literal["session"] = "session"
    user_attached: Literal[True] = True
    ratio_source_is_official_justification: Literal[True] = True
    ratio_material_delimitation_completed: Literal[False] = False
    controversy_equivalence_evaluated: Literal[False] = False
    material_facts_equivalence_evaluated: Literal[False] = False
    legal_applicability_evaluated: Literal[False] = False
    can_control_legal_decision: Literal[False] = False
    requires_human_review: bool = True
