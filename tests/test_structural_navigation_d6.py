from __future__ import annotations

from app.domain.chunks import ChunkMetadata, LegalChunk, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from app.domain.query import (
    QueryAnalysis,
    StructuralNavigationIntegration,
    StructuralNavigationLevel,
    StructuralNavigationStrategy,
)
from app.services.structural_navigation import (
    load_default_structural_navigation_policy,
    resolve_structural_path,
)
from llm.providers.runtime_query import RuntimeQueryAnalyzerProvider
from llm.query_analyzer import QueryAnalyzer


def _analyze(query: str) -> QueryAnalysis:
    return QueryAnalyzer(RuntimeQueryAnalyzerProvider()).analyze(query)


def _navigation(query: str) -> StructuralNavigationIntegration:
    result = _analyze(query)
    assert result.normative_ranking is not None
    assert result.structural_navigation is not None
    return result.structural_navigation


def _chunk(
    index: int,
    chunk_type: LegalChunkType,
    text: str,
    hierarchy: LegalHierarchy,
    legal_identifier: str | None = None,
) -> LegalChunk:
    return LegalChunk(
        chunk_id=f"lisr-navigation-{index:03d}",
        text=text,
        metadata=ChunkMetadata(
            document_id="lisr",
            canonical_id="lisr",
            source_type=SourceType.NORMATIVA,
            source_filename="LISR.md",
            chunk_index=index,
            chunk_type=chunk_type,
            legal_identifier=legal_identifier,
            hierarchy=hierarchy,
            source_sha256="a" * 64,
        ),
    )


def test_d6_professional_isr_builds_exact_article_routes_over_d5_focus() -> None:
    navigation = _navigation(
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    by_id = {item.corpus_id: item for item in navigation.targets}

    assert navigation.focus_source_ids[:2] == ["lisr", "cff"]
    assert navigation.navigation_applied is True
    assert navigation.hierarchy_levels == list(StructuralNavigationLevel)
    assert by_id["lisr"].strategy is StructuralNavigationStrategy.EXACT_ARTICLE_SEED
    assert "lisr:articulo_100" in by_id["lisr"].exact_normative_refs
    assert "lisr:articulo_106" in by_id["lisr"].exact_normative_refs
    assert "articulo_100" in by_id["lisr"].article_identifiers
    assert by_id["lisr"].hierarchy_scan_required is False


def test_d6_defense_preserves_exact_lfdc_article_seed() -> None:
    navigation = _navigation(
        "El SAT me notificó un crédito fiscal y quiero impugnarlo "
        "mediante una defensa en 2026."
    )
    by_id = {item.corpus_id: item for item in navigation.targets}

    assert navigation.focus_source_ids == ["cff", "lfdc", "lfpca", "lotfja"]
    assert by_id["lfdc"].exact_normative_refs == ["lfdc:articulo_2"]
    assert by_id["lfdc"].article_identifiers == ["articulo_2"]
    assert by_id["lfpca"].strategy is StructuralNavigationStrategy.HIERARCHY_DESCENT
    assert by_id["lfpca"].hierarchy_scan_required is True


def test_d6_unknown_query_does_not_invent_navigation_targets() -> None:
    navigation = _navigation("Necesito orientación sobre un asunto que no he descrito todavía.")

    assert navigation.navigation_applied is False
    assert navigation.targets == []
    assert navigation.focus_source_ids == []
    assert navigation.exact_normative_refs == []
    assert len(navigation.normative_corpus_ids) == 12


def test_d6_rif_keeps_temporal_review_pending() -> None:
    navigation = _navigation("¿Cómo calculaba ISR una persona física en RIF durante 2020?")

    assert navigation.requires_temporal_validation is True
    assert navigation.temporal_validation_completed is False
    assert navigation.normative_text_retrieved is False
    assert navigation.rag_retrieval_enabled is False
    assert "liva" in navigation.temporal_blocked_source_ids


def test_d6_reuses_existing_chunk_hierarchy_and_resolves_full_article_breadcrumb() -> None:
    title = "TÍTULO IV DE LAS PERSONAS FÍSICAS"
    chapter = "CAPÍTULO II DE LOS INGRESOS POR ACTIVIDADES EMPRESARIALES"
    section = "SECCIÓN I DE LAS PERSONAS FÍSICAS CON ACTIVIDADES EMPRESARIALES"
    chunks = [
        _chunk(0, LegalChunkType.TITLE, title, LegalHierarchy(title=title)),
        _chunk(
            1,
            LegalChunkType.CHAPTER,
            chapter,
            LegalHierarchy(title=title, chapter=chapter),
        ),
        _chunk(
            2,
            LegalChunkType.SECTION,
            section,
            LegalHierarchy(title=title, chapter=chapter, section=section),
        ),
        _chunk(
            3,
            LegalChunkType.ARTICLE,
            "ARTÍCULO 106",
            LegalHierarchy(
                title=title,
                chapter=chapter,
                section=section,
                article="106",
            ),
            legal_identifier="106",
        ),
    ]

    path = resolve_structural_path(
        chunks,
        corpus_id="lisr",
        article_identifier="articulo_106",
    )

    assert [item.metadata.chunk_type for item in path] == [
        LegalChunkType.TITLE,
        LegalChunkType.CHAPTER,
        LegalChunkType.SECTION,
        LegalChunkType.ARTICLE,
    ]
    assert path[-1].metadata.legal_identifier == "106"


def test_d6_structural_resolution_returns_empty_when_article_is_absent() -> None:
    chunks = [
        _chunk(
            0,
            LegalChunkType.ARTICLE,
            "ARTÍCULO 100",
            LegalHierarchy(article="100"),
            legal_identifier="100",
        )
    ]

    assert (
        resolve_structural_path(
            chunks,
            corpus_id="lisr",
            article_identifier="articulo_106",
        )
        == []
    )


def test_d6_is_navigation_only_and_preserves_complete_a8_space() -> None:
    navigation = _navigation(
        "Soy persona física y presto servicios profesionales; "
        "quiero calcular ISR del ejercicio 2025."
    )
    policy = load_default_structural_navigation_policy()

    assert navigation.hierarchy_levels == policy.hierarchy_levels
    assert navigation.full_normative_corpus_preserved is True
    assert navigation.source_exclusion_enabled is False
    assert navigation.structural_navigation_enabled is True
    assert navigation.uses_existing_chunk_hierarchy is True
    assert navigation.normative_text_retrieved is False
    assert navigation.requires_normative_validation is True
    assert navigation.requires_temporal_validation is True
    assert navigation.temporal_validation_completed is False
    assert navigation.rag_retrieval_enabled is False
    assert navigation.can_control_legal_decision is False
    assert len(navigation.normative_corpus_ids) == 12
