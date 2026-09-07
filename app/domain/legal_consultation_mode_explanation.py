from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.domain.explanation_mode import ExplanationMode
from app.domain.legal_explanation import LegalExplanationProfile
from app.domain.llm_trace import LLMTrace
from llm.models import RAGExplanation


class LegalConsultationModeExplanation(BaseModel):
    """G.9: explicación por modo preservada desde el resultado canónico."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    mode: ExplanationMode
    profile: LegalExplanationProfile

    explanation: RAGExplanation | None = None
    llm_trace: LLMTrace | None = None

    explanation_available: bool
    generation_performed: bool

    source_canonical_preserved: Literal[True] = True
    communication_profile_only: Literal[True] = True

    can_change_legal_decision: Literal[False] = False
    can_change_normative_basis: Literal[False] = False
    can_change_legal_authority: Literal[False] = False
    can_change_evidence: Literal[False] = False
    can_create_second_conclusion: Literal[False] = False
    can_assert_external_legal_authority: Literal[False] = False

    @model_validator(mode="after")
    def validate_mode_explanation(
        self,
    ) -> LegalConsultationModeExplanation:
        if self.profile.mode is not self.mode:
            raise ValueError(
                "G.9 exige que el perfil comunicativo corresponda al modo."
            )

        if self.explanation is None:
            if self.llm_trace is not None:
                raise ValueError(
                    "G.9 no admite traza LLM sin explicación canónica."
                )
            if self.explanation_available or self.generation_performed:
                raise ValueError(
                    "G.9 presenta disponibilidad de explicación inconsistente."
                )
            return self

        if not self.explanation_available:
            raise ValueError(
                "G.9 debe declarar disponible una explicación canónica existente."
            )

        if self.generation_performed != self.explanation.generation_performed:
            raise ValueError(
                "G.9 presenta un estado de generación inconsistente."
            )

        trace = self.llm_trace
        if trace is None:
            raise ValueError(
                "G.9 exige traza LLM para una explicación canónica existente."
            )

        if trace.explanation_mode is not self.mode:
            raise ValueError(
                "G.9 detectó un modo distinto entre explicación y traza LLM."
            )

        if trace.provider_name != self.explanation.provider_name:
            raise ValueError(
                "G.9 detectó proveedor LLM inconsistente."
            )

        if trace.model_name != self.explanation.model_name:
            raise ValueError(
                "G.9 detectó modelo LLM inconsistente."
            )

        answer = self.explanation.answer

        pairs = (
            (trace.evidence_ids, answer.evidence_ids, "evidencia"),
            (trace.normative_refs, answer.normative_refs, "normativa"),
            (trace.rule_refs, answer.rule_refs, "reglas"),
            (trace.calculation_refs, answer.calculation_refs, "cálculos"),
            (trace.cbr_refs, answer.cbr_refs, "CBR"),
            (
                trace.jurisprudence_refs,
                answer.jurisprudence_refs,
                "jurisprudencia",
            ),
            (trace.uncertainties, answer.uncertainties, "incertidumbres"),
        )

        for traced, explained, label in pairs:
            if traced != explained:
                raise ValueError(
                    f"G.9 detectó divergencia de {label} "
                    "entre explicación y traza."
                )

        if trace.generated != self.explanation.generation_performed:
            raise ValueError(
                "G.9 detectó generación LLM inconsistente."
            )

        if trace.requires_human_review != answer.requires_human_review:
            raise ValueError(
                "G.9 detectó revisión humana inconsistente."
            )

        if answer.changes_deterministic_result:
            raise ValueError(
                "G.9 no admite que la explicación modifique "
                "el resultado determinista."
            )

        if answer.asserts_external_legal_authority:
            raise ValueError(
                "G.9 no admite autoridad jurídica externa "
                "introducida por Llama."
            )

        return self
