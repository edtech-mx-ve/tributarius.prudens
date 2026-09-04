from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.jurisprudence_ratio import JurisprudenceRatioSourceSection
from app.domain.llama_hybrid_context import LlamaHybridContextPhase
from app.domain.query import FactOrigin


class HybridLlamaHypothesisKind(StrEnum):
    H1_FISCAL = "h1_fiscal"
    H2_JURISPRUDENTIAL_RATIO = "h2_jurisprudential_ratio"


class H1FactReference(BaseModel):
    """Referencia exacta a un hecho disponible en el contexto temprano F.2."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=1000)
    origin: FactOrigin


class FiscalHypothesisH1Draft(BaseModel):
    """Salida generativa H1 antes de aplicar la frontera determinista F.3."""

    model_config = ConfigDict(extra="forbid")

    legal_problem: str = Field(min_length=1, max_length=2000)
    proposition: str = Field(min_length=1, max_length=4000)
    facts_used: list[H1FactReference] = Field(default_factory=list, max_length=40)
    institutions: list[str] = Field(default_factory=list, max_length=20)
    candidate_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    candidate_normative_questions: list[str] = Field(default_factory=list, max_length=20)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    uncertainties: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0.0, le=1.0)
    requires_validation: Literal[True] = True
    changes_deterministic_result: Literal[False] = False
    can_control_legal_decision: Literal[False] = False
    asserts_external_legal_authority: Literal[False] = False

    @model_validator(mode="after")
    def validate_unique_references(self) -> FiscalHypothesisH1Draft:
        for values in (
            self.institutions,
            self.candidate_normative_refs,
            self.candidate_normative_questions,
            self.assumptions,
            self.uncertainties,
        ):
            if len(values) != len(set(values)):
                raise ValueError("H1 no admite referencias duplicadas.")
        fact_keys = [(item.name, item.value, item.origin.value) for item in self.facts_used]
        if len(fact_keys) != len(set(fact_keys)):
            raise ValueError("H1 no admite hechos duplicados.")
        return self


class ControlledFiscalHypothesisH1(BaseModel):
    """Hipótesis fiscal abductiva, temprana, trazable y carente de autoridad."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    kind: Literal[HybridLlamaHypothesisKind.H1_FISCAL] = HybridLlamaHypothesisKind.H1_FISCAL
    hypothesis_id: str = Field(pattern=r"^H1-[a-f0-9]{16}$")
    source_context_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_phase: Literal[LlamaHybridContextPhase.INITIAL_FISCAL_HYPOTHESIS] = (
        LlamaHybridContextPhase.INITIAL_FISCAL_HYPOTHESIS
    )
    legal_problem: str = Field(min_length=1, max_length=2000)
    proposition: str = Field(min_length=1, max_length=4000)
    facts_used: list[H1FactReference] = Field(default_factory=list, max_length=40)
    institutions: list[str] = Field(default_factory=list, max_length=20)
    candidate_normative_refs: list[str] = Field(default_factory=list, max_length=100)
    candidate_normative_questions: list[str] = Field(default_factory=list, max_length=20)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    uncertainties: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0.0, le=1.0)
    provider_name: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=200)
    requires_validation: Literal[True] = True
    must_be_contrasted_with_rbs: Literal[True] = True
    must_be_contrasted_with_cbr: Literal[True] = True
    normative_validation_pending: Literal[True] = True
    changes_deterministic_result: Literal[False] = False
    can_control_legal_decision: Literal[False] = False
    asserts_external_legal_authority: Literal[False] = False


class FiscalHypothesisH1Result(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation_performed: bool
    hypothesis: ControlledFiscalHypothesisH1 | None = None
    requires_human_review: bool = False
    trace: list[str] = Field(default_factory=list, max_length=30)


class JurisprudentialSupportSpan(BaseModel):
    """Fragmento literal usado para anclar una premisa H2 en la Justificación."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=1800)
    page: int = Field(ge=1)
    source_section: Literal[JurisprudenceRatioSourceSection.JUSTIFICATION] = (
        JurisprudenceRatioSourceSection.JUSTIFICATION
    )


class JurisprudentialRatioH2Draft(BaseModel):
    """Salida generativa H2 antes de validar su fidelidad a la Justificación."""

    model_config = ConfigDict(extra="forbid")

    legal_question: str = Field(min_length=1, max_length=2000)
    material_facts: list[str] = Field(default_factory=list, max_length=20)
    interpreted_norms: list[str] = Field(default_factory=list, max_length=100)
    essential_premises: list[str] = Field(min_length=1, max_length=20)
    proposed_ratio: str = Field(min_length=1, max_length=4000)
    possible_obiter: list[str] = Field(default_factory=list, max_length=20)
    supporting_spans: list[JurisprudentialSupportSpan] = Field(min_length=1, max_length=20)
    uncertainties: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0.0, le=1.0)
    requires_validation: Literal[True] = True
    changes_deterministic_result: Literal[False] = False
    can_control_legal_decision: Literal[False] = False
    asserts_external_legal_authority: Literal[False] = False

    @model_validator(mode="after")
    def validate_unique_references(self) -> JurisprudentialRatioH2Draft:
        for values in (
            self.material_facts,
            self.interpreted_norms,
            self.essential_premises,
            self.possible_obiter,
            self.uncertainties,
        ):
            if len(values) != len(set(values)):
                raise ValueError("H2 no admite referencias duplicadas.")
        span_keys = [(item.text, item.page) for item in self.supporting_spans]
        if len(span_keys) != len(set(span_keys)):
            raise ValueError("H2 no admite fragmentos de soporte duplicados.")
        return self


class ControlledJurisprudentialRatioH2(BaseModel):
    """Hipótesis de ratio decidendi reconstruida sólo desde la Justificación."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    kind: Literal[HybridLlamaHypothesisKind.H2_JURISPRUDENTIAL_RATIO] = (
        HybridLlamaHypothesisKind.H2_JURISPRUDENTIAL_RATIO
    )
    ratio_id: str = Field(pattern=r"^H2-[a-f0-9]{16}$")
    document_id: str = Field(min_length=3, max_length=200)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_context_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_phase: Literal[LlamaHybridContextPhase.JURISPRUDENTIAL_RATIO] = (
        LlamaHybridContextPhase.JURISPRUDENTIAL_RATIO
    )
    ratio_source_section: Literal[JurisprudenceRatioSourceSection.JUSTIFICATION] = (
        JurisprudenceRatioSourceSection.JUSTIFICATION
    )
    justification_source_pages: list[int] = Field(min_length=1, max_length=100)
    legal_question: str = Field(min_length=1, max_length=2000)
    material_facts: list[str] = Field(default_factory=list, max_length=20)
    interpreted_norms: list[str] = Field(default_factory=list, max_length=100)
    essential_premises: list[str] = Field(min_length=1, max_length=20)
    proposed_ratio: str = Field(min_length=1, max_length=4000)
    possible_obiter: list[str] = Field(default_factory=list, max_length=20)
    supporting_spans: list[JurisprudentialSupportSpan] = Field(min_length=1, max_length=20)
    uncertainties: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0.0, le=1.0)
    provider_name: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=200)
    requires_validation: Literal[True] = True
    ratio_material_delimitation_completed: Literal[False] = False
    controversy_equivalence_evaluated: Literal[False] = False
    material_facts_equivalence_evaluated: Literal[False] = False
    legal_applicability_evaluated: Literal[False] = False
    changes_deterministic_result: Literal[False] = False
    can_control_legal_decision: Literal[False] = False
    asserts_external_legal_authority: Literal[False] = False


class JurisprudentialRatioH2Result(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation_performed: bool
    ratio: ControlledJurisprudentialRatioH2 | None = None
    requires_human_review: bool = True
    trace: list[str] = Field(default_factory=list, max_length=30)
