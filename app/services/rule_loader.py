from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.rules import RuleSet

MAX_RULE_FILE_BYTES = 5 * 1024 * 1024


class RuleLoadError(ValueError):
    """Error controlado de carga."""


def load_rule_set(path: Path) -> RuleSet:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise RuleLoadError(f"No existe el archivo: {resolved.name}")
    if resolved.suffix.lower() != ".json":
        raise RuleLoadError("Solo se admiten reglas JSON.")
    if resolved.stat().st_size > MAX_RULE_FILE_BYTES:
        raise RuleLoadError("El archivo supera 5 MB.")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuleLoadError("JSON de reglas inválido.") from exc
    try:
        return RuleSet.model_validate(payload)
    except ValidationError as exc:
        raise RuleLoadError(f"Esquema de reglas inválido: {exc}") from exc
