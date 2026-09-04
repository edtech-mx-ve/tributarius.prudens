from __future__ import annotations

from app.domain.cbr import CaseField, CaseStatus, CBRCase, CBRQuery, CBRReuseDecision
from app.domain.cbr_h1_contrast import CBRAnalogicalEffect, CBRH1ContrastState
from app.domain.hybrid_llama_hypotheses import (
    ControlledFiscalHypothesisH1,
    FiscalHypothesisH1Result,
    H1FactReference,
)
from app.domain.llama_hybrid_context import LlamaHybridContextPhase
from app.domain.orchestration import HybridOrchestrationResult
from app.domain.query import FactOrigin
from app.services.cbr_h1_contrast import contrast_h1_with_cbr
from app.services.cbr_reasoning import assess_case_reuse
from app.services.hybrid_contract_baseline import audit_current_hybrid_contracts
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.legal_decision import build_legal_decision
from cbr.engine import retrieve_similar_cases
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request

NORM_REF = "lisr:articulo_113_e"


def _h1(proposition: str, *, refs: list[str] | None = None) -> FiscalHypothesisH1Result:
    hypothesis = ControlledFiscalHypothesisH1(
        hypothesis_id="H1-0123456789abcdef",
        source_context_sha256="a" * 64,
        source_phase=LlamaHybridContextPhase.INITIAL_FISCAL_HYPOTHESIS,
        legal_problem="Determinar el efecto fiscal aplicable.",
        proposition=proposition,
        facts_used=[
            H1FactReference(
                name="fiscal_regime",
                value="RESICO",
                origin=FactOrigin.EXPLICIT,
            )
        ],
        institutions=["resico_personas_fisicas"],
        candidate_normative_refs=refs or [],
        candidate_normative_questions=[],
        assumptions=[],
        uncertainties=[],
        confidence=0.70,
        provider_name="f5-static",
        model_name="llama-f5-test",
    )
    return FiscalHypothesisH1Result(
        generation_performed=True,
        hypothesis=hypothesis,
        requires_human_review=False,
        trace=["f3:h1=controlled"],
    )


def _query() -> CBRQuery:
    return CBRQuery(
        taxpayer_type="individual",
        activity="servicios profesionales",
        tax="ISR",
        problem_type="permanencia en regimen",
        procedural_stage="orientacion",
        fiscal_year=2026,
        top_k=5,
    )


def _case(
    case_id: str,
    resolution: str,
    *,
    status: CaseStatus = CaseStatus.ACTIVE,
    taxpayer_type: str = "individual",
    activity: str = "servicios profesionales",
    tax: str = "ISR",
    problem_type: str = "permanencia en regimen",
    procedural_stage: str = "orientacion",
    fiscal_year: int = 2026,
    refs: list[str] | None = None,
) -> CBRCase:
    return CBRCase(
        case_id=case_id,
        status=status,
        taxpayer_type=taxpayer_type,
        activity=activity,
        tax=tax,
        problem_type=problem_type,
        authority_act=None,
        procedural_stage=procedural_stage,
        fiscal_year=fiscal_year,
        resolution_summary=resolution,
        normative_refs=[NORM_REF] if refs is None else refs,
        source_refs=[f"SRC-{case_id}"],
    )


def _retrieval_and_assessments(cases: list[CBRCase]):
    retrieval = retrieve_similar_cases(_query(), cases)
    assessments = [
        assess_case_reuse(match, current_normative_refs={NORM_REF})
        for match in retrieval.matches
    ]
    return retrieval, assessments


def test_f5_without_h1_is_not_applicable_and_does_not_reexecute_cbr() -> None:
    retrieval, assessments = _retrieval_and_assessments(
        [_case("CASE-F5-001", "Puede permanecer en el régimen.")]
    )

    result = contrast_h1_with_cbr(
        None,
        cbr_result=retrieval,
        reuse_assessments=assessments,
    )

    assert result.state is CBRH1ContrastState.NOT_APPLICABLE
    assert result.effect is None
    assert result.cbr_reexecuted is False
    assert result.cbr_votes_against_rbs is False


def test_f5_without_retrieved_cases_fails_closed_to_insufficient_evidence() -> None:
    result = contrast_h1_with_cbr(
        _h1("Puede permanecer en el régimen."),
        cbr_result=None,
        reuse_assessments=[],
    )

    assert result.state is CBRH1ContrastState.INCONCLUSIVE
    assert result.effect is CBRAnalogicalEffect.INSUFFICIENT_EVIDENCE
    assert result.requires_human_review is True
    assert result.can_control_legal_decision is False


def test_f5_exact_reusable_analogy_supports_h1_without_becoming_authority() -> None:
    proposition = "Puede permanecer en el régimen."
    retrieval, assessments = _retrieval_and_assessments(
        [_case("CASE-F5-010", proposition)]
    )

    result = contrast_h1_with_cbr(
        _h1(proposition, refs=[NORM_REF]),
        cbr_result=retrieval,
        reuse_assessments=assessments,
    )

    assert result.state is CBRH1ContrastState.CONTRASTED
    assert result.effect is CBRAnalogicalEffect.SUPPORT
    assert result.selected_case_id == "CASE-F5-010"
    assert result.shared_h1_normative_refs == [NORM_REF]
    assert result.exact_text_support is True
    assert result.cbr_is_normative_authority is False
    assert result.cbr_is_jurisprudence is False


def test_f5_reusable_case_with_noncritical_differences_limits_analogy() -> None:
    retrieval, assessments = _retrieval_and_assessments(
        [
            _case(
                "CASE-F5-020",
                "La situación requiere revisar la permanencia.",
                activity="actividad comercial distinta",
            )
        ]
    )
    assert assessments[0].decision is CBRReuseDecision.ELIGIBLE

    result = contrast_h1_with_cbr(
        _h1("Puede permanecer en el régimen.", refs=[NORM_REF]),
        cbr_result=retrieval,
        reuse_assessments=assessments,
    )

    assert result.effect is CBRAnalogicalEffect.LIMIT
    assert CaseField.ACTIVITY in result.material_difference_fields
    assert result.critical_conflict_fields == []
    assert result.requires_human_review is True


def test_f5_historical_case_is_distinguished_not_promoted_to_current_support() -> None:
    retrieval, assessments = _retrieval_and_assessments(
        [
            _case(
                "CASE-F5-030",
                "Puede permanecer en el régimen.",
                status=CaseStatus.HISTORICAL,
                fiscal_year=2025,
            )
        ]
    )

    result = contrast_h1_with_cbr(
        _h1("Puede permanecer en el régimen.", refs=[NORM_REF]),
        cbr_result=retrieval,
        reuse_assessments=assessments,
    )

    assert result.effect is CBRAnalogicalEffect.DISTINGUISH
    assert result.temporal_distinction_detected is True
    assert result.requires_human_review is True


def test_f5_explicit_adverse_negation_limits_h1_without_overriding_it() -> None:
    retrieval, assessments = _retrieval_and_assessments(
        [_case("CASE-F5-040", "El contribuyente no puede permanecer en el régimen.")]
    )

    result = contrast_h1_with_cbr(
        _h1("El contribuyente puede permanecer en el régimen.", refs=[NORM_REF]),
        cbr_result=retrieval,
        reuse_assessments=assessments,
    )

    assert result.effect is CBRAnalogicalEffect.LIMIT
    assert result.explicit_negation_adversity is True
    assert result.hypothesis_changes_cbr_result is False
    assert result.can_control_legal_decision is False


def test_f5_does_not_infer_semantic_support_from_different_resolution_text() -> None:
    retrieval, assessments = _retrieval_and_assessments(
        [_case("CASE-F5-050", "Debe analizarse la situación fiscal concreta.")]
    )

    result = contrast_h1_with_cbr(
        _h1("Puede permanecer en el régimen.", refs=[NORM_REF]),
        cbr_result=retrieval,
        reuse_assessments=assessments,
    )

    assert result.state is CBRH1ContrastState.INCONCLUSIVE
    assert result.effect is CBRAnalogicalEffect.INSUFFICIENT_EVIDENCE
    assert result.exact_text_support is False
    assert "f5:cbr_h1:semantic_equivalence_inferred=false" in result.trace


def test_f5_rejected_weak_case_is_distinguished_not_counted_as_adverse_vote() -> None:
    retrieval, assessments = _retrieval_and_assessments(
        [
            _case(
                "CASE-F5-060",
                "El contribuyente no puede permanecer en el régimen.",
                activity="actividad comercial distinta",
                procedural_stage="fiscalizacion",
            )
        ]
    )
    assert assessments[0].decision is CBRReuseDecision.REJECTED

    result = contrast_h1_with_cbr(
        _h1("El contribuyente puede permanecer en el régimen.", refs=[NORM_REF]),
        cbr_result=retrieval,
        reuse_assessments=assessments,
    )

    assert result.effect is CBRAnalogicalEffect.DISTINGUISH
    assert result.rejected_case_ids == ["CASE-F5-060"]
    assert result.cbr_votes_against_rbs is False



def test_f5_existing_critical_mismatch_gate_blocks_nonanalogous_case() -> None:
    retrieval, assessments = _retrieval_and_assessments(
        [
            _case(
                "CASE-F5-065",
                "Puede permanecer en el régimen.",
                tax="IVA",
            )
        ]
    )
    assert retrieval.returned_count == 0
    assert assessments == []

    result = contrast_h1_with_cbr(
        _h1("Puede permanecer en el régimen.", refs=[NORM_REF]),
        cbr_result=retrieval,
        reuse_assessments=assessments,
    )

    assert result.effect is CBRAnalogicalEffect.INSUFFICIENT_EVIDENCE
    assert result.existing_cbr_retrieval_gate_preserved is True
    assert result.family_taxonomy_similarity_recomputed is False
    assert result.primary_cbr_profiles_promoted_to_operational_cases is False

def test_f5_uses_best_ranked_reusable_case_and_never_majority_vote() -> None:
    proposition = "Puede permanecer en el régimen."
    retrieval, assessments = _retrieval_and_assessments(
        [
            _case("CASE-F5-070", proposition),
            _case("CASE-F5-071", "El contribuyente no puede permanecer en el régimen."),
        ]
    )

    result = contrast_h1_with_cbr(
        _h1(proposition, refs=[NORM_REF]),
        cbr_result=retrieval,
        reuse_assessments=assessments,
    )

    assert result.selected_case_id == "CASE-F5-070"
    assert result.effect is CBRAnalogicalEffect.SUPPORT
    assert len(result.case_contrasts) == 2
    assert result.aggregation_method == "best_ranked_reusable_case_not_vote"
    assert result.cbr_votes_against_rbs is False


def test_f5_exposes_material_differences_for_later_h2_fact_comparison_only() -> None:
    retrieval, assessments = _retrieval_and_assessments(
        [
            _case(
                "CASE-F5-080",
                "La situación requiere revisar la permanencia.",
                activity="actividad comercial distinta",
            )
        ]
    )

    result = contrast_h1_with_cbr(
        _h1("Puede permanecer en el régimen.", refs=[NORM_REF]),
        cbr_result=retrieval,
        reuse_assessments=assessments,
    )

    assert result.may_assist_later_h2_fact_comparison is True
    assert result.cbr_is_jurisprudence is False
    assert result.material_difference_fields == [CaseField.ACTIVITY]


def test_f5_result_channel_is_additive_and_not_runtime_activated() -> None:
    baseline = _orchestrator(None).run(_request())

    assert "cbr_h1_contrast" in HybridOrchestrationResult.model_fields
    assert baseline.llama_fiscal_hypothesis_h1 is None
    assert baseline.rbs_h1_contrast is None
    assert baseline.cbr_h1_contrast is None


def test_f5_contrast_object_does_not_change_analyzer_or_legal_decision() -> None:
    baseline = _orchestrator(None).run(_request())
    h1 = _h1("Hipótesis experiencial no autoritativa.")
    contrast = contrast_h1_with_cbr(
        h1,
        cbr_result=baseline.cbr_result,
        reuse_assessments=baseline.cbr_reuse_assessments,
    )
    enriched = baseline.model_copy(update={"cbr_h1_contrast": contrast})

    baseline_analysis = build_integral_legal_analysis(baseline)
    enriched_analysis = build_integral_legal_analysis(enriched)
    baseline_decision = build_legal_decision(baseline_analysis)
    enriched_decision = build_legal_decision(enriched_analysis)

    assert enriched_analysis == baseline_analysis
    assert enriched_decision == baseline_decision


def test_f5_preserves_f1_contracts_and_real_llm_remains_inactive() -> None:
    audit = audit_current_hybrid_contracts()

    assert audit.all_contracts_preserved is True
    assert audit.real_llm_activation_performed is False
    assert audit.h1_h2_runtime_activation_performed is False
    assert audit.runtime_order_changed is False
    assert audit.legal_decision_changed is False
