from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.domain.documents import (
    DocumentMetadata,
    ExtractionStats,
    ProcessedDocument,
    SourceType,
)

logger = logging.getLogger(__name__)

MAX_PDF_SIZE_BYTES = 50 * 1024 * 1024
LEGAL_HEADING_RE = re.compile(
    r"^(T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N|SUBSECCI[ÓO]N|LIBRO|PARTE)\b",
    flags=re.IGNORECASE,
)
ARTICLE_RE = re.compile(
    r"^(ART[ÍI]CULO|ART\.)\s+[0-9]+(?:-[A-Z0-9]+)?(?:\s*[A-ZÁÉÍÓÚÑ].*)?$",
    flags=re.IGNORECASE,
)
NUMBERED_HEADING_RE = re.compile(r"^\d+(?:\.\d+){0,4}\s+\S+")


class DocumentPipelineError(RuntimeError):
    """Error base del pipeline documental."""


class InvalidDocumentError(DocumentPipelineError):
    """El archivo de entrada no cumple los requisitos del pipeline."""


class ExtractionError(DocumentPipelineError):
    """No fue posible extraer contenido útil del documento."""


@dataclass(frozen=True)
class ExtractedPage:
    number: int
    text: str


def validate_pdf_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise InvalidDocumentError(f"No existe el archivo: {resolved}")
    if not resolved.is_file():
        raise InvalidDocumentError(f"La ruta no corresponde a un archivo: {resolved}")
    if resolved.suffix.lower() != ".pdf":
        raise InvalidDocumentError("Solo se aceptan archivos PDF.")
    size = resolved.stat().st_size
    if size <= 0:
        raise InvalidDocumentError("El PDF está vacío.")
    if size > MAX_PDF_SIZE_BYTES:
        raise InvalidDocumentError(
            f"El PDF supera el límite de {MAX_PDF_SIZE_BYTES // (1024 * 1024)} MB."
        )
    return resolved


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")
    cleaned_lines: list[str] = []
    previous_blank = False

    for raw_line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if not line:
            if not previous_blank:
                cleaned_lines.append("")
            previous_blank = True
            continue
        cleaned_lines.append(line)
        previous_blank = False

    return "\n".join(cleaned_lines).strip()


def _is_heading(line: str) -> bool:
    if LEGAL_HEADING_RE.match(line) or ARTICLE_RE.match(line) or NUMBERED_HEADING_RE.match(line):
        return True
    if 4 <= len(line) <= 120 and line.isupper() and any(ch.isalpha() for ch in line):
        return True
    return False


def structure_to_markdown(page_text: str) -> tuple[str, int]:
    output: list[str] = []
    heading_count = 0

    for line in normalize_whitespace(page_text).splitlines():
        if not line:
            output.append("")
            continue

        if ARTICLE_RE.match(line):
            output.append(f"### {line}")
            heading_count += 1
        elif LEGAL_HEADING_RE.match(line):
            output.append(f"## {line}")
            heading_count += 1
        elif NUMBERED_HEADING_RE.match(line):
            output.append(f"### {line}")
            heading_count += 1
        elif _is_heading(line):
            output.append(f"## {line}")
            heading_count += 1
        else:
            output.append(line)

    return "\n".join(output).strip(), heading_count


def extract_pdf_pages(path: Path) -> tuple[list[ExtractedPage], str]:
    try:
        reader = PdfReader(str(path))
    except (PdfReadError, OSError, ValueError) as exc:
        raise ExtractionError(f"No fue posible abrir el PDF: {path.name}") from exc

    if len(reader.pages) == 0:
        raise ExtractionError("El PDF no contiene páginas.")

    pages: list[ExtractedPage] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            extracted = page.extract_text() or ""
        except Exception as exc:
            logger.exception("Fallo al extraer la página %s de %s", index, path.name)
            raise ExtractionError(f"Falló la extracción de la página {index}.") from exc
        pages.append(ExtractedPage(number=index, text=extracted))

    from pypdf import __version__ as pypdf_version

    return pages, pypdf_version


def build_markdown(title: str, pages: list[ExtractedPage]) -> tuple[str, int, int]:
    sections: list[str] = [
        f"# {title}",
        "",
        "> Documento normalizado por Tributarius prudens. "
        "El PDF original conserva el valor de fuente y evidencia.",
    ]
    total_headings = 0
    empty_pages = 0

    for page in pages:
        normalized, heading_count = structure_to_markdown(page.text)
        total_headings += heading_count
        if not normalized:
            empty_pages += 1
            normalized = "_[Página sin texto extraíble]_"

        sections.extend(
            [
                "",
                f"<!-- page:{page.number} -->",
                f"## Página {page.number}",
                "",
                normalized,
            ]
        )

    return "\n".join(sections).strip() + "\n", total_headings, empty_pages


def safe_stem(filename: str) -> str:
    stem = Path(filename).stem
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-_.")
    if not stem:
        raise InvalidDocumentError("No fue posible generar un nombre seguro para el documento.")
    return stem.lower()


def process_pdf(
    input_path: Path,
    source_type: SourceType,
    output_dir: Path,
    metadata_dir: Path,
) -> ProcessedDocument:
    source = validate_pdf_path(input_path)
    checksum = sha256_file(source)
    document_id = f"{source_type.value}-{checksum[:16]}"
    stem = safe_stem(source.name)

    output_dir = output_dir.expanduser().resolve()
    metadata_dir = metadata_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = output_dir / f"{stem}.md"
    metadata_path = metadata_dir / f"{stem}.json"

    if markdown_path.exists() or metadata_path.exists():
        raise InvalidDocumentError(
            "Ya existe una salida para este documento. "
            "No se sobrescriben archivos sin intervención explícita."
        )

    pages, extractor_version = extract_pdf_pages(source)
    markdown, heading_count, empty_pages = build_markdown(source.stem, pages)
    extracted_characters = sum(len(normalize_whitespace(page.text)) for page in pages)

    warnings: list[str] = []
    if empty_pages:
        warnings.append(f"{empty_pages} página(s) sin texto extraíble.")
    if extracted_characters == 0:
        raise ExtractionError(
            "No se extrajo texto. El documento puede requerir OCR; "
            "OCR no se ejecuta automáticamente."
        )

    metadata = DocumentMetadata(
        document_id=document_id,
        source_type=source_type,
        original_filename=source.name,
        source_path=str(source),
        normalized_path=str(markdown_path),
        sha256=checksum,
        processed_at_utc=datetime.now(UTC).isoformat(),
        extractor="pypdf",
        extractor_version=extractor_version,
        stats=ExtractionStats(
            page_count=len(pages),
            extracted_characters=extracted_characters,
            empty_pages=empty_pages,
            heading_count=heading_count,
        ),
        warnings=warnings,
    )

    markdown_path.write_text(markdown, encoding="utf-8")
    metadata_path.write_text(
        json.dumps(metadata.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info(
        "Documento procesado: id=%s source_type=%s pages=%s",
        metadata.document_id,
        metadata.source_type.value,
        metadata.stats.page_count,
    )
    return ProcessedDocument(metadata=metadata, markdown=markdown)
