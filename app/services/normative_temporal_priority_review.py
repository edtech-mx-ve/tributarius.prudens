from __future__ import annotations

import csv
import json
import os
import re
import tempfile
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path


class NormativeTemporalPriorityReviewError(RuntimeError):
    """Error controlado durante la revisión temporal prioritaria."""


_EXPLICIT_ENTRY_RE = re.compile(
    r"\bentrar[aá]\s+en\s+vigor\b|\bentra\s+en\s+vigor\b",
    re.IGNORECASE,
)
_TRANSITORY_RE = re.compile(r"\btransitorio(?:s)?\b", re.IGNORECASE)
_EFFECTS_RE = re.compile(
    r"\b(?:surtir[aá]\s+efectos|efectos?\s+a\s+partir\s+de)\b",
    re.IGNORECASE,
)
_PUBLICATION_RE = re.compile(
    r"\bpublicaci[oó]n\s+en\s+el\s+diario\s+oficial\b",
    re.IGNORECASE,
)
_VIGENCIA_RE = re.compile(r"\bvigencia\b", re.IGNORECASE)

# Solo identifica una fecha textual candidata. No la convierte en effective_from.
_DATE_SIGNAL_RE = re.compile(
    r"\b("
    r"\d{1,2}\s+de\s+"
    r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|"
    r"octubre|noviembre|diciembre)\s+de\s+\d{4}"
    r"|\d{1,2}[/-]\d{1,2}[/-]\d{4}"
    r"|\d{4}-\d{2}-\d{2}"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PriorityTemporalEvidence:
    canonical_id: str
    source_path: str
    line_number: int
    classification: str
    explicit_date_signal: str | None
    line: str
    promotion_status: str = "candidate_only_requires_verification"


@dataclass(frozen=True)
class PriorityTemporalReviewReport:
    total_input_lines: int
    total_priority_lines: int
    liva_lines: int
    cpeum_lines: int
    strong_entry_into_force: int
    effects_from_date: int
    transitory_context: int
    publication_reference: int
    generic_validity: int
    unclassified: int
    candidates_with_explicit_date_signal: int
    promotion_ready: int
    records: tuple[PriorityTemporalEvidence, ...]


def classify_temporal_line(line: str) -> tuple[str, str | None]:
    explicit_date = _DATE_SIGNAL_RE.search(line)
    date_signal = explicit_date.group(1) if explicit_date else None

    if _EXPLICIT_ENTRY_RE.search(line):
        return "strong_entry_into_force", date_signal
    if _EFFECTS_RE.search(line):
        return "effects_from_date", date_signal
    if _TRANSITORY_RE.search(line):
        return "transitory_context", date_signal
    if _PUBLICATION_RE.search(line):
        return "publication_reference", date_signal
    if _VIGENCIA_RE.search(line):
        return "generic_validity", date_signal
    return "unclassified", date_signal


def _parse_positive_int(raw: str, *, field: str) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise NormativeTemporalPriorityReviewError(
            f"Valor entero inválido en {field}: {raw!r}."
        ) from exc
    if value <= 0:
        raise NormativeTemporalPriorityReviewError(
            f"{field} debe ser > 0; recibido={value}."
        )
    return value


def load_priority_evidence(
    *,
    input_csv: Path,
    priority_documents: tuple[str, ...] = ("liva", "cpeum"),
) -> tuple[list[PriorityTemporalEvidence], int]:
    path = input_csv.expanduser().resolve()
    if not path.is_file():
        raise NormativeTemporalPriorityReviewError(
            f"No existe evidence_lines de 19I.11: {path}"
        )

    priority = {item.casefold() for item in priority_documents}
    records: list[PriorityTemporalEvidence] = []
    total_input = 0

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"canonical_id", "source_path", "line_number", "line"}
            if reader.fieldnames is None or not required.issubset(reader.fieldnames):
                raise NormativeTemporalPriorityReviewError(
                    "CSV 19I.11 sin columnas requeridas."
                )

            for row in reader:
                total_input += 1
                canonical_id = (row.get("canonical_id") or "").strip()
                if canonical_id.casefold() not in priority:
                    continue
                source_path = (row.get("source_path") or "").strip()
                line = " ".join((row.get("line") or "").split())
                line_number = _parse_positive_int(
                    row.get("line_number") or "",
                    field="line_number",
                )
                if not source_path or not line:
                    raise NormativeTemporalPriorityReviewError(
                        "Registro prioritario vacío en source_path o line."
                    )
                classification, date_signal = classify_temporal_line(line)
                records.append(
                    PriorityTemporalEvidence(
                        canonical_id=canonical_id,
                        source_path=source_path,
                        line_number=line_number,
                        classification=classification,
                        explicit_date_signal=date_signal,
                        line=line,
                    )
                )
    except OSError as exc:
        raise NormativeTemporalPriorityReviewError(
            f"No se pudo leer {path}."
        ) from exc

    return records, total_input


def build_priority_review_report(
    *,
    records: Iterable[PriorityTemporalEvidence],
    total_input_lines: int,
) -> PriorityTemporalReviewReport:
    materialized = tuple(records)

    def count_class(name: str) -> int:
        return sum(item.classification == name for item in materialized)

    return PriorityTemporalReviewReport(
        total_input_lines=total_input_lines,
        total_priority_lines=len(materialized),
        liva_lines=sum(item.canonical_id.casefold() == "liva" for item in materialized),
        cpeum_lines=sum(
            item.canonical_id.casefold() == "cpeum" for item in materialized
        ),
        strong_entry_into_force=count_class("strong_entry_into_force"),
        effects_from_date=count_class("effects_from_date"),
        transitory_context=count_class("transitory_context"),
        publication_reference=count_class("publication_reference"),
        generic_validity=count_class("generic_validity"),
        unclassified=count_class("unclassified"),
        candidates_with_explicit_date_signal=sum(
            item.explicit_date_signal is not None for item in materialized
        ),
        # Fail-closed: este sprint no promueve ninguna fecha automáticamente.
        promotion_ready=0,
        records=materialized,
    )


def _atomic_write(path: Path, content: str) -> None:
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
        temporary = Path(handle.name)
    os.replace(temporary, path)


def write_priority_review_outputs(
    *,
    output_dir: Path,
    report: PriorityTemporalReviewReport,
) -> dict[str, Path]:
    root = output_dir.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    report_path = root / "priority_temporal_review.json"
    candidates_path = root / "priority_temporal_candidates.csv"

    _atomic_write(
        report_path,
        json.dumps(
            asdict(report),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )

    fieldnames = list(asdict(report.records[0]).keys()) if report.records else [
        "canonical_id",
        "source_path",
        "line_number",
        "classification",
        "explicit_date_signal",
        "line",
        "promotion_status",
    ]
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8-sig",
        newline="",
        delete=False,
        dir=root,
        prefix=".priority_temporal_candidates.",
        suffix=".tmp",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in report.records:
            writer.writerow(asdict(record))
        temporary = Path(handle.name)
    os.replace(temporary, candidates_path)

    return {
        "report": report_path,
        "candidates": candidates_path,
    }
