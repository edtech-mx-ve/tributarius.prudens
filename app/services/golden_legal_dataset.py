from __future__ import annotations

import json
from pathlib import Path

from app.domain.golden_legal_case import GoldenLegalCase

DEFAULT_GOLDEN_DATASET = Path("app/resources/legal_validation_golden_cases.json")


def load_golden_legal_cases(
    path: Path = DEFAULT_GOLDEN_DATASET,
) -> list[GoldenLegalCase]:
    """Carga y valida el dataset dorado sin ejecutar ni alterar el motor jurídico."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("El dataset dorado debe ser una lista JSON.")

    cases = [GoldenLegalCase.model_validate(item) for item in payload]
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("El dataset dorado contiene case_id duplicados.")
    return cases
