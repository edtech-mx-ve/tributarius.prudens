from __future__ import annotations

import re
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

from app.domain.jurisprudence_document import JurisprudenceDocumentRepresentation
from app.domain.jurisprudence_extraction import JurisprudenceExtractedMetadata
from app.services.document_pipeline import MAX_PDF_SIZE_BYTES, InvalidDocumentError
from app.services.jurisprudence_ingestion import ingest_jurisprudence_pdf
from app.services.jurisprudence_metadata_extraction import extract_jurisprudence_metadata
from app.services.jurisprudence_representation import represent_jurisprudence_document
from app.web.jurisprudence_session import save_web_jurisprudence_session

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


class WebJurisprudenceUploadError(ValueError):
    """La carga jurisprudencial web no cumple los controles requeridos."""


def _safe_pdf_filename(filename: str) -> str:
    clean = Path(filename).name.strip()
    clean = _SAFE_FILENAME_RE.sub("-", clean).strip("-_.")
    if not clean:
        raise WebJurisprudenceUploadError("El archivo requiere un nombre válido.")
    if not clean.lower().endswith(".pdf"):
        raise WebJurisprudenceUploadError("Solo se aceptan archivos PDF.")
    return clean


def process_web_jurisprudence_upload(
    *,
    content: bytes,
    filename: str,
    temp_root: Path | None = None,
) -> tuple[
    str,
    JurisprudenceDocumentRepresentation,
    JurisprudenceExtractedMetadata,
]:
    """Procesa y registra un PDF jurisprudencial dentro de una sesión temporal."""

    if not content:
        raise WebJurisprudenceUploadError("El PDF está vacío.")
    if len(content) > MAX_PDF_SIZE_BYTES:
        raise WebJurisprudenceUploadError(
            f"El PDF supera el límite de {MAX_PDF_SIZE_BYTES // (1024 * 1024)} MB."
        )

    safe_filename = _safe_pdf_filename(filename)
    session_id = uuid4().hex
    base = (temp_root or Path(gettempdir()) / "tributarius-prudens").resolve()
    session_dir = base / session_id
    incoming_dir = session_dir / "incoming"
    incoming_dir.mkdir(parents=True, exist_ok=False)
    pdf_path = incoming_dir / safe_filename
    pdf_path.write_bytes(content)

    try:
        processed = ingest_jurisprudence_pdf(pdf_path, session_dir)
        representation = represent_jurisprudence_document(processed)
        extracted = extract_jurisprudence_metadata(representation)
        save_web_jurisprudence_session(
            session_id=session_id,
            representation=representation,
            metadata=extracted,
            temp_root=base,
        )
    except InvalidDocumentError as exc:
        raise WebJurisprudenceUploadError(str(exc)) from exc

    return session_id, representation, extracted
