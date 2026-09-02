from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.primary_legal_knowledge import PrimaryKnowledgeMap
from app.domain.primary_rbs_families import PrimaryRBSFamilyRegistry


class PrimaryRBSFamilyError(RuntimeError):
    """Error controlado del diseño de familias generales B.2."""


def load_primary_rbs_family_registry(path: Path) -> PrimaryRBSFamilyRegistry:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryRBSFamilyError(f"No existe el registro de familias RBS: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return PrimaryRBSFamilyRegistry.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PrimaryRBSFamilyError("El registro de familias RBS B.2 no es válido.") from exc


def validate_primary_rbs_family_links(
    registry: PrimaryRBSFamilyRegistry,
    knowledge_map: PrimaryKnowledgeMap,
) -> None:
    """Comprueba que B.2 cubra todas las familias ya referidas por el Bloque A."""
    family_ids = {family.family_id for family in registry.families}
    entry_ids = {entry.entry_id for entry in knowledge_map.entries}
    required_families = {
        family
        for entry in knowledge_map.entries
        for family in entry.rbs_families
    }

    missing = required_families - family_ids
    if missing:
        raise PrimaryRBSFamilyError(
            f"B.2 no registra familias exigidas por el Bloque A: {sorted(missing)}"
        )

    for family in registry.families:
        unknown_entries = set(family.primary_entry_ids) - entry_ids
        if unknown_entries:
            raise PrimaryRBSFamilyError(
                f"{family.family_id} referencia entradas primarias desconocidas: "
                f"{sorted(unknown_entries)}"
            )
