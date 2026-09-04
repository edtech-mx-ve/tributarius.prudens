from __future__ import annotations

from app.domain.jurisprudence import JurisprudenceCriterionType
from app.domain.jurisprudence_metadata import JurisprudenceMetadataRecord
from app.domain.jurisprudence_ratio import (
    JurisprudenceRatioRecord,
    JurisprudenceRatioSourceSection,
)


def _pages(record: JurisprudenceMetadataRecord, field_name: str) -> list[int]:
    return sorted(
        {
            page
            for evidence in record.evidence
            if evidence.field_name == field_name
            for page in evidence.source_pages
        }
    )


def build_jurisprudence_ratio_record(
    metadata_record: JurisprudenceMetadataRecord,
) -> JurisprudenceRatioRecord:
    """Localiza la ratio en la Justificación sin equiparar toda ella a ratio verificada."""

    extracted = metadata_record.extracted
    is_jurisprudence = (
        extracted.criterion_type is JurisprudenceCriterionType.JURISPRUDENCE
    )
    has_facts = bool(extracted.facts_text)
    has_criterion = bool(extracted.legal_criterion_text)
    has_justification = bool(extracted.justification_text)
    structured = is_jurisprudence and has_facts and has_criterion and has_justification
    ratio_source_established = is_jurisprudence and has_justification

    return JurisprudenceRatioRecord(
        document_id=metadata_record.document_id,
        source_sha256=metadata_record.source_sha256,
        criterion_type=extracted.criterion_type,
        facts_text=extracted.facts_text,
        legal_criterion_text=extracted.legal_criterion_text,
        justification_text=extracted.justification_text,
        facts_source_pages=_pages(metadata_record, "facts_text"),
        legal_criterion_source_pages=_pages(metadata_record, "legal_criterion_text"),
        justification_source_pages=_pages(metadata_record, "justification_text"),
        ratio_source_section=(
            JurisprudenceRatioSourceSection.JUSTIFICATION
            if ratio_source_established
            else JurisprudenceRatioSourceSection.UNKNOWN
        ),
        ratio_source_text=(
            extracted.justification_text if ratio_source_established else None
        ),
        structured_thesis_sections_established=structured,
        ratio_source_established=ratio_source_established,
        requires_human_review=True,
    )
