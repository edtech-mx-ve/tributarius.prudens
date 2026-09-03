from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from app.domain.primary_cbr_inventory import CurrentCBRInventory
from app.domain.primary_cbr_source_situations import (
    PrimaryCBRSituationExtraction,
    PrimaryCBRSituationKind,
)
from app.domain.primary_legal_knowledge import PrimaryKnowledgeMap, PrimaryManual


class PrimaryCBRSourceSituationError(RuntimeError):
    """Error controlado de extracción de situaciones CBR primarias."""


def load_primary_cbr_situation_extraction(path: Path) -> PrimaryCBRSituationExtraction:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryCBRSourceSituationError(
            f"No existe la extracción de situaciones CBR: {resolved}"
        )
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return PrimaryCBRSituationExtraction.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PrimaryCBRSourceSituationError(
            "La extracción de situaciones CBR primarias no es válida."
        ) from exc


def validate_prodecon_cbr_situation_extraction(
    extraction: PrimaryCBRSituationExtraction,
    knowledge_map: PrimaryKnowledgeMap,
    cbr_inventory: CurrentCBRInventory,
) -> None:
    """Contrasta C.2 con PRODECON, A.1 y el inventario CBR C.1."""
    if extraction.source is not PrimaryManual.PRODECON:
        raise PrimaryCBRSourceSituationError("C.2 debe contener únicamente situaciones PRODECON.")
    if extraction.baseline_commit != cbr_inventory.baseline_commit:
        raise PrimaryCBRSourceSituationError("C.2 debe conservar el baseline inventariado en C.1.")
    if extraction.source_entry_count != 12:
        raise PrimaryCBRSourceSituationError("C.2 debe cubrir los 12 apartados PRODECON.")
    if extraction.expected_situations_per_entry != 2:
        raise PrimaryCBRSourceSituationError(
            "C.2 fija dos situaciones fuente por apartado PRODECON."
        )
    if extraction.situation_count != 24:
        raise PrimaryCBRSourceSituationError("C.2 debe contener exactamente 24 situaciones.")

    prodecon_entries = [
        entry for entry in knowledge_map.entries if entry.manual is PrimaryManual.PRODECON
    ]
    entry_by_id = {entry.entry_id: entry for entry in prodecon_entries}
    if len(entry_by_id) != 12:
        raise PrimaryCBRSourceSituationError(
            "La base primaria ya no contiene 12 apartados PRODECON."
        )

    used_entry_ids = {item.source_entry_id for item in extraction.situations}
    if used_entry_ids != set(entry_by_id):
        raise PrimaryCBRSourceSituationError(
            "C.2 debe cubrir exactamente los 12 entry_id PRODECON de la base primaria."
        )

    counts = Counter(item.source_entry_id for item in extraction.situations)
    if any(counts[entry_id] != 2 for entry_id in entry_by_id):
        raise PrimaryCBRSourceSituationError(
            "Cada apartado PRODECON debe aportar exactamente dos situaciones CBR fuente."
        )

    for situation in extraction.situations:
        entry = entry_by_id[situation.source_entry_id]
        if situation.source_section_order != entry.order:
            raise PrimaryCBRSourceSituationError(
                f"Orden PRODECON inconsistente en {situation.situation_id}."
            )
        if situation.source_section_title != entry.title:
            raise PrimaryCBRSourceSituationError(
                f"Título PRODECON inconsistente en {situation.situation_id}."
            )
        if situation.source_entry_id == "PRODECON-12":
            if (
                situation.kind is not PrimaryCBRSituationKind.HISTORICAL_REGIME
                or not situation.historical_regime_context
            ):
                raise PrimaryCBRSourceSituationError(
                    "C.2 debe preservar RIF como contenido de régimen histórico."
                )
        elif situation.historical_regime_context:
            raise PrimaryCBRSourceSituationError(
                f"C.2 marcó contexto histórico de régimen fuera de RIF: {situation.situation_id}."
            )

    if cbr_inventory.source_tree_operational_case_count != 0:
        raise PrimaryCBRSourceSituationError(
            "El baseline C.1 esperado por C.2 no debe contener corpus CBR operacional versionado."
        )
    if cbr_inventory.cbr_is_normative_authority:
        raise PrimaryCBRSourceSituationError("CBR no puede convertirse en autoridad normativa.")
    if extraction.operational_cases_created:
        raise PrimaryCBRSourceSituationError("C.2 no debe crear casos operativos.")
