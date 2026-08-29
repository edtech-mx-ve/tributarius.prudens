from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse


class RuntimePublicationProvenanceError(RuntimeError):
    """Fallo controlado al auditar procedencia oficial del runtime."""


@dataclass(frozen=True)
class DocumentProvenanceResult:
    document_id: str
    chunk_count: int
    source_sha256_values: tuple[str, ...]
    source_filenames: tuple[str, ...]
    source_urls: tuple[str, ...]
    authority_hosts: tuple[str, ...]
    missing_source_url_chunks: int
    disallowed_host_urls: tuple[str, ...]
    exact_source_provenance_verified: bool
    promotion_ready: bool


@dataclass(frozen=True)
class RuntimePublicationProvenanceSummary:
    runtime_chunks: int
    candidate_documents: int
    missing_candidate_documents: tuple[str, ...]
    provenance_verified_documents: tuple[str, ...]
    provenance_blocked_documents: tuple[str, ...]
    promotion_ready_documents: tuple[str, ...]
    public_release_allowed: bool
    documents: tuple[DocumentProvenanceResult, ...]


def _read_json_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimePublicationProvenanceError(
            f"No se pudo leer JSON: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimePublicationProvenanceError(
            f"{path} debe contener un objeto JSON."
        )
    return payload


def _read_policy(path: Path) -> dict[str, dict[str, object]]:
    payload = _read_json_object(path)
    raw_documents = payload.get("documents")
    if not isinstance(raw_documents, list):
        raise RuntimePublicationProvenanceError(
            "La política debe contener documents como lista."
        )
    result: dict[str, dict[str, object]] = {}
    for item in raw_documents:
        if not isinstance(item, dict):
            raise RuntimePublicationProvenanceError(
                "Entrada de política inválida."
            )
        document_id = item.get("document_id")
        if not isinstance(document_id, str) or not document_id:
            raise RuntimePublicationProvenanceError(
                "document_id inválido en política."
            )
        if document_id in result:
            raise RuntimePublicationProvenanceError(
                f"document_id duplicado: {document_id}"
            )
        hosts = item.get("allowed_authority_hosts")
        if not isinstance(hosts, list) or not all(
            isinstance(host, str) and host for host in hosts
        ):
            raise RuntimePublicationProvenanceError(
                f"allowed_authority_hosts inválido para {document_id}."
            )
        if item.get("requires_exact_source_provenance") is not True:
            raise RuntimePublicationProvenanceError(
                f"{document_id} debe exigir procedencia exacta."
            )
        result[document_id] = item
    return result


def _get_metadata(payload: dict[str, object], line_number: int) -> dict[str, object]:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise RuntimePublicationProvenanceError(
            f"Chunk sin metadata en línea {line_number}."
        )
    return metadata


def _source_url(metadata: dict[str, object]) -> str | None:
    for key in ("source_url", "source_uri", "official_source_url"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _host(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        return ""
    return parsed.hostname.lower()


def audit_runtime_publication_provenance(
    *,
    chunks_path: Path,
    policy_path: Path,
) -> RuntimePublicationProvenanceSummary:
    policy = _read_policy(policy_path)
    candidate_ids = set(policy)

    counts: dict[str, int] = defaultdict(int)
    hashes: dict[str, set[str]] = defaultdict(set)
    filenames: dict[str, set[str]] = defaultdict(set)
    urls: dict[str, set[str]] = defaultdict(set)
    missing_url: dict[str, int] = defaultdict(int)
    runtime_chunks = 0

    try:
        with chunks_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                runtime_chunks += 1
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise RuntimePublicationProvenanceError(
                        f"JSONL inválido en línea {line_number}."
                    ) from exc
                if not isinstance(payload, dict):
                    raise RuntimePublicationProvenanceError(
                        f"Chunk inválido en línea {line_number}."
                    )
                metadata = _get_metadata(payload, line_number)
                document_id = metadata.get("document_id")
                if not isinstance(document_id, str):
                    raise RuntimePublicationProvenanceError(
                        f"document_id inválido en línea {line_number}."
                    )
                if document_id not in candidate_ids:
                    continue

                counts[document_id] += 1

                raw_sha = metadata.get("source_sha256")
                if isinstance(raw_sha, str) and len(raw_sha) == 64:
                    hashes[document_id].add(raw_sha)
                else:
                    hashes[document_id].add("<missing-or-invalid>")

                filename = metadata.get("source_filename")
                if isinstance(filename, str) and filename:
                    filenames[document_id].add(filename)
                else:
                    filenames[document_id].add("<missing>")

                source_url = _source_url(metadata)
                if source_url is None:
                    missing_url[document_id] += 1
                else:
                    urls[document_id].add(source_url)
    except OSError as exc:
        raise RuntimePublicationProvenanceError(
            f"No se pudo leer el runtime: {chunks_path}"
        ) from exc

    missing_documents = tuple(sorted(candidate_ids - set(counts)))
    verified: list[str] = []
    blocked: list[str] = []
    promotion_ready: list[str] = []
    documents: list[DocumentProvenanceResult] = []

    for document_id in sorted(candidate_ids & set(counts)):
        allowed_hosts_raw = policy[document_id]["allowed_authority_hosts"]
        assert isinstance(allowed_hosts_raw, list)
        allowed_hosts = {str(item).lower() for item in allowed_hosts_raw}

        observed_hosts = {_host(url) for url in urls[document_id]}
        disallowed = tuple(
            sorted(
                url
                for url in urls[document_id]
                if _host(url) not in allowed_hosts
            )
        )

        provenance_ok = (
            missing_url[document_id] == 0
            and bool(urls[document_id])
            and "" not in observed_hosts
            and not disallowed
            and "<missing-or-invalid>" not in hashes[document_id]
            and len(hashes[document_id]) == 1
            and "<missing>" not in filenames[document_id]
        )

        if provenance_ok:
            verified.append(document_id)
        else:
            blocked.append(document_id)

        # 19I.18H is diagnostic/fail-closed: no policy promotion is performed here.
        ready = False
        if ready:
            promotion_ready.append(document_id)

        documents.append(
            DocumentProvenanceResult(
                document_id=document_id,
                chunk_count=counts[document_id],
                source_sha256_values=tuple(sorted(hashes[document_id])),
                source_filenames=tuple(sorted(filenames[document_id])),
                source_urls=tuple(sorted(urls[document_id])),
                authority_hosts=tuple(sorted(host for host in observed_hosts if host)),
                missing_source_url_chunks=missing_url[document_id],
                disallowed_host_urls=disallowed,
                exact_source_provenance_verified=provenance_ok,
                promotion_ready=ready,
            )
        )

    return RuntimePublicationProvenanceSummary(
        runtime_chunks=runtime_chunks,
        candidate_documents=len(counts),
        missing_candidate_documents=missing_documents,
        provenance_verified_documents=tuple(verified),
        provenance_blocked_documents=tuple(blocked),
        promotion_ready_documents=tuple(promotion_ready),
        public_release_allowed=False,
        documents=tuple(documents),
    )


def write_runtime_publication_provenance_report(
    summary: RuntimePublicationProvenanceSummary,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
