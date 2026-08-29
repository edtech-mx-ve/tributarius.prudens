from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from app.domain.chunks import LegalChunk
from app.domain.documents import SourceType
from app.services.legal_unit_integrity import (
    ArticleConsistency,
    compare_article_unit,
    extract_article_identifier,
)
from rag.indexing.builder import IndexBuildError, load_chunks_jsonl


class NormativeIntegrityAuditError(RuntimeError):
    """Error controlado durante la auditoría normativa."""


@dataclass(frozen=True)
class IntegrityFinding:
    chunk_id: str
    parent_chunk_id: str | None
    document_id: str
    source_filename: str
    source_unit_label: str | None
    legal_identifier: str | None
    metadata_article: str | None
    text_article: str | None
    article_consistency: str
    version_label: str | None
    fiscal_year: int | None
    publication_date: str | None
    last_reform_date: str | None
    effective_from: str | None
    effective_to: str | None
    temporal_status: str
    promotion_eligible: bool
    page_start: int | None
    page_end: int | None
    text_excerpt: str


def _parse_iso_date(value: str | None) -> date | None:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def classify_temporal_status(chunk: LegalChunk) -> str:
    metadata = chunk.metadata
    start_raw = metadata.effective_from
    end_raw = metadata.effective_to

    start = _parse_iso_date(start_raw)
    end = _parse_iso_date(end_raw)

    if start_raw and start is None:
        return "invalid"
    if end_raw and end is None:
        return "invalid"
    if start is not None and end is not None and end < start:
        return "invalid"
    if start is not None and end is not None:
        return "bounded"
    if start is not None:
        return "open_end"
    if end is not None:
        return "open_start"
    return "unknown"


def _excerpt(text: str, *, limit: int = 280) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def analyze_normative_chunk(chunk: LegalChunk) -> IntegrityFinding:
    metadata = chunk.metadata
    label = metadata.source_unit_label or metadata.legal_identifier
    consistency = compare_article_unit(label, chunk.text)
    temporal_status = classify_temporal_status(chunk)

    # Replica las condiciones estructurales del puente 19I.2 sin promover
    # realmente el chunk. `text_without_article` no prueba correspondencia,
    # pero tampoco constituye contradicción.
    promotion_eligible = (
        bool(metadata.version_label)
        and consistency != ArticleConsistency.MISMATCH
        and temporal_status in {"bounded", "open_end", "open_start"}
    )

    return IntegrityFinding(
        chunk_id=chunk.chunk_id,
        parent_chunk_id=metadata.parent_chunk_id,
        document_id=metadata.document_id,
        source_filename=metadata.source_filename,
        source_unit_label=metadata.source_unit_label,
        legal_identifier=metadata.legal_identifier,
        metadata_article=extract_article_identifier(label),
        text_article=extract_article_identifier(chunk.text[:800]),
        article_consistency=consistency.value,
        version_label=metadata.version_label,
        fiscal_year=metadata.fiscal_year,
        publication_date=metadata.publication_date,
        last_reform_date=metadata.last_reform_date,
        effective_from=metadata.effective_from,
        effective_to=metadata.effective_to,
        temporal_status=temporal_status,
        promotion_eligible=promotion_eligible,
        page_start=metadata.page_start,
        page_end=metadata.page_end,
        text_excerpt=_excerpt(chunk.text),
    )


def _empty_counts() -> dict[str, int]:
    return {
        "normative_chunks": 0,
        "article_match": 0,
        "article_mismatch": 0,
        "metadata_without_article": 0,
        "text_without_article": 0,
        "temporal_bounded": 0,
        "temporal_open_end": 0,
        "temporal_open_start": 0,
        "temporal_unknown": 0,
        "temporal_invalid": 0,
        "promotion_eligible": 0,
    }


def _accumulate(counts: dict[str, int], finding: IntegrityFinding) -> None:
    counts["normative_chunks"] += 1

    article_key = {
        "match": "article_match",
        "mismatch": "article_mismatch",
        "metadata_without_article": "metadata_without_article",
        "text_without_article": "text_without_article",
    }.get(finding.article_consistency)
    if article_key is None:
        raise NormativeIntegrityAuditError(
            f"Estado de consistencia de artículo no soportado: "
            f"{finding.article_consistency!r}."
        )
    counts[article_key] += 1

    temporal_key = f"temporal_{finding.temporal_status}"
    if temporal_key not in counts:
        raise NormativeIntegrityAuditError(
            f"Estado temporal no soportado: {finding.temporal_status!r}."
        )
    counts[temporal_key] += 1

    if finding.promotion_eligible:
        counts["promotion_eligible"] += 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_normative_chunks(
    chunks: Iterable[LegalChunk],
) -> tuple[list[IntegrityFinding], dict[str, object]]:
    findings: list[IntegrityFinding] = []
    totals = _empty_counts()
    by_document: dict[str, dict[str, int]] = defaultdict(_empty_counts)
    total_chunks = 0

    for chunk in chunks:
        total_chunks += 1
        if chunk.metadata.source_type != SourceType.NORMATIVA:
            continue
        finding = analyze_normative_chunk(chunk)
        findings.append(finding)
        _accumulate(totals, finding)
        _accumulate(by_document[finding.document_id], finding)

    summary: dict[str, object] = {
        "total_chunks": total_chunks,
        **totals,
        "normative_documents": len(by_document),
        "by_document": {
            key: dict(value) for key, value in sorted(by_document.items())
        },
    }
    return findings, summary


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


def _write_csv(path: Path, findings: list[IntegrityFinding]) -> None:
    if not findings:
        _atomic_write_text(path, "")
        return
    fieldnames = list(asdict(findings[0]).keys())
    path.parent.mkdir(parents=True, exist_ok=True)
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


def _jsonl(findings: Iterable[IntegrityFinding]) -> str:
    rows = [
        json.dumps(asdict(finding), ensure_ascii=False, sort_keys=True)
        for finding in findings
    ]
    return ("\n".join(rows) + "\n") if rows else ""


def write_audit_outputs(
    *,
    input_path: Path,
    output_dir: Path,
    findings: list[IntegrityFinding],
    summary: dict[str, object],
) -> dict[str, Path]:
    resolved_input = input_path.expanduser().resolve()
    resolved_output = output_dir.expanduser().resolve()
    resolved_output.mkdir(parents=True, exist_ok=True)

    mismatch = [
        finding
        for finding in findings
        if finding.article_consistency == ArticleConsistency.MISMATCH.value
    ]
    temporal_backlog = [
        finding
        for finding in findings
        if finding.temporal_status in {"unknown", "invalid"}
    ]

    report = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "input_file": str(resolved_input),
        "input_sha256": _sha256(resolved_input),
        "policy": {
            "mutates_corpus": False,
            "last_reform_is_not_effective_from": True,
            "publication_date_is_not_effective_from": True,
            "mismatch_action": "quarantine_candidate",
            "temporal_unknown_action": "verified_enrichment_required",
        },
        "summary": summary,
    }

    report_path = resolved_output / "normative_integrity_report.json"
    findings_path = resolved_output / "normative_integrity_findings.csv"
    quarantine_path = resolved_output / "normative_quarantine.jsonl"
    temporal_path = resolved_output / "normative_temporal_enrichment.jsonl"

    _atomic_write_text(
        report_path,
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _write_csv(findings_path, findings)
    _atomic_write_text(quarantine_path, _jsonl(mismatch))
    _atomic_write_text(temporal_path, _jsonl(temporal_backlog))

    return {
        "report": report_path,
        "findings": findings_path,
        "quarantine": quarantine_path,
        "temporal_backlog": temporal_path,
    }


def run_audit(
    *,
    input_path: Path,
    output_dir: Path,
) -> tuple[list[IntegrityFinding], dict[str, object], dict[str, Path]]:
    try:
        chunks = load_chunks_jsonl(input_path)
    except IndexBuildError as exc:
        raise NormativeIntegrityAuditError(str(exc)) from exc

    findings, summary = audit_normative_chunks(chunks)
    if not findings:
        raise NormativeIntegrityAuditError(
            "El archivo no contiene chunks con source_type=normativa."
        )
    outputs = write_audit_outputs(
        input_path=input_path,
        output_dir=output_dir,
        findings=findings,
        summary=summary,
    )
    return findings, summary, outputs
