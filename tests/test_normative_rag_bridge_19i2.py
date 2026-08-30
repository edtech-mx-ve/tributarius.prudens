from pathlib import Path
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


def test_verified_permanent_cff_snapshot_becomes_candidate_without_invented_dates(
    tmp_path: Path,
) -> None:
    import json

    from app.domain.normative import NormativeValidityStatus
    from app.services.normative_temporal_runtime_guard import load_temporal_runtime_guard

    hit = _hit(
        unit="Artículo 27",
        text="Artículo 27. Las personas deberán solicitar su inscripción en el RFC.",
        effective_from=None,
        effective_to=None,
        version="2026-04-09",
    )
    hit.metadata.document_id = "cff"
    hit.metadata.source_filename = "cff.md"
    hit.metadata.title = "Código Fiscal de la Federación"

    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "source_sprint": "temporal-integrity",
                "policy": "fail-closed",
                "coverage_gaps": [],
                "entries": [],
                "verified_validity": [
                    {
                        "canonical_id": "cff",
                        "validity_status": "verified_in_force",
                        "validity_scope": "document",
                        "validity_basis": "official_consolidated_version",
                        "validity_verified_at": "2026-08-30",
                        "official_source": "https://www.diputados.gob.mx/LeyesBiblio/pdf/CFF.pdf",
                        "reason": "Fuente oficial consolidada verificada para la fecha.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    guard = load_temporal_runtime_guard(registry)

    candidate = candidate_from_normative_hit(hit, temporal_guard=guard)

    assert candidate is not None
    assert candidate.effective_from is None
    assert candidate.effective_to is None
    assert candidate.validity_status is NormativeValidityStatus.VERIFIED_IN_FORCE
    assert candidate.validity_verified_at == date(2026, 8, 30)


def test_unverified_cff_snapshot_remains_fail_closed() -> None:
    hit = _hit(
        unit="Artículo 27",
        text="Artículo 27. Las personas deberán solicitar su inscripción en el RFC.",
        effective_from=None,
        effective_to=None,
        version="2026-04-09",
    )
    hit.metadata.document_id = "cff"
    hit.metadata.last_reform_date = "2026-04-09"
    hit.metadata.publication_date = None

    assert candidate_from_normative_hit(hit) is None


def test_verified_cff_legal_unit_reform_chain_isolated_to_article_27(
    tmp_path: Path,
) -> None:
    import json

    from app.domain.normative import NormativeValidityBasis, NormativeValidityScope
    from app.services.normative_temporal_runtime_guard import load_temporal_runtime_guard

    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": "2.1",
                "source_sprint": "temporal-integrity-legal-unit",
                "policy": "fail-closed",
                "coverage_gaps": [
                    {
                        "canonical_id": "cff",
                        "gap_type": "document_wide_temporal_validity",
                        "status": "unknown_fail_closed",
                        "reason": "Vigencia documental completa no verificada.",
                    }
                ],
                "entries": [],
                "verified_validity": [
                    {
                        "canonical_id": "cff",
                        "legal_identifier": "Artículo 27",
                        "validity_status": "verified_in_force",
                        "validity_scope": "legal_unit",
                        "validity_basis": "verified_reform_chain",
                        "validity_verified_at": "2026-08-31",
                        "official_source": "https://www.diputados.gob.mx/LeyesBiblio/pdf/CFF.pdf",
                        "reason": "Cadena de reforma verificada para el Artículo 27.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    guard = load_temporal_runtime_guard(registry)

    article_27 = _hit(
        unit="Artículo 27",
        text="Artículo 27. Las personas deberán solicitar su inscripción en el RFC.",
        effective_from=None,
        effective_to=None,
        version="2026-04-09",
    )
    article_27.metadata.document_id = "cff"
    article_27.metadata.source_filename = "cff.md"
    article_27.metadata.title = "Código Fiscal de la Federación"

    article_28 = _hit(
        unit="Artículo 28",
        text="Artículo 28. Las personas que de acuerdo con las disposiciones fiscales...",
        effective_from=None,
        effective_to=None,
        version="2026-04-09",
    )
    article_28.metadata.document_id = "cff"
    article_28.metadata.source_filename = "cff.md"
    article_28.metadata.title = "Código Fiscal de la Federación"

    candidate_27 = candidate_from_normative_hit(article_27, temporal_guard=guard)
    candidate_28 = candidate_from_normative_hit(article_28, temporal_guard=guard)

    assert candidate_27 is not None
    assert candidate_27.validity_scope is NormativeValidityScope.LEGAL_UNIT
    assert candidate_27.validity_basis is NormativeValidityBasis.VERIFIED_REFORM_CHAIN
    assert candidate_27.effective_from is None
    assert candidate_27.effective_to is None
    assert candidate_28 is None
