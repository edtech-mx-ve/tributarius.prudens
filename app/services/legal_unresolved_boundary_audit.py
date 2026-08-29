from __future__ import annotations

import csv
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from app.domain.legal_chunks import LegalChunk
from app.services.legal_duplicate_boundary_audit import (
    audit_duplicate_boundaries,
)


class LegalUnresolvedBoundaryAuditError(RuntimeError):
    """Error controlado al inspeccionar fronteras duplicadas no resueltas."""


@dataclass(frozen=True)
class CandidateEvidence:
    chunk_id: str
    unit_label: str
    page_start: int | None
    page_end: int | None
    text_sha256: str
    contains_baseline_text: bool
    baseline_contains_candidate_text: bool
    shared_prefix_chars: int
    excerpt: str


@dataclass(frozen=True)
class UnresolvedBoundaryFinding:
    canonical_id: str
    baseline_chunk_id: str
    baseline_unit_label: str
    baseline_page_start: int | None
    baseline_page_end: int | None
    baseline_text_sha256: str
    baseline_excerpt: str
    candidate_evidence: tuple[CandidateEvidence, ...]
    classification: str


@dataclass(frozen=True)
class UnresolvedBoundaryReport:
    total_unresolved: int
    findings: tuple[UnresolvedBoundaryFinding, ...]


def _load(path: Path) -> list[LegalChunk]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise LegalUnresolvedBoundaryAuditError(f"No existe corpus: {resolved}")
    chunks: list[LegalChunk] = []
    with resolved.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                chunks.append(LegalChunk.model_validate_json(line))
            except ValueError as exc:
                raise LegalUnresolvedBoundaryAuditError(
                    f"JSONL inválido en {resolved}:{line_number}"
                ) from exc
    return chunks


def _compact(text: str) -> str:
    return " ".join(text.split())


def _excerpt(text: str, limit: int = 420) -> str:
    compact = _compact(text)
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def _shared_prefix_chars(left: str, right: str) -> int:
    left_compact = _compact(left)
    right_compact = _compact(right)
    limit = min(len(left_compact), len(right_compact))
    index = 0
    while index < limit and left_compact[index] == right_compact[index]:
        index += 1
    return index


def audit_unresolved_boundaries(
    *,
    baseline_path: Path,
    candidate_path: Path,
) -> UnresolvedBoundaryReport:
    duplicate_report = audit_duplicate_boundaries(
        baseline_path=baseline_path,
        candidate_path=candidate_path,
    )
    baseline = _load(baseline_path)
    candidate = _load(candidate_path)
    baseline_by_id = {chunk.chunk_id: chunk for chunk in baseline}
    candidate_by_id = {chunk.chunk_id: chunk for chunk in candidate}

    unresolved = [
        item
        for item in duplicate_report.findings
        if item.classification.startswith("unresolved_")
    ]

    findings: list[UnresolvedBoundaryFinding] = []
    for item in unresolved:
        old = baseline_by_id.get(item.baseline_chunk_id)
        if old is None:
            raise LegalUnresolvedBoundaryAuditError(
                f"No existe chunk baseline: {item.baseline_chunk_id}"
            )

        old_text = _compact(old.text)
        evidences: list[CandidateEvidence] = []
        for candidate_id in item.candidate_chunk_ids:
            current = candidate_by_id.get(candidate_id)
            if current is None:
                continue
            current_text = _compact(current.text)
            evidences.append(
                CandidateEvidence(
                    chunk_id=current.chunk_id,
                    unit_label=current.unit_label,
                    page_start=current.page_start,
                    page_end=current.page_end,
                    text_sha256=current.text_sha256,
                    contains_baseline_text=bool(
                        old_text and old_text in current_text
                    ),
                    baseline_contains_candidate_text=bool(
                        current_text and current_text in old_text
                    ),
                    shared_prefix_chars=_shared_prefix_chars(
                        old.text,
                        current.text,
                    ),
                    excerpt=_excerpt(current.text),
                )
            )

        findings.append(
            UnresolvedBoundaryFinding(
                canonical_id=old.canonical_id,
                baseline_chunk_id=old.chunk_id,
                baseline_unit_label=old.unit_label,
                baseline_page_start=old.page_start,
                baseline_page_end=old.page_end,
                baseline_text_sha256=old.text_sha256,
                baseline_excerpt=_excerpt(old.text),
                candidate_evidence=tuple(evidences),
                classification=item.classification,
            )
        )

    return UnresolvedBoundaryReport(
        total_unresolved=len(findings),
        findings=tuple(findings),
    )


def write_unresolved_boundary_outputs(
    *,
    output_dir: Path,
    report: UnresolvedBoundaryReport,
) -> None:
    resolved = output_dir.expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(
        asdict(report),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    json_path = resolved / "unresolved_boundary_audit.json"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=resolved,
        prefix=".unresolved_boundary_audit.",
        suffix=".tmp",
    ) as handle:
        handle.write(payload)
        temp_path = Path(handle.name)
    os.replace(temp_path, json_path)

    csv_path = resolved / "unresolved_boundary_candidates.csv"
    fields = [
        "canonical_id",
        "baseline_chunk_id",
        "baseline_unit_label",
        "baseline_page_start",
        "baseline_page_end",
        "classification",
        "candidate_chunk_id",
        "candidate_unit_label",
        "candidate_page_start",
        "candidate_page_end",
        "contains_baseline_text",
        "baseline_contains_candidate_text",
        "shared_prefix_chars",
        "baseline_excerpt",
        "candidate_excerpt",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for finding in report.findings:
            for evidence in finding.candidate_evidence:
                writer.writerow(
                    {
                        "canonical_id": finding.canonical_id,
                        "baseline_chunk_id": finding.baseline_chunk_id,
                        "baseline_unit_label": finding.baseline_unit_label,
                        "baseline_page_start": finding.baseline_page_start,
                        "baseline_page_end": finding.baseline_page_end,
                        "classification": finding.classification,
                        "candidate_chunk_id": evidence.chunk_id,
                        "candidate_unit_label": evidence.unit_label,
                        "candidate_page_start": evidence.page_start,
                        "candidate_page_end": evidence.page_end,
                        "contains_baseline_text": evidence.contains_baseline_text,
                        "baseline_contains_candidate_text": (
                            evidence.baseline_contains_candidate_text
                        ),
                        "shared_prefix_chars": evidence.shared_prefix_chars,
                        "baseline_excerpt": finding.baseline_excerpt,
                        "candidate_excerpt": evidence.excerpt,
                    }
                )
