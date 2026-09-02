from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.primary_rbs_inventory import CurrentRBSInventory
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
