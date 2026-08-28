from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.jurisprudence import JurisprudenceMetadata

_MAX_METADATA_BYTES = 5 * 1024 * 1024


class JurisprudenceMetadataError(ValueError):
    pass


def load_jurisprudence_metadata(path: Path) -> dict[str, JurisprudenceMetadata]:
    if path.suffix.lower() != ".jsonl":
        raise JurisprudenceMetadataError("Los metadatos deben usar formato JSONL.")
    if not path.is_file():
        raise JurisprudenceMetadataError("No se encontró el archivo de metadatos.")
    if path.stat().st_size > _MAX_METADATA_BYTES:
        raise JurisprudenceMetadataError("Los metadatos exceden 5 MiB.")

    records: dict[str, JurisprudenceMetadata] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise JurisprudenceMetadataError("No fue posible leer los metadatos.") from exc

    for line_number, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
            metadata = JurisprudenceMetadata.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise JurisprudenceMetadataError(
                f"Metadato jurisprudencial inválido en línea {line_number}."
            ) from exc
        if metadata.document_id in records:
            raise JurisprudenceMetadataError(
                f"document_id duplicado en línea {line_number}."
            )
        records[metadata.document_id] = metadata

    if not records:
        raise JurisprudenceMetadataError("El archivo de metadatos está vacío.")
    return records
