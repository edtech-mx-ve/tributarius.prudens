from __future__ import annotations

import csv
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


class NormativeTemporalCandidateVerifierError(RuntimeError):
    """Error controlado durante verificación de candidatos temporales."""


_DECREE_RE = re.compile(r"\bdecreto\b", re.IGNORECASE)
_REFORM_RE = re.compile(
    r"\b(reforma(?:n|do|da|s)?|adiciona(?:n|do|da|s)?|deroga(?:n|do|da|s)?)\b",
    re.IGNORECASE,
)
_TRANSITORY_RE = re.compile(r"\btransitorio(?:s)?\b", re.IGNORECASE)
_ARTICLE_RE = re.compile(
    r"\bart[ií]culo\s+[0-9]+(?:\s*-\s*[A-Z0-9]+)*\b",
    re.IGNORECASE,
)
_WHOLE_LAW_RE = re.compile(
    r"\b(la presente ley|esta ley|la presente constituci[oó]n)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TemporalCandidateVerification:
    canonical_id: str
    source_path: str
    line_number: int
    classification: str
    explicit_date_signal: str
    candidate_line: str
    context_before: tuple[str, ...]
    context_after: tuple[str, ...]
    scope_classification: str
    scope_reason: str
    promotion_status: str = "requires_human_verification"


@dataclass(frozen=True)
class TemporalCandidateVerificationReport:
    input_candidates: int
    explicit_date_candidates: int
    verified_records: int
    whole_document_candidates: int
    amendment_specific_candidates: int
    ambiguous_scope_candidates: int
    promotion_ready: int
    records: tuple[TemporalCandidateVerification, ...]


def _read_source_context(
    *,
    source_path: Path,
    line_number: int,
    radius: int,
) -> tuple[tuple[str, ...], str, tuple[str, ...]]:
    if radius < 1 or radius > 20:
        raise NormativeTemporalCandidateVerifierError(
            f"radius fuera de rango seguro: {radius}."
        )
    if not source_path.is_file():
        raise NormativeTemporalCandidateVerifierError(
            f"No existe fuente normalizada: {source_path}"
        )
    try:
        lines = source_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise NormativeTemporalCandidateVerifierError(
            f"No se pudo leer fuente: {source_path}"
        ) from exc

    if line_number <= 0 or line_number > len(lines):
        raise NormativeTemporalCandidateVerifierError(
            f"line_number fuera de rango en {source_path}: {line_number}."
        )

    index = line_number - 1
    before = tuple(
        " ".join(line.split())
        for line in lines[max(0, index - radius) : index]
        if line.strip()
    )
    current = " ".join(lines[index].split())
    after = tuple(
        " ".join(line.split())
        for line in lines[index + 1 : min(len(lines), index + radius + 1)]
        if line.strip()
    )
    return before, current, after


def classify_scope(
    *,
    candidate_line: str,
    context_before: tuple[str, ...],
    context_after: tuple[str, ...],
) -> tuple[str, str]:
    context = " ".join((*context_before, candidate_line, *context_after))

    has_decree = _DECREE_RE.search(context) is not None
    has_reform = _REFORM_RE.search(context) is not None
    has_transitory = _TRANSITORY_RE.search(context) is not None
    has_article = _ARTICLE_RE.search(context) is not None
    has_whole_law = _WHOLE_LAW_RE.search(context) is not None

    if has_whole_law and not (has_decree or has_reform):
        return (
            "whole_document_candidate",
            "El contexto menciona expresamente la ley/constitución como un todo "
            "sin señal cercana de decreto de reforma.",
        )

    if has_decree or has_reform or (has_transitory and has_article):
        return (
            "amendment_specific_candidate",
            "El contexto contiene señales de decreto/reforma/transitorio ligado "
            "a una unidad normativa; no debe trasladarse al documento completo.",
        )

    return (
        "ambiguous_scope_candidate",
        "La evidencia temporal no permite determinar con seguridad si la fecha "
        "aplica al documento completo o a una reforma/unidad específica.",
    )


def load_and_verify_candidates(
    *,
    input_csv: Path,
    context_radius: int = 5,
) -> TemporalCandidateVerificationReport:
    path = input_csv.expanduser().resolve()
    if not path.is_file():
        raise NormativeTemporalCandidateVerifierError(
            f"No existe CSV de candidatos 19I.12: {path}"
        )

    records: list[TemporalCandidateVerification] = []
    input_candidates = 0
    explicit_candidates = 0

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {
                "canonical_id",
                "source_path",
                "line_number",
                "classification",
                "explicit_date_signal",
                "line",
                "promotion_status",
            }
            if reader.fieldnames is None or not required.issubset(reader.fieldnames):
                raise NormativeTemporalCandidateVerifierError(
                    "CSV 19I.12 sin columnas requeridas."
                )

            for row in reader:
                input_candidates += 1
                date_signal = (row.get("explicit_date_signal") or "").strip()
                if not date_signal:
                    continue
                explicit_candidates += 1

                canonical_id = (row.get("canonical_id") or "").strip()
                source_raw = (row.get("source_path") or "").strip()
                line_raw = (row.get("line_number") or "").strip()
                classification = (row.get("classification") or "").strip()
                if not canonical_id or not source_raw or not classification:
                    raise NormativeTemporalCandidateVerifierError(
                        "Candidato temporal incompleto."
                    )
                try:
                    line_number = int(line_raw)
                except ValueError as exc:
                    raise NormativeTemporalCandidateVerifierError(
                        f"line_number inválido: {line_raw!r}."
                    ) from exc

                source_path = Path(source_raw).expanduser().resolve()
                before, current, after = _read_source_context(
                    source_path=source_path,
                    line_number=line_number,
                    radius=context_radius,
                )
                scope, reason = classify_scope(
                    candidate_line=current,
                    context_before=before,
                    context_after=after,
                )

                records.append(
                    TemporalCandidateVerification(
                        canonical_id=canonical_id,
                        source_path=str(source_path),
                        line_number=line_number,
                        classification=classification,
                        explicit_date_signal=date_signal,
                        candidate_line=current,
                        context_before=before,
                        context_after=after,
                        scope_classification=scope,
                        scope_reason=reason,
                    )
                )
    except OSError as exc:
        raise NormativeTemporalCandidateVerifierError(
            f"No se pudo leer {path}."
        ) from exc

    materialized = tuple(records)
    return TemporalCandidateVerificationReport(
        input_candidates=input_candidates,
        explicit_date_candidates=explicit_candidates,
        verified_records=len(materialized),
        whole_document_candidates=sum(
            item.scope_classification == "whole_document_candidate"
            for item in materialized
        ),
        amendment_specific_candidates=sum(
            item.scope_classification == "amendment_specific_candidate"
            for item in materialized
        ),
        ambiguous_scope_candidates=sum(
            item.scope_classification == "ambiguous_scope_candidate"
            for item in materialized
        ),
        # Fail-closed: incluso whole_document_candidate exige verificación humana.
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
        temp = Path(handle.name)
    os.replace(temp, path)


def write_verification_outputs(
    *,
    output_dir: Path,
    report: TemporalCandidateVerificationReport,
) -> dict[str, Path]:
    root = output_dir.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    json_path = root / "temporal_candidate_verification.json"
    csv_path = root / "temporal_candidate_verification.csv"

    _atomic_write(
        json_path,
        json.dumps(
            asdict(report),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )

    fieldnames = [
        "canonical_id",
        "source_path",
        "line_number",
        "classification",
        "explicit_date_signal",
        "candidate_line",
        "context_before",
        "context_after",
        "scope_classification",
        "scope_reason",
        "promotion_status",
    ]
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8-sig",
        newline="",
        delete=False,
        dir=root,
        prefix=".temporal_candidate_verification.",
        suffix=".tmp",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in report.records:
            row = asdict(record)
            row["context_before"] = " || ".join(record.context_before)
            row["context_after"] = " || ".join(record.context_after)
            writer.writerow(row)
        temp = Path(handle.name)
    os.replace(temp, csv_path)

    return {"report": json_path, "csv": csv_path}
