from __future__ import annotations

from collections import Counter

from app.domain.primary_cbr_inventory import CurrentCBRInventory
from app.domain.primary_cbr_source_situations import (
    PrimaryCBRSituationExtraction,
    PrimaryCBRSituationKind,
)
from app.domain.primary_legal_knowledge import PrimaryKnowledgeMap, PrimaryManual


class PrimaryCBRUNAMCaseError(RuntimeError):
    """Error controlado de extracción de casos prácticos UNAM C.3."""


def validate_unam_practical_case_extraction(
    extraction: PrimaryCBRSituationExtraction,
    knowledge_map: PrimaryKnowledgeMap,
    cbr_inventory: CurrentCBRInventory,
) -> None:
    """Contrasta C.3 con el capítulo V UNAM, A.2 y el inventario CBR C.1."""
    if extraction.source is not PrimaryManual.UNAM:
        raise PrimaryCBRUNAMCaseError("C.3 debe contener únicamente casos prácticos UNAM.")
    if extraction.baseline_commit != cbr_inventory.baseline_commit:
        raise PrimaryCBRUNAMCaseError("C.3 debe conservar el baseline inventariado en C.1.")
    if extraction.source_entry_count != 1:
        raise PrimaryCBRUNAMCaseError(
            "C.3 extrae los casos prácticos explícitos del capítulo V UNAM."
        )
    if extraction.expected_situations_per_entry != 13:
        raise PrimaryCBRUNAMCaseError(
            "El capítulo V UNAM contiene 13 casos prácticos explícitos inventariados."
        )
    if extraction.situation_count != 13:
        raise PrimaryCBRUNAMCaseError("C.3 debe contener exactamente 13 casos prácticos UNAM.")

    unam_entries = {
        entry.entry_id: entry
        for entry in knowledge_map.entries
        if entry.manual is PrimaryManual.UNAM
    }
    if set(unam_entries) != {
        "UNAM-I",
        "UNAM-II",
        "UNAM-III",
        "UNAM-IV",
        "UNAM-V",
        "UNAM-VI",
        "UNAM-VII",
    }:
        raise PrimaryCBRUNAMCaseError("La base primaria ya no contiene los 7 capítulos UNAM.")

    chapter_v = unam_entries["UNAM-V"]
    expected_ids = [f"U-CBR-SIT-{index:03d}" for index in range(1, 14)]
    if [item.situation_id for item in extraction.situations] != expected_ids:
        raise PrimaryCBRUNAMCaseError(
            "C.3 debe conservar una numeración determinista de los 13 casos UNAM."
        )

    if {item.source_entry_id for item in extraction.situations} != {"UNAM-V"}:
        raise PrimaryCBRUNAMCaseError(
            "Los casos prácticos explícitos C.3 pertenecen al capítulo V del manual UNAM."
        )

    for item in extraction.situations:
        if item.source_section_order != chapter_v.order:
            raise PrimaryCBRUNAMCaseError(f"Orden UNAM inconsistente en {item.situation_id}.")
        if item.source_section_title != chapter_v.title:
            raise PrimaryCBRUNAMCaseError(f"Título UNAM inconsistente en {item.situation_id}.")

    group_counts = Counter(
        "isr_persona_moral"
        if item.situation_id <= "U-CBR-SIT-005"
        else "isr_persona_fisica"
        if item.situation_id <= "U-CBR-SIT-011"
        else "iva"
        for item in extraction.situations
    )
    if group_counts != Counter(
        {"isr_persona_moral": 5, "isr_persona_fisica": 6, "iva": 2}
    ):
        raise PrimaryCBRUNAMCaseError(
            "C.3 debe preservar 5 casos ISR persona moral, 6 ISR persona física y 2 IVA."
        )

    rif_case = next(
        item for item in extraction.situations if item.situation_id == "U-CBR-SIT-008"
    )
    if (
        rif_case.kind is not PrimaryCBRSituationKind.HISTORICAL_REGIME
        or not rif_case.historical_regime_context
    ):
        raise PrimaryCBRUNAMCaseError(
            "El caso RIF UNAM debe conservarse como contexto de régimen histórico."
        )
    if any(
        item.historical_regime_context
        for item in extraction.situations
        if item.situation_id != rif_case.situation_id
    ):
        raise PrimaryCBRUNAMCaseError(
            "C.3 no debe extender la marca de régimen histórico fuera del caso RIF."
        )

    if cbr_inventory.source_tree_operational_case_count != 0:
        raise PrimaryCBRUNAMCaseError(
            "El baseline C.1 esperado por C.3 no contiene corpus CBR operacional versionado."
        )
    if cbr_inventory.cbr_is_normative_authority:
        raise PrimaryCBRUNAMCaseError("CBR no puede convertirse en autoridad normativa.")
    if extraction.operational_cases_created:
        raise PrimaryCBRUNAMCaseError("C.3 no debe crear casos operativos.")
