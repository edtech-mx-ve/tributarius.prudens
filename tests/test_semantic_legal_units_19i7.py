from __future__ import annotations

from rag.chunking.legal_structurer import structure_document


def _labels(text: str) -> list[str]:
    return [
        unit.label
        for unit in structure_document(text, profile="legal_article")
    ]


def test_real_article_headings_are_boundaries() -> None:
    text = (
        "Artículo 18.- Texto.\n"
        "Artículo 18-A.- Texto A.\n"
        "Artículo 18-K.- Texto K.\n"
        "Artículo 31. Texto 31.\n"
    )
    assert _labels(text) == [
        "Artículo 18",
        "Artículo 18-A",
        "Artículo 18-K",
        "Artículo 31",
    ]


def test_spaced_hyphen_identifier_is_normalized_as_single_unit() -> None:
    units = structure_document(
        "Artículo 18 -M.- Texto del precepto.\n",
        profile="legal_article",
    )
    assert len(units) == 1
    assert units[0].label == "Artículo 18 -M"


def test_cross_reference_at_line_start_is_not_boundary() -> None:
    text = (
        "Artículo 30.- Cuerpo principal.\n"
        "artículo 31-A, primer párrafo, inciso d) de este Código.\n"
        "Continúa el cuerpo del artículo 30.\n"
        "Artículo 31.- Nuevo artículo.\n"
    )
    units = structure_document(text, profile="legal_article")
    assert [unit.label for unit in units] == ["Artículo 30", "Artículo 31"]
    assert "artículo 31-A" in units[0].text


def test_de_la_ley_reference_is_not_article_identifier() -> None:
    text = (
        "Artículo 165.- Texto previo.\n"
        "artículo 166 de la Ley del Impuesto sobre la Renta, durante 2014.\n"
        "Continúa el texto.\n"
        "Artículo 166.- Encabezado real.\n"
    )
    units = structure_document(text, profile="legal_article")
    assert [unit.label for unit in units] == ["Artículo 165", "Artículo 166"]
    assert "artículo 166 de la Ley" in units[0].text


def test_bis_ter_quater_are_supported() -> None:
    text = (
        "Artículo 5 BIS.- Uno.\n"
        "Artículo 5 TER.- Dos.\n"
        "Artículo 5 QUÁTER.- Tres.\n"
    )
    assert _labels(text) == [
        "Artículo 5 BIS",
        "Artículo 5 TER",
        "Artículo 5 QUÁTER",
    ]


def test_plain_reference_without_heading_separator_is_not_boundary() -> None:
    text = (
        "Artículo 10.- Texto.\n"
        "Artículo 18 de esta Ley será aplicable en lo conducente.\n"
        "Más texto.\n"
    )
    units = structure_document(text, profile="legal_article")
    assert len(units) == 1
    assert units[0].label == "Artículo 10"
    assert "Artículo 18 de esta Ley" in units[0].text
