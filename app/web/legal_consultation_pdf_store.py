from __future__ import annotations

import json
import re
from pathlib import Path
from tempfile import gettempdir

from pydantic import ValidationError

from app.domain.legal_consultation_pdf_artifact import (
    LegalConsultationPdfArtifact,
)

_EXECUTION_ID_RE = re.compile(
    r"^TP-[A-F0-9]{32}$"
)

_MANIFEST_NAME = "manifest.json"
_PDF_NAME = "report.pdf"
_MAX_PDF_BYTES = 10 * 1024 * 1024


class WebLegalConsultationPdfStoreError(ValueError):
    """G.12: artefacto PDF temporal invalido o no disponible."""


def _artifact_root(
    temp_root: Path | None = None,
) -> Path:
    base = (
        temp_root
        if temp_root is not None
        else Path(gettempdir()) / "tributarius-prudens"
    )

    return (
        base / "legal-consultation-pdfs"
    ).resolve()


def validate_execution_id(
    execution_id: str,
) -> str:
    clean = execution_id.strip().upper()

    if not _EXECUTION_ID_RE.fullmatch(clean):
        raise WebLegalConsultationPdfStoreError(
            "Execution ID de consulta invalido."
        )

    return clean


def save_web_legal_consultation_pdf_artifact(
    artifact: LegalConsultationPdfArtifact,
    *,
    temp_root: Path | None = None,
) -> Path:
    execution_id = validate_execution_id(
        artifact.execution_id
    )

    if artifact.content_length > _MAX_PDF_BYTES:
        raise WebLegalConsultationPdfStoreError(
            "El PDF excede el tamano temporal permitido."
        )

    artifact_dir = (
        _artifact_root(temp_root) / execution_id
    )

    artifact_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    pdf_path = artifact_dir / _PDF_NAME
    manifest_path = artifact_dir / _MANIFEST_NAME

    pdf_path.write_bytes(artifact.pdf_bytes)

    manifest = artifact.model_dump(
        mode="json",
        exclude={"pdf_bytes"},
    )

    manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    return pdf_path


def load_web_legal_consultation_pdf_artifact(
    execution_id: str,
    *,
    temp_root: Path | None = None,
) -> LegalConsultationPdfArtifact:
    clean_id = validate_execution_id(
        execution_id
    )

    artifact_dir = (
        _artifact_root(temp_root) / clean_id
    )

    pdf_path = artifact_dir / _PDF_NAME
    manifest_path = artifact_dir / _MANIFEST_NAME

    if (
        not pdf_path.is_file()
        or not manifest_path.is_file()
    ):
        raise WebLegalConsultationPdfStoreError(
            "El PDF de la consulta no existe o ya no esta disponible."
        )

    try:
        pdf_bytes = pdf_path.read_bytes()

        if (
            len(pdf_bytes) <= 0
            or len(pdf_bytes) > _MAX_PDF_BYTES
        ):
            raise WebLegalConsultationPdfStoreError(
                "El PDF temporal tiene tamano invalido."
            )

        payload = json.loads(
            manifest_path.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(payload, dict):
            raise WebLegalConsultationPdfStoreError(
                "El manifiesto PDF temporal es invalido."
            )

        payload["pdf_bytes"] = pdf_bytes

        return LegalConsultationPdfArtifact.model_validate(
            payload
        )

    except (
        OSError,
        json.JSONDecodeError,
        ValidationError,
    ) as exc:
        raise WebLegalConsultationPdfStoreError(
            "El PDF temporal esta danado."
        ) from exc
