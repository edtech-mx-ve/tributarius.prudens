from __future__ import annotations

from datetime import UTC, datetime

from app.domain.orchestration import (
    HybridOrchestrationResult,
    OrchestrationStage,
)
from app.domain.traceability import TraceabilityRecord
from app.services.traceability import (
    build_canonical_result,
    build_traceability_record,
    verify_canonical_integrity,
)
from tests.test_block12_4_hypothesis_verification import (
    _orchestrator,
    _request,
)

_NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def _trace(
    result: HybridOrchestrationResult,
) -> TraceabilityRecord:
    request = _request()
    return build_traceability_record(
        request,
        result,
        execution_id="TP-" + ("A" * 32),
        folio="TP-20260902-" + ("A" * 12),
        created_at_utc=_NOW,
    )


def test_hypothesis_is_traceable_without_becoming_canonical_legal_evidence() -> None:
    result = _orchestrator(
        "Podría existir una obligación fiscal que debe verificarse."
    ).run(_request())
    trace = _trace(result)

    hypothesis_event = next(
        item
        for item in trace.events
        if item.stage == OrchestrationStage.LEGAL_HYPOTHESIS.value
    )
    verification_event = next(
        item
        for item in trace.events
        if item.stage == OrchestrationStage.LEGAL_HYPOTHESIS_VERIFICATION.value
    )

    assert result.initial_legal_hypothesis is not None
    assert hypothesis_event.evidence_refs == (
        result.initial_legal_hypothesis.authorized_evidence_ids
    )
    assert verification_event.evidence_refs == (
        result.initial_legal_hypothesis.authorized_evidence_ids
    )
    assert hypothesis_event.requires_human_review is False
    assert verification_event.requires_human_review is False

    evidence_ids = {item.ref_id for item in trace.evidence}
    assert not any(ref.startswith("legal-hypothesis:") for ref in evidence_ids)


def test_different_hypotheses_do_not_change_canonical_legal_hash() -> None:
    first = _orchestrator(
        "Primera hipótesis experimental sobre la posible obligación."
    ).run(_request())
    second = _orchestrator(
        "Segunda hipótesis deliberadamente distinta sobre la consulta."
    ).run(_request())

    first_canonical = build_canonical_result(_request(), first, now=_NOW)
    second_canonical = build_canonical_result(_request(), second, now=_NOW)

    assert first.initial_legal_hypothesis != second.initial_legal_hypothesis
    assert first.rule_result == second.rule_result
    assert first.isr_result == second.isr_result
    assert (
        first_canonical.traceability.canonical_result_sha256
        == second_canonical.traceability.canonical_result_sha256
    )
    assert verify_canonical_integrity(first_canonical) is True
    assert verify_canonical_integrity(second_canonical) is True


def test_hypothesis_absence_and_presence_preserve_deterministic_decision() -> None:
    baseline = _orchestrator(None).run(_request())
    experimental = _orchestrator(
        "Hipótesis no vinculante usada solo para orientar investigación."
    ).run(_request())

    assert baseline.applicable_normative_refs == experimental.applicable_normative_refs
    assert baseline.rule_result == experimental.rule_result
    assert baseline.isr_result == experimental.isr_result
    assert baseline.hybrid_coordination == experimental.hybrid_coordination
    assert baseline.heuristic_evaluation == experimental.heuristic_evaluation
    assert baseline.requires_human_review == experimental.requires_human_review


def test_verification_never_promotes_hypothesis_to_controlling_source() -> None:
    result = _orchestrator(
        "Perfil sujeto a revisión ISR."
    ).run(_request())

    verification = result.initial_legal_hypothesis_verification
    assert verification is not None
    assert verification.exact_text_match is True
    assert verification.semantic_equivalence_asserted is False
    assert verification.controlling_source == "rbs"
    assert verification.controlling_source != "llm"
    assert verification.controlling_source != "legal_hypothesis"


def test_experimental_stages_are_ordered_and_do_not_replace_explanation() -> None:
    result = _orchestrator(
        "Posible obligación fiscal pendiente de comprobación."
    ).run(_request())

    stages = [item.stage for item in result.traces]
    assert stages.index(OrchestrationStage.RETRIEVAL) < stages.index(
        OrchestrationStage.LEGAL_HYPOTHESIS
    )
    assert stages.index(OrchestrationStage.LEGAL_HYPOTHESIS) < stages.index(
        OrchestrationStage.NORMATIVE
    )
    assert stages.index(OrchestrationStage.LEGAL_HEURISTICS) < stages.index(
        OrchestrationStage.LEGAL_HYPOTHESIS_VERIFICATION
    )
    assert stages.index(
        OrchestrationStage.LEGAL_HYPOTHESIS_VERIFICATION
    ) < stages.index(OrchestrationStage.EXPLANATION)
    assert result.explanation is not None


def test_block12_contract_remains_explicitly_non_decisional_end_to_end() -> None:
    result = _orchestrator(
        "La hipótesis propone investigar una posible obligación tributaria."
    ).run(_request())

    hypothesis_result = result.initial_legal_hypothesis
    verification = result.initial_legal_hypothesis_verification

    assert hypothesis_result is not None
    assert hypothesis_result.hypothesis is not None
    assert hypothesis_result.hypothesis.requires_validation is True
    assert hypothesis_result.hypothesis.changes_deterministic_result is False
    assert hypothesis_result.hypothesis.asserts_external_legal_authority is False

    assert verification is not None
    assert verification.deterministic_result_preserved is True
    assert verification.semantic_equivalence_asserted is False
    assert result.rule_result.matched_rules
