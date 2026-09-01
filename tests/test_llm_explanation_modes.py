import json

from llm.models import DeterministicEvidence, ExplanationMode, LLMGenerationContext
from llm.service import LlamaRAGService
from tests.test_llm_service import retrieval_with_hit


class ModeAwareProvider:
    def __init__(self) -> None:
        self.contexts: list[LLMGenerationContext] = []

    @property
    def provider_name(self) -> str:
        return "mode-aware"

    @property
    def model_name(self) -> str:
        return "mode-aware-model"

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str:
        del response_schema
        self.contexts.append(context)
        prefix = (
            "Explicación pedagógica."
            if context.explanation_mode == ExplanationMode.STUDENT
            else "Explicación jurídica técnica."
        )
        return json.dumps(
            {
                "summary": "La conclusión jurídica es la misma.",
                "analysis": prefix,
                "evidence_ids": ["chunk-0001"],
                "normative_refs": ["NORM-001"],
                "rule_refs": ["RULE-001"],
                "calculation_refs": ["ISR=2300.00"],
                "cbr_refs": ["CASE-001"],
                "jurisprudence_refs": [],
                "uncertainties": [],
                "requires_human_review": False,
                "changes_deterministic_result": False,
                "asserts_external_legal_authority": False,
            },
            ensure_ascii=False,
        )


def deterministic() -> DeterministicEvidence:
    return DeterministicEvidence(
        applicable_normative_refs=["NORM-001"],
        rule_conclusions=["RULE-001"],
        calculations=["ISR=2300.00"],
        similar_cases=["CASE-001"],
    )


def test_student_and_professional_share_legal_conclusion_and_references() -> None:
    provider = ModeAwareProvider()
    service = LlamaRAGService(provider)

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


def test_student_mode_receives_only_pedagogical_presentation_instructions() -> None:
    context = LlamaRAGService._context_from_retrieval(
        retrieval_with_hit(),
        deterministic_evidence=deterministic(),
        explanation_mode=ExplanationMode.STUDENT,
    )

    assert context.explanation_mode == ExplanationMode.STUDENT
    assert context.presentation_instructions == [
        "Explicar conceptos jurídicos con lenguaje pedagógico.",
        "Desarrollar el razonamiento paso a paso.",
        "Relacionar hechos, normas y conclusión de forma explícita.",
    ]


def test_professional_mode_receives_only_technical_presentation_instructions() -> None:
    context = LlamaRAGService._context_from_retrieval(
        retrieval_with_hit(),
        deterministic_evidence=deterministic(),
        explanation_mode=ExplanationMode.PROFESSIONAL,
    )

    assert context.explanation_mode == ExplanationMode.PROFESSIONAL
    assert context.presentation_instructions == [
        "Usar lenguaje jurídico técnico y conciso.",
        "Priorizar fundamento, aplicabilidad, excepciones y riesgos.",
        "Exponer argumentos, contraargumentos y consecuencias prácticas.",
    ]


def test_mode_change_does_not_change_authorized_legal_context() -> None:
    student = LlamaRAGService._context_from_retrieval(
        retrieval_with_hit(),
        deterministic_evidence=deterministic(),
        explanation_mode=ExplanationMode.STUDENT,
    )
    professional = LlamaRAGService._context_from_retrieval(
        retrieval_with_hit(),
        deterministic_evidence=deterministic(),
        explanation_mode=ExplanationMode.PROFESSIONAL,
    )

    assert student.question == professional.question
    assert student.evidence == professional.evidence
    assert student.deterministic_evidence == professional.deterministic_evidence
    assert student.presentation_instructions != professional.presentation_instructions
