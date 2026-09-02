from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.domain.primary_rbs_corpus_validation import PrimaryRBSCorpusValidationReport
from app.domain.primary_rbs_decision_boundary import PrimaryRBSDecisionBoundaryMap
from app.domain.primary_rbs_inventory import CurrentRBSInventory


class PrimaryRBSCorpusValidationError(RuntimeError):
    """Error controlado de validación B.8."""


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryRBSCorpusValidationError(f"No existe {label}: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PrimaryRBSCorpusValidationError(f"No se pudo leer {label}.") from exc
    if not isinstance(payload, dict):
        raise PrimaryRBSCorpusValidationError(f"{label} debe ser un objeto JSON.")
    return payload


def _load_json_list(path: Path, *, label: str) -> list[dict[str, Any]]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryRBSCorpusValidationError(f"No existe {label}: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PrimaryRBSCorpusValidationError(f"No se pudo leer {label}.") from exc
    if not isinstance(payload, list) or not all(
        isinstance(item, dict) for item in payload
    ):
        raise PrimaryRBSCorpusValidationError(
            f"{label} debe ser una lista de objetos JSON."
        )
    return payload


def load_primary_rbs_corpus_validation_report(
    path: Path,
) -> PrimaryRBSCorpusValidationReport:
    payload = _load_json_object(path, label="el reporte B.8")
    try:
        return PrimaryRBSCorpusValidationReport.model_validate(payload)
    except ValidationError as exc:
        raise PrimaryRBSCorpusValidationError("El reporte B.8 no es válido.") from exc


def validate_primary_rbs_against_current_corpus(
    report: PrimaryRBSCorpusValidationReport,
    boundary_map: PrimaryRBSDecisionBoundaryMap,
    inventory: CurrentRBSInventory,
    *,
    primary_manifest_path: Path,
    fiscal_catalog_path: Path,
    temporal_registry_path: Path,
) -> None:
    """Valida B.8 contra el snapshot interno; no infiere vigencia normativa."""
    manifest = _load_json_object(primary_manifest_path, label="el manifiesto A.8")
    catalog = _load_json_list(fiscal_catalog_path, label="el catálogo fiscal")
    temporal = _load_json_object(temporal_registry_path, label="el registro temporal")

    manifest_ids = manifest.get("normative_corpus_ids")
    if not isinstance(manifest_ids, list) or not all(
        isinstance(item, str) for item in manifest_ids
    ):
        raise PrimaryRBSCorpusValidationError(
            "A.8 no expone normative_corpus_ids válidos."
        )
    if set(report.normative_corpus_ids) != set(manifest_ids):
        raise PrimaryRBSCorpusValidationError(
            "B.8 debe usar exactamente los 12 corpus de A.8."
        )

    catalog_normative_ids = {
        str(item.get("canonical_id"))
        for item in catalog
        if item.get("layer") == "normativa"
    }
    if not set(report.normative_corpus_ids) <= catalog_normative_ids:
        raise PrimaryRBSCorpusValidationError(
            "Faltan fuentes B.8 en el catálogo fiscal interno."
        )

    raw_gaps = temporal.get("coverage_gaps", [])
    if not isinstance(raw_gaps, list):
        raise PrimaryRBSCorpusValidationError("coverage_gaps temporal no es una lista.")
    blocked = {
        str(gap.get("canonical_id")).casefold()
        for gap in raw_gaps
        if isinstance(gap, dict)
        and gap.get("gap_type") == "document_wide_temporal_validity"
        and gap.get("status") == "unknown_fail_closed"
    }
    if set(report.document_wide_temporal_blocks) != blocked:
        raise PrimaryRBSCorpusValidationError(
            "B.8 no refleja los bloqueos temporales vigentes del registro."
        )
    if report.temporal_registry_source_sprint != temporal.get("source_sprint"):
        raise PrimaryRBSCorpusValidationError(
            "B.8 no corresponde al source_sprint temporal actual."
        )

    boundaries = {item.relation_id: item for item in boundary_map.boundaries}
    validations = {item.relation_id: item for item in report.relation_validations}
    if set(validations) != set(boundaries):
        raise PrimaryRBSCorpusValidationError(
            "B.8 debe validar exactamente las relaciones B.7."
        )

    known_refs = {ref for rule in inventory.rules for ref in rule.normative_refs}
    corpus_ids = set(report.normative_corpus_ids)
    for relation_id, validation in validations.items():
        boundary = boundaries[relation_id]
        if set(validation.normative_source_ids) != set(boundary.normative_source_ids):
            raise PrimaryRBSCorpusValidationError(
                f"{relation_id} altera fuentes normativas B.7."
            )
        if set(validation.exact_normative_refs) != set(boundary.exact_normative_refs):
            raise PrimaryRBSCorpusValidationError(
                f"{relation_id} altera referencias exactas B.7."
            )
        if not set(validation.normative_source_ids) <= corpus_ids:
            raise PrimaryRBSCorpusValidationError(
                f"{relation_id} sale del corpus cerrado A.8."
            )
        if not set(validation.exact_normative_refs) <= known_refs:
            raise PrimaryRBSCorpusValidationError(
                f"{relation_id} contiene referencias exactas no reconocidas por B.1."
            )
        expected_blocked = sorted(
            set(validation.normative_source_ids).intersection(blocked)
        )
        if validation.blocked_normative_sources != expected_blocked:
            raise PrimaryRBSCorpusValidationError(
                f"{relation_id} no refleja correctamente los bloqueos temporales."
            )

    rule_validations = {
        (item.rule_id, item.version): item for item in report.existing_rule_validations
    }
    inventory_rules = {(item.rule_id, item.version): item for item in inventory.rules}
    if set(rule_validations) != set(inventory_rules):
        raise PrimaryRBSCorpusValidationError(
            "B.8 debe validar exactamente las 14 reglas B.1."
        )
    for key, rule_validation in rule_validations.items():
        rule = inventory_rules[key]
        if rule_validation.normative_refs != rule.normative_refs:
            raise PrimaryRBSCorpusValidationError(
                f"{rule.rule_id} altera sus referencias normativas inventariadas."
            )
        ref_sources = {
            ref.split(":", 1)[0] for ref in rule_validation.normative_refs
        }
        if not ref_sources <= corpus_ids:
            raise PrimaryRBSCorpusValidationError(
                f"{rule.rule_id} referencia una fuente fuera del corpus A.8."
            )
