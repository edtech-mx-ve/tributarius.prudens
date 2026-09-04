from __future__ import annotations

from app.domain.cbr import CaseStatus
from app.domain.cbr_h1_contrast import CBRAnalogicalEffect
from app.domain.hybrid_coordination import HybridReasoningRelation
from app.domain.hybrid_legal_coordination import (
    H1CoordinationDisposition,
    HybridLegalCoordinationState,
)
from app.domain.hybrid_llama_hypotheses import (
    ControlledJurisprudentialRatioH2,
    JurisprudentialRatioH2Result,
    JurisprudentialSupportSpan,
)
from app.domain.hybrid_reasoning import NormalizedReasoningResult, ReasoningSource
from app.domain.jurisprudence import NormRelationType
from app.domain.jurisprudence_decision_application import (
    JurisprudenceCaseApplicationAssessment,
    JurisprudenceCaseApplicationStatus,
    JurisprudenceDecisionApplicationRecord,
    JurisprudenceDecisionEffect,
)
from app.domain.jurisprudence_ratio import JurisprudenceRatioSourceSection
from app.domain.llama_hybrid_context import LlamaHybridContextPhase
from app.domain.orchestration import HybridOrchestrationResult
from app.services.cbr_h1_contrast import contrast_h1_with_cbr
from app.services.cbr_reasoning import assess_case_reuse
from app.services.hybrid_contract_baseline import audit_current_hybrid_contracts
from app.services.hybrid_legal_coordination import coordinate_hybrid_legal_argument
from app.services.hybrid_reasoning_coordinator import coordinate_rbs_cbr
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.legal_decision import build_legal_decision
from app.services.rbs_h1_contrast import contrast_h1_with_rbs
from cbr.engine import retrieve_similar_cases
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request
from tests.test_block_f4_rbs_h1_determinative_contrast import _h1, _rules
from tests.test_block_f5_cbr_h1_analogical_contrast import _case, _query

NORM_REF = "lisr:articulo_113_e"
DOC_ID = "jurisprudencia-2032043"
EVIDENCE_REF = "JURIS-E5-2032043"


def _existing_coordination(
    conclusion: str | None = "Debe abandonar el régimen.",
    *,
    review: bool = False,
):
    rbs = NormalizedReasoningResult(
        reasoning_source=ReasoningSource.RBS,
        conclusion=conclusion,
        legal_basis=[NORM_REF] if conclusion else [],
        applicability=True if conclusion else False,
        requires_review=review,
        trace=["rbs:f6"],
    )
    cbr = NormalizedReasoningResult(
        reasoning_source=ReasoningSource.CBR,
        conclusion=conclusion,
        legal_basis=[NORM_REF] if conclusion else [],
        confidence=0.90 if conclusion else None,
        applicability=True if conclusion else False,
        requires_review=False,
        trace=["cbr:f6"],
    )
    return coordinate_rbs_cbr(rbs, cbr)


def _cbr_contrast(
    h1,
    resolution: str,
    *,
    status: CaseStatus = CaseStatus.ACTIVE,
    activity: str = "servicios profesionales",
):
    cases = [
        _case(
            "CASE-F6-001",
            resolution,
            status=status,
            activity=activity,
        )
    ]
    retrieval = retrieve_similar_cases(_query(), cases)
    assessments = [
        assess_case_reuse(match, current_normative_refs={NORM_REF})
        for match in retrieval.matches
    ]
    return contrast_h1_with_cbr(
        h1,
        cbr_result=retrieval,
        reuse_assessments=assessments,
    )


def _application(
    effect: JurisprudenceDecisionEffect,
) -> JurisprudenceDecisionApplicationRecord:
    if effect is JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION:
        assessment = JurisprudenceCaseApplicationAssessment(
            document_id=DOC_ID,
            authorized_evidence_refs=[EVIDENCE_REF],
            shared_normative_refs=[NORM_REF],
            relation_types=[NormRelationType.INTERPRETS],
            controversy_similarity_score=0.70,
            material_fact_similarity_score=0.80,
            matched_controversy_terms=["resico", "ingresos"],
            matched_material_fact_anchors=["fiscal_regime:resico"],
            hard_material_conflicts=[],
            normative_equivalence_established=True,
            controversy_equivalence_established=True,
            material_facts_equivalence_established=True,
            ratio_transfer_established=True,
            status=JurisprudenceCaseApplicationStatus.APPLICABLE,
            decision_effect=effect,
            binding_jurisprudence_applies=True,
            must_be_respected_by_legal_decision=True,
            requires_human_review=True,
            reasons=["binding_ratio_requires_conclusion_consistency_verification"],
        )
    elif effect is JurisprudenceDecisionEffect.REVIEW_REQUIRED:
        assessment = JurisprudenceCaseApplicationAssessment(
            document_id=DOC_ID,
            authorized_evidence_refs=[EVIDENCE_REF],
            shared_normative_refs=[NORM_REF],
            relation_types=[NormRelationType.INTERPRETS],
            controversy_similarity_score=0.10,
            material_fact_similarity_score=0.20,
            matched_controversy_terms=[],
            matched_material_fact_anchors=[],
            hard_material_conflicts=[],
            normative_equivalence_established=True,
            controversy_equivalence_established=False,
            material_facts_equivalence_established=False,
            ratio_transfer_established=False,
            status=JurisprudenceCaseApplicationStatus.REVIEW_REQUIRED,
            decision_effect=effect,
            binding_jurisprudence_applies=False,
            must_be_respected_by_legal_decision=False,
            requires_human_review=True,
            reasons=["controversy_equivalence_requires_review"],
        )
    else:
        assessment = JurisprudenceCaseApplicationAssessment(
            document_id=DOC_ID,
            authorized_evidence_refs=[EVIDENCE_REF],
            shared_normative_refs=[NORM_REF],
            relation_types=[NormRelationType.INTERPRETS],
            controversy_similarity_score=0.40,
            material_fact_similarity_score=0.0,
            matched_controversy_terms=["resico"],
            matched_material_fact_anchors=[],
            hard_material_conflicts=["tax:query=isr;jurisprudence=iva"],
            normative_equivalence_established=True,
            controversy_equivalence_established=True,
            material_facts_equivalence_established=False,
            ratio_transfer_established=False,
            status=JurisprudenceCaseApplicationStatus.NOT_APPLICABLE,
            decision_effect=effect,
            binding_jurisprudence_applies=False,
            must_be_respected_by_legal_decision=False,
            requires_human_review=False,
            reasons=["hard_material_fact_conflict"],
        )
    return JurisprudenceDecisionApplicationRecord(
        assessments=[assessment],
        applicable_document_ids=(
            [DOC_ID]
            if effect is JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
            else []
        ),
        binding_evidence_refs=(
            [EVIDENCE_REF]
            if effect is JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
            else []
        ),
        requires_human_review=assessment.requires_human_review,
    )


def _h2() -> JurisprudentialRatioH2Result:
    ratio = ControlledJurisprudentialRatioH2(
        ratio_id="H2-fedcba9876543210",
        document_id=DOC_ID,
        source_sha256="b" * 64,
        source_context_sha256="c" * 64,
        source_phase=LlamaHybridContextPhase.JURISPRUDENTIAL_RATIO,
        ratio_source_section=JurisprudenceRatioSourceSection.JUSTIFICATION,
        justification_source_pages=[1],
        legal_question="¿Qué ocurre al exceder el límite de ingresos?",
        material_facts=["Se excedió el límite de ingresos."],
        interpreted_norms=[NORM_REF],
        essential_premises=["El límite es una condición sustantiva del régimen."],
        proposed_ratio=(
            "Exceder el límite elimina la condición económica necesaria para "
            "permanecer en el régimen."
        ),
        possible_obiter=[],
        supporting_spans=[
            JurisprudentialSupportSpan(
                text="El límite es una condición sustantiva del régimen.",
                page=1,
                source_section=JurisprudenceRatioSourceSection.JUSTIFICATION,
            )
        ],
        uncertainties=[],
        confidence=0.82,
        provider_name="f6-static",
        model_name="llama-f6-test",
    )
    return JurisprudentialRatioH2Result(
        generation_performed=True,
        ratio=ratio,
        requires_human_review=False,
        trace=["f3:h2=controlled"],
    )


def test_f6_without_deterministic_coordination_fails_closed_not_ready() -> None:
    result = coordinate_hybrid_legal_argument(
        applicable_normative_refs=[NORM_REF],
        existing_coordination=None,
    )

    assert result.state is HybridLegalCoordinationState.NOT_READY
    assert result.canonical_conclusion is None
    assert result.requires_human_review is True
    assert result.single_conclusion_preserved is True
    assert result.can_control_legal_decision is False


def test_f6_rbs_confirmed_h1_and_cbr_support_preserve_one_canonical_conclusion() -> None:
    proposition = "Debe abandonar el régimen."
    h1 = _h1(proposition, refs=[NORM_REF])
    rbs = contrast_h1_with_rbs(
        h1,
        rule_result=_rules(proposition, normative_refs=[NORM_REF]),
    )
    cbr = _cbr_contrast(h1, proposition)

    result = coordinate_hybrid_legal_argument(
        applicable_normative_refs=[NORM_REF],
        existing_coordination=_existing_coordination(proposition),
        h1_result=h1,
        rbs_h1_contrast=rbs,
        cbr_h1_contrast=cbr,
    )

    assert result.state is HybridLegalCoordinationState.COORDINATED
    assert result.canonical_conclusion == proposition
    assert result.reasoning_controller == "rbs"
    assert result.legal_authority_source == "normative_evidence"
    assert result.h1_disposition is H1CoordinationDisposition.CONFIRMED
    assert result.rbs_h1_relation is HybridReasoningRelation.CONFIRMATION
    assert result.cbr_h1_effect is CBRAnalogicalEffect.SUPPORT
    assert result.majority_vote_used is False
    assert result.weighted_score_aggregation_used is False


def test_f6_cbr_support_cannot_vote_away_rbs_contradiction_of_h1() -> None:
    h1 = _h1("El contribuyente puede permanecer en el régimen.", refs=[NORM_REF])
    rbs_conclusion = "El contribuyente no puede permanecer en el régimen."
    rbs = contrast_h1_with_rbs(
        h1,
        rule_result=_rules(rbs_conclusion, normative_refs=[NORM_REF]),
    )
    cbr = _cbr_contrast(h1, h1.hypothesis.proposition)

    result = coordinate_hybrid_legal_argument(
        applicable_normative_refs=[NORM_REF],
        existing_coordination=_existing_coordination(rbs_conclusion),
        h1_result=h1,
        rbs_h1_contrast=rbs,
        cbr_h1_contrast=cbr,
    )

    assert result.h1_disposition is H1CoordinationDisposition.CONTRADICTED
    assert result.cbr_h1_effect is CBRAnalogicalEffect.SUPPORT
    assert result.canonical_conclusion == rbs_conclusion
    assert result.cbr_can_override_rbs is False
    assert result.requires_human_review is True


def test_f6_cbr_limit_does_not_reverse_rbs_confirmation() -> None:
    proposition = "Debe abandonar el régimen."
    h1 = _h1(proposition, refs=[NORM_REF])
    rbs = contrast_h1_with_rbs(
        h1,
        rule_result=_rules(proposition, normative_refs=[NORM_REF]),
    )
    cbr = _cbr_contrast(
        h1,
        "La situación requiere revisar la permanencia.",
        activity="actividad comercial distinta",
    )

    result = coordinate_hybrid_legal_argument(
        applicable_normative_refs=[NORM_REF],
        existing_coordination=_existing_coordination(proposition),
        h1_result=h1,
        rbs_h1_contrast=rbs,
        cbr_h1_contrast=cbr,
    )

    assert result.h1_disposition is H1CoordinationDisposition.CONFIRMED
    assert result.cbr_h1_effect is CBRAnalogicalEffect.LIMIT
    assert result.cbr_h1_requires_review is True
    assert result.canonical_conclusion == proposition
    assert result.majority_vote_used is False


def test_f6_binding_jurisprudence_governs_interpretation_without_second_conclusion() -> None:
    conclusion = "Debe abandonar el régimen."
    result = coordinate_hybrid_legal_argument(
        applicable_normative_refs=[NORM_REF],
        existing_coordination=_existing_coordination(conclusion),
        jurisprudence_application=_application(
            JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
        ),
    )

    assert result.canonical_conclusion == conclusion
    assert result.jurisprudence_effect is JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
    assert result.binding_interpretation_required is True
    assert result.binding_jurisprudence_document_ids == [DOC_ID]
    assert result.binding_jurisprudence_evidence_refs == [EVIDENCE_REF]
    assert result.normative_basis_preserved is True
    assert result.jurisprudence_replaces_normative_basis is False
    assert result.jurisprudence_creates_second_conclusion is False
    assert result.conclusion_consistency_evaluated is False
    assert result.verification_required is True


def test_f6_h2_is_linked_to_e6_but_never_becomes_authority() -> None:
    result = coordinate_hybrid_legal_argument(
        applicable_normative_refs=[NORM_REF],
        existing_coordination=_existing_coordination(),
        h2_results=[_h2()],
        jurisprudence_application=_application(
            JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
        ),
    )

    assert len(result.h2_links) == 1
    link = result.h2_links[0]
    assert link.ratio_id == "H2-fedcba9876543210"
    assert link.document_id == DOC_ID
    assert link.shared_applicable_normative_refs == [NORM_REF]
    assert link.linked_to_e6_assessment is True
    assert link.binding_jurisprudence_applies is True
    assert link.e6_decision_effect is JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
    assert link.ratio_source_is_justification is True
    assert link.ratio_fidelity_reverified is False
    assert link.consistency_with_h1_rbs_cbr_evaluated is False
    assert link.h2_used_as_legal_authority is False
    assert result.h2_used_as_legal_authority is False


def test_f6_binding_effect_does_not_depend_on_h2_generation() -> None:
    result = coordinate_hybrid_legal_argument(
        applicable_normative_refs=[NORM_REF],
        existing_coordination=_existing_coordination(),
        h2_results=[],
        jurisprudence_application=_application(
            JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
        ),
    )

    assert result.h2_links == []
    assert result.binding_interpretation_required is True
    assert result.binding_jurisprudence_document_ids == [DOC_ID]
    assert result.e6_application_recomputed is False


def test_f6_e6_review_required_is_not_promoted_to_binding_interpretation() -> None:
    result = coordinate_hybrid_legal_argument(
        applicable_normative_refs=[NORM_REF],
        existing_coordination=_existing_coordination(),
        jurisprudence_application=_application(
            JurisprudenceDecisionEffect.REVIEW_REQUIRED
        ),
    )

    assert result.jurisprudence_effect is JurisprudenceDecisionEffect.REVIEW_REQUIRED
    assert result.binding_interpretation_required is False
    assert result.binding_jurisprudence_document_ids == []
    assert result.requires_human_review is True


def test_f6_non_applicable_jurisprudence_has_no_effect_on_canonical_conclusion() -> None:
    conclusion = "Debe abandonar el régimen."
    result = coordinate_hybrid_legal_argument(
        applicable_normative_refs=[NORM_REF],
        existing_coordination=_existing_coordination(conclusion),
        jurisprudence_application=_application(JurisprudenceDecisionEffect.NO_EFFECT),
    )

    assert result.jurisprudence_effect is JurisprudenceDecisionEffect.NO_EFFECT
    assert result.binding_interpretation_required is False
    assert result.canonical_conclusion == conclusion


def test_f6_preserves_existing_rbs_cbr_relation_instead_of_recomputing_it() -> None:
    existing = _existing_coordination("Debe abandonar el régimen.")
    result = coordinate_hybrid_legal_argument(
        applicable_normative_refs=[NORM_REF],
        existing_coordination=existing,
    )

    assert result.existing_rbs_cbr_relation is existing.relation
    assert result.existing_hybrid_coordination_preserved is True
    assert result.rbs_reexecuted is False
    assert result.cbr_reexecuted is False
    assert "f6:existing_hybrid_coordination_preserved=true" in result.trace


def test_f6_result_channel_is_additive_and_not_runtime_activated() -> None:
    baseline = _orchestrator(None).run(_request())

    assert "hybrid_legal_coordination" in HybridOrchestrationResult.model_fields
    assert baseline.hybrid_legal_coordination is None
    assert baseline.llama_fiscal_hypothesis_h1 is None
    assert baseline.rbs_h1_contrast is None
    assert baseline.cbr_h1_contrast is None


def test_f6_coordination_object_does_not_change_analyzer_or_legal_decision() -> None:
    baseline = _orchestrator(None).run(_request())
    coordination = coordinate_hybrid_legal_argument(
        applicable_normative_refs=list(baseline.applicable_normative_refs),
        existing_coordination=baseline.hybrid_coordination,
    )
    enriched = baseline.model_copy(update={"hybrid_legal_coordination": coordination})

    baseline_analysis = build_integral_legal_analysis(baseline)
    enriched_analysis = build_integral_legal_analysis(enriched)
    baseline_decision = build_legal_decision(baseline_analysis)
    enriched_decision = build_legal_decision(enriched_analysis)

    assert enriched_analysis == baseline_analysis
    assert enriched_decision == baseline_decision


def test_f6_preserves_f1_contracts_and_real_llm_remains_inactive() -> None:
    audit = audit_current_hybrid_contracts()

    assert audit.all_contracts_preserved is True
    assert audit.real_llm_activation_performed is False
    assert audit.h1_h2_runtime_activation_performed is False
    assert audit.runtime_order_changed is False
    assert audit.legal_decision_changed is False
