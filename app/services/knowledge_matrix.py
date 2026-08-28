from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.domain.knowledge import MasterMatrixEntryCreate, MasterMatrixEntryRead
from app.repositories.knowledge import KnowledgeRepository


class KnowledgeMatrixError(RuntimeError):
    """Error controlado de carga o validación de la matriz maestra."""


_MATRIX_ADAPTER = TypeAdapter(list[MasterMatrixEntryCreate])


def load_matrix_file(path: Path) -> list[MasterMatrixEntryCreate]:
    resolved = path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise KnowledgeMatrixError(f"No existe el archivo de matriz: {resolved}")
    if resolved.suffix.lower() != ".json":
        raise KnowledgeMatrixError("La matriz maestra debe estar en formato JSON.")

    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
        entries = _MATRIX_ADAPTER.validate_python(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise KnowledgeMatrixError("La matriz maestra no es válida.") from exc

    module_keys = [entry.module_key for entry in entries]
    if len(module_keys) != len(set(module_keys)):
        raise KnowledgeMatrixError("La matriz contiene module_key duplicados.")
    return entries


def persist_matrix(
    session: Session,
    entries: list[MasterMatrixEntryCreate],
) -> list[MasterMatrixEntryRead]:
    repository = KnowledgeRepository(session)
    persisted = [repository.upsert_matrix_entry(entry) for entry in entries]
    return [
        MasterMatrixEntryRead(
            id=item.id,
            module_key=item.module_key,
            module_name=item.module_name,
            prodecon_refs=item.prodecon_refs,
            unam_refs=item.unam_refs,
            normative_refs=item.normative_refs,
            jurisprudential_refs=item.jurisprudential_refs,
            rule_refs=item.rule_refs,
            calculation_refs=item.calculation_refs,
            cbr_refs=item.cbr_refs,
            notes=item.notes,
        )
        for item in persisted
    ]


def list_matrix(session: Session) -> list[MasterMatrixEntryRead]:
    repository = KnowledgeRepository(session)
    return [
        MasterMatrixEntryRead(
            id=item.id,
            module_key=item.module_key,
            module_name=item.module_name,
            prodecon_refs=item.prodecon_refs,
            unam_refs=item.unam_refs,
            normative_refs=item.normative_refs,
            jurisprudential_refs=item.jurisprudential_refs,
            rule_refs=item.rule_refs,
            calculation_refs=item.calculation_refs,
            cbr_refs=item.cbr_refs,
            notes=item.notes,
        )
        for item in repository.list_matrix_entries()
    ]
