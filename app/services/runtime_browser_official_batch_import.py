from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_PDF_BYTES = 50 * 1024 * 1024


class BatchImportError(RuntimeError):
    """Raised when browser evidence cannot be imported safely."""


@dataclass(frozen=True)
class PreparedEvidence:
    document_id: str
    source_url: str
    input_path: str
    sha256: str
    size_bytes: int


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BatchImportError(f"No se pudo leer JSON válido: {path}") from exc
    if not isinstance(value, dict):
        raise BatchImportError(f"Se esperaba un objeto JSON: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_pdf(path: Path) -> tuple[str, int]:
    if not path.is_file():
        raise BatchImportError(f"Falta PDF esperado: {path}")

    size = path.stat().st_size
    if size == 0 or size > MAX_PDF_BYTES:
        raise BatchImportError(f"Tamaño PDF inválido: {path} ({size} bytes)")

    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise BatchImportError(f"El archivo no inicia con %PDF-: {path}")

    return _sha256(path), size


def _registry_entries(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = registry.get("documents", registry.get("entries"))
    if isinstance(raw, list):
        out: dict[str, dict[str, Any]] = {}
        for item in raw:
            if isinstance(item, dict) and isinstance(item.get("document_id"), str):
                out[item["document_id"]] = item
        return out
    if isinstance(raw, dict):
        return {str(k): v for k, v in raw.items() if isinstance(v, dict)}
    raise BatchImportError("Registro oficial sin colección documents/entries utilizable.")


def _plan_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("documents", "plan", "items"):
        value = plan.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    raise BatchImportError("Plan J.8 sin lista documents/plan/items.")


def _manifest_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("documents", "evidence", "entries"):
        value = manifest.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    return []


def _document_id(row: dict[str, Any]) -> str | None:
    for key in ("document_id", "id"):
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _status(row: dict[str, Any]) -> str:
    value = row.get("status")
    return value if isinstance(value, str) else ""


def _official_url(entry: dict[str, Any], document_id: str) -> str:
    urls = entry.get("candidate_urls") or entry.get("source_urls") or []
    if isinstance(urls, str):
        urls = [urls]
    if not urls or not isinstance(urls[0], str):
        raise BatchImportError(f"Sin URL oficial registrada: {document_id}")
    source_url = urls[0]
    if not source_url.startswith("https://www.diputados.gob.mx/"):
        raise BatchImportError(
            f"Autoridad no permitida para lote Cámara: {source_url}"
        )
    return source_url


def _validate_existing_evidence(
    *,
    row: dict[str, Any],
    document_id: str,
    evidence_dir: Path,
    expected_source_url: str,
) -> None:
    evidence_file = row.get("evidence_file")
    expected_sha = row.get("sha256")
    expected_size = row.get("size_bytes")
    source_url = row.get("source_url")

    if source_url != expected_source_url:
        raise BatchImportError(
            f"URL de evidencia existente no coincide con registro: {document_id}"
        )
    if not isinstance(evidence_file, str) or not evidence_file:
        raise BatchImportError(
            f"Evidencia existente sin ruta válida: {document_id}"
        )
    if not isinstance(expected_sha, str) or len(expected_sha) != 64:
        raise BatchImportError(
            f"Evidencia existente sin SHA-256 válido: {document_id}"
        )
    if not isinstance(expected_size, int) or expected_size <= 0:
        raise BatchImportError(
            f"Evidencia existente sin tamaño válido: {document_id}"
        )

    evidence_path = evidence_dir / evidence_file
    actual_sha, actual_size = _validate_pdf(evidence_path)
    if actual_sha != expected_sha.lower() or actual_size != expected_size:
        raise BatchImportError(
            f"Integridad de evidencia existente falló: {document_id}"
        )


def prepare_batch(
    *,
    downloads_dir: Path,
    plan_path: Path,
    registry_path: Path,
    manifest_path: Path,
    evidence_dir: Path | None = None,
) -> tuple[list[PreparedEvidence], list[str], list[str]]:
    """Prepare pending downloads and safely reconcile stale plan entries.

    Returns:
        prepared: pending documents that must be imported now.
        existing_documents: all document IDs already in the manifest.
        skipped_existing_pending: pending IDs from J.8 already present and
            successfully revalidated in the evidence store.
    """
    plan = _load_json(plan_path)
    registry = _registry_entries(_load_json(registry_path))
    manifest = _load_json(manifest_path) if manifest_path.exists() else {}
    manifest_rows = _manifest_rows(manifest)
    existing_rows = {
        document_id: row
        for row in manifest_rows
        if (document_id := _document_id(row)) is not None
    }

    pending_ids = [
        _document_id(row)
        for row in _plan_rows(plan)
        if _status(row) == "pending_browser_download"
    ]
    pending = [x for x in pending_ids if x]
    if not pending:
        raise BatchImportError("J.8 no contiene documentos pending_browser_download.")

    evidence_root = evidence_dir or manifest_path.parent
    skipped_existing_pending: list[str] = []
    prepared: list[PreparedEvidence] = []

    for document_id in pending:
        entry = registry.get(document_id)
        if entry is None:
            raise BatchImportError(f"Documento no registrado: {document_id}")
        source_url = _official_url(entry, document_id)

        existing_row = existing_rows.get(document_id)
        if existing_row is not None:
            _validate_existing_evidence(
                row=existing_row,
                document_id=document_id,
                evidence_dir=evidence_root,
                expected_source_url=source_url,
            )
            skipped_existing_pending.append(document_id)
            continue

        path = downloads_dir / f"{document_id}.pdf"
        sha, size = _validate_pdf(path)
        prepared.append(
            PreparedEvidence(
                document_id=document_id,
                source_url=source_url,
                input_path=str(path),
                sha256=sha,
                size_bytes=size,
            )
        )

    return prepared, sorted(existing_rows), sorted(skipped_existing_pending)


def _write_report(report_path: Path, report: dict[str, Any]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _build_report(
    *,
    status: str,
    prepared: list[PreparedEvidence],
    existing_documents: list[str],
    skipped_existing_pending: list[str],
) -> dict[str, Any]:
    # `preserved_existing_documents` is intentionally retained for backward
    # compatibility with J.9 tests/consumers. It means all pre-existing
    # manifest evidence, not only stale-plan entries skipped in this run.
    return {
        "sprint": "19I.18J.9",
        "status": status,
        "imported_documents": [x.document_id for x in prepared],
        "imported_count": len(prepared),
        "existing_documents": existing_documents,
        "preserved_existing_documents": existing_documents,
        "skipped_existing_pending_documents": skipped_existing_pending,
        "public_release_allowed": False,
        "policy": (
            "La importación en lote acredita integridad de evidencia "
            "descargada manualmente. No acredita por sí sola identidad "
            "con el corpus, vigencia ni derechos de redistribución."
        ),
    }


def import_batch(
    *,
    downloads_dir: Path,
    plan_path: Path,
    registry_path: Path,
    evidence_dir: Path,
    manifest_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    prepared, existing_documents, skipped_existing_pending = prepare_batch(
        downloads_dir=downloads_dir,
        plan_path=plan_path,
        registry_path=registry_path,
        manifest_path=manifest_path,
        evidence_dir=evidence_dir,
    )

    old_manifest = _load_json(manifest_path) if manifest_path.exists() else {}
    old_rows = _manifest_rows(old_manifest)

    if not prepared:
        report = _build_report(
            status="nothing_to_import",
            prepared=prepared,
            existing_documents=existing_documents,
            skipped_existing_pending=skipped_existing_pending,
        )
        _write_report(report_path, report)
        return report

    destination_files = evidence_dir / "files"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix="tp-j9-",
        dir=str(evidence_dir.parent),
    ) as tmp:
        staged_files = Path(tmp) / "files"
        staged_files.mkdir(parents=True)

        for item in prepared:
            src = Path(item.input_path)
            dst = staged_files / f"{item.document_id}.pdf"
            shutil.copyfile(src, dst)
            sha, size = _validate_pdf(dst)
            if sha != item.sha256 or size != item.size_bytes:
                raise BatchImportError(
                    f"Integridad cambió durante staging: {item.document_id}"
                )

        new_rows = list(old_rows)
        for item in prepared:
            new_rows.append(
                {
                    "document_id": item.document_id,
                    "source_url": item.source_url,
                    "sha256": item.sha256,
                    "size_bytes": item.size_bytes,
                    "evidence_file": f"files/{item.document_id}.pdf",
                    "acquisition_method": "manual_browser_official_url",
                }
            )

        destination_files.mkdir(parents=True, exist_ok=True)
        created: list[Path] = []
        try:
            for item in prepared:
                dst = destination_files / f"{item.document_id}.pdf"
                if dst.exists():
                    raise BatchImportError(f"Se rehúsa sobrescribir evidencia: {dst}")
                os.replace(staged_files / dst.name, dst)
                created.append(dst)

            manifest_key = next(
                (
                    key
                    for key in ("documents", "evidence", "entries")
                    if isinstance(old_manifest.get(key), list)
                ),
                "documents",
            )
            new_manifest = dict(old_manifest)
            new_manifest[manifest_key] = new_rows
            tmp_manifest = evidence_dir / ".evidence_manifest.json.tmp"
            tmp_manifest.write_text(
                json.dumps(
                    new_manifest,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            os.replace(tmp_manifest, manifest_path)
        except Exception:
            for path in created:
                path.unlink(missing_ok=True)
            raise

    report = _build_report(
        status="batch_import_completed",
        prepared=prepared,
        existing_documents=existing_documents,
        skipped_existing_pending=skipped_existing_pending,
    )
    _write_report(report_path, report)
    return report
