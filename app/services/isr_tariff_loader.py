from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.isr import ISRTariff

MAX_TARIFF_FILE_BYTES = 1024 * 1024


class ISRTariffLoadError(ValueError):
    """Error controlado al cargar parámetros de ISR."""


def load_isr_tariff(path: Path) -> ISRTariff:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ISRTariffLoadError(f"No existe la tarifa: {resolved.name}")
    if resolved.suffix.lower() != ".json":
        raise ISRTariffLoadError("Solo se admiten tarifas JSON.")
    if resolved.stat().st_size > MAX_TARIFF_FILE_BYTES:
        raise ISRTariffLoadError("La tarifa supera 1 MB.")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ISRTariffLoadError("No fue posible leer una tarifa JSON válida.") from exc
    try:
        return ISRTariff.model_validate(payload)
    except ValidationError as exc:
        raise ISRTariffLoadError(f"Esquema de tarifa inválido: {exc}") from exc
