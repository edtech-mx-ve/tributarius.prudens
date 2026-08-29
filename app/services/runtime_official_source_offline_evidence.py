from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

from app.services.runtime_official_source_audit import (
    OfficialSourceAuditError,
    fetch_official_pdf,
)


@dataclass(frozen=True)
class EvidenceRecord:
    document_id: str
    source_url: str
    final_url: str
    filename: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class OfflineEvidenceDocumentResult:
    document_id: str
    local_source_sha256: str
    evidence_sha256: str | None
    source_url: str | None
    evidence_file: str | None
    evidence_integrity_ok: bool
    exact_local_hash_match: bool
    official_provenance_verified: bool
    blocked_reason: str | None


@dataclass(frozen=True)
class OfflineEvidenceAuditSummary:
    candidate_documents: int
    evidence_records: int
    verified_documents: tuple[str, ...]
    blocked_documents: tuple[str, ...]
    missing_evidence_documents: tuple[str, ...]
    promotion_ready_documents: tuple[str, ...]
    public_release_allowed: bool
    documents: tuple[OfflineEvidenceDocumentResult, ...]


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _read_json_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OfficialSourceAuditError(f"No se pudo leer JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise OfficialSourceAuditError(f"{path} debe contener un objeto JSON.")
    return payload


def _validate_https_authority_url(url: str, allowed_hosts: set[str]) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme.lower() != "https":
        raise OfficialSourceAuditError(f"URL no HTTPS: {url}")
    if host not in allowed_hosts:
        raise OfficialSourceAuditError(f"Host no permitido: {url}")


def _safe_filename(filename: str) -> str:
    candidate = Path(filename)
    if (
        not filename
        or candidate.name != filename
        or candidate.is_absolute()
        or ".." in candidate.parts
        or "\\" in filename
        or "/" in filename
    ):
        raise OfficialSourceAuditError(f"Nombre de archivo inseguro: {filename}")
    return filename


def acquire_official_evidence_bundle(
    *,
    candidate_registry_path: Path,
    output_dir: Path,
    timeout_seconds: int = 45,
    max_bytes: int = 50 * 1024 * 1024,
    document_ids: Iterable[str] | None = None,
) -> Path:
    registry = _read_json_object(candidate_registry_path)
    raw_hosts = registry.get("allowed_authority_hosts")
    raw_documents = registry.get("documents")
    if not isinstance(raw_hosts, list) or not all(
        isinstance(item, str) and item for item in raw_hosts
    ):
        raise OfficialSourceAuditError("allowed_authority_hosts inválido.")
    if not isinstance(raw_documents, list):
        raise OfficialSourceAuditError("documents inválido.")
    allowed_hosts = {item.lower() for item in raw_hosts}

    selected = set(document_ids or [])
    records: list[EvidenceRecord] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir = output_dir / "files"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    for raw in raw_documents:
        if not isinstance(raw, dict):
            raise OfficialSourceAuditError("Entrada candidata inválida.")
        document_id = raw.get("document_id")
        urls = raw.get("candidate_urls")
        if not isinstance(document_id, str) or not document_id:
            raise OfficialSourceAuditError("document_id inválido.")
        if selected and document_id not in selected:
            continue
        if not isinstance(urls, list) or not urls or not all(
            isinstance(url, str) and url for url in urls
        ):
            raise OfficialSourceAuditError(
                f"candidate_urls inválido para {document_id}."
            )

        acquired = None
        last_error: OfficialSourceAuditError | None = None
        for url in urls:
            _validate_https_authority_url(url, allowed_hosts)
            try:
                artifact = fetch_official_pdf(
                    url,
                    allowed_hosts,
                    timeout_seconds,
                    max_bytes,
                )
            except OfficialSourceAuditError as exc:
                last_error = exc
                continue
            acquired = artifact
            break

        if acquired is None:
            if last_error is not None:
                print(f"WARN {document_id}: {last_error}")
            continue

        filename = _safe_filename(f"{document_id}.pdf")
        target = evidence_dir / filename

        # Descarga nuevamente de forma explícita al archivo destino usando urllib
        # no es necesaria: fetch_official_pdf solo devuelve hash. Para preservar
        # bytes, el adquirente copia desde una descarga temporal propia.
        # Se reutiliza un helper local seguro para no cambiar la API de 19I.18J.
        import ssl
        from urllib.request import Request, urlopen

        request = Request(
            acquired.final_url,
            headers={
                "User-Agent": "Tributarius-Prudens/19I.18J.2",
                "Accept": "application/pdf,*/*;q=0.8",
                "Accept-Encoding": "identity",
                "Connection": "close",
            },
        )
        context = ssl.create_default_context()
        digest = hashlib.sha256()
        size = 0
        prefix = b""
        tmp = target.with_suffix(".pdf.tmp")
        try:
            with urlopen(
                request,
                timeout=timeout_seconds,
                context=context,
            ) as response, tmp.open("wb") as handle:
                final_url = response.geturl()
                _validate_https_authority_url(final_url, allowed_hosts)
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    if not prefix:
                        prefix = block[:5]
                    size += len(block)
                    if size > max_bytes:
                        raise OfficialSourceAuditError(
                            f"PDF remoto excede límite: {document_id}"
                        )
                    digest.update(block)
                    handle.write(block)
            if prefix != b"%PDF-":
                raise OfficialSourceAuditError(
                    f"Respuesta sin firma PDF: {document_id}"
                )
            sha256 = digest.hexdigest()
            if sha256 != acquired.sha256:
                raise OfficialSourceAuditError(
                    f"Descarga no determinista para {document_id}: "
                    f"{acquired.sha256} != {sha256}"
                )
            tmp.replace(target)
        finally:
            if tmp.exists():
                tmp.unlink()

        records.append(
            EvidenceRecord(
                document_id=document_id,
                source_url=acquired.requested_url,
                final_url=acquired.final_url,
                filename=filename,
                sha256=sha256,
                size_bytes=size,
            )
        )

    manifest = {
        "schema_version": "1.0",
        "purpose": "offline_official_source_evidence",
        "allowed_authority_hosts": sorted(allowed_hosts),
        "records": [asdict(item) for item in records],
    }
    manifest_path = output_dir / "evidence_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def audit_offline_official_evidence(
    *,
    bridge_report_path: Path,
    candidate_registry_path: Path,
    evidence_bundle_dir: Path,
) -> OfflineEvidenceAuditSummary:
    bridge_payload = _read_json_object(bridge_report_path)
    registry = _read_json_object(candidate_registry_path)
    manifest = _read_json_object(evidence_bundle_dir / "evidence_manifest.json")

    raw_bridge = bridge_payload.get("documents")
    raw_candidates = registry.get("documents")
    raw_hosts = registry.get("allowed_authority_hosts")
    raw_records = manifest.get("records")

    if not isinstance(raw_bridge, list):
        raise OfficialSourceAuditError("Bridge 19I.18I sin documents.")
    if not isinstance(raw_candidates, list):
        raise OfficialSourceAuditError("Registry sin documents.")
    if not isinstance(raw_hosts, list) or not all(
        isinstance(item, str) and item for item in raw_hosts
    ):
        raise OfficialSourceAuditError("allowed_authority_hosts inválido.")
    if not isinstance(raw_records, list):
        raise OfficialSourceAuditError("Manifest de evidencia sin records.")

    allowed_hosts = {item.lower() for item in raw_hosts}
    bridge: dict[str, tuple[str, str]] = {}
    for item in raw_bridge:
        if not isinstance(item, dict):
            raise OfficialSourceAuditError("Entrada bridge inválida.")
        document_id = item.get("document_id")
        local_sha = item.get("local_source_sha256")
        local_path = item.get("resolved_source_path")
        if (
            not isinstance(document_id, str)
            or not isinstance(local_sha, str)
            or len(local_sha) != 64
            or not isinstance(local_path, str)
            or item.get("bridge_verified") is not True
        ):
            raise OfficialSourceAuditError("Bridge no verificado o inválido.")
        bridge[document_id] = (local_sha, local_path)

    candidate_ids = {
        item["document_id"]
        for item in raw_candidates
        if isinstance(item, dict) and isinstance(item.get("document_id"), str)
    }
    if candidate_ids != set(bridge):
        raise OfficialSourceAuditError(
            "Cobertura candidata distinta del bridge verificado."
        )

    records: dict[str, dict[str, object]] = {}
    for item in raw_records:
        if not isinstance(item, dict):
            raise OfficialSourceAuditError("Record de evidencia inválido.")
        document_id = item.get("document_id")
        if not isinstance(document_id, str) or document_id not in bridge:
            raise OfficialSourceAuditError(
                f"document_id de evidencia inválido: {document_id}"
            )
        if document_id in records:
            raise OfficialSourceAuditError(
                f"Evidencia duplicada para {document_id}"
            )
        records[document_id] = item

    verified: list[str] = []
    blocked: list[str] = []
    missing: list[str] = []
    results: list[OfflineEvidenceDocumentResult] = []

    for document_id in sorted(bridge):
        local_sha, _local_path = bridge[document_id]
        record = records.get(document_id)
        if record is None:
            missing.append(document_id)
            blocked.append(document_id)
            results.append(
                OfflineEvidenceDocumentResult(
                    document_id=document_id,
                    local_source_sha256=local_sha,
                    evidence_sha256=None,
                    source_url=None,
                    evidence_file=None,
                    evidence_integrity_ok=False,
                    exact_local_hash_match=False,
                    official_provenance_verified=False,
                    blocked_reason="missing_official_evidence",
                )
            )
            continue

        source_url = record.get("final_url")
        filename = record.get("filename")
        expected_sha = record.get("sha256")
        expected_size = record.get("size_bytes")
        if (
            not isinstance(source_url, str)
            or not isinstance(filename, str)
            or not isinstance(expected_sha, str)
            or len(expected_sha) != 64
            or not isinstance(expected_size, int)
            or expected_size <= 0
        ):
            raise OfficialSourceAuditError(
                f"Record de evidencia malformado: {document_id}"
            )
        _validate_https_authority_url(source_url, allowed_hosts)
        filename = _safe_filename(filename)
        evidence_file = evidence_bundle_dir / "files" / filename
        if not evidence_file.is_file():
            raise OfficialSourceAuditError(
                f"Archivo de evidencia ausente: {evidence_file}"
            )

        actual_sha, actual_size = _sha256_file(evidence_file)
        integrity_ok = (
            actual_sha == expected_sha and actual_size == expected_size
        )
        exact_match = integrity_ok and actual_sha == local_sha
        if exact_match:
            verified.append(document_id)
            reason = None
        else:
            blocked.append(document_id)
            reason = (
                "evidence_integrity_failed"
                if not integrity_ok
                else "official_binary_differs_from_local_pdf"
            )

        results.append(
            OfflineEvidenceDocumentResult(
                document_id=document_id,
                local_source_sha256=local_sha,
                evidence_sha256=actual_sha,
                source_url=source_url,
                evidence_file=str(evidence_file),
                evidence_integrity_ok=integrity_ok,
                exact_local_hash_match=exact_match,
                official_provenance_verified=exact_match,
                blocked_reason=reason,
            )
        )

    return OfflineEvidenceAuditSummary(
        candidate_documents=len(bridge),
        evidence_records=len(records),
        verified_documents=tuple(verified),
        blocked_documents=tuple(blocked),
        missing_evidence_documents=tuple(missing),
        promotion_ready_documents=(),
        public_release_allowed=False,
        documents=tuple(results),
    )


def write_offline_evidence_audit_report(
    summary: OfflineEvidenceAuditSummary,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
