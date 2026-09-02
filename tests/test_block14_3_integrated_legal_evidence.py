from __future__ import annotations

from app.domain.integral_legal_evidence import (
    IntegralLegalEvidenceChannel,
    IntegralLegalEvidenceItem,
)
from app.domain.orchestration import HybridOrchestrationResult
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.integral_legal_evidence import build_integral_legal_evidence_map
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request


def _result() -> HybridOrchestrationResult:
    return _orchestrator(None).run(_request())


def _item(
    result: HybridOrchestrationResult,
    channel: IntegralLegalEvidenceChannel,
) -> IntegralLegalEvidenceItem:
    evidence_map = build_integral_legal_evidence_map(result)
    return next(item for item in evidence_map.items if item.channel == channel)


def test_integral_evidence_map_contains_exact_five_legal_channels() -> None:
    evidence_map = build_integral_legal_evidence_map(_result())

    assert [item.channel for item in evidence_map.items] == [
        IntegralLegalEvidenceChannel.NORMATIVE,
        IntegralLegalEvidenceChannel.RBS,
        IntegralLegalEvidenceChannel.CBR,
        IntegralLegalEvidenceChannel.JURISPRUDENCE,
        IntegralLegalEvidenceChannel.CALCULATION,
    ]


def test_normative_channel_uses_only_applicable_normative_refs() -> None:
    result = _result()
    item = _item(result, IntegralLegalEvidenceChannel.NORMATIVE)

    assert item.present is True
    assert item.references == result.applicable_normative_refs


def test_rbs_channel_references_matched_rules_without_reinterpreting_them() -> None:
    result = _result()
    item = _item(result, IntegralLegalEvidenceChannel.RBS)

    assert item.present is True
    assert item.references == [
        f"{rule.rule_id}:{rule.version}" for rule in result.rule_result.matched_rules
    ]


def test_calculation_channel_is_traced_to_norm_tariff_and_source() -> None:
    result = _result()
    item = _item(result, IntegralLegalEvidenceChannel.CALCULATION)

    assert result.isr_result is not None
    assert item.present is True
    assert item.references == [
        result.isr_result.normative_ref,
        result.isr_result.tariff_version,
        result.isr_result.source_reference,
    ]


def test_absent_optional_cbr_and_jurisprudence_are_explicit_not_invented() -> None:
    result = _result()

    cbr = _item(result, IntegralLegalEvidenceChannel.CBR)
    jurisprudence = _item(result, IntegralLegalEvidenceChannel.JURISPRUDENCE)

    assert result.cbr_result is None
    assert result.jurisprudence_result is None
    assert cbr.present is False
    assert cbr.references == []
    assert jurisprudence.present is False
    assert jurisprudence.references == []


def test_removing_a_channel_does_not_change_existing_legal_conclusion() -> None:
    result = _result()
    before = build_integral_legal_analysis(result)

    result.isr_result = None
    after = build_integral_legal_analysis(result)

    assert before.canonical_conclusion == after.canonical_conclusion
    assert before.controlling_source == after.controlling_source
    assert (
        _item(result, IntegralLegalEvidenceChannel.CALCULATION).present
        is False
    )


def test_analyzer_1_0_exposes_integrated_evidence_map() -> None:
    result = _result()
    analysis = build_integral_legal_analysis(result)

    assert analysis.evidence_map == build_integral_legal_evidence_map(result)
    assert analysis.canonical_conclusion == result.rule_result.matched_rules[0].conclusion
    assert analysis.controlling_source == "rbs"


def test_integral_evidence_map_does_not_mutate_orchestration_result() -> None:
    result = _result()
    before = result.model_copy(deep=True)

    build_integral_legal_evidence_map(result)

    assert result == before
