from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from app.domain.chunks import LegalChunk
from app.domain.documents import SourceType
from app.services.legal_unit_integrity import (
    ArticleConsistency,
    compare_article_unit,
    extract_article_identifier,
)
from app.services.normative_integrity_audit import (
    NormativeIntegrityAuditError,
    classify_temporal_status,
)
from rag.indexing.builder import IndexBuildError, load_chunks_jsonl


class CausalClass(StrEnum):
    NON_ARTICLE_UNIT = "non_article_unit"
    RETRIEVAL_MATCH = "retrieval_match"
    RETRIEVAL_CONTINUATION_PARENT_VERIFIED = "retrieval_continuation_parent_verified"
    RETRIEVAL_MISMATCH_PARENT_VERIFIED = "retrieval_mismatch_parent_verified"
    CANONICAL_PARENT_MISMATCH = "canonical_parent_mismatch"
    CANONICAL_PARENT_UNVERIFIABLE = "canonical_parent_unverifiable"
    PARENT_MISSING = "parent_missing"


@dataclass(frozen=True)
class ParentAuditFinding:
    chunk_id: str
    parent_chunk_id: str | None
    document_id: str
    source_unit_type: str | None
    source_unit_label: str | None
    retrieval_article: str | None
    parent_article: str | None
    metadata_article: str | None
    retrieval_consistency: str
    parent_consistency: str | None
    causal_class: str
    temporal_status: str
    page_start: int | None
    page_end: int | None
    retrieval_subchunk_index: int | None
    retrieval_subchunk_count: int | None
    text_excerpt: str
    parent_excerpt: str | None


def _excerpt(text: str, *, limit: int = 240) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _is_article_unit(chunk: LegalChunk) -> bool:
    metadata = chunk.metadata
    label = metadata.source_unit_label or metadata.legal_identifier
    if extract_article_identifier(label) is not None:
        return True
    return metadata.source_unit_type == "article"


def _canonical_index(chunks: Iterable[LegalChunk]) -> dict[str, LegalChunk]:
    index: dict[str, LegalChunk] = {}
    for chunk in chunks:
        if chunk.chunk_id in index:
            raise NormativeIntegrityAuditError(
                f"chunk_id canónico duplicado: {chunk.chunk_id}"
            )
        index[chunk.chunk_id] = chunk
    return index


def classify_cause(
    retrieval_chunk: LegalChunk,
    canonical_parent: LegalChunk | None,
) -> ParentAuditFinding:
    metadata = retrieval_chunk.metadata
    label = metadata.source_unit_label or metadata.legal_identifier
    retrieval_consistency = compare_article_unit(label, retrieval_chunk.text)

    if not _is_article_unit(retrieval_chunk):
        causal = CausalClass.NON_ARTICLE_UNIT
        parent_consistency: ArticleConsistency | None = None
    elif canonical_parent is None:
        causal = CausalClass.PARENT_MISSING
        parent_consistency = None
    else:
        parent_label = (
            canonical_parent.metadata.source_unit_label
            or canonical_parent.metadata.legal_identifier
        )
        parent_consistency = compare_article_unit(parent_label, canonical_parent.text)

        if parent_consistency == ArticleConsistency.MISMATCH:
            causal = CausalClass.CANONICAL_PARENT_MISMATCH
        elif parent_consistency in {
            ArticleConsistency.METADATA_WITHOUT_ARTICLE,
            ArticleConsistency.TEXT_WITHOUT_ARTICLE,
        }:
            causal = CausalClass.CANONICAL_PARENT_UNVERIFIABLE
        elif retrieval_consistency == ArticleConsistency.MATCH:
            causal = CausalClass.RETRIEVAL_MATCH
        elif retrieval_consistency == ArticleConsistency.TEXT_WITHOUT_ARTICLE:
            causal = CausalClass.RETRIEVAL_CONTINUATION_PARENT_VERIFIED
        elif retrieval_consistency == ArticleConsistency.MISMATCH:
            causal = CausalClass.RETRIEVAL_MISMATCH_PARENT_VERIFIED
        else:
            causal = CausalClass.CANONICAL_PARENT_UNVERIFIABLE

    return ParentAuditFinding(
        chunk_id=retrieval_chunk.chunk_id,
        parent_chunk_id=metadata.parent_chunk_id,
        document_id=metadata.document_id,
        source_unit_type=metadata.source_unit_type,
        source_unit_label=metadata.source_unit_label,
        retrieval_article=extract_article_identifier(retrieval_chunk.text[:800]),
        parent_article=(
            extract_article_identifier(canonical_parent.text[:800])
            if canonical_parent is not None
            else None
        ),
        metadata_article=extract_article_identifier(label),
        retrieval_consistency=retrieval_consistency.value,
        parent_consistency=(
            parent_consistency.value if parent_consistency is not None else None
        ),
        causal_class=causal.value,
        temporal_status=classify_temporal_status(retrieval_chunk),
        page_start=metadata.page_start,
        page_end=metadata.page_end,
        retrieval_subchunk_index=metadata.retrieval_subchunk_index,
        retrieval_subchunk_count=metadata.retrieval_subchunk_count,
        text_excerpt=_excerpt(retrieval_chunk.text),
        parent_excerpt=(
            _excerpt(canonical_parent.text) if canonical_parent is not None else None
        ),
    )


def audit_parent_integrity(
    *,
    retrieval_chunks: Iterable[LegalChunk],
    canonical_chunks: Iterable[LegalChunk],
) -> tuple[list[ParentAuditFinding], dict[str, object]]:
    parent_index = _canonical_index(canonical_chunks)
    findings: list[ParentAuditFinding] = []
    totals: Counter[str] = Counter()
    by_document: dict[str, Counter[str]] = defaultdict(Counter)

    retrieval_total = 0
    normative_total = 0
    for chunk in retrieval_chunks:
        retrieval_total += 1
        if chunk.metadata.source_type != SourceType.NORMATIVA:
            continue
        normative_total += 1
        parent = (
            parent_index.get(chunk.metadata.parent_chunk_id)
            if chunk.metadata.parent_chunk_id is not None
            else None
        )
        finding = classify_cause(chunk, parent)
        findings.append(finding)
        totals[finding.causal_class] += 1
        by_document[finding.document_id][finding.causal_class] += 1

    summary: dict[str, object] = {
        "retrieval_chunks": retrieval_total,
        "normative_chunks": normative_total,
        "canonical_chunks": len(parent_index),
        "causal_counts": dict(sorted(totals.items())),
        "by_document": {
            document_id: dict(sorted(counter.items()))
            for document_id, counter in sorted(by_document.items())
        },
    }
    return findings, summary


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        delete=False,
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def _write_csv(path: Path, findings: list[ParentAuditFinding]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not findings:
        _atomic_write_text(path, "")
        return
    fieldnames = list(asdict(findings[0]).keys())
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8-sig",
        newline="",
        delete=False,
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for finding in findings:
            writer.writerow(asdict(finding))
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def _jsonl(findings: Iterable[ParentAuditFinding]) -> str:
    rows = [
        json.dumps(asdict(finding), ensure_ascii=False, sort_keys=True)
        for finding in findings
    ]
    return ("\n".join(rows) + "\n") if rows else ""


def write_parent_audit_outputs(
    *,
    retrieval_path: Path,
    canonical_path: Path,
    output_dir: Path,
    findings: list[ParentAuditFinding],
    summary: dict[str, object],
) -> dict[str, Path]:
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    repair_19c = [
        f for f in findings
        if f.causal_class == CausalClass.CANONICAL_PARENT_MISMATCH.value
    ]
    repair_19f = [
        f for f in findings
        if f.causal_class == CausalClass.RETRIEVAL_MISMATCH_PARENT_VERIFIED.value
    ]
    parent_review = [
        f for f in findings
        if f.causal_class in {
            CausalClass.CANONICAL_PARENT_UNVERIFIABLE.value,
            CausalClass.PARENT_MISSING.value,
        }
    ]

    report = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "retrieval_file": str(retrieval_path.expanduser().resolve()),
        "retrieval_sha256": _sha256(retrieval_path.expanduser().resolve()),
        "canonical_file": str(canonical_path.expanduser().resolve()),
        "canonical_sha256": _sha256(canonical_path.expanduser().resolve()),
        "policy": {
            "mutates_corpus": False,
            "rebuilds_faiss": False,
            "article_only_causal_analysis": True,
            "rmf_rule_units_are_not_article_failures": True,
        },
        "summary": summary,
    }

    report_path = output_dir / "normative_parent_audit_report.json"
    findings_path = output_dir / "normative_parent_audit_findings.csv"
    repair_19c_path = output_dir / "repair_queue_19c.jsonl"
    repair_19f_path = output_dir / "repair_queue_19f.jsonl"
    parent_review_path = output_dir / "parent_review_queue.jsonl"

    _atomic_write_text(
        report_path,
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _write_csv(findings_path, findings)
    _atomic_write_text(repair_19c_path, _jsonl(repair_19c))
    _atomic_write_text(repair_19f_path, _jsonl(repair_19f))
    _atomic_write_text(parent_review_path, _jsonl(parent_review))

    return {
        "report": report_path,
        "findings": findings_path,
        "repair_19c": repair_19c_path,
        "repair_19f": repair_19f_path,
        "parent_review": parent_review_path,
    }


def run_parent_audit(
    *,
    retrieval_path: Path,
    canonical_path: Path,
    output_dir: Path,
) -> tuple[list[ParentAuditFinding], dict[str, object], dict[str, Path]]:
    try:
        retrieval_chunks = load_chunks_jsonl(retrieval_path)
        canonical_chunks = load_chunks_jsonl(canonical_path)
    except IndexBuildError as exc:
        raise NormativeIntegrityAuditError(str(exc)) from exc

    findings, summary = audit_parent_integrity(
        retrieval_chunks=retrieval_chunks,
        canonical_chunks=canonical_chunks,
    )
    if not findings:
        raise NormativeIntegrityAuditError(
            "No se encontraron subchunks normativos para auditoría causal."
        )

    outputs = write_parent_audit_outputs(
        retrieval_path=retrieval_path,
        canonical_path=canonical_path,
        output_dir=output_dir,
        findings=findings,
        summary=summary,
    )
    return findings, summary, outputs
