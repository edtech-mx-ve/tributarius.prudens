from llm.context import build_controlled_legal_context
from llm.models import DeterministicEvidence, ExplanationMode
from tests.test_llm_service import retrieval_with_hit


def test_context_defaults_to_professional_explanation() -> None:
    context = build_controlled_legal_context(retrieval_with_hit())

    assert context.explanation_mode == ExplanationMode.PROFESSIONAL


def test_context_accepts_student_explanation_without_changing_evidence() -> None:
    professional = build_controlled_legal_context(
        retrieval_with_hit(),
        explanation_mode=ExplanationMode.PROFESSIONAL,
    )
    student = build_controlled_legal_context(
        retrieval_with_hit(),
        explanation_mode=ExplanationMode.STUDENT,
    )

    assert professional.evidence == student.evidence
    assert professional.deterministic_evidence == student.deterministic_evidence
    assert professional.explanation_mode != student.explanation_mode


def test_context_preserves_all_deterministic_reasoning_channels() -> None:
    deterministic = DeterministicEvidence(
        applicable_normative_refs=["NORM-001"],
        rule_conclusions=["RULE-001"],
        calculations=["ISR=2300.00"],
        similar_cases=["CASE-001"],
        jurisprudential_criteria=["JURIS-001"],
        requires_human_review=True,
    )

    context = build_controlled_legal_context(
        retrieval_with_hit(),
        deterministic_evidence=deterministic,
    )

    assert context.deterministic_evidence is not None
    assert context.deterministic_evidence.applicable_normative_refs == ["NORM-001"]
    assert context.deterministic_evidence.rule_conclusions == ["RULE-001"]
    assert context.deterministic_evidence.calculations == ["ISR=2300.00"]
    assert context.deterministic_evidence.similar_cases == ["CASE-001"]
    assert context.deterministic_evidence.jurisprudential_criteria == ["JURIS-001"]
    assert context.deterministic_evidence.requires_human_review is True


def test_context_enriches_documentary_channels_without_mutating_input() -> None:
    deterministic = DeterministicEvidence(
        applicable_normative_refs=["NORM-001"],
    )

    context = build_controlled_legal_context(
        retrieval_with_hit(),
        deterministic_evidence=deterministic,
    )

    assert context.deterministic_evidence is not None
    assert context.deterministic_evidence.normative_evidence_refs == ["chunk-0001"]
    assert deterministic.normative_evidence_refs == []
