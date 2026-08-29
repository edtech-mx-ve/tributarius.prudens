from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path


class RuntimeSourceBridgeError(RuntimeError):
    """Fallo controlado al auditar el puente runtime -> PDF fuente local."""


@dataclass(frozen=True)
class SourceBridgeDocument:
    document_id: str
    runtime_chunk_count: int
    runtime_source_filenames: tuple[str, ...]
    runtime_source_sha256_values: tuple[str, ...]
    resolved_source_path: str | None
    local_source_sha256: str | None
    resolution_method: str
    filename_match: bool
    sha256_match: bool
    bridge_verified: bool


@dataclass(frozen=True)
class RuntimeSourceBridgeSummary:
    runtime_chunks: int
    candidate_documents: int
    verified_documents: tuple[str, ...]
    blocked_documents: tuple[str, ...]
    missing_source_files: tuple[str, ...]
    hash_mismatch_documents: tuple[str, ...]
    public_release_allowed: bool
    documents: tuple[SourceBridgeDocument, ...]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise RuntimeSourceBridgeError(
            f"No se pudo leer archivo fuente: {path}"
        ) from exc
    return digest.hexdigest()


def _read_candidate_ids(policy_path: Path) -> tuple[str, ...]:
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeSourceBridgeError(
            f"No se pudo leer política: {policy_path}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeSourceBridgeError("La política debe ser un objeto JSON.")
    raw_ids = payload.get("candidate_document_ids")
    if not isinstance(raw_ids, list) or not all(
        isinstance(item, str) and item for item in raw_ids
    ):
        raise RuntimeSourceBridgeError(
            "candidate_document_ids inválido en política 19I.18G."
        )
    if len(raw_ids) != len(set(raw_ids)):
        raise RuntimeSourceBridgeError(
            "candidate_document_ids contiene duplicados."
        )
    return tuple(raw_ids)


def _metadata(payload: dict[str, object], line_number: int) -> dict[str, object]:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise RuntimeSourceBridgeError(
            f"Chunk sin metadata en línea {line_number}."
        )
    return metadata


def _normalize_filename(value: str) -> str:
    return Path(value).name.casefold()


def audit_runtime_source_bridge(
    *,
    chunks_path: Path,
    content_policy_path: Path,
    corpus_dir: Path,
) -> RuntimeSourceBridgeSummary:
    candidate_ids = set(_read_candidate_ids(content_policy_path))
    if not corpus_dir.is_dir():
        raise RuntimeSourceBridgeError(
            f"Corpus no encontrado o no es directorio: {corpus_dir}"
        )

    counts: dict[str, int] = defaultdict(int)
    filenames: dict[str, set[str]] = defaultdict(set)
    source_hashes: dict[str, set[str]] = defaultdict(set)
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
                    raise RuntimeSourceBridgeError(
                        f"JSONL inválido en línea {line_number}."
                    ) from exc
                if not isinstance(payload, dict):
                    raise RuntimeSourceBridgeError(
                        f"Chunk inválido en línea {line_number}."
                    )
                metadata = _metadata(payload, line_number)
                document_id = metadata.get("document_id")
                if not isinstance(document_id, str):
                    raise RuntimeSourceBridgeError(
                        f"document_id inválido en línea {line_number}."
                    )
                if document_id not in candidate_ids:
                    continue

                counts[document_id] += 1
                raw_filename = metadata.get("source_filename")
                if isinstance(raw_filename, str) and raw_filename:
                    filenames[document_id].add(Path(raw_filename).name)
                else:
                    filenames[document_id].add("<missing>")

                raw_sha = metadata.get("source_sha256")
                if isinstance(raw_sha, str) and len(raw_sha) == 64:
                    source_hashes[document_id].add(raw_sha.lower())
                else:
                    source_hashes[document_id].add("<missing-or-invalid>")
    except OSError as exc:
        raise RuntimeSourceBridgeError(
            f"No se pudo leer runtime chunks: {chunks_path}"
        ) from exc

    corpus_paths = tuple(
        path
        for path in corpus_dir.rglob("*")
        if path.is_file() and path.suffix.casefold() == ".pdf"
    )
    corpus_files = {
        _normalize_filename(path.name): path
        for path in corpus_paths
    }
    corpus_hash_index: dict[str, list[Path]] = defaultdict(list)
    for source_path in corpus_paths:
        corpus_hash_index[_sha256_file(source_path)].append(source_path)

    verified: list[str] = []
    blocked: list[str] = []
    missing_files: list[str] = []
    hash_mismatches: list[str] = []
    documents: list[SourceBridgeDocument] = []

    for document_id in sorted(candidate_ids):
        observed_filenames = tuple(sorted(filenames.get(document_id, set())))
        observed_hashes = tuple(sorted(source_hashes.get(document_id, set())))

        resolved: Path | None = None
        resolution_method = "unresolved"
        filename_metadata_valid = (
            len(observed_filenames) == 1
            and observed_filenames[0] != "<missing>"
        )
        filename_match = False
        if filename_metadata_valid:
            resolved = corpus_files.get(
                _normalize_filename(observed_filenames[0])
            )
            if resolved is not None:
                filename_match = True
                resolution_method = "filename"

        runtime_sha: str | None = None
        if (
            len(observed_hashes) == 1
            and observed_hashes[0] != "<missing-or-invalid>"
        ):
            runtime_sha = observed_hashes[0]

        if resolved is None and runtime_sha is not None:
            hash_candidates = corpus_hash_index.get(runtime_sha, [])
            if len(hash_candidates) == 1:
                resolved = hash_candidates[0]
                resolution_method = "sha256"
            elif len(hash_candidates) > 1:
                resolution_method = "sha256_ambiguous"

        local_sha: str | None = None
        if resolved is not None:
            local_sha = _sha256_file(resolved)

        sha_match = (
            local_sha is not None
            and runtime_sha is not None
            and local_sha == runtime_sha
        )
        bridge_ok = (
            counts.get(document_id, 0) > 0
            and resolved is not None
            and sha_match
        )

        if resolved is None:
            missing_files.append(document_id)
        elif not sha_match:
            hash_mismatches.append(document_id)

        if bridge_ok:
            verified.append(document_id)
        else:
            blocked.append(document_id)

        documents.append(
            SourceBridgeDocument(
                document_id=document_id,
                runtime_chunk_count=counts.get(document_id, 0),
                runtime_source_filenames=observed_filenames,
                runtime_source_sha256_values=observed_hashes,
                resolved_source_path=(
                    str(resolved.resolve()) if resolved is not None else None
                ),
                local_source_sha256=local_sha,
                resolution_method=resolution_method,
                filename_match=filename_match,
                sha256_match=sha_match,
                bridge_verified=bridge_ok,
            )
        )

    return RuntimeSourceBridgeSummary(
        runtime_chunks=runtime_chunks,
        candidate_documents=len(candidate_ids),
        verified_documents=tuple(verified),
        blocked_documents=tuple(blocked),
        missing_source_files=tuple(missing_files),
        hash_mismatch_documents=tuple(hash_mismatches),
        public_release_allowed=False,
        documents=tuple(documents),
    )


def write_runtime_source_bridge_report(
    summary: RuntimeSourceBridgeSummary,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
