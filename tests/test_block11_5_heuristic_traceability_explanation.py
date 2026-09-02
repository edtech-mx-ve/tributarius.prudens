from __future__ import annotations

from app.domain.legal_heuristics import (
    LegalHeuristicEvaluation,
    LegalHeuristicKind,
    LegalHeuristicLevel,
    LegalHeuristicSignal,
)
from app.services.legal_heuristic_explanation import (
    build_heuristic_explanation_evidence,
)
from llm.models import DeterministicEvidence, ExplanationMode, LLMGenerationContext


def _evaluation() -> LegalHeuristicEvaluation:
    return LegalHeuristicEvaluation(
        canonical_conclusion="Conclusión normativa",
        controlling_source="rbs",
        signals=[
            LegalHeuristicSignal(
                code="HEUR-TEMP-002",
                kind=LegalHeuristicKind.TEMPORAL_CONFLICT,
                level=LegalHeuristicLevel.REVIEW,
                message="Verificar vigencia del precedente histórico.",
                evidence_refs=["historical"],
                requires_review=True,
            )
        ],
        analysis_priority=["Verificar vigencia normativa del precedente histórico."],
        requires_review=True,
        normative_priority_preserved=True,
        trace=["heuristics:explicit=true"],
    )


def test_projection_is_literal_and_deterministic() -> None:
    signals, priorities, review = build_heuristic_explanation_evidence(_evaluation())

    assert signals == [
        (
            "HEUR-TEMP-002|temporal_conflict|review|review=true|"
            "Verificar vigencia del precedente histórico."
        )
    ]
    assert priorities == ["Verificar vigencia normativa del precedente histórico."]
    assert review is True


def test_projection_does_not_expose_or_change_canonical_conclusion() -> None:
    evaluation = _evaluation()

    signals, priorities, _ = build_heuristic_explanation_evidence(evaluation)

    assert evaluation.canonical_conclusion == "Conclusión normativa"
    assert evaluation.controlling_source == "rbs"
    assert all("Conclusión normativa" not in item for item in signals)
    assert all("Conclusión normativa" not in item for item in priorities)


def test_none_evaluation_produces_neutral_explanation_evidence() -> None:
    assert build_heuristic_explanation_evidence(None) == ([], [], False)


def test_deterministic_evidence_accepts_heuristic_projection() -> None:
    signals, priorities, review = build_heuristic_explanation_evidence(_evaluation())

    evidence = DeterministicEvidence(
        hybrid_conclusion="Conclusión normativa",
        hybrid_controlling_source="rbs",
        heuristic_signals=signals,
        heuristic_priorities=priorities,
        heuristic_requires_review=review,
        requires_human_review=review,
    )

    assert evidence.hybrid_conclusion == "Conclusión normativa"
    assert evidence.hybrid_controlling_source == "rbs"
    assert evidence.heuristic_requires_review is True
    assert evidence.requires_human_review is True


def test_explanation_mode_cannot_change_heuristic_evidence() -> None:
    signals, priorities, review = build_heuristic_explanation_evidence(_evaluation())
    evidence = DeterministicEvidence(
        hybrid_conclusion="Conclusión normativa",
        hybrid_controlling_source="rbs",
        heuristic_signals=signals,
        heuristic_priorities=priorities,
        heuristic_requires_review=review,
    )

    contexts = [
        LLMGenerationContext.model_construct(
            question="Consulta",
            evidence=[],
            deterministic_evidence=evidence,
            explanation_mode=mode,
            presentation_instructions=[],
        )
        for mode in ExplanationMode
    ]

    dumps = [
        context.deterministic_evidence.model_dump(mode="json")
        for context in contexts
        if context.deterministic_evidence is not None
    ]
    assert len(dumps) == 3
    assert dumps[0] == dumps[1] == dumps[2]
