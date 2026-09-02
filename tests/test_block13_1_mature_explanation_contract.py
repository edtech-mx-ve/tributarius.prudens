from __future__ import annotations

import pytest

from app.domain.legal_explanation import MatureLegalExplanationContext
from app.services.legal_explanation_profile import (
    assert_explanation_mode_invariance,
    build_mature_legal_explanation_context,
)
from llm.models import DeterministicEvidence, ExplanationMode


def _evidence() -> DeterministicEvidence:
    return DeterministicEvidence(
        applicable_normative_refs=["CFF:ART-1", "LISR:ART-90"],
        rule_conclusions=["La obligación fiscal resulta aplicable."],
        calculations=["ISR@2026:v1"],
        similar_cases=["CASE-001"],
        jurisprudential_criteria=["JUR-001"],
        hybrid_relation="confirmation",
        hybrid_conclusion="La obligación fiscal resulta aplicable.",
        hybrid_controlling_source="rbs",
        hybrid_reasons=["RBS y CBR confirman la misma conclusión."],
        heuristic_signals=["HEUR-NORM-OK"],
        heuristic_priorities=["HEUR-NORM-OK"],
        heuristic_requires_review=False,
        requires_human_review=False,
    )


def test_three_modes_share_exactly_the_same_legal_invariant() -> None:
    evidence = _evidence()
    contexts = [
        build_mature_legal_explanation_context(evidence, mode)
        for mode in ExplanationMode
    ]

    assert contexts[0].invariant == contexts[1].invariant == contexts[2].invariant
    assert_explanation_mode_invariance(contexts)


def test_three_modes_have_distinct_communication_profiles() -> None:
    contexts = [
        build_mature_legal_explanation_context(_evidence(), mode)
        for mode in ExplanationMode
    ]

    assert {context.profile.mode for context in contexts} == set(ExplanationMode)
    assert len({context.profile.audience_label for context in contexts}) == 3
    assert len({tuple(context.profile.section_order) for context in contexts}) == 3
    assert len({tuple(context.profile.style_instructions) for context in contexts}) == 3


def test_taxpayer_profile_cannot_change_controlling_source_or_conclusion() -> None:
    evidence = _evidence()
    context = build_mature_legal_explanation_context(
        evidence,
        ExplanationMode.TAXPAYER,
    )

    assert context.invariant.hybrid_controlling_source == "rbs"
    assert context.invariant.hybrid_conclusion == evidence.hybrid_conclusion
    assert context.invariant.applicable_normative_refs == (
        evidence.applicable_normative_refs
    )
    assert context.profile.mode is ExplanationMode.TAXPAYER


def test_student_profile_preserves_review_and_calculation_state() -> None:
    evidence = _evidence().model_copy(
        update={
            "requires_human_review": True,
            "heuristic_requires_review": True,
        }
    )
    context = build_mature_legal_explanation_context(
        evidence,
        ExplanationMode.STUDENT,
    )

    assert context.invariant.requires_human_review is True
    assert context.invariant.heuristic_requires_review is True
    assert context.invariant.calculations == ["ISR@2026:v1"]


def test_professional_profile_preserves_cbr_and_jurisprudence() -> None:
    context = build_mature_legal_explanation_context(
        _evidence(),
        ExplanationMode.PROFESSIONAL,
    )

    assert context.invariant.similar_cases == ["CASE-001"]
    assert context.invariant.jurisprudential_criteria == ["JUR-001"]


def test_builder_deep_copies_source_evidence() -> None:
    evidence = _evidence()
    context = build_mature_legal_explanation_context(
        evidence,
        ExplanationMode.TAXPAYER,
    )

    evidence.applicable_normative_refs.append("CFF:ART-2")
    evidence.hybrid_reasons.append("Mutación posterior.")

    assert context.invariant.applicable_normative_refs == ["CFF:ART-1", "LISR:ART-90"]
    assert context.invariant.hybrid_reasons == [
        "RBS y CBR confirman la misma conclusión."
    ]


def test_invariance_guard_rejects_legal_difference_between_modes() -> None:
    baseline = build_mature_legal_explanation_context(
        _evidence(),
        ExplanationMode.TAXPAYER,
    )
    altered = MatureLegalExplanationContext(
        invariant=baseline.invariant.model_copy(
            update={"hybrid_conclusion": "Conclusión alterada por presentación."}
        ),
        profile=build_mature_legal_explanation_context(
            _evidence(),
            ExplanationMode.PROFESSIONAL,
        ).profile,
    )

    with pytest.raises(
        ValueError,
        match="contenido jurídico invariante",
    ):
        assert_explanation_mode_invariance([baseline, altered])


def test_invariance_guard_requires_at_least_one_context() -> None:
    with pytest.raises(ValueError, match="al menos un contexto"):
        assert_explanation_mode_invariance([])
