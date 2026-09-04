from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Literal

from app.domain.jurisprudence import (
    JurisprudenceCriterionType,
    JurisprudenceStatus,
    NormRelationType,
)
from app.domain.jurisprudence_document import JurisprudenceDocumentRepresentation
from app.domain.jurisprudence_extraction import JurisprudenceExtractedMetadata
from app.domain.jurisprudence_metadata import (
    JurisprudenceMetadataEvidence,
    JurisprudenceMetadataRecord,
)

REGISTRO_RE = re.compile(
    r"(?im)^\s*(?:registro(?:\s+digital)?|registro)\s*[:.]?\s*(\d{4,12})\s*$"
)
TESIS_RE = re.compile(r"(?im)^\s*tesis\s*[:.]\s*(?!aislada\s*$)(.+?)\s*$")
RUBRO_RE = re.compile(r"(?im)^\s*(?:rubro|t[ií]tulo)\s*[:.]\s*(.+?)\s*$")
INSTANCIA_RE = re.compile(
    r"(?im)^\s*(?:instancia|tribunal|[oó]rgano)\s*[:.]\s*(.+?)\s*$"
)
MATERIA_RE = re.compile(r"(?im)^\s*materia(?:\(s\))?\s*[:.]\s*(.+?)\s*$")
PUBLICACION_RE = re.compile(
    r"(?im)^\s*(?:publicaci[oó]n|fecha de publicaci[oó]n)\s*[:.]\s*(.+?)\s*$"
)
PUBLICATION_SOURCE_RE = re.compile(
    r"(?im)^\s*(?:fuente|publicado en|medio de publicaci[oó]n)\s*[:.]\s*(.+?)\s*$"
)
EPOCH_RE = re.compile(r"(?im)^\s*[eé]poca\s*[:.]\s*(.+?)\s*$")
TYPE_LABEL_RE = re.compile(r"(?im)^\s*tipo\s*[:.]\s*(.+?)\s*$")
BINDING_FORCE_RE = re.compile(
    r"(?im)^\s*(?:obligatoriedad|car[aá]cter|fuerza obligatoria)\s*[:.]\s*(.+?)\s*$"
)
CRITERION_TEXT_RE = re.compile(
    r"(?ims)^\s*(?:texto|criterio)\s*[:.]\s*(.+?)"
    r"(?=^\s*(?:precedentes?|registro(?:\s+digital)?|tesis|rubro|instancia|materia|"
    r"publicaci[oó]n|[eé]poca|tipo|obligatoriedad|car[aá]cter|fuerza obligatoria)\s*[:.]|\Z)"
)

FACTS_RE = re.compile(
    r"(?ims)^\s*hechos\s*:\s*(.+?)(?=^\s*criterio\s+jur[ií]dico\s*:|\Z)"
)
LEGAL_CRITERION_RE = re.compile(
    r"(?ims)^\s*criterio\s+jur[ií]dico\s*:\s*(.+?)(?=^\s*justificaci[oó]n\s*:|\Z)"
)
JUSTIFICATION_RE = re.compile(
    r"(?ims)^\s*justificaci[oó]n\s*:\s*(.+?)"
    r"(?=^\s*(?:instancia|tesis|fuente|tipo|publicaci[oó]n|precedentes?)\s*:|\Z)"
)
BINDING_EFFECTIVE_DATE_RE = re.compile(
    r"(?i)aplicaci[oó]n\s+obligatoria\s+a\s+partir\s+del\s+"
    r"((?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)?\s*"
    r"\d{1,2}\s+de\s+[a-záéíóúñ]+\s+de\s+\d{4})"
)
BINDING_DECLARATION_RE = re.compile(
    r"(?im)^.*(?:aplicaci[oó]n|car[aá]cter)\s+obligatori[oa].*$"
)
NORMATIVE_REF_RE = re.compile(
    r"(?i)\b(?:art[ií]culo|art\.)\s*(\d+(?:-[A-Z0-9]+)?)"
    r"(?:\s+de(?:l| la)?\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9 ._-]{1,80}))?"
)
ISOLATED_THESIS_TYPE_RE = re.compile(r"(?i)\btesis\s+aislada\b")
JURISPRUDENCE_TYPE_RE = re.compile(r"(?i)\bjurisprudencia\b")
PRECEDENT_TYPE_RE = re.compile(r"(?i)\bprecedente\b")


class _FieldMatch:
    def __init__(self, value: str | None, pages: list[int]) -> None:
        self.value = value
        self.pages = pages


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def _page_matches(
    document: JurisprudenceDocumentRepresentation,
    pattern: re.Pattern[str],
) -> _FieldMatch:
    for page in document.pages:
        match = pattern.search(page.text)
        if match:
            return _FieldMatch(match.group(1).strip(), [page.number])
    return _FieldMatch(None, [])


def _pages_containing_values(
    document: JurisprudenceDocumentRepresentation,
    values: Iterable[str],
) -> list[int]:
    needles = [value for value in values if value]
    return [
        page.number
        for page in document.pages
        if page.has_extractable_text and any(value in page.text for value in needles)
    ]


def _criterion_type_from_label(value: str | None) -> JurisprudenceCriterionType:
    if not value:
        return JurisprudenceCriterionType.UNKNOWN
    if ISOLATED_THESIS_TYPE_RE.search(value):
        return JurisprudenceCriterionType.ISOLATED_THESIS
    if JURISPRUDENCE_TYPE_RE.search(value):
        return JurisprudenceCriterionType.JURISPRUDENCE
    if PRECEDENT_TYPE_RE.search(value):
        return JurisprudenceCriterionType.PRECEDENT
    return JurisprudenceCriterionType.UNKNOWN


def _criterion_type(text: str) -> JurisprudenceCriterionType:
    """Compatibilidad para documentos heredados sin etiqueta Tipo explícita."""
    explicit = _first_match(TYPE_LABEL_RE, text)
    labeled = _criterion_type_from_label(explicit)
    if labeled is not JurisprudenceCriterionType.UNKNOWN:
        return labeled
    if re.search(r"(?im)^\s*tesis\s+aislada\s*$", text):
        return JurisprudenceCriterionType.ISOLATED_THESIS
    if re.search(r"(?im)^\s*jurisprudencia\s*$", text):
        return JurisprudenceCriterionType.JURISPRUDENCE
    if re.search(r"(?im)^\s*precedente\s*$", text):
        return JurisprudenceCriterionType.PRECEDENT
    return JurisprudenceCriterionType.UNKNOWN


def _status(text: str) -> JurisprudenceStatus:
    if re.search(
        r"(?i)\b(?:tesis|criterio|jurisprudencia)\s+"
        r"(?:superad[oa]|sustituid[oa])\b",
        text,
    ) or re.search(r"(?i)\bsuperad[oa]\s+por\s+(?:contradicci[oó]n|criterio)", text):
        return JurisprudenceStatus.SUPERSEDED
    if re.search(
        r"(?i)\b(?:tesis|criterio|jurisprudencia)\s+invalidad[oa]\b|"
        r"\b(?:tesis|criterio|jurisprudencia)\s+sin\s+vigencia\b",
        text,
    ):
        return JurisprudenceStatus.INVALIDATED
    if re.search(
        r"(?i)\b(?:tesis|criterio|jurisprudencia)\s+hist[oó]ric[oa]\b",
        text,
    ):
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
    thesis_number = _first_match(TESIS_RE, text)
    title = _first_match(RUBRO_RE, text)
    court_or_body = _first_match(INSTANCIA_RE, text)
    matter = _first_match(MATERIA_RE, text)
    publication_date_text = _first_match(PUBLICACION_RE, text)
    publication_source = _first_match(PUBLICATION_SOURCE_RE, text)
    epoch = _first_match(EPOCH_RE, text)
    binding_force_text = _first_match(BINDING_FORCE_RE, text)
    if binding_force_text is None:
        declaration = BINDING_DECLARATION_RE.search(text)
        binding_force_text = declaration.group(0).strip() if declaration else None
    binding_effective_date_text = _first_match(BINDING_EFFECTIVE_DATE_RE, text)
    facts_text = _first_match(FACTS_RE, text)
    legal_criterion_text = _first_match(LEGAL_CRITERION_RE, text)
    justification_text = _first_match(JUSTIFICATION_RE, text)
    criterion_text = legal_criterion_text or _first_match(CRITERION_TEXT_RE, text)
    criterion_type = _criterion_type(text)
    status = _status(text)
    related_refs = _normative_refs(text)

    source_pages = _pages_containing_values(
        document,
        (
            identifier or "",
            thesis_number or "",
            title or "",
            court_or_body or "",
            matter or "",
            publication_date_text or "",
            publication_source or "",
            epoch or "",
            binding_force_text or "",
            binding_effective_date_text or "",
            facts_text or "",
            legal_criterion_text or "",
            justification_text or "",
        ),
    )

    warnings: list[str] = []
    if identifier is None:
        warnings.append("No se identificó registro digital.")
    if title is None:
        warnings.append("No se identificó rubro o título explícito.")
    if court_or_body is None:
        warnings.append("No se identificó órgano o instancia.")
    if criterion_type is JurisprudenceCriterionType.UNKNOWN:
        warnings.append("No se determinó el tipo de criterio desde una expresión explícita.")
    if publication_date_text is None:
        warnings.append("No se identificó fecha de publicación.")

    return JurisprudenceExtractedMetadata(
        identifier=identifier,
        thesis_number=thesis_number,
        title=title,
        court_or_body=court_or_body,
        criterion_type=criterion_type,
        publication_date_text=publication_date_text,
        publication_source=publication_source,
        epoch=epoch,
        status=status,
        matter=matter,
        binding_force_text=binding_force_text,
        binding_effective_date_text=binding_effective_date_text,
        facts_text=facts_text,
        legal_criterion_text=legal_criterion_text,
        justification_text=justification_text,
        criterion_text=criterion_text,
        related_normative_refs=related_refs,
        relation_type=NormRelationType.UNKNOWN,
        source_pages=source_pages,
        requires_human_review=True,
        warnings=warnings,
    )


def _append_evidence(
    evidence: list[JurisprudenceMetadataEvidence],
    *,
    field_name: str,
    value: str | None,
    pages: list[int],
    extraction_basis: Literal["explicit_label", "explicit_text_pattern"] = "explicit_label",
) -> None:
    if value is None or not pages:
        return
    evidence.append(
        JurisprudenceMetadataEvidence(
            field_name=field_name,
            value=value,
            source_pages=pages,
            extraction_basis=extraction_basis,
        )
    )


def build_jurisprudence_metadata_record(
    document: JurisprudenceDocumentRepresentation,
    *,
    extracted: JurisprudenceExtractedMetadata,
) -> JurisprudenceMetadataRecord:
    """E.2: enlaza metadatos ya extraídos con su procedencia documental."""
    evidence: list[JurisprudenceMetadataEvidence] = []

    field_patterns: tuple[tuple[str, re.Pattern[str], str | None], ...] = (
        ("identifier", REGISTRO_RE, extracted.identifier),
        ("thesis_number", TESIS_RE, extracted.thesis_number),
        ("title", RUBRO_RE, extracted.title),
        ("court_or_body", INSTANCIA_RE, extracted.court_or_body),
        ("publication_date_text", PUBLICACION_RE, extracted.publication_date_text),
        ("publication_source", PUBLICATION_SOURCE_RE, extracted.publication_source),
        ("epoch", EPOCH_RE, extracted.epoch),
        ("matter", MATERIA_RE, extracted.matter),
        ("binding_force_text", BINDING_FORCE_RE, extracted.binding_force_text),
        (
            "binding_effective_date_text",
            BINDING_EFFECTIVE_DATE_RE,
            extracted.binding_effective_date_text,
        ),
        ("facts_text", FACTS_RE, extracted.facts_text),
        ("legal_criterion_text", LEGAL_CRITERION_RE, extracted.legal_criterion_text),
        ("justification_text", JUSTIFICATION_RE, extracted.justification_text),
        ("criterion_text", LEGAL_CRITERION_RE, extracted.criterion_text),
    )
    for field_name, pattern, value in field_patterns:
        page_match = _page_matches(document, pattern)
        _append_evidence(
            evidence,
            field_name=field_name,
            value=value,
            pages=page_match.pages,
        )

    type_match = _page_matches(document, TYPE_LABEL_RE)
    if extracted.criterion_type is not JurisprudenceCriterionType.UNKNOWN:
        type_pages = type_match.pages or _pages_containing_values(
            document, [extracted.criterion_type.value]
        )
        _append_evidence(
            evidence,
            field_name="criterion_type",
            value=extracted.criterion_type.value,
            pages=type_pages,
            extraction_basis=(
                "explicit_label" if type_match.pages else "explicit_text_pattern"
            ),
        )

    if extracted.related_normative_refs:
        norm_pages = [
            page.number
            for page in document.pages
            if page.has_extractable_text and NORMATIVE_REF_RE.search(page.text)
        ]
        _append_evidence(
            evidence,
            field_name="related_normative_refs",
            value=" | ".join(extracted.related_normative_refs),
            pages=norm_pages,
            extraction_basis="explicit_text_pattern",
        )

    missing_core_fields = [
        field_name
        for field_name, value in (
            ("identifier", extracted.identifier),
            ("title", extracted.title),
            ("court_or_body", extracted.court_or_body),
            (
                "criterion_type",
                None
                if extracted.criterion_type is JurisprudenceCriterionType.UNKNOWN
                else extracted.criterion_type.value,
            ),
            ("publication_date_text", extracted.publication_date_text),
        )
        if value is None
    ]

    return JurisprudenceMetadataRecord(
        document_id=document.document_id,
        original_filename=document.original_filename,
        source_sha256=document.source_sha256,
        extracted=extracted,
        evidence=evidence,
        missing_core_fields=missing_core_fields,
    )


def extract_jurisprudence_metadata_record(
    document: JurisprudenceDocumentRepresentation,
) -> JurisprudenceMetadataRecord:
    """E.2: extrae y traza metadatos sin decidir efectos jurídicos."""
    extracted = extract_jurisprudence_metadata(document)
    return build_jurisprudence_metadata_record(document, extracted=extracted)
