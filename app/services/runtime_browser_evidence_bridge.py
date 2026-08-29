from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

from app.services.runtime_official_source_audit import OfficialSourceAuditError


@dataclass(frozen=True)
class BrowserBridgeDocumentResult:
    document_id: str
    source_url: str
    browser_evidence_file: str
    browser_evidence_sha256: str
    local_source_sha256: str
    evidence_integrity_ok: bool
    bridge_verified: bool
    exact_binary_match: bool
    official_binary_provenance_status: str
    blocked_reason: str | None


@dataclass(frozen=True)
class BrowserBridgeAuditSummary:
    observed_browser_documents: int
    exact_binary_verified_documents: tuple[str, ...]
    differing_binary_documents: tuple[str, ...]
    blocked_documents: tuple[str, ...]
    public_release_allowed: bool
    documents: tuple[BrowserBridgeDocumentResult, ...]


def _read_json_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OfficialSourceAuditError(f"No se pudo leer JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise OfficialSourceAuditError(f"{path} debe contener un objeto JSON.")
    return payload


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _safe_relative_pdf(value: str) -> Path:
    candidate = Path(value)
    if (
        not value
        or candidate.is_absolute()
        or ".." in candidate.parts
        or "\\" in value
        or candidate.suffix.lower() != ".pdf"
    ):
        raise OfficialSourceAuditError(
            f"Ruta de evidencia insegura o inválida: {value}"
        )
    return candidate


def _validate_official_https_url(url: str, allowed_hosts: set[str]) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme.lower() != "https":
        raise OfficialSourceAuditError(f"URL no HTTPS: {url}")
    if host not in allowed_hosts:
        raise OfficialSourceAuditError(f"Host oficial no permitido: {url}")


def audit_browser_evidence_against_local_bridge(
    *,
    browser_evidence_dir: Path,
    bridge_report_path: Path,
    candidate_registry_path: Path,
) -> BrowserBridgeAuditSummary:
    manifest = _read_json_object(browser_evidence_dir / "evidence_manifest.json")
    bridge_payload = _read_json_object(bridge_report_path)
    registry = _read_json_object(candidate_registry_path)

    raw_browser = manifest.get("documents")
    raw_bridge = bridge_payload.get("documents")
    raw_registry = registry.get("documents")
    raw_hosts = registry.get("allowed_authority_hosts")

    if not isinstance(raw_browser, list):
        raise OfficialSourceAuditError("Manifest J.6 sin documents.")
    if not isinstance(raw_bridge, list):
        raise OfficialSourceAuditError("Bridge 19I.18I sin documents.")
    if not isinstance(raw_registry, list):
        raise OfficialSourceAuditError("Registry oficial sin documents.")
    if not isinstance(raw_hosts, list) or not all(
        isinstance(item, str) and item for item in raw_hosts
    ):
        raise OfficialSourceAuditError("allowed_authority_hosts inválido.")

    allowed_hosts = {item.lower() for item in raw_hosts}

    registry_urls: dict[str, set[str]] = {}
    for raw in raw_registry:
        if not isinstance(raw, dict):
            raise OfficialSourceAuditError("Entrada registry inválida.")
        document_id = raw.get("document_id")
        urls = raw.get("candidate_urls")
        if (
            not isinstance(document_id, str)
            or not document_id
            or not isinstance(urls, list)
            or not urls
            or not all(isinstance(url, str) and url for url in urls)
        ):
            raise OfficialSourceAuditError("Registry oficial inválido.")
        for url in urls:
            _validate_official_https_url(url, allowed_hosts)
        registry_urls[document_id] = set(urls)

    bridge: dict[str, str] = {}
    for raw in raw_bridge:
        if not isinstance(raw, dict):
            raise OfficialSourceAuditError("Entrada bridge inválida.")
        document_id = raw.get("document_id")
        local_sha = raw.get("local_source_sha256")
        if (
            not isinstance(document_id, str)
            or not isinstance(local_sha, str)
            or len(local_sha) != 64
            or raw.get("bridge_verified") is not True
        ):
            raise OfficialSourceAuditError(
                "Bridge local no verificado o inválido."
            )
        bridge[document_id] = local_sha.lower()

    seen: set[str] = set()
    results: list[BrowserBridgeDocumentResult] = []
    exact: list[str] = []
    differing: list[str] = []
    blocked: list[str] = []

    for raw in raw_browser:
        if not isinstance(raw, dict):
            raise OfficialSourceAuditError("Entrada J.6 inválida.")
        document_id = raw.get("document_id")
        source_url = raw.get("source_url")
        evidence_file = raw.get("evidence_file")
        expected_sha = raw.get("sha256")
        expected_size = raw.get("size_bytes")
        acquisition_method = raw.get("acquisition_method")

        if not isinstance(document_id, str) or not document_id:
            raise OfficialSourceAuditError("document_id J.6 inválido.")
        if document_id in seen:
            raise OfficialSourceAuditError(
                f"Evidencia J.6 duplicada para {document_id}."
            )
        seen.add(document_id)

        if document_id not in registry_urls or document_id not in bridge:
            raise OfficialSourceAuditError(
                f"{document_id} no existe en registry/bridge verificado."
            )
        if (
            not isinstance(source_url, str)
            or source_url not in registry_urls[document_id]
        ):
            raise OfficialSourceAuditError(
                f"URL J.6 no coincide con registry para {document_id}."
            )
        _validate_official_https_url(source_url, allowed_hosts)

        if acquisition_method != "manual_browser_official_url":
            raise OfficialSourceAuditError(
                f"Método de adquisición inválido para {document_id}."
            )
        if (
            not isinstance(evidence_file, str)
            or not isinstance(expected_sha, str)
            or len(expected_sha) != 64
            or not isinstance(expected_size, int)
            or expected_size <= 4
        ):
            raise OfficialSourceAuditError(
                f"Metadatos de evidencia inválidos para {document_id}."
            )

        relative_pdf = _safe_relative_pdf(evidence_file)
        evidence_path = browser_evidence_dir / relative_pdf
        if not evidence_path.is_file():
            raise OfficialSourceAuditError(
                f"Evidencia inexistente para {document_id}: {evidence_path}"
            )
        with evidence_path.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise OfficialSourceAuditError(
                    f"Evidencia sin firma PDF para {document_id}."
                )

        actual_sha, actual_size = _sha256_file(evidence_path)
        integrity_ok = (
            actual_sha == expected_sha.lower()
            and actual_size == expected_size
        )
        local_sha = bridge[document_id]

        if not integrity_ok:
            blocked.append(document_id)
            results.append(
                BrowserBridgeDocumentResult(
                    document_id=document_id,
                    source_url=source_url,
                    browser_evidence_file=evidence_file,
                    browser_evidence_sha256=actual_sha,
                    local_source_sha256=local_sha,
                    evidence_integrity_ok=False,
                    bridge_verified=True,
                    exact_binary_match=False,
                    official_binary_provenance_status="evidence_integrity_failed",
                    blocked_reason="evidence_integrity_failed",
                )
            )
            continue

        matches = actual_sha == local_sha
        if matches:
            exact.append(document_id)
            status = "exact_binary_official_source_verified"
            reason = None
        else:
            differing.append(document_id)
            blocked.append(document_id)
            status = "official_binary_differs_from_local_pdf"
            reason = "official_binary_differs_from_local_pdf"

        results.append(
            BrowserBridgeDocumentResult(
                document_id=document_id,
                source_url=source_url,
                browser_evidence_file=evidence_file,
                browser_evidence_sha256=actual_sha,
                local_source_sha256=local_sha,
                evidence_integrity_ok=True,
                bridge_verified=True,
                exact_binary_match=matches,
                official_binary_provenance_status=status,
                blocked_reason=reason,
            )
        )

    return BrowserBridgeAuditSummary(
        observed_browser_documents=len(results),
        exact_binary_verified_documents=tuple(sorted(exact)),
        differing_binary_documents=tuple(sorted(differing)),
        blocked_documents=tuple(sorted(blocked)),
        public_release_allowed=False,
        documents=tuple(sorted(results, key=lambda item: item.document_id)),
    )


def write_browser_bridge_report(
    summary: BrowserBridgeAuditSummary,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(summary)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
