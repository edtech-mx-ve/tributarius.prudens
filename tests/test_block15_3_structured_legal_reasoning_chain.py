from __future__ import annotations

from app.domain.integral_legal_analysis import IntegralLegalAnalysis
from app.domain.legal_reasoning_chain import LegalReasoningStepKind
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.legal_decision import build_legal_decision
from app.services.legal_reasoning_chain import build_legal_reasoning_chain
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request


def _analysis() -> IntegralLegalAnalysis:
    result = _orchestrator(None).run(_request())
    return build_integral_legal_analysis(result)


def test_reasoning_chain_projects_existing_rule_conclusions_only() -> None:
    decision = build_legal_decision(_analysis())
    rule_steps = [
        step
        for step in decision.reasoning_chain.steps
        if step.kind == LegalReasoningStepKind.RULE_APPLICATION
    ]

    assert len(rule_steps) == len(decision.rule_conclusions)

    for step, conclusion in zip(rule_steps, decision.rule_conclusions, strict=True):
        assert step.rule_ref == f"{conclusion.rule_id}:{conclusion.version}"
        assert step.inference_code == conclusion.conclusion_code
        assert step.conclusion == conclusion.conclusion


def test_reasoning_chain_never_invents_normative_references() -> None:
    decision = build_legal_decision(_analysis())
    allowed = set(decision.applicable_normative_refs)

    for step in decision.reasoning_chain.steps:
        assert set(step.normative_refs).issubset(allowed)


def test_rule_source_refs_are_exposed_only_when_present_in_evidence_map() -> None:
    decision = build_legal_decision(_analysis())
    allowed = {
        ref
        for item in decision.evidence_map.items
        for ref in item.references
    }

    for step in decision.reasoning_chain.steps:
        assert set(step.evidence_refs).issubset(allowed)


def test_chain_does_not_invent_fact_to_rule_links() -> None:
    decision = build_legal_decision(_analysis())

    rule_steps = [
        step
        for step in decision.reasoning_chain.steps
        if step.kind == LegalReasoningStepKind.RULE_APPLICATION
    ]

    assert all(step.fact_refs == [] for step in rule_steps)


def test_final_determination_preserves_single_legal_decision_conclusion() -> None:
    decision = build_legal_decision(_analysis())
    final_steps = [
        step
        for step in decision.reasoning_chain.steps
        if step.kind == LegalReasoningStepKind.FINAL_DETERMINATION
    ]

    assert len(final_steps) == 1
    final = final_steps[0]
    assert final.conclusion == decision.conclusion
    assert final.controlling_source == decision.controlling_source
    assert final.requires_human_review == decision.requires_human_review


def test_chain_has_stable_monotonic_sequence() -> None:
    decision = build_legal_decision(_analysis())

    sequences = [step.sequence for step in decision.reasoning_chain.steps]

    assert sequences == list(range(1, len(sequences) + 1))


def test_reasoning_chain_cannot_promote_llama_to_controller() -> None:
    decision = build_legal_decision(_analysis())

    assert all(
        step.controlling_source != "llama"
        for step in decision.reasoning_chain.steps
    )


def test_build_legal_reasoning_chain_is_deterministic() -> None:
    decision = build_legal_decision(_analysis())

    first = build_legal_reasoning_chain(decision)
    second = build_legal_reasoning_chain(decision)

    assert first == second


def test_reasoning_chain_does_not_change_decision_conclusion() -> None:
    decision = build_legal_decision(_analysis())
    expected = decision.conclusion

    decision.reasoning_chain = build_legal_reasoning_chain(decision)

    assert decision.conclusion == expected
