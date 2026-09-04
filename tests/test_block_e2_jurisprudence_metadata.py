from pathlib import Path

from app.domain.jurisprudence import (
    JurisprudenceCriterionType,
    JurisprudenceStatus,
    NormRelationType,
)
from app.domain.jurisprudence_document import (
    JurisprudenceDocumentRepresentation,
    JurisprudencePage,
)
from app.services.jurisprudence_metadata_extraction import (
    extract_jurisprudence_metadata_record,
)
from app.web.jurisprudence_session import (
    load_web_jurisprudence_metadata_record,
    save_web_jurisprudence_session,
)

SHA = "c" * 64
SESSION_ID = "d" * 32


def _representation(*pages: str) -> JurisprudenceDocumentRepresentation:
    jurisprudence_pages = [
        JurisprudencePage(number=index, text=text, has_extractable_text=True)
        for index, text in enumerate(pages, start=1)
    ]
    full_text = "\n\n".join(pages)
    return JurisprudenceDocumentRepresentation(
        document_id="jurisprudencia-e2-test",
        original_filename="criterio-e2.pdf",
        source_sha256=SHA,
        page_count=len(jurisprudence_pages),
        extracted_characters=len(full_text),
        pages=jurisprudence_pages,
        full_text=full_text,
    )


def test_e2_extracts_explicit_metadata_without_legal_promotion() -> None:
    document = _representation(
        """Registro digital: 20261234
Tesis: 1a./J. 25/2026 (11a.)
Rubro: DEVOLUCIÓN DE SALDO A FAVOR. REQUISITOS.
Instancia: Primera Sala
Época: Undécima Época
Materia: Administrativa
Tipo: Jurisprudencia
Publicación: viernes 14 de agosto de 2026
Fuente: Semanario Judicial de la Federación
Obligatoriedad: dato declarado en la fuente; pendiente de validación del sistema.
Texto: Para resolver la controversia se interpreta el artículo 22 del CFF.
"""
    )

    record = extract_jurisprudence_metadata_record(document)
    extracted = record.extracted

    assert extracted.identifier == "20261234"
    assert extracted.thesis_number == "1a./J. 25/2026 (11a.)"
    assert extracted.title == "DEVOLUCIÓN DE SALDO A FAVOR. REQUISITOS."
    assert extracted.court_or_body == "Primera Sala"
    assert extracted.epoch == "Undécima Época"
    assert extracted.publication_source == "Semanario Judicial de la Federación"
    assert extracted.criterion_type is JurisprudenceCriterionType.JURISPRUDENCE
    assert "Artículo 22 de CFF" in extracted.related_normative_refs

    assert record.metadata_verified is False
    assert record.authenticity_verified is False
    assert record.temporal_validity_verified is False
    assert record.normative_relation_verified is False
    assert record.legal_applicability_evaluated is False
    assert record.binding_force_evaluated is False
    assert record.can_control_legal_decision is False


def test_e2_preserves_field_level_page_provenance() -> None:
    document = _representation(
        "Registro digital: 20261234\nRubro: CRITERIO DE PRUEBA.",
        "Instancia: Primera Sala\nTipo: Jurisprudencia\nPublicación: agosto de 2026",
    )

    record = extract_jurisprudence_metadata_record(document)
    evidence = {item.field_name: item for item in record.evidence}

    assert evidence["identifier"].source_pages == [1]
    assert evidence["title"].source_pages == [1]
    assert evidence["court_or_body"].source_pages == [2]
    assert evidence["criterion_type"].source_pages == [2]
    assert evidence["publication_date_text"].source_pages == [2]
    assert all(item.verified is False for item in record.evidence)


def test_e2_missing_core_metadata_stays_missing_and_reviewable() -> None:
    record = extract_jurisprudence_metadata_record(
        _representation("Documento con un criterio fiscal sin ficha explícita.")
    )

    assert record.extracted.identifier is None
    assert record.extracted.title is None
    assert record.extracted.court_or_body is None
    assert record.extracted.criterion_type is JurisprudenceCriterionType.UNKNOWN
    assert record.extracted.requires_human_review is True
    assert set(record.missing_core_fields) == {
        "identifier",
        "title",
        "court_or_body",
        "criterion_type",
        "publication_date_text",
    }


def test_e2_norm_mention_is_not_a_verified_relation() -> None:
    record = extract_jurisprudence_metadata_record(
        _representation(
            "Registro digital: 20261234\n"
            "Rubro: INTERPRETACIÓN FISCAL.\n"
            "Instancia: Primera Sala\n"
            "Tipo: Jurisprudencia\n"
            "Publicación: agosto de 2026\n"
            "Texto: El asunto menciona el artículo 28 del CFF."
        )
    )

    assert "Artículo 28 de CFF" in record.extracted.related_normative_refs
    assert record.extracted.relation_type is NormRelationType.UNKNOWN
    assert record.normative_relation_verified is False


def test_e2_temporal_words_do_not_complete_temporal_validation() -> None:
    record = extract_jurisprudence_metadata_record(
        _representation(
            "Registro: 20261234\n"
            "Rubro: CRITERIO HISTÓRICO.\n"
            "Instancia: Tribunal Colegiado\n"
            "Tipo: Tesis aislada\n"
            "Publicación: 2020\n"
            "Criterio superado por contradicción posterior."
        )
    )

    assert record.extracted.status is JurisprudenceStatus.SUPERSEDED
    assert record.temporal_validity_verified is False
    assert record.legal_applicability_evaluated is False


def test_e2_metadata_record_round_trip_is_session_scoped(tmp_path: Path) -> None:
    document = _representation(
        "Registro digital: 20261234\n"
        "Rubro: CRITERIO DE SESIÓN.\n"
        "Instancia: Primera Sala\n"
        "Tipo: Jurisprudencia\n"
        "Publicación: agosto de 2026"
    )
    record = extract_jurisprudence_metadata_record(document)
    (tmp_path / SESSION_ID).mkdir()

    save_web_jurisprudence_session(
        session_id=SESSION_ID,
        representation=document,
        metadata=record.extracted,
        metadata_record=record,
        temp_root=tmp_path,
    )
    loaded = load_web_jurisprudence_metadata_record(SESSION_ID, temp_root=tmp_path)

    assert loaded is not None
    assert loaded.document_id == document.document_id
    assert loaded.source_sha256 == SHA
    assert loaded.source_scope == "session"
    assert loaded.user_attached is True
    assert loaded.can_control_legal_decision is False
