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
    extract_jurisprudence_metadata,
)

SHA256 = "b" * 64


def _representation(text: str) -> JurisprudenceDocumentRepresentation:
    return JurisprudenceDocumentRepresentation(
        document_id="jurisprudencia-meta-test",
        original_filename="criterio.pdf",
        source_sha256=SHA256,
        page_count=1,
        extracted_characters=len(text),
        pages=[JurisprudencePage(number=1, text=text, has_extractable_text=True)],
        full_text=text,
    )


def test_extracts_explicit_jurisprudence_metadata() -> None:
    text = """Registro digital: 20261234
Rubro: DEVOLUCIÓN DE SALDO A FAVOR. REQUISITOS.
Instancia: Primera Sala
Materia: Administrativa
Tipo: Jurisprudencia
Publicación: 15 de agosto de 2026
Se interpreta el artículo 22 del CFF.
"""
    result = extract_jurisprudence_metadata(_representation(text))

    assert result.identifier == "20261234"
    assert result.title == "DEVOLUCIÓN DE SALDO A FAVOR. REQUISITOS."
    assert result.court_or_body == "Primera Sala"
    assert result.matter == "Administrativa"
    assert result.criterion_type is JurisprudenceCriterionType.JURISPRUDENCE
    assert result.publication_date_text == "15 de agosto de 2026"
    assert "Artículo 22 de CFF" in result.related_normative_refs
    assert result.source_pages == [1]
    assert result.requires_human_review is True


def test_detects_isolated_thesis_without_promoting_status() -> None:
    text = """Registro: 123456
Rubro: CRITERIO DE PRUEBA.
Instancia: Tribunal Colegiado
Tipo: Tesis aislada
Publicación: junio de 2025
"""
    result = extract_jurisprudence_metadata(_representation(text))

    assert result.criterion_type is JurisprudenceCriterionType.ISOLATED_THESIS
    assert result.status is JurisprudenceStatus.UNKNOWN
    assert result.relation_type is NormRelationType.UNKNOWN


def test_detects_explicit_superseded_status() -> None:
    result = extract_jurisprudence_metadata(
        _representation("Rubro: CRITERIO.\nCriterio superado por contradicción posterior.")
    )

    assert result.status is JurisprudenceStatus.SUPERSEDED


def test_missing_metadata_remains_unknown_and_reviewable() -> None:
    result = extract_jurisprudence_metadata(
        _representation("Texto jurisprudencial sin ficha estructurada.")
    )

    assert result.identifier is None
    assert result.title is None
    assert result.court_or_body is None
    assert result.criterion_type is JurisprudenceCriterionType.UNKNOWN
    assert result.status is JurisprudenceStatus.UNKNOWN
    assert result.requires_human_review is True
    assert result.warnings


def test_does_not_infer_norm_relation_from_mention() -> None:
    result = extract_jurisprudence_metadata(
        _representation("Rubro: PRUEBA.\nSe analiza el artículo 28 del CFF.")
    )

    assert "Artículo 28 de CFF" in result.related_normative_refs
    assert result.relation_type is NormRelationType.UNKNOWN


def test_adjective_jurisprudencial_does_not_promote_criterion_type() -> None:
    result = extract_jurisprudence_metadata(
        _representation("Texto jurisprudencial sin tipo de criterio declarado.")
    )

    assert result.criterion_type is JurisprudenceCriterionType.UNKNOWN
