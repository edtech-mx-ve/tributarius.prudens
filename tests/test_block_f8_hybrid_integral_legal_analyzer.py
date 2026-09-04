from __future__ import annotations

import pytest

from app.domain.hybrid_legal_verification import (
    HybridLegalVerificationState,
    HybridSemanticAssessment,
)
from app.domain.integral_legal_analysis import IntegralLegalAnalysisStatus
from app.domain.jurisprudence_decision_application import JurisprudenceDecisionEffect
from app.services.cbr_h1_contrast import contrast_h1_with_cbr
from app.services.cbr_reasoning import assess_case_reuse
from app.services.hybrid_contract_baseline import audit_current_hybrid_contracts
from app.services.hybrid_hypothesis_generation import LlamaFiscalHypothesisH1Service
from app.services.hybrid_integral_legal_analyzer import (
    HybridIntegralLegalAnalyzerError,
    build_hybrid_integral_legal_analysis,
)
from app.services.hybrid_legal_coordination import coordinate_hybrid_legal_argument
from app.services.hybrid_legal_verification import (
    build_hybrid_legal_verification_packet,
    verify_hybrid_legal_argument,
)
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.legal_decision import build_legal_decision
from app.services.rbs_h1_contrast import contrast_h1_with_rbs
from cbr.engine import retrieve_similar_cases
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request
from tests.test_block_f3_controlled_h1_h2 import (
    StaticMessageProvider,
    _h1_context,
    _valid_h1_payload,
)
from tests.test_block_f4_rbs_h1_determinative_contrast import _rules
from tests.test_block_f5_cbr_h1_analogical_contrast import _case, _query
from tests.test_block_f6_hybrid_legal_coordination import (
    NORM_REF,
    _application,
    _existing_coordination,
)
from tests.test_block_f7_hybrid_legal_verification import (
    _binding_packet,
    _semantic_draft,
)


def _base():
    return _orchestrator(None).run(_request())


def _deterministic_verified_result():
    base = _base()
    base_analysis = build_integral_legal_analysis(base)
    assert base_analysis.canonical_conclusion is not None
    coordination = coordinate_hybrid_legal_argument(
        applicable_normative_refs=list(base.applicable_normative_refs),
        existing_coordination=_existing_coordination(base_analysis.canonical_conclusion),
    )
    packet = build_hybrid_legal_verification_packet(coordination=coordination)
    verification = verify_hybrid_legal_argument(packet)
    assert verification.state is HybridLegalVerificationState.VERIFIED
    return base.model_copy(
        update={
            "hybrid_legal_coordination": coordination,
            "hybrid_legal_verification": verification,
        }
    )


def _h1_verified_result(
    *, semantic: HybridSemanticAssessment = HybridSemanticAssessment.CONSISTENT
):
    base = _base()
    base_analysis = build_integral_legal_analysis(base)
    proposition = base_analysis.canonical_conclusion
    assert proposition is not None

    h1 = LlamaFiscalHypothesisH1Service(
        StaticMessageProvider(_valid_h1_payload(proposition=proposition))
    ).generate(_h1_context())
    rbs = contrast_h1_with_rbs(
        h1,
        rule_result=_rules(proposition, normative_refs=[NORM_REF]),
    )
    cases = [_case("CASE-F8-001", proposition)]
    retrieval = retrieve_similar_cases(_query(), cases)
    assessments = [
        assess_case_reuse(match, current_normative_refs={NORM_REF})
        for match in retrieval.matches
    ]
    cbr = contrast_h1_with_cbr(
        h1,
        cbr_result=retrieval,
        reuse_assessments=assessments,
    )
    coordination = coordinate_hybrid_legal_argument(
        applicable_normative_refs=list(base.applicable_normative_refs),
        existing_coordination=_existing_coordination(proposition),
        h1_result=h1,
        rbs_h1_contrast=rbs,
        cbr_h1_contrast=cbr,
    )
    packet = build_hybrid_legal_verification_packet(
        coordination=coordination,
        initial_context=_h1_context(),
        h1_result=h1,
        rbs_h1_contrast=rbs,
        cbr_h1_contrast=cbr,
    )
    draft = _semantic_draft(packet, h1_consistency=semantic.value)
    verification = verify_hybrid_legal_argument(packet, semantic_draft=draft)
    return base.model_copy(
        update={
            "llama_initial_context": _h1_context(),
            "llama_fiscal_hypothesis_h1": h1,
            "rbs_h1_contrast": rbs,
            "cbr_h1_contrast": cbr,
            "hybrid_legal_coordination": coordination,
            "hybrid_legal_verification": verification,
        }
    )


def test_f8_requires_f7_result_and_does_not_silently_fallback() -> None:
    with pytest.raises(HybridIntegralLegalAnalyzerError, match="exige el resultado"):
        build_hybrid_integral_legal_analysis(_base())


def test_f8_consumes_verified_chain_without_reconstructing_conclusion() -> None:
    result = _deterministic_verified_result()
    verification = result.hybrid_legal_verification
    assert verification is not None

    analysis = build_hybrid_integral_legal_analysis(result)

    assert analysis.schema_version == "1.1"
    assert analysis.source_analyzer_schema_version == "1.0"
    assert analysis.hybrid_verification_consumed is True
    assert analysis.hybrid_projection.verification_state is HybridLegalVerificationState.VERIFIED
    assert analysis.canonical_conclusion == verification.canonical_conclusion
    assert analysis.hybrid_projection.canonical_conclusion == verification.canonical_conclusion
    assert analysis.hybrid_projection.reasoning_controller == "rbs"
    assert analysis.hybrid_projection.legal_authority_source == "normative_evidence"
    assert analysis.canonical_conclusion_reconstructed is False
    assert analysis.source_results_reexecuted is False
    assert analysis.creates_second_conclusion is False
    assert analysis.legal_decision_created is False
    assert analysis.can_control_legal_decision is False


def test_f8_projects_h1_rbs_and_cbr_after_verified_f7() -> None:
    result = _h1_verified_result()
    verification = result.hybrid_legal_verification
    coordination = result.hybrid_legal_coordination
    assert verification is not None and coordination is not None
    assert verification.state is HybridLegalVerificationState.VERIFIED

    analysis = build_hybrid_integral_legal_analysis(result)
    projection = analysis.hybrid_projection

    assert projection.h1_hypothesis_id == verification.h1_hypothesis_id
    assert projection.h1_disposition == coordination.h1_disposition
    assert projection.rbs_h1_relation == coordination.rbs_h1_relation
    assert projection.cbr_h1_effect == coordination.cbr_h1_effect
    assert projection.semantic_verification_performed is True
    assert projection.requires_correction is False
    assert projection.requires_human_review is False


def test_f8_correction_required_blocks_analyzer_closure_without_silent_fix() -> None:
    result = _h1_verified_result(semantic=HybridSemanticAssessment.INCONSISTENT)
    verification = result.hybrid_legal_verification
    assert verification is not None
    assert verification.state is HybridLegalVerificationState.CORRECTION_REQUIRED

    analysis = build_hybrid_integral_legal_analysis(result)

    assert analysis.status is IntegralLegalAnalysisStatus.REVIEW_REQUIRED
    assert analysis.requires_correction is True
    assert analysis.requires_human_review is False
    assert analysis.readiness.can_close_automatically is False
    assert analysis.hybrid_projection.analyzer_may_close is False
    assert analysis.hybrid_projection.correction_codes == verification.correction_codes
    assert any(
        item.startswith("hybrid_verification_correction:")
        for item in analysis.readiness.missing_requirements
    )
    assert analysis.canonical_conclusion == verification.canonical_conclusion
    assert analysis.canonical_conclusion_reconstructed is False


def test_f8_human_review_from_f7_blocks_closure_and_is_preserved() -> None:
    result = _h1_verified_result(semantic=HybridSemanticAssessment.UNRESOLVED)
    verification = result.hybrid_legal_verification
    assert verification is not None
    assert verification.state is HybridLegalVerificationState.HUMAN_REVIEW

    analysis = build_hybrid_integral_legal_analysis(result)

    assert analysis.status is IntegralLegalAnalysisStatus.REVIEW_REQUIRED
    assert analysis.requires_correction is False
    assert analysis.requires_human_review is True
    assert analysis.readiness.requires_human_review is True
    assert analysis.readiness.can_close_automatically is False
    assert analysis.hybrid_projection.review_codes == verification.review_codes
    assert any(
        item.startswith("hybrid_verification_review:")
        for item in analysis.readiness.missing_requirements
    )


def test_f8_does_not_reconstruct_a_conclusion_when_f7_has_none() -> None:
    base = _base()
    packet = build_hybrid_legal_verification_packet(coordination=None)
    verification = verify_hybrid_legal_argument(packet)
    assert verification.state is HybridLegalVerificationState.HUMAN_REVIEW
    assert verification.canonical_conclusion is None
    enriched = base.model_copy(update={"hybrid_legal_verification": verification})

    analysis = build_hybrid_integral_legal_analysis(enriched)

    assert analysis.canonical_conclusion is None
    assert analysis.controlling_source is None
    assert analysis.status is IntegralLegalAnalysisStatus.REVIEW_REQUIRED
    assert analysis.hybrid_projection.canonical_conclusion_reconstructed is False


def test_f8_projects_binding_jurisprudence_as_interpretation_not_second_conclusion() -> None:
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
    draft = _semantic_draft(packet)
    verification = verify_hybrid_legal_argument(packet, semantic_draft=draft)
    assert verification.state is HybridLegalVerificationState.VERIFIED
    enriched = base.model_copy(
        update={
            "hybrid_legal_coordination": coordination,
            "hybrid_legal_verification": verification,
        }
    )

    analysis = build_hybrid_integral_legal_analysis(enriched)
    projection = analysis.hybrid_projection

    assert projection.jurisprudence_effect is JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
    assert projection.binding_interpretation_required is True
    assert projection.binding_jurisprudence_document_ids
    assert projection.binding_jurisprudence_evidence_refs
    assert projection.legal_authority_source == "normative_evidence"
    assert projection.creates_second_conclusion is False
    assert analysis.canonical_conclusion == base_analysis.canonical_conclusion


def test_f8_rejects_divergence_between_f6_and_f7_canonical_conclusions() -> None:
    result = _deterministic_verified_result()
    verification = result.hybrid_legal_verification
    assert verification is not None
    tampered = result.model_copy(
        update={
            "hybrid_legal_verification": verification.model_copy(
                update={"canonical_conclusion": "Conclusión ajena a F.6."}
            )
        }
    )

    with pytest.raises(HybridIntegralLegalAnalyzerError, match="divergencia"):
        build_hybrid_integral_legal_analysis(tampered)


def test_f8_keeps_analyzer_1_0_public_builder_unchanged_for_compatibility() -> None:
    result = _deterministic_verified_result()
    base = _base()

    assert build_integral_legal_analysis(result) == build_integral_legal_analysis(base)


def test_f8_does_not_activate_f9_legal_decision_path() -> None:
    result = _deterministic_verified_result()
    legacy_analysis = build_integral_legal_analysis(result)
    legacy_decision = build_legal_decision(legacy_analysis)
    hybrid_analysis = build_hybrid_integral_legal_analysis(result)

    assert legacy_decision.conclusion == legacy_analysis.canonical_conclusion
    assert hybrid_analysis.legal_decision_created is False
    assert hybrid_analysis.can_control_legal_decision is False


def test_f8_returns_defensive_hybrid_projection_copies() -> None:
    result = _deterministic_verified_result()
    coordination = result.hybrid_legal_coordination
    assert coordination is not None

    analysis = build_hybrid_integral_legal_analysis(result)
    analysis.hybrid_projection.applicable_normative_refs.append("REF-NO-PERSISTENTE")

    assert (
        analysis.hybrid_projection.applicable_normative_refs
        != coordination.applicable_normative_refs
    )


def test_f8_preserves_f1_contracts_and_runtime_activation_boundaries() -> None:
    audit = audit_current_hybrid_contracts()

    assert audit.all_contracts_preserved is True
    assert audit.real_llm_activation_performed is False
    assert audit.h1_h2_runtime_activation_performed is False
    assert audit.runtime_order_changed is False
    assert audit.legal_decision_changed is False
