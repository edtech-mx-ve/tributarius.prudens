from __future__ import annotations

from app.domain.legal_chunks import LegalUnitType
from rag.chunking.legal_structurer import (
    stable_chunk_id,
    structure_document,
    structure_prodecon_sections,
)


def test_legal_article_profile_splits_by_article() -> None:
    text = """Artículo 1. Disposición inicial.
Texto uno.
Artículo 2-A. Segunda disposición.
Texto dos.
"""
    units = structure_document(text, profile="legal_article")
    assert len(units) == 2
    assert all(item.unit_type is LegalUnitType.ARTICLE for item in units)


def test_rmf_profile_splits_by_rule_number() -> None:
    text = """2.1.1. Regla primera
Contenido A.
2.1.2. Regla segunda
Contenido B.
"""
    units = structure_document(text, profile="administrative_rule")
    assert len(units) == 2


def test_unam_real_heading_shapes_produce_exactly_seven_chapters() -> None:
    text = """I. Principios constitucionales en materia tributaria: derechos . . . 17
II. La interpretación de la norma tributaria . . . 61

I. PRINCIPIOS CONSTITUCIONALES
EN MATERIA TRIBUTARIA: DERECHOS
HUMANOS DE LOS CONTRIBUYENTES
Gabriela autora
Contenido I.

II. LA INTERPRETACIÓN DE LA NORMA
TRIBUTARIA
Autor
Contenido II.

III. LOS TRIBUTOS Y SUS ELEMENTOS
ESENCIALES
Autor
Contenido III.

IV. SUJETOS DE LA OBLIGACIÓN TRIBUTARIA
Autor
Contenido IV.

V. EL CÁLCULO DE LAS CONTRIBUCIONES:
CASOS PRÁCTICOS EN LOS IMPUESTOS
Autor
Contenido V.

VI. FORMAS DE EXTINCIÓN DE LA DEUDA
TRIBUTARIA
Autor
Contenido VI.

VII. EL INCUMPLIMIENTO
DE LAS OBLIGACIONES TRIBUTARIAS
Autor
Contenido VII.
"""
    units = structure_document(text, profile="academic_chapter")
    assert len(units) == 7
    assert [unit.label.split(" — ", 1)[0] for unit in units] == [
        "Capítulo I",
        "Capítulo II",
        "Capítulo III",
        "Capítulo IV",
        "Capítulo V",
        "Capítulo VI",
        "Capítulo VII",
    ]


def test_unam_ignores_internal_roman_lists() -> None:
    text = """I. PRINCIPIOS CONSTITUCIONALES
Contenido.
I. CONTRIBUYENTE
Lista interna.
II. LA INTERPRETACIÓN DE LA NORMA
TRIBUTARIA
Contenido.
III. LOS TRIBUTOS Y SUS ELEMENTOS
ESENCIALES
Contenido.
IV. SUJETOS DE LA OBLIGACIÓN TRIBUTARIA
Contenido.
V. EL CÁLCULO DE LAS CONTRIBUCIONES
Contenido.
VI. FORMAS DE EXTINCIÓN DE LA DEUDA
TRIBUTARIA
Contenido.
VII. EL INCUMPLIMIENTO
DE LAS OBLIGACIONES TRIBUTARIAS
Contenido.
"""
    units = structure_document(text, profile="academic_chapter")
    assert len(units) == 7


def test_fallback_uses_headings() -> None:
    units = structure_document(
        "# Introducción\nTexto.\n\n## Conceptos\nTexto.",
        profile="legal_article",
    )
    assert len(units) == 2
    assert all(item.used_fallback for item in units)


def test_document_without_structure_is_one_fallback() -> None:
    units = structure_document("Texto sin estructura.", profile="legal_article")
    assert len(units) == 1
    assert units[0].used_fallback is True


def test_prodecon_sections_are_preserved() -> None:
    units = structure_prodecon_sections(
        [
            ("PRODECON-01", "Contenido 1", 11, 22),
            ("PRODECON-02", "Contenido 2", 23, 36),
        ]
    )
    assert len(units) == 2


def test_chunk_id_is_deterministic() -> None:
    first = stable_chunk_id(
        "cff",
        LegalUnitType.ARTICLE,
        "Artículo 1",
        "Texto.",
        ordinal=1,
    )
    second = stable_chunk_id(
        "cff",
        LegalUnitType.ARTICLE,
        "Artículo 1",
        "Texto.",
        ordinal=1,
    )
    assert first == second


def test_chunk_id_ordinal_prevents_duplicate_collision() -> None:
    first = stable_chunk_id(
        "cff",
        LegalUnitType.ARTICLE,
        "Artículo 1",
        "Texto.",
        ordinal=1,
    )
    second = stable_chunk_id(
        "cff",
        LegalUnitType.ARTICLE,
        "Artículo 1",
        "Texto.",
        ordinal=2,
    )
    assert first != second


def test_chunk_service_assigns_ordinal_to_each_unit() -> None:
    from app.services.corpus_chunking_service import _make_chunks
    from rag.chunking.legal_structurer import StructuredUnit

    units = [
        StructuredUnit(
            unit_type=LegalUnitType.ARTICLE,
            label="Artículo 1",
            text="Texto repetido.",
        ),
        StructuredUnit(
            unit_type=LegalUnitType.ARTICLE,
            label="Artículo 1",
            text="Texto repetido.",
        ),
    ]
    metadata = {
        "source_role": "normativa",
        "document_type": "ley",
        "matter": ["fiscal"],
        "jurisdiction": "México",
        "fiscal_year": None,
        "publication_date": None,
        "last_reform_date": None,
        "effective_from": None,
        "effective_to": None,
    }

    chunks = _make_chunks(
        canonical_id="cff",
        title="Código Fiscal de la Federación",
        source_sha256="a" * 64,
        metadata=metadata,
        units=units,
    )

    assert len(chunks) == 2
    assert chunks[0].chunk_id != chunks[1].chunk_id
    assert ":00001:" in chunks[0].chunk_id
    assert ":00002:" in chunks[1].chunk_id
