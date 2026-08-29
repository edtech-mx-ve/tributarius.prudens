from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.legal_chunks import LegalUnitType

_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
_PAGE_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:p[aá]gina|page)\s+(\d+)\s*$",
    re.IGNORECASE,
)
_ARTICLE_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(art[ií]culo|art\.)\s+"
    r"("
    r"[0-9]+o?"
    r"(?:\s*-\s*[A-ZÁÉÍÓÚÑ0-9]+)*"
    r"(?:\s+(?:BIS|TER|QU[AÁ]TER))?"
    r")"
    r"\s*(?:\.-|\.|:|—|–|-(?![A-ZÁÉÍÓÚÑ0-9])|$)",
    re.IGNORECASE,
)
_RULE_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?"
    r"((?:\d+\.){2,5}\d+)\.?\s+",
    re.IGNORECASE,
)
_STRUCTURAL_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?"
    r"(t[ií]tulo|cap[ií]tulo|secci[oó]n|subsecci[oó]n)\s+(.+?)\s*$",
    re.IGNORECASE,
)
_ROMAN_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(I|II|III|IV|V|VI|VII)\.\s+(.+?)\s*$"
)

_UNAM_ORDER = ("I", "II", "III", "IV", "V", "VI", "VII")
_UNAM_FIRST_LINE_PREFIX = {
    "I": "PRINCIPIOS CONSTITUCIONALES",
    "II": "LA INTERPRETACION DE LA NORMA",
    "III": "LOS TRIBUTOS Y SUS ELEMENTOS",
    "IV": "SUJETOS DE LA OBLIGACION TRIBUTARIA",
    "V": "EL CALCULO DE LAS CONTRIBUCIONES",
    "VI": "FORMAS DE EXTINCION DE LA DEUDA",
    "VII": "EL INCUMPLIMIENTO",
}


@dataclass(frozen=True, slots=True)
class StructuredUnit:
    unit_type: LegalUnitType
    label: str
    text: str
    hierarchy: tuple[str, ...] = ()
    page_start: int | None = None
    page_end: int | None = None
    used_fallback: bool = False


def _clean_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _ascii_upper(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ascii", "ignore").decode("ascii").upper()


def _uppercase_ratio(value: str) -> float:
    letters = [char for char in value if char.isalpha()]
    if not letters:
        return 0.0
    return sum(char.isupper() for char in letters) / len(letters)


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9_.:-]+", "-", ascii_text).strip("-").lower()
    return slug or hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def stable_chunk_id(
    canonical_id: str,
    unit_type: LegalUnitType,
    label: str,
    text: str,
    *,
    ordinal: int = 1,
) -> str:
    if ordinal < 1:
        raise ValueError("ordinal debe ser >= 1")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"{canonical_id}:{unit_type.value}:{_slug(label)}:{ordinal:05d}:{digest}"


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _current_page(line: str, current: int | None) -> int | None:
    match = _PAGE_RE.match(line)
    return int(match.group(1)) if match else current


def _is_unam_chapter_start(line: str, numeral: str) -> bool:
    match = _ROMAN_RE.match(line)
    if match is None or match.group(1) != numeral:
        return False

    title = match.group(2).strip()
    normalized = _ascii_upper(title)

    # El índice usa capitalización normal; los encabezados reales del cuerpo
    # están en versales. Además, exigimos el prefijo real de cada capítulo.
    return (
        _uppercase_ratio(title) >= 0.85
        and normalized.startswith(_UNAM_FIRST_LINE_PREFIX[numeral])
    )


def _find_unam_chapter_starts(lines: list[str]) -> list[tuple[int, str]]:
    starts: list[tuple[int, str]] = []
    search_from = 0

    for numeral in _UNAM_ORDER:
        found: tuple[int, str] | None = None
        for index in range(search_from, len(lines)):
            if _is_unam_chapter_start(lines[index], numeral):
                found = (index, numeral)
                break
        if found is None:
            return []
        starts.append(found)
        search_from = found[0] + 1

    return starts


def _collect_unam_title(lines: list[str], start: int) -> str:
    match = _ROMAN_RE.match(lines[start])
    if match is None:
        raise ValueError("Inicio de capítulo UNAM inválido.")

    parts = [match.group(2).strip()]
    for offset in range(1, 3):
        index = start + offset
        if index >= len(lines):
            break
        candidate = lines[index].strip()
        if not candidate or _ROMAN_RE.match(candidate) or _PAGE_RE.match(candidate):
            break
        # Solo agrega continuación del título si permanece claramente en versales.
        if _uppercase_ratio(candidate) < 0.80:
            break
        parts.append(candidate)

    return _clean_line(" ".join(parts))


def _structure_unam_chapters(text: str) -> list[StructuredUnit]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    starts = _find_unam_chapter_starts(lines)
    if len(starts) != 7:
        return []

    page_at_line: list[int | None] = []
    page: int | None = None
    for line in lines:
        page = _current_page(line, page)
        page_at_line.append(page)

    units: list[StructuredUnit] = []
    for position, (start, numeral) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        body = "\n".join(lines[start:end]).strip()
        if not body:
            return []

        title = _collect_unam_title(lines, start)
        page_start = page_at_line[start]
        page_end = page_at_line[end - 1] if end > start else page_start

        units.append(
            StructuredUnit(
                unit_type=LegalUnitType.ACADEMIC_CHAPTER,
                label=f"Capítulo {numeral} — {title}",
                text=body,
                hierarchy=(f"Capítulo {numeral}",),
                page_start=page_start,
                page_end=page_end,
                used_fallback=False,
            )
        )
    return units


def _detect_boundary(line: str, profile: str) -> tuple[LegalUnitType, str] | None:
    if profile == "administrative_rule":
        rule = _RULE_RE.match(line)
        if rule:
            return LegalUnitType.ADMINISTRATIVE_RULE, rule.group(1).rstrip(".")

    if profile == "legal_article":
        article = _ARTICLE_RE.match(line)
        if article:
            return LegalUnitType.ARTICLE, f"Artículo {article.group(2).strip()}"

    return None


def _heading_label(line: str) -> str | None:
    heading = _HEADING_RE.match(line)
    if heading:
        return _clean_line(heading.group(2))
    structural = _STRUCTURAL_RE.match(line)
    if structural:
        return _clean_line(f"{structural.group(1)} {structural.group(2)}")
    return None


def structure_document(text: str, *, profile: str) -> list[StructuredUnit]:
    if not text or not text.strip():
        raise ValueError("El documento normalizado está vacío.")

    if profile == "academic_chapter":
        academic_units = _structure_unam_chapters(text)
        if academic_units:
            return academic_units

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    units: list[StructuredUnit] = []
    hierarchy: list[str] = []
    buffer: list[str] = []
    current_type: LegalUnitType | None = None
    current_label: str | None = None
    start_page: int | None = None
    current_page: int | None = None
    structured_found = False

    def flush(end_page: int | None) -> None:
        nonlocal buffer, current_type, current_label, start_page
        body = "\n".join(buffer).strip()
        if current_type is not None and current_label is not None and body:
            units.append(
                StructuredUnit(
                    unit_type=current_type,
                    label=current_label,
                    text=body,
                    hierarchy=tuple(hierarchy),
                    page_start=start_page,
                    page_end=end_page,
                    used_fallback=False,
                )
            )
        buffer = []
        current_type = None
        current_label = None
        start_page = None

    for raw_line in lines:
        page_before = current_page
        current_page = _current_page(raw_line, current_page)
        boundary = _detect_boundary(raw_line, profile)

        if boundary:
            structured_found = True
            if current_type is not None:
                flush(page_before or current_page)
            current_type, current_label = boundary
            start_page = current_page
            buffer = [raw_line]
            continue

        heading = _heading_label(raw_line)
        if heading and current_type is None:
            if len(hierarchy) >= 6:
                hierarchy.pop(0)
            hierarchy.append(heading)

        if current_type is not None:
            buffer.append(raw_line)

    if current_type is not None:
        flush(current_page)

    if structured_found and units:
        return units

    units = _structure_by_headings(text)
    if units:
        return units

    return [
        StructuredUnit(
            unit_type=LegalUnitType.STRUCTURAL_SECTION,
            label="Documento completo",
            text=text.strip(),
            used_fallback=True,
        )
    ]


def _structure_by_headings(text: str) -> list[StructuredUnit]:
    lines = text.splitlines()
    boundaries: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        label = _heading_label(line)
        if label:
            boundaries.append((index, label))

    if not boundaries:
        return []

    units: list[StructuredUnit] = []
    for pos, (start, label) in enumerate(boundaries):
        end = boundaries[pos + 1][0] if pos + 1 < len(boundaries) else len(lines)
        body = "\n".join(lines[start:end]).strip()
        if body:
            units.append(
                StructuredUnit(
                    unit_type=LegalUnitType.STRUCTURAL_SECTION,
                    label=label,
                    text=body,
                    hierarchy=(label,),
                    used_fallback=True,
                )
            )
    return units


def structure_prodecon_sections(
    sections: Iterable[tuple[str, str, int | None, int | None]],
) -> list[StructuredUnit]:
    result: list[StructuredUnit] = []
    for label, text, page_start, page_end in sections:
        if not text.strip():
            continue
        result.append(
            StructuredUnit(
                unit_type=LegalUnitType.PRODECON_SECTION,
                label=label,
                text=text.strip(),
                hierarchy=(label,),
                page_start=page_start,
                page_end=page_end,
                used_fallback=False,
            )
        )
    if not result:
        raise ValueError("PRODECON no contiene secciones utilizables.")
    return result
