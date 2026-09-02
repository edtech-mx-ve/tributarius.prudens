from __future__ import annotations

from app.domain.integral_legal_analysis import IntegralLegalAnalysis
from app.domain.legal_consequences import (
    LegalConsequenceKind,
    LegalConsequenceStatus,
)
from app.domain.rules import RuleConclusion
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.legal_consequences import build_legal_consequences
from app.services.legal_decision import build_legal_decision
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request


def _analysis() -> IntegralLegalAnalysis:
    result = _orchestrator(None).run(_request())
    return build_integral_legal_analysis(result)


def _rule(code: str, conclusion: str) -> RuleConclusion:
    return RuleConclusion(
        rule_id="TEST_RULE",
        version="1.0",
        conclusion_code=code,
        conclusion=conclusion,
        normative_refs=[],
        source_refs=[],
        requires_human_review=False,
    )


def test_consequences_are_created_only_from_explicit_rule_semantics() -> None:
    analysis = _analysis()
    analysis.rule_conclusions = [
        _rule("obligation_file_return", "Debe presentarse la declaración."),
        _rule("right_refund", "Puede solicitarse devolución."),
        _rule("generic_result", "Conclusión sin consecuencia tipificada."),
    ]

    decision = build_legal_decision(analysis)

    kinds = [item.kind for item in decision.consequences.items]
    assert kinds == [
        LegalConsequenceKind.OBLIGATION,
        LegalConsequenceKind.RIGHT,
    ]


def test_action_risk_and_deadline_prefixes_are_supported() -> None:
    analysis = _analysis()
    analysis.rule_conclusions = [
        _rule("action_submit_evidence", "Presentar documentación."),
        _rule("risk_penalty", "Existe riesgo de sanción."),
        _rule("deadline_30_days", "El plazo aplicable es de 30 días."),
    ]

    decision = build_legal_decision(analysis)

    assert [item.kind for item in decision.consequences.items] == [
        LegalConsequenceKind.ACTION,
        LegalConsequenceKind.RISK,
        LegalConsequenceKind.DEADLINE,
    ]


def test_unknown_rule_conclusion_does_not_create_invented_consequence() -> None:
    analysis = _analysis()
    analysis.rule_conclusions = [
        _rule("taxable_event_exists", "Se actualiza el hecho imponible."),
    ]

    decision = build_legal_decision(analysis)

    assert decision.consequences.items == []


def test_consequence_refs_are_subset_of_existing_decision_evidence() -> None:
    decision = build_legal_decision(_analysis())
    allowed_norms = set(decision.applicable_normative_refs)
    allowed_evidence = {
        ref
        for item in decision.evidence_map.items
        for ref in item.references
    }

    for item in decision.consequences.items:
        assert set(item.normative_refs).issubset(allowed_norms)
        assert set(item.evidence_refs).issubset(allowed_evidence)


def test_pending_information_makes_consequence_conditional() -> None:
    analysis = _analysis()
    analysis.rule_conclusions = [
        _rule("obligation_file_return", "Debe presentarse la declaración."),
    ]
    analysis.missing_fields = list(analysis.missing_fields)
    if not analysis.missing_fields:
        from app.domain.query import MissingField

        analysis.missing_fields = [
            MissingField(name="periodo", reason="Falta el periodo fiscal.")
        ]

    decision = build_legal_decision(analysis)

    assert decision.consequences.items[0].status == LegalConsequenceStatus.CONDITIONAL


def test_human_review_is_propagated_to_consequences() -> None:
    analysis = _analysis()
    analysis.rule_conclusions = [
        _rule("risk_penalty", "Existe riesgo de sanción."),
    ]
    analysis.requires_human_review = True

    decision = build_legal_decision(analysis)

    assert decision.consequences.items[0].requires_human_review is True
    assert decision.consequences.items[0].status == LegalConsequenceStatus.CONDITIONAL


def test_build_legal_consequences_is_deterministic() -> None:
    decision = build_legal_decision(_analysis())

    first = build_legal_consequences(decision)
    second = build_legal_consequences(decision)

    assert first == second


def test_consequences_do_not_change_canonical_conclusion() -> None:
    decision = build_legal_decision(_analysis())
    expected = decision.conclusion

    decision.consequences = build_legal_consequences(decision)

    assert decision.conclusion == expected


def test_consequence_keeps_source_rule_traceability() -> None:
    analysis = _analysis()
    analysis.rule_conclusions = [
        _rule("action_submit_evidence", "Presentar documentación."),
    ]

    decision = build_legal_decision(analysis)

    assert decision.consequences.items[0].source_rule_refs == ["TEST_RULE:1.0"]
