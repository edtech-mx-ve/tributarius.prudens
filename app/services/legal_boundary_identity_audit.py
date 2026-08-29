from __future__ import annotations

import csv
import json
import os
import tempfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from app.domain.legal_chunks import LegalChunk
from app.services.absorbed_numeric_audit import audit_absorbed_numeric


class LegalBoundaryIdentityAuditError(RuntimeError):
    """Error controlado al comprobar identidad de fronteras legales."""


@dataclass(frozen=True)
class BoundaryIdentityFinding:
    canonical_id: str
    baseline_chunk_id: str
    baseline_unit_label: str
    candidate_same_label_count: int
    candidate_chunk_ids: tuple[str, ...]
    baseline_text_preserved_exactly: bool
    baseline_text_contained_in_candidate: bool
    classification: str


@dataclass(frozen=True)
class BoundaryIdentityReport:
    total_probable_legitimate: int
    preserved_boundary_identity: int
    missing_boundary_identity: int
    ambiguous_boundary_identity: int
    classifications: dict[str, int]
    findings: tuple[BoundaryIdentityFinding, ...]


def _load(path: Path) -> list[LegalChunk]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise LegalBoundaryIdentityAuditError(f"No existe corpus: {resolved}")
    chunks: list[LegalChunk] = []
    with resolved.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                chunks.append(LegalChunk.model_validate_json(line))
            except ValueError as exc:
                raise LegalBoundaryIdentityAuditError(
                    f"JSONL inválido en {resolved}:{line_number}"
                ) from exc
    return chunks


def _compact(value: str) -> str:
    return " ".join(value.split())


def audit_boundary_identity(
    *,
    baseline_path: Path,
    candidate_path: Path,
) -> BoundaryIdentityReport:
    numeric = audit_absorbed_numeric(
        baseline_path=baseline_path,
        candidate_path=candidate_path,
    )
    baseline = _load(baseline_path)
    candidate = _load(candidate_path)

    baseline_by_id = {chunk.chunk_id: chunk for chunk in baseline}
    candidate_by_key: dict[tuple[str, str, str], list[LegalChunk]] = defaultdict(list)
    for chunk in candidate:
        key = (
            chunk.canonical_id,
            chunk.unit_type.value,
            chunk.unit_label.strip().casefold(),
        )
        candidate_by_key[key].append(chunk)

    targets = [
        item
        for item in numeric.findings
        if item.classification == "probable_legitimate_article_boundary"
    ]

    findings: list[BoundaryIdentityFinding] = []
    for item in targets:
        old = baseline_by_id[item.removed_chunk_id]
        key = (
            old.canonical_id,
            old.unit_type.value,
            old.unit_label.strip().casefold(),
        )
        matches = candidate_by_key.get(key, [])
        exact = any(match.text_sha256 == old.text_sha256 for match in matches)
        old_compact = _compact(old.text)
        contained = any(
            old_compact and old_compact in _compact(match.text)
            for match in matches
        )

        if len(matches) == 1:
            classification = (
                "boundary_preserved_content_expanded"
                if not exact
                else "boundary_preserved_exact"
            )
        elif len(matches) == 0:
            classification = "boundary_missing_requires_review"
        else:
            classification = "boundary_ambiguous_duplicate_label"

        findings.append(
            BoundaryIdentityFinding(
                canonical_id=old.canonical_id,
                baseline_chunk_id=old.chunk_id,
                baseline_unit_label=old.unit_label,
                candidate_same_label_count=len(matches),
                candidate_chunk_ids=tuple(match.chunk_id for match in matches),
                baseline_text_preserved_exactly=exact,
                baseline_text_contained_in_candidate=contained,
                classification=classification,
            )
        )

    counts = Counter(item.classification for item in findings)
    preserved = sum(
        item.classification.startswith("boundary_preserved")
        for item in findings
    )
    missing = sum(
        item.classification == "boundary_missing_requires_review"
        for item in findings
    )
    ambiguous = sum(
        item.classification == "boundary_ambiguous_duplicate_label"
        for item in findings
    )
    return BoundaryIdentityReport(
        total_probable_legitimate=len(findings),
        preserved_boundary_identity=preserved,
        missing_boundary_identity=missing,
        ambiguous_boundary_identity=ambiguous,
        classifications=dict(sorted(counts.items())),
        findings=tuple(findings),
    )


def write_boundary_identity_outputs(
    *,
    output_dir: Path,
    report: BoundaryIdentityReport,
) -> None:
    resolved = output_dir.expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(
        asdict(report),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    json_path = resolved / "boundary_identity_audit.json"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=resolved,
        prefix=".boundary_identity_audit.",
        suffix=".tmp",
    ) as handle:
        handle.write(payload)
        temp_path = Path(handle.name)
    os.replace(temp_path, json_path)

    csv_path = resolved / "boundary_identity_findings.csv"
    fields = (
        list(asdict(report.findings[0]).keys())
        if report.findings
        else [
            "canonical_id",
            "baseline_chunk_id",
            "baseline_unit_label",
            "candidate_same_label_count",
            "candidate_chunk_ids",
            "baseline_text_preserved_exactly",
            "baseline_text_contained_in_candidate",
            "classification",
        ]
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for finding in report.findings:
            row = asdict(finding)
            row["candidate_chunk_ids"] = "|".join(finding.candidate_chunk_ids)
            writer.writerow(row)
