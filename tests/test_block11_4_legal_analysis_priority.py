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
    relation: HybridReasoningRelation = HybridReasoningRelation.CONFIRMATION,
    rbs_legal_basis: list[str] | None = None,
    rbs_uncertainty: list[str] | None = None,
    rbs_conflicts: list[str] | None = None,
    rbs_temporal_context: str | None = None,
    cbr_temporal_context: str | None = "active",
    cbr_conflicts: list[str] | None = None,
    cbr_uncertainty: list[str] | None = None,
    cbr_applicability: bool | None = True,
    requires_review: bool = False,
) -> HybridCoordinationResult:
    rbs = NormalizedReasoningResult(
        reasoning_source=ReasoningSource.RBS,
        conclusion="Conclusión normativa",
        legal_basis=(
            rbs_legal_basis if rbs_legal_basis is not None else ["CFF:1"]
        ),
        references=["norma:CFF:1"],
        uncertainty=rbs_uncertainty or [],
        applicability=True,
        temporal_context=rbs_temporal_context,
        conflicting_facts=rbs_conflicts or [],
    )
    cbr = NormalizedReasoningResult(
        reasoning_source=ReasoningSource.CBR,
        conclusion="Resolución experiencial",
        legal_basis=["CFF:1"],
        references=["caso:CBR-001"],
        confidence=0.91,
        uncertainty=cbr_uncertainty or [],
        applicability=cbr_applicability,
        temporal_context=cbr_temporal_context,
        conflicting_facts=cbr_conflicts or [],
    )
    return HybridCoordinationResult(
        relation=relation,
        conclusion="Conclusión normativa",
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
            normative_priority_preserved=True,
        ),
        shared_legal_basis=["CFF:1"],
        requires_review=requires_review,
    )


def test_clean_confirmation_has_no_artificial_pending_priority() -> None:
    evaluated = evaluate_legal_heuristics(_coordination())

    assert evaluated.analysis_priority == []
    assert evaluated.controlling_source == "rbs"
    assert evaluated.normative_priority_preserved is True


def test_missing_normative_basis_precedes_evidentiary_and_cbr_analogy() -> None:
    evaluated = evaluate_legal_heuristics(
        _coordination(
            relation=HybridReasoningRelation.CORRECTION,
            rbs_legal_basis=[],
            rbs_uncertainty=["Falta corroboración documental."],
            cbr_conflicts=["actividad: consulta=A; caso=B"],
        )
    )

    priorities = evaluated.analysis_priority
    assert priorities.index("Verificar fundamento normativo de la conclusión RBS.") < (
        priorities.index("Completar o depurar evidencia antes del cierre jurídico.")
    )
    assert priorities.index("Completar o depurar evidencia antes del cierre jurídico.") < (
        priorities.index("Priorizar norma aplicable sobre analogía experiencial.")
    )


def test_temporal_review_precedes_cbr_fact_comparison() -> None:
    evaluated = evaluate_legal_heuristics(
        _coordination(
            cbr_temporal_context="historical",
            cbr_applicability=True,
            cbr_conflicts=["fiscal_year: consulta=2026; caso=2024"],
        )
    )

    priorities = evaluated.analysis_priority
    assert priorities.index(
        "Verificar vigencia normativa del precedente histórico."
    ) < priorities.index(
        "Verificar diferencias fácticas antes de reutilizar el caso CBR."
    )


def test_temporal_conflict_precedes_evidentiary_uncertainty() -> None:
    evaluated = evaluate_legal_heuristics(
        _coordination(
            rbs_temporal_context="2026",
            cbr_temporal_context="2025",
            cbr_uncertainty=["Debe verificarse el expediente fuente."],
        )
    )

    priorities = evaluated.analysis_priority
    assert priorities.index(
        "Resolver vigencia y compatibilidad temporal de las fuentes."
    ) < priorities.index(
        "Resolver la incertidumbre del precedente CBR antes de reutilizarlo."
    )


def test_human_review_does_not_displace_normative_controller() -> None:
    coordination = _coordination(
        relation=HybridReasoningRelation.CONTRADICTION,
        requires_review=True,
    )

    evaluated = evaluate_legal_heuristics(coordination)

    assert evaluated.requires_review is True
    assert "Someter la decisión híbrida a revisión humana." in evaluated.analysis_priority
    assert evaluated.canonical_conclusion == coordination.conclusion
    assert evaluated.controlling_source == coordination.controlling_source
    assert evaluated.normative_priority_preserved is True


def test_priority_is_deterministic_and_duplicate_free() -> None:
    coordination = _coordination(
        relation=HybridReasoningRelation.CORRECTION,
        rbs_uncertainty=["Documento faltante."],
        cbr_uncertainty=["Caso sujeto a revisión."],
        cbr_conflicts=["actividad: consulta=A; caso=B"],
    )

    first = evaluate_legal_heuristics(coordination)
    second = evaluate_legal_heuristics(coordination)

    assert first.analysis_priority == second.analysis_priority
    assert len(first.analysis_priority) == len(set(first.analysis_priority))
    assert "heuristics:priority_items=" in " ".join(first.trace)
