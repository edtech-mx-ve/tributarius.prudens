from __future__ import annotations

from datetime import date
from pathlib import Path

from app.domain.integral_legal_evidence import IntegralLegalEvidenceChannel
from app.domain.jurisprudence import (
    JurisprudenceCriterionType,
    JurisprudenceStatus,
    NormRelationType,
)
from app.domain.jurisprudence_document import (
    JurisprudenceDocumentRepresentation,
    JurisprudencePage,
)
from app.domain.jurisprudence_evidence import JurisprudenceEvidenceDecision
from app.domain.jurisprudence_extraction import JurisprudenceExtractedMetadata
from app.domain.jurisprudence_normative_relations import (
    JurisprudenceNormativeLinkBasis,
    JurisprudenceNormativeMention,
    JurisprudenceNormativeRelationRecord,
    JurisprudenceNormativeUnitType,
)
from app.domain.jurisprudence_ratio import (
    JurisprudenceRatioRecord,
    JurisprudenceRatioSourceSection,
)
from app.domain.jurisprudence_temporal import (
    JurisprudencePublicationDatePrecision,
    JurisprudenceTemporalRecord,
)
from app.services.integral_legal_evidence import build_integral_legal_evidence_map
from app.services.jurisprudence_hybrid_stage import run_session_jurisprudence_stage
from app.web.runtime_runner import _present_session_jurisprudence
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request

SHA = "e" * 64
DOC_ID = "jurisprudencia-e5"


def _document(
    text: str = "La controversia interpreta el artículo 22 del CFF.",
) -> JurisprudenceDocumentRepresentation:
    return JurisprudenceDocumentRepresentation(
        document_id=DOC_ID,
        original_filename="criterio-e5.pdf",
        source_sha256=SHA,
        page_count=1,
        extracted_characters=len(text),
        pages=[JurisprudencePage(number=1, text=text, has_extractable_text=True)],
        full_text=text,
    )


def _metadata() -> JurisprudenceExtractedMetadata:
    return JurisprudenceExtractedMetadata(
        identifier="20261234",
        title="APLICABILIDAD DEL ARTÍCULO 22 DEL CFF.",
        court_or_body="Primera Sala",
        criterion_type=JurisprudenceCriterionType.JURISPRUDENCE,
        status=JurisprudenceStatus.CURRENT,
        facts_text="Una persona solicitó la aplicación del artículo 22 del CFF.",
        legal_criterion_text="El artículo 22 del CFF debe aplicarse al supuesto resuelto.",
        justification_text=(
            "La justificación interpreta el artículo 22 del CFF para resolver "
            "la controversia planteada."
        ),
        matter="fiscal",
        related_normative_refs=["Artículo 22 de CFF"],
        relation_type=NormRelationType.INTERPRETS,
        source_pages=[1],
        requires_human_review=True,
    )


def _relation_record(
    *,
    normative_ref: str = "cff:articulo_22",
    relation_type: NormRelationType = NormRelationType.INTERPRETS,
    material: bool = True,
) -> JurisprudenceNormativeRelationRecord:
    mention = JurisprudenceNormativeMention(
        mention_id="E3-NORM-001",
        source_page=1,
        source_excerpt="La controversia interpreta el artículo 22 del CFF.",
        legal_unit_type=JurisprudenceNormativeUnitType.ARTICLE,
        legal_unit=normative_ref.rsplit("_", 1)[-1],
        instrument_match="CFF",
        candidate_corpus_id="cff",
        candidate_normative_ref=normative_ref,
        corpus_in_primary_manifest=True,
        relation_type=relation_type,
        linkage_basis=(
            JurisprudenceNormativeLinkBasis.EXPLICIT_RELATION_LANGUAGE
            if material
            else JurisprudenceNormativeLinkBasis.EXPLICIT_NORMATIVE_MENTION
        ),
        material_relation_explicit=material,
    )
    return JurisprudenceNormativeRelationRecord(
        document_id=DOC_ID,
        source_sha256=SHA,
        normative_corpus_ids=["cff"],
        mentions=[mention],
        mention_count=1,
        linked_to_primary_corpus_count=1,
        unresolved_or_external_count=0,
        explicit_material_relation_count=1 if material else 0,
    )


def _temporal_record(
    *,
    publication_date: date = date(2026, 1, 15),
    status: JurisprudenceStatus = JurisprudenceStatus.CURRENT,
) -> JurisprudenceTemporalRecord:
    return JurisprudenceTemporalRecord(
        document_id=DOC_ID,
        source_sha256=SHA,
        criterion_type=JurisprudenceCriterionType.JURISPRUDENCE,
        publication_date_text=publication_date.isoformat(),
        parsed_publication_start=publication_date,
        parsed_publication_end=publication_date,
        publication_date_precision=JurisprudencePublicationDatePrecision.DAY,
        publication_date_source_pages=[1],
        binding_character_mandatory=True,
        binding_character_basis="official_type_jurisprudence",
        binding_effective_date_text=publication_date.isoformat(),
        parsed_binding_start=publication_date,
        parsed_binding_end=publication_date,
        binding_date_precision=JurisprudencePublicationDatePrecision.DAY,
        binding_date_source_pages=[1],
        criterion_status_claim=status,
        binding_force_evaluated=True,
    )


def _ratio_record() -> JurisprudenceRatioRecord:
    justification = (
        "La justificación interpreta el artículo 22 del CFF para resolver "
        "la controversia planteada."
    )
    return JurisprudenceRatioRecord(
        document_id=DOC_ID,
        source_sha256=SHA,
        criterion_type=JurisprudenceCriterionType.JURISPRUDENCE,
        facts_text="Una persona solicitó la aplicación del artículo 22 del CFF.",
        legal_criterion_text="El artículo 22 del CFF debe aplicarse al supuesto resuelto.",
        justification_text=justification,
        facts_source_pages=[1],
        legal_criterion_source_pages=[1],
        justification_source_pages=[1],
        ratio_source_section=JurisprudenceRatioSourceSection.JUSTIFICATION,
        ratio_source_text=justification,
        structured_thesis_sections_established=True,
        ratio_source_established=True,
    )


def _run(
    *,
    relation_record: JurisprudenceNormativeRelationRecord | None = None,
    temporal_record: JurisprudenceTemporalRecord | None = None,
    applicable_ref: str = "cff:articulo_22",
):
    document = _document()
    return run_session_jurisprudence_stage(
        query="controversia aplicabilidad artículo 22 cff",
        documents=[document],
        metadata_by_document_id={DOC_ID: _metadata()},
        applicable_normative_refs={applicable_ref},
        matter="fiscal",
        top_k=5,
        normative_relation_records={
            DOC_ID: relation_record or _relation_record()
        },
        temporal_records={DOC_ID: temporal_record or _temporal_record()},
        ratio_records={DOC_ID: _ratio_record()},
        query_date=date(2026, 9, 3),
    )


def test_e5_admits_only_material_temporally_eligible_session_evidence() -> None:
    result = _run()

    integration = result.evidence_integration
    assert integration is not None
    assert integration.admitted_count == 1
    assert integration.review_only_count == 0
    assert integration.rejected_count == 0
    assert result.evidence == [f"session-jurisprudence:{DOC_ID}:page:1"]

    assessment = integration.assessments[0]
    assert assessment.decision is JurisprudenceEvidenceDecision.ADMITTED
    assert assessment.authorized_for_evidence is True
    assert assessment.shared_normative_refs == ["cff:articulo_22"]
    assert assessment.material_normative_relation_established is True
    assert assessment.normative_evidence_preserved is True
    assert assessment.legal_applicability_determined is False
    assert assessment.binding_force_evaluated is True
    assert assessment.binding_character_mandatory is True
    assert assessment.mandatory_by_query_date is True
    assert assessment.ratio_source_established is True
    assert assessment.justification_normative_relevance_established is True
    assert assessment.can_control_legal_decision is False


def test_e5_does_not_promote_a_bare_normative_citation() -> None:
    result = _run(
        relation_record=_relation_record(
            relation_type=NormRelationType.CITES,
            material=False,
        )
    )

    integration = result.evidence_integration
    assert integration is not None
    assert integration.admitted_count == 0
    assert integration.review_only_count == 1
    assert result.evidence == []
    assert "normative_mention_without_material_relation" in (
        integration.assessments[0].reasons
    )


def test_e5_rejects_criterion_published_after_query_date() -> None:
    result = _run(
        temporal_record=_temporal_record(publication_date=date(2027, 1, 15))
    )

    integration = result.evidence_integration
    assert integration is not None
    assert integration.rejected_count == 1
    assert result.evidence == []
    assert integration.assessments[0].temporally_eligible is False


def test_e5_rejects_jurisprudence_about_a_different_normative_rule() -> None:
    result = _run(
        relation_record=_relation_record(normative_ref="cff:articulo_28"),
        applicable_ref="cff:articulo_22",
    )

    integration = result.evidence_integration
    assert integration is not None
    assert integration.rejected_count == 1
    assert integration.assessments[0].normative_relevance_established is False
    assert result.evidence == []


def test_e5_explicit_conflict_is_evidence_but_never_controls_decision() -> None:
    result = _run(
        relation_record=_relation_record(relation_type=NormRelationType.CONFLICTS)
    )

    integration = result.evidence_integration
    assert integration is not None
    assessment = integration.assessments[0]
    assert assessment.authorized_for_evidence is True
    assert assessment.requires_human_review is True
    assert "explicit_normative_conflict_requires_review" in assessment.reasons
    assert integration.can_control_legal_decision is False


def test_e5_integral_evidence_map_includes_only_authorized_session_refs() -> None:
    session = _run()
    result = _orchestrator(None).run(_request()).model_copy(
        update={"session_jurisprudence_result": session}
    )

    evidence_map = build_integral_legal_evidence_map(result)
    item = next(
        evidence
        for evidence in evidence_map.items
        if evidence.channel is IntegralLegalEvidenceChannel.JURISPRUDENCE
    )

    assert item.present is True
    assert item.references == [f"session-jurisprudence:{DOC_ID}:page:1"]
    assert item.requires_human_review is True


def test_e5_web_projection_excludes_non_admitted_session_candidates() -> None:
    result = _run(
        relation_record=_relation_record(
            relation_type=NormRelationType.CITES,
            material=False,
        )
    )

    assert _present_session_jurisprudence(result) == []


def test_e5_runtime_loads_e3_e4_and_ratio_session_records() -> None:
    source = Path("app/web/runtime_runner.py").read_text(encoding="utf-8")

    assert "load_web_jurisprudence_normative_relation_record(" in source
    assert "load_web_jurisprudence_temporal_record(" in source
    assert "session_jurisprudence_normative_relations=" in source
    assert "session_jurisprudence_temporal_records=" in source
    assert "load_web_jurisprudence_ratio_record(" in source
    assert "session_jurisprudence_ratio_records=" in source
