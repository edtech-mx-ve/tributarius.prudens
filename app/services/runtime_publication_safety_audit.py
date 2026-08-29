from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, Literal

RedistributionStatus = Literal[
    "public_redistribution_verified",
    "restricted_or_internal_only",
    "unknown_requires_review",
]

_ALLOWED_STATUS: Final[str] = "public_redistribution_verified"


class RuntimePublicationSafetyError(RuntimeError):
    """Error controlado al auditar la publicación del runtime."""


@dataclass(frozen=True)
class DocumentPublicationResult:
    document_id: str
    chunk_count: int
    text_bytes: int
    redistribution_status: str
    evidence: str | None
    publishable: bool


@dataclass(frozen=True)
class RuntimePublicationSafetySummary:
    runtime_chunks: int
    observed_documents: int
    policy_documents: int
    verified_documents: int
    blocked_documents: int
    missing_policy_documents: int
    public_release_allowed: bool
    results: tuple[DocumentPublicationResult, ...]


def _load_policy(path: Path) -> dict[str, dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimePublicationSafetyError(
            f"No se pudo leer la política de publicación: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimePublicationSafetyError("La política debe ser un objeto.")
    if payload.get("allowed_status") != _ALLOWED_STATUS:
        raise RuntimePublicationSafetyError(
            "La política no declara el estado permitido esperado."
        )
    raw_documents = payload.get("documents")
    if not isinstance(raw_documents, list):
        raise RuntimePublicationSafetyError(
            "La política debe contener una lista documents."
        )

    result: dict[str, dict[str, object]] = {}
    for raw in raw_documents:
        if not isinstance(raw, dict):
            raise RuntimePublicationSafetyError(
                "Entrada inválida en documents."
            )
        document_id = raw.get("document_id")
        status = raw.get("redistribution_status")
        if not isinstance(document_id, str) or not document_id.strip():
            raise RuntimePublicationSafetyError("document_id inválido.")
        if document_id in result:
            raise RuntimePublicationSafetyError(
                f"document_id duplicado en política: {document_id}"
            )
        if status not in {
            "public_redistribution_verified",
            "restricted_or_internal_only",
            "unknown_requires_review",
        }:
            raise RuntimePublicationSafetyError(
                f"redistribution_status inválido para {document_id}."
            )
        if status == _ALLOWED_STATUS:
            evidence = raw.get("evidence")
            if not isinstance(evidence, str) or not evidence.strip():
                raise RuntimePublicationSafetyError(
                    f"{document_id} requiere evidencia explícita para publicar."
                )
        result[document_id] = raw
    return result


def _document_id(payload: dict[str, object]) -> str:
    direct = payload.get("document_id")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        nested = metadata.get("document_id")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    raise RuntimePublicationSafetyError(
        "Chunk runtime sin document_id verificable."
    )


def _text_bytes(payload: dict[str, object]) -> int:
    text = payload.get("text")
    if isinstance(text, str):
        return len(text.encode("utf-8"))
    return 0


def audit_runtime_publication_safety(
    *,
    chunks_path: Path,
    policy_path: Path,
) -> RuntimePublicationSafetySummary:
    policy = _load_policy(policy_path)
    counts: Counter[str] = Counter()
    text_bytes: Counter[str] = Counter()
    runtime_chunks = 0

    try:
        with chunks_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise RuntimePublicationSafetyError(
                        f"JSONL inválido en línea {line_number}."
                    ) from exc
                if not isinstance(payload, dict):
                    raise RuntimePublicationSafetyError(
                        f"Chunk inválido en línea {line_number}."
                    )
                document_id = _document_id(payload)
                counts[document_id] += 1
                text_bytes[document_id] += _text_bytes(payload)
                runtime_chunks += 1
    except OSError as exc:
        raise RuntimePublicationSafetyError(
            f"No se pudo leer runtime chunks: {chunks_path}"
        ) from exc

    if runtime_chunks == 0:
        raise RuntimePublicationSafetyError("Runtime chunks está vacío.")

    results: list[DocumentPublicationResult] = []
    verified = 0
    blocked = 0
    missing = 0

    for document_id in sorted(counts):
        raw = policy.get(document_id)
        if raw is None:
            status = "missing_policy_entry"
            evidence = None
            publishable = False
            missing += 1
        else:
            raw_status = raw.get("redistribution_status")
            status = str(raw_status)
            raw_evidence = raw.get("evidence")
            evidence = raw_evidence if isinstance(raw_evidence, str) else None
            publishable = status == _ALLOWED_STATUS
        if publishable:
            verified += 1
        else:
            blocked += 1
        results.append(
            DocumentPublicationResult(
                document_id=document_id,
                chunk_count=counts[document_id],
                text_bytes=text_bytes[document_id],
                redistribution_status=status,
                evidence=evidence,
                publishable=publishable,
            )
        )

    return RuntimePublicationSafetySummary(
        runtime_chunks=runtime_chunks,
        observed_documents=len(counts),
        policy_documents=len(policy),
        verified_documents=verified,
        blocked_documents=blocked,
        missing_policy_documents=missing,
        public_release_allowed=blocked == 0 and missing == 0,
        results=tuple(results),
    )


def write_publication_safety_report(
    summary: RuntimePublicationSafetySummary,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(summary)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
