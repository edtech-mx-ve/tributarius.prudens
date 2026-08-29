from __future__ import annotations

import csv
import json
import os
import re
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from app.domain.legal_chunks import LegalChunk
from app.services.semantic_delta_audit import (
    SemanticDeltaAuditError,
    audit_semantic_delta,
)

_HEADING_LIKE_RE = re.compile(
    r"(?i)^\s*(?:#{1,6}\s*)?art[ií]culo\s+"
    r"(?P<identifier>"
    r"\d+o?"
    r"(?:\s*-\s*[a-z0-9áéíóúñ]+)*"
    r"(?:\s+(?:bis|ter|qu[aá]ter))?"
    r")"
    r"\s*(?P<separator>\.-|\.|:|—|–|-(?![a-z0-9áéíóúñ])|$)"
)

_REFERENCE_AFTER_ID_RE = re.compile(
    r"(?i)^\s*(?:#{1,6}\s*)?art[ií]culo\s+"
    r"\d+o?(?:\s*-\s*[a-z0-9áéíóúñ]+)*"
    r"(?:\s+(?:bis|ter|qu[aá]ter))?"
    r"\s+(de|del|que|a|al|en|por|para|con|fracci[oó]n|p[aá]rrafo)\b"
)

_REFORM_CONTEXT_RE = re.compile(
    r"(?i)\b("
    r"reformad[oa]|adicionad[oa]|derogad[oa]|decreto|transitorio|"
    r"publicad[oa]\s+en\s+el\s+diario\s+oficial|dof"
    r")\b"
)


class AbsorbedNumericAuditError(RuntimeError):
    """Error controlado al refinar artículos numéricos absorbidos."""


@dataclass(frozen=True)
class AbsorbedNumericFinding:
    canonical_id: str
    removed_chunk_id: str
    unit_label: str
    page_start: int | None
    page_end: int | None
    absorbed_into_candidate_chunk_id: str
    first_line: str
    candidate_contains_removed_text: bool
    classification: str
    rationale: str
    excerpt: str


@dataclass(frozen=True)
class AbsorbedNumericReport:
    baseline_path: str
    candidate_path: str
    total_absorbed_numeric: int
    classifications: dict[str, int]
    findings: tuple[AbsorbedNumericFinding, ...]


def _load(path: Path) -> list[LegalChunk]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise AbsorbedNumericAuditError(f"No existe corpus: {resolved}")
    chunks: list[LegalChunk] = []
    try:
        with resolved.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    chunks.append(LegalChunk.model_validate_json(line))
                except ValueError as exc:
                    raise AbsorbedNumericAuditError(
                        f"JSONL inválido en {resolved}:{line_number}"
                    ) from exc
    except OSError as exc:
        raise AbsorbedNumericAuditError(f"No se pudo leer {resolved}") from exc
    return chunks


def _compact(text: str) -> str:
    return " ".join(text.split())


def _excerpt(text: str, limit: int = 260) -> str:
    compact = _compact(text)
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def _classify(chunk: LegalChunk) -> tuple[str, str]:
    first_line = next(
        (line.strip() for line in chunk.text.splitlines() if line.strip()),
        "",
    )
    compact = _compact(chunk.text)

    if _REFERENCE_AFTER_ID_RE.match(first_line):
        return (
            "reference_like_false_boundary",
            "La primera línea continúa con una preposición o descriptor; no parece encabezado.",
        )

    if _REFORM_CONTEXT_RE.search(first_line) and not _HEADING_LIKE_RE.match(first_line):
        return (
            "reform_or_transitory_context",
            "La unidad inicia en contexto de reforma/transitorio y no satisface encabezado fuerte.",
        )

    match = _HEADING_LIKE_RE.match(first_line)
    if match is not None:
        if len(compact) < 80:
            return (
                "short_heading_candidate_requires_review",
                (
                    "Existe encabezado fuerte, pero el fragmento es demasiado corto "
                    "para promover automáticamente."
                ),
            )
        return (
            "probable_legitimate_article_boundary",
            (
                "La primera línea satisface un encabezado fuerte y el contenido "
                "tiene cuerpo sustantivo."
            ),
        )

    return (
        "ambiguous_numeric_boundary_requires_review",
        "No coincide con referencia típica ni con encabezado fuerte.",
    )


def audit_absorbed_numeric(
    *,
    baseline_path: Path,
    candidate_path: Path,
) -> AbsorbedNumericReport:
    try:
        delta = audit_semantic_delta(
            baseline_path=baseline_path,
            candidate_path=candidate_path,
        )
    except SemanticDeltaAuditError as exc:
        raise AbsorbedNumericAuditError(str(exc)) from exc

    baseline = _load(baseline_path)
    candidate = _load(candidate_path)
    baseline_by_id = {chunk.chunk_id: chunk for chunk in baseline}
    candidate_by_id = {chunk.chunk_id: chunk for chunk in candidate}

    target = [
        item
        for item in delta.removed
        if item.classification == "absorbed_numeric_article_requires_review"
    ]

    findings: list[AbsorbedNumericFinding] = []
    for item in target:
        if item.absorbed_into_candidate_chunk_id is None:
            continue
        removed = baseline_by_id[item.chunk_id]
        absorbed = candidate_by_id.get(item.absorbed_into_candidate_chunk_id)
        if absorbed is None:
            raise AbsorbedNumericAuditError(
                "No se encontró el candidato absorbente: "
                + item.absorbed_into_candidate_chunk_id
            )

        classification, rationale = _classify(removed)
        first_line = next(
            (line.strip() for line in removed.text.splitlines() if line.strip()),
            "",
        )
        probe = _compact(removed.text)[:120]
        contains = bool(probe and probe in _compact(absorbed.text))

        findings.append(
            AbsorbedNumericFinding(
                canonical_id=removed.canonical_id,
                removed_chunk_id=removed.chunk_id,
                unit_label=removed.unit_label,
                page_start=removed.page_start,
                page_end=removed.page_end,
                absorbed_into_candidate_chunk_id=absorbed.chunk_id,
                first_line=first_line,
                candidate_contains_removed_text=contains,
                classification=classification,
                rationale=rationale,
                excerpt=_excerpt(removed.text),
            )
        )

    counts = Counter(item.classification for item in findings)
    return AbsorbedNumericReport(
        baseline_path=str(baseline_path.expanduser().resolve()),
        candidate_path=str(candidate_path.expanduser().resolve()),
        total_absorbed_numeric=len(findings),
        classifications=dict(sorted(counts.items())),
        findings=tuple(findings),
    )


def write_absorbed_numeric_outputs(
    *,
    output_dir: Path,
    report: AbsorbedNumericReport,
) -> None:
    resolved = output_dir.expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(
        asdict(report),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    json_path = resolved / "absorbed_numeric_audit.json"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=resolved,
        prefix=".absorbed_numeric_audit.",
        suffix=".tmp",
    ) as handle:
        handle.write(payload)
        temp_path = Path(handle.name)
    os.replace(temp_path, json_path)

    csv_path = resolved / "absorbed_numeric_findings.csv"
    fields = list(asdict(report.findings[0]).keys()) if report.findings else [
        "canonical_id",
        "removed_chunk_id",
        "unit_label",
        "page_start",
        "page_end",
        "absorbed_into_candidate_chunk_id",
        "first_line",
        "candidate_contains_removed_text",
        "classification",
        "rationale",
        "excerpt",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for finding in report.findings:
            writer.writerow(asdict(finding))
