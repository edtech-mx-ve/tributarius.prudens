from __future__ import annotations

import csv
import json
import os
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from app.domain.legal_chunks import LegalChunk
from app.services.absorbed_numeric_audit import audit_absorbed_numeric
from app.services.semantic_delta_audit import audit_semantic_delta


class SemanticResidualAuditError(RuntimeError):
    """Error controlado al auditar residuos semánticos del candidato 19I.7."""


@dataclass(frozen=True)
class ResidualFinding:
    source_audit: str
    original_classification: str
    canonical_id: str
    baseline_chunk_id: str
    unit_label: str
    page_start: int | None
    page_end: int | None
    candidate_contains_baseline: bool
    candidate_container_ids: tuple[str, ...]
    classification: str


@dataclass(frozen=True)
class SemanticResidualReport:
    total_residuals: int
    safe_absorptions: int
    requires_review: int
    classifications: dict[str, int]
    findings: tuple[ResidualFinding, ...]


def _load(path: Path) -> list[LegalChunk]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise SemanticResidualAuditError(f"No existe corpus: {resolved}")
    chunks: list[LegalChunk] = []
    with resolved.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                chunks.append(LegalChunk.model_validate_json(line))
            except ValueError as exc:
                raise SemanticResidualAuditError(
                    f"JSONL inválido en {resolved}:{line_number}"
                ) from exc
    return chunks


def _compact(value: str) -> str:
    return " ".join(value.split())


def _containers(old: LegalChunk, candidates: list[LegalChunk]) -> tuple[str, ...]:
    old_text = _compact(old.text)
    if not old_text:
        return ()
    return tuple(
        chunk.chunk_id
        for chunk in candidates
        if chunk.canonical_id == old.canonical_id
        and old_text in _compact(chunk.text)
    )


def audit_semantic_residuals(
    *,
    baseline_path: Path,
    candidate_path: Path,
) -> SemanticResidualReport:
    baseline = _load(baseline_path)
    candidate = _load(candidate_path)
    baseline_by_id = {chunk.chunk_id: chunk for chunk in baseline}

    numeric = audit_absorbed_numeric(
        baseline_path=baseline_path,
        candidate_path=candidate_path,
    )
    delta = audit_semantic_delta(
        baseline_path=baseline_path,
        candidate_path=candidate_path,
    )

    targets: list[tuple[str, str, str]] = []

    for numeric_finding in numeric.findings:
        if numeric_finding.classification == "ambiguous_numeric_boundary_requires_review":
            targets.append(
                (
                    "absorbed_numeric_19i72",
                    numeric_finding.classification,
                    numeric_finding.removed_chunk_id,
                )
            )

    for removed_finding in delta.removed:
        if removed_finding.classification in {
            "absorbed_other_boundary",
            "missing_reference_like_boundary",
        }:
            targets.append(
                (
                    "semantic_delta_19i71",
                    removed_finding.classification,
                    removed_finding.chunk_id,
                )
            )

    seen: set[str] = set()
    findings: list[ResidualFinding] = []

    for source_audit, original_classification, chunk_id in targets:
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        old = baseline_by_id.get(chunk_id)
        if old is None:
            raise SemanticResidualAuditError(
                f"No existe chunk baseline residual: {chunk_id}"
            )

        container_ids = _containers(old, candidate)
        contained = bool(container_ids)

        if original_classification == "missing_reference_like_boundary":
            classification = (
                "reference_like_text_preserved"
                if contained
                else "reference_like_text_missing_requires_review"
            )
        elif original_classification == "absorbed_other_boundary":
            classification = (
                "other_boundary_text_preserved_requires_review"
                if contained
                else "other_boundary_text_missing_requires_review"
            )
        else:
            classification = (
                "ambiguous_numeric_text_preserved_requires_review"
                if contained
                else "ambiguous_numeric_text_missing_requires_review"
            )

        findings.append(
            ResidualFinding(
                source_audit=source_audit,
                original_classification=original_classification,
                canonical_id=old.canonical_id,
                baseline_chunk_id=old.chunk_id,
                unit_label=old.unit_label,
                page_start=old.page_start,
                page_end=old.page_end,
                candidate_contains_baseline=contained,
                candidate_container_ids=container_ids,
                classification=classification,
            )
        )

    counts = Counter(item.classification for item in findings)
    safe = counts.get("reference_like_text_preserved", 0)
    return SemanticResidualReport(
        total_residuals=len(findings),
        safe_absorptions=safe,
        requires_review=len(findings) - safe,
        classifications=dict(sorted(counts.items())),
        findings=tuple(findings),
    )


def write_semantic_residual_outputs(
    *,
    output_dir: Path,
    report: SemanticResidualReport,
) -> None:
    resolved = output_dir.expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(
        asdict(report),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    json_path = resolved / "semantic_residual_audit.json"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=resolved,
        prefix=".semantic_residual_audit.",
        suffix=".tmp",
    ) as handle:
        handle.write(payload)
        temp_path = Path(handle.name)
    os.replace(temp_path, json_path)

    csv_path = resolved / "semantic_residual_findings.csv"
    fields = (
        list(asdict(report.findings[0]).keys())
        if report.findings
        else [
            "source_audit",
            "original_classification",
            "canonical_id",
            "baseline_chunk_id",
            "unit_label",
            "page_start",
            "page_end",
            "candidate_contains_baseline",
            "candidate_container_ids",
            "classification",
        ]
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for finding in report.findings:
            row = asdict(finding)
            row["candidate_container_ids"] = "|".join(
                finding.candidate_container_ids
            )
            writer.writerow(row)
