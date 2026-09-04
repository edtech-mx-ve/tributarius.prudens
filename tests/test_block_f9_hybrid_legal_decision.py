from __future__ import annotations

import pytest

from app.domain.hybrid_legal_decision import HybridLegalDecisionStatus
from app.domain.hybrid_legal_verification import (
    HybridLegalVerificationState,
    HybridSemanticAssessment,
)
from app.domain.integral_legal_analysis import IntegralLegalAnalysisStatus
from app.domain.jurisprudence_decision_application import JurisprudenceDecisionEffect
from app.services.hybrid_contract_baseline import audit_current_hybrid_contracts
from app.services.hybrid_integral_legal_analyzer import build_hybrid_integral_legal_analysis
from app.services.hybrid_legal_decision import (
    HybridLegalDecisionError,
    build_hybrid_legal_decision,
)
from app.services.hybrid_legal_verification import verify_hybrid_legal_argument
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.legal_decision import build_legal_decision
from tests.test_block_f6_hybrid_legal_coordination import _application
from tests.test_block_f7_hybrid_legal_verification import _binding_packet, _semantic_draft
from tests.test_block_f8_hybrid_integral_legal_analyzer import (
    _base,
    _deterministic_verified_result,
    _h1_verified_result,
)


def _verified_analysis():
    return build_hybrid_integral_legal_analysis(_deterministic_verified_result())


def _binding_analysis():
    base = _base()
    base_analysis = build_integral_legal_analysis(base)
    assert base_analysis.canonical_conclusion is not None

    source_packet = _binding_packet()
    application = _application(JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION)
    coordination = source_packet.coordination
    assert coordination is not None
    coordination = coordination.model_copy(
        update={"canonical_conclusion": base_analysis.canonical_conclusion}
    )
    packet = source_packet.model_copy(
        update={"coordination": coordination, "jurisprudence_application": application}
    )
    verification = verify_hybrid_legal_argument(
        packet,
        semantic_draft=_semantic_draft(packet),
    )
    enriched = base.model_copy(
        update={
            "hybrid_legal_coordination": coordination,
            "hybrid_legal_verification": verification,
        }
    )
    return build_hybrid_integral_legal_analysis(enriched)


def test_f9_requires_hybrid_analyzer_f8_contract() -> None:
    base_analysis = build_integral_legal_analysis(_base())

    with pytest.raises(HybridLegalDecisionError, match="sólo acepta"):
        build_hybrid_legal_decision(base_analysis)  # type: ignore[arg-type]


def test_f9_formalizes_verified_f8_as_single_normative_determination() -> None:
    analysis = _verified_analysis()
    assert analysis.readiness.can_close_automatically is True

    decision = build_hybrid_legal_decision(analysis)

    assert decision.schema_version == "1.1"
    assert decision.source_analysis_schema_version == "1.1"
    assert decision.status is HybridLegalDecisionStatus.DETERMINED
    assert decision.conclusion == analysis.canonical_conclusion
    assert decision.controlling_source == "normative_evidence"
    assert decision.hybrid_projection.reasoning_controller == "rbs"
    assert decision.hybrid_projection.legal_authority_source == "normative_evidence"
    assert decision.hybrid_projection.single_determination_preserved is True
    assert decision.hybrid_projection.second_conclusion_created is False


def test_f9_preserves_exact_normative_basis_from_f8() -> None:
    analysis = _verified_analysis()

    decision = build_hybrid_legal_decision(analysis)

    assert (
        decision.applicable_normative_refs
        == analysis.hybrid_projection.applicable_normative_refs
    )
    assert (
        decision.hybrid_projection.applicable_normative_refs
        == analysis.hybrid_projection.applicable_normative_refs
    )
    assert decision.hybrid_projection.normative_basis_preserved is True
    assert decision.controlling_source not in {"rbs", "llama", "jurisprudence"}


def test_f9_binding_jurisprudence_governs_interpretation_without_second_conclusion() -> None:
    analysis = _binding_analysis()
    assert (
        analysis.hybrid_projection.jurisprudence_effect
        is JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
    )

    decision = build_hybrid_legal_decision(analysis)
    projection = decision.hybrid_projection

    assert decision.status is HybridLegalDecisionStatus.DETERMINED
    assert decision.conclusion == analysis.canonical_conclusion
    assert decision.controlling_source == "normative_evidence"
    assert projection.binding_interpretation_required is True
    assert projection.binding_interpretation == "jurisprudence"
    assert projection.binding_jurisprudence_document_ids
    assert projection.binding_jurisprudence_evidence_refs
    assert projection.jurisprudence_replaces_normative_basis is False
    assert projection.jurisprudence_creates_second_conclusion is False
    assert projection.second_conclusion_created is False


def test_f9_correction_required_blocks_formal_determination_without_human_review() -> None:
    result = _h1_verified_result(semantic=HybridSemanticAssessment.INCONSISTENT)
    analysis = build_hybrid_integral_legal_analysis(result)
    assert analysis.hybrid_projection.verification_state is (
        HybridLegalVerificationState.CORRECTION_REQUIRED
    )

    decision = build_hybrid_legal_decision(analysis)

    assert decision.status is HybridLegalDecisionStatus.CORRECTION_REQUIRED
    assert decision.conclusion is None
    assert decision.controlling_source is None
    assert decision.requires_correction is True
    assert decision.requires_human_review is False
    assert decision.hybrid_projection.source_canonical_conclusion == analysis.canonical_conclusion
    assert decision.hybrid_projection.closes_automatically is False


def test_f9_human_review_blocks_formal_determination() -> None:
    result = _h1_verified_result(semantic=HybridSemanticAssessment.UNRESOLVED)
    analysis = build_hybrid_integral_legal_analysis(result)

    decision = build_hybrid_legal_decision(analysis)

    assert decision.status is HybridLegalDecisionStatus.HUMAN_REVIEW_REQUIRED
    assert decision.conclusion is None
    assert decision.controlling_source is None
    assert decision.requires_human_review is True
    assert decision.hybrid_projection.closes_automatically is False


def test_f9_insufficient_evidence_does_not_invent_a_conclusion() -> None:
    analysis = _verified_analysis().model_copy(deep=True)
    analysis.status = IntegralLegalAnalysisStatus.INSUFFICIENT_EVIDENCE
    analysis.canonical_conclusion = None
    analysis.hybrid_projection.canonical_conclusion = None

    decision = build_hybrid_legal_decision(analysis)

    assert decision.status is HybridLegalDecisionStatus.INSUFFICIENT_EVIDENCE
    assert decision.conclusion is None
    assert decision.controlling_source is None
    assert decision.canonical_conclusion_reconstructed is False


def test_f9_conditional_analysis_preserves_one_candidate_without_auto_closure() -> None:
    analysis = _verified_analysis().model_copy(deep=True)
    analysis.status = IntegralLegalAnalysisStatus.NEEDS_CLARIFICATION
    analysis.readiness.requires_clarification = True
    analysis.readiness.can_close_automatically = False

    decision = build_hybrid_legal_decision(analysis)

    assert decision.status is HybridLegalDecisionStatus.CONDITIONALLY_DETERMINED
    assert decision.conclusion == analysis.canonical_conclusion
    assert decision.controlling_source == "normative_evidence"
    assert decision.hybrid_projection.closes_automatically is False


def test_f9_uses_f8_hybrid_projection_as_final_normative_basis() -> None:
    analysis = _verified_analysis().model_copy(deep=True)
    analysis.applicable_normative_refs.append("REF-LEGACY-NO-HYBRID")

    decision = build_hybrid_legal_decision(analysis)

    assert (
        decision.applicable_normative_refs
        == analysis.hybrid_projection.applicable_normative_refs
    )
    assert "REF-LEGACY-NO-HYBRID" not in decision.applicable_normative_refs


def test_f9_reasoning_chain_separates_rbs_reasoning_from_normative_final_authority() -> None:
    decision = build_hybrid_legal_decision(_verified_analysis())

    rule_steps = [
        step for step in decision.reasoning_chain.steps if step.kind == "rule_application"
    ]
    final_steps = [
        step for step in decision.reasoning_chain.steps if step.kind == "final_determination"
    ]

    assert rule_steps
    assert all(step.controlling_source == "rbs" for step in rule_steps)
    assert len(final_steps) == 1
    assert final_steps[0].controlling_source == "normative_evidence"
    assert final_steps[0].conclusion == decision.conclusion


def test_f9_does_not_promote_h1_h2_cbr_or_jurisprudence_to_legal_authority() -> None:
    analysis = build_hybrid_integral_legal_analysis(_h1_verified_result())

    decision = build_hybrid_legal_decision(analysis)
    projection = decision.hybrid_projection

    assert projection.h1_hypothesis_id is not None
    assert projection.h1_h2_used_as_legal_authority is False
    assert projection.cbr_used_as_legal_authority is False
    assert projection.legal_authority_source == "normative_evidence"
    assert decision.legal_authority_reassigned_by_llm is False


def test_f9_records_no_reexecution_and_full_f7_f8_trace() -> None:
    analysis = _verified_analysis()

    decision = build_hybrid_legal_decision(analysis)
    projection = decision.hybrid_projection

    assert projection.source_verification_packet_sha256 == (
        analysis.hybrid_projection.verification_packet_sha256
    )
    assert decision.hybrid_analysis_consumed is True
    assert decision.source_results_reexecuted is False
    assert projection.h1_reexecuted is False
    assert projection.h2_reexecuted is False
    assert projection.rbs_reexecuted is False
    assert projection.cbr_reexecuted is False
    assert projection.jurisprudence_recomputed is False
    assert projection.verification_reexecuted is False
    assert projection.analyzer_reexecuted is False


def test_f9_keeps_legacy_legal_decision_1_0_unchanged() -> None:
    base = _base()
    base_analysis = build_integral_legal_analysis(base)
    legacy_before = build_legal_decision(base_analysis)

    hybrid_analysis = _verified_analysis()
    build_hybrid_legal_decision(hybrid_analysis)
    legacy_after = build_legal_decision(base_analysis)

    assert legacy_after == legacy_before
    assert legacy_after.schema_version == "1.0"


def test_f9_returns_defensive_copies() -> None:
    analysis = _verified_analysis()
    decision = build_hybrid_legal_decision(analysis)

    decision.applicable_normative_refs.append("REF-NO-PERSISTENTE")
    decision.hybrid_projection.applicable_normative_refs.append("REF-HYBRID-NO-PERSISTENTE")

    assert decision.applicable_normative_refs != analysis.applicable_normative_refs
    assert (
        decision.hybrid_projection.applicable_normative_refs
        != analysis.hybrid_projection.applicable_normative_refs
    )


def test_f9_preserves_f1_contracts_and_runtime_activation_boundaries() -> None:
    audit = audit_current_hybrid_contracts()

    assert audit.all_contracts_preserved is True
    assert audit.real_llm_activation_performed is False
    assert audit.h1_h2_runtime_activation_performed is False
    assert audit.runtime_order_changed is False
    assert audit.legal_decision_changed is False
