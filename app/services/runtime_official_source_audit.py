from __future__ import annotations

import hashlib
import json
import ssl
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class OfficialSourceAuditError(RuntimeError):
    """Fallo controlado de auditoría de procedencia oficial."""


@dataclass(frozen=True)
class RemoteArtifact:
    requested_url: str
    final_url: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class OfficialSourceDocumentResult:
    document_id: str
    local_source_path: str
    local_source_sha256: str
    candidate_urls: tuple[str, ...]
    attempted_urls: tuple[str, ...]
    matching_official_url: str | None
    remote_sha256_values: tuple[str, ...]
    fetch_errors: tuple[str, ...]
    exact_hash_match: bool
    official_provenance_verified: bool
    promotion_ready: bool


@dataclass(frozen=True)
class OfficialSourceAuditSummary:
    candidate_documents: int
    bridge_verified_documents: int
    official_provenance_verified_documents: tuple[str, ...]
    official_provenance_blocked_documents: tuple[str, ...]
    promotion_ready_documents: tuple[str, ...]
    public_release_allowed: bool
    documents: tuple[OfficialSourceDocumentResult, ...]


Fetcher = Callable[[str, set[str], int, int], RemoteArtifact]


def _read_json_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OfficialSourceAuditError(
            f"No se pudo leer JSON: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise OfficialSourceAuditError(
            f"{path} debe contener un objeto JSON."
        )
    return payload


def _validate_candidate_url(url: str, allowed_hosts: set[str]) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme.lower() != "https":
        raise OfficialSourceAuditError(
            f"URL oficial no HTTPS: {url}"
        )
    if host not in allowed_hosts:
        raise OfficialSourceAuditError(
            f"Host oficial no permitido: {url}"
        )


def fetch_official_pdf(
    url: str,
    allowed_hosts: set[str],
    timeout_seconds: int,
    max_bytes: int,
) -> RemoteArtifact:
    _validate_candidate_url(url, allowed_hosts)
    request_profiles = (
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/127.0 Safari/537.36"
            ),
            "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-MX,es;q=0.9,en;q=0.6",
            "Accept-Encoding": "identity",
            "Connection": "close",
            "Referer": "https://www.diputados.gob.mx/LeyesBiblio/index.htm",
        },
        {
            "User-Agent": "Tributarius-Prudens/19I.18J.1",
            "Accept": "application/pdf,*/*;q=0.8",
            "Accept-Encoding": "identity",
            "Connection": "close",
        },
    )
    context = ssl.create_default_context()
    errors: list[str] = []

    for profile_number, headers in enumerate(request_profiles, start=1):
        request = Request(url, headers=headers)
        digest = hashlib.sha256()
        size = 0
        prefix = b""
        try:
            with urlopen(
                request,
                timeout=timeout_seconds,
                context=context,
            ) as response:
                final_url = response.geturl()
                _validate_candidate_url(final_url, allowed_hosts)
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    if not prefix:
                        prefix = block[:5]
                    size += len(block)
                    if size > max_bytes:
                        raise OfficialSourceAuditError(
                            f"PDF remoto excede límite de {max_bytes} bytes: {url}"
                        )
                    digest.update(block)
        except HTTPError as exc:
            errors.append(
                f"profile={profile_number}; HTTP {exc.code} {exc.reason}"
            )
            continue
        except (URLError, TimeoutError, OSError) as exc:
            errors.append(
                f"profile={profile_number}; {type(exc).__name__}: {exc}"
            )
            continue

        if prefix != b"%PDF-":
            errors.append(
                f"profile={profile_number}; respuesta sin firma PDF"
            )
            continue

        return RemoteArtifact(
            requested_url=url,
            final_url=final_url,
            sha256=digest.hexdigest(),
            size_bytes=size,
        )

    raise OfficialSourceAuditError(
        f"No se pudo descargar {url}: " + " | ".join(errors)
    )


def _bridge_documents(
    bridge_report: dict[str, object],
) -> dict[str, dict[str, object]]:
    raw_documents = bridge_report.get("documents")
    if not isinstance(raw_documents, list):
        raise OfficialSourceAuditError(
            "El reporte 19I.18I no contiene documents."
        )
    result: dict[str, dict[str, object]] = {}
    for item in raw_documents:
        if not isinstance(item, dict):
            raise OfficialSourceAuditError(
                "Entrada inválida en reporte 19I.18I."
            )
        document_id = item.get("document_id")
        if not isinstance(document_id, str) or not document_id:
            raise OfficialSourceAuditError(
                "document_id inválido en reporte 19I.18I."
            )
        if item.get("bridge_verified") is not True:
            raise OfficialSourceAuditError(
                f"Puente local no verificado para {document_id}."
            )
        result[document_id] = item
    return result


def audit_official_source_provenance(
    *,
    bridge_report_path: Path,
    candidate_registry_path: Path,
    fetcher: Fetcher = fetch_official_pdf,
    timeout_seconds: int = 45,
    max_bytes: int = 50 * 1024 * 1024,
) -> OfficialSourceAuditSummary:
    bridge = _bridge_documents(_read_json_object(bridge_report_path))
    registry = _read_json_object(candidate_registry_path)

    raw_hosts = registry.get("allowed_authority_hosts")
    raw_documents = registry.get("documents")
    if not isinstance(raw_hosts, list) or not all(
        isinstance(item, str) and item for item in raw_hosts
    ):
        raise OfficialSourceAuditError(
            "allowed_authority_hosts inválido."
        )
    if not isinstance(raw_documents, list):
        raise OfficialSourceAuditError(
            "documents inválido en registro de candidatas."
        )
    allowed_hosts = {item.lower() for item in raw_hosts}

    candidate_map: dict[str, tuple[str, ...]] = {}
    for item in raw_documents:
        if not isinstance(item, dict):
            raise OfficialSourceAuditError(
                "Entrada candidata inválida."
            )
        document_id = item.get("document_id")
        urls = item.get("candidate_urls")
        if not isinstance(document_id, str) or not document_id:
            raise OfficialSourceAuditError(
                "document_id inválido en candidatas."
            )
        if not isinstance(urls, list) or not urls or not all(
            isinstance(url, str) and url for url in urls
        ):
            raise OfficialSourceAuditError(
                f"candidate_urls inválido para {document_id}."
            )
        if document_id in candidate_map:
            raise OfficialSourceAuditError(
                f"document_id duplicado: {document_id}"
            )
        for url in urls:
            _validate_candidate_url(url, allowed_hosts)
        candidate_map[document_id] = tuple(urls)

    if set(candidate_map) != set(bridge):
        missing = sorted(set(bridge) - set(candidate_map))
        extra = sorted(set(candidate_map) - set(bridge))
        raise OfficialSourceAuditError(
            f"Cobertura de candidatas no exacta; missing={missing}; extra={extra}"
        )

    verified: list[str] = []
    blocked: list[str] = []
    documents: list[OfficialSourceDocumentResult] = []

    for document_id in sorted(candidate_map):
        bridge_item = bridge[document_id]
        local_path = bridge_item.get("resolved_source_path")
        local_sha = bridge_item.get("local_source_sha256")
        if not isinstance(local_path, str) or not local_path:
            raise OfficialSourceAuditError(
                f"resolved_source_path inválido para {document_id}."
            )
        if not isinstance(local_sha, str) or len(local_sha) != 64:
            raise OfficialSourceAuditError(
                f"local_source_sha256 inválido para {document_id}."
            )

        attempted: list[str] = []
        remote_hashes: list[str] = []
        errors: list[str] = []
        matching_url: str | None = None

        for url in candidate_map[document_id]:
            attempted.append(url)
            try:
                artifact = fetcher(
                    url,
                    allowed_hosts,
                    timeout_seconds,
                    max_bytes,
                )
            except OfficialSourceAuditError as exc:
                errors.append(str(exc))
                continue
            remote_hashes.append(artifact.sha256)
            if artifact.sha256 == local_sha:
                matching_url = artifact.final_url
                break

        exact_match = matching_url is not None
        if exact_match:
            verified.append(document_id)
        else:
            blocked.append(document_id)

        # Diagnóstico fail-closed: 19I.18J no modifica la política 19I.18E.
        documents.append(
            OfficialSourceDocumentResult(
                document_id=document_id,
                local_source_path=local_path,
                local_source_sha256=local_sha,
                candidate_urls=candidate_map[document_id],
                attempted_urls=tuple(attempted),
                matching_official_url=matching_url,
                remote_sha256_values=tuple(remote_hashes),
                fetch_errors=tuple(errors),
                exact_hash_match=exact_match,
                official_provenance_verified=exact_match,
                promotion_ready=False,
            )
        )

    return OfficialSourceAuditSummary(
        candidate_documents=len(candidate_map),
        bridge_verified_documents=len(bridge),
        official_provenance_verified_documents=tuple(verified),
        official_provenance_blocked_documents=tuple(blocked),
        promotion_ready_documents=(),
        public_release_allowed=False,
        documents=tuple(documents),
    )


def write_official_source_provenance_report(
    summary: OfficialSourceAuditSummary,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
