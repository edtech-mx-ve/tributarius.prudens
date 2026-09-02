from __future__ import annotations

import re

from app.domain.jurisprudence import (
    JurisprudenceCriterionType,
    JurisprudenceStatus,
    NormRelationType,
)
from app.domain.jurisprudence_document import JurisprudenceDocumentRepresentation
from app.domain.jurisprudence_extraction import JurisprudenceExtractedMetadata

REGISTRO_RE = re.compile(
    r"(?im)^\s*(?:registro(?:\s+digital)?|registro)\s*[:.]?\s*(\d{4,12})\s*$"
)
RUBRO_RE = re.compile(r"(?im)^\s*(?:rubro|t[ií]tulo)\s*[:.]\s*(.+?)\s*$")
INSTANCIA_RE = re.compile(
    r"(?im)^\s*(?:instancia|tribunal|[oó]rgano)\s*[:.]\s*(.+?)\s*$"
)
MATERIA_RE = re.compile(r"(?im)^\s*materia(?:\(s\))?\s*[:.]\s*(.+?)\s*$")
PUBLICACION_RE = re.compile(
    r"(?im)^\s*(?:publicaci[oó]n|fecha de publicaci[oó]n)\s*[:.]\s*(.+?)\s*$"
)
NORMATIVE_REF_RE = re.compile(
    r"(?i)\b(?:art[ií]culo|art\.)\s*(\d+(?:-[A-Z0-9]+)?)"
    r"(?:\s+de(?:l| la)?\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9 ._-]{1,80}))?"
)
JURISPRUDENCE_TYPE_RE = re.compile(r"(?i)\bjurisprudencia\b")
ISOLATED_THESIS_TYPE_RE = re.compile(r"(?i)\btesis\s+aislada\b")
PRECEDENT_TYPE_RE = re.compile(r"(?i)\bprecedente\b")


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def _criterion_type(text: str) -> JurisprudenceCriterionType:
    if ISOLATED_THESIS_TYPE_RE.search(text):
        return JurisprudenceCriterionType.ISOLATED_THESIS
    if JURISPRUDENCE_TYPE_RE.search(text):
        return JurisprudenceCriterionType.JURISPRUDENCE
    if PRECEDENT_TYPE_RE.search(text):
        return JurisprudenceCriterionType.PRECEDENT
    return JurisprudenceCriterionType.UNKNOWN


def _status(text: str) -> JurisprudenceStatus:
    lowered = text.casefold()
    if any(term in lowered for term in ("superada", "superado", "sustituida", "sustituido")):
        return JurisprudenceStatus.SUPERSEDED
    if any(term in lowered for term in ("invalidada", "invalidado", "sin vigencia")):
        return JurisprudenceStatus.INVALIDATED
    if any(term in lowered for term in ("histórica", "historica", "histórico", "historico")):
        return JurisprudenceStatus.HISTORICAL
    return JurisprudenceStatus.UNKNOWN


def _normative_refs(text: str) -> list[str]:
    refs: list[str] = []
    for match in NORMATIVE_REF_RE.finditer(text):
        article = match.group(1)
        document = (match.group(2) or "").strip(" .")
        ref = f"Artículo {article}"
        if document:
            ref = f"{ref} de {document}"
        if ref not in refs:
            refs.append(ref)
    return refs[:100]


def extract_jurisprudence_metadata(
    document: JurisprudenceDocumentRepresentation,
) -> JurisprudenceExtractedMetadata:
    """Identifica metadatos explícitos sin convertir inferencias en hechos verificados."""
    text = document.full_text
    identifier = _first_match(REGISTRO_RE, text)
    title = _first_match(RUBRO_RE, text)
    court_or_body = _first_match(INSTANCIA_RE, text)
    matter = _first_match(MATERIA_RE, text)
    publication_date_text = _first_match(PUBLICACION_RE, text)
    criterion_type = _criterion_type(text)
    status = _status(text)
    related_refs = _normative_refs(text)

    source_pages = [
        page.number
        for page in document.pages
        if page.has_extractable_text
        and any(
            value and value in page.text
            for value in (identifier, title, court_or_body, matter, publication_date_text)
        )
    ]

    warnings: list[str] = []
    if identifier is None:
        warnings.append("No se identificó registro digital.")
    if title is None:
        warnings.append("No se identificó rubro o título explícito.")
    if court_or_body is None:
        warnings.append("No se identificó órgano o instancia.")
    if criterion_type is JurisprudenceCriterionType.UNKNOWN:
        warnings.append("No se determinó el tipo de criterio.")
    if publication_date_text is None:
        warnings.append("No se identificó fecha de publicación.")

    return JurisprudenceExtractedMetadata(
        identifier=identifier,
        title=title,
        court_or_body=court_or_body,
        criterion_type=criterion_type,
        publication_date_text=publication_date_text,
        status=status,
        matter=matter,
        related_normative_refs=related_refs,
        relation_type=NormRelationType.UNKNOWN,
        source_pages=source_pages,
        requires_human_review=True,
        warnings=warnings,
    )
