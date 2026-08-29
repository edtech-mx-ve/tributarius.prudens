from __future__ import annotations

import csv
import hashlib
import json
import os
import re
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
    normalize_article_identifier,
)
from app.services.normative_integrity_audit import NormativeIntegrityAuditError
from rag.indexing.builder import IndexBuildError, load_chunks_jsonl

_ARTICLE_MENTION_RE = re.compile(
    r"\bart(?:í|i)culo\s+"
    r"([0-9]+o?(?:-[a-z0-9]+)*(?:\s*(?:bis|ter|qu[aá]ter))?)"
    r"(?=[\s\.,;:\)\]-]|$)",
    re.IGNORECASE,
)

# Encabezado fuerte: debe iniciar una línea y presentar un separador típico de
# encabezado legal tras el identificador. Evita tratar "Artículo 5 de la Ley..."
# como un nuevo límite cuando es una referencia cruzada en el cuerpo.
_ARTICLE_HEADING_RE = re.compile(
    r"(?im)^[ \t]*(?:#{1,6}[ \t]+)?art(?:í|i)culo\s+"
    r"(?P<identifier>"
    r"[0-9]+o?(?:-[a-z0-9]+)*(?:\s*(?:bis|ter|qu[aá]ter))?"
    r")"
    r"(?P<separator>[ \t]*(?:\.-|\.|—|–|-(?![a-z0-9])|:))[ \t]*",
)


class BoundaryRefinementClass(StrEnum):
    NON_ARTICLE_UNIT = "non_article_unit"
    RETRIEVAL_MATCH = "retrieval_match"
    RETRIEVAL_CONTINUATION = "retrieval_continuation"
    TRUE_SECONDARY_ARTICLE_BOUNDARY = "true_secondary_article_boundary"
    CROSS_REFERENCE_FALSE_POSITIVE = "cross_reference_false_positive"
    CANONICAL_PARENT_START_MISMATCH = "canonical_parent_start_mismatch"
    UNRESOLVED = "unresolved"
    PARENT_MISSING = "parent_missing"


@dataclass(frozen=True)
class ArticleHeading:
    identifier: str
    start: int
    end: int
    raw: str


@dataclass(frozen=True)
class BoundaryRefinementFinding:
    chunk_id: str
    parent_chunk_id: str | None
    document_id: str
    source_unit_label: str | None
    metadata_article: str | None
    first_article_mention: str | None
    first_strong_heading: str | None
    first_strong_heading_offset: int | None
    parent_first_heading: str | None
    parent_secondary_headings: tuple[str, ...]
    retrieval_consistency: str
    parent_consistency: str | None
    refinement_class: str
    retrieval_subchunk_index: int | None
    retrieval_subchunk_count: int | None
    page_start: int | None
    page_end: int | None
    text_excerpt: str
    parent_excerpt: str | None


def _excerpt(text: str, *, limit: int = 260) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def find_article_headings(text: str) -> tuple[ArticleHeading, ...]:
    """Localiza encabezados fuertes de artículo anclados al inicio de línea."""
    headings: list[ArticleHeading] = []
    for match in _ARTICLE_HEADING_RE.finditer(text):
        identifier = normalize_article_identifier(match.group("identifier"))
        headings.append(
            ArticleHeading(
                identifier=identifier,
                start=match.start(),
                end=match.end(),
                raw=match.group(0).strip(),
            )
        )
    return tuple(headings)


def _first_article_mention(text: str, *, prefix_chars: int = 800) -> str | None:
    match = _ARTICLE_MENTION_RE.search(text[:prefix_chars])
    if match is None:
        return None
    return normalize_article_identifier(match.group(1))


def _metadata_article(chunk: LegalChunk) -> str | None:
    label = chunk.metadata.source_unit_label or chunk.metadata.legal_identifier
    return extract_article_identifier(label)


def _is_article_unit(chunk: LegalChunk) -> bool:
    if _metadata_article(chunk) is not None:
        return True
    return chunk.metadata.source_unit_type == "article"


def _starts_at_strong_heading(
    heading: ArticleHeading | None,
    *,
    max_prefix_chars: int,
) -> bool:
    return heading is not None and heading.start <= max_prefix_chars


def refine_boundary_cause(
    retrieval_chunk: LegalChunk,
    canonical_parent: LegalChunk | None,
    *,
    heading_prefix_chars: int = 160,
) -> BoundaryRefinementFinding:
    """Refina el falso positivo de 19I.4 usando límites jurídicos fuertes.

    Un artículo citado dentro del cuerpo no constituye por sí mismo un nuevo
    límite. Un encabezado fuerte distinto al esperado, al inicio del subchunk y
    también presente como encabezado secundario del padre, sí constituye
    evidencia estructural de que el padre canónico abarca más de un artículo.
    """
    if heading_prefix_chars < 0:
        raise ValueError("heading_prefix_chars debe ser >= 0.")

    metadata = retrieval_chunk.metadata
    metadata_article = _metadata_article(retrieval_chunk)
    retrieval_consistency = compare_article_unit(
        metadata.source_unit_label or metadata.legal_identifier,
        retrieval_chunk.text,
    )
    retrieval_headings = find_article_headings(retrieval_chunk.text)
    first_heading = retrieval_headings[0] if retrieval_headings else None
    first_mention = _first_article_mention(retrieval_chunk.text)

    parent_consistency: ArticleConsistency | None = None
    parent_headings: tuple[ArticleHeading, ...] = ()
    parent_first_heading: ArticleHeading | None = None
    parent_secondary: tuple[ArticleHeading, ...] = ()

    if canonical_parent is not None:
        parent_label = (
            canonical_parent.metadata.source_unit_label
            or canonical_parent.metadata.legal_identifier
        )
        parent_consistency = compare_article_unit(parent_label, canonical_parent.text)
        parent_headings = find_article_headings(canonical_parent.text)
        parent_first_heading = parent_headings[0] if parent_headings else None
        if metadata_article is not None:
            parent_secondary = tuple(
                heading
                for heading in parent_headings
                if heading.identifier != metadata_article
            )

    if not _is_article_unit(retrieval_chunk):
        refinement = BoundaryRefinementClass.NON_ARTICLE_UNIT
    elif canonical_parent is None:
        refinement = BoundaryRefinementClass.PARENT_MISSING
    elif parent_consistency == ArticleConsistency.MISMATCH:
        refinement = BoundaryRefinementClass.CANONICAL_PARENT_START_MISMATCH
    elif retrieval_consistency == ArticleConsistency.MATCH:
        refinement = BoundaryRefinementClass.RETRIEVAL_MATCH
    elif retrieval_consistency == ArticleConsistency.TEXT_WITHOUT_ARTICLE:
        refinement = BoundaryRefinementClass.RETRIEVAL_CONTINUATION
    elif retrieval_consistency == ArticleConsistency.MISMATCH:
        first_heading_is_boundary = (
            first_heading is not None
            and metadata_article is not None
            and first_heading.identifier != metadata_article
            and _starts_at_strong_heading(
                first_heading,
                max_prefix_chars=heading_prefix_chars,
            )
            and any(
                heading.identifier == first_heading.identifier
                for heading in parent_secondary
            )
        )
        if first_heading_is_boundary:
            refinement = BoundaryRefinementClass.TRUE_SECONDARY_ARTICLE_BOUNDARY
        elif first_mention is not None and (
            first_heading is None
            or first_heading.start > heading_prefix_chars
            or first_heading.identifier == metadata_article
        ):
            refinement = BoundaryRefinementClass.CROSS_REFERENCE_FALSE_POSITIVE
        else:
            refinement = BoundaryRefinementClass.UNRESOLVED
    else:
        refinement = BoundaryRefinementClass.UNRESOLVED

    return BoundaryRefinementFinding(
        chunk_id=retrieval_chunk.chunk_id,
        parent_chunk_id=metadata.parent_chunk_id,
        document_id=metadata.document_id,
        source_unit_label=metadata.source_unit_label,
        metadata_article=metadata_article,
        first_article_mention=first_mention,
        first_strong_heading=(
            first_heading.identifier if first_heading is not None else None
        ),
        first_strong_heading_offset=(
            first_heading.start if first_heading is not None else None
        ),
        parent_first_heading=(
            parent_first_heading.identifier
            if parent_first_heading is not None
            else None
        ),
        parent_secondary_headings=tuple(
            heading.identifier for heading in parent_secondary
        ),
        retrieval_consistency=retrieval_consistency.value,
        parent_consistency=(
            parent_consistency.value if parent_consistency is not None else None
        ),
        refinement_class=refinement.value,
        retrieval_subchunk_index=metadata.retrieval_subchunk_index,
        retrieval_subchunk_count=metadata.retrieval_subchunk_count,
        page_start=metadata.page_start,
        page_end=metadata.page_end,
        text_excerpt=_excerpt(retrieval_chunk.text),
        parent_excerpt=(
            _excerpt(canonical_parent.text) if canonical_parent is not None else None
        ),
    )


def _canonical_index(chunks: Iterable[LegalChunk]) -> dict[str, LegalChunk]:
    index: dict[str, LegalChunk] = {}
    for chunk in chunks:
        if chunk.chunk_id in index:
            raise NormativeIntegrityAuditError(
                f"chunk_id canónico duplicado: {chunk.chunk_id}"
            )
        index[chunk.chunk_id] = chunk
    return index


def audit_boundary_refinement(
    *,
    retrieval_chunks: Iterable[LegalChunk],
    canonical_chunks: Iterable[LegalChunk],
) -> tuple[list[BoundaryRefinementFinding], dict[str, object]]:
    parent_index = _canonical_index(canonical_chunks)
    findings: list[BoundaryRefinementFinding] = []
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
        finding = refine_boundary_cause(chunk, parent)
        findings.append(finding)
        totals[finding.refinement_class] += 1
        by_document[finding.document_id][finding.refinement_class] += 1

    summary: dict[str, object] = {
        "retrieval_chunks": retrieval_total,
        "normative_chunks": normative_total,
        "canonical_chunks": len(parent_index),
        "refinement_counts": dict(sorted(totals.items())),
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


def _write_csv(
    path: Path,
    findings: list[BoundaryRefinementFinding],
) -> None:
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
            row = asdict(finding)
            row["parent_secondary_headings"] = "|".join(
                finding.parent_secondary_headings
            )
            writer.writerow(row)
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def _jsonl(findings: Iterable[BoundaryRefinementFinding]) -> str:
    rows = [
        json.dumps(asdict(finding), ensure_ascii=False, sort_keys=True)
        for finding in findings
    ]
    return ("\n".join(rows) + "\n") if rows else ""


def write_boundary_refinement_outputs(
    *,
    retrieval_path: Path,
    canonical_path: Path,
    output_dir: Path,
    findings: list[BoundaryRefinementFinding],
    summary: dict[str, object],
) -> dict[str, Path]:
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    boundary_queue = [
        finding
        for finding in findings
        if finding.refinement_class
        == BoundaryRefinementClass.TRUE_SECONDARY_ARTICLE_BOUNDARY.value
    ]
    cross_reference_queue = [
        finding
        for finding in findings
        if finding.refinement_class
        == BoundaryRefinementClass.CROSS_REFERENCE_FALSE_POSITIVE.value
    ]
    canonical_start_queue = [
        finding
        for finding in findings
        if finding.refinement_class
        == BoundaryRefinementClass.CANONICAL_PARENT_START_MISMATCH.value
    ]
    unresolved_queue = [
        finding
        for finding in findings
        if finding.refinement_class
        in {
            BoundaryRefinementClass.UNRESOLVED.value,
            BoundaryRefinementClass.PARENT_MISSING.value,
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
            "strong_heading_must_be_line_anchored": True,
            "cross_reference_is_not_boundary": True,
            "repair_requires_evidence": True,
        },
        "summary": summary,
    }

    report_path = output_dir / "legal_boundary_refinement_report.json"
    findings_path = output_dir / "legal_boundary_refinement_findings.csv"
    boundary_path = output_dir / "true_secondary_boundaries.jsonl"
    cross_reference_path = output_dir / "cross_reference_false_positives.jsonl"
    canonical_start_path = output_dir / "canonical_start_mismatches.jsonl"
    unresolved_path = output_dir / "unresolved_boundaries.jsonl"

    _atomic_write_text(
        report_path,
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _write_csv(findings_path, findings)
    _atomic_write_text(boundary_path, _jsonl(boundary_queue))
    _atomic_write_text(cross_reference_path, _jsonl(cross_reference_queue))
    _atomic_write_text(canonical_start_path, _jsonl(canonical_start_queue))
    _atomic_write_text(unresolved_path, _jsonl(unresolved_queue))

    return {
        "report": report_path,
        "findings": findings_path,
        "true_boundaries": boundary_path,
        "cross_references": cross_reference_path,
        "canonical_start": canonical_start_path,
        "unresolved": unresolved_path,
    }


def run_boundary_refinement(
    *,
    retrieval_path: Path,
    canonical_path: Path,
    output_dir: Path,
) -> tuple[
    list[BoundaryRefinementFinding],
    dict[str, object],
    dict[str, Path],
]:
    try:
        retrieval_chunks = load_chunks_jsonl(retrieval_path)
        canonical_chunks = load_chunks_jsonl(canonical_path)
    except IndexBuildError as exc:
        raise NormativeIntegrityAuditError(str(exc)) from exc

    findings, summary = audit_boundary_refinement(
        retrieval_chunks=retrieval_chunks,
        canonical_chunks=canonical_chunks,
    )
    if not findings:
        raise NormativeIntegrityAuditError(
            "No se encontraron subchunks normativos para refinamiento."
        )

    outputs = write_boundary_refinement_outputs(
        retrieval_path=retrieval_path,
        canonical_path=canonical_path,
        output_dir=output_dir,
        findings=findings,
        summary=summary,
    )
    return findings, summary, outputs
