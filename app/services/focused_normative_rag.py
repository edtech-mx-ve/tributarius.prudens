from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.domain.chunks import LegalChunkType
from app.domain.documents import SourceType
from app.domain.query import (
    FocusedRAGExecution,
    FocusedRAGPlan,
    FocusedRAGRetrievalMode,
    FocusedRAGTarget,
    StructuralNavigationIntegration,
)
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.models import RetrievalHit, RetrievalResult


class FocusedRAGError(RuntimeError):
    """Error controlado de recuperación normativa focal D.7."""


class _FocusedRAGPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1200)
    focus_only: bool = True
    normative_only: bool = True
    exact_article_seed_enabled: bool = True
    focused_semantic_enabled: bool = True
    exact_seed_top_k: int = Field(default=2, ge=1, le=20)
    per_source_top_k: int = Field(default=3, ge=1, le=20)
    semantic_score_weight: float = Field(default=0.8, ge=0, le=1)
    source_priority_weight: float = Field(default=0.2, ge=0, le=1)
    allowed_chunk_types: list[LegalChunkType] = Field(min_length=5, max_length=5)
    full_normative_corpus_preserved: bool = True
    source_exclusion_enabled: bool = False
    expansion_to_full_corpus_enabled: bool = False
    expansion_reserved_for_d8: bool = True
    requires_normative_validation: bool = True
    requires_temporal_validation: bool = True
    temporal_validation_completed: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d7_policy_boundary(self) -> _FocusedRAGPolicy:
        if not self.focus_only or not self.normative_only:
            raise ValueError("D.7 debe ser focal y exclusivamente normativo.")
        if not self.exact_article_seed_enabled or not self.focused_semantic_enabled:
            raise ValueError("D.7 requiere semillas exactas y búsqueda semántica focal.")
        if abs(self.semantic_score_weight + self.source_priority_weight - 1.0) > 1e-9:
            raise ValueError("Los pesos D.7 deben sumar 1.0.")
        expected_types = {
            LegalChunkType.ARTICLE,
            LegalChunkType.SECTION,
            LegalChunkType.FRACTION,
            LegalChunkType.SUBSECTION,
            LegalChunkType.PARAGRAPH,
        }
        if set(self.allowed_chunk_types) != expected_types:
            raise ValueError("La política D.7 perdió los tipos materiales de chunk.")
        if not self.full_normative_corpus_preserved or self.source_exclusion_enabled:
            raise ValueError("D.7 no puede excluir corpus del espacio normativo completo.")
        if self.expansion_to_full_corpus_enabled or not self.expansion_reserved_for_d8:
            raise ValueError("La expansión al corpus completo pertenece a D.8.")
        if not self.requires_normative_validation or not self.requires_temporal_validation:
            raise ValueError("D.7 no reemplaza validación normativa ni temporal.")
        if self.temporal_validation_completed or self.can_control_legal_decision:
            raise ValueError("D.7 no puede adelantar D.9 ni controlar Legal Decision.")
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
class FocusedRAGRun:
    retrieval: RetrievalResult
    execution: FocusedRAGExecution


@dataclass(frozen=True)
class _ScoredHit:
    hit: RetrievalHit
    exact_seed: bool
    source_rank: int
    source_relevance_score: float
    final_score: float


def _resource_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "resources"


@lru_cache(maxsize=1)
def load_default_focused_rag_policy() -> _FocusedRAGPolicy:
    path = _resource_dir() / "focused_rag_policy.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _FocusedRAGPolicy.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise FocusedRAGError("La política de RAG focalizado D.7 no es válida.") from exc


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _article_label(identifier: str) -> str:
    prefix = "articulo_"
    if not identifier.startswith(prefix):
        raise FocusedRAGError(f"Identificador de artículo D.7 inválido: {identifier}")
    parts = identifier.removeprefix(prefix).split("_")
    if not parts or not parts[0].isdigit():
        raise FocusedRAGError(f"Identificador de artículo D.7 inválido: {identifier}")
    number = parts[0]
    suffix = "-".join(part.upper() for part in parts[1:])
    return f"Artículo {number}-{suffix}" if suffix else f"Artículo {number}"


def _article_filter_labels(identifier: str) -> tuple[str, ...]:
    label = _article_label(identifier)
    bare = label.removeprefix("Artículo ")
    number, separator, suffix = bare.partition("-")
    variants = [label, bare, f"Artículo {number}o.", f"{number}o."]
    if separator:
        variants.extend(
            [
                f"Artículo {number}o.-{suffix}",
                f"{number}o.-{suffix}",
                f"Artículo {number} {suffix}",
                f"{number} {suffix}",
            ]
        )
    return tuple(dict.fromkeys(variants))


def build_focused_rag_plan(
    navigation: StructuralNavigationIntegration,
) -> FocusedRAGPlan:
    """Convierte D.6 en un plan RAG focal sin recuperar aún contenido."""
    policy = load_default_focused_rag_policy()

    if len(navigation.normative_corpus_ids) != 12:
        raise FocusedRAGError("D.7 requiere exactamente los 12 corpus A.8.")
    if not navigation.full_normative_corpus_preserved or navigation.source_exclusion_enabled:
        raise FocusedRAGError("D.6 no preservó el espacio normativo requerido por D.7.")
    if not navigation.structural_navigation_enabled or navigation.rag_retrieval_enabled:
        raise FocusedRAGError("D.7 recibió una salida D.6 con frontera inválida.")

    targets: list[FocusedRAGTarget] = []
    for target in navigation.targets:
        modes = [FocusedRAGRetrievalMode.FOCUSED_SEMANTIC]
        if target.exact_normative_refs:
            modes.insert(0, FocusedRAGRetrievalMode.EXACT_ARTICLE)
        targets.append(
            FocusedRAGTarget(
                rank=target.rank,
                corpus_id=target.corpus_id,
                source_rank=target.source_rank,
                source_relevance_score=target.relevance_score,
                retrieval_modes=modes,
                exact_normative_refs=list(target.exact_normative_refs),
                article_identifiers=list(target.article_identifiers),
                requires_normative_validation=True,
                requires_temporal_validation=True,
                can_control_legal_decision=False,
            )
        )

    return FocusedRAGPlan(
        plan_applied=bool(targets),
        targets=targets,
        focus_source_ids=[item.corpus_id for item in targets],
        exact_normative_refs=_unique(
            [ref for item in targets for ref in item.exact_normative_refs]
        ),
        temporal_blocked_source_ids=list(navigation.temporal_blocked_source_ids),
        normative_corpus_ids=list(navigation.normative_corpus_ids),
        allowed_chunk_types=list(policy.allowed_chunk_types),
        normative_only=True,
        full_normative_corpus_preserved=True,
        source_exclusion_enabled=False,
        structural_navigation_consumed=True,
        rag_retrieval_enabled=bool(targets),
        normative_text_retrieved=False,
        expansion_to_full_corpus_enabled=False,
        expansion_pending=True,
        requires_normative_validation=True,
        requires_temporal_validation=True,
        temporal_validation_completed=False,
        can_control_legal_decision=False,
    )


def _filters_for_target(
    plan: FocusedRAGPlan,
    corpus_id: str,
    *,
    legal_identifier: str | None = None,
) -> RetrievalFilters:
    return RetrievalFilters(
        source_types={SourceType.NORMATIVA},
        chunk_types=set(plan.allowed_chunk_types),
        document_ids={corpus_id},
        legal_identifier=legal_identifier,
    )


def _score_hit(
    hit: RetrievalHit,
    target: FocusedRAGTarget,
    policy: _FocusedRAGPolicy,
) -> float:
    semantic = min(1.0, max(0.0, hit.score))
    return min(
        1.0,
        policy.semantic_score_weight * semantic
        + policy.source_priority_weight * target.source_relevance_score,
    )


def _stable_legal_ref(hit: RetrievalHit) -> str | None:
    # Import diferido: normative_rag_bridge depende del dominio de orquestación.
    from app.services.normative_rag_bridge import stable_legal_ref_from_hit

    return stable_legal_ref_from_hit(hit)


def _accept_hit(
    hit: RetrievalHit,
    *,
    focus_source_ids: set[str],
    expected_source_id: str,
) -> tuple[bool, bool, bool]:
    non_normative = hit.metadata.source_type is not SourceType.NORMATIVA
    outside_focus = (
        hit.metadata.document_id not in focus_source_ids
        or hit.metadata.document_id != expected_source_id
    )
    return (not non_normative and not outside_focus, non_normative, outside_focus)


def _select_diverse_candidates(
    candidates: dict[str, _ScoredHit],
    *,
    top_k: int,
) -> list[_ScoredHit]:
    """Preserve exact seeds while preventing one source from monopolizing top_k."""
    exact_by_source: dict[int, list[_ScoredHit]] = {}
    semantic: list[_ScoredHit] = []

    for item in candidates.values():
        if item.exact_seed:
            exact_by_source.setdefault(item.source_rank, []).append(item)
        else:
            semantic.append(item)

    for bucket in exact_by_source.values():
        bucket.sort(
            key=lambda item: (
                -item.final_score,
                item.hit.chunk_id,
            )
        )

    selected: list[_ScoredHit] = []
    source_ranks = sorted(exact_by_source)

    while len(selected) < top_k:
        added = False

        for source_rank in source_ranks:
            bucket = exact_by_source[source_rank]
            if not bucket:
                continue

            selected.append(bucket.pop(0))
            added = True

            if len(selected) >= top_k:
                break

        if not added:
            break

    if len(selected) < top_k:
        semantic.sort(
            key=lambda item: (
                -item.final_score,
                item.source_rank,
                item.hit.chunk_id,
            )
        )
        selected.extend(
            semantic[: top_k - len(selected)]
        )

    return selected


def _collect_result(
    candidates: dict[str, _ScoredHit],
    *,
    query: str,
    top_k: int,
    candidate_count: int,
    plan: FocusedRAGPlan,
    rejected_non_normative: int,
    rejected_outside_focus: int,
) -> FocusedRAGRun:
    ordered = _select_diverse_candidates(
        candidates,
        top_k=top_k,
    )
    hits = [
        item.hit.model_copy(
            update={
                "rank": rank,
                "score": item.final_score,
            }
        )
        for rank, item in enumerate(ordered, start=1)
    ]
    retrieval = RetrievalResult(
        query=query,
        requested_top_k=top_k,
        candidate_count=candidate_count,
        returned_count=len(hits),
        hits=hits,
    )
    hit_source_ids = _unique([item.metadata.document_id for item in hits])
    exact_seed_hit_ids = [
        item.hit.chunk_id for item in ordered if item.exact_seed
    ]
    execution = FocusedRAGExecution(
        retrieval_applied=True,
        requested_top_k=top_k,
        candidate_count=candidate_count,
        returned_count=len(hits),
        focus_source_ids=list(plan.focus_source_ids),
        hit_chunk_ids=[item.chunk_id for item in hits],
        hit_source_ids=hit_source_ids,
        exact_seed_hit_ids=exact_seed_hit_ids,
        rejected_non_normative_hits=rejected_non_normative,
        rejected_outside_focus_hits=rejected_outside_focus,
        normative_only=True,
        focus_scope_enforced=True,
        normative_text_retrieved=bool(hits),
        full_normative_corpus_preserved=True,
        expansion_pending=True,
        requires_normative_validation=True,
        requires_temporal_validation=True,
        temporal_validation_completed=False,
        can_control_legal_decision=False,
    )
    return FocusedRAGRun(retrieval=retrieval, execution=execution)


def execute_focused_rag(
    query: str,
    *,
    plan: FocusedRAGPlan,
    retriever: RetrieverLike,
    top_k: int,
) -> FocusedRAGRun:
    """Ejecuta D.7 sobre el foco D.6 y devuelve sólo evidencia normativa interna."""
    clean_query = query.strip()
    if not clean_query:
        raise FocusedRAGError("La consulta D.7 no puede estar vacía.")
    if top_k < 1 or top_k > 20:
        raise FocusedRAGError("top_k D.7 debe estar entre 1 y 20.")
    if not plan.plan_applied or not plan.rag_retrieval_enabled:
        raise FocusedRAGError("D.7 requiere un plan focal activo.")

    policy = load_default_focused_rag_policy()
    focus_ids = set(plan.focus_source_ids)
    candidates: dict[str, _ScoredHit] = {}
    candidate_count = 0
    rejected_non_normative = 0
    rejected_outside_focus = 0

    for target in plan.targets:
        for expected_ref, identifier in zip(
            target.exact_normative_refs,
            target.article_identifiers,
            strict=True,
        ):
            exact_result = None
            for exact_label in _article_filter_labels(identifier):
                exact_result = retriever.search(
                    f"{clean_query} {exact_label}",
                    top_k=policy.exact_seed_top_k,
                    filters=_filters_for_target(
                        plan,
                        target.corpus_id,
                        legal_identifier=exact_label,
                    ),
                )
                candidate_count += exact_result.candidate_count
                if exact_result.hits:
                    break
            if exact_result is None:
                continue
            for hit in exact_result.hits:
                accepted, non_normative, outside_focus = _accept_hit(
                    hit,
                    focus_source_ids=focus_ids,
                    expected_source_id=target.corpus_id,
                )
                rejected_non_normative += int(non_normative)
                rejected_outside_focus += int(outside_focus)
                if not accepted or _stable_legal_ref(hit) != expected_ref:
                    continue
                scored = _ScoredHit(
                    hit=hit,
                    exact_seed=True,
                    source_rank=target.rank,
                    source_relevance_score=target.source_relevance_score,
                    final_score=1.0,
                )
                candidates[hit.chunk_id] = scored

        semantic_result = retriever.search(
            clean_query,
            top_k=min(policy.per_source_top_k, top_k),
            filters=_filters_for_target(plan, target.corpus_id),
        )
        candidate_count += semantic_result.candidate_count
        for hit in semantic_result.hits:
            accepted, non_normative, outside_focus = _accept_hit(
                hit,
                focus_source_ids=focus_ids,
                expected_source_id=target.corpus_id,
            )
            rejected_non_normative += int(non_normative)
            rejected_outside_focus += int(outside_focus)
            if not accepted:
                continue
            scored = _ScoredHit(
                hit=hit,
                exact_seed=False,
                source_rank=target.rank,
                source_relevance_score=target.source_relevance_score,
                final_score=_score_hit(hit, target, policy),
            )
            current = candidates.get(hit.chunk_id)
            if current is None or (
                not current.exact_seed and scored.final_score > current.final_score
            ):
                candidates[hit.chunk_id] = scored

    return _collect_result(
        candidates,
        query=clean_query,
        top_k=top_k,
        candidate_count=candidate_count,
        plan=plan,
        rejected_non_normative=rejected_non_normative,
        rejected_outside_focus=rejected_outside_focus,
    )
