from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SemanticRuntimeSmokeError(RuntimeError):
    """Fallo controlado durante smoke E2E del runtime semántico."""


@dataclass(frozen=True)
class SmokeExpectation:
    case_id: str
    query: str
    expected_document_id: str
    fiscal_year: int = 2026


@dataclass(frozen=True)
class SmokeCaseResult:
    case_id: str
    expected_document_id: str
    returned_document_ids: tuple[str, ...]
    primary_document_found: bool
    status: str
    evidence_count: int
    normative_reference_count: int
    jurisprudence_count: int


DEFAULT_SMOKE_CASES: tuple[SmokeExpectation, ...] = (
    SmokeExpectation(
        case_id="liva_tasa",
        query="¿Cuál es la tasa general del IVA y cuál es su fundamento?",
        expected_document_id="liva",
    ),
    SmokeExpectation(
        case_id="cpeum_principios",
        query=(
            "¿Qué principios constitucionales limitan la creación "
            "y cobro de contribuciones en México?"
        ),
        expected_document_id="cpeum",
    ),
    SmokeExpectation(
        case_id="lieps",
        query="¿Qué regula la Ley del IEPS y cuál es su fundamento legal?",
        expected_document_id="lieps",
    ),
)


def _normalize_document_id(value: str) -> str:
    clean = value.strip().replace("\\\\", "/").rsplit("/", 1)[-1]
    if clean.casefold().endswith(".md"):
        clean = clean[:-3]
    return clean.casefold()


def _document_ids(evidence: object) -> tuple[str, ...]:
    if not isinstance(evidence, list):
        return ()
    values: list[str] = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        if item.get("kind") != "document":
            continue

        # El presenter 19I expone document_id a nivel superior. Se conserva
        # compatibilidad con fixtures antiguos que lo anidaban en metadata.
        raw = item.get("document_id")
        if isinstance(raw, str) and raw.strip():
            values.append(_normalize_document_id(raw))
            continue

        metadata = item.get("metadata")
        if isinstance(metadata, dict):
            raw = metadata.get("document_id")
            if isinstance(raw, str) and raw.strip():
                values.append(_normalize_document_id(raw))
                continue

        raw_source = item.get("source_reference")
        if isinstance(raw_source, str) and raw_source.strip():
            values.append(_normalize_document_id(raw_source))
    return tuple(values)


def inspect_consultation_payload(
    payload: dict[str, Any],
    expectation: SmokeExpectation,
) -> SmokeCaseResult:
    status = str(payload.get("status", ""))
    result = payload.get("result")
    if status != "ready" or not isinstance(result, dict):
        raise SemanticRuntimeSmokeError(
            f"{expectation.case_id}: respuesta no lista; status={status!r}"
        )

    evidence = result.get("evidence")
    document_ids = _document_ids(evidence)

    normative_count = 0
    refs = result.get("applicable_normative_refs")
    if isinstance(refs, list):
        normative_count = len(refs)

    jurisprudence = result.get("jurisprudence")
    jurisprudence_count = 0
    if isinstance(jurisprudence, dict):
        items = jurisprudence.get("items")
        if isinstance(items, list):
            jurisprudence_count = len(items)

    return SmokeCaseResult(
        case_id=expectation.case_id,
        expected_document_id=expectation.expected_document_id,
        returned_document_ids=document_ids,
        primary_document_found=expectation.expected_document_id in document_ids,
        status=status,
        evidence_count=len(evidence) if isinstance(evidence, list) else 0,
        normative_reference_count=normative_count,
        jurisprudence_count=jurisprudence_count,
    )


def assert_smoke_result(result: SmokeCaseResult) -> None:
    if not result.primary_document_found:
        raise SemanticRuntimeSmokeError(
            f"{result.case_id}: no apareció documento esperado "
            f"{result.expected_document_id}; "
            f"devueltos={','.join(result.returned_document_ids)}"
        )
    if result.evidence_count <= 0:
        raise SemanticRuntimeSmokeError(
            f"{result.case_id}: la respuesta carece de evidencia."
        )
