from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.cbr import CaseStatus, CBRCase, CBRQuery
from app.domain.primary_cbr_inventory import CurrentCBRInventory
from app.models.cbr import CBRCaseRecord
from app.services.cbr_anonymizer import PATTERNS
from app.services.cbr_loader import MAX_CBR_FILE_BYTES, CBRLoadError, load_cbr_cases_jsonl
from app.services.cbr_reasoning import MINIMUM_REUSE_SIMILARITY
from cbr.engine import CRITICAL_FIELDS, MINIMUM_CBR_SIMILARITY
from cbr.similarity import (
    EXACT_FIELDS,
    FIELD_WEIGHTS,
    OPTIONAL_EXACT_FIELDS,
    SEMANTIC_TOKEN_FIELDS,
)
from scripts.retrieve_similar_cases import MAX_QUERY_BYTES, load_query


class CurrentCBRInventoryError(RuntimeError):
    """Error controlado del inventario CBR C.1."""


POST_BASELINE_OPERATIONAL_CASE_FILES = frozenset(
    {
        "cbr/data/production_cases.jsonl",
    }
)


def load_current_cbr_inventory(path: Path) -> CurrentCBRInventory:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise CurrentCBRInventoryError(f"No existe el inventario CBR: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return CurrentCBRInventory.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise CurrentCBRInventoryError("El inventario CBR C.1 no es válido.") from exc


def _load_primary_knowledge_cbr_families(path: Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        entries = payload["entries"]
        if not isinstance(entries, list):
            raise TypeError("entries debe ser una lista")
        families = {
            family
            for entry in entries
            if isinstance(entry, dict)
            for family in entry.get("cbr_families", [])
            if isinstance(family, str)
        }
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise CurrentCBRInventoryError(
            "No fue posible leer las familias CBR referenciadas por la base primaria."
        ) from exc
    return sorted(families)


def validate_current_cbr_inventory(
    inventory: CurrentCBRInventory,
    repository_root: Path,
) -> None:
    """Contrasta C.1 con el CBR real sin alterar su implementación."""
    root = repository_root.expanduser().resolve()
    if not root.is_dir():
        raise CurrentCBRInventoryError(f"No existe el repositorio: {root}")

    missing_components = [
        item.path for item in inventory.components if not (root / item.path).is_file()
    ]
    if missing_components:
        raise CurrentCBRInventoryError(
            f"Faltan componentes CBR inventariados: {missing_components}."
        )

    if list(CBRCase.model_fields) != inventory.case_schema_fields:
        raise CurrentCBRInventoryError("El esquema CBRCase difiere del inventario C.1.")
    if list(CBRQuery.model_fields) != inventory.query_schema_fields:
        raise CurrentCBRInventoryError("El esquema CBRQuery difiere del inventario C.1.")

    actual_statuses = [status.value for status in CaseStatus]
    if actual_statuses != inventory.case_statuses:
        raise CurrentCBRInventoryError("Los estados CBR difieren del inventario C.1.")

    actual_similarity_fields = [field.value for field in FIELD_WEIGHTS]
    actual_weights = {field.value: weight for field, weight in FIELD_WEIGHTS.items()}
    if actual_similarity_fields != inventory.similarity_fields:
        raise CurrentCBRInventoryError("Los campos de similitud CBR cambiaron.")
    if actual_weights != inventory.field_weights:
        raise CurrentCBRInventoryError("Los pesos de similitud CBR cambiaron.")

    if sorted(field.value for field in EXACT_FIELDS) != sorted(inventory.exact_fields):
        raise CurrentCBRInventoryError("Los campos CBR de coincidencia exacta cambiaron.")
    if sorted(field.value for field in SEMANTIC_TOKEN_FIELDS) != sorted(
        inventory.semantic_token_fields
    ):
        raise CurrentCBRInventoryError("Los campos CBR tokenizados cambiaron.")
    if sorted(field.value for field in OPTIONAL_EXACT_FIELDS) != sorted(
        inventory.optional_exact_fields
    ):
        raise CurrentCBRInventoryError("Los campos CBR opcionales exactos cambiaron.")
    if list(CRITICAL_FIELDS) != inventory.critical_fields:
        raise CurrentCBRInventoryError("Los campos críticos CBR cambiaron.")

    if MINIMUM_CBR_SIMILARITY != inventory.minimum_retrieval_similarity:
        raise CurrentCBRInventoryError("El umbral de recuperación CBR cambió.")
    if MINIMUM_REUSE_SIMILARITY != inventory.minimum_reuse_similarity:
        raise CurrentCBRInventoryError("El umbral de reutilización CBR cambió.")
    if MAX_CBR_FILE_BYTES != inventory.cbr_loader_max_bytes:
        raise CurrentCBRInventoryError("El límite del corpus CBR cambió.")
    if MAX_QUERY_BYTES != inventory.query_loader_max_bytes:
        raise CurrentCBRInventoryError("El límite de consulta CBR cambió.")
    if CBRCaseRecord.__tablename__ != inventory.storage_table:
        raise CurrentCBRInventoryError("La tabla de persistencia CBR cambió.")

    top_k = CBRQuery.model_fields["top_k"]
    if top_k.default != inventory.query_top_k_default:
        raise CurrentCBRInventoryError("El top_k por defecto CBR cambió.")

    fixture_cases_path = root / inventory.fixture_cases_file
    try:
        fixture_cases = load_cbr_cases_jsonl(fixture_cases_path)
    except CBRLoadError as exc:
        raise CurrentCBRInventoryError("Los casos fixture CBR ya no son válidos.") from exc
    if [case.case_id for case in fixture_cases] != inventory.fixture_case_ids:
        raise CurrentCBRInventoryError("Los casos fixture CBR difieren de C.1.")

    try:
        load_query(root / inventory.fixture_query_file)
    except ValueError as exc:
        raise CurrentCBRInventoryError("La consulta fixture CBR ya no es válida.") from exc

    data_dir = root / "cbr" / "data"
    actual_operational_files = {
        item.relative_to(root).as_posix()
        for item in data_dir.glob("*.jsonl")
        if item.is_file()
    }

    baseline_operational_files = set(
        inventory.source_tree_operational_case_files
    )

    missing_baseline_files = sorted(
        baseline_operational_files
        - actual_operational_files
    )

    unexpected_operational_files = sorted(
        actual_operational_files
        - baseline_operational_files
        - POST_BASELINE_OPERATIONAL_CASE_FILES
    )

    if missing_baseline_files or unexpected_operational_files:
        raise CurrentCBRInventoryError(
            "El corpus operacional CBR versionado difiere "
            "del baseline C.1 o contiene extensiones "
            "posteriores no autorizadas."
        )

    actual_identifier_types = [kind for kind, _ in PATTERNS]
    if actual_identifier_types != inventory.anonymizer_identifier_types:
        raise CurrentCBRInventoryError("Los identificadores del anonimizador CBR cambiaron.")

    primary_families = _load_primary_knowledge_cbr_families(
        root / "app" / "resources" / "primary_legal_knowledge_map.json"
    )
    if primary_families != inventory.primary_knowledge_cbr_families:
        raise CurrentCBRInventoryError(
            "Las referencias de familias CBR de la base primaria difieren de C.1."
        )

    orchestrator_source = (root / "app" / "services" / "hybrid_orchestrator.py").read_text(
        encoding="utf-8"
    )
    orchestration_source = (root / "app" / "domain" / "orchestration.py").read_text(
        encoding="utf-8"
    )
    if (
        "from cbr.engine import retrieve_similar_cases" not in orchestrator_source
        or "assess_case_reuse" not in orchestrator_source
        or "cbr_cases: list[CBRCase] | None = None" not in orchestrator_source
        or "cbr_query: CBRQuery | None = None" not in orchestration_source
    ):
        raise CurrentCBRInventoryError("La integración CBR del orquestador cambió.")
