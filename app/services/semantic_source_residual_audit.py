from __future__ import annotations

import csv
import json
import os
import tempfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from app.domain.legal_chunks import LegalChunk
from app.services.semantic_residual_audit import audit_semantic_residuals
from rag.chunking.legal_structurer import (
    _ARTICLE_RE,
    _HEADING_RE,
    _RULE_RE,
    _STRUCTURAL_RE,
)


class SemanticSourceResidualAuditError(RuntimeError):
    """Fallo controlado al contrastar residuos con la fuente normalizada."""


@dataclass(frozen=True)
class SemanticSourceResidualFinding:
    canonical_id: str
    baseline_chunk_id: str
    unit_type: str
    unit_label: str
    page_start: int | None
    page_end: int | None
    original_classification: str
    source_path: str | None
    source_line_found: bool
    first_line: str
    source_line: str | None
    parser_article_match: bool
    parser_rule_match: bool
    parser_structural_match: bool
    parser_markdown_heading_match: bool
    candidate_identity_ids: tuple[str, ...]
    candidate_container_ids: tuple[str, ...]
    classification: str
    rationale: str


@dataclass(frozen=True)
class SemanticSourceResidualReport:
    total_requires_review: int
    resolved_safe: int
    still_requires_review: int
    classifications: dict[str, int]
    findings: tuple[SemanticSourceResidualFinding, ...]


def _load_chunks(path: Path) -> list[LegalChunk]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise SemanticSourceResidualAuditError(f"No existe corpus: {resolved}")
    chunks: list[LegalChunk] = []
    with resolved.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                chunks.append(LegalChunk.model_validate_json(line))
            except ValueError as exc:
                raise SemanticSourceResidualAuditError(
                    f"JSONL inválido en {resolved}:{line_number}"
                ) from exc
    return chunks


def _compact(value: str) -> str:
    return " ".join(value.split())


def _first_nonempty_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), "")


def _normalized_source_path(root: Path, canonical_id: str) -> Path | None:
    resolved = root.expanduser().resolve()
    direct = resolved / f"{canonical_id}.md"
    if direct.is_file():
        return direct

    target = canonical_id.casefold()
    for candidate in resolved.glob("*.md"):
        if candidate.stem.casefold() == target:
            return candidate
    return None


def _find_source_line(source_text: str, first_line: str) -> str | None:
    if not first_line:
        return None

    exact = first_line.strip()
    lines = source_text.splitlines()
    for line in lines:
        if line.strip() == exact:
            return line.strip()

    compact_target = _compact(first_line)
    for line in lines:
        if _compact(line) == compact_target:
            return line.strip()

    probe = compact_target[:100]
    if len(probe) >= 50:
        matches = [line.strip() for line in lines if probe in _compact(line)]
        if len(matches) == 1:
            return matches[0]
    return None


def _identity_key(chunk: LegalChunk) -> tuple[str, str, str]:
    return (
        chunk.canonical_id.casefold(),
        chunk.unit_type.value,
        chunk.unit_label.strip().casefold(),
    )


def _container_ids(
    baseline: LegalChunk,
    candidates: list[LegalChunk],
) -> tuple[str, ...]:
    baseline_text = _compact(baseline.text)
    if not baseline_text:
        return ()
    return tuple(
        chunk.chunk_id
        for chunk in candidates
        if chunk.canonical_id == baseline.canonical_id
        and baseline_text in _compact(chunk.text)
    )


def audit_semantic_source_residuals(
    *,
    baseline_path: Path,
    candidate_path: Path,
    normalized_root: Path,
) -> SemanticSourceResidualReport:
    residual = audit_semantic_residuals(
        baseline_path=baseline_path,
        candidate_path=candidate_path,
    )
    baseline = _load_chunks(baseline_path)
    candidate = _load_chunks(candidate_path)
    baseline_by_id = {chunk.chunk_id: chunk for chunk in baseline}

    candidate_by_identity: dict[tuple[str, str, str], list[LegalChunk]] = defaultdict(list)
    candidate_by_doc: dict[str, list[LegalChunk]] = defaultdict(list)
    for chunk in candidate:
        candidate_by_identity[_identity_key(chunk)].append(chunk)
        candidate_by_doc[chunk.canonical_id].append(chunk)

    review_targets = [
        finding
        for finding in residual.findings
        if finding.classification.endswith("_requires_review")
    ]

    findings: list[SemanticSourceResidualFinding] = []
    for residual_finding in review_targets:
        old = baseline_by_id.get(residual_finding.baseline_chunk_id)
        if old is None:
            raise SemanticSourceResidualAuditError(
                f"No existe chunk baseline: {residual_finding.baseline_chunk_id}"
            )

        source_path = _normalized_source_path(normalized_root, old.canonical_id)
        first_line = _first_nonempty_line(old.text)
        source_line: str | None = None
        if source_path is not None:
            try:
                source_text = source_path.read_text(encoding="utf-8")
            except OSError as exc:
                raise SemanticSourceResidualAuditError(
                    f"No se pudo leer fuente normalizada: {source_path}"
                ) from exc
            source_line = _find_source_line(source_text, first_line)

        line_for_parser = source_line or first_line
        article_match = _ARTICLE_RE.match(line_for_parser) is not None
        rule_match = _RULE_RE.match(line_for_parser) is not None
        structural_match = _STRUCTURAL_RE.match(line_for_parser) is not None
        heading_match = _HEADING_RE.match(line_for_parser) is not None
        parser_accepts = (
            article_match or rule_match or structural_match or heading_match
        )

        identity_matches = tuple(
            chunk.chunk_id
            for chunk in candidate_by_identity.get(_identity_key(old), [])
        )
        containers = _container_ids(
            old,
            candidate_by_doc.get(old.canonical_id, []),
        )

        if len(identity_matches) == 1:
            classification = "boundary_identity_preserved_unique"
            rationale = (
                "La misma identidad estructural existe una sola vez en el candidato."
            )
        elif len(identity_matches) > 1:
            classification = "boundary_identity_preserved_duplicate_requires_review"
            rationale = (
                "La identidad estructural sigue presente, pero aparece duplicada."
            )
        elif source_line is None:
            classification = "source_line_not_found_requires_review"
            rationale = (
                "No fue posible localizar la primera línea 19C en la fuente normalizada."
            )
        elif not parser_accepts and containers:
            classification = "parser_rejects_false_boundary_text_preserved"
            rationale = (
                "El parser actual ya no reconoce la línea como frontera y el texto "
                "permanece contenido en el candidato."
            )
        elif not parser_accepts:
            classification = "parser_rejects_boundary_text_missing_requires_review"
            rationale = (
                "El parser actual rechaza la frontera y no se confirmó preservación "
                "integral del texto."
            )
        elif parser_accepts and containers:
            classification = "parser_accepts_identity_changed_requires_review"
            rationale = (
                "La fuente satisface un patrón estructural actual y el texto se "
                "preserva, pero cambió la identidad de la unidad."
            )
        else:
            classification = "parser_accepts_identity_missing_requires_review"
            rationale = (
                "La fuente satisface un patrón estructural actual, pero no existe "
                "identidad equivalente ni contención integral en el candidato."
            )

        findings.append(
            SemanticSourceResidualFinding(
                canonical_id=old.canonical_id,
                baseline_chunk_id=old.chunk_id,
                unit_type=old.unit_type.value,
                unit_label=old.unit_label,
                page_start=old.page_start,
                page_end=old.page_end,
                original_classification=residual_finding.classification,
                source_path=str(source_path) if source_path is not None else None,
                source_line_found=source_line is not None,
                first_line=first_line,
                source_line=source_line,
                parser_article_match=article_match,
                parser_rule_match=rule_match,
                parser_structural_match=structural_match,
                parser_markdown_heading_match=heading_match,
                candidate_identity_ids=identity_matches,
                candidate_container_ids=containers,
                classification=classification,
                rationale=rationale,
            )
        )

    counts = Counter(item.classification for item in findings)
    safe_classes = {
        "boundary_identity_preserved_unique",
        "parser_rejects_false_boundary_text_preserved",
    }
    resolved_safe = sum(
        count for key, count in counts.items() if key in safe_classes
    )
    return SemanticSourceResidualReport(
        total_requires_review=len(findings),
        resolved_safe=resolved_safe,
        still_requires_review=len(findings) - resolved_safe,
        classifications=dict(sorted(counts.items())),
        findings=tuple(findings),
    )


def write_semantic_source_residual_outputs(
    *,
    output_dir: Path,
    report: SemanticSourceResidualReport,
) -> None:
    resolved = output_dir.expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(
        asdict(report),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    json_path = resolved / "semantic_source_residual_audit.json"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=resolved,
        prefix=".semantic_source_residual_audit.",
        suffix=".tmp",
    ) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    os.replace(temporary, json_path)

    csv_path = resolved / "semantic_source_residual_findings.csv"
    fields = (
        list(asdict(report.findings[0]).keys())
        if report.findings
        else [
            "canonical_id",
            "baseline_chunk_id",
            "unit_type",
            "unit_label",
            "page_start",
            "page_end",
            "original_classification",
            "source_path",
            "source_line_found",
            "first_line",
            "source_line",
            "parser_article_match",
            "parser_rule_match",
            "parser_structural_match",
            "parser_markdown_heading_match",
            "candidate_identity_ids",
            "candidate_container_ids",
            "classification",
            "rationale",
        ]
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for finding in report.findings:
            row = asdict(finding)
            row["candidate_identity_ids"] = "|".join(finding.candidate_identity_ids)
            row["candidate_container_ids"] = "|".join(finding.candidate_container_ids)
            writer.writerow(row)
