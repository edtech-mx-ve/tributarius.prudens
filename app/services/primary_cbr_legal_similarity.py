from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

from pydantic import ValidationError

from app.domain.cbr import CaseField, FieldSimilarity
from app.domain.primary_cbr_corpus_validation import (
    PrimaryCBRCorpusValidationOutcome,
    PrimaryCBRCorpusValidationReport,
)
from app.domain.primary_cbr_families import PrimaryCBRFamilyRegistry
from app.domain.primary_cbr_legal_similarity import (
    PrimaryCBRLegalSimilarityDecision,
    PrimaryCBRLegalSimilarityIndex,
    PrimaryCBRLegalSimilarityMatch,
    PrimaryCBRLegalSimilarityNeighbors,
    PrimaryCBRLegalSimilarityProfile,
)
from app.domain.primary_cbr_problem_institution import (
    PrimaryCBRClassifiedSimilaritySeed,
    PrimaryCBRProblemInstitutionClassification,
)
from cbr.engine import MINIMUM_CBR_SIMILARITY
from cbr.similarity import (
    FIELD_WEIGHTS,
    critical_field_conflicts,
    partial_case_similarity,
    set_jaccard_similarity,
)


class PrimaryCBRLegalSimilarityError(RuntimeError):
    """Error controlado de similitud jurídica primaria C.9."""


COMPONENT_WEIGHTS: dict[str, float] = {
    "existing_cbr_fields": 0.60,
    "family_overlap": 0.25,
    "taxonomy_overlap": 0.15,
}
CRITICAL_EXISTING_FIELDS = (
    CaseField.TAXPAYER_TYPE,
    CaseField.TAX,
    CaseField.PROBLEM_TYPE,
)


def load_primary_cbr_legal_similarity_index(path: Path) -> PrimaryCBRLegalSimilarityIndex:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryCBRLegalSimilarityError(f"No existe el índice CBR C.9: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return PrimaryCBRLegalSimilarityIndex.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PrimaryCBRLegalSimilarityError(
            "El índice de similitud CBR C.9 no es válido."
        ) from exc


def _field_values(seed: PrimaryCBRClassifiedSimilaritySeed) -> dict[CaseField, str | int | None]:
    return {
        CaseField.TAXPAYER_TYPE: seed.taxpayer_type,
        CaseField.ACTIVITY: seed.activity,
        CaseField.TAX: seed.tax,
        CaseField.PROBLEM_TYPE: seed.problem_type,
        CaseField.AUTHORITY_ACT: seed.authority_act,
        CaseField.PROCEDURAL_STAGE: seed.procedural_stage,
        CaseField.FISCAL_YEAR: seed.fiscal_year,
    }


def _active_field_names(scores: list[FieldSimilarity]) -> list[str]:
    return [item.field.value for item in scores if item.weight > 0]


def _weighted_legal_similarity(
    existing_score: float,
    family_score: float,
    taxonomy_score: float,
    *,
    existing_fields_active: bool,
) -> float:
    components = [
        (family_score, COMPONENT_WEIGHTS["family_overlap"]),
        (taxonomy_score, COMPONENT_WEIGHTS["taxonomy_overlap"]),
    ]
    if existing_fields_active:
        components.insert(0, (existing_score, COMPONENT_WEIGHTS["existing_cbr_fields"]))
    weighted = sum(score * weight for score, weight in components)
    denominator = sum(weight for _, weight in components)
    return 0.0 if denominator == 0 else weighted / denominator


def score_primary_cbr_legal_similarity(
    left: PrimaryCBRLegalSimilarityProfile,
    right: PrimaryCBRLegalSimilarityProfile,
) -> tuple[
    PrimaryCBRLegalSimilarityDecision,
    float,
    float,
    float,
    float,
    list[FieldSimilarity],
    list[CaseField],
]:
    """Compara dos perfiles C.9 usando el mismo núcleo de similitud CBR existente."""
    if left.primary_family_id != right.primary_family_id:
        return (
            PrimaryCBRLegalSimilarityDecision.BLOCKED_PRIMARY_FAMILY,
            0.0,
            0.0,
            0.0,
            0.0,
            [],
            [],
        )

    if left.historical_regime_context != right.historical_regime_context:
        return (
            PrimaryCBRLegalSimilarityDecision.BLOCKED_HISTORICAL_CONTEXT,
            0.0,
            0.0,
            0.0,
            0.0,
            [],
            [],
        )

    existing_score, field_scores = partial_case_similarity(
        _field_values(left.similarity_seed),
        _field_values(right.similarity_seed),
    )
    conflicts = critical_field_conflicts(field_scores, CRITICAL_EXISTING_FIELDS)
    if conflicts:
        return (
            PrimaryCBRLegalSimilarityDecision.BLOCKED_CRITICAL_CONFLICT,
            0.0,
            existing_score,
            0.0,
            0.0,
            field_scores,
            conflicts,
        )

    family_score = set_jaccard_similarity(left.family_ids, right.family_ids)
    taxonomy_score = set_jaccard_similarity(left.concept_ids, right.concept_ids)
    overall = _weighted_legal_similarity(
        existing_score,
        family_score,
        taxonomy_score,
        existing_fields_active=any(item.weight > 0 for item in field_scores),
    )
    decision = (
        PrimaryCBRLegalSimilarityDecision.ELIGIBLE
        if overall >= MINIMUM_CBR_SIMILARITY
        else PrimaryCBRLegalSimilarityDecision.BELOW_THRESHOLD
    )
    return (
        decision,
        overall,
        existing_score,
        family_score,
        taxonomy_score,
        field_scores,
        conflicts,
    )


def _profiles_from_upstream(
    classification: PrimaryCBRProblemInstitutionClassification,
    corpus_validation: PrimaryCBRCorpusValidationReport,
    family_registry: PrimaryCBRFamilyRegistry,
) -> list[PrimaryCBRLegalSimilarityProfile]:
    c5_by_id = {item.situation_id: item for item in classification.classifications}
    c7_by_id = {item.situation_id: item for item in corpus_validation.situations}
    profiles: list[PrimaryCBRLegalSimilarityProfile] = []
    for assignment in family_registry.assignments:
        c5 = c5_by_id[assignment.situation_id]
        c7 = c7_by_id[assignment.situation_id]
        profiles.append(
            PrimaryCBRLegalSimilarityProfile(
                situation_id=assignment.situation_id,
                source=assignment.source,
                source_entry_id=assignment.source_entry_id,
                historical_regime_context=assignment.historical_regime_context,
                similarity_seed=c5.similarity_seed,
                primary_family_id=assignment.primary_family_id,
                family_ids=assignment.family_ids,
                concept_ids=assignment.family_basis_concept_ids,
                corpus_validation_outcome=c7.validation_outcome,
                corpus_validated=c7.corpus_validated,
                temporal_validation_pending=c7.temporal_validation_pending,
            )
        )
    return profiles


def build_primary_cbr_legal_similarity_index(
    classification: PrimaryCBRProblemInstitutionClassification,
    corpus_validation: PrimaryCBRCorpusValidationReport,
    family_registry: PrimaryCBRFamilyRegistry,
    *,
    top_k: int = 5,
) -> PrimaryCBRLegalSimilarityIndex:
    baselines = {
        classification.baseline_commit,
        corpus_validation.baseline_commit,
        family_registry.baseline_commit,
    }
    if len(baselines) != 1:
        raise PrimaryCBRLegalSimilarityError("C.9 debe conservar el baseline C.5/C.7/C.8.")
    profiles = _profiles_from_upstream(classification, corpus_validation, family_registry)
    by_id = {item.situation_id: item for item in profiles}
    if len(by_id) != len(profiles):
        raise PrimaryCBRLegalSimilarityError("C.9 recibió situaciones duplicadas.")

    counts = {decision: 0 for decision in PrimaryCBRLegalSimilarityDecision}
    same_family_count = 0
    directed_eligible: dict[str, list[tuple[float, str, float, float, float, list[str]]]] = {
        profile.situation_id: [] for profile in profiles
    }

    for left, right in combinations(profiles, 2):
        if left.primary_family_id == right.primary_family_id:
            same_family_count += 1
        decision, overall, existing, family, taxonomy, field_scores, _ = (
            score_primary_cbr_legal_similarity(left, right)
        )
        counts[decision] += 1
        if decision is not PrimaryCBRLegalSimilarityDecision.ELIGIBLE:
            continue
        active_fields = _active_field_names(field_scores)
        directed_eligible[left.situation_id].append(
            (overall, right.situation_id, existing, family, taxonomy, active_fields)
        )
        directed_eligible[right.situation_id].append(
            (overall, left.situation_id, existing, family, taxonomy, active_fields)
        )

    neighbors: list[PrimaryCBRLegalSimilarityNeighbors] = []
    for profile in profiles:
        candidates = sorted(
            directed_eligible[profile.situation_id],
            key=lambda item: (-item[0], item[1]),
        )
        selected = candidates[:top_k]
        matches: list[PrimaryCBRLegalSimilarityMatch] = []
        for rank, (overall, other_id, existing, family, taxonomy, active_fields) in enumerate(
            selected,
            start=1,
        ):
            other = by_id[other_id]
            requires_review = (
                other.corpus_validation_outcome
                is not PrimaryCBRCorpusValidationOutcome.CONSISTENT
            )
            matches.append(
                PrimaryCBRLegalSimilarityMatch(
                    rank=rank,
                    situation_id=other_id,
                    source=other.source,
                    primary_family_id=other.primary_family_id,
                    similarity=round(overall, 6),
                    existing_cbr_field_similarity=round(existing, 6),
                    family_overlap_similarity=round(family, 6),
                    taxonomy_overlap_similarity=round(taxonomy, 6),
                    active_existing_cbr_fields=active_fields,
                    corpus_validation_outcome=other.corpus_validation_outcome,
                    corpus_validated=other.corpus_validated,
                    historical_regime_context=other.historical_regime_context,
                    requires_normative_review=requires_review,
                )
            )
        neighbors.append(
            PrimaryCBRLegalSimilarityNeighbors(
                situation_id=profile.situation_id,
                candidate_count=len(candidates),
                returned_count=len(matches),
                matches=matches,
            )
        )

    total_pairs = len(profiles) * (len(profiles) - 1) // 2
    return PrimaryCBRLegalSimilarityIndex(
        schema_version="1.0",
        baseline_commit=family_registry.baseline_commit,
        purpose=(
            "Extender la similitud CBR existente con partición por familia C.8 y solapamiento "
            "taxonómico, preservando FIELD_WEIGHTS, umbral 0.60, trazabilidad C.7 y sin crear "
            "casos operativos ni reutilización jurídica automática."
        ),
        minimum_similarity=MINIMUM_CBR_SIMILARITY,
        top_k=top_k,
        profile_count=len(profiles),
        total_pair_count=total_pairs,
        same_primary_family_pair_count=same_family_count,
        blocked_primary_family_pair_count=counts[
            PrimaryCBRLegalSimilarityDecision.BLOCKED_PRIMARY_FAMILY
        ],
        blocked_critical_conflict_pair_count=counts[
            PrimaryCBRLegalSimilarityDecision.BLOCKED_CRITICAL_CONFLICT
        ],
        blocked_historical_context_pair_count=counts[
            PrimaryCBRLegalSimilarityDecision.BLOCKED_HISTORICAL_CONTEXT
        ],
        below_threshold_pair_count=counts[PrimaryCBRLegalSimilarityDecision.BELOW_THRESHOLD],
        eligible_pair_count=counts[PrimaryCBRLegalSimilarityDecision.ELIGIBLE],
        stored_neighbor_link_count=sum(len(items[:top_k]) for items in directed_eligible.values()),
        component_weights=COMPONENT_WEIGHTS,
        critical_existing_fields=[field.value for field in CRITICAL_EXISTING_FIELDS],
        profiles=profiles,
        neighbors=neighbors,
    )


def validate_primary_cbr_legal_similarity_index(
    index: PrimaryCBRLegalSimilarityIndex,
    classification: PrimaryCBRProblemInstitutionClassification,
    corpus_validation: PrimaryCBRCorpusValidationReport,
    family_registry: PrimaryCBRFamilyRegistry,
) -> None:
    """Reproduce C.9 desde C.5/C.7/C.8 y comprueba que no altere el CBR histórico."""
    if index.minimum_similarity != MINIMUM_CBR_SIMILARITY:
        raise PrimaryCBRLegalSimilarityError("C.9 debe conservar el umbral 0.60 del CBR actual.")
    if index.component_weights != COMPONENT_WEIGHTS:
        raise PrimaryCBRLegalSimilarityError("C.9 alteró los pesos de componentes jurídicos.")
    if index.critical_existing_fields != [field.value for field in CRITICAL_EXISTING_FIELDS]:
        raise PrimaryCBRLegalSimilarityError("C.9 alteró los campos críticos CBR existentes.")
    if set(FIELD_WEIGHTS) != set(CaseField) or abs(sum(FIELD_WEIGHTS.values()) - 1.0) > 1e-9:
        raise PrimaryCBRLegalSimilarityError(
            "FIELD_WEIGHTS del CBR existente dejó de ser válido."
        )

    expected = build_primary_cbr_legal_similarity_index(
        classification,
        corpus_validation,
        family_registry,
        top_k=index.top_k,
    )
    if index.model_dump(mode="json") != expected.model_dump(mode="json"):
        raise PrimaryCBRLegalSimilarityError("El índice C.9 no es reproducible desde C.5/C.7/C.8.")
