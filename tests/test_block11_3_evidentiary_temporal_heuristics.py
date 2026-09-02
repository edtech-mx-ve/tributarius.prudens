from __future__ import annotations

from app.domain.hybrid_coordination import (
    HybridCoordinationFactors,
    HybridCoordinationResult,
    HybridReasoningRelation,
)
from app.domain.hybrid_reasoning import NormalizedReasoningResult, ReasoningSource
from app.services.legal_heuristics import evaluate_legal_heuristics


def _coordination(
    *,
    rbs_conflicts: list[str] | None = None,
    cbr_conflicts: list[str] | None = None,
    cbr_uncertainty: list[str] | None = None,
    cbr_temporal_context: str | None = "active",
    cbr_applicability: bool | None = True,
    rbs_temporal_context: str | None = None,
) -> HybridCoordinationResult:
    rbs = NormalizedReasoningResult(
        reasoning_source=ReasoningSource.RBS,
        conclusion="Conclusión normativa",
        legal_basis=["CFF:1"],
        references=["norma:CFF:1"],
        applicability=True,
        temporal_context=rbs_temporal_context,
        conflicting_facts=rbs_conflicts or [],
    )
    cbr = NormalizedReasoningResult(
        reasoning_source=ReasoningSource.CBR,
        conclusion="Resolución experiencial",
        legal_basis=["CFF:1"],
        references=["caso:CBR-001"],
        confidence=0.9,
        uncertainty=cbr_uncertainty or [],
        applicability=cbr_applicability,
        temporal_context=cbr_temporal_context,
        conflicting_facts=cbr_conflicts or [],
    )
    return HybridCoordinationResult(
        relation=HybridReasoningRelation.CONFIRMATION,
        conclusion="Conclusión normativa",
        controlling_source="rbs",
        rbs_result=rbs,
        cbr_result=cbr,
        factors=HybridCoordinationFactors(
            rbs_has_conclusion=True,
            rbs_applicability=True,
            cbr_applicability=cbr_applicability,
            cbr_similarity=0.9,
            cbr_temporal_context=cbr_temporal_context,
            shared_legal_basis_count=1,
            normative_priority_preserved=True,
        ),
        shared_legal_basis=["CFF:1"],
    )


def _codes(coordination: HybridCoordinationResult) -> set[str]:
    return {
        signal.code
        for signal in evaluate_legal_heuristics(coordination).signals
    }


def test_rbs_conflicting_facts_require_probative_review() -> None:
    coordination = _coordination(rbs_conflicts=["ingreso=100 vs ingreso=200"])

    evaluated = evaluate_legal_heuristics(coordination)

    assert "HEUR-EVID-002" in {signal.code for signal in evaluated.signals}
    assert evaluated.requires_review is True
    assert evaluated.canonical_conclusion == coordination.conclusion
    assert evaluated.controlling_source == "rbs"


def test_cbr_fact_differences_warn_without_displacing_rbs() -> None:
    coordination = _coordination(
        cbr_conflicts=["fiscal_year: consulta=2026; caso=2025"]
    )

    evaluated = evaluate_legal_heuristics(coordination)
    signal = next(
        item for item in evaluated.signals if item.code == "HEUR-EVID-003"
    )

    assert signal.requires_review is False
    assert evaluated.canonical_conclusion == "Conclusión normativa"
    assert evaluated.controlling_source == "rbs"
    assert evaluated.normative_priority_preserved is True


def test_cbr_uncertainty_requires_review_when_reuse_remains_possible() -> None:
    coordination = _coordination(
        cbr_uncertainty=["Debe verificarse el soporte documental del caso."]
    )

    evaluated = evaluate_legal_heuristics(coordination)

    assert "HEUR-EVID-004" in {signal.code for signal in evaluated.signals}
    assert evaluated.requires_review is True


def test_historical_cbr_case_requires_vigency_review() -> None:
    coordination = _coordination(cbr_temporal_context="historical")

    evaluated = evaluate_legal_heuristics(coordination)

    assert "HEUR-TEMP-002" in {signal.code for signal in evaluated.signals}
    assert evaluated.requires_review is True
    assert any(
        item.startswith("Verificar vigencia normativa")
        for item in evaluated.analysis_priority
    )


def test_superseded_or_invalidated_cbr_case_is_flagged_for_exclusion() -> None:
    for status in ("superseded", "invalidated"):
        coordination = _coordination(
            cbr_temporal_context=status,
            cbr_applicability=False,
        )

        evaluated = evaluate_legal_heuristics(coordination)

        assert "HEUR-TEMP-003" in {signal.code for signal in evaluated.signals}
        assert evaluated.requires_review is True
        assert any(
            item.startswith("Excluir el precedente")
            for item in evaluated.analysis_priority
        )
        assert evaluated.controlling_source == "rbs"


def test_distinct_explicit_temporal_contexts_require_compatibility_review() -> None:
    coordination = _coordination(
        rbs_temporal_context="2026",
        cbr_temporal_context="2025",
    )

    evaluated = evaluate_legal_heuristics(coordination)

    assert "HEUR-TEMP-001" in {signal.code for signal in evaluated.signals}
    assert evaluated.requires_review is True
    assert evaluated.canonical_conclusion == coordination.conclusion
