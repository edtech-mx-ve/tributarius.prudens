from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.primary_cbr_fact_normalization import PrimaryCBRFactNormalization
from app.domain.primary_cbr_inventory import CurrentCBRInventory
from app.domain.primary_cbr_problem_institution import (
    PrimaryCBRProblemInstitutionClassification,
)
from app.domain.primary_legal_knowledge import (
    FiscalProblemInstitutionKind,
    FiscalProblemInstitutionTaxonomy,
)


class PrimaryCBRProblemInstitutionError(RuntimeError):
    """Error controlado de clasificación problema/institución C.5."""


def load_primary_cbr_problem_institution_classification(
    path: Path,
) -> PrimaryCBRProblemInstitutionClassification:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryCBRProblemInstitutionError(
            f"No existe la clasificación CBR C.5: {resolved}"
        )
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return PrimaryCBRProblemInstitutionClassification.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PrimaryCBRProblemInstitutionError(
            "La clasificación problema/institución C.5 no es válida."
        ) from exc


def validate_primary_cbr_problem_institution_classification(
    classification: PrimaryCBRProblemInstitutionClassification,
    normalization: PrimaryCBRFactNormalization,
    taxonomy: FiscalProblemInstitutionTaxonomy,
    inventory: CurrentCBRInventory,
) -> None:
    """Contrasta C.5 con hechos C.4, taxonomía A.6 e inventario CBR C.1."""
    if classification.baseline_commit != normalization.baseline_commit:
        raise PrimaryCBRProblemInstitutionError("C.5 debe conservar el baseline de C.4.")
    if classification.baseline_commit != inventory.baseline_commit:
        raise PrimaryCBRProblemInstitutionError("C.5 debe conservar el baseline CBR de C.1.")
    if classification.taxonomy_schema_version != taxonomy.schema_version:
        raise PrimaryCBRProblemInstitutionError("C.5 no corresponde a la versión A.6 cargada.")
    if classification.taxonomy_concept_count != len(taxonomy.concepts):
        raise PrimaryCBRProblemInstitutionError("C.5 no refleja todos los conceptos A.6.")

    problem_count = sum(
        concept.kind is FiscalProblemInstitutionKind.PROBLEM for concept in taxonomy.concepts
    )
    institution_count = sum(
        concept.kind is FiscalProblemInstitutionKind.INSTITUTION
        for concept in taxonomy.concepts
    )
    if classification.taxonomy_problem_count != problem_count:
        raise PrimaryCBRProblemInstitutionError("Conteo de problemas A.6 inconsistente.")
    if classification.taxonomy_institution_count != institution_count:
        raise PrimaryCBRProblemInstitutionError("Conteo de instituciones A.6 inconsistente.")

    normalized_by_id = {item.situation_id: item for item in normalization.situations}
    classified_by_id = {item.situation_id: item for item in classification.classifications}
    if set(classified_by_id) != set(normalized_by_id):
        raise PrimaryCBRProblemInstitutionError(
            "C.5 debe clasificar exactamente las 37 situaciones normalizadas C.4."
        )
    if classification.source_situation_count != normalization.normalized_situation_count:
        raise PrimaryCBRProblemInstitutionError("C.5 perdió situaciones fuente de C.4.")

    concepts = {concept.concept_id: concept for concept in taxonomy.concepts}
    for situation_id, result in classified_by_id.items():
        normalized = normalized_by_id[situation_id]
        if (
            result.source is not normalized.source
            or result.source_entry_id != normalized.source_entry_id
            or result.historical_regime_context != normalized.historical_regime_context
        ):
            raise PrimaryCBRProblemInstitutionError(
                f"C.5 perdió identidad fuente en {situation_id}."
            )

        known_fact_ids = {fact.fact_id for fact in normalized.facts}
        for match in [*result.problem_matches, *result.institution_matches]:
            concept = concepts.get(match.concept_id)
            if concept is None:
                raise PrimaryCBRProblemInstitutionError(
                    f"C.5 usa concepto A.6 inexistente: {match.concept_id}."
                )
            if (
                match.label != concept.label
                or match.kind is not concept.kind
                or result.source_entry_id not in concept.primary_entries
            ):
                raise PrimaryCBRProblemInstitutionError(
                    f"C.5 contradice la taxonomía A.6 en {situation_id}/{match.concept_id}."
                )
            if not set(match.evidence_fact_ids) <= known_fact_ids:
                raise PrimaryCBRProblemInstitutionError(
                    f"C.5 referencia hechos C.4 inexistentes en {situation_id}."
                )
            if not concept.requires_normative_validation or concept.can_control_legal_decision:
                raise PrimaryCBRProblemInstitutionError(
                    f"A.6 perdió su frontera orientativa en {match.concept_id}."
                )

        old_seed = normalized.similarity_seed.model_dump()
        new_seed = result.similarity_seed.model_dump()
        for field_name in (
            "taxpayer_type",
            "activity",
            "tax",
            "authority_act",
            "procedural_stage",
            "fiscal_year",
        ):
            if new_seed[field_name] != old_seed[field_name]:
                raise PrimaryCBRProblemInstitutionError(
                    f"C.5 alteró un hecho C.4 existente: {situation_id}/{field_name}."
                )
            if new_seed["evidence_fact_ids"].get(field_name, []) != old_seed[
                "evidence_fact_ids"
            ].get(field_name, []):
                raise PrimaryCBRProblemInstitutionError(
                    f"C.5 alteró la trazabilidad C.4: {situation_id}/{field_name}."
                )

        expected_unresolved = list(normalized.unresolved_required_case_fields)
        if result.primary_problem_id is not None:
            expected_unresolved = [
                field_name for field_name in expected_unresolved if field_name != "problem_type"
            ]
            primary_match = next(match for match in result.problem_matches if match.primary)
            if result.similarity_seed.evidence_fact_ids.get("problem_type", []) != (
                primary_match.evidence_fact_ids
            ):
                raise PrimaryCBRProblemInstitutionError(
                    f"C.5 problem_type perdió evidencia primaria en {situation_id}."
                )
        elif result.similarity_seed.evidence_fact_ids.get("problem_type"):
            raise PrimaryCBRProblemInstitutionError(
                f"C.5 creó evidencia problem_type sin problema exacto en {situation_id}."
            )
        if result.unresolved_required_case_fields != expected_unresolved:
            raise PrimaryCBRProblemInstitutionError(
                f"C.5 alteró indebidamente campos CBR pendientes en {situation_id}."
            )

        if result.historical_regime_context and result.corpus_validated:
            raise PrimaryCBRProblemInstitutionError(
                "C.5 no puede declarar vigente un caso histórico antes de C.7."
            )

    if classification.primary_problem_match_count != 35:
        raise PrimaryCBRProblemInstitutionError("C.5 espera 35 matches exactos de problema A.6.")
    if classification.primary_problem_no_exact_match_count != 2:
        raise PrimaryCBRProblemInstitutionError("C.5 espera 2 no-match de problema A.6.")
    if classification.primary_institution_match_count != 31:
        raise PrimaryCBRProblemInstitutionError(
            "C.5 espera 31 matches exactos de institución A.6."
        )
    if classification.primary_institution_no_exact_match_count != 6:
        raise PrimaryCBRProblemInstitutionError(
            "C.5 espera 6 no-match de institución A.6."
        )
    if classification.problem_type_seed_count != 35:
        raise PrimaryCBRProblemInstitutionError("C.5 debe resolver problem_type en 35 situaciones.")
    if classification.modifies_existing_cbr_engine or classification.creates_operational_cases:
        raise PrimaryCBRProblemInstitutionError("C.5 no debe modificar el CBR operativo.")
