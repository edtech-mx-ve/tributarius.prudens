from __future__ import annotations

import csv
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from app.domain.legal_chunks import LegalChunk
from app.services.absorbed_numeric_audit import audit_absorbed_numeric
from rag.chunking.legal_structurer import _ARTICLE_RE


class LegalHeadingSourceAuditError(RuntimeError):
    """Error controlado al contrastar chunks absorbidos contra Markdown fuente."""


@dataclass(frozen=True)
class HeadingSourceFinding:
    canonical_id: str
    removed_chunk_id: str
    unit_label: str
    normalized_path: str
    markdown_match_found: bool
    current_parser_matches_source_line: bool
    source_line_number: int | None
    source_line: str | None
    previous_line: str | None
    next_line: str | None
    classification: str


@dataclass(frozen=True)
class HeadingSourceReport:
    total_probable_legitimate: int
    markdown_match_found: int
    parser_matches_source_line: int
    parser_misses_source_line: int
    findings: tuple[HeadingSourceFinding, ...]


def _load_chunks(path: Path) -> dict[str, LegalChunk]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise LegalHeadingSourceAuditError(f"No existe corpus: {resolved}")
    result: dict[str, LegalChunk] = {}
    with resolved.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                chunk = LegalChunk.model_validate_json(line)
            except ValueError as exc:
                raise LegalHeadingSourceAuditError(
                    f"JSONL inválido en {resolved}:{line_number}"
                ) from exc
            result[chunk.chunk_id] = chunk
    return result


def _candidate_normalized_paths(
    *,
    project_root: Path,
    canonical_id: str,
) -> tuple[Path, ...]:
    root = project_root.expanduser().resolve()
    candidates = (
        root / "knowledge" / "normalized" / "normativa" / f"{canonical_id}.md",
        root / "knowledge" / "normalized" / "normativa" / f"{canonical_id.lower()}.md",
        root / "knowledge" / "normalized" / "normativa" / f"{canonical_id.upper()}.md",
    )
    existing = tuple(path for path in candidates if path.is_file())
    if existing:
        return existing

    normative = root / "knowledge" / "normalized" / "normativa"
    if not normative.is_dir():
        return ()
    needle = canonical_id.casefold()
    return tuple(
        path
        for path in normative.glob("*.md")
        if path.stem.casefold() == needle
    )


def _find_source_line(
    *,
    lines: list[str],
    chunk: LegalChunk,
) -> tuple[int | None, str | None, str | None, str | None]:
    first_line = next(
        (line.strip() for line in chunk.text.splitlines() if line.strip()),
        "",
    )
    if not first_line:
        return None, None, None, None

    for index, raw in enumerate(lines):
        if raw.strip() == first_line:
            previous = lines[index - 1] if index > 0 else None
            following = lines[index + 1] if index + 1 < len(lines) else None
            return index + 1, raw, previous, following

    # Fallback robusto: busca un prefijo suficiente para tolerar espacios de extracción.
    prefix = " ".join(first_line.split())[:80]
    for index, raw in enumerate(lines):
        if prefix and prefix in " ".join(raw.split()):
            previous = lines[index - 1] if index > 0 else None
            following = lines[index + 1] if index + 1 < len(lines) else None
            return index + 1, raw, previous, following

    return None, None, None, None


def audit_heading_sources(
    *,
    project_root: Path,
    baseline_path: Path,
    candidate_path: Path,
) -> HeadingSourceReport:
    numeric = audit_absorbed_numeric(
        baseline_path=baseline_path,
        candidate_path=candidate_path,
    )
    baseline = _load_chunks(baseline_path)

    targets = [
        item
        for item in numeric.findings
        if item.classification == "probable_legitimate_article_boundary"
    ]

    findings: list[HeadingSourceFinding] = []
    for item in targets:
        chunk = baseline[item.removed_chunk_id]
        paths = _candidate_normalized_paths(
            project_root=project_root,
            canonical_id=item.canonical_id,
        )
        if not paths:
            findings.append(
                HeadingSourceFinding(
                    canonical_id=item.canonical_id,
                    removed_chunk_id=item.removed_chunk_id,
                    unit_label=item.unit_label,
                    normalized_path="",
                    markdown_match_found=False,
                    current_parser_matches_source_line=False,
                    source_line_number=None,
                    source_line=None,
                    previous_line=None,
                    next_line=None,
                    classification="normalized_source_missing",
                )
            )
            continue

        path = paths[0]
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise LegalHeadingSourceAuditError(
                f"No se pudo leer {path}"
            ) from exc

        line_number, source_line, previous, following = _find_source_line(
            lines=lines,
            chunk=chunk,
        )
        found = source_line is not None
        parser_matches = bool(
            source_line is not None and _ARTICLE_RE.match(source_line)
        )

        if not found:
            classification = "source_line_not_found"
        elif parser_matches:
            classification = "parser_should_split_but_did_not"
        else:
            classification = "source_heading_variant_not_supported"

        findings.append(
            HeadingSourceFinding(
                canonical_id=item.canonical_id,
                removed_chunk_id=item.removed_chunk_id,
                unit_label=item.unit_label,
                normalized_path=str(path),
                markdown_match_found=found,
                current_parser_matches_source_line=parser_matches,
                source_line_number=line_number,
                source_line=source_line,
                previous_line=previous,
                next_line=following,
                classification=classification,
            )
        )

    found_count = sum(item.markdown_match_found for item in findings)
    parser_count = sum(item.current_parser_matches_source_line for item in findings)
    return HeadingSourceReport(
        total_probable_legitimate=len(findings),
        markdown_match_found=found_count,
        parser_matches_source_line=parser_count,
        parser_misses_source_line=found_count - parser_count,
        findings=tuple(findings),
    )


def write_heading_source_outputs(
    *,
    output_dir: Path,
    report: HeadingSourceReport,
) -> None:
    resolved = output_dir.expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(
        asdict(report),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    json_path = resolved / "heading_source_audit.json"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=resolved,
        prefix=".heading_source_audit.",
        suffix=".tmp",
    ) as handle:
        handle.write(payload)
        temp_path = Path(handle.name)
    os.replace(temp_path, json_path)

    csv_path = resolved / "heading_source_findings.csv"
    fields = (
        list(asdict(report.findings[0]).keys())
        if report.findings
        else [
            "canonical_id",
            "removed_chunk_id",
            "unit_label",
            "normalized_path",
            "markdown_match_found",
            "current_parser_matches_source_line",
            "source_line_number",
            "source_line",
            "previous_line",
            "next_line",
            "classification",
        ]
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for finding in report.findings:
            writer.writerow(asdict(finding))
