from __future__ import annotations

import re
import unicodedata
from datetime import date

from app.domain.jurisprudence import JurisprudenceStatus, NormRelationType
from app.domain.jurisprudence_applicability import (
    SessionJurisprudenceApplicabilityAssessment,
)
from app.domain.jurisprudence_evidence import (
    JurisprudenceEvidenceAssessment,
    JurisprudenceEvidenceDecision,
    JurisprudenceEvidenceIntegrationRecord,
)
from app.domain.jurisprudence_normative_relations import (
    JurisprudenceNormativeRelationRecord,
)
from app.domain.jurisprudence_ratio import JurisprudenceRatioRecord
from app.domain.jurisprudence_session_retrieval import (
    SessionJurisprudenceRetrievalResult,
)
from app.domain.jurisprudence_temporal import (
    JurisprudenceBindingTemporalState,
    JurisprudencePublicationTemporalState,
    JurisprudenceTemporalRecord,
)
from app.services.jurisprudence_temporal_control import (
    assess_jurisprudence_temporal_context,
)

_ARTICLE_HUMAN_RE = re.compile(
    r"^articulo\s+(?P<unit>[0-9a-z._-]+)\s+(?:de|del)\s+(?P<corpus>[a-z0-9_]+)$"
)
_SHORT_REF_RE = re.compile(r"^(?P<corpus>[a-z0-9_]+):(?P<unit>[0-9a-z._-]+)$")


class JurisprudenceEvidenceIntegrationError(ValueError):
    pass


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return " ".join(without_marks.split())


def _canonical_ref(value: str) -> str:
    clean = _normalize_text(value).replace(" ", "_")
    if ":articulo_" in clean or ":regla_" in clean:
        return clean

    human = _ARTICLE_HUMAN_RE.fullmatch(_normalize_text(value))
    if human:
        unit = human.group("unit").replace(".", "_")
        return f"{human.group('corpus')}:articulo_{unit}"

    short = _SHORT_REF_RE.fullmatch(_normalize_text(value))
    if short:
        unit = short.group("unit").replace(".", "_")
        return f"{short.group('corpus')}:articulo_{unit}"

    return clean


def _problem_relevance(
    assessment: SessionJurisprudenceApplicabilityAssessment | None,
) -> bool:
    """E.5 no usa la materia formal como veto si norma y ratio sí coinciden."""
    return assessment is not None


def _material_mentions(
    record: JurisprudenceNormativeRelationRecord,
    applicable_normative_refs: set[str],
) -> tuple[list[str], list[str], list[NormRelationType]]:
    applicable = {_canonical_ref(reference) for reference in applicable_normative_refs}
    shared: list[str] = []
    material: list[str] = []
    relation_types: list[NormRelationType] = []

    for mention in record.mentions:
        reference = mention.candidate_normative_ref
        if reference is None:
            continue
        canonical = _canonical_ref(reference)
        if canonical not in applicable:
            continue
        if reference not in shared:
            shared.append(reference)
        if mention.material_relation_explicit:
            if reference not in material:
                material.append(reference)
            if mention.relation_type not in relation_types:
                relation_types.append(mention.relation_type)

    return shared, material, relation_types


def _ratio_mentions_normative_ref(ratio_text: str | None, reference: str) -> bool:
    if not ratio_text:
        return False
    normalized = _normalize_text(ratio_text)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    canonical = _canonical_ref(reference)
    if ":" not in canonical:
        return False
    unit = canonical.split(":", 1)[1]
    tokens = [token for token in unit.split("_") if token]
    if not tokens:
        return False
    return all(re.search(rf"\b{re.escape(token)}\b", normalized) for token in tokens)


def _validate_record_provenance(
    *,
    document_id: str,
    source_sha256: str,
    relation_record: JurisprudenceNormativeRelationRecord,
    temporal_record: JurisprudenceTemporalRecord,
    ratio_record: JurisprudenceRatioRecord,
) -> None:
    for label, record_document_id, record_sha in (
        ("E.3", relation_record.document_id, relation_record.source_sha256),
        ("E.4", temporal_record.document_id, temporal_record.source_sha256),
        ("E.5-ratio", ratio_record.document_id, ratio_record.source_sha256),
    ):
        if record_document_id != document_id:
            raise JurisprudenceEvidenceIntegrationError(
                f"El registro {label} no corresponde al documento recuperado."
            )
        if record_sha != source_sha256:
            raise JurisprudenceEvidenceIntegrationError(
                f"La huella {label} no coincide con la evidencia recuperada."
            )


def _review_only_missing_records(
    *,
    evidence_ref: str,
    document_id: str,
    page_number: int,
    source_sha256: str,
    retrieval_score: float,
    base: SessionJurisprudenceApplicabilityAssessment | None,
    missing: list[str],
) -> JurisprudenceEvidenceAssessment:
    return JurisprudenceEvidenceAssessment(
        evidence_ref=evidence_ref,
        document_id=document_id,
        page_number=page_number,
        source_sha256=source_sha256,
        retrieval_score=retrieval_score,
        decision=JurisprudenceEvidenceDecision.REVIEW_ONLY,
        authorized_for_evidence=False,
        temporal_state=JurisprudencePublicationTemporalState.UNKNOWN,
        binding_state=JurisprudenceBindingTemporalState.MANDATORY_DATE_UNKNOWN,
        binding_character_mandatory=False,
        mandatory_by_query_date=None,
        temporally_eligible=False,
        structured_thesis_sections_established=False,
        ratio_source_established=False,
        ratio_page_contains_justification=False,
        justification_normative_relevance_established=False,
        criterion_status_claim=JurisprudenceStatus.UNKNOWN,
        problem_relevance_established=_problem_relevance(base),
        normative_relevance_established=False,
        material_normative_relation_established=False,
        binding_force_evaluated=False,
        requires_human_review=True,
        reasons=missing,
    )


def integrate_session_jurisprudence_evidence(
    *,
    retrieval: SessionJurisprudenceRetrievalResult,
    applicability: list[SessionJurisprudenceApplicabilityAssessment],
    normative_relation_records: dict[str, JurisprudenceNormativeRelationRecord],
    temporal_records: dict[str, JurisprudenceTemporalRecord],
    ratio_records: dict[str, JurisprudenceRatioRecord],
    applicable_normative_refs: set[str],
    query_date: date,
) -> JurisprudenceEvidenceIntegrationRecord:
    """E.5 admite jurisprudencia sólo con ratio anclada en la Justificación."""

    applicability_by_page = {
        (item.document_id, item.page_number): item for item in applicability
    }
    assessments: list[JurisprudenceEvidenceAssessment] = []

    for hit in retrieval.hits:
        evidence_ref = f"session-jurisprudence:{hit.document_id}:page:{hit.page_number}"
        reasons: list[str] = []
        base = applicability_by_page.get((hit.document_id, hit.page_number))
        relation_record = normative_relation_records.get(hit.document_id)
        temporal_record = temporal_records.get(hit.document_id)
        ratio_record = ratio_records.get(hit.document_id)

        if relation_record is None or temporal_record is None or ratio_record is None:
            missing = []
            if relation_record is None:
                missing.append("missing_e3_normative_relation_record")
            if temporal_record is None:
                missing.append("missing_e4_temporal_record")
            if ratio_record is None:
                missing.append("missing_e5_ratio_record")
            assessments.append(
                _review_only_missing_records(
                    evidence_ref=evidence_ref,
                    document_id=hit.document_id,
                    page_number=hit.page_number,
                    source_sha256=hit.source_sha256,
                    retrieval_score=hit.score,
                    base=base,
                    missing=missing,
                )
            )
            continue

        _validate_record_provenance(
            document_id=hit.document_id,
            source_sha256=hit.source_sha256,
            relation_record=relation_record,
            temporal_record=temporal_record,
            ratio_record=ratio_record,
        )

        shared_refs, material_refs, relation_types = _material_mentions(
            relation_record,
            applicable_normative_refs,
        )
        temporal = assess_jurisprudence_temporal_context(
            temporal_record,
            query_date=query_date,
        )
        problem_relevant = _problem_relevance(base)
        norm_relevant = bool(shared_refs)
        material_relation = bool(material_refs)
        structured = ratio_record.structured_thesis_sections_established
        ratio_source = ratio_record.ratio_source_established
        ratio_page = hit.page_number in ratio_record.justification_source_pages
        ratio_norm_relevant = any(
            _ratio_mentions_normative_ref(ratio_record.ratio_source_text, reference)
            for reference in material_refs
        )

        if not temporal.binding_character_mandatory:
            reasons.append("official_type_is_not_mandatory_jurisprudence")
        elif temporal.mandatory_by_query_date is not True:
            reasons.extend(temporal.reasons)
        if not problem_relevant:
            reasons.append("problem_relevance_not_established")
        elif base is not None and "matter_mismatch" in base.reasons:
            reasons.append("cross_matter_classification_requires_review")
        if not norm_relevant:
            reasons.append("no_shared_applicable_normative_ref")
        if norm_relevant and not material_relation:
            reasons.append("normative_mention_without_material_relation")
        if not structured:
            reasons.append("structured_thesis_sections_incomplete")
        if not ratio_source:
            reasons.append("justification_not_available_as_ratio_source")
        if ratio_source and not ratio_page:
            reasons.append("retrieved_page_does_not_contain_justification")
        if ratio_source and material_relation and not ratio_norm_relevant:
            reasons.append("justification_not_linked_to_applicable_norm")
        if not temporal.temporally_eligible_for_evidence:
            reasons.extend(temporal.reasons)

        status = temporal.criterion_status_claim
        if status in {
            JurisprudenceStatus.SUPERSEDED,
            JurisprudenceStatus.INVALIDATED,
        }:
            reasons.append(f"status_claim_blocks_evidence_{status.value}")
        elif status is JurisprudenceStatus.HISTORICAL:
            reasons.append("historical_status_requires_specific_temporal_review")

        hard_rejection = (
            not problem_relevant
            or not norm_relevant
            or not temporal.binding_character_mandatory
            or temporal.mandatory_by_query_date is False
            or status
            in {
                JurisprudenceStatus.SUPERSEDED,
                JurisprudenceStatus.INVALIDATED,
            }
        )
        review_only = (
            not material_relation
            or not temporal.temporally_eligible_for_evidence
            or not structured
            or not ratio_source
            or not ratio_page
            or not ratio_norm_relevant
            or status is JurisprudenceStatus.HISTORICAL
        )

        if hard_rejection:
            decision = JurisprudenceEvidenceDecision.REJECTED
            authorized = False
        elif review_only:
            decision = JurisprudenceEvidenceDecision.REVIEW_ONLY
            authorized = False
        else:
            decision = JurisprudenceEvidenceDecision.ADMITTED
            authorized = True
            reasons.extend(
                [
                    "mandatory_jurisprudence_admitted_as_separate_evidence",
                    "ratio_source_is_official_justification",
                    "material_facts_and_ratio_transfer_remain_for_e6",
                ]
            )

        if NormRelationType.CONFLICTS in relation_types:
            reasons.append("explicit_normative_conflict_requires_review")
        if temporal.requires_human_review:
            reasons.append("temporal_record_requires_review")

        assessments.append(
            JurisprudenceEvidenceAssessment(
                evidence_ref=evidence_ref,
                document_id=hit.document_id,
                page_number=hit.page_number,
                source_sha256=hit.source_sha256,
                retrieval_score=hit.score,
                decision=decision,
                authorized_for_evidence=authorized,
                shared_normative_refs=shared_refs,
                explicit_material_relation_refs=material_refs,
                material_relation_types=relation_types,
                temporal_state=temporal.publication_state,
                binding_state=temporal.binding_state,
                binding_character_mandatory=temporal.binding_character_mandatory,
                mandatory_by_query_date=temporal.mandatory_by_query_date,
                temporally_eligible=temporal.temporally_eligible_for_evidence,
                structured_thesis_sections_established=structured,
                ratio_source_established=ratio_source,
                ratio_page_contains_justification=ratio_page,
                justification_normative_relevance_established=ratio_norm_relevant,
                criterion_status_claim=status,
                problem_relevance_established=problem_relevant,
                normative_relevance_established=norm_relevant,
                material_normative_relation_established=material_relation,
                binding_force_evaluated=temporal_record.binding_force_evaluated,
                requires_human_review=True,
                reasons=list(dict.fromkeys(reasons)) or ["evidence_review_required"],
            )
        )

    authorized_refs = [
        item.evidence_ref for item in assessments if item.authorized_for_evidence
    ]
    admitted = sum(
        item.decision is JurisprudenceEvidenceDecision.ADMITTED for item in assessments
    )
    review_only_count = sum(
        item.decision is JurisprudenceEvidenceDecision.REVIEW_ONLY
        for item in assessments
    )
    rejected = sum(
        item.decision is JurisprudenceEvidenceDecision.REJECTED for item in assessments
    )
    return JurisprudenceEvidenceIntegrationRecord(
        assessments=assessments,
        authorized_evidence_refs=authorized_refs,
        admitted_count=admitted,
        review_only_count=review_only_count,
        rejected_count=rejected,
        binding_force_evaluated=(
            bool(assessments) and all(item.binding_force_evaluated for item in assessments)
        ),
        requires_human_review=bool(assessments),
    )
