from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.cbr import CBRRetrievalResult, CBRReuseAssessment
from app.domain.hybrid_reasoning import NormalizedReasoningResult, ReasoningSource


class LegalConsultationRetrievedCBR(BaseModel):
    """G.6: CBR recuperado y evaluado, preservado como apoyo analogico."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    retrieval: CBRRetrievalResult | None = None
    reuse_assessments: list[CBRReuseAssessment] = Field(default_factory=list)
    normalized_reasoning: NormalizedReasoningResult
    hybrid_controlling_source: Literal["rbs"] | None = None

    analogical_role_preserved: Literal[True] = True
    source_results_already_computed: Literal[True] = True
    source_result_reexecuted: Literal[False] = False
    can_be_legal_authority: Literal[False] = False
    can_control_legal_decision: Literal[False] = False

    @model_validator(mode="after")
    def validate_retrieved_cbr(
        self,
    ) -> LegalConsultationRetrievedCBR:
        if (
            self.normalized_reasoning.reasoning_source
            is not ReasoningSource.CBR
        ):
            raise ValueError(
                "G.6 exige razonamiento normalizado de origen CBR."
            )

        if self.retrieval is None:
            if self.reuse_assessments:
                raise ValueError(
                    "G.6 no permite evaluaciones de reutilizacion sin retrieval."
                )
            return self

        if self.retrieval.returned_count != len(self.retrieval.matches):
            raise ValueError(
                "G.6 detecto un conteo CBR recuperado inconsistente."
            )

        match_ids = [
            item.case_id
            for item in self.retrieval.matches
        ]
        assessment_ids = [
            item.case_id
            for item in self.reuse_assessments
        ]

        if assessment_ids != match_ids:
            raise ValueError(
                "G.6 exige una evaluacion de reutilizacion por cada caso recuperado."
            )

        return self
