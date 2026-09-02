from __future__ import annotations

from app.domain.hybrid_coordination import (
    HybridCoordinationFactors,
    HybridCoordinationResult,
    HybridReasoningRelation,
)
from app.domain.hybrid_reasoning import NormalizedReasoningResult, ReasoningSource
from app.domain.legal_heuristics import LegalHeuristicKind, LegalHeuristicLevel
from app.services.legal_heuristics import evaluate_legal_heuristics


def _result(
    source: ReasoningSource,
    *,
    conclusion: str | None = "Conclusión A",
    legal_basis: list[str] | None = None,
    references: list[str] | None = None,
    uncertainty: list[str] | None = None,
    applicability: bool | None = True,
    temporal_context: str | None = "2026",
) -> NormalizedReasoningResult:
    return NormalizedReasoningResult(
        reasoning_source=source,
        conclusion=conclusion,
        legal_basis=legal_basis if legal_basis is not None else ["CFF:1"],
        references=references or [],
        uncertainty=uncertainty or [],
        applicability=applicability,
        temporal_context=temporal_context,
    )


def _coordination(
    *,
    relation: HybridReasoningRelation = HybridReasoningRelation.CONFIRMATION,
    conclusion: str | None = "Conclusión A",
    controlling_source: str | None = "rbs",
    rbs: NormalizedReasoningResult | None = None,
    cbr: NormalizedReasoningResult | None = None,
    requires_review: bool = False,
) -> HybridCoordinationResult:
    rbs_result = rbs or _result(ReasoningSource.RBS, conclusion=conclusion)
    cbr_result = cbr or _result(ReasoningSource.CBR, conclusion=conclusion)
    return HybridCoordinationResult(
        relation=relation,
        conclusion=conclusion,
        controlling_source=controlling_source,
        rbs_result=rbs_result,
        cbr_result=cbr_result,
        factors=HybridCoordinationFactors(
            rbs_has_conclusion=rbs_result.conclusion is not None,
            rbs_applicability=rbs_result.applicability,
            cbr_applicability=cbr_result.applicability,
            cbr_similarity=cbr_result.confidence,
            cbr_temporal_context=cbr_result.temporal_context,
            shared_legal_basis_count=1,
            normative_priority_preserved=True,
        ),
        shared_legal_basis=["CFF:1"],
        requires_review=requires_review,
    )


def test_heuristics_never_replace_hybrid_conclusion_or_controller() -> None:
    coordination = _coordination(
        relation=HybridReasoningRelation.CONTRADICTION,
        requires_review=True,
    )

    evaluated = evaluate_legal_heuristics(coordination)

    assert evaluated.canonical_conclusion == coordination.conclusion
    assert evaluated.controlling_source == coordination.controlling_source
    assert evaluated.normative_priority_preserved is True


def test_missing_normative_basis_generates_explicit_review_signal() -> None:
    rbs = _result(ReasoningSource.RBS, legal_basis=[])
    coordination = _coordination(rbs=rbs)

    evaluated = evaluate_legal_heuristics(coordination)

    signal = next(
        item
        for item in evaluated.signals
        if item.kind == LegalHeuristicKind.NORMATIVE_RELEVANCE
    )
    assert signal.code == "HEUR-NORM-001"
    assert signal.level == LegalHeuristicLevel.REVIEW
    assert signal.requires_review is True
    assert evaluated.requires_review is True


def test_insufficient_evidence_is_explicit_and_prioritized() -> None:
    rbs = _result(
        ReasoningSource.RBS,
        uncertainty=["Falta acreditar un hecho relevante."],
        references=["RBS-E1"],
    )
    cbr = _result(ReasoningSource.CBR, references=["CBR-E1"])
    coordination = _coordination(
        relation=HybridReasoningRelation.INSUFFICIENT_EVIDENCE,
        rbs=rbs,
        cbr=cbr,
    )

    evaluated = evaluate_legal_heuristics(coordination)

    signal = next(
        item
        for item in evaluated.signals
        if item.kind == LegalHeuristicKind.EVIDENCE_SUFFICIENCY
    )
    assert signal.requires_review is True
    assert signal.evidence_refs == ["RBS-E1", "CBR-E1"]
    assert "Completar o depurar evidencia" in evaluated.analysis_priority[0]


def test_temporal_conflict_requires_review_without_changing_conclusion() -> None:
    rbs = _result(ReasoningSource.RBS, temporal_context="2026")
    cbr = _result(ReasoningSource.CBR, temporal_context="2024")
    coordination = _coordination(rbs=rbs, cbr=cbr)

    evaluated = evaluate_legal_heuristics(coordination)

    assert any(
        item.kind == LegalHeuristicKind.TEMPORAL_CONFLICT
        and item.requires_review
        for item in evaluated.signals
    )
    assert evaluated.canonical_conclusion == "Conclusión A"


def test_contradiction_and_exception_force_human_review() -> None:
    for relation in (
        HybridReasoningRelation.CONTRADICTION,
        HybridReasoningRelation.EXCEPTION,
    ):
        evaluated = evaluate_legal_heuristics(
            _coordination(relation=relation, requires_review=False)
        )
        assert evaluated.requires_review is True
        assert any(
            item.kind == LegalHeuristicKind.HUMAN_REVIEW
            for item in evaluated.signals
        )


def test_correction_prioritizes_norm_over_case_analogy() -> None:
    evaluated = evaluate_legal_heuristics(
        _coordination(relation=HybridReasoningRelation.CORRECTION)
    )

    signal = next(
        item
        for item in evaluated.signals
        if item.kind == LegalHeuristicKind.ANALYSIS_PRIORITY
    )
    assert signal.level == LegalHeuristicLevel.WARNING
    assert any(
        item.startswith("Priorizar norma aplicable")
        for item in evaluated.analysis_priority
    )


def test_clean_confirmation_has_no_forced_review() -> None:
    evaluated = evaluate_legal_heuristics(_coordination())

    assert evaluated.requires_review is False
    assert evaluated.canonical_conclusion == "Conclusión A"
    assert evaluated.controlling_source == "rbs"
    assert not any(item.requires_review for item in evaluated.signals)
