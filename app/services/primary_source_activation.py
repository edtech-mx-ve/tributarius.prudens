from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.domain.primary_legal_knowledge import (
    FiscalProblemInstitutionTaxonomy,
    PrimaryKnowledgeManifest,
    PrimaryKnowledgeMap,
    PrimaryManual,
)
from app.domain.query import (
    MultidimensionalQueryAnalysis,
    PrimaryActivationEvidenceKind,
    PrimarySourceActivation,
    PrimarySourceActivationEntry,
    PrimarySourceActivationEvidence,
)
from app.services.multidimensional_query_analysis import (
    load_default_multidimensional_query_profile,
    load_default_problem_institution_taxonomy,
)
from app.services.primary_legal_knowledge import (
    load_primary_knowledge_manifest,
    load_primary_knowledge_map,
)


class PrimarySourceActivationError(RuntimeError):
    """Error controlado de activación PRODECON/UNAM D.2."""


class _ActivationWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_problem: float = Field(gt=0, le=1)
    secondary_problem: float = Field(gt=0, le=1)
    primary_institution: float = Field(gt=0, le=1)
    secondary_institution: float = Field(gt=0, le=1)
    dimension: float = Field(gt=0, le=1)


class _PrimarySourceActivationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1000)
    minimum_activation_score: float = Field(gt=0, le=1)
    weights: _ActivationWeights
    direct_dimension_entries: dict[str, list[str]]
    entry_activation_requirements: dict[str, list[str]]
    requires_normative_validation: bool = True
    full_normative_corpus_preserved: bool = True
    normative_ranking_enabled: bool = False
    rbs_activation_enabled: bool = False
    cbr_activation_enabled: bool = False
    rag_retrieval_enabled: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d2_policy_boundary(self) -> _PrimarySourceActivationPolicy:
        if not self.requires_normative_validation:
            raise ValueError("D.2 siempre requiere validación normativa posterior.")
        if not self.full_normative_corpus_preserved:
            raise ValueError("D.2 no puede reducir el corpus normativo disponible.")
        if (
            self.normative_ranking_enabled
            or self.rbs_activation_enabled
            or self.cbr_activation_enabled
            or self.rag_retrieval_enabled
        ):
            raise ValueError("D.2 no puede adelantar etapas D.3-D.7.")
        if self.can_control_legal_decision:
            raise ValueError("D.2 no puede controlar Legal Decision.")
        return self


def _default_resource_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "resources"


@lru_cache(maxsize=1)
def load_default_primary_source_activation_policy() -> _PrimarySourceActivationPolicy:
    path = _default_resource_dir() / "primary_source_activation_policy.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _PrimarySourceActivationPolicy.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PrimarySourceActivationError("La política de activación D.2 no es válida.") from exc


@lru_cache(maxsize=1)
def load_default_primary_knowledge_map() -> PrimaryKnowledgeMap:
    return load_primary_knowledge_map(_default_resource_dir() / "primary_legal_knowledge_map.json")


@lru_cache(maxsize=1)
def load_default_primary_knowledge_manifest() -> PrimaryKnowledgeManifest:
    return load_primary_knowledge_manifest(
        _default_resource_dir() / "primary_legal_knowledge_manifest.json"
    )


def _validate_activation_contract(
    policy: _PrimarySourceActivationPolicy,
    knowledge_map: PrimaryKnowledgeMap,
    taxonomy: FiscalProblemInstitutionTaxonomy,
    manifest: PrimaryKnowledgeManifest,
) -> None:
    d1_profile = load_default_multidimensional_query_profile()
    if policy.baseline_commit != d1_profile.baseline_commit:
        raise PrimarySourceActivationError("D.2 no corresponde al baseline D.1 cargado.")
    if len(knowledge_map.entries) != 19:
        raise PrimarySourceActivationError("D.2 espera 12 entradas PRODECON y 7 UNAM.")
    if len(manifest.normative_corpus_ids) != 12:
        raise PrimarySourceActivationError("D.2 espera exactamente los 12 corpus A.8.")

    entries = {item.entry_id: item for item in knowledge_map.entries}
    known_entries = set(entries)
    known_sources = set(manifest.normative_corpus_ids)
    for concept in taxonomy.concepts:
        if set(concept.primary_entries) - known_entries:
            raise PrimarySourceActivationError(
                f"A.6 referencia entradas primarias inexistentes en {concept.concept_id}."
            )
    for refs in policy.direct_dimension_entries.values():
        if set(refs) - known_entries:
            raise PrimarySourceActivationError("D.2 contiene una ruta dimensional inexistente.")
    for entry_id, requirements in policy.entry_activation_requirements.items():
        entry = entries.get(entry_id)
        if entry is None:
            raise PrimarySourceActivationError("D.2 contiene una compuerta de entrada inválida.")
        if not requirements:
            raise PrimarySourceActivationError("La compuerta D.2 requiere contexto explícito.")
    for entry in entries.values():
        if entry.historical_content and entry.entry_id not in policy.entry_activation_requirements:
            raise PrimarySourceActivationError(
                "Toda entrada histórica D.2 debe tener una compuerta explícita."
            )
    for entry in knowledge_map.entries:
        if set(entry.candidate_normative_sources) - known_sources:
            raise PrimarySourceActivationError(
                f"{entry.entry_id} apunta fuera de los doce corpus A.8."
            )
        if not entry.requires_normative_validation or entry.can_control_legal_decision:
            raise PrimarySourceActivationError(
                f"{entry.entry_id} perdió su frontera orientativa A.1-A.8."
            )


def _dimension_keys(multidimensional: MultidimensionalQueryAnalysis) -> set[str]:
    return {
        f"{item.dimension.value}:{item.value}"
        for item in multidimensional.dimensions
    }


def _add_evidence(
    evidence_by_entry: dict[str, list[PrimarySourceActivationEvidence]],
    score_by_entry: dict[str, float],
    *,
    entry_id: str,
    kind: PrimaryActivationEvidenceKind,
    ref: str,
    contribution: float,
    detail: str,
) -> None:
    evidence_by_entry[entry_id].append(
        PrimarySourceActivationEvidence(
            kind=kind,
            ref=ref,
            contribution=contribution,
            detail=detail,
        )
    )
    score_by_entry[entry_id] = min(1.0, score_by_entry[entry_id] + contribution)


def _activate_taxonomy_matches(
    multidimensional: MultidimensionalQueryAnalysis,
    policy: _PrimarySourceActivationPolicy,
    taxonomy: FiscalProblemInstitutionTaxonomy,
    evidence_by_entry: dict[str, list[PrimarySourceActivationEvidence]],
    score_by_entry: dict[str, float],
) -> None:
    concepts = {item.concept_id: item for item in taxonomy.concepts}
    for match in multidimensional.problem_matches:
        concept = concepts[match.concept_id]
        weight = (
            policy.weights.primary_problem
            if match.primary
            else policy.weights.secondary_problem
        )
        contribution = round(match.score * weight, 6)
        for entry_id in concept.primary_entries:
            _add_evidence(
                evidence_by_entry,
                score_by_entry,
                entry_id=entry_id,
                kind=PrimaryActivationEvidenceKind.PROBLEM,
                ref=match.concept_id,
                contribution=contribution,
                detail=f"A.6 problema; primary={str(match.primary).lower()}.",
            )

    for match in multidimensional.institution_matches:
        concept = concepts[match.concept_id]
        weight = (
            policy.weights.primary_institution
            if match.primary
            else policy.weights.secondary_institution
        )
        contribution = round(match.score * weight, 6)
        for entry_id in concept.primary_entries:
            _add_evidence(
                evidence_by_entry,
                score_by_entry,
                entry_id=entry_id,
                kind=PrimaryActivationEvidenceKind.INSTITUTION,
                ref=match.concept_id,
                contribution=contribution,
                detail=f"A.6 institución; primary={str(match.primary).lower()}.",
            )


def _activate_dimensions(
    multidimensional: MultidimensionalQueryAnalysis,
    policy: _PrimarySourceActivationPolicy,
    evidence_by_entry: dict[str, list[PrimarySourceActivationEvidence]],
    score_by_entry: dict[str, float],
) -> None:
    for dimension in multidimensional.dimensions:
        key = f"{dimension.dimension.value}:{dimension.value}"
        contribution = round(dimension.confidence * policy.weights.dimension, 6)
        for entry_id in policy.direct_dimension_entries.get(key, []):
            _add_evidence(
                evidence_by_entry,
                score_by_entry,
                entry_id=entry_id,
                kind=PrimaryActivationEvidenceKind.DIMENSION,
                ref=key,
                contribution=contribution,
                detail=f"Dimensión D.1 explícita: {key}.",
            )


def activate_primary_sources(
    multidimensional: MultidimensionalQueryAnalysis,
    *,
    policy: _PrimarySourceActivationPolicy | None = None,
    knowledge_map: PrimaryKnowledgeMap | None = None,
    taxonomy: FiscalProblemInstitutionTaxonomy | None = None,
    manifest: PrimaryKnowledgeManifest | None = None,
) -> PrimarySourceActivation:
    """Activa PRODECON/UNAM para navegación sin crear fundamento jurídico."""
    resolved_policy = policy or load_default_primary_source_activation_policy()
    resolved_map = knowledge_map or load_default_primary_knowledge_map()
    resolved_taxonomy = taxonomy or load_default_problem_institution_taxonomy()
    resolved_manifest = manifest or load_default_primary_knowledge_manifest()
    _validate_activation_contract(
        resolved_policy,
        resolved_map,
        resolved_taxonomy,
        resolved_manifest,
    )

    evidence_by_entry: dict[str, list[PrimarySourceActivationEvidence]] = defaultdict(list)
    score_by_entry: dict[str, float] = defaultdict(float)
    _activate_taxonomy_matches(
        multidimensional,
        resolved_policy,
        resolved_taxonomy,
        evidence_by_entry,
        score_by_entry,
    )
    _activate_dimensions(
        multidimensional,
        resolved_policy,
        evidence_by_entry,
        score_by_entry,
    )

    context_keys = _dimension_keys(multidimensional)
    entries_by_id = {item.entry_id: item for item in resolved_map.entries}
    suppressed: list[str] = []
    suppressed_historical: list[str] = []
    activated: list[PrimarySourceActivationEntry] = []

    for entry_id, score in score_by_entry.items():
        if score < resolved_policy.minimum_activation_score:
            continue
        entry = entries_by_id[entry_id]
        requirements = resolved_policy.entry_activation_requirements.get(entry_id, [])
        if requirements and not set(requirements) <= context_keys:
            suppressed.append(entry_id)
            if entry.historical_content:
                suppressed_historical.append(entry_id)
            continue
        activated.append(
            PrimarySourceActivationEntry(
                entry_id=entry.entry_id,
                manual=entry.manual,
                order=entry.order,
                title=entry.title,
                score=round(score, 6),
                evidence=evidence_by_entry[entry_id],
                candidate_normative_sources=list(entry.candidate_normative_sources),
                historical_content=entry.historical_content,
                requires_temporal_validation=entry.requires_temporal_validation,
                requires_normative_validation=entry.requires_normative_validation,
                can_control_legal_decision=False,
            )
        )

    manual_order = {PrimaryManual.PRODECON: 0, PrimaryManual.UNAM: 1}
    activated.sort(key=lambda item: (-item.score, manual_order[item.manual], item.order))
    suppressed.sort()
    suppressed_historical.sort()

    hinted_sources = {
        source
        for entry in activated
        for source in entry.candidate_normative_sources
    }
    canonical_hints = [
        source
        for source in resolved_manifest.normative_corpus_ids
        if source in hinted_sources
    ]
    requires_temporal = multidimensional.requires_temporal_validation or any(
        entry.historical_content for entry in activated
    )

    return PrimarySourceActivation(
        schema_version=resolved_policy.schema_version,
        activation_applied=bool(activated),
        entries=activated,
        prodecon_count=sum(item.manual is PrimaryManual.PRODECON for item in activated),
        unam_count=sum(item.manual is PrimaryManual.UNAM for item in activated),
        suppressed_entry_ids=suppressed,
        suppressed_historical_entry_ids=suppressed_historical,
        candidate_normative_hints=canonical_hints,
        normative_corpus_ids=list(resolved_manifest.normative_corpus_ids),
        full_normative_corpus_preserved=True,
        requires_temporal_validation=requires_temporal,
        requires_normative_validation=True,
        normative_ranking_enabled=False,
        rbs_activation_enabled=False,
        cbr_activation_enabled=False,
        rag_retrieval_enabled=False,
        can_control_legal_decision=False,
    )
