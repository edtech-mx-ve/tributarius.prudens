from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.domain.chunks import LegalChunk, LegalChunkType
from app.domain.documents import SourceType
from app.domain.query import (
    NormativeRankingIntegration,
    StructuralNavigationIntegration,
    StructuralNavigationLevel,
    StructuralNavigationStrategy,
    StructuralNavigationTarget,
)


class StructuralNavigationError(RuntimeError):
    """Error controlado de navegación jurídica estructural D.6."""


class _StructuralNavigationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1200)
    hierarchy_levels: list[StructuralNavigationLevel] = Field(min_length=4, max_length=4)
    focus_only: bool = True
    exact_article_seed_enabled: bool = True
    hierarchy_descent_fallback: bool = True
    full_normative_corpus_preserved: bool = True
    source_exclusion_enabled: bool = False
    uses_existing_chunk_hierarchy: bool = True
    requires_normative_validation: bool = True
    requires_temporal_validation: bool = True
    rag_retrieval_enabled: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d6_policy_boundary(self) -> _StructuralNavigationPolicy:
        if self.hierarchy_levels != list(StructuralNavigationLevel):
            raise ValueError("D.6 exige título/capítulo/sección/artículo en ese orden.")
        if not self.focus_only:
            raise ValueError("D.6 navega el foco D.5; D.8 expande después al corpus completo.")
        if not self.exact_article_seed_enabled or not self.hierarchy_descent_fallback:
            raise ValueError("D.6 requiere semillas exactas y descenso jerárquico de respaldo.")
        if not self.full_normative_corpus_preserved or self.source_exclusion_enabled:
            raise ValueError("D.6 no puede excluir fuentes normativas.")
        if not self.uses_existing_chunk_hierarchy:
            raise ValueError("D.6 debe reutilizar app.domain.chunks.LegalHierarchy.")
        if not self.requires_normative_validation or not self.requires_temporal_validation:
            raise ValueError("D.6 no reemplaza validación normativa ni temporal.")
        if self.rag_retrieval_enabled or self.can_control_legal_decision:
            raise ValueError("D.6 no puede adelantar D.7 ni controlar Legal Decision.")
        return self


def _resource_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "resources"


@lru_cache(maxsize=1)
def load_default_structural_navigation_policy() -> _StructuralNavigationPolicy:
    path = _resource_dir() / "structural_navigation_policy.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _StructuralNavigationPolicy.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise StructuralNavigationError("La política estructural D.6 no es válida.") from exc


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _source_from_ref(ref: str) -> str:
    return ref.split(":", 1)[0]


def _article_identifier_from_ref(ref: str) -> str:
    try:
        _source, identifier = ref.split(":", 1)
    except ValueError as exc:
        raise StructuralNavigationError(f"Referencia normativa D.6 inválida: {ref}") from exc
    if not re.fullmatch(r"articulo_[0-9]+(?:_[a-z0-9]+)*", identifier):
        raise StructuralNavigationError(f"D.6 sólo acepta semillas de artículo: {ref}")
    return identifier


def build_structural_navigation(
    ranking: NormativeRankingIntegration,
) -> StructuralNavigationIntegration:
    """Convierte D.5 en rutas focales, sin recuperar todavía contenido normativo."""
    policy = load_default_structural_navigation_policy()

    if len(ranking.normative_corpus_ids) != 12:
        raise StructuralNavigationError("D.6 requiere exactamente los 12 corpus A.8.")
    if not ranking.full_normative_corpus_preserved or ranking.source_exclusion_enabled:
        raise StructuralNavigationError("D.5 no preservó el espacio normativo requerido por D.6.")
    if ranking.structural_navigation_enabled or ranking.rag_retrieval_enabled:
        raise StructuralNavigationError("D.6 recibió una salida D.5 con etapas futuras activadas.")

    ranked_by_id = {item.corpus_id: item for item in ranking.ranked_sources}
    targets: list[StructuralNavigationTarget] = []
    for navigation_rank, corpus_id in enumerate(ranking.focus_source_ids, start=1):
        source = ranked_by_id.get(corpus_id)
        if source is None:
            raise StructuralNavigationError(f"Foco D.5 inexistente en ranking: {corpus_id}")
        refs = _unique(
            [ref for ref in source.exact_normative_refs if _source_from_ref(ref) == corpus_id]
        )
        identifiers = [_article_identifier_from_ref(ref) for ref in refs]
        seeded = bool(refs)
        targets.append(
            StructuralNavigationTarget(
                rank=navigation_rank,
                corpus_id=corpus_id,
                source_rank=source.rank,
                relevance_score=source.relevance_score,
                navigation_levels=list(policy.hierarchy_levels),
                target_level=StructuralNavigationLevel.ARTICLE,
                strategy=(
                    StructuralNavigationStrategy.EXACT_ARTICLE_SEED
                    if seeded
                    else StructuralNavigationStrategy.HIERARCHY_DESCENT
                ),
                exact_normative_refs=refs,
                article_identifiers=identifiers,
                hierarchy_scan_required=not seeded,
                rbs_temporal_block_detected=source.rbs_temporal_block_detected,
                requires_normative_validation=True,
                requires_temporal_validation=True,
                can_control_legal_decision=False,
            )
        )

    exact_refs = _unique([ref for target in targets for ref in target.exact_normative_refs])
    temporal_blocked_source_ids = [
        item.corpus_id for item in ranking.ranked_sources if item.rbs_temporal_block_detected
    ]
    return StructuralNavigationIntegration(
        navigation_applied=bool(targets),
        targets=targets,
        focus_source_ids=[item.corpus_id for item in targets],
        hierarchy_levels=list(policy.hierarchy_levels),
        exact_normative_refs=exact_refs,
        temporal_blocked_source_ids=temporal_blocked_source_ids,
        normative_corpus_ids=list(ranking.normative_corpus_ids),
        full_normative_corpus_preserved=True,
        source_exclusion_enabled=False,
        structural_navigation_enabled=True,
        uses_existing_chunk_hierarchy=True,
        normative_text_retrieved=False,
        requires_normative_validation=True,
        requires_temporal_validation=True,
        temporal_validation_completed=False,
        rag_retrieval_enabled=False,
        can_control_legal_decision=False,
    )


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return " ".join(
        "".join(char for char in normalized if not unicodedata.combining(char)).split()
    )


def _normalize_article_identifier(value: str) -> str | None:
    clean = _fold(value).replace("º", "o").replace("°", "o")
    if clean.startswith("articulo_"):
        return clean.replace("-", "_")
    match = re.search(
        r"\bart(?:iculo|\.)?\s*([0-9]+)(?:o\.?)?(?:\s*[-.]?\s*([a-z]+))?",
        clean,
    )
    if match is None:
        match = re.search(r"\b([0-9]+)(?:o\.)?(?:\s*[-.]?\s*([a-z]+))?\b", clean)
    if match is None:
        return None
    number, suffix = match.group(1), match.group(2)
    return f"articulo_{number}_{suffix}" if suffix else f"articulo_{number}"


def _chunk_document_id(chunk: LegalChunk) -> str:
    return (chunk.metadata.canonical_id or chunk.metadata.document_id).strip().casefold()


def _structural_label(chunk: LegalChunk, level: StructuralNavigationLevel) -> str | None:
    hierarchy = chunk.metadata.hierarchy
    if level is StructuralNavigationLevel.TITLE:
        return hierarchy.title
    if level is StructuralNavigationLevel.CHAPTER:
        return hierarchy.chapter
    if level is StructuralNavigationLevel.SECTION:
        return hierarchy.section
    return hierarchy.article or chunk.metadata.source_unit_label or chunk.metadata.legal_identifier


def resolve_structural_path(
    chunks: list[LegalChunk],
    *,
    corpus_id: str,
    article_identifier: str,
) -> list[LegalChunk]:
    """Resuelve breadcrumb título→capítulo→sección→artículo sobre chunks ya existentes.

    D.6 sólo navega metadatos estructurales. No puntúa ni recupera semánticamente texto.
    """
    expected_article = _normalize_article_identifier(article_identifier)
    if expected_article is None:
        raise StructuralNavigationError("No se pudo normalizar el artículo solicitado.")

    corpus = [
        chunk
        for chunk in chunks
        if chunk.metadata.source_type is SourceType.NORMATIVA
        and _chunk_document_id(chunk) == corpus_id.casefold()
    ]
    article = next(
        (
            chunk
            for chunk in corpus
            if chunk.metadata.chunk_type is LegalChunkType.ARTICLE
            and _normalize_article_identifier(
                _structural_label(chunk, StructuralNavigationLevel.ARTICLE) or ""
            )
            == expected_article
        ),
        None,
    )
    if article is None:
        return []

    path: list[LegalChunk] = []
    hierarchy = article.metadata.hierarchy
    labels: list[tuple[StructuralNavigationLevel, LegalChunkType, str | None]] = [
        (StructuralNavigationLevel.TITLE, LegalChunkType.TITLE, hierarchy.title),
        (StructuralNavigationLevel.CHAPTER, LegalChunkType.CHAPTER, hierarchy.chapter),
        (StructuralNavigationLevel.SECTION, LegalChunkType.SECTION, hierarchy.section),
    ]
    for level, chunk_type, label in labels:
        if not label:
            continue
        expected = _fold(label)
        ancestor = next(
            (
                chunk
                for chunk in corpus
                if chunk.metadata.chunk_type is chunk_type
                and _fold(_structural_label(chunk, level) or chunk.text) == expected
            ),
            None,
        )
        if ancestor is not None:
            path.append(ancestor)
    path.append(article)
    return path
