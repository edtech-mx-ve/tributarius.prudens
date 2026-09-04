from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from app.domain.documents import ProcessedDocument, SourceType
from app.domain.jurisprudence_ingestion import (
    JurisprudenceIngestionReceipt,
    JurisprudenceIngestionResult,
)
from app.services.document_pipeline import (
    InvalidDocumentError,
    process_pdf,
    safe_stem,
    validate_pdf_path,
)
from app.services.legal_chunker import build_chunks, write_chunks_jsonl

_PDF_SIGNATURE_SCAN_BYTES = 1024
_NORMALIZATION_NOTICE_RE = re.compile(
    r"(?m)^> Documento normalizado por Tributarius prudens\. "
    r"El PDF original conserva el valor de fuente y evidencia\.\n?"
)


@dataclass(frozen=True)
class JurisprudenceIngestionPaths:
    """Rutas aisladas para evidencia jurisprudencial aportada en una sesión."""

    root: Path
    normalized_dir: Path
    metadata_dir: Path
    chunks_dir: Path
    ingestion_dir: Path

    @classmethod
    def from_session_dir(cls, session_dir: Path) -> JurisprudenceIngestionPaths:
        root = session_dir.expanduser().resolve() / "jurisprudence"
        return cls(
            root=root,
            normalized_dir=root / "normalized",
            metadata_dir=root / "metadata",
            chunks_dir=root / "chunks",
            ingestion_dir=root / "ingestion",
        )


def _validate_pdf_signature(path: Path) -> None:
    try:
        header = path.read_bytes()[:_PDF_SIGNATURE_SCAN_BYTES]
    except OSError as exc:
        raise InvalidDocumentError("No fue posible leer el PDF jurisprudencial.") from exc
    if b"%PDF-" not in header:
        raise InvalidDocumentError(
            "El archivo no contiene una firma PDF válida en su encabezado."
        )


def _write_ingestion_receipt(
    receipt: JurisprudenceIngestionReceipt,
    *,
    output_path: Path,
) -> Path:
    resolved = output_path.expanduser().resolve()
    if resolved.exists():
        raise InvalidDocumentError(
            "Ya existe un manifiesto de ingesta para este documento en la sesión."
        )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        json.dumps(receipt.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return resolved


def ingest_jurisprudence_pdf_with_trace(
    input_path: Path,
    session_dir: Path,
) -> JurisprudenceIngestionResult:
    """E.1: ingiere, normaliza y segmenta jurisprudencia estrictamente de sesión.

    La ingesta sólo acredita que el archivo aportado fue recibido, extraído y
    preservado con trazabilidad técnica. No acredita autenticidad, vigencia,
    obligatoriedad ni aplicabilidad jurídica y no puede controlar Legal Decision.
    """
    paths = JurisprudenceIngestionPaths.from_session_dir(session_dir)
    source = validate_pdf_path(input_path)
    _validate_pdf_signature(source)
    processed = process_pdf(
        input_path=source,
        source_type=SourceType.JURISPRUDENCIA,
        output_dir=paths.normalized_dir,
        metadata_dir=paths.metadata_dir,
    )
    chunking_markdown = _NORMALIZATION_NOTICE_RE.sub("", processed.markdown)
    chunks, report = build_chunks(chunking_markdown, processed.metadata)
    stem = safe_stem(processed.metadata.original_filename)
    write_chunks_jsonl(chunks, paths.chunks_dir / f"{stem}.jsonl")

    receipt = JurisprudenceIngestionReceipt(
        jurisprudence_document_id=processed.metadata.document_id,
        original_filename=processed.metadata.original_filename,
        source_sha256=processed.metadata.sha256,
        text_extracted=processed.metadata.stats.extracted_characters > 0,
        extracted_characters=processed.metadata.stats.extracted_characters,
        page_count=processed.metadata.stats.page_count,
        chunk_count=report.chunk_count,
        processed_at_utc=processed.metadata.processed_at_utc,
        warnings=list(processed.metadata.warnings),
    )
    _write_ingestion_receipt(
        receipt,
        output_path=paths.ingestion_dir / f"{stem}.json",
    )

    return JurisprudenceIngestionResult(
        document=processed,
        chunks=chunks,
        chunking_report=report,
        receipt=receipt,
    )


def ingest_jurisprudence_pdf(
    input_path: Path,
    session_dir: Path,
) -> ProcessedDocument:
    """Compatibilidad histórica: conserva el retorno ProcessedDocument.

    Internamente ejecuta el contrato completo E.1, incluido chunking y manifiesto
    de ingesta, sin registrar la jurisprudencia en el corpus permanente.
    """
    return ingest_jurisprudence_pdf_with_trace(input_path, session_dir).document
