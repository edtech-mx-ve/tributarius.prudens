from __future__ import annotations

import csv
import json
import os
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from app.domain.legal_chunks import LegalChunk
from app.services.legal_boundary_identity_audit import audit_boundary_identity


class LegalDuplicateBoundaryAuditError(RuntimeError):
    """Error controlado al desambiguar etiquetas legales repetidas."""


@dataclass(frozen=True)
class DuplicateBoundaryFinding:
    canonical_id: str
    baseline_chunk_id: str
    baseline_unit_label: str
    baseline_page_start: int | None
    baseline_page_end: int | None
    candidate_chunk_ids: tuple[str, ...]
    content_matches: tuple[str, ...]
    page_overlap_matches: tuple[str, ...]
    resolved_candidate_chunk_id: str | None
    classification: str
    rationale: str


@dataclass(frozen=True)
class DuplicateBoundaryReport:
    total_ambiguous: int
    resolved_unique_content: int
    resolved_unique_page_overlap: int
    unresolved: int
    classifications: dict[str, int]
    findings: tuple[DuplicateBoundaryFinding, ...]


def _load(path: Path) -> list[LegalChunk]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise LegalDuplicateBoundaryAuditError(f"No existe corpus: {resolved}")
    chunks: list[LegalChunk] = []
    with resolved.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                chunks.append(LegalChunk.model_validate_json(line))
            except ValueError as exc:
                raise LegalDuplicateBoundaryAuditError(
                    f"JSONL inválido en {resolved}:{line_number}"
                ) from exc
    return chunks


def _compact(text: str) -> str:
    return " ".join(text.split())


def _full_content_match(old: LegalChunk, candidate: LegalChunk) -> bool:
    old_text = _compact(old.text)
    candidate_text = _compact(candidate.text)
    return bool(old_text and old_text in candidate_text)


def _prefix_probe_match(
    old: LegalChunk,
    candidate: LegalChunk,
    *,
    probe_chars: int = 160,
) -> bool:
    old_text = _compact(old.text)
    candidate_text = _compact(candidate.text)
    if len(old_text) < 80:
        return False
    probe = old_text[:probe_chars]
    return probe in candidate_text


def _page_overlap(old: LegalChunk, candidate: LegalChunk) -> bool:
    if (
        old.page_start is None
        or old.page_end is None
        or candidate.page_start is None
        or candidate.page_end is None
    ):
        return False
    return not (
        old.page_end < candidate.page_start
        or candidate.page_end < old.page_start
    )


def audit_duplicate_boundaries(
    *,
    baseline_path: Path,
    candidate_path: Path,
) -> DuplicateBoundaryReport:
    identity = audit_boundary_identity(
        baseline_path=baseline_path,
        candidate_path=candidate_path,
    )
    baseline = _load(baseline_path)
    candidate = _load(candidate_path)

    baseline_by_id = {chunk.chunk_id: chunk for chunk in baseline}
    candidate_by_id = {chunk.chunk_id: chunk for chunk in candidate}

    ambiguous = [
        item
        for item in identity.findings
        if item.classification == "boundary_ambiguous_duplicate_label"
    ]

    findings: list[DuplicateBoundaryFinding] = []
    for item in ambiguous:
        old = baseline_by_id[item.baseline_chunk_id]
        candidates = [
            candidate_by_id[chunk_id]
            for chunk_id in item.candidate_chunk_ids
            if chunk_id in candidate_by_id
        ]

        full_content_matches = tuple(
            chunk.chunk_id
            for chunk in candidates
            if _full_content_match(old, chunk)
        )
        prefix_probe_matches = tuple(
            chunk.chunk_id
            for chunk in candidates
            if _prefix_probe_match(old, chunk)
        )
        page_matches = tuple(
            chunk.chunk_id
            for chunk in candidates
            if _page_overlap(old, chunk)
        )

        resolved: str | None = None
        content_matches: tuple[str, ...]
        if len(full_content_matches) == 1:
            resolved = full_content_matches[0]
            content_matches = full_content_matches
            classification = "resolved_unique_full_content"
            rationale = (
                "Una sola candidata con igual etiqueta contiene íntegramente "
                "el texto normalizado de la unidad 19C."
            )
        elif len(full_content_matches) > 1:
            content_matches = full_content_matches
            classification = "unresolved_multiple_full_content_matches"
            rationale = (
                "Más de una candidata contiene íntegramente la unidad 19C."
            )
        elif len(page_matches) == 1:
            resolved = page_matches[0]
            content_matches = prefix_probe_matches
            classification = "resolved_unique_page_overlap"
            rationale = (
                "No hubo contención textual completa; una sola candidata "
                "se solapa con el rango de páginas 19C."
            )
        elif len(prefix_probe_matches) == 1:
            resolved = prefix_probe_matches[0]
            content_matches = prefix_probe_matches
            classification = "resolved_unique_prefix_probe"
            rationale = (
                "Sin contención completa ni página única, una sola candidata "
                "conserva un prefijo sustantivo de la unidad 19C."
            )
        elif len(prefix_probe_matches) > 1:
            content_matches = prefix_probe_matches
            classification = "unresolved_multiple_prefix_probe_matches"
            rationale = (
                "Varias candidatas comparten el prefijo sustantivo de 19C."
            )
        elif len(page_matches) > 1:
            content_matches = ()
            classification = "unresolved_multiple_page_overlaps"
            rationale = (
                "Varias candidatas con igual etiqueta se solapan con las "
                "páginas de la unidad 19C."
            )
        else:
            content_matches = ()
            classification = "unresolved_no_unique_evidence"
            rationale = (
                "No existe evidencia suficiente para resolver automáticamente."
            )

        findings.append(
            DuplicateBoundaryFinding(
                canonical_id=old.canonical_id,
                baseline_chunk_id=old.chunk_id,
                baseline_unit_label=old.unit_label,
                baseline_page_start=old.page_start,
                baseline_page_end=old.page_end,
                candidate_chunk_ids=tuple(chunk.chunk_id for chunk in candidates),
                content_matches=content_matches,
                page_overlap_matches=page_matches,
                resolved_candidate_chunk_id=resolved,
                classification=classification,
                rationale=rationale,
            )
        )

    counts = Counter(item.classification for item in findings)
    return DuplicateBoundaryReport(
        total_ambiguous=len(findings),
        resolved_unique_content=(
            counts.get("resolved_unique_full_content", 0)
            + counts.get("resolved_unique_prefix_probe", 0)
        ),
        resolved_unique_page_overlap=counts.get(
            "resolved_unique_page_overlap",
            0,
        ),
        unresolved=sum(
            value for key, value in counts.items() if key.startswith("unresolved_")
        ),
        classifications=dict(sorted(counts.items())),
        findings=tuple(findings),
    )


def write_duplicate_boundary_outputs(
    *,
    output_dir: Path,
    report: DuplicateBoundaryReport,
) -> None:
    resolved = output_dir.expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(
        asdict(report),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    json_path = resolved / "duplicate_boundary_audit.json"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=resolved,
        prefix=".duplicate_boundary_audit.",
        suffix=".tmp",
    ) as handle:
        handle.write(payload)
        temp_path = Path(handle.name)
    os.replace(temp_path, json_path)

    csv_path = resolved / "duplicate_boundary_findings.csv"
    fields = (
        list(asdict(report.findings[0]).keys())
        if report.findings
        else [
            "canonical_id",
            "baseline_chunk_id",
            "baseline_unit_label",
            "baseline_page_start",
            "baseline_page_end",
            "candidate_chunk_ids",
            "content_matches",
            "page_overlap_matches",
            "resolved_candidate_chunk_id",
            "classification",
            "rationale",
        ]
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for finding in report.findings:
            row = asdict(finding)
            row["candidate_chunk_ids"] = "|".join(finding.candidate_chunk_ids)
            row["content_matches"] = "|".join(finding.content_matches)
            row["page_overlap_matches"] = "|".join(finding.page_overlap_matches)
            writer.writerow(row)
