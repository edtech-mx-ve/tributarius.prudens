from datetime import date

from app.domain.orchestration import HybridOrchestrationRequest, NormativeCandidate
from app.services.hybrid_orchestrator import _evaluate_normative_candidates


def test_unknown_validity_reaches_orchestrator_as_evidence() -> None:
    results, evidence_refs, applicable_refs = _evaluate_normative_candidates(
        HybridOrchestrationRequest(
            query="Analiza el artículo 27 del CFF",
            query_date=date(2026, 8, 31),
            query_fiscal_year=2026,
            normative_candidates=[
                NormativeCandidate(
                    ref="cff-articulo-27",
                    legal_unit_id=27,
                    version_label="CFF-foundational",
                )
            ],
        )
    )
    assert len(results) == 1
    assert evidence_refs == ["cff-articulo-27"]
    assert applicable_refs == []
    assert results[0].evidence_available is True
    assert results[0].applicable is False
    assert results[0].requires_human_review is True


def test_confirmed_norm_is_evidence_and_applicable() -> None:
    results, evidence_refs, applicable_refs = _evaluate_normative_candidates(
        HybridOrchestrationRequest(
            query="Analiza norma de prueba",
            query_date=date(2026, 8, 31),
            query_fiscal_year=2026,
            normative_candidates=[
                NormativeCandidate(
                    ref="norma-2026",
                    legal_unit_id=1,
                    version_label="2026",
                    effective_from=date(2026, 1, 1),
                    effective_to=date(2026, 12, 31),
                    fiscal_year=2026,
                )
            ],
        )
    )
    assert len(results) == 1
    assert evidence_refs == ["norma-2026"]
    assert applicable_refs == ["norma-2026"]
