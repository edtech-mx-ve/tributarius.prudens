from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from app.domain.legal_chunks import LegalChunk

_TEXTUAL_ORDINAL_RE = re.compile(
    r"(?i)^\s*art[ií]culo\s+"
    r"(primero|segundo|tercero|cuarto|quinto|sexto|s[eé]ptimo|octavo|noveno|"
    r"d[eé]cimo|[uú]nico)\b"
)
_REFERENCE_LIKE_RE = re.compile(
    r"(?i)^\s*art[ií]culo\s+\d+(?:\s*-\s*[a-z0-9áéíóúñ]+)?\s+"
    r"(de|del|que|a|al|en|por|para|con)\b"
)
_NUMERIC_ARTICLE_RE = re.compile(
    r"(?i)^\s*art[ií]culo\s+\d+o?"
    r"(?:\s*-\s*[a-z0-9áéíóúñ]+)*"
    r"(?:\s+(?:bis|ter|qu[aá]ter))?\s*$"
)


class SemanticDeltaAuditError(RuntimeError):
    """Fallo controlado al auditar diferencias semánticas."""


@dataclass(frozen=True)
class RemovedChunkFinding:
    canonical_id: str
    chunk_id: str
    unit_type: str
    unit_label: str
    page_start: int | None
    page_end: int | None
    text_sha256: str
    classification: str
    absorbed_into_candidate_chunk_id: str | None
    excerpt: str


@dataclass(frozen=True)
class AddedChunkFinding:
    canonical_id: str
    chunk_id: str
    unit_type: str
    unit_label: str
    page_start: int | None
    page_end: int | None
    text_sha256: str
    classification: str
    contains_removed_chunk_ids: tuple[str, ...]
    excerpt: str


@dataclass(frozen=True)
class SemanticDeltaAuditReport:
    baseline_path: str
    candidate_path: str
    baseline_sha256: str
    candidate_sha256: str
    baseline_chunks: int
    candidate_chunks: int
    exact_text_preserved: int
    removed_chunks: int
    added_chunks: int
    removed_classifications: dict[str, int]
    added_classifications: dict[str, int]
    removed: tuple[RemovedChunkFinding, ...]
    added: tuple[AddedChunkFinding, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path) -> list[LegalChunk]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise SemanticDeltaAuditError(f"No existe corpus: {resolved}")
    chunks: list[LegalChunk] = []
    try:
        with resolved.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    chunks.append(LegalChunk.model_validate_json(line))
                except ValueError as exc:
                    raise SemanticDeltaAuditError(
                        f"JSONL inválido en {resolved}:{line_number}"
                    ) from exc
    except OSError as exc:
        raise SemanticDeltaAuditError(f"No se pudo leer {resolved}") from exc
    return chunks


def _excerpt(text: str, limit: int = 240) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def _probe(text: str, limit: int = 120) -> str:
    compact = " ".join(text.split())
    return compact[:limit]


def _classify_removed(chunk: LegalChunk, absorbed: bool) -> str:
    label = chunk.unit_label.strip()
    if absorbed:
        if _REFERENCE_LIKE_RE.match(label):
            return "absorbed_reference_like_boundary"
        if _TEXTUAL_ORDINAL_RE.match(label):
            return "absorbed_textual_ordinal"
        if _NUMERIC_ARTICLE_RE.match(label):
            return "absorbed_numeric_article_requires_review"
        return "absorbed_other_boundary"
    if _REFERENCE_LIKE_RE.match(label):
        return "missing_reference_like_boundary"
    if _TEXTUAL_ORDINAL_RE.match(label):
        return "missing_textual_ordinal_requires_review"
    if _NUMERIC_ARTICLE_RE.match(label):
        return "missing_numeric_article_requires_review"
    return "missing_other_requires_review"


def _classify_added(
    chunk: LegalChunk,
    contained_removed: tuple[str, ...],
) -> str:
    if contained_removed:
        return "candidate_merged_baseline_units"
    return "candidate_new_or_resegmented_unit"


def audit_semantic_delta(
    *,
    baseline_path: Path,
    candidate_path: Path,
) -> SemanticDeltaAuditReport:
    baseline_resolved = baseline_path.expanduser().resolve()
    candidate_resolved = candidate_path.expanduser().resolve()
    baseline = _load(baseline_resolved)
    candidate = _load(candidate_resolved)

    candidate_hashes = {chunk.text_sha256 for chunk in candidate}
    baseline_hashes = {chunk.text_sha256 for chunk in baseline}
    exact_text_preserved = sum(
        chunk.text_sha256 in candidate_hashes for chunk in baseline
    )

    removed_chunks = [
        chunk for chunk in baseline if chunk.text_sha256 not in candidate_hashes
    ]
    added_chunks = [
        chunk for chunk in candidate if chunk.text_sha256 not in baseline_hashes
    ]

    candidate_by_doc: dict[str, list[LegalChunk]] = defaultdict(list)
    for chunk in candidate:
        candidate_by_doc[chunk.canonical_id].append(chunk)

    removed_findings: list[RemovedChunkFinding] = []
    removed_to_candidate: dict[str, str] = {}

    for chunk in removed_chunks:
        probe = _probe(chunk.text)
        absorbed_id: str | None = None
        if len(probe) >= 40:
            for candidate_chunk in candidate_by_doc[chunk.canonical_id]:
                if probe in " ".join(candidate_chunk.text.split()):
                    absorbed_id = candidate_chunk.chunk_id
                    removed_to_candidate[chunk.chunk_id] = absorbed_id
                    break

        removed_findings.append(
            RemovedChunkFinding(
                canonical_id=chunk.canonical_id,
                chunk_id=chunk.chunk_id,
                unit_type=chunk.unit_type.value,
                unit_label=chunk.unit_label,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                text_sha256=chunk.text_sha256,
                classification=_classify_removed(
                    chunk,
                    absorbed=absorbed_id is not None,
                ),
                absorbed_into_candidate_chunk_id=absorbed_id,
                excerpt=_excerpt(chunk.text),
            )
        )

    removed_ids_by_candidate: dict[str, list[str]] = defaultdict(list)
    for removed_id, candidate_id in removed_to_candidate.items():
        removed_ids_by_candidate[candidate_id].append(removed_id)

    added_findings: list[AddedChunkFinding] = []
    for chunk in added_chunks:
        contained = tuple(sorted(removed_ids_by_candidate.get(chunk.chunk_id, [])))
        added_findings.append(
            AddedChunkFinding(
                canonical_id=chunk.canonical_id,
                chunk_id=chunk.chunk_id,
                unit_type=chunk.unit_type.value,
                unit_label=chunk.unit_label,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                text_sha256=chunk.text_sha256,
                classification=_classify_added(chunk, contained),
                contains_removed_chunk_ids=contained,
                excerpt=_excerpt(chunk.text),
            )
        )

    removed_counts = Counter(item.classification for item in removed_findings)
    added_counts = Counter(item.classification for item in added_findings)

    return SemanticDeltaAuditReport(
        baseline_path=str(baseline_resolved),
        candidate_path=str(candidate_resolved),
        baseline_sha256=_sha256(baseline_resolved),
        candidate_sha256=_sha256(candidate_resolved),
        baseline_chunks=len(baseline),
        candidate_chunks=len(candidate),
        exact_text_preserved=exact_text_preserved,
        removed_chunks=len(removed_chunks),
        added_chunks=len(added_chunks),
        removed_classifications=dict(sorted(removed_counts.items())),
        added_classifications=dict(sorted(added_counts.items())),
        removed=tuple(removed_findings),
        added=tuple(added_findings),
    )


def write_semantic_delta_outputs(
    *,
    output_dir: Path,
    report: SemanticDeltaAuditReport,
) -> None:
    resolved = output_dir.expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)

    json_path = resolved / "semantic_delta_audit.json"
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
        dir=resolved,
        prefix=".semantic_delta_audit.",
        suffix=".tmp",
    ) as handle:
        handle.write(payload)
        temp_path = Path(handle.name)
    os.replace(temp_path, json_path)

    removed_path = resolved / "removed_units.csv"
    with removed_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(asdict(report.removed[0]).keys())
            if report.removed
            else [
                "canonical_id",
                "chunk_id",
                "unit_type",
                "unit_label",
                "page_start",
                "page_end",
                "text_sha256",
                "classification",
                "absorbed_into_candidate_chunk_id",
                "excerpt",
            ],
        )
        writer.writeheader()
        for removed_item in report.removed:
            writer.writerow(asdict(removed_item))

    added_path = resolved / "added_units.csv"
    with added_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = (
            list(asdict(report.added[0]).keys())
            if report.added
            else [
                "canonical_id",
                "chunk_id",
                "unit_type",
                "unit_label",
                "page_start",
                "page_end",
                "text_sha256",
                "classification",
                "contains_removed_chunk_ids",
                "excerpt",
            ]
        )
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for added_item in report.added:
            row = asdict(added_item)
            row["contains_removed_chunk_ids"] = "|".join(
                added_item.contains_removed_chunk_ids
            )
            writer.writerow(row)
