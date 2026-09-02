from app.domain.hybrid_coordination import (
    HybridCoordinationFactors,
    HybridCoordinationResult,
    HybridReasoningRelation,
)
from app.domain.hybrid_reasoning import NormalizedReasoningResult, ReasoningSource
from app.domain.rules import RuleEvaluationResult
from app.services.hybrid_orchestrator import _deterministic_evidence
from app.web.runtime_runner import _explanation_mode
from llm.context import build_controlled_legal_context
from llm.models import ExplanationMode
from tests.test_llm_service import retrieval_with_hit


def _reasoning(source: ReasoningSource, conclusion: str) -> NormalizedReasoningResult:
    return NormalizedReasoningResult(
        reasoning_source=source,
        conclusion=conclusion,
        legal_basis=["CFF:ART-1"],
        applicability=True,
    )


def _coordination() -> HybridCoordinationResult:
    return HybridCoordinationResult(
        relation=HybridReasoningRelation.CONFIRMATION,
        conclusion="La obligación fiscal resulta aplicable.",
        controlling_source="rbs",
        rbs_result=_reasoning(ReasoningSource.RBS, "La obligación fiscal resulta aplicable."),
        cbr_result=_reasoning(ReasoningSource.CBR, "La obligación fiscal resulta aplicable."),
        factors=HybridCoordinationFactors(
            rbs_has_conclusion=True,
            rbs_applicability=True,
            cbr_applicability=True,
            cbr_similarity=0.91,
            shared_legal_basis_count=1,
        ),
        shared_legal_basis=["CFF:ART-1"],
        reasons=["RBS y CBR confirman la misma conclusión."],
    )


def test_three_web_modes_map_to_three_explicit_explanation_modes() -> None:
    assert _explanation_mode("taxpayer") is ExplanationMode.TAXPAYER
    assert _explanation_mode("student") is ExplanationMode.STUDENT
    assert _explanation_mode("professional") is ExplanationMode.PROFESSIONAL


def test_three_modes_change_only_presentation_instructions() -> None:
    contexts = [
        build_controlled_legal_context(retrieval_with_hit(), explanation_mode=mode)
        for mode in ExplanationMode
    ]
    baseline = contexts[0]
    for context in contexts[1:]:
        assert context.question == baseline.question
        assert context.evidence == baseline.evidence
        assert context.deterministic_evidence == baseline.deterministic_evidence
    assert len({tuple(item.presentation_instructions) for item in contexts}) == 3


def test_taxpayer_mode_is_clear_and_does_not_authorize_legal_changes() -> None:
    context = build_controlled_legal_context(
        retrieval_with_hit(), explanation_mode=ExplanationMode.TAXPAYER
    )
    assert context.presentation_instructions == [
        "Usar lenguaje claro, directo y accesible para el contribuyente.",
        "Explicar primero la consecuencia práctica y después su fundamento.",
        "Evitar tecnicismos innecesarios sin alterar la conclusión jurídica.",
    ]


def test_hybrid_decision_enters_deterministic_llm_boundary() -> None:
    coordination = _coordination()
    evidence = _deterministic_evidence(
        ["NORM-001"],
        RuleEvaluationResult(matched_rules=[], traces=[], requires_human_review=False),
        None,
        None,
        None,
        coordination,
    )
    assert evidence.hybrid_relation == "confirmation"
    assert evidence.hybrid_conclusion == coordination.conclusion
    assert evidence.hybrid_controlling_source == "rbs"
    assert evidence.hybrid_reasons == coordination.reasons


def test_hybrid_review_cannot_be_removed_from_deterministic_boundary() -> None:
    coordination = _coordination().model_copy(update={"requires_review": True})
    evidence = _deterministic_evidence(
        [],
        RuleEvaluationResult(matched_rules=[], traces=[], requires_human_review=False),
        None,
        None,
        None,
        coordination,
    )
    assert evidence.requires_human_review is True
