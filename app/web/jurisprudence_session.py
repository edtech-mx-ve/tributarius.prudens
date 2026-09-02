from __future__ import annotations

import json
import re
from pathlib import Path
from tempfile import gettempdir

from app.domain.jurisprudence_document import JurisprudenceDocumentRepresentation
from app.domain.jurisprudence_extraction import JurisprudenceExtractedMetadata

_SESSION_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_MANIFEST_NAME = "session-jurisprudence.json"


class WebJurisprudenceSessionError(ValueError):
    """La sesión jurisprudencial temporal no es válida o no puede recuperarse."""


def _session_root(temp_root: Path | None = None) -> Path:
    return (temp_root or Path(gettempdir()) / "tributarius-prudens").resolve()


def validate_session_id(session_id: str) -> str:
    clean = session_id.strip().lower()
    if not _SESSION_ID_RE.fullmatch(clean):
        raise WebJurisprudenceSessionError("Identificador de sesión jurisprudencial inválido.")
    return clean


def save_web_jurisprudence_session(
    *,
    session_id: str,
    representation: JurisprudenceDocumentRepresentation,
    metadata: JurisprudenceExtractedMetadata,
    temp_root: Path | None = None,
) -> Path:
    clean_id = validate_session_id(session_id)
    session_dir = _session_root(temp_root) / clean_id
    if not session_dir.exists() or not session_dir.is_dir():
        raise WebJurisprudenceSessionError("La sesión jurisprudencial no existe.")

    manifest = session_dir / _MANIFEST_NAME
    payload = {
        "session_id": clean_id,
        "representation": representation.model_dump(mode="json"),
        "metadata": metadata.model_dump(mode="json"),
    }
    manifest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def load_web_jurisprudence_session(
    session_id: str,
    *,
    temp_root: Path | None = None,
) -> tuple[JurisprudenceDocumentRepresentation, JurisprudenceExtractedMetadata]:
    clean_id = validate_session_id(session_id)
    manifest = _session_root(temp_root) / clean_id / _MANIFEST_NAME
    if not manifest.exists() or not manifest.is_file():
        raise WebJurisprudenceSessionError(
            "La sesión jurisprudencial no existe o ya no está disponible."
        )

    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        representation = JurisprudenceDocumentRepresentation.model_validate(
            payload["representation"]
        )
        metadata = JurisprudenceExtractedMetadata.model_validate(payload["metadata"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise WebJurisprudenceSessionError(
            "La sesión jurisprudencial temporal está dañada."
        ) from exc

    return representation, metadata
