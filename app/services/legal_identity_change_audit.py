from __future__ import annotations

import csv
import json
import os
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from app.domain.legal_chunks import LegalChunk
from app.services.semantic_source_residual_audit import (
    audit_semantic_source_residuals,
)
from rag.chunking.legal_structurer import (
    _HEADING_RE,
    _RULE_RE,
    _STRUCTURAL_RE,
    _detect_boundary,
)


class LegalIdentityChangeAuditError(RuntimeError):
    """Fallo controlado al auditar cambios de identidad legal."""


@dataclass(frozen=True)
class CandidateIdentityEvidence:
    chunk_id: str
    unit_type: str
    unit_label: str
    page_start: int | None
    page_end: int | None
    starts_with_source_line: bool
    contains_source_line: bool


@dataclass(frozen=True)
class LegalIdentityChangeFinding:
    canonical_id: str
    baseline_chunk_id: str
    baseline_unit_type: str
    baseline_unit_label: str
    baseline_page_start: int | None
    baseline_page_end: int | None
    source_line: str
    parser_unit_type: str | None
    parser_unit_label: str | None
    parser_matches_baseline_identity: bool
    candidate_container_ids: tuple[str, ...]
    candidate_evidence: tuple[CandidateIdentityEvidence, ...]
    classification: str
    rationale: str


@dataclass(frozen=True)
class LegalIdentityChangeReport:
    total_identity_changed: int
    resolved_safe: int
    requires_review: int
    classifications: dict[str, int]
    findings: tuple[LegalIdentityChangeFinding, ...]


def _load_chunks(path: Path) -> list[LegalChunk]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise LegalIdentityChangeAuditError(f"No existe corpus: {resolved}")
    chunks: list[LegalChunk] = []
    with resolved.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                chunks.append(LegalChunk.model_validate_json(line))
            except ValueError as exc:
                raise LegalIdentityChangeAuditError(
                    f"JSONL inválido en {resolved}:{line_number}"
                ) from exc
    return chunks


def _clean(value: str) -> str:
    return " ".join(value.split())


def _identity(unit_type: str, unit_label: str) -> tuple[str, str]:
    return unit_type, _clean(unit_label).casefold()


def _detect_identity(line: str) -> tuple[str | None, str | None]:
    article = _detect_boundary(line, "legal_article")
    if article is not None:
        unit_type, label = article
        return unit_type.value, label

    rule = _RULE_RE.match(line)
    if rule:
        return "administrative_rule", rule.group(1).rstrip(".")

    structural = _STRUCTURAL_RE.match(line)
    if structural:
        return (
            "structural_section",
            _clean(f"{structural.group(1)} {structural.group(2)}"),
        )

    heading = _HEADING_RE.match(line)
    if heading:
        return "structural_section", _clean(heading.group(2))

    return None, None


def _starts_with_line(text: str, line: str) -> bool:
    compact_text = _clean(text)
    compact_line = _clean(line)
    return bool(compact_line and compact_text.startswith(compact_line))


def _contains_line(text: str, line: str) -> bool:
    compact_line = _clean(line)
    return bool(compact_line and compact_line in _clean(text))


def audit_legal_identity_changes(
    *,
    baseline_path: Path,
    candidate_path: Path,
    normalized_root: Path,
) -> LegalIdentityChangeReport:
    source_report = audit_semantic_source_residuals(
        baseline_path=baseline_path,
        candidate_path=candidate_path,
        normalized_root=normalized_root,
    )
    baseline = _load_chunks(baseline_path)
    candidate = _load_chunks(candidate_path)
    baseline_by_id = {chunk.chunk_id: chunk for chunk in baseline}
    candidate_by_id = {chunk.chunk_id: chunk for chunk in candidate}

    targets = [
        finding
        for finding in source_report.findings
        if finding.classification
        == "parser_accepts_identity_changed_requires_review"
    ]

    findings: list[LegalIdentityChangeFinding] = []
    for target in targets:
        old = baseline_by_id.get(target.baseline_chunk_id)
        if old is None:
            raise LegalIdentityChangeAuditError(
                f"No existe chunk baseline: {target.baseline_chunk_id}"
            )

        source_line = target.source_line or target.first_line
        parser_type, parser_label = _detect_identity(source_line)
        parser_matches_baseline = (
            parser_type is not None
            and parser_label is not None
            and _identity(parser_type, parser_label)
            == _identity(old.unit_type.value, old.unit_label)
        )

        evidence: list[CandidateIdentityEvidence] = []
        for candidate_id in target.candidate_container_ids:
            current = candidate_by_id.get(candidate_id)
            if current is None:
                continue
            evidence.append(
                CandidateIdentityEvidence(
                    chunk_id=current.chunk_id,
                    unit_type=current.unit_type.value,
                    unit_label=current.unit_label,
                    page_start=current.page_start,
                    page_end=current.page_end,
                    starts_with_source_line=_starts_with_line(
                        current.text,
                        source_line,
                    ),
                    contains_source_line=_contains_line(
                        current.text,
                        source_line,
                    ),
                )
            )

        exact_parser_identity = [
            item
            for item in evidence
            if parser_type is not None
            and parser_label is not None
            and _identity(item.unit_type, item.unit_label)
            == _identity(parser_type, parser_label)
        ]

        if len(exact_parser_identity) == 1:
            classification = "parser_identity_preserved_in_container"
            rationale = (
                "El parser detecta una identidad estructural y una sola unidad "
                "contenedora conserva exactamente esa identidad."
            )
        elif len(exact_parser_identity) > 1:
            classification = "parser_identity_duplicated_requires_review"
            rationale = (
                "Más de una unidad contenedora conserva la identidad detectada."
            )
        elif parser_matches_baseline and evidence:
            classification = "baseline_identity_missing_from_candidate_requires_review"
            rationale = (
                "La fuente y el parser confirman la identidad 19C, pero ninguna "
                "unidad contenedora candidata conserva esa identidad."
            )
        elif evidence and any(item.starts_with_source_line for item in evidence):
            classification = "source_line_starts_different_identity_requires_review"
            rationale = (
                "Una unidad candidata inicia con la misma línea fuente pero fue "
                "etiquetada con una identidad distinta."
            )
        elif evidence:
            classification = "source_line_merged_under_neighbor_requires_review"
            rationale = (
                "El texto fue preservado dentro de otra unidad candidata, pero "
                "no como inicio de una unidad con identidad equivalente."
            )
        else:
            classification = "no_candidate_container_requires_review"
            rationale = (
                "No se encontró unidad candidata que contenga íntegramente el "
                "texto baseline."
            )

        findings.append(
            LegalIdentityChangeFinding(
                canonical_id=old.canonical_id,
                baseline_chunk_id=old.chunk_id,
                baseline_unit_type=old.unit_type.value,
                baseline_unit_label=old.unit_label,
                baseline_page_start=old.page_start,
                baseline_page_end=old.page_end,
                source_line=source_line,
                parser_unit_type=parser_type,
                parser_unit_label=parser_label,
                parser_matches_baseline_identity=parser_matches_baseline,
                candidate_container_ids=target.candidate_container_ids,
                candidate_evidence=tuple(evidence),
                classification=classification,
                rationale=rationale,
            )
        )

    counts = Counter(item.classification for item in findings)
    safe_classes = {"parser_identity_preserved_in_container"}
    resolved_safe = sum(
        count for key, count in counts.items() if key in safe_classes
    )
    return LegalIdentityChangeReport(
        total_identity_changed=len(findings),
        resolved_safe=resolved_safe,
        requires_review=len(findings) - resolved_safe,
        classifications=dict(sorted(counts.items())),
        findings=tuple(findings),
    )


def write_legal_identity_change_outputs(
    *,
    output_dir: Path,
    report: LegalIdentityChangeReport,
) -> None:
    resolved = output_dir.expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(
        asdict(report),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    json_path = resolved / "legal_identity_change_audit.json"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=resolved,
        prefix=".legal_identity_change_audit.",
        suffix=".tmp",
    ) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    os.replace(temporary, json_path)

    csv_path = resolved / "legal_identity_change_findings.csv"
    fields = [
        "canonical_id",
        "baseline_chunk_id",
        "baseline_unit_type",
        "baseline_unit_label",
        "baseline_page_start",
        "baseline_page_end",
        "source_line",
        "parser_unit_type",
        "parser_unit_label",
        "parser_matches_baseline_identity",
        "candidate_container_ids",
        "candidate_evidence",
        "classification",
        "rationale",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for finding in report.findings:
            row = asdict(finding)
            row["candidate_container_ids"] = "|".join(
                finding.candidate_container_ids
            )
            row["candidate_evidence"] = json.dumps(
                [asdict(item) for item in finding.candidate_evidence],
                ensure_ascii=False,
                sort_keys=True,
            )
            writer.writerow(row)
