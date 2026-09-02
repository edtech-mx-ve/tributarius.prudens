from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.primary_legal_knowledge import (
    FiscalProblemInstitutionTaxonomy,
    LegalRelationTaxonomy,
    PrimaryKnowledgeComponent,
    PrimaryKnowledgeManifest,
    PrimaryKnowledgeMap,
    PrimaryLegalKnowledgeResource,
    PrimaryLegalTaxonomy,
)


class PrimaryLegalKnowledgeError(RuntimeError):
    """Error controlado al cargar la guía primaria PRODECON + UNAM."""


def load_primary_knowledge_map(path: Path) -> PrimaryKnowledgeMap:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryLegalKnowledgeError(f"No existe la guía primaria: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return PrimaryKnowledgeMap.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PrimaryLegalKnowledgeError(
            "La guía primaria PRODECON + UNAM no es válida."
        ) from exc


def load_primary_legal_taxonomy(path: Path) -> PrimaryLegalTaxonomy:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryLegalKnowledgeError(f"No existe la taxonomía primaria: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return PrimaryLegalTaxonomy.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PrimaryLegalKnowledgeError(
            "La taxonomía jurídica primaria PRODECON + UNAM no es válida."
        ) from exc


def validate_primary_taxonomy_links(
    knowledge_map: PrimaryKnowledgeMap,
    taxonomy: PrimaryLegalTaxonomy,
) -> None:
    """Garantiza que taxonomía, RBS y CBR solo apunten a conocimiento registrado."""
    entry_ids = {entry.entry_id for entry in knowledge_map.entries}
    map_rbs = {family for entry in knowledge_map.entries for family in entry.rbs_families}
    map_cbr = {family for entry in knowledge_map.entries for family in entry.cbr_families}
    map_sources = {
        source
        for entry in knowledge_map.entries
        for source in entry.candidate_normative_sources
    }

    for concept in taxonomy.concepts:
        unknown_entries = set(concept.primary_entries) - entry_ids
        unknown_rbs = set(concept.rbs_families) - map_rbs
        unknown_cbr = set(concept.cbr_families) - map_cbr
        unknown_sources = set(concept.candidate_normative_sources) - map_sources
        if unknown_entries or unknown_rbs or unknown_cbr or unknown_sources:
            raise PrimaryLegalKnowledgeError(
                f"Taxonomía primaria inconsistente en {concept.concept_id}."
            )


def load_fiscal_problem_institution_taxonomy(path: Path) -> FiscalProblemInstitutionTaxonomy:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryLegalKnowledgeError(f"No existe la taxonomía A.6: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return FiscalProblemInstitutionTaxonomy.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PrimaryLegalKnowledgeError("La taxonomía A.6 no es válida.") from exc


def load_legal_relation_taxonomy(path: Path) -> LegalRelationTaxonomy:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryLegalKnowledgeError(f"No existe la taxonomía A.7: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return LegalRelationTaxonomy.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PrimaryLegalKnowledgeError("La taxonomía A.7 no es válida.") from exc


def validate_a6_a7_links(
    knowledge_map: PrimaryKnowledgeMap,
    problems: FiscalProblemInstitutionTaxonomy,
    relations: LegalRelationTaxonomy,
) -> None:
    entry_ids = {entry.entry_id for entry in knowledge_map.entries}
    rbs = {family for entry in knowledge_map.entries for family in entry.rbs_families}
    cbr = {family for entry in knowledge_map.entries for family in entry.cbr_families}
    sources = {
        source
        for entry in knowledge_map.entries
        for source in entry.candidate_normative_sources
    }
    concepts = {concept.concept_id: concept for concept in problems.concepts}
    relation_ids = {relation.relation_id for relation in relations.relations}

    for concept in problems.concepts:
        if (
            set(concept.primary_entries) - entry_ids
            or set(concept.rbs_families) - rbs
            or set(concept.cbr_families) - cbr
            or set(concept.candidate_normative_sources) - sources
            or set(concept.relation_ids) - relation_ids
        ):
            raise PrimaryLegalKnowledgeError(f"A.6 inconsistente en {concept.concept_id}.")

    problem_ids = {key for key, value in concepts.items() if value.kind.value == "problem"}
    institution_ids = {key for key, value in concepts.items() if value.kind.value == "institution"}
    for relation in relations.relations:
        if (
            set(relation.primary_entries) - entry_ids
            or set(relation.rbs_families) - rbs
            or set(relation.cbr_families) - cbr
            or set(relation.candidate_normative_sources) - sources
            or set(relation.problem_concepts) - problem_ids
            or set(relation.institution_concepts) - institution_ids
        ):
            raise PrimaryLegalKnowledgeError(f"A.7 inconsistente en {relation.relation_id}.")


def load_primary_knowledge_manifest(path: Path) -> PrimaryKnowledgeManifest:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryLegalKnowledgeError(f"No existe el manifiesto A.8: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return PrimaryKnowledgeManifest.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PrimaryLegalKnowledgeError("El manifiesto A.8 no es válido.") from exc


def _canonical_payload_sha256(payload: dict[str, object]) -> str:
    import hashlib

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_primary_legal_knowledge_resource(
    resource_dir: Path,
    manifest_path: Path,
) -> PrimaryLegalKnowledgeResource:
    manifest = load_primary_knowledge_manifest(manifest_path)
    base = resource_dir.expanduser().resolve()
    components = manifest.components

    knowledge_map = load_primary_knowledge_map(
        base / components[PrimaryKnowledgeComponent.KNOWLEDGE_MAP]
    )
    legal_taxonomy = load_primary_legal_taxonomy(
        base / components[PrimaryKnowledgeComponent.LEGAL_TAXONOMY]
    )
    problems = load_fiscal_problem_institution_taxonomy(
        base / components[PrimaryKnowledgeComponent.PROBLEM_INSTITUTION_TAXONOMY]
    )
    relations = load_legal_relation_taxonomy(
        base / components[PrimaryKnowledgeComponent.RELATION_TAXONOMY]
    )

    validate_primary_taxonomy_links(knowledge_map, legal_taxonomy)
    validate_a6_a7_links(knowledge_map, problems, relations)

    map_sources = {
        source
        for entry in knowledge_map.entries
        for source in entry.candidate_normative_sources
    }
    manifest_sources = set(manifest.normative_corpus_ids)
    if map_sources != manifest_sources:
        raise PrimaryLegalKnowledgeError(
            "A.8 exige correspondencia exacta entre la matriz y los doce corpus normativos."
        )

    rbs_families = tuple(
        sorted({family for entry in knowledge_map.entries for family in entry.rbs_families})
    )
    cbr_families = tuple(
        sorted({family for entry in knowledge_map.entries for family in entry.cbr_families})
    )
    canonical_payload: dict[str, object] = {
        "schema_version": manifest.schema_version,
        "knowledge_version": manifest.knowledge_version,
        "effective_date": manifest.effective_date,
        "knowledge_map": knowledge_map.model_dump(mode="json"),
        "legal_taxonomy": legal_taxonomy.model_dump(mode="json"),
        "problem_institution_taxonomy": problems.model_dump(mode="json"),
        "relation_taxonomy": relations.model_dump(mode="json"),
        "normative_corpus_ids": sorted(manifest.normative_corpus_ids),
        "rbs_families": list(rbs_families),
        "cbr_families": list(cbr_families),
    }
    digest = _canonical_payload_sha256(canonical_payload)

    return PrimaryLegalKnowledgeResource(
        schema_version=manifest.schema_version,
        knowledge_version=manifest.knowledge_version,
        effective_date=manifest.effective_date,
        knowledge_map=knowledge_map,
        legal_taxonomy=legal_taxonomy,
        problem_institution_taxonomy=problems,
        relation_taxonomy=relations,
        normative_corpus_ids=tuple(sorted(manifest.normative_corpus_ids)),
        rbs_families=rbs_families,
        cbr_families=cbr_families,
        canonical_sha256=digest,
        requires_normative_validation=manifest.requires_normative_validation,
        can_control_legal_decision=manifest.can_control_legal_decision,
    )
