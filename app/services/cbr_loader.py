from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.cbr import CBRCase

MAX_CBR_FILE_BYTES = 5 * 1024 * 1024


class CBRLoadError(ValueError):
    """Error controlado al cargar un corpus CBR."""


def load_cbr_cases_jsonl(path: Path) -> list[CBRCase]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise CBRLoadError(f"No existe el archivo CBR: {resolved.name}")
    if resolved.suffix.lower() != ".jsonl":
        raise CBRLoadError("El corpus CBR debe usar formato JSONL.")
    if resolved.stat().st_size > MAX_CBR_FILE_BYTES:
        raise CBRLoadError("El corpus CBR supera 5 MB.")

    cases: list[CBRCase] = []
    seen: set[str] = set()
    try:
        lines = resolved.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise CBRLoadError("No fue posible leer el corpus CBR.") from exc

    for number, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("El caso debe ser un objeto JSON.")
            if payload.get("anonymized") is not True:
                raise ValueError("El caso no declara anonimización validada.")
            if payload.get("validated") is not True:
                raise ValueError("El caso no declara validación previa.")
            case = CBRCase.model_validate(payload)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise CBRLoadError(
                f"Caso CBR inválido en la línea {number}."
            ) from exc
        if case.case_id in seen:
            raise CBRLoadError(f"case_id duplicado: {case.case_id}.")
        seen.add(case.case_id)
        cases.append(case)

    if not cases:
        raise CBRLoadError("El corpus CBR no contiene casos válidos.")
    return cases
