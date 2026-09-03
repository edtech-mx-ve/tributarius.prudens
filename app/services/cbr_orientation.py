from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.domain.cbr import CaseField, FieldSimilarity
from app.domain.primary_cbr_legal_similarity import (
    PrimaryCBRLegalSimilarityIndex,
    PrimaryCBRLegalSimilarityProfile,
)
from app.domain.primary_cbr_levels import PrimaryCBRLevelRegistry
from app.domain.primary_legal_knowledge import FiscalProblemInstitutionTaxonomy
from app.domain.query import (
    CBROrientationIntegration,
    CBROrientationMatch,
    MultidimensionalQueryAnalysis,
    PrimarySourceActivation,
    QueryDimensionName,
    QueryTemporalSignalKind,
    RBSOrientationIntegration,
)
from app.services.multidimensional_query_analysis import (
    load_default_problem_institution_taxonomy,
)
from app.services.primary_cbr_families import PRIMARY_FAMILY_BY_CONCEPT
from app.services.primary_cbr_legal_similarity import (
    COMPONENT_WEIGHTS,
    CRITICAL_EXISTING_FIELDS,
    load_primary_cbr_legal_similarity_index,
)
from app.services.primary_cbr_levels import load_primary_cbr_level_registry
from cbr.similarity import (
    critical_field_conflicts,
    partial_case_similarity,
    set_jaccard_similarity,
)


class CBROrientationError(RuntimeError):
    """Error controlado de integración CBR orientadora D.4."""


class _CBROrientationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    integration_baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    expected_cbr_baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1200)
    minimum_similarity: float = Field(ge=0, le=1)
    top_k: int = Field(ge=1, le=20)
    expected_primary_profile_count: int = Field(ge=1)
    expected_validated_profile_count: int = Field(ge=0)
    expected_operational_case_count: int = Field(ge=0)
    requires_primary_entry_overlap: bool
    requires_primary_family_match: bool
    blocks_critical_field_conflicts: bool
    blocks_historical_context_mismatch: bool
    requires_normative_validation: bool
    requires_temporal_validation: bool
    full_normative_corpus_preserved: bool
    reuse_existing_cbr_similarity: bool
    uses_operational_cbr_cases: bool
    operational_reuse_enabled: bool
    normative_ranking_enabled: bool
    rag_retrieval_enabled: bool
    can_control_legal_decision: bool

    @model_validator(mode="after")
    def enforce_policy_boundary(self) -> _CBROrientationPolicy:
        if not self.requires_primary_entry_overlap or not self.requires_primary_family_match:
            raise ValueError("D.4 exige solapamiento de entrada y familia CBR primaria.")
        if not self.blocks_critical_field_conflicts:
            raise ValueError("D.4 debe conservar los conflictos críticos de C.9.")
        if not self.blocks_historical_context_mismatch:
            raise ValueError("D.4 debe conservar la barrera histórica de C.9.")
        if not self.requires_normative_validation or not self.requires_temporal_validation:
            raise ValueError("D.4 debe conservar revisión normativa y temporal.")
        if not self.full_normative_corpus_preserved or not self.reuse_existing_cbr_similarity:
            raise ValueError("D.4 debe preservar el corpus y reutilizar C.9.")
        if self.uses_operational_cbr_cases or self.operational_reuse_enabled:
            raise ValueError("D.4 no puede usar casos CBR operativos.")
        if self.normative_ranking_enabled or self.rag_retrieval_enabled:
            raise ValueError("D.4 no puede adelantar D.5 ni D.7.")
        if self.can_control_legal_decision:
            raise ValueError("D.4 no puede controlar Legal Decision.")
        return self


_RESOURCE_DIR = Path(__file__).resolve().parents[1] / "resources"


@lru_cache(maxsize=1)
def load_default_cbr_orientation_policy() -> _CBROrientationPolicy:
    path = _RESOURCE_DIR / "cbr_orientation_policy.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _CBROrientationPolicy.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise CBROrientationError("La política D.4 no es válida.") from exc


@lru_cache(maxsize=1)
def load_default_primary_cbr_legal_similarity() -> PrimaryCBRLegalSimilarityIndex:
    return load_primary_cbr_legal_similarity_index(
        _RESOURCE_DIR / "primary_cbr_legal_similarity.json"
    )


@lru_cache(maxsize=1)
def load_default_primary_cbr_levels() -> PrimaryCBRLevelRegistry:
    return load_primary_cbr_level_registry(_RESOURCE_DIR / "primary_cbr_levels.json")


def _first_dimension(
    multidimensional: MultidimensionalQueryAnalysis,
    name: QueryDimensionName,
) -> str | None:
    return next(
        (item.value for item in multidimensional.dimensions if item.dimension is name),
        None,
    )


def _query_field_values(
    multidimensional: MultidimensionalQueryAnalysis,
) -> dict[CaseField, str | int | None]:
    fiscal_year_text = _first_dimension(multidimensional, QueryDimensionName.FISCAL_YEAR)
    fiscal_year = int(fiscal_year_text) if fiscal_year_text is not None else None
    return {
        CaseField.TAXPAYER_TYPE: _first_dimension(
            multidimensional, QueryDimensionName.TAXPAYER_TYPE
        ),
        CaseField.ACTIVITY: _first_dimension(multidimensional, QueryDimensionName.ACTIVITY),
        CaseField.TAX: _first_dimension(multidimensional, QueryDimensionName.TAX),
        CaseField.PROBLEM_TYPE: multidimensional.primary_problem_id,
        CaseField.AUTHORITY_ACT: _first_dimension(
            multidimensional, QueryDimensionName.AUTHORITY_ACT
        ),
        CaseField.PROCEDURAL_STAGE: _first_dimension(
            multidimensional, QueryDimensionName.PROCEDURAL_STAGE
        ),
        CaseField.FISCAL_YEAR: fiscal_year,
    }


def _query_concept_ids(multidimensional: MultidimensionalQueryAnalysis) -> list[str]:
    return [
        item.concept_id
        for item in [
            *multidimensional.problem_matches,
            *multidimensional.institution_matches,
        ]
    ]


def _query_family_profile(
    multidimensional: MultidimensionalQueryAnalysis,
    taxonomy: FiscalProblemInstitutionTaxonomy,
) -> tuple[str | None, list[str], list[str]]:
    concept_ids = _query_concept_ids(multidimensional)
    if not concept_ids:
        return None, [], []

    ordered_anchor_concepts = [
        concept_id
        for concept_id in (
            multidimensional.primary_problem_id,
            multidimensional.primary_institution_id,
            *concept_ids,
        )
        if concept_id is not None
    ]
    primary_family_id = next(
        (
            PRIMARY_FAMILY_BY_CONCEPT[concept_id]
            for concept_id in ordered_anchor_concepts
            if concept_id in PRIMARY_FAMILY_BY_CONCEPT
        ),
        None,
    )
    if primary_family_id is None:
        return None, [], concept_ids

    taxonomy_by_id = {item.concept_id: item for item in taxonomy.concepts}
    families: list[str] = []
    for concept_id in concept_ids:
        concept = taxonomy_by_id.get(concept_id)
        if concept is None:
            raise CBROrientationError(f"D.4 recibió concepto A.6 desconocido: {concept_id}.")
        for family_id in concept.cbr_families:
            if family_id not in families:
                families.append(family_id)
    if primary_family_id not in families:
        raise CBROrientationError(
            f"D.4 no encontró respaldo A.6 para la familia {primary_family_id}."
        )
    families.remove(primary_family_id)
    families.insert(0, primary_family_id)
    return primary_family_id, families, concept_ids


def _query_historical_context(multidimensional: MultidimensionalQueryAnalysis) -> bool:
    return any(
        item.kind is QueryTemporalSignalKind.HISTORICAL_CONTEXT
        for item in multidimensional.temporal_signals
    )


def _weighted_similarity(
    existing_score: float,
    family_score: float,
    taxonomy_score: float,
    field_scores: list[FieldSimilarity],
) -> float:
    components = [
        (family_score, COMPONENT_WEIGHTS["family_overlap"]),
        (taxonomy_score, COMPONENT_WEIGHTS["taxonomy_overlap"]),
    ]
    if any(item.weight > 0 for item in field_scores):
        components.insert(
            0,
            (existing_score, COMPONENT_WEIGHTS["existing_cbr_fields"]),
        )
    denominator = sum(weight for _, weight in components)
    return 0.0 if denominator == 0 else sum(
        score * weight for score, weight in components
    ) / denominator


def _profile_field_values(
    profile: PrimaryCBRLegalSimilarityProfile,
) -> dict[CaseField, str | int | None]:
    seed = profile.similarity_seed
    return {
        CaseField.TAXPAYER_TYPE: seed.taxpayer_type,
        CaseField.ACTIVITY: seed.activity,
        CaseField.TAX: seed.tax,
        CaseField.PROBLEM_TYPE: seed.problem_type,
        CaseField.AUTHORITY_ACT: seed.authority_act,
        CaseField.PROCEDURAL_STAGE: seed.procedural_stage,
        CaseField.FISCAL_YEAR: seed.fiscal_year,
    }


def _normative_sources_from_refs(
    refs: list[str],
    normative_corpus_ids: list[str],
) -> list[str]:
    corpus_set = set(normative_corpus_ids)
    seen: set[str] = set()
    result: list[str] = []
    for ref in refs:
        corpus_id = ref.split(":", 1)[0]
        if corpus_id in corpus_set and corpus_id not in seen:
            seen.add(corpus_id)
            result.append(corpus_id)
    return result


def _validate_upstream(
    policy: _CBROrientationPolicy,
    legal_similarity: PrimaryCBRLegalSimilarityIndex,
    levels: PrimaryCBRLevelRegistry,
    activation: PrimarySourceActivation,
    rbs_orientation: RBSOrientationIntegration,
) -> None:
    if legal_similarity.baseline_commit != policy.expected_cbr_baseline_commit:
        raise CBROrientationError("D.4 recibió un índice C.9 con baseline inesperado.")
    if levels.baseline_commit != policy.expected_cbr_baseline_commit:
        raise CBROrientationError("D.4 recibió niveles C.10 con baseline inesperado.")
    if legal_similarity.profile_count != policy.expected_primary_profile_count:
        raise CBROrientationError("D.4 espera exactamente 37 perfiles CBR C.9.")
    if levels.validated_membership_count != policy.expected_validated_profile_count:
        raise CBROrientationError("D.4 espera exactamente 20 perfiles validados C.10.")
    if levels.operational_membership_count != policy.expected_operational_case_count:
        raise CBROrientationError("D.4 no espera casos operativos CBR en este bloque.")
    if abs(legal_similarity.minimum_similarity - policy.minimum_similarity) > 1e-9:
        raise CBROrientationError("D.4 debe conservar el umbral 0.60 de C.9.")
    if legal_similarity.component_weights != COMPONENT_WEIGHTS:
        raise CBROrientationError("D.4 debe conservar los pesos jurídicos C.9.")
    if activation.normative_corpus_ids != rbs_orientation.normative_corpus_ids:
        raise CBROrientationError("D.4 recibió espacios normativos D.2/D.3 distintos.")
    if not activation.full_normative_corpus_preserved:
        raise CBROrientationError("D.2 no preservó el corpus completo para D.4.")
    if not rbs_orientation.full_normative_corpus_preserved:
        raise CBROrientationError("D.3 no preservó el corpus completo para D.4.")


def integrate_cbr_orientation(
    multidimensional: MultidimensionalQueryAnalysis,
    primary_activation: PrimarySourceActivation,
    rbs_orientation: RBSOrientationIntegration,
    *,
    policy: _CBROrientationPolicy | None = None,
    legal_similarity: PrimaryCBRLegalSimilarityIndex | None = None,
    levels: PrimaryCBRLevelRegistry | None = None,
    taxonomy: FiscalProblemInstitutionTaxonomy | None = None,
) -> CBROrientationIntegration:
    """Orienta con CBR C.8-C.10 sin producir reutilización operativa ni autoridad."""
    resolved_policy = policy or load_default_cbr_orientation_policy()
    resolved_similarity = legal_similarity or load_default_primary_cbr_legal_similarity()
    resolved_levels = levels or load_default_primary_cbr_levels()
    resolved_taxonomy = taxonomy or load_default_problem_institution_taxonomy()
    _validate_upstream(
        resolved_policy,
        resolved_similarity,
        resolved_levels,
        primary_activation,
        rbs_orientation,
    )

    primary_family_id, family_ids, concept_ids = _query_family_profile(
        multidimensional,
        resolved_taxonomy,
    )
    historical_context = _query_historical_context(multidimensional)
    active_entries = {item.entry_id for item in primary_activation.entries}
    level_by_id = {item.situation_id: item for item in resolved_levels.assessments}
    query_fields = _query_field_values(multidimensional)

    candidates: list[
        tuple[float, PrimaryCBRLegalSimilarityProfile, float, float, float, list[str]]
    ] = []
    comparable_count = 0
    if primary_family_id is not None and active_entries:
        for profile in resolved_similarity.profiles:
            if profile.source_entry_id not in active_entries:
                continue
            if profile.primary_family_id != primary_family_id:
                continue
            if profile.historical_regime_context != historical_context:
                continue

            existing_score, field_scores = partial_case_similarity(
                query_fields,
                _profile_field_values(profile),
            )
            conflicts = critical_field_conflicts(field_scores, CRITICAL_EXISTING_FIELDS)
            if conflicts:
                continue
            comparable_count += 1
            family_score = set_jaccard_similarity(family_ids, profile.family_ids)
            taxonomy_score = set_jaccard_similarity(concept_ids, profile.concept_ids)
            overall = _weighted_similarity(
                existing_score,
                family_score,
                taxonomy_score,
                field_scores,
            )
            if overall < resolved_policy.minimum_similarity:
                continue
            active_fields = [
                item.field.value for item in field_scores if item.weight > 0
            ]
            candidates.append(
                (
                    overall,
                    profile,
                    existing_score,
                    family_score,
                    taxonomy_score,
                    active_fields,
                )
            )

    candidates.sort(
        key=lambda item: (
            -item[0],
            not item[1].corpus_validated,
            item[1].situation_id,
        )
    )
    selected = candidates[: resolved_policy.top_k]
    matches: list[CBROrientationMatch] = []
    for rank, (
        overall,
        profile,
        existing_score,
        family_score,
        taxonomy_score,
        active_fields,
    ) in enumerate(selected, start=1):
        level = level_by_id[profile.situation_id]
        matches.append(
            CBROrientationMatch(
                rank=rank,
                situation_id=profile.situation_id,
                source=profile.source,
                source_entry_id=profile.source_entry_id,
                primary_family_id=profile.primary_family_id,
                family_ids=list(profile.family_ids),
                concept_ids=list(profile.concept_ids),
                similarity=round(overall, 6),
                existing_cbr_field_similarity=round(existing_score, 6),
                family_overlap_similarity=round(family_score, 6),
                taxonomy_overlap_similarity=round(taxonomy_score, 6),
                active_existing_cbr_fields=active_fields,
                knowledge_level=level.highest_level,
                corpus_validation_outcome=profile.corpus_validation_outcome,
                corpus_validated=profile.corpus_validated,
                validated_normative_refs=list(level.validated_normative_refs),
                historical_regime_context=profile.historical_regime_context,
                requires_normative_review=not profile.corpus_validated,
                requires_temporal_review=True,
                retrieval_eligible=True,
                operational_reuse_allowed=False,
                orientation_only=True,
                can_control_legal_decision=False,
            )
        )

    normative_refs = [
        ref
        for match in matches
        if match.corpus_validated
        for ref in match.validated_normative_refs
    ]
    candidate_normative_sources = _normative_sources_from_refs(
        normative_refs,
        primary_activation.normative_corpus_ids,
    )
    return CBROrientationIntegration(
        schema_version=resolved_policy.schema_version,
        activation_applied=bool(matches),
        query_primary_family_id=primary_family_id,
        query_family_ids=family_ids,
        query_concept_ids=concept_ids,
        query_historical_context=historical_context,
        candidate_count=comparable_count,
        returned_count=len(matches),
        matches=matches,
        available_primary_profile_count=resolved_similarity.profile_count,
        available_validated_profile_count=resolved_levels.validated_membership_count,
        available_operational_case_count=resolved_levels.operational_membership_count,
        candidate_normative_sources=candidate_normative_sources,
        normative_corpus_ids=list(primary_activation.normative_corpus_ids),
        full_normative_corpus_preserved=True,
        requires_normative_validation=True,
        requires_temporal_validation=bool(matches) or multidimensional.requires_temporal_validation,
        reuse_existing_cbr_similarity=True,
        uses_primary_cbr_profiles=True,
        uses_operational_cbr_cases=False,
        operational_reuse_enabled=False,
        normative_ranking_enabled=False,
        rag_retrieval_enabled=False,
        can_control_legal_decision=False,
    )
