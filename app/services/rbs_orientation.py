from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.domain.primary_legal_knowledge import FiscalProblemInstitutionTaxonomy
from app.domain.primary_rbs_corpus_validation import PrimaryRBSCorpusValidationReport
from app.domain.primary_rbs_decision_boundary import PrimaryRBSDecisionBoundaryMap
from app.domain.primary_rbs_deduplication import PrimaryRBSDeduplicationMap
from app.domain.primary_rbs_existing_integration import ExistingRBSRuleIntegrationMap
from app.domain.query import (
    MultidimensionalQueryAnalysis,
    PrimarySourceActivation,
    RBSOrientationEvidence,
    RBSOrientationEvidenceKind,
    RBSOrientationIntegration,
    RBSOrientationRelation,
)
from app.services.multidimensional_query_analysis import (
    load_default_multidimensional_query_profile,
    load_default_problem_institution_taxonomy,
)
from app.services.primary_rbs_corpus_validation import (
    load_primary_rbs_corpus_validation_report,
)
from app.services.primary_rbs_decision_boundary import (
    load_primary_rbs_decision_boundary_map,
)
from app.services.primary_rbs_deduplication import load_primary_rbs_deduplication_map
from app.services.primary_rbs_existing_integration import (
    load_existing_rbs_rule_integration_map,
)
from app.services.primary_source_activation import (
    load_default_primary_knowledge_manifest,
    load_default_primary_source_activation_policy,
)


class RBSOrientationError(RuntimeError):
    """Error controlado de integración RBS orientadora D.3."""


class _RBSOrientationWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_entry_coverage: float = Field(gt=0, le=1)
    rbs_family_overlap: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def validate_total_weight(self) -> _RBSOrientationWeights:
        if abs(self.primary_entry_coverage + self.rbs_family_overlap - 1.0) > 1e-9:
            raise ValueError("Los pesos D.3 deben sumar 1.0.")
        return self


class _RBSOrientationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1200)
    minimum_orientation_score: float = Field(gt=0, le=1)
    weights: _RBSOrientationWeights
    requires_primary_entry_overlap: bool = True
    expected_primary_relation_count: int = Field(ge=1)
    expected_existing_rule_count: int = Field(ge=1)
    requires_normative_validation: bool = True
    requires_case_date_validation: bool = True
    full_normative_corpus_preserved: bool = True
    reuse_existing_rule_engine: bool = True
    production_rule_execution_enabled: bool = False
    normative_ranking_enabled: bool = False
    cbr_activation_enabled: bool = False
    rag_retrieval_enabled: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d3_boundary(self) -> _RBSOrientationPolicy:
        if not self.requires_primary_entry_overlap:
            raise ValueError("D.3 debe partir de una entrada primaria activada por D.2.")
        if not self.requires_normative_validation or not self.requires_case_date_validation:
            raise ValueError("D.3 debe conservar validación normativa y temporal posterior.")
        if not self.full_normative_corpus_preserved:
            raise ValueError("D.3 no puede reducir el corpus normativo disponible.")
        if not self.reuse_existing_rule_engine:
            raise ValueError("D.3 debe reutilizar el RBS existente.")
        if (
            self.production_rule_execution_enabled
            or self.normative_ranking_enabled
            or self.cbr_activation_enabled
            or self.rag_retrieval_enabled
        ):
            raise ValueError("D.3 no puede adelantar ejecución, D.4, D.5 ni D.7.")
        if self.can_control_legal_decision:
            raise ValueError("D.3 no puede controlar Legal Decision.")
        return self


def _default_resource_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "resources"


@lru_cache(maxsize=1)
def load_default_rbs_orientation_policy() -> _RBSOrientationPolicy:
    path = _default_resource_dir() / "rbs_orientation_policy.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _RBSOrientationPolicy.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise RBSOrientationError("La política RBS orientadora D.3 no es válida.") from exc


@lru_cache(maxsize=1)
def load_default_primary_rbs_deduplication() -> PrimaryRBSDeduplicationMap:
    return load_primary_rbs_deduplication_map(
        _default_resource_dir() / "primary_rbs_deduplication_map.json"
    )


@lru_cache(maxsize=1)
def load_default_primary_rbs_boundary() -> PrimaryRBSDecisionBoundaryMap:
    return load_primary_rbs_decision_boundary_map(
        _default_resource_dir() / "primary_rbs_decision_boundary.json"
    )


@lru_cache(maxsize=1)
def load_default_primary_rbs_corpus_validation() -> PrimaryRBSCorpusValidationReport:
    return load_primary_rbs_corpus_validation_report(
        _default_resource_dir() / "primary_rbs_corpus_validation.json"
    )


@lru_cache(maxsize=1)
def load_default_existing_rbs_integration() -> ExistingRBSRuleIntegrationMap:
    return load_existing_rbs_rule_integration_map(
        _default_resource_dir() / "primary_rbs_existing_integration.json"
    )


def _validate_d3_contract(
    policy: _RBSOrientationPolicy,
    taxonomy: FiscalProblemInstitutionTaxonomy,
    deduplication: PrimaryRBSDeduplicationMap,
    boundary_map: PrimaryRBSDecisionBoundaryMap,
    corpus_validation: PrimaryRBSCorpusValidationReport,
    existing_integration: ExistingRBSRuleIntegrationMap,
    activation: PrimarySourceActivation,
) -> None:
    d1_profile = load_default_multidimensional_query_profile()
    d2_policy = load_default_primary_source_activation_policy()
    manifest = load_default_primary_knowledge_manifest()
    if policy.baseline_commit != d1_profile.baseline_commit:
        raise RBSOrientationError("D.3 no corresponde al baseline D.1 cargado.")
    if policy.baseline_commit != d2_policy.baseline_commit:
        raise RBSOrientationError("D.3 no corresponde al baseline D.2 cargado.")
    if deduplication.deduplicated_relation_count != policy.expected_primary_relation_count:
        raise RBSOrientationError("D.3 espera exactamente 18 relaciones RBS B.5.")
    if existing_integration.total_rules != policy.expected_existing_rule_count:
        raise RBSOrientationError("D.3 espera exactamente las 14 reglas productivas B.9.")

    relation_ids = {item.canonical_id for item in deduplication.relations}
    boundary_ids = {item.relation_id for item in boundary_map.boundaries}
    validation_ids = {item.relation_id for item in corpus_validation.relation_validations}
    if relation_ids != boundary_ids or relation_ids != validation_ids:
        raise RBSOrientationError("D.3 requiere cobertura exacta B.5/B.7/B.8.")

    linked_relation_ids = {
        relation_id
        for item in existing_integration.integrations
        for relation_id in item.primary_relation_ids
    }
    if linked_relation_ids - relation_ids:
        raise RBSOrientationError("B.9 enlaza una relación inexistente para D.3.")
    if len(taxonomy.concepts) != 12:
        raise RBSOrientationError("D.3 debe consumir exactamente los 12 conceptos A.6.")
    if activation.normative_corpus_ids != manifest.normative_corpus_ids:
        raise RBSOrientationError("D.3 debe preservar los 12 corpus recibidos desde D.2.")
    if corpus_validation.normative_corpus_ids != manifest.normative_corpus_ids:
        raise RBSOrientationError("B.8 y A.8 difieren en el corpus normativo de D.3.")
    if not activation.full_normative_corpus_preserved:
        raise RBSOrientationError("D.2 redujo indebidamente el espacio normativo antes de D.3.")


def _query_rbs_families(
    multidimensional: MultidimensionalQueryAnalysis,
    taxonomy: FiscalProblemInstitutionTaxonomy,
) -> set[str]:
    concepts = {item.concept_id: item for item in taxonomy.concepts}
    families: set[str] = set()
    for match in [*multidimensional.problem_matches, *multidimensional.institution_matches]:
        concept = concepts.get(match.concept_id)
        if concept is None:
            raise RBSOrientationError(
                f"D.3 recibió un concepto A.6 desconocido: {match.concept_id}."
            )
        families.update(concept.rbs_families)
    return families


def _existing_rules_by_relation(
    integration: ExistingRBSRuleIntegrationMap,
) -> dict[str, list[str]]:
    output: dict[str, list[str]] = defaultdict(list)
    for item in integration.integrations:
        for relation_id in item.primary_relation_ids:
            output[relation_id].append(item.rule_id)
    for values in output.values():
        values.sort()
    return dict(output)


def integrate_rbs_orientation(
    multidimensional: MultidimensionalQueryAnalysis,
    primary_activation: PrimarySourceActivation,
    *,
    policy: _RBSOrientationPolicy | None = None,
    taxonomy: FiscalProblemInstitutionTaxonomy | None = None,
    deduplication: PrimaryRBSDeduplicationMap | None = None,
    boundary_map: PrimaryRBSDecisionBoundaryMap | None = None,
    corpus_validation: PrimaryRBSCorpusValidationReport | None = None,
    existing_integration: ExistingRBSRuleIntegrationMap | None = None,
) -> RBSOrientationIntegration:
    """Integra D.1-D.2 con B.5-B.9 exclusivamente para orientación RBS."""
    resolved_policy = policy or load_default_rbs_orientation_policy()
    resolved_taxonomy = taxonomy or load_default_problem_institution_taxonomy()
    resolved_deduplication = deduplication or load_default_primary_rbs_deduplication()
    resolved_boundary = boundary_map or load_default_primary_rbs_boundary()
    resolved_corpus = corpus_validation or load_default_primary_rbs_corpus_validation()
    resolved_existing = existing_integration or load_default_existing_rbs_integration()

    _validate_d3_contract(
        resolved_policy,
        resolved_taxonomy,
        resolved_deduplication,
        resolved_boundary,
        resolved_corpus,
        resolved_existing,
        primary_activation,
    )

    active_entry_scores = {
        item.entry_id: item.score for item in primary_activation.entries
    }
    query_families = _query_rbs_families(multidimensional, resolved_taxonomy)
    boundary_by_relation = {
        item.relation_id: item for item in resolved_boundary.boundaries
    }
    validation_by_relation = {
        item.relation_id: item for item in resolved_corpus.relation_validations
    }
    rules_by_relation = _existing_rules_by_relation(resolved_existing)

    oriented: list[RBSOrientationRelation] = []
    for relation in resolved_deduplication.relations:
        matched_entries = [
            entry_id
            for entry_id in relation.primary_entry_ids
            if entry_id in active_entry_scores
        ]
        if resolved_policy.requires_primary_entry_overlap and not matched_entries:
            continue

        entry_component = sum(
            active_entry_scores.get(entry_id, 0.0)
            for entry_id in relation.primary_entry_ids
        ) / len(relation.primary_entry_ids)
        relation_families = set(relation.rbs_families)
        matched_families = sorted(relation_families & query_families)
        family_component = (
            len(matched_families) / len(relation_families)
            if relation_families and query_families
            else 0.0
        )
        score = round(
            resolved_policy.weights.primary_entry_coverage * entry_component
            + resolved_policy.weights.rbs_family_overlap * family_component,
            6,
        )
        if score < resolved_policy.minimum_orientation_score:
            continue

        evidence = [
            RBSOrientationEvidence(
                kind=RBSOrientationEvidenceKind.PRIMARY_ENTRY,
                ref=entry_id,
                contribution=active_entry_scores[entry_id],
                detail="Entrada primaria activada por D.2.",
            )
            for entry_id in matched_entries
        ]
        evidence.extend(
            RBSOrientationEvidence(
                kind=RBSOrientationEvidenceKind.RBS_FAMILY,
                ref=family_id,
                contribution=1.0,
                detail="Familia RBS sustentada por problema/institución A.6 detectado en D.1.",
            )
            for family_id in matched_families
        )

        boundary = boundary_by_relation[relation.canonical_id]
        validation = validation_by_relation[relation.canonical_id]
        oriented.append(
            RBSOrientationRelation(
                relation_id=relation.canonical_id,
                label=relation.label,
                score=score,
                primary_entry_component=round(entry_component, 6),
                family_overlap_component=round(family_component, 6),
                matched_primary_entry_ids=matched_entries,
                rbs_family_ids=list(relation.rbs_families),
                matched_rbs_family_ids=matched_families,
                evidence=evidence,
                role=boundary.role,
                normative_source_ids=list(boundary.normative_source_ids),
                exact_normative_refs=list(boundary.exact_normative_refs),
                linked_existing_rule_ids=rules_by_relation.get(relation.canonical_id, []),
                corpus_validation_status=validation.status,
                blocked_normative_sources=list(validation.blocked_normative_sources),
                corpus_membership_validated=validation.corpus_membership_validated,
                temporal_applicability_confirmed=False,
                requires_case_date_validation=validation.requires_case_date_validation,
                executable_determination_enabled=False,
                determination_ready=False,
                orientation_only=True,
                can_control_legal_decision=False,
            )
        )

    oriented.sort(key=lambda item: (-item.score, item.relation_id))
    activated_families = sorted(
        {family for item in oriented for family in item.rbs_family_ids}
    )
    linked_rules = sorted(
        {rule_id for item in oriented for rule_id in item.linked_existing_rule_ids}
    )
    candidate_sources_set = {
        source for item in oriented for source in item.normative_source_ids
    }
    candidate_sources = [
        source
        for source in primary_activation.normative_corpus_ids
        if source in candidate_sources_set
    ]

    return RBSOrientationIntegration(
        schema_version=resolved_policy.schema_version,
        activation_applied=bool(oriented),
        relations=oriented,
        activated_relation_count=len(oriented),
        activated_rbs_family_ids=activated_families,
        linked_existing_rule_ids=linked_rules,
        available_primary_relation_count=resolved_deduplication.deduplicated_relation_count,
        available_existing_rule_count=resolved_existing.total_rules,
        candidate_normative_sources=candidate_sources,
        normative_corpus_ids=list(primary_activation.normative_corpus_ids),
        full_normative_corpus_preserved=True,
        requires_normative_validation=True,
        requires_temporal_validation=bool(oriented),
        reuse_existing_rule_engine=True,
        production_rule_execution_enabled=False,
        normative_ranking_enabled=False,
        cbr_activation_enabled=False,
        rag_retrieval_enabled=False,
        can_control_legal_decision=False,
    )
