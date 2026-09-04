from __future__ import annotations

from app.domain.jurisprudence_hybrid import SessionJurisprudenceHybridResult
from app.domain.jurisprudence_normative_relations import (
    JurisprudenceNormativeRelationRecord,
)
from app.domain.jurisprudence_ratio import (
    JurisprudenceRatioRecord,
    JurisprudenceRatioSourceSection,
)
from app.domain.jurisprudence_temporal import JurisprudenceTemporalRecord
from app.domain.llama_hybrid_context import (
    InitialFiscalHypothesisContext,
    JurisprudentialRatioContext,
    LlamaFactSnapshot,
    LlamaHeuristicRouteContext,
    PostDeterministicHybridReviewContext,
)
from app.domain.orchestration import HybridOrchestrationResult
from app.domain.query import QueryAnalysis


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _primary_taxonomy_label(analysis: QueryAnalysis, concept_id: str | None) -> str | None:
    if concept_id is None or analysis.multidimensional is None:
        return None
    for item in [
        *analysis.multidimensional.problem_matches,
        *analysis.multidimensional.institution_matches,
    ]:
        if item.concept_id == concept_id:
            return item.label
    return None


def build_initial_fiscal_hypothesis_context(
    analysis: QueryAnalysis,
) -> InitialFiscalHypothesisContext:
    """F.2 prepara la futura entrada H1 antes del resultado RBS/CBR determinativo."""

    multidimensional = analysis.multidimensional
    primary_activation = analysis.primary_source_activation
    rbs_orientation = analysis.rbs_orientation
    cbr_orientation = analysis.cbr_orientation
    normative_ranking = analysis.normative_ranking
    structural_navigation = analysis.structural_navigation

    primary_problem_id = (
        multidimensional.primary_problem_id if multidimensional is not None else None
    )
    primary_institution_id = (
        multidimensional.primary_institution_id if multidimensional is not None else None
    )

    exact_normative_hints: list[str] = []
    if normative_ranking is not None:
        exact_normative_hints.extend(normative_ranking.exact_normative_refs)
    if structural_navigation is not None:
        exact_normative_hints.extend(structural_navigation.exact_normative_refs)

    route = LlamaHeuristicRouteContext(
        primary_problem_id=primary_problem_id,
        primary_problem_label=_primary_taxonomy_label(analysis, primary_problem_id),
        primary_institution_id=primary_institution_id,
        primary_institution_label=_primary_taxonomy_label(
            analysis, primary_institution_id
        ),
        primary_manual_entry_ids=(
            [item.entry_id for item in primary_activation.entries]
            if primary_activation is not None
            else []
        ),
        rbs_orientation_relation_ids=(
            [item.relation_id for item in rbs_orientation.relations]
            if rbs_orientation is not None
            else []
        ),
        rbs_orientation_family_ids=(
            list(rbs_orientation.activated_rbs_family_ids)
            if rbs_orientation is not None
            else []
        ),
        cbr_orientation_situation_ids=(
            [item.situation_id for item in cbr_orientation.matches]
            if cbr_orientation is not None
            else []
        ),
        cbr_orientation_family_ids=(
            list(cbr_orientation.query_family_ids)
            if cbr_orientation is not None
            else []
        ),
        normative_focus_source_ids=(
            list(normative_ranking.focus_source_ids)
            if normative_ranking is not None
            else []
        ),
        exact_normative_hints=_unique(exact_normative_hints),
        temporal_signal_values=(
            _unique([item.value for item in multidimensional.temporal_signals])
            if multidimensional is not None
            else []
        ),
        unresolved_dimensions=(
            _unique([item.value for item in multidimensional.unresolved_dimensions])
            if multidimensional is not None
            else []
        ),
    )

    return InitialFiscalHypothesisContext(
        question=analysis.original_query,
        normalized_query=analysis.normalized_query,
        primary_intent=analysis.primary_intent,
        facts=[
            LlamaFactSnapshot(name=item.name, value=item.value, origin=item.origin)
            for item in analysis.facts
        ],
        missing_fields=_unique([item.name for item in analysis.missing_fields]),
        ambiguities=_unique(list(analysis.ambiguities)),
        heuristic_route=route,
        requires_clarification=analysis.requires_clarification,
        requires_human_review=analysis.requires_human_review,
    )


def _material_normative_refs(
    relation: JurisprudenceNormativeRelationRecord | None,
) -> tuple[list[str], list[str]]:
    if relation is None:
        return [], []
    refs: list[str] = []
    relation_types: list[str] = []
    for item in relation.mentions:
        if not item.material_relation_explicit:
            continue
        if item.candidate_normative_ref is not None:
            refs.append(item.candidate_normative_ref)
        relation_types.append(item.relation_type.value)
    return _unique(refs), _unique(relation_types)


def _e5_document_state(
    session_result: SessionJurisprudenceHybridResult,
    document_id: str,
) -> tuple[bool, bool]:
    integration = session_result.evidence_integration
    if integration is None:
        return False, session_result.requires_human_review

    assessments = [
        item
        for item in integration.assessments
        if item.document_id == document_id
    ]
    if not assessments:
        return False, session_result.requires_human_review
    return (
        any(item.authorized_for_evidence for item in assessments),
        any(item.requires_human_review for item in assessments),
    )


def build_jurisprudential_ratio_contexts(
    *,
    session_result: SessionJurisprudenceHybridResult,
    ratio_records: dict[str, JurisprudenceRatioRecord],
    normative_relation_records: dict[str, JurisprudenceNormativeRelationRecord],
    temporal_records: dict[str, JurisprudenceTemporalRecord],
) -> list[JurisprudentialRatioContext]:
    """F.2 expone sólo Justificación trazable; todavía no pide a Llama formular H2."""

    contexts: list[JurisprudentialRatioContext] = []
    for document_id in sorted(ratio_records):
        ratio = ratio_records[document_id]
        if (
            not ratio.ratio_source_established
            or ratio.ratio_source_section is not JurisprudenceRatioSourceSection.JUSTIFICATION
            or not ratio.justification_text
            or not ratio.justification_source_pages
        ):
            continue

        relation = normative_relation_records.get(document_id)
        temporal = temporal_records.get(document_id)
        normative_refs, relation_types = _material_normative_refs(relation)
        authorized, review = _e5_document_state(session_result, document_id)

        contexts.append(
            JurisprudentialRatioContext(
                document_id=document_id,
                source_sha256=ratio.source_sha256,
                criterion_type=ratio.criterion_type,
                facts_text=ratio.facts_text,
                legal_criterion_text=ratio.legal_criterion_text,
                justification_text=ratio.justification_text,
                facts_source_pages=list(ratio.facts_source_pages),
                legal_criterion_source_pages=list(
                    ratio.legal_criterion_source_pages
                ),
                justification_source_pages=list(ratio.justification_source_pages),
                candidate_normative_refs=normative_refs,
                material_relation_types=relation_types,
                binding_character_mandatory=(
                    temporal.binding_character_mandatory
                    if temporal is not None
                    else False
                ),
                binding_from=(
                    temporal.parsed_binding_start if temporal is not None else None
                ),
                e5_authorized_for_evidence=authorized,
                e5_requires_human_review=review,
            )
        )
    return contexts


def build_post_deterministic_hybrid_review_context(
    result: HybridOrchestrationResult,
) -> PostDeterministicHybridReviewContext:
    """F.2 prepara el contexto posterior que F.6/F.7 podrán contrastar con H1/H2."""

    rule_result = getattr(result, "rule_result", None)
    rbs_reasoning = getattr(result, "rbs_reasoning", None)
    rbs_conclusion = None
    rbs_requires_review = bool(
        rule_result is not None and rule_result.requires_human_review
    )
    if rbs_reasoning is not None:
        rbs_conclusion = rbs_reasoning.conclusion
        rbs_requires_review = rbs_requires_review or rbs_reasoning.requires_review

    cbr_case_refs: list[str] = []
    cbr_requires_review = False
    cbr_result = getattr(result, "cbr_result", None)
    if cbr_result is not None:
        cbr_case_refs = [item.case_id for item in cbr_result.matches]
        cbr_requires_review = any(
            item.requires_human_review for item in cbr_result.matches
        )
    cbr_assessments = getattr(result, "cbr_reuse_assessments", [])
    if cbr_assessments:
        cbr_requires_review = cbr_requires_review or any(
            item.requires_human_review for item in cbr_assessments
        )

    hybrid_relation = None
    hybrid_conclusion = None
    hybrid_controlling_source = None
    hybrid_reasons: list[str] = []
    hybrid_coordination = getattr(result, "hybrid_coordination", None)
    if hybrid_coordination is not None:
        hybrid_relation = hybrid_coordination.relation.value
        hybrid_conclusion = hybrid_coordination.conclusion
        hybrid_controlling_source = hybrid_coordination.controlling_source
        hybrid_reasons = list(hybrid_coordination.reasons)

    heuristic_signals: list[str] = []
    heuristic_priorities: list[str] = []
    heuristic_evaluation = getattr(result, "heuristic_evaluation", None)
    if heuristic_evaluation is not None:
        heuristic_signals = [item.code for item in heuristic_evaluation.signals]
        heuristic_priorities = list(heuristic_evaluation.analysis_priority)

    jurisprudence_docs: list[str] = []
    jurisprudence_refs: list[str] = []
    jurisprudence_review = False
    session_jurisprudence = getattr(result, "session_jurisprudence_result", None)
    if session_jurisprudence is not None:
        jurisprudence_review = session_jurisprudence.requires_human_review
        application = session_jurisprudence.decision_application
        if application is not None:
            jurisprudence_docs = list(application.applicable_document_ids)
            jurisprudence_refs = list(application.binding_evidence_refs)
            jurisprudence_review = (
                jurisprudence_review or application.requires_human_review
            )

    return PostDeterministicHybridReviewContext(
        question=result.analysis.original_query,
        applicable_normative_refs=_unique(
            list(getattr(result, "applicable_normative_refs", []))
        ),
        rule_conclusions=_unique(
            [item.conclusion for item in rule_result.matched_rules]
            if rule_result is not None
            else []
        ),
        rbs_conclusion=rbs_conclusion,
        rbs_requires_review=rbs_requires_review,
        cbr_case_refs=_unique(cbr_case_refs),
        cbr_requires_review=cbr_requires_review,
        hybrid_relation=hybrid_relation,
        hybrid_conclusion=hybrid_conclusion,
        hybrid_controlling_source=hybrid_controlling_source,
        hybrid_reasons=_unique(hybrid_reasons),
        heuristic_signals=_unique(heuristic_signals),
        heuristic_priorities=_unique(heuristic_priorities),
        jurisprudence_applicable_document_ids=_unique(jurisprudence_docs),
        jurisprudence_binding_evidence_refs=_unique(jurisprudence_refs),
        jurisprudence_requires_review=jurisprudence_review,
    )
