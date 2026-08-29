from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

MAX_PDF_BYTES = 50 * 1024 * 1024


class AcquisitionReadinessError(RuntimeError):
    """Raised when acquisition readiness cannot be evaluated safely."""


@dataclass(frozen=True)
class AcquisitionItem:
    document_id: str
    source_url: str
    expected_filename: str
    state: str
    size_bytes: int | None
    sha256: str | None
    detail: str | None


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AcquisitionReadinessError(
            f"No se pudo leer JSON válido: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise AcquisitionReadinessError(
            f"Se esperaba un objeto JSON: {path}"
        )
    return value


def _rows(payload: dict[str, Any], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def _doc_id(row: dict[str, Any]) -> str | None:
    value = row.get("document_id", row.get("id"))
    return value if isinstance(value, str) and value else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_candidate(path: Path) -> tuple[str, int]:
    if not path.is_file():
        raise AcquisitionReadinessError(f"No es archivo regular: {path}")
    size = path.stat().st_size
    if size == 0 or size > MAX_PDF_BYTES:
        raise AcquisitionReadinessError(
            f"Tamaño fuera de rango: {size} bytes"
        )
    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise AcquisitionReadinessError("Firma %PDF- ausente")
    return _sha256(path), size


def build_acquisition_readiness(
    *,
    downloads_dir: Path,
    plan_path: Path,
    evidence_manifest_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    plan = _load_json(plan_path)
    manifest = (
        _load_json(evidence_manifest_path)
        if evidence_manifest_path.exists()
        else {}
    )

    existing = {
        document_id
        for row in _rows(manifest, ("documents", "evidence", "entries"))
        if (document_id := _doc_id(row)) is not None
    }

    plan_rows = _rows(plan, ("documents", "plan", "items"))
    items: list[AcquisitionItem] = []

    for row in plan_rows:
        document_id = _doc_id(row)
        if document_id is None:
            continue
        status = row.get("status")
        source_url = row.get("source_url", row.get("url"))
        if not isinstance(source_url, str):
            source_url = ""
        if status == "exact_binary_verified" or document_id in existing:
            items.append(
                AcquisitionItem(
                    document_id=document_id,
                    source_url=source_url,
                    expected_filename=f"{document_id}.pdf",
                    state="already_available_as_evidence",
                    size_bytes=None,
                    sha256=None,
                    detail=None,
                )
            )
            continue
        if status != "pending_browser_download":
            continue

        path = downloads_dir / f"{document_id}.pdf"
        if not path.exists():
            items.append(
                AcquisitionItem(
                    document_id=document_id,
                    source_url=source_url,
                    expected_filename=path.name,
                    state="missing_download",
                    size_bytes=None,
                    sha256=None,
                    detail=str(path),
                )
            )
            continue

        try:
            sha, size = _validate_candidate(path)
        except AcquisitionReadinessError as exc:
            items.append(
                AcquisitionItem(
                    document_id=document_id,
                    source_url=source_url,
                    expected_filename=path.name,
                    state="invalid_download",
                    size_bytes=path.stat().st_size if path.exists() else None,
                    sha256=None,
                    detail=str(exc),
                )
            )
            continue

        items.append(
            AcquisitionItem(
                document_id=document_id,
                source_url=source_url,
                expected_filename=path.name,
                state="ready_for_batch_import",
                size_bytes=size,
                sha256=sha,
                detail=str(path),
            )
        )

    pending = [
        item.document_id
        for item in items
        if item.state in {"missing_download", "invalid_download"}
    ]
    ready = [
        item.document_id
        for item in items
        if item.state == "ready_for_batch_import"
    ]
    existing_docs = [
        item.document_id
        for item in items
        if item.state == "already_available_as_evidence"
    ]

    report = {
        "sprint": "19I.18J.9.1",
        "status": "ready" if not pending else "incomplete",
        "downloads_dir": str(downloads_dir),
        "already_available_documents": existing_docs,
        "ready_for_batch_import_documents": ready,
        "pending_or_invalid_documents": pending,
        "items": [asdict(item) for item in items],
        "batch_import_allowed": not pending,
        "public_release_allowed": False,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
