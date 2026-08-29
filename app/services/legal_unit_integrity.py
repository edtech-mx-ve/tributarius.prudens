from __future__ import annotations

import re
import unicodedata
from enum import StrEnum

# La expresión se limita a identificadores de artículo. No intenta interpretar
# fracciones, incisos ni transitorios: esas unidades deben auditarse por separado.
_ARTICLE_RE = re.compile(
    r"\bart(?:í|i)culo\s+"
    r"([0-9]+o?(?:-[a-z0-9]+)*(?:\s*(?:bis|ter|qu[aá]ter))?)"
    r"(?=[\s\.,;:\)\]-]|$)",
    re.IGNORECASE,
)


class ArticleConsistency(StrEnum):
    MATCH = "match"
    MISMATCH = "mismatch"
    METADATA_WITHOUT_ARTICLE = "metadata_without_article"
    TEXT_WITHOUT_ARTICLE = "text_without_article"


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return without_marks.casefold()


def normalize_article_identifier(value: str) -> str:
    """Normaliza un identificador para comparación exacta y reproducible."""
    folded = _fold(value)
    return re.sub(r"[^a-z0-9-]", "", folded)


def extract_article_identifier(value: str | None) -> str | None:
    """Extrae el primer identificador explícito `Artículo ...` de un texto."""
    if not value:
        return None
    match = _ARTICLE_RE.search(value)
    if match is None:
        return None
    return normalize_article_identifier(match.group(1))


def compare_article_unit(
    metadata_label: str | None,
    text: str,
    *,
    text_prefix_chars: int = 800,
) -> ArticleConsistency:
    """Compara la etiqueta jurídica con el primer artículo explícito del texto.

    La ausencia de artículo explícito en el texto no se interpreta como
    contradicción; queda clasificada como `text_without_article`.
    """
    metadata_article = extract_article_identifier(metadata_label)
    if metadata_article is None:
        return ArticleConsistency.METADATA_WITHOUT_ARTICLE

    text_article = extract_article_identifier(text[:text_prefix_chars])
    if text_article is None:
        return ArticleConsistency.TEXT_WITHOUT_ARTICLE

    if metadata_article == text_article:
        return ArticleConsistency.MATCH
    return ArticleConsistency.MISMATCH
