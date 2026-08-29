from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from app.services.runtime_official_source_audit import OfficialSourceAuditError

_MAX_DEFAULT_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class BrowserEvidenceItem:
    document_id: str
    source_url: str
    evidence_file: str
    sha256: str
    size_bytes: int
    acquisition_method: str


@dataclass(frozen=True)
class BrowserEvidenceImportSummary:
    imported_documents: tuple[str, ...]
    output_dir: str
    manifest_path: str
    items: tuple[BrowserEvidenceItem, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OfficialSourceAuditError(f"No se pudo leer JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise OfficialSourceAuditError(f"{path} debe contener un objeto JSON.")
    return payload


def _candidate_urls(registry_path: Path) -> dict[str, tuple[str, ...]]:
    payload = _read_json(registry_path)
    raw = payload.get("documents")
    if not isinstance(raw, list):
        raise OfficialSourceAuditError("Campo documents inválido.")
    result: dict[str, tuple[str, ...]] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise OfficialSourceAuditError("Entrada documents inválida.")
        document_id = item.get("document_id")
        urls = item.get("candidate_urls")
        if not isinstance(document_id, str) or not document_id:
            raise OfficialSourceAuditError("document_id inválido.")
        if not isinstance(urls, list) or not urls or not all(
            isinstance(url, str) and url.startswith("https://") for url in urls
        ):
            raise OfficialSourceAuditError(
                f"candidate_urls inválido para {document_id}."
            )
        result[document_id] = tuple(urls)
    return result


def import_browser_downloaded_official_pdf(
    *,
    document_id: str,
    input_pdf: Path,
    output_dir: Path,
    registry_path: Path,
    max_bytes: int = _MAX_DEFAULT_BYTES,
) -> BrowserEvidenceImportSummary:
    if max_bytes <= 0:
        raise OfficialSourceAuditError("max_bytes debe ser positivo.")
    candidates = _candidate_urls(registry_path)
    if document_id not in candidates:
        raise OfficialSourceAuditError(
            f"document_id no permitido: {document_id}"
        )
    if not input_pdf.is_file():
        raise OfficialSourceAuditError(f"PDF inexistente: {input_pdf}")

    size = input_pdf.stat().st_size
    if size <= 4 or size > max_bytes:
        raise OfficialSourceAuditError(
            f"Tamaño PDF inválido para {document_id}: {size} bytes."
        )
    with input_pdf.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise OfficialSourceAuditError(
                f"El archivo de {document_id} no inicia con %PDF-."
            )

    files_dir = output_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    destination = files_dir / f"{document_id}.pdf"
    if destination.exists():
        raise OfficialSourceAuditError(
            f"Ya existe evidencia para {document_id}: {destination}"
        )

    source_sha = _sha256(input_pdf)
    shutil.copyfile(input_pdf, destination)
    if _sha256(destination) != source_sha:
        destination.unlink(missing_ok=True)
        raise OfficialSourceAuditError(
            f"Fallo de integridad al copiar {document_id}."
        )

    item = BrowserEvidenceItem(
        document_id=document_id,
        source_url=candidates[document_id][0],
        evidence_file=f"files/{document_id}.pdf",
        sha256=source_sha,
        size_bytes=size,
        acquisition_method="manual_browser_official_url",
    )

    manifest_path = output_dir / "evidence_manifest.json"
    existing: list[dict[str, object]] = []
    if manifest_path.exists():
        manifest = _read_json(manifest_path)
        raw_items = manifest.get("documents")
        if not isinstance(raw_items, list):
            destination.unlink(missing_ok=True)
            raise OfficialSourceAuditError(
                "Manifest existente: campo documents inválido."
            )
        existing = [dict(entry) for entry in raw_items if isinstance(entry, dict)]
        if len(existing) != len(raw_items):
            destination.unlink(missing_ok=True)
            raise OfficialSourceAuditError(
                "Manifest existente contiene entradas inválidas."
            )

    if any(entry.get("document_id") == document_id for entry in existing):
        destination.unlink(missing_ok=True)
        raise OfficialSourceAuditError(
            f"Manifest ya contiene {document_id}."
        )

    existing.append(asdict(item))
    existing.sort(key=lambda entry: str(entry.get("document_id", "")))
    manifest_payload = {
        "schema_version": "1.0",
        "acquisition_mode": "browser_manual_official_url",
        "documents": existing,
    }
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return BrowserEvidenceImportSummary(
        imported_documents=(document_id,),
        output_dir=str(output_dir),
        manifest_path=str(manifest_path),
        items=(item,),
    )
