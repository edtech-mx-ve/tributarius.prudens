from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.domain.primary_legal_knowledge import (
    FiscalProblemInstitutionKind,
    FiscalProblemInstitutionTaxonomy,
)
from app.domain.query import (
    ExtractedFact,
    FactOrigin,
    MultidimensionalQueryAnalysis,
    QueryDimensionBasis,
    QueryDimensionName,
    QueryDimensionValue,
    QueryIntent,
    QueryTaxonomyBasis,
    QueryTaxonomyKind,
    QueryTaxonomyMatch,
    QueryTemporalSignal,
    QueryTemporalSignalKind,
)
from app.services.primary_legal_knowledge import load_fiscal_problem_institution_taxonomy


class MultidimensionalQueryAnalysisError(RuntimeError):
    """Error controlado del analizador multidimensional D.1."""


class _MultidimensionalQueryProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1000)
    dimension_terms: dict[QueryDimensionName, dict[str, list[str]]]
    intent_problem_map: dict[QueryIntent, list[str]]
    intent_institution_map: dict[QueryIntent, list[str]]
    dimension_institution_map: dict[str, list[str]]
    required_dimensions_by_intent: dict[QueryIntent, list[QueryDimensionName]]
    current_context_terms: list[str]
    historical_context_terms: list[str]
    vigency_request_terms: list[str]
    requires_normative_validation: bool = True
    downstream_activation_enabled: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d1_profile_boundary(self) -> _MultidimensionalQueryProfile:
        if not self.requires_normative_validation:
            raise ValueError("D.1 siempre requiere validación normativa posterior.")
        if self.downstream_activation_enabled:
            raise ValueError("D.1 no puede activar etapas D.2-D.9.")
        if self.can_control_legal_decision:
            raise ValueError("D.1 no puede controlar Legal Decision.")
        return self


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _contains_phrase(folded_text: str, phrase: str) -> bool:
    folded_phrase = _fold(phrase).strip()
    if not folded_phrase:
        return False
    pattern = rf"(?<![a-z0-9]){re.escape(folded_phrase)}(?![a-z0-9])"
    return re.search(pattern, folded_text) is not None


def _default_resource_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "resources"


@lru_cache(maxsize=1)
def load_default_multidimensional_query_profile() -> _MultidimensionalQueryProfile:
    path = _default_resource_dir() / "multidimensional_query_profiles.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _MultidimensionalQueryProfile.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise MultidimensionalQueryAnalysisError(
            "El perfil multidimensional D.1 no es válido."
        ) from exc


@lru_cache(maxsize=1)
def load_default_problem_institution_taxonomy() -> FiscalProblemInstitutionTaxonomy:
    return load_fiscal_problem_institution_taxonomy(
        _default_resource_dir() / "fiscal_problem_institution_taxonomy.json"
    )


def _validate_profile_against_taxonomy(
    profile: _MultidimensionalQueryProfile,
    taxonomy: FiscalProblemInstitutionTaxonomy,
) -> None:
    concepts = {item.concept_id: item for item in taxonomy.concepts}
    problem_ids = {
        item.concept_id
        for item in taxonomy.concepts
        if item.kind is FiscalProblemInstitutionKind.PROBLEM
    }
    institution_ids = {
        item.concept_id
        for item in taxonomy.concepts
        if item.kind is FiscalProblemInstitutionKind.INSTITUTION
    }
    if len(problem_ids) != 6 or len(institution_ids) != 6:
        raise MultidimensionalQueryAnalysisError(
            "D.1 espera exactamente la taxonomía A.6 de 6 problemas y 6 instituciones."
        )

    for refs in profile.intent_problem_map.values():
        if set(refs) - problem_ids:
            raise MultidimensionalQueryAnalysisError(
                "D.1 contiene un puente de intención hacia un problema A.6 inexistente."
            )
    for refs in profile.intent_institution_map.values():
        if set(refs) - institution_ids:
            raise MultidimensionalQueryAnalysisError(
                "D.1 contiene un puente de intención hacia una institución A.6 inexistente."
            )
    for refs in profile.dimension_institution_map.values():
        if set(refs) - institution_ids:
            raise MultidimensionalQueryAnalysisError(
                "D.1 contiene un puente dimensional hacia una institución A.6 inexistente."
            )
    if len(concepts) != 12:
        raise MultidimensionalQueryAnalysisError(
            "D.1 debe consumir exactamente los 12 conceptos A.6."
        )


def _normalize_structured_value(
    dimension: QueryDimensionName,
    value: str,
    profile: _MultidimensionalQueryProfile,
) -> str:
    clean = " ".join(value.split())
    folded = _fold(clean)
    for canonical, terms in profile.dimension_terms.get(dimension, {}).items():
        if folded == _fold(canonical) or any(folded == _fold(term) for term in terms):
            return canonical
    return clean


def _add_dimension(
    output: list[QueryDimensionValue],
    *,
    dimension: QueryDimensionName,
    value: str,
    origin: FactOrigin,
    basis: QueryDimensionBasis,
    evidence: str,
    confidence: float,
) -> None:
    key = (dimension, value.casefold())
    for index, item in enumerate(output):
        if (item.dimension, item.value.casefold()) != key:
            continue
        if confidence > item.confidence:
            output[index] = QueryDimensionValue(
                dimension=dimension,
                value=value,
                origin=origin,
                basis=basis,
                evidence=evidence,
                confidence=confidence,
            )
        return
    output.append(
        QueryDimensionValue(
            dimension=dimension,
            value=value,
            origin=origin,
            basis=basis,
            evidence=evidence,
            confidence=confidence,
        )
    )


def _dimensions_from_facts(
    facts: list[ExtractedFact],
    profile: _MultidimensionalQueryProfile,
) -> list[QueryDimensionValue]:
    output: list[QueryDimensionValue] = []
    aliases: dict[str, QueryDimensionName] = {
        "matter": QueryDimensionName.TAX,
        "tax": QueryDimensionName.TAX,
        "taxpayer_type": QueryDimensionName.TAXPAYER_TYPE,
        "activity": QueryDimensionName.ACTIVITY,
        "fiscal_regime": QueryDimensionName.FISCAL_REGIME,
        "authority_act": QueryDimensionName.AUTHORITY_ACT,
        "procedural_stage": QueryDimensionName.PROCEDURAL_STAGE,
        "fiscal_year": QueryDimensionName.FISCAL_YEAR,
    }
    for fact in facts:
        dimension = aliases.get(fact.name.strip().casefold())
        if dimension is None:
            continue
        value = _normalize_structured_value(dimension, fact.value, profile)
        _add_dimension(
            output,
            dimension=dimension,
            value=value,
            origin=fact.origin,
            basis=QueryDimensionBasis.STRUCTURED_FACT,
            evidence=f"fact:{fact.name}",
            confidence=1.0 if fact.origin is FactOrigin.EXPLICIT else 0.75,
        )
    return output


def _dimensions_from_text(
    normalized_query: str,
    profile: _MultidimensionalQueryProfile,
    output: list[QueryDimensionValue],
) -> None:
    folded = _fold(normalized_query)
    for dimension, canonical_terms in profile.dimension_terms.items():
        for canonical, terms in canonical_terms.items():
            matched = next((term for term in terms if _contains_phrase(folded, term)), None)
            if matched is None:
                continue
            _add_dimension(
                output,
                dimension=dimension,
                value=canonical,
                origin=FactOrigin.EXPLICIT,
                basis=QueryDimensionBasis.QUERY_TEXT,
                evidence=matched,
                confidence=1.0,
            )

    for year in re.findall(r"(?<!\d)(19\d{2}|20\d{2}|21\d{2}|2200)(?!\d)", normalized_query):
        _add_dimension(
            output,
            dimension=QueryDimensionName.FISCAL_YEAR,
            value=year,
            origin=FactOrigin.EXPLICIT,
            basis=QueryDimensionBasis.QUERY_TEXT,
            evidence=year,
            confidence=1.0,
        )


def _match_taxonomy_text(
    normalized_query: str,
    taxonomy: FiscalProblemInstitutionTaxonomy,
) -> dict[str, QueryTaxonomyMatch]:
    folded = _fold(normalized_query)
    matches: dict[str, QueryTaxonomyMatch] = {}
    for concept in taxonomy.concepts:
        candidates = [concept.label, *concept.aliases]
        matched = next((term for term in candidates if _contains_phrase(folded, term)), None)
        if matched is None:
            continue
        kind = (
            QueryTaxonomyKind.PROBLEM
            if concept.kind is FiscalProblemInstitutionKind.PROBLEM
            else QueryTaxonomyKind.INSTITUTION
        )
        matches[concept.concept_id] = QueryTaxonomyMatch(
            concept_id=concept.concept_id,
            kind=kind,
            label=concept.label,
            basis=QueryTaxonomyBasis.TAXONOMY_TEXT,
            evidence=matched,
            score=1.0,
        )
    return matches


def _put_taxonomy_match(
    matches: dict[str, QueryTaxonomyMatch],
    *,
    concept_id: str,
    basis: QueryTaxonomyBasis,
    evidence: str,
    score: float,
    taxonomy_by_id: dict[str, Any],
) -> None:
    concept = taxonomy_by_id.get(concept_id)
    if concept is None:
        raise MultidimensionalQueryAnalysisError(
            f"D.1 referencia concepto A.6 inexistente: {concept_id}."
        )
    kind = (
        QueryTaxonomyKind.PROBLEM
        if concept.kind is FiscalProblemInstitutionKind.PROBLEM
        else QueryTaxonomyKind.INSTITUTION
    )
    candidate = QueryTaxonomyMatch(
        concept_id=concept_id,
        kind=kind,
        label=concept.label,
        basis=basis,
        evidence=evidence,
        score=score,
    )
    current = matches.get(concept_id)
    if current is None or candidate.score > current.score:
        matches[concept_id] = candidate


def _bridge_intents(
    primary_intent: QueryIntent,
    secondary_intents: list[QueryIntent],
    profile: _MultidimensionalQueryProfile,
    taxonomy_by_id: dict[str, Any],
    matches: dict[str, QueryTaxonomyMatch],
) -> None:
    for position, intent in enumerate([primary_intent, *secondary_intents]):
        score = 0.90 if position == 0 else 0.80
        for concept_id in profile.intent_problem_map.get(intent, []):
            _put_taxonomy_match(
                matches,
                concept_id=concept_id,
                basis=QueryTaxonomyBasis.INTENT_BRIDGE,
                evidence=f"intent:{intent.value}",
                score=score,
                taxonomy_by_id=taxonomy_by_id,
            )
        for concept_id in profile.intent_institution_map.get(intent, []):
            _put_taxonomy_match(
                matches,
                concept_id=concept_id,
                basis=QueryTaxonomyBasis.INTENT_BRIDGE,
                evidence=f"intent:{intent.value}",
                score=score,
                taxonomy_by_id=taxonomy_by_id,
            )


def _bridge_dimensions(
    dimensions: list[QueryDimensionValue],
    profile: _MultidimensionalQueryProfile,
    taxonomy_by_id: dict[str, Any],
    matches: dict[str, QueryTaxonomyMatch],
) -> None:
    for dimension in dimensions:
        key = f"{dimension.dimension.value}:{dimension.value}"
        for concept_id in profile.dimension_institution_map.get(key, []):
            _put_taxonomy_match(
                matches,
                concept_id=concept_id,
                basis=QueryTaxonomyBasis.DIMENSION_BRIDGE,
                evidence=key,
                score=0.85,
                taxonomy_by_id=taxonomy_by_id,
            )


def _rank_matches(
    matches: dict[str, QueryTaxonomyMatch],
    taxonomy: FiscalProblemInstitutionTaxonomy,
    kind: QueryTaxonomyKind,
) -> list[QueryTaxonomyMatch]:
    taxonomy_order = {item.concept_id: index for index, item in enumerate(taxonomy.concepts)}
    selected = [item for item in matches.values() if item.kind is kind]
    selected.sort(key=lambda item: (-item.score, taxonomy_order[item.concept_id]))
    if not selected:
        return []
    return [
        item.model_copy(update={"primary": index == 0})
        for index, item in enumerate(selected)
    ]


def _temporal_signals(
    normalized_query: str,
    dimensions: list[QueryDimensionValue],
    profile: _MultidimensionalQueryProfile,
) -> list[QueryTemporalSignal]:
    folded = _fold(normalized_query)
    output: list[QueryTemporalSignal] = []
    seen: set[tuple[QueryTemporalSignalKind, str]] = set()

    def add(kind: QueryTemporalSignalKind, value: str, evidence: str) -> None:
        key = (kind, value.casefold())
        if key in seen:
            return
        seen.add(key)
        output.append(QueryTemporalSignal(kind=kind, value=value, evidence=evidence))

    for item in dimensions:
        if item.dimension is QueryDimensionName.FISCAL_YEAR:
            add(QueryTemporalSignalKind.EXPLICIT_YEAR, item.value, item.evidence)
        if item.dimension is QueryDimensionName.FISCAL_REGIME and item.value == "RIF":
            add(QueryTemporalSignalKind.HISTORICAL_CONTEXT, "RIF", item.evidence)

    for term in profile.current_context_terms:
        if _contains_phrase(folded, term):
            add(QueryTemporalSignalKind.CURRENT_CONTEXT, "current", term)
    for term in profile.historical_context_terms:
        if _contains_phrase(folded, term):
            add(QueryTemporalSignalKind.HISTORICAL_CONTEXT, "historical", term)
    for term in profile.vigency_request_terms:
        if _contains_phrase(folded, term):
            add(QueryTemporalSignalKind.VIGENCY_REQUEST, "vigency", term)
    return output


def analyze_query_multidimensional(
    *,
    normalized_query: str,
    primary_intent: QueryIntent,
    secondary_intents: list[QueryIntent],
    facts: list[ExtractedFact],
    profile: _MultidimensionalQueryProfile | None = None,
    taxonomy: FiscalProblemInstitutionTaxonomy | None = None,
) -> MultidimensionalQueryAnalysis:
    """Construye D.1 sin resolver Derecho ni activar etapas heurísticas posteriores."""
    resolved_profile = profile or load_default_multidimensional_query_profile()
    resolved_taxonomy = taxonomy or load_default_problem_institution_taxonomy()
    _validate_profile_against_taxonomy(resolved_profile, resolved_taxonomy)
    taxonomy_by_id = {item.concept_id: item for item in resolved_taxonomy.concepts}

    dimensions = _dimensions_from_facts(facts, resolved_profile)
    _dimensions_from_text(normalized_query, resolved_profile, dimensions)

    matches = _match_taxonomy_text(normalized_query, resolved_taxonomy)
    _bridge_intents(
        primary_intent,
        secondary_intents,
        resolved_profile,
        taxonomy_by_id,
        matches,
    )
    _bridge_dimensions(
        dimensions,
        resolved_profile,
        taxonomy_by_id,
        matches,
    )

    problems = _rank_matches(matches, resolved_taxonomy, QueryTaxonomyKind.PROBLEM)
    institutions = _rank_matches(matches, resolved_taxonomy, QueryTaxonomyKind.INSTITUTION)
    temporal = _temporal_signals(normalized_query, dimensions, resolved_profile)

    present = {item.dimension for item in dimensions}
    required = resolved_profile.required_dimensions_by_intent.get(primary_intent, [])
    unresolved = [dimension for dimension in required if dimension not in present]
    requires_temporal = bool(
        temporal
        or any(
            item.dimension in {QueryDimensionName.TAX, QueryDimensionName.FISCAL_REGIME}
            for item in dimensions
        )
        or problems
        or institutions
    )

    return MultidimensionalQueryAnalysis(
        schema_version=resolved_profile.schema_version,
        dimensions=dimensions,
        primary_problem_id=problems[0].concept_id if problems else None,
        primary_institution_id=institutions[0].concept_id if institutions else None,
        problem_matches=problems,
        institution_matches=institutions,
        temporal_signals=temporal,
        unresolved_dimensions=unresolved,
        semantic_issue_count=len(problems) + len(institutions),
        requires_temporal_validation=requires_temporal,
        downstream_activation_enabled=False,
        can_control_legal_decision=False,
    )
