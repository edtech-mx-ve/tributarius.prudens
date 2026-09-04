from __future__ import annotations

from typing import Literal

from app.domain.cbr_h1_contrast import CBRAnalogicalEffect, CBRH1ContrastResult
from app.domain.hybrid_coordination import HybridCoordinationResult, HybridReasoningRelation
from app.domain.hybrid_legal_coordination import (
    H1CoordinationDisposition,
    H2HybridCoordinationLink,
    HybridLegalCoordinationResult,
    HybridLegalCoordinationState,
)
from app.domain.hybrid_llama_hypotheses import (
    FiscalHypothesisH1Result,
    JurisprudentialRatioH2Result,
)
from app.domain.jurisprudence_decision_application import (
    JurisprudenceDecisionApplicationRecord,
    JurisprudenceDecisionEffect,
)
from app.domain.rbs_h1_contrast import RBSH1ContrastResult


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _h1_disposition(
    h1: FiscalHypothesisH1Result | None,
    rbs_contrast: RBSH1ContrastResult | None,
) -> tuple[str | None, H1CoordinationDisposition, HybridReasoningRelation | None, bool, list[str]]:
    reasons: list[str] = []
    hypothesis = h1.hypothesis if h1 is not None and h1.generation_performed else None
    if hypothesis is None:
        if rbs_contrast is not None and rbs_contrast.hypothesis_id is not None:
            reasons.append("rbs_h1_contrast_present_without_generated_h1")
            return None, H1CoordinationDisposition.NOT_PRESENT, None, True, reasons
        return None, H1CoordinationDisposition.NOT_PRESENT, None, False, reasons

    if rbs_contrast is None:
        reasons.append("generated_h1_missing_rbs_determinative_contrast")
        return (
            hypothesis.hypothesis_id,
            H1CoordinationDisposition.UNRESOLVED,
            None,
            True,
            reasons,
        )

    if rbs_contrast.hypothesis_id != hypothesis.hypothesis_id:
        reasons.append("rbs_h1_contrast_hypothesis_id_mismatch")
        return (
            hypothesis.hypothesis_id,
            H1CoordinationDisposition.UNRESOLVED,
            rbs_contrast.relation,
            True,
            reasons,
        )

    mapping = {
        HybridReasoningRelation.CONFIRMATION: H1CoordinationDisposition.CONFIRMED,
        HybridReasoningRelation.CORRECTION: H1CoordinationDisposition.CORRECTED,
        HybridReasoningRelation.CONTRADICTION: H1CoordinationDisposition.CONTRADICTED,
        HybridReasoningRelation.EXCEPTION: H1CoordinationDisposition.LIMITED_BY_EXCEPTION,
        HybridReasoningRelation.INSUFFICIENT_EVIDENCE: H1CoordinationDisposition.UNRESOLVED,
        HybridReasoningRelation.HUMAN_REVIEW: H1CoordinationDisposition.UNRESOLVED,
    }
    relation = rbs_contrast.relation
    disposition = (
        mapping[relation]
        if relation is not None
        else H1CoordinationDisposition.UNRESOLVED
    )
    if disposition is H1CoordinationDisposition.UNRESOLVED:
        reasons.append("rbs_could_not_resolve_h1_relation")
    else:
        reasons.append(f"rbs_controls_h1_disposition:{disposition.value}")
    return (
        hypothesis.hypothesis_id,
        disposition,
        relation,
        rbs_contrast.requires_human_review,
        reasons,
    )


def _cbr_effect(
    h1_id: str | None,
    cbr_contrast: CBRH1ContrastResult | None,
) -> tuple[CBRAnalogicalEffect | None, bool, list[str]]:
    reasons: list[str] = []
    if cbr_contrast is None:
        return None, False, reasons
    if h1_id is None:
        if cbr_contrast.hypothesis_id is not None:
            reasons.append("cbr_h1_contrast_present_without_generated_h1")
            return cbr_contrast.effect, True, reasons
        return cbr_contrast.effect, cbr_contrast.requires_human_review, reasons
    if cbr_contrast.hypothesis_id != h1_id:
        reasons.append("cbr_h1_contrast_hypothesis_id_mismatch")
        return cbr_contrast.effect, True, reasons
    if cbr_contrast.effect is not None:
        reasons.append(f"cbr_experiential_effect:{cbr_contrast.effect.value}")
    return cbr_contrast.effect, cbr_contrast.requires_human_review, reasons


def _jurisprudence_effect(
    application: JurisprudenceDecisionApplicationRecord | None,
) -> tuple[JurisprudenceDecisionEffect, list[str], list[str], bool, list[str]]:
    if application is None:
        return JurisprudenceDecisionEffect.NO_EFFECT, [], [], False, []

    reasons: list[str] = []
    if application.applicable_document_ids:
        reasons.append("e6_binding_jurisprudence_governs_interpretation")
        return (
            JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION,
            list(application.applicable_document_ids),
            list(application.binding_evidence_refs),
            application.requires_human_review,
            reasons,
        )

    if any(
        item.decision_effect is JurisprudenceDecisionEffect.REVIEW_REQUIRED
        for item in application.assessments
    ):
        reasons.append("e6_jurisprudence_application_requires_review")
        return (
            JurisprudenceDecisionEffect.REVIEW_REQUIRED,
            [],
            [],
            True,
            reasons,
        )

    reasons.append("e6_jurisprudence_has_no_effect_on_current_case")
    return (
        JurisprudenceDecisionEffect.NO_EFFECT,
        [],
        [],
        application.requires_human_review,
        reasons,
    )


def _h2_links(
    h2_results: list[JurisprudentialRatioH2Result],
    *,
    applicable_normative_refs: list[str],
    application: JurisprudenceDecisionApplicationRecord | None,
) -> list[H2HybridCoordinationLink]:
    assessments = {
        item.document_id: item
        for item in application.assessments
    } if application is not None else {}
    applicable_refs = set(applicable_normative_refs)
    links: list[H2HybridCoordinationLink] = []
    for result in h2_results:
        if not result.generation_performed or result.ratio is None:
            continue
        ratio = result.ratio
        assessment = assessments.get(ratio.document_id)
        shared = [
            ref for ref in ratio.interpreted_norms if ref in applicable_refs
        ]
        links.append(
            H2HybridCoordinationLink(
                ratio_id=ratio.ratio_id,
                document_id=ratio.document_id,
                interpreted_normative_refs=list(ratio.interpreted_norms),
                shared_applicable_normative_refs=_unique(shared),
                linked_to_e6_assessment=assessment is not None,
                e6_decision_effect=(
                    assessment.decision_effect
                    if assessment is not None
                    else JurisprudenceDecisionEffect.NO_EFFECT
                ),
                binding_jurisprudence_applies=(
                    assessment.binding_jurisprudence_applies
                    if assessment is not None
                    else False
                ),
            )
        )
    return links


def coordinate_hybrid_legal_argument(
    *,
    applicable_normative_refs: list[str],
    existing_coordination: HybridCoordinationResult | None,
    h1_result: FiscalHypothesisH1Result | None = None,
    rbs_h1_contrast: RBSH1ContrastResult | None = None,
    cbr_h1_contrast: CBRH1ContrastResult | None = None,
    h2_results: list[JurisprudentialRatioH2Result] | None = None,
    jurisprudence_application: JurisprudenceDecisionApplicationRecord | None = None,
) -> HybridLegalCoordinationResult:
    """Coordina resultados ya calculados sin crear una segunda conclusión.

    Jerarquía operacional F.6:
    - la conclusión del coordinador RBS-CBR existente se conserva;
    - RBS determina la disposición de H1;
    - CBR sólo añade valor analógico y nunca vota contra RBS;
    - E.6 decide si jurisprudencia obligatoria gobierna la interpretación;
    - H2 permanece como hipótesis de ratio pendiente de verificación F.7.
    """

    normative_refs = _unique(list(applicable_normative_refs))
    canonical = existing_coordination.conclusion if existing_coordination is not None else None
    reasoning_controller: Literal["rbs"] | None = (
        "rbs"
        if existing_coordination is not None
        and existing_coordination.controlling_source == "rbs"
        and canonical is not None
        else None
    )
    legal_authority_source: Literal["normative_evidence"] | None = (
        "normative_evidence" if normative_refs else None
    )

    h1_id, h1_disposition, rbs_relation, h1_review, h1_reasons = _h1_disposition(
        h1_result,
        rbs_h1_contrast,
    )
    cbr_effect, cbr_review, cbr_reasons = _cbr_effect(h1_id, cbr_h1_contrast)
    jurisprudence_effect, binding_docs, binding_refs, jurisprudence_review, juris_reasons = (
        _jurisprudence_effect(jurisprudence_application)
    )
    links = _h2_links(
        list(h2_results or []),
        applicable_normative_refs=normative_refs,
        application=jurisprudence_application,
    )

    reasons = [
        "existing_rbs_cbr_canonical_conclusion_preserved",
        "normative_evidence_remains_legal_authority",
        *h1_reasons,
        *cbr_reasons,
        *juris_reasons,
    ]
    if cbr_effect is not None:
        reasons.append("cbr_effect_does_not_change_rbs_h1_disposition")
    if links:
        reasons.append("h2_linked_for_later_verification_not_used_as_authority")

    structural_review = existing_coordination is None or canonical is None
    if h1_id is not None and rbs_h1_contrast is None:
        structural_review = True
    if rbs_h1_contrast is not None and h1_id is not None:
        structural_review = structural_review or rbs_h1_contrast.hypothesis_id != h1_id
    if cbr_h1_contrast is not None and h1_id is not None:
        structural_review = structural_review or cbr_h1_contrast.hypothesis_id != h1_id

    existing_review = (
        existing_coordination.requires_review
        if existing_coordination is not None
        else True
    )
    requires_review = bool(
        structural_review
        or existing_review
        or h1_review
        or cbr_review
        or jurisprudence_review
        or (h1_result is not None and h1_result.requires_human_review)
        or any(item.requires_human_review for item in (h2_results or []))
    )

    verification_required = bool(
        h1_id is not None
        or links
        or jurisprudence_effect is not JurisprudenceDecisionEffect.NO_EFFECT
    )

    if canonical is None:
        state = HybridLegalCoordinationState.NOT_READY
    elif requires_review:
        state = HybridLegalCoordinationState.REVIEW_REQUIRED
    else:
        state = HybridLegalCoordinationState.COORDINATED

    trace = [
        "f6:coordination=argumentative_hierarchy_not_vote",
        "f6:existing_hybrid_coordination_preserved=true",
        "f6:rbs_reexecuted=false",
        "f6:cbr_reexecuted=false",
        "f6:e6_application_recomputed=false",
        "f6:h1_used_as_legal_authority=false",
        "f6:h2_used_as_legal_authority=false",
        "f6:cbr_can_override_rbs=false",
        "f6:jurisprudence_replaces_normative_basis=false",
        "f6:single_conclusion_preserved=true",
        "f6:conclusion_consistency_evaluated=false",
    ]
    if h1_id is not None:
        trace.append(f"f6:h1_disposition={h1_disposition.value}")
    if cbr_effect is not None:
        trace.append(f"f6:cbr_effect={cbr_effect.value}")
    trace.append(f"f6:jurisprudence_effect={jurisprudence_effect.value}")
    for link in links:
        trace.append(f"f6:h2_link={link.ratio_id}:{link.document_id}")

    return HybridLegalCoordinationResult(
        state=state,
        canonical_conclusion=canonical,
        reasoning_controller=reasoning_controller,
        legal_authority_source=legal_authority_source,
        applicable_normative_refs=normative_refs,
        existing_rbs_cbr_relation=(
            existing_coordination.relation if existing_coordination is not None else None
        ),
        h1_hypothesis_id=h1_id,
        h1_disposition=h1_disposition,
        rbs_h1_relation=rbs_relation,
        cbr_h1_effect=cbr_effect,
        rbs_h1_requires_review=(
            rbs_h1_contrast.requires_human_review
            if rbs_h1_contrast is not None
            else False
        ),
        cbr_h1_requires_review=(
            cbr_h1_contrast.requires_human_review
            if cbr_h1_contrast is not None
            else False
        ),
        h2_links=links,
        jurisprudence_effect=jurisprudence_effect,
        binding_interpretation_required=(
            jurisprudence_effect is JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
        ),
        binding_jurisprudence_document_ids=binding_docs,
        binding_jurisprudence_evidence_refs=binding_refs,
        verification_required=verification_required,
        reasons=_unique(reasons),
        requires_human_review=requires_review,
        trace=trace,
    )
