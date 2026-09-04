from __future__ import annotations

import re
import unicodedata

from app.domain.jurisprudence import NormRelationType
from app.domain.jurisprudence_decision_application import (
    JurisprudenceCaseApplicationAssessment,
    JurisprudenceCaseApplicationStatus,
    JurisprudenceDecisionApplicationRecord,
    JurisprudenceDecisionEffect,
)
from app.domain.jurisprudence_evidence import JurisprudenceEvidenceAssessment
from app.domain.jurisprudence_hybrid import SessionJurisprudenceHybridResult
from app.domain.jurisprudence_normative_relations import JurisprudenceNormativeRelationRecord
from app.domain.jurisprudence_ratio import JurisprudenceRatioRecord
from app.domain.query import QueryAnalysis, QueryDimensionName

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "articulo", "articulos", "criterio", "juridico", "juridica", "justificacion",
    "tesis", "jurisprudencia", "norma", "regla", "ley", "fiscal", "fiscales",
    "aplica", "aplicable", "aplicacion", "interpretacion", "interpretar", "debe",
    "puede", "para", "como", "conforme", "respecto", "sobre", "entre", "desde",
    "hasta", "cuando", "donde", "cual", "cuales", "este", "esta", "estos", "estas",
    "del", "las", "los", "una", "uno", "que", "por", "sin", "sus", "sea", "son",
}
_HARD_GROUPS = {
    QueryDimensionName.TAX: {"isr", "iva", "ieps", "isan"},
    QueryDimensionName.FISCAL_REGIME: {"resico", "rif"},
}


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    clean = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(clean.split())


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(_normalize(value))
        if len(token) >= 4 and token not in _STOPWORDS and not token.isdigit()
    }


def _controversy_similarity(query: str, ratio: JurisprudenceRatioRecord) -> tuple[float, list[str]]:
    query_tokens = _tokens(query)
    ratio_tokens = _tokens(
        " ".join(
            item
            for item in (ratio.legal_criterion_text, ratio.ratio_source_text)
            if item
        )
    )
    matched = sorted(query_tokens & ratio_tokens)
    denominator = max(1, min(len(query_tokens), 12))
    return min(1.0, len(matched) / denominator), matched


def _dimension_values(analysis: QueryAnalysis) -> dict[QueryDimensionName, list[str]]:
    multidimensional = analysis.multidimensional
    if multidimensional is None:
        return {}
    result: dict[QueryDimensionName, list[str]] = {}
    for item in multidimensional.dimensions:
        result.setdefault(item.dimension, []).append(_normalize(item.value))
    return result


def _material_facts(
    analysis: QueryAnalysis,
    ratio: JurisprudenceRatioRecord,
) -> tuple[float, list[str], list[str]]:
    source = _normalize(
        " ".join(item for item in (ratio.facts_text, ratio.ratio_source_text) if item)
    )
    dimensions = _dimension_values(analysis)
    anchors: list[str] = []
    conflicts: list[str] = []

    for dimension, values in dimensions.items():
        for value in values:
            if value and value in source:
                anchors.append(f"{dimension.value}:{value}")

        group = _HARD_GROUPS.get(dimension)
        if group is None or not values:
            continue
        expected = {token for value in values for token in group if token in value}
        present = {token for token in group if re.search(rf"\b{re.escape(token)}\b", source)}
        if expected and present and not (expected & present):
            conflicts.append(
                f"{dimension.value}:query={','.join(sorted(expected))};"
                f"jurisprudence={','.join(sorted(present))}"
            )

    fact_values = [_normalize(fact.value) for fact in analysis.facts]
    for value in fact_values:
        if len(value) >= 4 and value in source:
            anchors.append(f"fact:{value}")

    unique_anchors = list(dict.fromkeys(anchors))
    meaningful_count = max(1, len(dimensions) + min(len(fact_values), 4))
    score = min(1.0, len(unique_anchors) / meaningful_count)
    return score, unique_anchors, conflicts


def _material_relation_types(
    record: JurisprudenceNormativeRelationRecord,
    shared_refs: set[str],
) -> list[NormRelationType]:
    result: list[NormRelationType] = []
    for mention in record.mentions:
        if (
            mention.candidate_normative_ref in shared_refs
            and mention.material_relation_explicit
            and mention.relation_type not in result
        ):
            result.append(mention.relation_type)
    return result


def evaluate_jurisprudence_for_legal_decision(
    *,
    analysis: QueryAnalysis,
    session_result: SessionJurisprudenceHybridResult,
    ratio_records: dict[str, JurisprudenceRatioRecord],
    normative_relation_records: dict[str, JurisprudenceNormativeRelationRecord],
) -> JurisprudenceDecisionApplicationRecord:
    """E.6 determina si la ratio obligatoria gobierna la interpretación del caso."""

    integration = session_result.evidence_integration
    if integration is None:
        return JurisprudenceDecisionApplicationRecord(
            assessments=[],
            applicable_document_ids=[],
            binding_evidence_refs=[],
            requires_human_review=False,
        )

    by_document: dict[str, list[JurisprudenceEvidenceAssessment]] = {}
    for item in integration.assessments:
        if item.authorized_for_evidence:
            by_document.setdefault(item.document_id, []).append(item)

    assessments: list[JurisprudenceCaseApplicationAssessment] = []
    for document_id, evidence_items in by_document.items():
        ratio = ratio_records.get(document_id)
        relation_record = normative_relation_records.get(document_id)
        if ratio is None or relation_record is None:
            continue

        evidence_refs = [item.evidence_ref for item in evidence_items]
        shared_refs = list(
            dict.fromkeys(ref for item in evidence_items for ref in item.shared_normative_refs)
        )
        relation_types = _material_relation_types(relation_record, set(shared_refs))
        controversy_score, controversy_terms = _controversy_similarity(
            analysis.normalized_query,
            ratio,
        )
        fact_score, fact_anchors, hard_conflicts = _material_facts(analysis, ratio)

        normative_equivalence = bool(shared_refs and relation_types)
        controversy_equivalence = controversy_score >= 0.20 or len(controversy_terms) >= 2
        material_equivalence = not hard_conflicts and (
            bool(fact_anchors) or controversy_score >= 0.35
        )
        ratio_transfer = (
            normative_equivalence
            and controversy_equivalence
            and material_equivalence
            and ratio.ratio_source_established
        )

        reasons: list[str] = []
        if normative_equivalence:
            reasons.append("same_applicable_norm_and_material_jurisprudential_relation")
        else:
            reasons.append("normative_equivalence_not_established")
        if controversy_equivalence:
            reasons.append("controversy_equivalence_established")
        else:
            reasons.append("controversy_equivalence_requires_review")
        if hard_conflicts:
            reasons.append("hard_material_fact_conflict")
        elif material_equivalence:
            reasons.append("material_facts_equivalence_established")
        else:
            reasons.append("material_facts_equivalence_requires_review")

        if hard_conflicts:
            status = JurisprudenceCaseApplicationStatus.NOT_APPLICABLE
            effect = JurisprudenceDecisionEffect.NO_EFFECT
            requires_review = False
        elif ratio_transfer:
            status = JurisprudenceCaseApplicationStatus.APPLICABLE
            effect = JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
            requires_review = True
            reasons.extend(
                [
                    "binding_ratio_governs_interpretation_of_shared_norm",
                    "binding_ratio_requires_conclusion_consistency_verification",
                ]
            )
        else:
            status = JurisprudenceCaseApplicationStatus.REVIEW_REQUIRED
            effect = JurisprudenceDecisionEffect.REVIEW_REQUIRED
            requires_review = True

        assessments.append(
            JurisprudenceCaseApplicationAssessment(
                document_id=document_id,
                authorized_evidence_refs=evidence_refs,
                shared_normative_refs=shared_refs,
                relation_types=relation_types,
                controversy_similarity_score=controversy_score,
                material_fact_similarity_score=fact_score,
                matched_controversy_terms=controversy_terms,
                matched_material_fact_anchors=fact_anchors,
                hard_material_conflicts=hard_conflicts,
                normative_equivalence_established=normative_equivalence,
                controversy_equivalence_established=controversy_equivalence,
                material_facts_equivalence_established=material_equivalence,
                ratio_transfer_established=ratio_transfer,
                status=status,
                decision_effect=effect,
                binding_jurisprudence_applies=ratio_transfer,
                must_be_respected_by_legal_decision=ratio_transfer,
                requires_human_review=requires_review,
                reasons=list(dict.fromkeys(reasons)),
            )
        )

    applicable_docs = list(
        dict.fromkeys(
            item.document_id for item in assessments if item.binding_jurisprudence_applies
        )
    )
    binding_refs = list(
        dict.fromkeys(
            ref
            for item in assessments
            if item.binding_jurisprudence_applies
            for ref in item.authorized_evidence_refs
        )
    )
    return JurisprudenceDecisionApplicationRecord(
        assessments=assessments,
        applicable_document_ids=applicable_docs,
        binding_evidence_refs=binding_refs,
        requires_human_review=any(item.requires_human_review for item in assessments),
    )
