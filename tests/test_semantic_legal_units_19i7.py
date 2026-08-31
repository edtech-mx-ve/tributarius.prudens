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
    assert units[0].label == "Artículo 18-M"


def test_dot_hyphen_ordinal_identifiers_preserve_compound_suffix() -> None:
    text = (
        "Artículo 1o.- Texto del artículo primero.\n"
        "Artículo 1o.-A.- Texto A.\n"
        "Artículo 1o.-A BIS.- Texto A BIS.\n"
        "Artículo 1o.-B.- Texto B.\n"
        "Artículo 1o.-C.- Texto C.\n"
        "Artículo 2o.- Texto del artículo segundo.\n"
    )
    assert _labels(text) == [
        "Artículo 1o",
        "Artículo 1o-A",
        "Artículo 1o-A BIS",
        "Artículo 1o-B",
        "Artículo 1o-C",
        "Artículo 2o",
    ]


def test_dot_before_bis_is_part_of_article_identifier() -> None:
    text = (
        "ARTÍCULO 6o. Bis. - Texto del artículo bis.\n"
        "ARTÍCULO 7o. Bis. - Texto del artículo siguiente.\n"
    )
    assert _labels(text) == [
        "Artículo 6o Bis",
        "Artículo 7o Bis",
    ]


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


def test_lowercase_reform_and_transitory_references_are_not_boundaries() -> None:
    text = (
        "Artículo 4o.- Texto normativo real.\n"
        "### artículo 4o.-A de la misma, o a las que se les aplique la tasa de 0%.\n"
        "### artículo 4o. de la Constitución, para quedar como sigue:\n"
        "artículo 103. Se derogan diversas disposiciones.\n"
        "Artículo 5o.- Siguiente precepto real.\n"
    )
    units = structure_document(text, profile="legal_article")
    assert [unit.label for unit in units] == ["Artículo 4o", "Artículo 5o"]
    assert "artículo 4o.-A de la misma" in units[0].text
    assert "artículo 4o. de la Constitución" in units[0].text
    assert "artículo 103. Se derogan" in units[0].text


def test_article_fraction_amount_heading_is_not_new_article_boundary() -> None:
    text = (
        "Artículo 8o.- Texto normativo real.\n"
        "### Artículo 8o. fracción II primer párrafo: $156,135.00\n"
        "### Artículo 8o. fracción II segundo párrafo: $156,135.01 y hasta $197,771.00\n"
        "Artículo 9o.- Siguiente artículo real.\n"
    )
    units = structure_document(text, profile="legal_article")
    assert [unit.label for unit in units] == ["Artículo 8o", "Artículo 9o"]
    assert "Artículo 8o. fracción II primer párrafo" in units[0].text
    assert "Artículo 8o. fracción II segundo párrafo" in units[0].text


def test_uppercase_article_heading_is_supported() -> None:
    text = (
        "ARTÍCULO 32-B BIS. Texto del precepto.\n"
        "ARTICULO 32-B TER. Texto del siguiente precepto.\n"
    )
    assert _labels(text) == [
        "Artículo 32-B BIS",
        "Artículo 32-B TER",
    ]


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
