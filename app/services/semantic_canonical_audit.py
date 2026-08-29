from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from app.domain.legal_chunks import LegalChunk


class SemanticCanonicalAuditError(RuntimeError):
    """Error controlado al comparar corpus canónicos."""


@dataclass(frozen=True)
class DocumentSemanticDelta:
    canonical_id: str
    baseline_chunks: int
    candidate_chunks: int
    delta: int
    baseline_article_units: int
    candidate_article_units: int
    labels_only_baseline: tuple[str, ...]
    labels_only_candidate: tuple[str, ...]


@dataclass(frozen=True)
class SemanticCanonicalReport:
    baseline_path: str
    candidate_path: str
    baseline_sha256: str
    candidate_sha256: str
    baseline_chunks: int
    candidate_chunks: int
    duplicate_candidate_ids: int
    candidate_empty_text: int
    documents: tuple[DocumentSemanticDelta, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path) -> list[LegalChunk]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise SemanticCanonicalAuditError(f"No existe corpus: {resolved}")
    chunks: list[LegalChunk] = []
    try:
        with resolved.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    chunks.append(LegalChunk.model_validate_json(line))
                except ValueError as exc:
                    raise SemanticCanonicalAuditError(
                        f"JSONL inválido en {resolved}:{line_number}"
                    ) from exc
    except OSError as exc:
        raise SemanticCanonicalAuditError(f"No se pudo leer {resolved}") from exc
    return chunks


def _labels(chunks: list[LegalChunk]) -> dict[str, Counter[str]]:
    result: dict[str, Counter[str]] = defaultdict(Counter)
    for chunk in chunks:
        result[chunk.canonical_id][chunk.unit_label] += 1
    return result


def compare_canonical_corpora(
    *,
    baseline_path: Path,
    candidate_path: Path,
) -> SemanticCanonicalReport:
    baseline_resolved = baseline_path.expanduser().resolve()
    candidate_resolved = candidate_path.expanduser().resolve()
    baseline = _load(baseline_resolved)
    candidate = _load(candidate_resolved)

    candidate_ids = [chunk.chunk_id for chunk in candidate]
    duplicate_ids = len(candidate_ids) - len(set(candidate_ids))
    empty_text = sum(not chunk.text.strip() for chunk in candidate)

    baseline_by_doc: dict[str, list[LegalChunk]] = defaultdict(list)
    candidate_by_doc: dict[str, list[LegalChunk]] = defaultdict(list)
    for chunk in baseline:
        baseline_by_doc[chunk.canonical_id].append(chunk)
    for chunk in candidate:
        candidate_by_doc[chunk.canonical_id].append(chunk)

    baseline_labels = _labels(baseline)
    candidate_labels = _labels(candidate)
    documents: list[DocumentSemanticDelta] = []

    for canonical_id in sorted(set(baseline_by_doc) | set(candidate_by_doc)):
        old = baseline_by_doc[canonical_id]
        new = candidate_by_doc[canonical_id]
        old_articles = sum(chunk.unit_type.value == "article" for chunk in old)
        new_articles = sum(chunk.unit_type.value == "article" for chunk in new)
        old_set = set(baseline_labels[canonical_id])
        new_set = set(candidate_labels[canonical_id])
        documents.append(
            DocumentSemanticDelta(
                canonical_id=canonical_id,
                baseline_chunks=len(old),
                candidate_chunks=len(new),
                delta=len(new) - len(old),
                baseline_article_units=old_articles,
                candidate_article_units=new_articles,
                labels_only_baseline=tuple(sorted(old_set - new_set)),
                labels_only_candidate=tuple(sorted(new_set - old_set)),
            )
        )

    return SemanticCanonicalReport(
        baseline_path=str(baseline_resolved),
        candidate_path=str(candidate_resolved),
        baseline_sha256=_sha256(baseline_resolved),
        candidate_sha256=_sha256(candidate_resolved),
        baseline_chunks=len(baseline),
        candidate_chunks=len(candidate),
        duplicate_candidate_ids=duplicate_ids,
        candidate_empty_text=empty_text,
        documents=tuple(documents),
    )


def write_semantic_report(path: Path, report: SemanticCanonicalReport) -> None:
    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        asdict(report),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=resolved.parent,
        prefix=f".{resolved.name}.",
        suffix=".tmp",
    ) as handle:
        handle.write(payload)
        temp_path = Path(handle.name)
    os.replace(temp_path, resolved)
