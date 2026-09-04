from __future__ import annotations

import re
import unicodedata

from app.domain.cbr import (
    CaseField,
    CaseStatus,
    CBRMatch,
    CBRRetrievalResult,
    CBRReuseAssessment,
    CBRReuseDecision,
)
from app.domain.cbr_h1_contrast import (
    CBRAnalogicalEffect,
    CBRCaseH1Contrast,
    CBRH1ContrastResult,
    CBRH1ContrastState,
)
from app.domain.hybrid_llama_hypotheses import FiscalHypothesisH1Result
from app.services.cbr_reasoning import MINIMUM_REUSE_SIMILARITY
from cbr.engine import MINIMUM_CBR_SIMILARITY

CRITICAL_FIELDS = (
    CaseField.TAXPAYER_TYPE,
    CaseField.TAX,
    CaseField.PROBLEM_TYPE,
)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    ascii_text = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return " ".join(re.findall(r"[a-z0-9]+", ascii_text))


def _tokens_without_negation(text: str) -> tuple[list[str], bool]:
    tokens = _fold(text).split()
    has_negation = "no" in tokens
    return [token for token in tokens if token != "no"], has_negation


def _explicit_negation_adversity(hypothesis: str, resolution: str) -> bool:
    h_tokens, h_negated = _tokens_without_negation(hypothesis)
    r_tokens, r_negated = _tokens_without_negation(resolution)
    return bool(h_tokens) and h_tokens == r_tokens and h_negated != r_negated


def _material_differences(match: CBRMatch) -> list[CaseField]:
    return [
        item.field
        for item in match.field_scores
        if item.weight > 0 and item.score < 1.0
    ]


def _critical_conflicts(match: CBRMatch) -> list[CaseField]:
    critical = set(CRITICAL_FIELDS)
    return [
        item.field
        for item in match.field_scores
        if item.field in critical and item.weight > 0 and item.score != 1.0
    ]


def _case_effect(
    match: CBRMatch,
    *,
    assessment: CBRReuseAssessment | None,
    proposition: str,
    h1_refs: list[str],
) -> CBRCaseH1Contrast:
    material_differences = _material_differences(match)
    critical_conflicts = _critical_conflicts(match)
    shared_h1_refs = [ref for ref in h1_refs if ref in set(match.normative_refs)]
    historical = match.status is CaseStatus.HISTORICAL
    exact_support = _fold(proposition) == _fold(match.resolution_summary)
    negation_adversity = _explicit_negation_adversity(
        proposition,
        match.resolution_summary,
    )

    if critical_conflicts:
        effect = CBRAnalogicalEffect.DISTINGUISH
        reasons = [
            "El caso presenta conflicto en un campo CBR jurídicamente crítico y no puede "
            "usarse como analogía material para H1."
        ]
        review = True
    elif historical:
        effect = CBRAnalogicalEffect.DISTINGUISH
        reasons = [
            "El caso pertenece a un contexto histórico y su diferencia temporal impide "
            "tratarlo como apoyo actual sin revisión de vigencia."
        ]
        review = True
    elif assessment is None:
        effect = CBRAnalogicalEffect.INSUFFICIENT_EVIDENCE
        reasons = [
            "El caso recuperado carece de evaluación de reutilización CBR y F.5 no presume "
            "su aptitud analógica."
        ]
        review = True
    elif assessment.decision is CBRReuseDecision.REJECTED:
        effect = CBRAnalogicalEffect.DISTINGUISH
        reasons = [
            "El control CBR rechazó la reutilización del caso; la diferencia se conserva "
            "como distinción y no como argumento contra H1."
        ]
        review = True
    elif assessment.decision is CBRReuseDecision.REVIEW_REQUIRED:
        effect = CBRAnalogicalEffect.DISTINGUISH
        reasons = [
            "El caso exige revisión antes de reutilizarse; F.5 lo distingue y no eleva una "
            "analogía incierta a apoyo de H1."
        ]
        review = True
    elif negation_adversity:
        effect = CBRAnalogicalEffect.LIMIT
        reasons = [
            "Un caso reutilizable presenta una resolución con negación léxica explícita de "
            "la misma proposición; limita H1 como experiencia adversa, sin autoridad normativa."
        ]
        review = True
    elif exact_support:
        effect = CBRAnalogicalEffect.SUPPORT
        reasons = [
            "El caso reutilizable mejor clasificado reproduce exactamente la proposición de "
            "H1; constituye apoyo experiencial y no una fuente jurídica controladora."
        ]
        review = bool(material_differences)
        if material_differences:
            reasons.append(
                "Existen diferencias no críticas que deben conservarse como límites de la "
                "analogía aun cuando la resolución coincida con H1."
            )
    elif material_differences:
        effect = CBRAnalogicalEffect.LIMIT
        reasons = [
            "El caso es reutilizable, pero presenta diferencias materiales no críticas; su "
            "valor se limita a una analogía parcial y no demuestra la corrección de H1."
        ]
        review = True
    else:
        effect = CBRAnalogicalEffect.INSUFFICIENT_EVIDENCE
        reasons = [
            "El caso es comparable, pero F.5 no infiere equivalencia semántica entre una "
            "resolución distinta y la proposición de H1."
        ]
        review = False

    return CBRCaseH1Contrast(
        case_id=match.case_id,
        rank=match.rank,
        similarity=match.similarity,
        status=match.status,
        reuse_decision=None if assessment is None else assessment.decision,
        effect=effect,
        normative_refs=_unique(match.normative_refs),
        shared_h1_normative_refs=_unique(shared_h1_refs),
        material_difference_fields=material_differences,
        critical_conflict_fields=critical_conflicts,
        historical_context=historical,
        exact_text_support=exact_support,
        explicit_negation_adversity=negation_adversity,
        requires_human_review=review,
        reasons=reasons,
    )


def contrast_h1_with_cbr(
    h1_result: FiscalHypothesisH1Result | None,
    *,
    cbr_result: CBRRetrievalResult | None,
    reuse_assessments: list[CBRReuseAssessment],
) -> CBRH1ContrastResult:
    """Contrasta H1 con experiencia CBR ya recuperada, sin reejecutar CBR ni RBS.

    F.5 selecciona el caso reutilizable mejor rankeado y evita cualquier votación
    por mayoría. Los casos CBR sólo pueden apoyar, limitar o distinguir la hipótesis
    como experiencia comparable; nunca se convierten en norma o jurisprudencia.
    """

    if (
        h1_result is None
        or not h1_result.generation_performed
        or h1_result.hypothesis is None
    ):
        return CBRH1ContrastResult(
            state=CBRH1ContrastState.NOT_APPLICABLE,
            retrieval_threshold=MINIMUM_CBR_SIMILARITY,
            reuse_threshold=MINIMUM_REUSE_SIMILARITY,
            critical_fields=list(CRITICAL_FIELDS),
            reasons=["No existe H1 controlada que deba contrastarse con CBR."],
            trace=[
                "f5:cbr_h1:state=not_applicable",
                "f5:cbr_h1:cbr_reexecuted=false",
                "f5:cbr_h1:existing_cbr_retrieval_gate_preserved=true",
                "f5:cbr_h1:family_taxonomy_similarity_recomputed=false",
                "f5:cbr_h1:cbr_votes_against_rbs=false",
                "f5:cbr_h1:can_control_legal_decision=false",
            ],
        )

    hypothesis = h1_result.hypothesis
    h1_refs = _unique(hypothesis.candidate_normative_refs)

    if cbr_result is None or not cbr_result.matches:
        return CBRH1ContrastResult(
            state=CBRH1ContrastState.INCONCLUSIVE,
            hypothesis_id=hypothesis.hypothesis_id,
            effect=CBRAnalogicalEffect.INSUFFICIENT_EVIDENCE,
            h1_proposition=hypothesis.proposition,
            h1_candidate_normative_refs=h1_refs,
            retrieval_threshold=MINIMUM_CBR_SIMILARITY,
            reuse_threshold=MINIMUM_REUSE_SIMILARITY,
            critical_fields=list(CRITICAL_FIELDS),
            reasons=[
                "CBR no aportó casos recuperados con los cuales contrastar H1."
            ],
            requires_human_review=True,
            trace=[
                "f5:cbr_h1:state=inconclusive",
                "f5:cbr_h1:effect=insufficient_evidence",
                "f5:cbr_h1:returned_cases=0",
                "f5:cbr_h1:cbr_reexecuted=false",
                "f5:cbr_h1:existing_cbr_retrieval_gate_preserved=true",
                "f5:cbr_h1:family_taxonomy_similarity_recomputed=false",
                "f5:cbr_h1:semantic_equivalence_inferred=false",
                "f5:cbr_h1:cbr_votes_against_rbs=false",
                "f5:cbr_h1:can_control_legal_decision=false",
            ],
        )

    assessment_by_case = {item.case_id: item for item in reuse_assessments}
    case_contrasts = [
        _case_effect(
            match,
            assessment=assessment_by_case.get(match.case_id),
            proposition=hypothesis.proposition,
            h1_refs=h1_refs,
        )
        for match in cbr_result.matches
    ]

    eligible_ids = [
        item.case_id
        for item in reuse_assessments
        if item.decision is CBRReuseDecision.ELIGIBLE
    ]
    review_ids = [
        item.case_id
        for item in reuse_assessments
        if item.decision is CBRReuseDecision.REVIEW_REQUIRED
    ]
    rejected_ids = [
        item.case_id
        for item in reuse_assessments
        if item.decision is CBRReuseDecision.REJECTED
    ]

    reusable_case_ids = set(eligible_ids)
    selected = next(
        (item for item in case_contrasts if item.case_id in reusable_case_ids),
        case_contrasts[0],
    )

    cbr_refs = _unique(
        [ref for item in cbr_result.matches for ref in item.normative_refs]
    )
    shared_refs = [ref for ref in h1_refs if ref in set(cbr_refs)]
    material_fields = list(dict.fromkeys(selected.material_difference_fields))
    critical_conflicts = list(dict.fromkeys(selected.critical_conflict_fields))
    temporal_distinction = selected.historical_context or any(
        field is CaseField.FISCAL_YEAR for field in material_fields
    )

    state = (
        CBRH1ContrastState.INCONCLUSIVE
        if selected.effect is CBRAnalogicalEffect.INSUFFICIENT_EVIDENCE
        else CBRH1ContrastState.CONTRASTED
    )
    review = selected.requires_human_review or any(
        item.requires_human_review for item in case_contrasts
    )

    reasons = list(selected.reasons)
    if len(case_contrasts) > 1:
        reasons.append(
            "La clasificación global usa el caso reutilizable mejor rankeado; los demás "
            "casos se conservan como contraste trazable y no se contabilizan como votos."
        )

    trace = [
        f"f5:cbr_h1:state={state.value}",
        f"f5:cbr_h1:effect={selected.effect.value}",
        f"f5:cbr_h1:considered_cases={len(case_contrasts)}",
        f"f5:cbr_h1:eligible_cases={len(eligible_ids)}",
        f"f5:cbr_h1:selected_case={selected.case_id}",
        f"f5:cbr_h1:material_difference_fields={len(material_fields)}",
        f"f5:cbr_h1:critical_conflict_fields={len(critical_conflicts)}",
        "f5:cbr_h1:aggregation=best_ranked_reusable_case_not_vote",
        "f5:cbr_h1:cbr_reexecuted=false",
        "f5:cbr_h1:existing_cbr_retrieval_gate_preserved=true",
        "f5:cbr_h1:existing_reuse_assessment_preserved=true",
        "f5:cbr_h1:primary_cbr_profiles_promoted_to_operational_cases=false",
        "f5:cbr_h1:family_taxonomy_similarity_recomputed=false",
        "f5:cbr_h1:h1_normative_refs_treated_as_candidates=true",
        "f5:cbr_h1:rbs_result_used=false",
        "f5:cbr_h1:semantic_equivalence_inferred=false",
        "f5:cbr_h1:cbr_is_normative_authority=false",
        "f5:cbr_h1:cbr_is_jurisprudence=false",
        "f5:cbr_h1:cbr_votes_against_rbs=false",
        "f5:cbr_h1:may_assist_later_h2_fact_comparison=true",
        "f5:cbr_h1:hypothesis_changes_cbr_result=false",
        "f5:cbr_h1:can_control_legal_decision=false",
    ]

    return CBRH1ContrastResult(
        state=state,
        hypothesis_id=hypothesis.hypothesis_id,
        effect=selected.effect,
        h1_proposition=hypothesis.proposition,
        h1_candidate_normative_refs=h1_refs,
        considered_case_ids=[item.case_id for item in case_contrasts],
        eligible_case_ids=eligible_ids,
        review_required_case_ids=review_ids,
        rejected_case_ids=rejected_ids,
        selected_case_id=selected.case_id,
        selected_case_similarity=selected.similarity,
        cbr_normative_refs=cbr_refs,
        shared_h1_normative_refs=_unique(shared_refs),
        material_difference_fields=material_fields,
        critical_conflict_fields=critical_conflicts,
        temporal_distinction_detected=temporal_distinction,
        exact_text_support=selected.exact_text_support,
        explicit_negation_adversity=selected.explicit_negation_adversity,
        case_contrasts=case_contrasts,
        retrieval_threshold=MINIMUM_CBR_SIMILARITY,
        reuse_threshold=MINIMUM_REUSE_SIMILARITY,
        critical_fields=list(CRITICAL_FIELDS),
        reasons=reasons,
        requires_human_review=review,
        trace=trace,
    )
