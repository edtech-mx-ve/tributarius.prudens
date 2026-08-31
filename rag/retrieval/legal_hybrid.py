from __future__ import annotations

import json
import math
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field, ValidationError, model_validator

from app.domain.documents import SourceType
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.models import RetrievalHit, RetrievalResult
from rag.retrieval.retriever import RetrievalError

QueryMode = Literal["normative", "doctrinal", "neutral"]


class LegalRetrievalWeights(BaseModel):
    lexical: float = Field(default=0.10, ge=0.0, le=0.50)
    route: float = Field(default=0.12, ge=0.0, le=0.50)
    authority: float = Field(default=0.05, ge=0.0, le=0.50)
    doctrine: float = Field(default=0.08, ge=0.0, le=0.50)


class DocumentRoute(BaseModel):
    document_id: str = Field(min_length=2, max_length=200)
    aliases: list[str] = Field(min_length=1)
    modes: set[QueryMode] = Field(default_factory=set)


class LegalRetrievalPolicy(BaseModel):
    candidate_pool: int = Field(default=100, ge=5, le=100)
    target_candidates: int = Field(default=5, ge=1, le=20)
    max_hits_per_document: int = Field(default=3, ge=1, le=20)
    weights: LegalRetrievalWeights = Field(default_factory=LegalRetrievalWeights)
    authority_by_role: dict[str, float] = Field(default_factory=dict)
    doctrinal_markers: list[str] = Field(default_factory=list)
    normative_markers: list[str] = Field(default_factory=list)
    document_routes: list[DocumentRoute] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_authority_scores(self) -> LegalRetrievalPolicy:
        invalid = [
            role
            for role, score in self.authority_by_role.items()
            if not 0.0 <= score <= 1.0
        ]
        if invalid:
            raise ValueError(
                "authority_by_role debe contener valores entre 0 y 1: "
                + ", ".join(sorted(invalid))
            )
        return self


class LegalScoreTrace(BaseModel):
    chunk_id: str
    document_id: str
    query_mode: QueryMode
    vector_score: float
    lexical_score: float = Field(ge=0.0, le=1.0)
    route_score: float = Field(ge=0.0, le=1.0)
    authority_score: float = Field(ge=0.0, le=1.0)
    doctrine_score: float = Field(ge=0.0, le=1.0)
    final_score: float
    targeted: bool
    exact_legal_reference: bool = False
    reasons: list[str] = Field(default_factory=list)


class LegalHybridRetrievalResult(BaseModel):
    result: RetrievalResult
    traces: dict[str, LegalScoreTrace]
    query_mode: QueryMode
    routed_document_ids: list[str]
    semantic_candidate_count: int = Field(ge=0)
    enriched_candidate_count: int = Field(ge=0)


class RetrieverLike(Protocol):
    def find_exact_legal_reference(
        self,
        *,
        document_id: str,
        legal_identifier: str,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult: ...

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult: ...


_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_STOPWORDS = frozenset(
    {
        "a",
        "al",
        "de",
        "del",
        "el",
        "en",
        "la",
        "las",
        "los",
        "para",
        "por",
        "que",
        "se",
        "su",
        "sus",
        "un",
        "una",
        "y",
    }
)


def normalize_search_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return " ".join(_WORD_RE.findall(without_marks))


def tokenize_search_text(value: str) -> set[str]:
    return {
        token
        for token in normalize_search_text(value).split()
        if token not in _STOPWORDS and len(token) > 1
    }


def _phrase_matches(query_tokens: set[str], phrase: str) -> bool:
    phrase_tokens = tokenize_search_text(phrase)
    return bool(phrase_tokens) and phrase_tokens.issubset(query_tokens)


def classify_query_mode(query: str, policy: LegalRetrievalPolicy) -> QueryMode:
    normalized = normalize_search_text(query)
    query_tokens = tokenize_search_text(query)

    doctrinal = any(
        normalize_search_text(marker) in normalized
        for marker in policy.doctrinal_markers
    )
    if doctrinal:
        return "doctrinal"

    normative = any(
        _phrase_matches(query_tokens, marker)
        for marker in policy.normative_markers
    )
    return "normative" if normative else "neutral"


def route_documents(
    query: str,
    mode: QueryMode,
    policy: LegalRetrievalPolicy,
) -> set[str]:
    query_tokens = tokenize_search_text(query)
    routed: set[str] = set()
    for route in policy.document_routes:
        if route.modes and mode not in route.modes:
            continue
        if any(_phrase_matches(query_tokens, alias) for alias in route.aliases):
            routed.add(route.document_id)
    return routed


_ARTICLE_REFERENCE_RE = re.compile(
    r"\bart(?:iculo)?\.?\s+(\d+(?:-[a-z]+)?)\b",
    re.IGNORECASE,
)


def extract_article_identifier(query: str) -> str | None:
    decomposed = unicodedata.normalize("NFKD", query.casefold())
    normalized = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    match = _ARTICLE_REFERENCE_RE.search(normalized)
    if match is None:
        return None
    suffix = match.group(1).upper()
    return f"Artículo {suffix}"


def _merge_exact_filter(
    filters: RetrievalFilters | None,
    document_id: str,
    legal_identifier: str,
) -> RetrievalFilters | None:
    active = filters or RetrievalFilters()
    if active.document_ids and document_id not in active.document_ids:
        return None
    if active.legal_identifier is not None:
        requested = normalize_search_text(active.legal_identifier)
        exact = normalize_search_text(legal_identifier)
        if requested != exact:
            return None
    return RetrievalFilters(
        source_types=set(active.source_types),
        chunk_types=set(active.chunk_types),
        fiscal_year=active.fiscal_year,
        version_label=active.version_label,
        document_ids={document_id},
        legal_identifier=legal_identifier,
    )


def lexical_relevance(query: str, hit: RetrievalHit) -> float:
    query_tokens = tokenize_search_text(query)
    if not query_tokens:
        return 0.0

    metadata = hit.metadata
    searchable = " ".join(
        value
        for value in (
            hit.text,
            metadata.document_id,
            metadata.title or "",
            metadata.source_unit_label or "",
            metadata.legal_identifier or "",
            " ".join(metadata.matter),
        )
        if value
    )
    hit_tokens = tokenize_search_text(searchable)
    if not hit_tokens:
        return 0.0

    matched = len(query_tokens & hit_tokens)
    # Cobertura de la consulta; la raíz cuadrada evita premiar en exceso consultas
    # muy cortas sin convertir este componente en un clasificador probabilístico.
    coverage = matched / len(query_tokens)
    density = matched / math.sqrt(len(query_tokens) * len(hit_tokens))
    return min(1.0, 0.8 * coverage + 0.2 * density)


def _authority_score(
    hit: RetrievalHit,
    policy: LegalRetrievalPolicy,
) -> float:
    role = normalize_search_text(hit.metadata.source_role or "").replace(" ", "_")
    if role in policy.authority_by_role:
        return policy.authority_by_role[role]

    if hit.metadata.source_type == SourceType.NORMATIVA:
        return 0.70
    if hit.metadata.source_type == SourceType.UNAM:
        return 0.40
    if hit.metadata.source_type == SourceType.PRODECON:
        return 0.35
    return 0.30


def _doctrine_score(hit: RetrievalHit) -> float:
    role = normalize_search_text(hit.metadata.source_role or "")
    if role == "doctrina" or hit.metadata.source_type == SourceType.UNAM:
        return 1.0
    return 0.0


def _merge_target_filter(
    filters: RetrievalFilters | None,
    document_id: str,
) -> RetrievalFilters | None:
    active = filters or RetrievalFilters()
    if active.document_ids and document_id not in active.document_ids:
        return None
    return RetrievalFilters(
        source_types=set(active.source_types),
        chunk_types=set(active.chunk_types),
        fiscal_year=active.fiscal_year,
        version_label=active.version_label,
        document_ids={document_id},
        legal_identifier=active.legal_identifier,
    )


def _deduplicate_hits(hits: Iterable[RetrievalHit]) -> dict[str, RetrievalHit]:
    unique: dict[str, RetrievalHit] = {}
    for hit in hits:
        current = unique.get(hit.chunk_id)
        if current is None or hit.score > current.score:
            unique[hit.chunk_id] = hit
    return unique


@dataclass(frozen=True)
class LegalHybridRetriever:
    base: RetrieverLike
    policy: LegalRetrievalPolicy

    @classmethod
    def from_policy_file(
        cls,
        base: RetrieverLike,
        path: Path = Path("app/resources/legal_retrieval_policy.json"),
    ) -> LegalHybridRetriever:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            policy = LegalRetrievalPolicy.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise RetrievalError(
                f"No fue posible cargar la política de recuperación: {path}"
            ) from exc
        return cls(base=base, policy=policy)

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult:
        return self.search_with_trace(
            query,
            top_k=top_k,
            filters=filters,
        ).result

    def search_with_trace(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> LegalHybridRetrievalResult:
        clean_query = query.strip()
        if not clean_query:
            raise RetrievalError("La consulta no puede estar vacía.")
        if top_k < 1 or top_k > 100:
            raise RetrievalError("top_k debe estar entre 1 y 100.")

        mode = classify_query_mode(clean_query, self.policy)
        routed = route_documents(clean_query, mode, self.policy)
        exact_identifier = extract_article_identifier(clean_query)
        exact_chunk_ids: set[str] = set()
        exact_hits: list[RetrievalHit] = []
        if exact_identifier is not None:
            for document_id in sorted(routed):
                exact_filter = _merge_exact_filter(
                    filters, document_id, exact_identifier
                )
                if exact_filter is None:
                    continue
                exact = self.base.find_exact_legal_reference(
                    document_id=document_id,
                    legal_identifier=exact_identifier,
                    top_k=self.policy.target_candidates,
                    filters=filters,
                )
                exact_hits.extend(exact.hits)
                exact_chunk_ids.update(hit.chunk_id for hit in exact.hits)

        semantic_k = max(top_k, self.policy.candidate_pool)
        semantic = self.base.search(
            clean_query,
            top_k=semantic_k,
            filters=filters,
        )

        hits = [*exact_hits, *semantic.hits]
        enriched_count = len(exact_hits)

        # Enriquecimiento dirigido: una ruta jurídica explícita debe recuperar
        # candidatos del documento objetivo incluso si ya aparece de forma débil
        # en el pool semántico amplio. El deduplicado posterior evita duplicados.
        for document_id in sorted(routed):
            target_filter = _merge_target_filter(filters, document_id)
            if target_filter is None:
                continue
            targeted = self.base.search(
                clean_query,
                top_k=self.policy.target_candidates,
                filters=target_filter,
            )
            hits.extend(targeted.hits)
            enriched_count += len(targeted.hits)

        unique = _deduplicate_hits(hits)
        scored: list[
            tuple[bool, float, float, str, RetrievalHit, LegalScoreTrace]
        ] = []
        for hit in unique.values():
            lex = lexical_relevance(clean_query, hit)
            target = hit.metadata.document_id in routed
            exact_reference = hit.chunk_id in exact_chunk_ids
            route_score = 1.0 if target else 0.0
            authority = _authority_score(hit, self.policy)
            doctrine = _doctrine_score(hit)

            final_score = hit.score + self.policy.weights.lexical * lex
            reasons: list[str] = [f"semantic={hit.score:.4f}"]
            if exact_reference:
                reasons.append("exact_legal_reference")

            if target:
                final_score += self.policy.weights.route * route_score
                reasons.append("document_route")

            if mode == "normative":
                final_score += self.policy.weights.authority * authority
                reasons.append("legal_authority")
            elif mode == "doctrinal":
                final_score += self.policy.weights.doctrine * doctrine
                if doctrine:
                    reasons.append("doctrinal_fit")

            trace = LegalScoreTrace(
                chunk_id=hit.chunk_id,
                document_id=hit.metadata.document_id,
                query_mode=mode,
                vector_score=hit.score,
                lexical_score=lex,
                route_score=route_score,
                authority_score=authority,
                doctrine_score=doctrine,
                final_score=final_score,
                targeted=target,
                exact_legal_reference=exact_reference,
                reasons=reasons,
            )
            scored.append(
                (
                    exact_reference,
                    final_score,
                    hit.score,
                    hit.chunk_id,
                    hit,
                    trace,
                )
            )

        scored.sort(key=lambda row: (not row[0], -row[1], -row[2], row[3]))

        selected: list[tuple[RetrievalHit, LegalScoreTrace]] = []
        per_document: dict[str, int] = {}
        for _exact, final_score, _vector_score, _chunk_id, hit, trace in scored:
            document_id = hit.metadata.document_id
            count = per_document.get(document_id, 0)
            if count >= self.policy.max_hits_per_document:
                continue
            per_document[document_id] = count + 1
            selected.append(
                (
                    RetrievalHit(
                        rank=len(selected) + 1,
                        score=min(1.0, max(0.0, final_score)),
                        chunk_id=hit.chunk_id,
                        text=hit.text,
                        metadata=hit.metadata,
                    ),
                    trace,
                )
            )
            if len(selected) >= top_k:
                break

        # Cobertura mínima de rutas explícitas: si una ley fue identificada por
        # alias jurídico pero quedó fuera del top_k por competencia semántica,
        # sustituimos únicamente el último resultado no ruteado por el mejor
        # candidato de esa fuente. No fuerza rango 1 ni altera el score interno.
        selected_ids = {hit.chunk_id for hit, _trace in selected}
        selected_documents = {
            hit.metadata.document_id for hit, _trace in selected
        }
        for routed_document in sorted(routed - selected_documents):
            routed_candidate = next(
                (
                    (hit, trace)
                    for _exact, _final, _vector, _chunk_id, hit, trace in scored
                    if hit.metadata.document_id == routed_document
                    and hit.chunk_id not in selected_ids
                ),
                None,
            )
            if routed_candidate is None:
                continue

            replace_index = next(
                (
                    index
                    for index in range(len(selected) - 1, -1, -1)
                    if selected[index][0].metadata.document_id not in routed
                ),
                None,
            )
            if replace_index is None:
                continue

            raw_hit, trace = routed_candidate
            selected_ids.discard(selected[replace_index][0].chunk_id)
            selected[replace_index] = (
                RetrievalHit(
                    rank=replace_index + 1,
                    score=min(1.0, max(0.0, trace.final_score)),
                    chunk_id=raw_hit.chunk_id,
                    text=raw_hit.text,
                    metadata=raw_hit.metadata,
                ),
                trace,
            )
            selected_ids.add(raw_hit.chunk_id)

        normalized_selected = [
            (
                hit.model_copy(update={"rank": rank}),
                trace,
            )
            for rank, (hit, trace) in enumerate(selected, start=1)
        ]

        result = RetrievalResult(
            query=clean_query,
            requested_top_k=top_k,
            candidate_count=semantic.candidate_count,
            returned_count=len(normalized_selected),
            hits=[hit for hit, _trace in normalized_selected],
        )
        return LegalHybridRetrievalResult(
            result=result,
            traces={
                trace.chunk_id: trace
                for _hit, trace in normalized_selected
            },
            query_mode=mode,
            routed_document_ids=sorted(routed),
            semantic_candidate_count=len(semantic.hits),
            enriched_candidate_count=enriched_count,
        )
