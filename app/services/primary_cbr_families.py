from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.primary_cbr_corpus_validation import PrimaryCBRCorpusValidationReport
from app.domain.primary_cbr_families import PrimaryCBRFamilyRegistry
from app.domain.primary_cbr_inventory import CurrentCBRInventory
from app.domain.primary_cbr_problem_institution import (
    PrimaryCBRProblemInstitutionClassification,
)
from app.domain.primary_legal_knowledge import (
    FiscalProblemInstitution,
    FiscalProblemInstitutionTaxonomy,
)


class PrimaryCBRFamilyRegistryError(RuntimeError):
    """Error controlado de creación/asignación de familias CBR C.8."""


PRIMARY_FAMILY_BY_CONCEPT: dict[str, str] = {
    "determinacion_contribucion": "CBR-CALCULO",
    "cumplimiento_fiscal": "CBR-OBLIGACION",
    "actuacion_autoridad": "CBR-AUTORIDAD",
    "incumplimiento_fiscal": "CBR-INCUMPLIMIENTO",
    "defensa_contribuyente": "CBR-DEFENSA",
    "interpretacion_fiscal": "CBR-INTERPRETACION",
    "relacion_tributaria": "CBR-SUJETO",
    "tributo": "CBR-TRIBUTO",
    "obligacion_tributaria": "CBR-OBLIGACION",
    "derechos_contribuyente": "CBR-DERECHOS",
    "deuda_tributaria": "CBR-DEUDA",
    "regimen_isr": "CBR-CALCULO",
}


def load_primary_cbr_family_registry(path: Path) -> PrimaryCBRFamilyRegistry:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryCBRFamilyRegistryError(f"No existe el registro CBR C.8: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return PrimaryCBRFamilyRegistry.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PrimaryCBRFamilyRegistryError(
            "El registro de familias CBR C.8 no es válido."
        ) from exc


def _ordered_family_union(
    concept_ids: list[str],
    taxonomy_by_id: dict[str, FiscalProblemInstitution],
    *,
    primary_family_id: str,
    historical_regime_context: bool,
) -> list[str]:
    families: list[str] = []
    for concept_id in concept_ids:
        concept = taxonomy_by_id[concept_id]
        for family_id in concept.cbr_families:
            if family_id not in families:
                families.append(family_id)
    if historical_regime_context and "CBR-TEMPORALIDAD" not in families:
        families.append("CBR-TEMPORALIDAD")
    if primary_family_id not in families:
        raise PrimaryCBRFamilyRegistryError(
            f"La familia primaria {primary_family_id} no está respaldada por A.6."
        )
    families.remove(primary_family_id)
    families.insert(0, primary_family_id)
    return families


def validate_primary_cbr_family_registry(
    registry: PrimaryCBRFamilyRegistry,
    inventory: CurrentCBRInventory,
    taxonomy: FiscalProblemInstitutionTaxonomy,
    classification: PrimaryCBRProblemInstitutionClassification,
    corpus_validation: PrimaryCBRCorpusValidationReport,
) -> None:
    """Contrasta C.8 con C.1, A.6, C.5 y C.7 sin activar similitud ni casos operativos."""
    baselines = {
        inventory.baseline_commit,
        classification.baseline_commit,
        corpus_validation.baseline_commit,
        registry.baseline_commit,
    }
    if len(baselines) != 1:
        raise PrimaryCBRFamilyRegistryError("C.8 debe conservar el baseline C.1/C.5/C.7.")

    inventory_family_ids = inventory.primary_knowledge_cbr_families
    registry_family_ids = [item.family_id for item in registry.families]
    if registry_family_ids != inventory_family_ids:
        raise PrimaryCBRFamilyRegistryError(
            "C.8 debe formalizar exactamente las 12 familias inventariadas en C.1."
        )

    taxonomy_by_id = {concept.concept_id: concept for concept in taxonomy.concepts}
    for family in registry.families:
        expected_source_concepts = [
            concept.concept_id
            for concept in taxonomy.concepts
            if family.family_id in concept.cbr_families
        ]
        if family.source_concept_ids != expected_source_concepts:
            raise PrimaryCBRFamilyRegistryError(
                f"{family.family_id} no refleja exactamente sus vínculos A.6."
            )
        expected_anchors = [
            concept_id
            for concept_id, family_id in PRIMARY_FAMILY_BY_CONCEPT.items()
            if family_id == family.family_id and concept_id in taxonomy_by_id
        ]
        if family.primary_anchor_concept_ids != expected_anchors:
            raise PrimaryCBRFamilyRegistryError(
                f"{family.family_id} altera los conceptos ancla de partición C.8."
            )

    c5_by_id = {item.situation_id: item for item in classification.classifications}
    c7_by_id = {item.situation_id: item for item in corpus_validation.situations}
    c8_by_id = {item.situation_id: item for item in registry.assignments}
    if set(c8_by_id) != set(c5_by_id) or set(c8_by_id) != set(c7_by_id):
        raise PrimaryCBRFamilyRegistryError(
            "C.8 debe asignar exactamente las 37 situaciones C.5/C.7."
        )

    family_set = set(registry_family_ids)
    for situation_id, assignment in c8_by_id.items():
        c5 = c5_by_id[situation_id]
        c7 = c7_by_id[situation_id]
        if (
            assignment.source != c5.source
            or assignment.source_entry_id != c5.source_entry_id
            or assignment.historical_regime_context != c5.historical_regime_context
        ):
            raise PrimaryCBRFamilyRegistryError(
                f"C.8 perdió identidad fuente en {situation_id}."
            )
        if (
            assignment.corpus_validation_outcome != c7.validation_outcome
            or assignment.corpus_validated != c7.corpus_validated
            or assignment.temporal_validation_pending != c7.temporal_validation_pending
        ):
            raise PrimaryCBRFamilyRegistryError(
                f"C.8 alteró el estado de validación C.7 en {situation_id}."
            )
        if assignment.primary_problem_id != c5.primary_problem_id:
            raise PrimaryCBRFamilyRegistryError(
                f"C.8 alteró el problema primario C.5 en {situation_id}."
            )
        if assignment.primary_institution_id != c5.primary_institution_id:
            raise PrimaryCBRFamilyRegistryError(
                f"C.8 alteró la institución primaria C.5 en {situation_id}."
            )

        basis_concepts = [
            match.concept_id for match in [*c5.problem_matches, *c5.institution_matches]
        ]
        if assignment.family_basis_concept_ids != basis_concepts:
            raise PrimaryCBRFamilyRegistryError(
                f"C.8 no conserva todos los conceptos exactos C.5 en {situation_id}."
            )

        anchor_concept = c5.primary_problem_id or c5.primary_institution_id
        if anchor_concept is None:
            raise PrimaryCBRFamilyRegistryError(
                f"{situation_id} carece de concepto primario para crear familia CBR."
            )
        expected_primary = PRIMARY_FAMILY_BY_CONCEPT.get(anchor_concept)
        if expected_primary is None:
            raise PrimaryCBRFamilyRegistryError(
                f"No existe familia primaria C.8 para {anchor_concept}."
            )
        if assignment.primary_family_id != expected_primary:
            raise PrimaryCBRFamilyRegistryError(
                f"{situation_id} no usa la familia principal esperada."
            )

        expected_families = _ordered_family_union(
            basis_concepts,
            taxonomy_by_id,
            primary_family_id=expected_primary,
            historical_regime_context=assignment.historical_regime_context,
        )
        if assignment.family_ids != expected_families:
            raise PrimaryCBRFamilyRegistryError(
                f"{situation_id} no conserva las facetas CBR derivadas de A.6."
            )
        if not set(assignment.family_ids) <= family_set:
            raise PrimaryCBRFamilyRegistryError(
                f"{situation_id} usa una familia fuera del inventario C.1."
            )

    actual_primary_counts = {family_id: 0 for family_id in registry_family_ids}
    actual_membership_counts = {family_id: 0 for family_id in registry_family_ids}
    for assignment in registry.assignments:
        actual_primary_counts[assignment.primary_family_id] += 1
        for family_id in assignment.family_ids:
            actual_membership_counts[family_id] += 1
    if registry.primary_family_counts != actual_primary_counts:
        raise PrimaryCBRFamilyRegistryError("Los conteos primarios C.8 no son reproducibles.")
    if registry.family_membership_counts != actual_membership_counts:
        raise PrimaryCBRFamilyRegistryError("Los conteos de pertenencia C.8 no son reproducibles.")
    if any(count == 0 for count in actual_membership_counts.values()):
        raise PrimaryCBRFamilyRegistryError(
            "Las 12 familias C.1/A.6 deben quedar representadas en C.8."
        )
