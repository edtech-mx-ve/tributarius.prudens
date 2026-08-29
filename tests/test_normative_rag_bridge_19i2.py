from datetime import date

from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from app.domain.normative import NormativeApplicabilityRequest
from app.services.normative_engine import evaluate_normative_applicability
from app.services.normative_rag_bridge import (
    build_normative_candidates,
    candidate_from_normative_hit,
)
from rag.retrieval.models import RetrievalHit, RetrievalResult


def _hit(
    *,
    source_type: SourceType = SourceType.NORMATIVA,
    unit: str = "Artículo 1o",
    text: str = "Artículo 1o. Disposición fiscal de prueba.",
    effective_from: str | None = "2026-01-01",
    effective_to: str | None = None,
    version: str | None = "2026-01-01",
) -> RetrievalHit:
    return RetrievalHit(
        rank=1,
        score=0.91,
        chunk_id="r19f-test-liva-article-1",
        text=text,
        metadata=ChunkMetadata(
            document_id="liva",
            source_type=source_type,
            source_filename="liva.md",
            chunk_index=1,
            chunk_type=LegalChunkType.ARTICLE,
            legal_identifier=unit,
            hierarchy=LegalHierarchy(article=unit),
            source_sha256="a" * 64,
            version_label=version,
            source_role="ley",
            document_type="ley",
            title="Ley del Impuesto al Valor Agregado",
            source_unit_type="article",
            source_unit_label=unit,
            matter=["iva"],
            effective_from=effective_from,
            effective_to=effective_to,
        ),
    )


def test_normative_hit_with_temporal_metadata_becomes_candidate() -> None:
    candidate = candidate_from_normative_hit(_hit())

    assert candidate is not None
    assert candidate.ref == "r19f-test-liva-article-1"
    assert candidate.version_label == "2026-01-01"
    assert candidate.effective_from == date(2026, 1, 1)


def test_supporting_sources_never_become_normative_candidates() -> None:
    assert candidate_from_normative_hit(_hit(source_type=SourceType.PRODECON)) is None
    assert candidate_from_normative_hit(_hit(source_type=SourceType.UNAM)) is None


def test_unknown_validity_is_not_silently_promoted() -> None:
    assert candidate_from_normative_hit(_hit(effective_from=None)) is None


def test_inconsistent_article_label_and_text_is_rejected() -> None:
    hit = _hit(
        unit="Artículo 1o",
        text="Artículo 2-C. Las personas físicas...",
    )
    assert candidate_from_normative_hit(hit) is None


def test_candidate_is_applicable_for_query_date_when_temporally_valid() -> None:
    candidate = candidate_from_normative_hit(_hit())
    assert candidate is not None

    result = evaluate_normative_applicability(
        NormativeApplicabilityRequest(
            legal_unit_id=candidate.legal_unit_id,
            version_label=candidate.version_label,
            effective_from=candidate.effective_from,
            effective_to=candidate.effective_to,
            fiscal_year=candidate.fiscal_year,
            query_date=date(2026, 8, 29),
            query_fiscal_year=2026,
        )
    )
    assert result.applicable is True


def test_bridge_deduplicates_and_filters_retrieval() -> None:
    normative = _hit()
    supporting = _hit(source_type=SourceType.PRODECON)
    supporting.chunk_id = "prodecon-support"
    retrieval = RetrievalResult(
        query="IVA fundamento",
        requested_top_k=3,
        candidate_count=3,
        returned_count=3,
        hits=[normative, normative.model_copy(), supporting],
    )

    candidates = build_normative_candidates(retrieval)

    assert len(candidates) == 1
    assert candidates[0].ref == normative.chunk_id


def test_article_identifier_regex_detects_real_article_tokens() -> None:
    assert candidate_from_normative_hit(
        _hit(
            unit="Artículo 1o",
            text="Artículo 1o. Esta disposición sí corresponde.",
        )
    ) is not None
    assert candidate_from_normative_hit(
        _hit(
            unit="Artículo 1o",
            text="Artículo 2-C. Esta disposición no corresponde.",
        )
    ) is None


def test_hyphenated_article_identifier_mismatch_is_rejected() -> None:
    assert candidate_from_normative_hit(
        _hit(
            unit="Artículo 2-C",
            text="Artículo 2-C. Texto coincidente.",
        )
    ) is not None
    assert candidate_from_normative_hit(
        _hit(
            unit="Artículo 2-C",
            text="Artículo 1o. Texto distinto.",
        )
    ) is None
