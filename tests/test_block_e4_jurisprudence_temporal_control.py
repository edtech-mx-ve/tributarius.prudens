from datetime import date
from pathlib import Path

from app.domain.jurisprudence import JurisprudenceStatus
from app.domain.jurisprudence_document import (
    JurisprudenceDocumentRepresentation,
    JurisprudencePage,
)
from app.domain.jurisprudence_temporal import (
    JurisprudencePublicationDatePrecision,
    JurisprudencePublicationTemporalState,
)
from app.services.jurisprudence_metadata_extraction import (
    extract_jurisprudence_metadata_record,
)
from app.services.jurisprudence_temporal_control import (
    assess_jurisprudence_temporal_context,
    build_jurisprudence_temporal_record,
)
from app.web.jurisprudence_session import (
    load_web_jurisprudence_temporal_record,
    save_web_jurisprudence_session,
)

SHA = "e" * 64
SESSION_ID = "f" * 32


def _representation(text: str) -> JurisprudenceDocumentRepresentation:
    return JurisprudenceDocumentRepresentation(
        document_id="jurisprudencia-e4-test",
        original_filename="criterio-e4.pdf",
        source_sha256=SHA,
        page_count=1,
        extracted_characters=len(text),
        pages=[JurisprudencePage(number=1, text=text, has_extractable_text=True)],
        full_text=text,
    )


def _temporal(text: str):
    document = _representation(text)
    metadata = extract_jurisprudence_metadata_record(document)
    return document, metadata, build_jurisprudence_temporal_record(metadata)


def test_e4_parses_exact_spanish_publication_date_without_promoting_legal_effect() -> None:
    _, _, record = _temporal(
        "Registro: 20261234\nRubro: PRUEBA.\nInstancia: Primera Sala\n"
        "Tipo: Jurisprudencia\nPublicación: viernes 14 de agosto de 2026"
    )

    assert record.publication_date_precision is JurisprudencePublicationDatePrecision.DAY
    assert record.parsed_publication_start == date(2026, 8, 14)
    assert record.parsed_publication_end == date(2026, 8, 14)
    assert record.publication_date_source_pages == [1]
    assert record.publication_date_verified is False
    assert record.criterion_status_verified is False
    assert record.legal_applicability_evaluated is False
    assert record.can_control_legal_decision is False


def test_e4_future_publication_is_temporally_ineligible_for_earlier_query() -> None:
    _, _, record = _temporal(
        "Registro: 20261234\nRubro: PRUEBA.\nInstancia: Primera Sala\n"
        "Tipo: Jurisprudencia\nPublicación: 15 de agosto de 2026"
    )

    assessment = assess_jurisprudence_temporal_context(
        record, query_date=date(2026, 8, 14)
    )

    assert (
        assessment.publication_state
        is JurisprudencePublicationTemporalState.PUBLISHED_AFTER_QUERY_DATE
    )
    assert assessment.published_by_query_date is False
    assert assessment.temporally_eligible_for_evidence is False
    assert assessment.legal_applicability_evaluated is False


def test_e4_exact_publication_before_query_only_clears_chronological_barrier() -> None:
    _, _, record = _temporal(
        "Registro: 20261234\nRubro: PRUEBA.\nInstancia: Primera Sala\n"
        "Tipo: Jurisprudencia\nPublicación: 14 de agosto de 2026"
    )

    assessment = assess_jurisprudence_temporal_context(
        record, query_date=date(2026, 9, 3)
    )

    assert (
        assessment.publication_state
        is JurisprudencePublicationTemporalState.PUBLISHED_BY_QUERY_DATE
    )
    assert assessment.published_by_query_date is True
    assert assessment.temporally_eligible_for_evidence is True
    assert assessment.requires_human_review is True
    assert "publication_date_not_legally_verified" in assessment.reasons
    assert assessment.can_control_legal_decision is False


def test_e4_month_precision_inside_same_month_fails_closed_as_ambiguous() -> None:
    _, _, record = _temporal(
        "Registro: 20261234\nRubro: PRUEBA.\nInstancia: Primera Sala\n"
        "Tipo: Jurisprudencia\nPublicación: agosto de 2026"
    )

    assert record.publication_date_precision is JurisprudencePublicationDatePrecision.MONTH
    assessment = assess_jurisprudence_temporal_context(
        record, query_date=date(2026, 8, 15)
    )

    assert (
        assessment.publication_state
        is JurisprudencePublicationTemporalState.AMBIGUOUS_AT_QUERY_DATE
    )
    assert assessment.published_by_query_date is None
    assert assessment.temporally_eligible_for_evidence is False
    assert assessment.requires_human_review is True


def test_e4_year_precision_after_year_end_can_clear_only_publication_barrier() -> None:
    _, _, record = _temporal(
        "Registro: 20261234\nRubro: PRUEBA.\nInstancia: Primera Sala\n"
        "Tipo: Tesis aislada\nPublicación: 2025"
    )

    assessment = assess_jurisprudence_temporal_context(
        record, query_date=date(2026, 1, 1)
    )

    assert record.publication_date_precision is JurisprudencePublicationDatePrecision.YEAR
    assert assessment.temporally_eligible_for_evidence is True
    assert assessment.legal_applicability_evaluated is False


def test_e4_missing_or_unparseable_publication_date_fails_closed() -> None:
    _, _, missing = _temporal("Rubro: PRUEBA SIN FECHA.")
    _, _, invalid = _temporal(
        "Rubro: PRUEBA.\nPublicación: fecha pendiente de publicación"
    )

    missing_assessment = assess_jurisprudence_temporal_context(
        missing, query_date=date(2026, 9, 3)
    )
    invalid_assessment = assess_jurisprudence_temporal_context(
        invalid, query_date=date(2026, 9, 3)
    )

    assert missing.publication_date_precision is JurisprudencePublicationDatePrecision.UNKNOWN
    assert invalid.publication_date_precision is JurisprudencePublicationDatePrecision.INVALID
    assert missing_assessment.temporally_eligible_for_evidence is False
    assert invalid_assessment.temporally_eligible_for_evidence is False


def test_e4_superseded_text_remains_an_unverified_status_claim() -> None:
    _, _, record = _temporal(
        "Registro: 20261234\nRubro: PRUEBA.\nInstancia: Tribunal Colegiado\n"
        "Tipo: Tesis aislada\nPublicación: 2020\n"
        "Criterio superado por contradicción posterior."
    )

    assessment = assess_jurisprudence_temporal_context(
        record, query_date=date(2026, 9, 3)
    )

    assert record.criterion_status_claim is JurisprudenceStatus.SUPERSEDED
    assert record.criterion_status_verified is False
    assert assessment.status_claim_treated_as_verified is False
    assert assessment.requires_human_review is True
    assert "unverified_status_claim_superseded" in assessment.reasons
    assert assessment.legal_applicability_evaluated is False


def test_e4_temporal_record_round_trip_is_session_scoped(tmp_path: Path) -> None:
    document, metadata, record = _temporal(
        "Registro: 20261234\nRubro: PRUEBA.\nInstancia: Primera Sala\n"
        "Tipo: Jurisprudencia\nPublicación: 14 de agosto de 2026"
    )
    (tmp_path / SESSION_ID).mkdir()

    save_web_jurisprudence_session(
        session_id=SESSION_ID,
        representation=document,
        metadata=metadata.extracted,
        metadata_record=metadata,
        temporal_record=record,
        temp_root=tmp_path,
    )
    loaded = load_web_jurisprudence_temporal_record(SESSION_ID, temp_root=tmp_path)

    assert loaded is not None
    assert loaded.document_id == document.document_id
    assert loaded.source_scope == "session"
    assert loaded.user_attached is True
    assert loaded.can_control_legal_decision is False
