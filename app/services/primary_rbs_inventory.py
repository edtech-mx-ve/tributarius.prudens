from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.primary_rbs_inventory import CurrentRBSInventory
from app.domain.rules import RuleSet
from app.services.rule_loader import RuleLoadError, load_rule_set


class CurrentRBSInventoryError(RuntimeError):
    """Error controlado del inventario RBS B.1."""


def load_current_rbs_inventory(path: Path) -> CurrentRBSInventory:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise CurrentRBSInventoryError(f"No existe el inventario RBS: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return CurrentRBSInventory.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise CurrentRBSInventoryError("El inventario RBS B.1 no es válido.") from exc


def validate_current_rbs_inventory(
    inventory: CurrentRBSInventory,
    production_dir: Path,
) -> None:
    """Contrasta B.1 con los JSON reales sin alterar las reglas de producción."""
    resolved = production_dir.expanduser().resolve()
    actual_files = sorted(path.name for path in resolved.glob("*.json"))
    if actual_files != sorted(inventory.production_rule_files):
        raise CurrentRBSInventoryError(
            "Los archivos RBS de producción no coinciden con el inventario B.1."
        )

    actual: dict[tuple[str, str], tuple[str, str, tuple[str, ...], bool, bool]] = {}
    try:
        for filename in actual_files:
            rule_set = load_rule_set(resolved / filename)
            for rule in rule_set.rules:
                key = (rule.rule_id, rule.version)
                if key in actual:
                    raise CurrentRBSInventoryError(
                        f"Regla duplicada entre archivos de producción: {rule.rule_id}."
                    )
                actual[key] = (
                    filename,
                    rule.conclusion_code,
                    tuple(rule.normative_refs),
                    rule.enabled,
                    rule.requires_human_review,
                )
    except RuleLoadError as exc:
        raise CurrentRBSInventoryError(
            "No fue posible validar una regla RBS de producción."
        ) from exc

    expected = {
        (rule.rule_id, rule.version): (
            rule.source_file,
            rule.conclusion_code,
            tuple(rule.normative_refs),
            rule.enabled,
            rule.requires_human_review,
        )
        for rule in inventory.rules
    }
    if actual != expected:
        raise CurrentRBSInventoryError(
            "El contenido RBS de producción no coincide con el inventario B.1."
        )


def load_current_production_rule_set(
    inventory_path: Path,
    production_dir: Path,
) -> RuleSet:
    """Carga en memoria el RBS productivo exacto definido por B.1."""
    inventory = load_current_rbs_inventory(inventory_path)
    validate_current_rbs_inventory(inventory, production_dir)

    resolved = production_dir.expanduser().resolve()
    schema_versions: set[str] = set()
    rules = []

    try:
        for filename in inventory.production_rule_files:
            rule_set = load_rule_set(resolved / filename)
            schema_versions.add(rule_set.schema_version)
            rules.extend(rule_set.rules)
    except RuleLoadError as exc:
        raise CurrentRBSInventoryError(
            "No fue posible ensamblar el RBS productivo B.1."
        ) from exc

    if len(schema_versions) != 1:
        raise CurrentRBSInventoryError(
            "Los archivos RBS de producci?n usan esquemas incompatibles."
        )

    if len(rules) != inventory.total_rules:
        raise CurrentRBSInventoryError(
            "El RBS ensamblado no coincide con total_rules de B.1."
        )

    return RuleSet(
        schema_version=next(iter(schema_versions)),
        rules=rules,
    )
