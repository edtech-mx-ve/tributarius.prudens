from __future__ import annotations

import json
import re
from pathlib import Path
from tempfile import gettempdir

from app.domain.jurisprudence_document import JurisprudenceDocumentRepresentation
from app.domain.jurisprudence_extraction import JurisprudenceExtractedMetadata
from app.domain.jurisprudence_ingestion import JurisprudenceIngestionReceipt
from app.domain.jurisprudence_metadata import JurisprudenceMetadataRecord
from app.domain.jurisprudence_normative_relations import JurisprudenceNormativeRelationRecord
from app.domain.jurisprudence_ratio import JurisprudenceRatioRecord
from app.domain.jurisprudence_temporal import JurisprudenceTemporalRecord

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
    ingestion_receipt: JurisprudenceIngestionReceipt | None = None,
    metadata_record: JurisprudenceMetadataRecord | None = None,
    normative_relation_record: JurisprudenceNormativeRelationRecord | None = None,
    temporal_record: JurisprudenceTemporalRecord | None = None,
    ratio_record: JurisprudenceRatioRecord | None = None,
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
        "ingestion_receipt": (
            ingestion_receipt.model_dump(mode="json")
            if ingestion_receipt is not None
            else None
        ),
        "metadata_record": (
            metadata_record.model_dump(mode="json")
            if metadata_record is not None
            else None
        ),
        "normative_relation_record": (
            normative_relation_record.model_dump(mode="json")
            if normative_relation_record is not None
            else None
        ),
        "temporal_record": (
            temporal_record.model_dump(mode="json")
            if temporal_record is not None
            else None
        ),
        "ratio_record": (
            ratio_record.model_dump(mode="json")
            if ratio_record is not None
            else None
        ),
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


def load_web_jurisprudence_ingestion_receipt(
    session_id: str,
    *,
    temp_root: Path | None = None,
) -> JurisprudenceIngestionReceipt | None:
    """Recupera la trazabilidad E.1 sin alterar el contrato histórico de sesión."""
    clean_id = validate_session_id(session_id)
    manifest = _session_root(temp_root) / clean_id / _MANIFEST_NAME
    if not manifest.exists() or not manifest.is_file():
        raise WebJurisprudenceSessionError(
            "La sesión jurisprudencial no existe o ya no está disponible."
        )
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        raw_receipt = payload.get("ingestion_receipt")
        if raw_receipt is None:
            return None
        return JurisprudenceIngestionReceipt.model_validate(raw_receipt)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise WebJurisprudenceSessionError(
            "La trazabilidad de ingesta jurisprudencial está dañada."
        ) from exc


def load_web_jurisprudence_metadata_record(
    session_id: str,
    *,
    temp_root: Path | None = None,
) -> JurisprudenceMetadataRecord | None:
    """Recupera la trazabilidad E.2 sin alterar el contrato histórico de sesión."""
    clean_id = validate_session_id(session_id)
    manifest = _session_root(temp_root) / clean_id / _MANIFEST_NAME
    if not manifest.exists() or not manifest.is_file():
        raise WebJurisprudenceSessionError(
            "La sesión jurisprudencial no existe o ya no está disponible."
        )
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        raw_record = payload.get("metadata_record")
        if raw_record is None:
            return None
        return JurisprudenceMetadataRecord.model_validate(raw_record)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise WebJurisprudenceSessionError(
            "La trazabilidad de metadatos jurisprudenciales está dañada."
        ) from exc


def load_web_jurisprudence_normative_relation_record(
    session_id: str,
    *,
    temp_root: Path | None = None,
) -> JurisprudenceNormativeRelationRecord | None:
    """Recupera la trazabilidad E.3 sin promoverla a evidencia aplicable."""
    clean_id = validate_session_id(session_id)
    manifest = _session_root(temp_root) / clean_id / _MANIFEST_NAME
    if not manifest.exists() or not manifest.is_file():
        raise WebJurisprudenceSessionError(
            "La sesión jurisprudencial no existe o ya no está disponible."
        )
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        raw_record = payload.get("normative_relation_record")
        if raw_record is None:
            return None
        return JurisprudenceNormativeRelationRecord.model_validate(raw_record)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise WebJurisprudenceSessionError(
            "La trazabilidad de relaciones normativas jurisprudenciales está dañada."
        ) from exc


def load_web_jurisprudence_temporal_record(
    session_id: str,
    *,
    temp_root: Path | None = None,
) -> JurisprudenceTemporalRecord | None:
    """Recupera el perfil temporal E.4 sin promoverlo a aplicabilidad jurídica."""
    clean_id = validate_session_id(session_id)
    manifest = _session_root(temp_root) / clean_id / _MANIFEST_NAME
    if not manifest.exists() or not manifest.is_file():
        raise WebJurisprudenceSessionError(
            "La sesión jurisprudencial no existe o ya no está disponible."
        )
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        raw_record = payload.get("temporal_record")
        if raw_record is None:
            return None
        return JurisprudenceTemporalRecord.model_validate(raw_record)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise WebJurisprudenceSessionError(
            "La trazabilidad temporal jurisprudencial está dañada."
        ) from exc


def load_web_jurisprudence_ratio_record(
    session_id: str,
    *,
    temp_root: Path | None = None,
) -> JurisprudenceRatioRecord | None:
    """Recupera la estructura E.5 Hechos/Criterio/Justificación de la sesión."""
    clean_id = validate_session_id(session_id)
    manifest = _session_root(temp_root) / clean_id / _MANIFEST_NAME
    if not manifest.exists() or not manifest.is_file():
        raise WebJurisprudenceSessionError(
            "La sesión jurisprudencial no existe o ya no está disponible."
        )
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        raw_record = payload.get("ratio_record")
        if raw_record is None:
            return None
        return JurisprudenceRatioRecord.model_validate(raw_record)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise WebJurisprudenceSessionError(
            "La trazabilidad de ratio decidendi jurisprudencial está dañada."
        ) from exc
