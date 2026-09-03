from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.primary_cbr_fact_normalization import PrimaryCBRFactNormalization
from app.domain.primary_cbr_inventory import CurrentCBRInventory
from app.domain.primary_cbr_source_situations import PrimaryCBRSituationExtraction


class PrimaryCBRFactNormalizationError(RuntimeError):
    """Error controlado de normalización de hechos CBR C.4."""


def load_primary_cbr_fact_normalization(path: Path) -> PrimaryCBRFactNormalization:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryCBRFactNormalizationError(
            f"No existe el recurso de normalización CBR C.4: {resolved}"
        )
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return PrimaryCBRFactNormalization.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PrimaryCBRFactNormalizationError(
            "El recurso de normalización CBR C.4 no es válido."
        ) from exc


def validate_primary_cbr_fact_normalization(
    normalization: PrimaryCBRFactNormalization,
    prodecon: PrimaryCBRSituationExtraction,
    unam: PrimaryCBRSituationExtraction,
    inventory: CurrentCBRInventory,
) -> None:
    """Valida C.4 contra C.1-C.3 sin crear casos operativos ni inferencia legal."""
    if normalization.baseline_commit != inventory.baseline_commit:
        raise PrimaryCBRFactNormalizationError(
            "C.4 debe conservar el baseline CBR inventariado en C.1."
        )
    if normalization.prodecon_situation_count != prodecon.situation_count:
        raise PrimaryCBRFactNormalizationError("C.4 perdió situaciones PRODECON de C.2.")
    if normalization.unam_situation_count != unam.situation_count:
        raise PrimaryCBRFactNormalizationError("C.4 perdió casos UNAM de C.3.")

    source_items = {item.situation_id: item for item in [*prodecon.situations, *unam.situations]}
    normalized_items = {item.situation_id: item for item in normalization.situations}
    if set(source_items) != set(normalized_items):
        raise PrimaryCBRFactNormalizationError(
            "C.4 debe cubrir exactamente las 37 situaciones fuente C.2/C.3."
        )

    raw_statement_count = sum(len(item.raw_fact_statements) for item in source_items.values())
    if normalization.source_raw_fact_statement_count != raw_statement_count:
        raise PrimaryCBRFactNormalizationError(
            "C.4 no conserva el número exacto de afirmaciones fuente."
        )

    expected_similarity_fields = inventory.similarity_fields
    if normalization.similarity_fields_from_c1 != expected_similarity_fields:
        raise PrimaryCBRFactNormalizationError(
            "C.4 debe usar exactamente los campos de similitud inventariados en C.1."
        )

    expected_required = [
        "taxpayer_type",
        "activity",
        "tax",
        "problem_type",
        "fiscal_year",
    ]
    if normalization.required_case_fields != expected_required:
        raise PrimaryCBRFactNormalizationError(
            "C.4 debe conservar los campos requeridos por CBRCase antes de C.5/C.10."
        )

    for situation_id, normalized in normalized_items.items():
        source = source_items[situation_id]
        if normalized.source is not source.source:
            raise PrimaryCBRFactNormalizationError(
                f"Fuente alterada durante C.4: {situation_id}."
            )
        if normalized.source_entry_id != source.source_entry_id:
            raise PrimaryCBRFactNormalizationError(
                f"Entrada primaria alterada durante C.4: {situation_id}."
            )
        if normalized.historical_regime_context != source.historical_regime_context:
            raise PrimaryCBRFactNormalizationError(
                f"Contexto histórico alterado durante C.4: {situation_id}."
            )
        if normalized.raw_fact_count != len(source.raw_fact_statements):
            raise PrimaryCBRFactNormalizationError(
                f"Conteo de afirmaciones fuente alterado en {situation_id}."
            )

        for fact in normalized.facts:
            expected_text = source.raw_fact_statements[fact.raw_fact_index - 1]
            if fact.source_text != expected_text:
                raise PrimaryCBRFactNormalizationError(
                    f"C.4 perdió trazabilidad literal en {fact.fact_id}."
                )
            if fact.legal_inference_added:
                raise PrimaryCBRFactNormalizationError(
                    f"C.4 añadió inferencia jurídica en {fact.fact_id}."
                )

        seed = normalized.similarity_seed
        unresolved_expected = []
        values = {
            "taxpayer_type": seed.taxpayer_type,
            "activity": seed.activity,
            "tax": seed.tax,
            "problem_type": seed.problem_type,
            "fiscal_year": seed.fiscal_year,
        }
        for field_name in normalization.required_case_fields:
            if values[field_name] is None:
                unresolved_expected.append(field_name)
        if normalized.unresolved_required_case_fields != unresolved_expected:
            raise PrimaryCBRFactNormalizationError(
                f"Campos pendientes CBR inconsistentes en {situation_id}."
            )

    if inventory.source_tree_operational_case_count != 0:
        raise PrimaryCBRFactNormalizationError(
            "C.4 parte del baseline sin corpus CBR operacional versionado."
        )
    if normalization.creates_operational_cases or normalization.modifies_existing_cbr_engine:
        raise PrimaryCBRFactNormalizationError(
            "C.4 no debe modificar el motor CBR ni crear casos operativos."
        )
    if normalization.source_is_normative_authority or normalization.can_control_legal_decision:
        raise PrimaryCBRFactNormalizationError(
            "La normalización CBR no puede convertirse en autoridad normativa."
        )
