from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path


class RuntimePublicationContentAuditError(RuntimeError):
    """Fallo controlado de la auditoría de conformidad del contenido."""


@dataclass(frozen=True)
class DocumentContentConformity:
    document_id: str
    chunk_count: int
    source_types: tuple[str, ...]
    source_roles: tuple[str, ...]
    source_filenames: tuple[str, ...]
    source_sha256_count: int
    text_hash_checked: int
    text_hash_mismatch: int
    editorial_marker_hits: int
    metadata_conformant: bool
    integrity_conformant: bool
    requires_manual_review: bool
    technical_conformity_passed: bool


@dataclass(frozen=True)
class RuntimePublicationContentSummary:
    runtime_chunks: int
    candidate_chunks: int
    candidate_documents: int
    missing_candidate_documents: tuple[str, ...]
    unexpected_candidate_documents: tuple[str, ...]
    metadata_nonconformant_documents: tuple[str, ...]
    integrity_nonconformant_documents: tuple[str, ...]
    manual_review_documents: tuple[str, ...]
    technically_conformant_documents: tuple[str, ...]
    publication_promotion_allowed: bool
    documents: tuple[DocumentContentConformity, ...]


def _read_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimePublicationContentAuditError(
            f"No se pudo leer JSON: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimePublicationContentAuditError(
            f"{path} debe contener un objeto JSON."
        )
    return payload


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        char for char in normalized if not unicodedata.combining(char)
    )


def _metadata(payload: dict[str, object], line_number: int) -> dict[str, object]:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise RuntimePublicationContentAuditError(
            f"Chunk sin metadata en línea {line_number}."
        )
    return metadata


def _document_id(metadata: dict[str, object], line_number: int) -> str:
    value = metadata.get("document_id")
    if not isinstance(value, str) or not value.strip():
        raise RuntimePublicationContentAuditError(
            f"document_id inválido en línea {line_number}."
        )
    return value.strip()


def audit_runtime_publication_content(
    *,
    chunks_path: Path,
    content_policy_path: Path,
) -> RuntimePublicationContentSummary:
    policy = _read_object(content_policy_path)
    raw_ids = policy.get("candidate_document_ids")
    if not isinstance(raw_ids, list) or not all(
        isinstance(item, str) and item for item in raw_ids
    ):
        raise RuntimePublicationContentAuditError(
            "candidate_document_ids inválido."
        )
    candidate_ids = set(raw_ids)
    if len(candidate_ids) != len(raw_ids):
        raise RuntimePublicationContentAuditError(
            "candidate_document_ids contiene duplicados."
        )

    expected_source_type = policy.get("expected_source_type")
    expected_roles = policy.get("expected_roles")
    raw_markers = policy.get("editorial_review_markers")
    if not isinstance(expected_source_type, str):
        raise RuntimePublicationContentAuditError(
            "expected_source_type inválido."
        )
    if not isinstance(expected_roles, dict):
        raise RuntimePublicationContentAuditError("expected_roles inválido.")
    if set(expected_roles) != candidate_ids:
        raise RuntimePublicationContentAuditError(
            "expected_roles debe cubrir exactamente los candidatos."
        )
    if not isinstance(raw_markers, list) or not all(
        isinstance(item, str) and item.strip() for item in raw_markers
    ):
        raise RuntimePublicationContentAuditError(
            "editorial_review_markers inválido."
        )
    markers = tuple(_normalize(item) for item in raw_markers)

    counts: Counter[str] = Counter()
    source_types: dict[str, set[str]] = defaultdict(set)
    source_roles: dict[str, set[str]] = defaultdict(set)
    source_filenames: dict[str, set[str]] = defaultdict(set)
    source_hashes: dict[str, set[str]] = defaultdict(set)
    text_hash_checked: Counter[str] = Counter()
    text_hash_mismatch: Counter[str] = Counter()
    marker_hits: Counter[str] = Counter()
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
                    raise RuntimePublicationContentAuditError(
                        f"JSONL inválido en línea {line_number}."
                    ) from exc
                if not isinstance(payload, dict):
                    raise RuntimePublicationContentAuditError(
                        f"Chunk inválido en línea {line_number}."
                    )

                metadata = _metadata(payload, line_number)
                document_id = _document_id(metadata, line_number)
                if document_id not in candidate_ids:
                    continue
                counts[document_id] += 1

                raw_source_type = metadata.get("source_type")
                if isinstance(raw_source_type, str):
                    source_types[document_id].add(raw_source_type)
                else:
                    source_types[document_id].add("<missing>")

                raw_role = metadata.get("source_role")
                if isinstance(raw_role, str) and raw_role:
                    source_roles[document_id].add(raw_role)
                else:
                    source_roles[document_id].add("<missing>")

                raw_filename = metadata.get("source_filename")
                if isinstance(raw_filename, str) and raw_filename:
                    source_filenames[document_id].add(raw_filename)
                else:
                    source_filenames[document_id].add("<missing>")

                raw_source_sha = metadata.get("source_sha256")
                if isinstance(raw_source_sha, str) and len(raw_source_sha) == 64:
                    source_hashes[document_id].add(raw_source_sha)
                else:
                    source_hashes[document_id].add("<missing-or-invalid>")

                text = payload.get("text")
                if not isinstance(text, str) or not text:
                    raise RuntimePublicationContentAuditError(
                        f"Texto inválido en línea {line_number}."
                    )

                raw_text_sha = metadata.get("retrieval_text_sha256")
                if isinstance(raw_text_sha, str) and len(raw_text_sha) == 64:
                    text_hash_checked[document_id] += 1
                    actual = hashlib.sha256(text.encode("utf-8")).hexdigest()
                    if actual != raw_text_sha:
                        text_hash_mismatch[document_id] += 1

                normalized_text = _normalize(text)
                if any(marker in normalized_text for marker in markers):
                    marker_hits[document_id] += 1
    except OSError as exc:
        raise RuntimePublicationContentAuditError(
            f"No se pudo leer runtime chunks: {chunks_path}"
        ) from exc

    missing = tuple(sorted(candidate_ids - set(counts)))
    unexpected = tuple(sorted(set(counts) - candidate_ids))
    documents: list[DocumentContentConformity] = []
    metadata_bad: list[str] = []
    integrity_bad: list[str] = []
    manual_review: list[str] = []
    passed: list[str] = []

    for document_id in sorted(candidate_ids & set(counts)):
        expected_doc_roles_raw = expected_roles.get(document_id)
        if not isinstance(expected_doc_roles_raw, list) or not all(
            isinstance(item, str) and item for item in expected_doc_roles_raw
        ):
            raise RuntimePublicationContentAuditError(
                f"Roles esperados inválidos para {document_id}."
            )
        expected_doc_roles = set(expected_doc_roles_raw)
        observed_types = source_types[document_id]
        observed_roles = source_roles[document_id]

        metadata_ok = (
            observed_types == {expected_source_type}
            and observed_roles.issubset(expected_doc_roles)
            and "<missing>" not in source_filenames[document_id]
            and "<missing-or-invalid>" not in source_hashes[document_id]
            and len(source_hashes[document_id]) == 1
        )
        integrity_ok = text_hash_mismatch[document_id] == 0
        requires_review = marker_hits[document_id] > 0
        technical_pass = metadata_ok and integrity_ok and not requires_review

        if not metadata_ok:
            metadata_bad.append(document_id)
        if not integrity_ok:
            integrity_bad.append(document_id)
        if requires_review:
            manual_review.append(document_id)
        if technical_pass:
            passed.append(document_id)

        documents.append(
            DocumentContentConformity(
                document_id=document_id,
                chunk_count=counts[document_id],
                source_types=tuple(sorted(observed_types)),
                source_roles=tuple(sorted(observed_roles)),
                source_filenames=tuple(sorted(source_filenames[document_id])),
                source_sha256_count=len(source_hashes[document_id]),
                text_hash_checked=text_hash_checked[document_id],
                text_hash_mismatch=text_hash_mismatch[document_id],
                editorial_marker_hits=marker_hits[document_id],
                metadata_conformant=metadata_ok,
                integrity_conformant=integrity_ok,
                requires_manual_review=requires_review,
                technical_conformity_passed=technical_pass,
            )
        )

    return RuntimePublicationContentSummary(
        runtime_chunks=runtime_chunks,
        candidate_chunks=sum(counts.values()),
        candidate_documents=len(counts),
        missing_candidate_documents=missing,
        unexpected_candidate_documents=unexpected,
        metadata_nonconformant_documents=tuple(metadata_bad),
        integrity_nonconformant_documents=tuple(integrity_bad),
        manual_review_documents=tuple(manual_review),
        technically_conformant_documents=tuple(passed),
        publication_promotion_allowed=False,
        documents=tuple(documents),
    )


def write_runtime_publication_content_report(
    summary: RuntimePublicationContentSummary,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
