from __future__ import annotations

from app.services.legal_explanation_profile import (
    assert_explanation_mode_invariance,
    build_mature_legal_explanation_context,
)
from llm.context import build_controlled_legal_context
from llm.models import DeterministicEvidence, ExplanationMode
from tests.test_llm_service import retrieval_with_hit


def _deterministic() -> DeterministicEvidence:
    return DeterministicEvidence(
        applicable_normative_refs=["CFF:ART-1"],
        rule_conclusions=["La obligación fiscal resulta aplicable."],
        calculations=["ISR@2026:v1"],
        similar_cases=["CASE-001"],
        jurisprudential_criteria=["JUR-001"],
        hybrid_relation="confirmation",
        hybrid_conclusion="La obligación fiscal resulta aplicable.",
        hybrid_controlling_source="rbs",
        hybrid_reasons=["RBS y CBR confirman la conclusión."],
        heuristic_signals=["HEUR-NORM-OK"],
        heuristic_priorities=["HEUR-NORM-OK"],
        requires_human_review=False,
    )


def test_llm_context_receives_mature_profile_for_each_mode() -> None:
    contexts = [
        build_controlled_legal_context(
            retrieval_with_hit(),
            deterministic_evidence=_deterministic(),
            explanation_mode=mode,
        )
        for mode in ExplanationMode
    ]

    assert [item.audience_label for item in contexts] == [
        "Contribuyente",
        "Estudiante",
        "Profesional",
    ]
    assert all(item.communication_goal for item in contexts)
    assert all(item.presentation_sections for item in contexts)
    assert len({tuple(item.presentation_sections) for item in contexts}) == 3


def test_modes_change_presentation_but_not_deterministic_evidence() -> None:
    contexts = [
        build_controlled_legal_context(
            retrieval_with_hit(),
            deterministic_evidence=_deterministic(),
            explanation_mode=mode,
        )
        for mode in ExplanationMode
    ]

    baseline = contexts[0]
    for context in contexts[1:]:
        assert context.question == baseline.question
        assert context.evidence == baseline.evidence
        assert context.deterministic_evidence == baseline.deterministic_evidence

    assert len({tuple(item.presentation_instructions) for item in contexts}) == 3
    assert len({tuple(item.presentation_sections) for item in contexts}) == 3


def test_llm_context_profile_matches_mature_contract_exactly() -> None:
    evidence = _deterministic()
    for mode in ExplanationMode:
        mature = build_mature_legal_explanation_context(evidence, mode)
        llm_context = build_controlled_legal_context(
            retrieval_with_hit(),
            deterministic_evidence=evidence,
            explanation_mode=mode,
        )

        assert llm_context.audience_label == mature.profile.audience_label
        assert llm_context.communication_goal == mature.profile.communication_goal
        assert llm_context.presentation_sections == mature.profile.section_order
        assert llm_context.presentation_instructions == mature.profile.style_instructions


def test_profile_invariance_guard_accepts_all_three_modes() -> None:
    evidence = _deterministic()
    mature_contexts = [
        build_mature_legal_explanation_context(evidence, mode)
        for mode in ExplanationMode
    ]

    assert_explanation_mode_invariance(mature_contexts)


def test_context_builder_does_not_mutate_caller_deterministic_evidence() -> None:
    evidence = _deterministic()
    original = evidence.model_copy(deep=True)

    build_controlled_legal_context(
        retrieval_with_hit(),
        deterministic_evidence=evidence,
        explanation_mode=ExplanationMode.TAXPAYER,
    )

    assert evidence == original


def test_legacy_taxpayer_instructions_are_preserved() -> None:
    context = build_controlled_legal_context(
        retrieval_with_hit(),
        explanation_mode=ExplanationMode.TAXPAYER,
    )

    assert context.presentation_instructions == [
        "Usar lenguaje claro, directo y accesible para el contribuyente.",
        "Explicar primero la consecuencia práctica y después su fundamento.",
        "Evitar tecnicismos innecesarios sin alterar la conclusión jurídica.",
    ]
