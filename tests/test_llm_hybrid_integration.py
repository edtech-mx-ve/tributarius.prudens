from __future__ import annotations

from datetime import date

from app.domain.orchestration import HybridOrchestrationRequest
from llm.models import ExplanationMode


def test_hybrid_request_defaults_to_professional_explanation_mode() -> None:
    request = HybridOrchestrationRequest(
        query="¿Qué tratamiento corresponde?",
        query_date=date(2026, 9, 1),
    )

    assert request.explanation_mode == ExplanationMode.PROFESSIONAL


def test_hybrid_request_accepts_student_explanation_mode() -> None:
    request = HybridOrchestrationRequest(
        query="Explícame el fundamento paso a paso.",
        query_date=date(2026, 9, 1),
        explanation_mode=ExplanationMode.STUDENT,
    )

    assert request.explanation_mode == ExplanationMode.STUDENT


def test_hybrid_orchestrator_forwards_mode_without_changing_deterministic_pipeline() -> None:
    from pathlib import Path

    source = Path("app/services/hybrid_orchestrator.py").read_text(encoding="utf-8")

    deterministic_position = source.index("deterministic = _deterministic_evidence(")
    explain_position = source.index("explanation = self._llm_service.explain(")
    mode_position = source.index("explanation_mode=request.explanation_mode")

    assert deterministic_position < explain_position < mode_position
    assert "deterministic_evidence=deterministic" in source
    assert "explanation_mode=request.explanation_mode" in source


def test_hybrid_trace_records_requested_explanation_mode() -> None:
    from pathlib import Path

    source = Path("app/services/hybrid_orchestrator.py").read_text(encoding="utf-8")

    assert 'f"modo={request.explanation_mode.value}."' in source
