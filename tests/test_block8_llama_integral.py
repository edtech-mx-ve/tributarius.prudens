from __future__ import annotations

import json

import pytest

from app.services.llm_traceability import build_llm_trace
from llm.errors import LLMResponseValidationError
from llm.models import (
    DeterministicEvidence,
    ExplanationMode,
    LLMGenerationContext,
)
from llm.service import LlamaRAGService
from rag.retrieval.models import RetrievalResult
from tests.test_llm_optional_jurisprudence import jurisprudence_retrieval
from tests.test_llm_service import retrieval_with_hit


class IntegralProvider:
    def __init__(self, *, mode_sensitive: bool = False, **overrides: object) -> None:
        self._mode_sensitive = mode_sensitive
        self._overrides = overrides

    @property
    def provider_name(self) -> str:
        return "integral"

    @property
    def model_name(self) -> str:
        return "integral-model"

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str:
        del response_schema
        analysis = "Análisis fundado."
        if self._mode_sensitive:
            analysis = (
                "Explicación pedagógica paso a paso."
                if context.explanation_mode == ExplanationMode.STUDENT
                else "Análisis jurídico técnico y conciso."
            )

        jurisprudence_refs = [
            item.chunk_id
            for item in context.evidence
            if item.source_type.value == "jurisprudencia"
        ]
        evidence_ids = [item.chunk_id for item in context.evidence]
        payload: dict[str, object] = {
            "summary": "La conclusión jurídica permanece estable.",
            "analysis": analysis,
            "evidence_ids": evidence_ids,
            "normative_refs": ["NORM-001"],
            "rule_refs": ["RULE-001"],
            "calculation_refs": ["ISR=2300.00"],
            "cbr_refs": ["CASE-001"],
            "jurisprudence_refs": jurisprudence_refs,
            "uncertainties": [],
            "requires_human_review": False,
            "changes_deterministic_result": False,
            "asserts_external_legal_authority": False,
        }
        payload.update(self._overrides)
        return json.dumps(payload, ensure_ascii=False)


def deterministic(*, requires_human_review: bool = False) -> DeterministicEvidence:
    return DeterministicEvidence(
        applicable_normative_refs=["NORM-001"],
        rule_conclusions=["RULE-001"],
        calculations=["ISR=2300.00"],
        similar_cases=["CASE-001"],
        requires_human_review=requires_human_review,
    )


def test_block8_abstains_when_documentary_evidence_is_absent() -> None:
    retrieval = RetrievalResult(
        query="Consulta sin evidencia",
        requested_top_k=5,
        candidate_count=0,
        returned_count=0,
        hits=[],
    )

    result = LlamaRAGService(IntegralProvider()).explain(
        retrieval,
        deterministic_evidence=deterministic(),
    )

    assert result.generation_performed is False
    assert result.answer.evidence_ids == []
    assert result.answer.requires_human_review is True


def test_block8_student_and_professional_preserve_same_legal_result() -> None:
    service = LlamaRAGService(IntegralProvider(mode_sensitive=True))

    student = service.explain(
        retrieval_with_hit(),
        deterministic_evidence=deterministic(),
        explanation_mode=ExplanationMode.STUDENT,
    )
    professional = service.explain(
        retrieval_with_hit(),
        deterministic_evidence=deterministic(),
        explanation_mode=ExplanationMode.PROFESSIONAL,
    )

    assert student.answer.summary == professional.answer.summary
    assert student.answer.evidence_ids == professional.answer.evidence_ids
    assert student.answer.normative_refs == professional.answer.normative_refs
    assert student.answer.rule_refs == professional.answer.rule_refs
    assert student.answer.calculation_refs == professional.answer.calculation_refs
    assert student.answer.cbr_refs == professional.answer.cbr_refs
    assert student.answer.analysis != professional.answer.analysis


def test_block8_optional_jurisprudence_is_separate_and_traceable() -> None:
    result = LlamaRAGService(IntegralProvider()).explain(
        retrieval_with_hit(),
        deterministic_evidence=deterministic(),
        jurisprudence_retrieval=jurisprudence_retrieval(),
    )
    trace = build_llm_trace(
        result,
        explanation_mode=ExplanationMode.PROFESSIONAL,
    )

    assert "juris-chunk-0001" in result.answer.evidence_ids
    assert result.answer.jurisprudence_refs == ["juris-chunk-0001"]
    assert "juris-chunk-0001" not in result.answer.normative_refs
    assert trace.jurisprudence_refs == ["juris-chunk-0001"]
    assert trace.normative_refs == ["NORM-001"]


def test_block8_rejects_invented_normative_authority() -> None:
    provider = IntegralProvider(normative_refs=["NORM-INVENTADA"])

    with pytest.raises(LLMResponseValidationError, match="normative_refs"):
        LlamaRAGService(provider).explain(
            retrieval_with_hit(),
            deterministic_evidence=deterministic(),
        )


def test_block8_rejects_attempt_to_override_deterministic_result() -> None:
    provider = IntegralProvider(changes_deterministic_result=True)

    with pytest.raises(LLMResponseValidationError, match="no puede modificar"):
        LlamaRAGService(provider).explain(
            retrieval_with_hit(),
            deterministic_evidence=deterministic(),
        )


def test_block8_rejects_external_legal_authority() -> None:
    provider = IntegralProvider(asserts_external_legal_authority=True)

    with pytest.raises(LLMResponseValidationError, match="autoridad jurídica externa"):
        LlamaRAGService(provider).explain(
            retrieval_with_hit(),
            deterministic_evidence=deterministic(),
        )


def test_block8_preserves_required_human_review() -> None:
    provider = IntegralProvider(requires_human_review=False)

    with pytest.raises(
        LLMResponseValidationError,
        match="no puede eliminar una revisión humana",
    ):
        LlamaRAGService(provider).explain(
            retrieval_with_hit(),
            deterministic_evidence=deterministic(requires_human_review=True),
        )


def test_block8_trace_preserves_provider_mode_and_reasoning_channels() -> None:
    result = LlamaRAGService(IntegralProvider()).explain(
        retrieval_with_hit(),
        deterministic_evidence=deterministic(),
        explanation_mode=ExplanationMode.STUDENT,
    )
    trace = build_llm_trace(
        result,
        explanation_mode=ExplanationMode.STUDENT,
    )

    assert trace.provider_name == "integral"
    assert trace.model_name == "integral-model"
    assert trace.explanation_mode == ExplanationMode.STUDENT
    assert trace.evidence_ids == ["chunk-0001"]
    assert trace.normative_refs == ["NORM-001"]
    assert trace.rule_refs == ["RULE-001"]
    assert trace.calculation_refs == ["ISR=2300.00"]
    assert trace.cbr_refs == ["CASE-001"]
    assert trace.generated is True
