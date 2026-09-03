from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.domain.documents import SourceType
from app.domain.query import (
    FocusedRAGExecution,
    FocusedRAGPlan,
    FullCorpusExpansionExecution,
    FullCorpusExpansionPlan,
    FullCorpusExpansionReason,
    MultidimensionalQueryAnalysis,
    NormativeRankingIntegration,
)
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.models import RetrievalHit, RetrievalResult


class FullCorpusExpansionError(RuntimeError):
    """Error controlado de expansión normativa D.8."""


class _FullCorpusExpansionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1200)
    normative_only: bool = True
    minimum_focused_hits: int = Field(default=3, ge=1, le=20)
    minimum_focused_source_count: int = Field(default=2, ge=1, le=5)
    per_source_top_k: int = Field(default=2, ge=1, le=20)
    semantic_score_weight: float = Field(default=0.9, ge=0, le=1)
    source_priority_weight: float = Field(default=0.1, ge=0, le=1)
    focused_merge_bonus: float = Field(default=0.05, ge=0, le=0.25)
    full_corpus_fallback_enabled: bool = True
    expand_when_no_focused_hits: bool = True
    expand_when_focused_hits_insufficient: bool = True
    expand_when_source_coverage_insufficient: bool = True
    trigger_on_multi_issue: bool = True
    multi_issue_minimum: int = Field(default=4, ge=2, le=20)
    trigger_on_temporal_block: bool = False
    focused_priority_preserved: bool = True
    full_normative_corpus_preserved: bool = True
    source_exclusion_enabled: bool = False
    requires_normative_validation: bool = True
    requires_temporal_validation: bool = True
    temporal_validation_completed: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d8_policy_boundary(self) -> _FullCorpusExpansionPolicy:
        if not self.normative_only:
            raise ValueError("D.8 sólo puede expandir evidencia normativa interna.")
        if abs(self.semantic_score_weight + self.source_priority_weight - 1.0) > 1e-9:
            raise ValueError("Los pesos de expansión D.8 deben sumar 1.0.")
        if not self.full_corpus_fallback_enabled:
            raise ValueError("D.8 requiere fallback al corpus completo cuando no hay foco.")
        if not all(
            (
                self.expand_when_no_focused_hits,
                self.expand_when_focused_hits_insufficient,
                self.expand_when_source_coverage_insufficient,
            )
        ):
            raise ValueError("D.8 debe cubrir las tres formas básicas de insuficiencia focal.")
        if not self.focused_priority_preserved:
            raise ValueError("D.8 debe preservar prioridad para evidencia focal D.7.")
        if not self.full_normative_corpus_preserved or self.source_exclusion_enabled:
            raise ValueError("D.8 no puede excluir corpus del espacio normativo A.8.")
        if not self.requires_normative_validation or not self.requires_temporal_validation:
            raise ValueError("D.8 no reemplaza validación normativa ni temporal.")
        if self.temporal_validation_completed or self.can_control_legal_decision:
            raise ValueError("D.8 no puede adelantar D.9 ni controlar Legal Decision.")
        return self


class RetrieverLike(Protocol):
    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult: ...


@dataclass(frozen=True)
class FullCorpusExpansionRun:
    retrieval: RetrievalResult
    execution: FullCorpusExpansionExecution


@dataclass(frozen=True)
class _ExpansionCandidate:
    hit: RetrievalHit
    source_rank: int
    final_score: float


def _resource_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "resources"


@lru_cache(maxsize=1)
def load_default_full_corpus_expansion_policy() -> _FullCorpusExpansionPolicy:
    path = _resource_dir() / "full_corpus_expansion_policy.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _FullCorpusExpansionPolicy.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise FullCorpusExpansionError("La política de expansión D.8 no es válida.") from exc


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _unique_reasons(
    values: list[FullCorpusExpansionReason],
) -> list[FullCorpusExpansionReason]:
    return list(dict.fromkeys(values))


def build_full_corpus_expansion_plan(
    multidimensional: MultidimensionalQueryAnalysis,
    ranking: NormativeRankingIntegration,
    focused_plan: FocusedRAGPlan,
) -> FullCorpusExpansionPlan:
    """Construye D.8 sin recuperar contenido ni decidir aplicabilidad."""
    policy = load_default_full_corpus_expansion_policy()
    corpus_ids = list(ranking.normative_corpus_ids)
    if len(corpus_ids) != 12 or len(set(corpus_ids)) != 12:
        raise FullCorpusExpansionError("D.8 requiere exactamente los 12 corpus A.8.")
    if focused_plan.normative_corpus_ids != corpus_ids:
        raise FullCorpusExpansionError("D.7 y D.5 no conservan el mismo corpus A.8.")
    if not ranking.full_normative_corpus_preserved or ranking.source_exclusion_enabled:
        raise FullCorpusExpansionError("D.5 perdió el espacio normativo requerido por D.8.")
    if not focused_plan.full_normative_corpus_preserved or focused_plan.source_exclusion_enabled:
        raise FullCorpusExpansionError("D.7 perdió el espacio normativo requerido por D.8.")

    focus_source_ids = list(focused_plan.focus_source_ids)
    focus_set = set(focus_source_ids)
    expansion_source_ids = [
        item.corpus_id for item in ranking.ranked_sources if item.corpus_id not in focus_set
    ]
    if not focus_source_ids:
        expansion_source_ids = [item.corpus_id for item in ranking.ranked_sources]

    source_relevance_scores = {
        item.corpus_id: item.relevance_score for item in ranking.ranked_sources
    }
    return FullCorpusExpansionPlan(
        plan_applied=True,
        focus_source_ids=focus_source_ids,
        expansion_source_ids=expansion_source_ids,
        normative_corpus_ids=corpus_ids,
        source_relevance_scores=source_relevance_scores,
        allowed_chunk_types=list(focused_plan.allowed_chunk_types),
        semantic_issue_count=multidimensional.semantic_issue_count,
        temporal_blocked_source_ids=list(focused_plan.temporal_blocked_source_ids),
        minimum_focused_hits=policy.minimum_focused_hits,
        minimum_focused_source_count=policy.minimum_focused_source_count,
        full_corpus_fallback_enabled=True,
        expansion_after_focused_insufficiency=True,
        trigger_on_multi_issue=policy.trigger_on_multi_issue,
        trigger_on_temporal_block=policy.trigger_on_temporal_block,
        normative_only=True,
        focused_priority_preserved=True,
        expansion_to_full_corpus_enabled=True,
        full_normative_corpus_preserved=True,
        source_exclusion_enabled=False,
        requires_normative_validation=True,
        requires_temporal_validation=True,
        temporal_validation_completed=False,
        can_control_legal_decision=False,
    )


def _expansion_reasons(
    plan: FullCorpusExpansionPlan,
    focused_execution: FocusedRAGExecution | None,
) -> list[FullCorpusExpansionReason]:
    policy = load_default_full_corpus_expansion_policy()
    if focused_execution is None or not plan.focus_source_ids:
        return [FullCorpusExpansionReason.NO_FOCUSED_PLAN]

    reasons: list[FullCorpusExpansionReason] = []
    if focused_execution.returned_count == 0:
        reasons.append(FullCorpusExpansionReason.NO_FOCUSED_HITS)
    elif focused_execution.returned_count < plan.minimum_focused_hits:
        reasons.append(FullCorpusExpansionReason.INSUFFICIENT_FOCUSED_HITS)

    required_sources = min(plan.minimum_focused_source_count, len(plan.focus_source_ids))
    if len(focused_execution.hit_source_ids) < required_sources:
        reasons.append(FullCorpusExpansionReason.INSUFFICIENT_FOCUSED_SOURCE_COVERAGE)

    if plan.trigger_on_multi_issue and plan.semantic_issue_count >= policy.multi_issue_minimum:
        reasons.append(FullCorpusExpansionReason.MULTI_ISSUE_QUERY)
    if plan.trigger_on_temporal_block and plan.temporal_blocked_source_ids:
        reasons.append(FullCorpusExpansionReason.TEMPORAL_BLOCK_PRESENT)
    return _unique_reasons(reasons)


def _filters_for_source(plan: FullCorpusExpansionPlan, source_id: str) -> RetrievalFilters:
    return RetrievalFilters(
        source_types={SourceType.NORMATIVA},
        chunk_types=set(plan.allowed_chunk_types),
        document_ids={source_id},
    )


def _accept_expansion_hit(
    hit: RetrievalHit,
    *,
    expected_source_id: str,
    normative_corpus_ids: set[str],
) -> tuple[bool, bool, bool]:
    non_normative = hit.metadata.source_type is not SourceType.NORMATIVA
    outside_corpus = (
        hit.metadata.document_id not in normative_corpus_ids
        or hit.metadata.document_id != expected_source_id
    )
    return (not non_normative and not outside_corpus, non_normative, outside_corpus)


def _score_expansion_hit(
    hit: RetrievalHit,
    *,
    source_relevance: float,
    policy: _FullCorpusExpansionPolicy,
) -> float:
    semantic = min(1.0, max(0.0, hit.score))
    return min(
        1.0,
        policy.semantic_score_weight * semantic
        + policy.source_priority_weight * source_relevance,
    )


def _merge_hits(
    *,
    focused_retrieval: RetrievalResult | None,
    focused_execution: FocusedRAGExecution | None,
    expansion_candidates: dict[str, _ExpansionCandidate],
    source_rank: dict[str, int],
    top_k: int,
    policy: _FullCorpusExpansionPolicy,
) -> tuple[list[RetrievalHit], list[str], list[str]]:
    exact_ids = set(focused_execution.exact_seed_hit_ids if focused_execution else [])
    scored: dict[str, tuple[RetrievalHit, bool, bool, int, float]] = {}

    if focused_retrieval is not None:
        for hit in focused_retrieval.hits:
            exact = hit.chunk_id in exact_ids
            score = 1.0 if exact else min(1.0, max(0.0, hit.score) + policy.focused_merge_bonus)
            scored[hit.chunk_id] = (
                hit,
                True,
                exact,
                source_rank.get(hit.metadata.document_id, 12),
                score,
            )

    for item in expansion_candidates.values():
        current = scored.get(item.hit.chunk_id)
        candidate = (
            item.hit,
            False,
            False,
            item.source_rank,
            item.final_score,
        )
        if current is None or item.final_score > current[4]:
            scored[item.hit.chunk_id] = candidate

    ordered = sorted(
        scored.values(),
        key=lambda item: (
            not item[2],
            -item[4],
            not item[1],
            item[3],
            item[0].chunk_id,
        ),
    )[:top_k]
    hits = [
        item[0].model_copy(update={"rank": rank, "score": item[4]})
        for rank, item in enumerate(ordered, start=1)
    ]
    retained_focus_ids = [item[0].chunk_id for item in ordered if item[1]]
    retained_expansion_ids = [item[0].chunk_id for item in ordered if not item[1]]
    return hits, retained_focus_ids, retained_expansion_ids


def execute_full_corpus_expansion(
    query: str,
    *,
    plan: FullCorpusExpansionPlan,
    retriever: RetrieverLike,
    top_k: int,
    focused_retrieval: RetrievalResult | None = None,
    focused_execution: FocusedRAGExecution | None = None,
) -> FullCorpusExpansionRun:
    """Decide y, cuando procede, expande D.7 a los 12 corpus normativos A.8."""
    clean_query = query.strip()
    if not clean_query:
        raise FullCorpusExpansionError("La consulta D.8 no puede estar vacía.")
    if top_k < 1 or top_k > 20:
        raise FullCorpusExpansionError("top_k D.8 debe estar entre 1 y 20.")
    if not plan.plan_applied or not plan.expansion_to_full_corpus_enabled:
        raise FullCorpusExpansionError("D.8 requiere un plan de expansión activo.")
    if (focused_retrieval is None) != (focused_execution is None):
        raise FullCorpusExpansionError("D.8 requiere retrieval y ejecución D.7 conjuntamente.")

    policy = load_default_full_corpus_expansion_policy()
    reasons = _expansion_reasons(plan, focused_execution)
    expansion_applied = bool(reasons)
    source_rank = {
        source_id: rank
        for rank, source_id in enumerate(
            [*plan.focus_source_ids, *plan.expansion_source_ids],
            start=1,
        )
    }

    if not expansion_applied:
        assert focused_retrieval is not None
        assert focused_execution is not None
        execution = FullCorpusExpansionExecution(
            expansion_applied=False,
            trigger_reasons=[],
            requested_top_k=top_k,
            candidate_count=focused_retrieval.candidate_count,
            returned_count=focused_retrieval.returned_count,
            focus_source_ids=list(plan.focus_source_ids),
            searched_expansion_source_ids=[],
            combined_searched_source_ids=list(plan.focus_source_ids),
            focused_hit_chunk_ids=[item.chunk_id for item in focused_retrieval.hits],
            expansion_hit_chunk_ids=[],
            merged_hit_chunk_ids=[item.chunk_id for item in focused_retrieval.hits],
            hit_source_ids=_unique(
                [item.metadata.document_id for item in focused_retrieval.hits]
            ),
            normative_only=True,
            focused_priority_preserved=True,
            normative_text_retrieved=bool(focused_retrieval.hits),
            full_corpus_search_coverage_complete=False,
            full_normative_corpus_preserved=True,
            source_exclusion_enabled=False,
            requires_normative_validation=True,
            requires_temporal_validation=True,
            temporal_validation_completed=False,
            can_control_legal_decision=False,
        )
        return FullCorpusExpansionRun(retrieval=focused_retrieval, execution=execution)

    candidates: dict[str, _ExpansionCandidate] = {}
    candidate_count = focused_retrieval.candidate_count if focused_retrieval else 0
    rejected_non_normative = 0
    rejected_outside_corpus = 0
    corpus_set = set(plan.normative_corpus_ids)

    for source_id in plan.expansion_source_ids:
        result = retriever.search(
            clean_query,
            top_k=min(policy.per_source_top_k, top_k),
            filters=_filters_for_source(plan, source_id),
        )
        candidate_count += result.candidate_count
        for hit in result.hits:
            accepted, non_normative, outside_corpus = _accept_expansion_hit(
                hit,
                expected_source_id=source_id,
                normative_corpus_ids=corpus_set,
            )
            rejected_non_normative += int(non_normative)
            rejected_outside_corpus += int(outside_corpus)
            if not accepted:
                continue
            score = _score_expansion_hit(
                hit,
                source_relevance=plan.source_relevance_scores[source_id],
                policy=policy,
            )
            current = candidates.get(hit.chunk_id)
            if current is None or score > current.final_score:
                candidates[hit.chunk_id] = _ExpansionCandidate(
                    hit=hit,
                    source_rank=source_rank[source_id],
                    final_score=score,
                )

    hits, retained_focus_ids, retained_expansion_ids = _merge_hits(
        focused_retrieval=focused_retrieval,
        focused_execution=focused_execution,
        expansion_candidates=candidates,
        source_rank=source_rank,
        top_k=top_k,
        policy=policy,
    )
    retrieval = RetrievalResult(
        query=clean_query,
        requested_top_k=top_k,
        candidate_count=candidate_count,
        returned_count=len(hits),
        hits=hits,
    )
    combined_searched = _unique(
        [*plan.focus_source_ids, *plan.expansion_source_ids]
    )
    execution = FullCorpusExpansionExecution(
        expansion_applied=True,
        trigger_reasons=reasons,
        requested_top_k=top_k,
        candidate_count=candidate_count,
        returned_count=len(hits),
        focus_source_ids=list(plan.focus_source_ids),
        searched_expansion_source_ids=list(plan.expansion_source_ids),
        combined_searched_source_ids=combined_searched,
        focused_hit_chunk_ids=retained_focus_ids,
        expansion_hit_chunk_ids=retained_expansion_ids,
        merged_hit_chunk_ids=[item.chunk_id for item in hits],
        hit_source_ids=_unique([item.metadata.document_id for item in hits]),
        rejected_non_normative_hits=rejected_non_normative,
        rejected_outside_corpus_hits=rejected_outside_corpus,
        normative_only=True,
        focused_priority_preserved=True,
        normative_text_retrieved=bool(hits),
        full_corpus_search_coverage_complete=(
            set(combined_searched) == set(plan.normative_corpus_ids)
        ),
        full_normative_corpus_preserved=True,
        source_exclusion_enabled=False,
        requires_normative_validation=True,
        requires_temporal_validation=True,
        temporal_validation_completed=False,
        can_control_legal_decision=False,
    )
    return FullCorpusExpansionRun(retrieval=retrieval, execution=execution)
