from __future__ import annotations

from app.domain.hybrid_coordination import (
    HybridCoordinationFactors,
    HybridCoordinationResult,
    HybridReasoningRelation,
)
from app.domain.hybrid_reasoning import NormalizedReasoningResult, ReasoningSource
from app.domain.legal_heuristics import LegalHeuristicKind
from app.services.legal_heuristic_explanation import (
    build_heuristic_explanation_evidence,
)
from app.services.legal_heuristics import evaluate_legal_heuristics
from app.services.legal_heuristics_stage import run_legal_heuristics_stage
from llm.models import DeterministicEvidence, ExplanationMode, LLMGenerationContext


def _coordination(
    *,
    relation: HybridReasoningRelation = HybridReasoningRelation.CONFIRMATION,
    requires_review: bool = False,
    rbs_legal_basis: list[str] | None = None,
    rbs_uncertainty: list[str] | None = None,
    rbs_conflicts: list[str] | None = None,
    rbs_temporal_context: str | None = None,
    cbr_temporal_context: str | None = "active",
    cbr_uncertainty: list[str] | None = None,
    cbr_conflicts: list[str] | None = None,
    cbr_applicability: bool | None = True,
) -> HybridCoordinationResult:
    rbs = NormalizedReasoningResult(
        reasoning_source=ReasoningSource.RBS,
        conclusion="Conclusión normativa controladora",
        legal_basis=(
            ["CFF:1"] if rbs_legal_basis is None else rbs_legal_basis
        ),
        references=["norma:CFF:1"],
        uncertainty=rbs_uncertainty or [],
        applicability=True,
        temporal_context=rbs_temporal_context,
        conflicting_facts=rbs_conflicts or [],
        trace=["rbs:normalized=true"],
    )
    cbr = NormalizedReasoningResult(
        reasoning_source=ReasoningSource.CBR,
        conclusion="Resolución experiencial comparable",
        legal_basis=["CFF:1"],
        references=["caso:CBR-001"],
        confidence=0.91,
        uncertainty=cbr_uncertainty or [],
        applicability=cbr_applicability,
        temporal_context=cbr_temporal_context,
        conflicting_facts=cbr_conflicts or [],
        trace=["cbr:normalized=true"],
    )
    return HybridCoordinationResult(
        relation=relation,
        conclusion="Conclusión normativa controladora",
        controlling_source="rbs",
        rbs_result=rbs,
        cbr_result=cbr,
        factors=HybridCoordinationFactors(
            rbs_has_conclusion=True,
            rbs_applicability=True,
            cbr_applicability=cbr_applicability,
            cbr_similarity=0.91,
            cbr_temporal_context=cbr_temporal_context,
            shared_legal_basis_count=1,
            rbs_requires_review=False,
            cbr_requires_review=requires_review,
            normative_priority_preserved=True,
        ),
        shared_legal_basis=["CFF:1"],
        reasons=["La norma aplicable conserva prioridad sobre el precedente."],
        requires_review=requires_review,
        trace=["hybrid:coordinated=true"],
    )


def test_block11_clean_path_preserves_hybrid_decision() -> None:
    coordination = _coordination()

    evaluation, stage_trace, review = run_legal_heuristics_stage(coordination)

    assert evaluation is not None
    assert evaluation.canonical_conclusion == coordination.conclusion
    assert evaluation.controlling_source == coordination.controlling_source
    assert evaluation.normative_priority_preserved is True
    assert evaluation.requires_review is False
    assert review is False
    assert stage_trace.stage.value == "legal_heuristics"
    assert stage_trace.status.value == "completed"


def test_block11_conflict_escalates_without_replacing_rbs() -> None:
    coordination = _coordination(
        relation=HybridReasoningRelation.CONTRADICTION,
        requires_review=True,
    )

    evaluation = evaluate_legal_heuristics(coordination)

    assert evaluation.requires_review is True
    assert evaluation.canonical_conclusion == "Conclusión normativa controladora"
    assert evaluation.controlling_source == "rbs"
    assert evaluation.normative_priority_preserved is True
    assert any(
        signal.kind == LegalHeuristicKind.HUMAN_REVIEW
        for signal in evaluation.signals
    )


def test_block11_temporal_and_evidentiary_controls_are_cumulative() -> None:
    coordination = _coordination(
        rbs_temporal_context="2026",
        cbr_temporal_context="historical",
        cbr_uncertainty=["Expediente incompleto."],
        cbr_conflicts=["ejercicio: consulta=2026; caso=2024"],
    )

    evaluation = evaluate_legal_heuristics(coordination)
    codes = {signal.code for signal in evaluation.signals}

    assert {"HEUR-TEMP-001", "HEUR-TEMP-002", "HEUR-EVID-003", "HEUR-EVID-004"} <= codes
    assert evaluation.requires_review is True
    assert evaluation.controlling_source == "rbs"


def test_block11_priority_is_deterministic_and_subordinate_to_normative_control() -> None:
    coordination = _coordination(
        relation=HybridReasoningRelation.CORRECTION,
        rbs_legal_basis=[],
        rbs_uncertainty=["Falta soporte documental."],
        cbr_temporal_context="historical",
        cbr_conflicts=["actividad: consulta=A; caso=B"],
    )

    first = evaluate_legal_heuristics(coordination)
    second = evaluate_legal_heuristics(coordination)

    assert first.analysis_priority == second.analysis_priority
    assert len(first.analysis_priority) == len(set(first.analysis_priority))
    assert first.analysis_priority[0] == (
        "Verificar fundamento normativo de la conclusión RBS."
    )
    assert first.controlling_source == "rbs"
    assert first.canonical_conclusion == coordination.conclusion


def test_block11_explanation_projection_is_mode_invariant() -> None:
    evaluation = evaluate_legal_heuristics(
        _coordination(
            cbr_temporal_context="historical",
            cbr_uncertainty=["Debe verificarse vigencia."],
        )
    )
    signals, priorities, review = build_heuristic_explanation_evidence(evaluation)
    evidence = DeterministicEvidence(
        hybrid_conclusion=evaluation.canonical_conclusion,
        hybrid_controlling_source=evaluation.controlling_source,
        heuristic_signals=signals,
        heuristic_priorities=priorities,
        heuristic_requires_review=review,
        requires_human_review=review,
    )

    contexts = [
        LLMGenerationContext.model_construct(
            question="Consulta fiscal",
            evidence=[],
            deterministic_evidence=evidence,
            explanation_mode=mode,
            presentation_instructions=[],
        )
        for mode in ExplanationMode
    ]
    serialized = [
        context.deterministic_evidence.model_dump(mode="json")
        for context in contexts
        if context.deterministic_evidence is not None
    ]

    assert len(serialized) == 3
    assert serialized[0] == serialized[1] == serialized[2]
    assert serialized[0]["hybrid_conclusion"] == "Conclusión normativa controladora"
    assert serialized[0]["hybrid_controlling_source"] == "rbs"


def test_block11_explanation_projection_never_invents_legal_authority() -> None:
    evaluation = evaluate_legal_heuristics(
        _coordination(
            relation=HybridReasoningRelation.CORRECTION,
            cbr_temporal_context="historical",
        )
    )

    signals, priorities, _ = build_heuristic_explanation_evidence(evaluation)
    projected = "\n".join([*signals, *priorities])

    assert "CFF:1" not in projected
    assert "HEUR-" in projected
    assert evaluation.canonical_conclusion == "Conclusión normativa controladora"
    assert evaluation.controlling_source == "rbs"
