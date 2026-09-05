from pathlib import Path

from app.domain.hybrid_llama_hypotheses import (
    ControlledFiscalHypothesisH1,
    FiscalHypothesisH1Result,
)
from app.domain.orchestration import (
    OrchestrationStage,
    StageStatus,
)
from app.services.hybrid_h1_traceability import (
    build_hybrid_h1_generation_trace,
    build_hybrid_h1_verification_trace,
)


def _valid_h1_result() -> FiscalHypothesisH1Result:
    hypothesis = ControlledFiscalHypothesisH1(
        hypothesis_id="H1-aaaaaaaaaaaaaaaa",
        source_context_sha256="b" * 64,
        legal_problem="Determinar el tratamiento fiscal aplicable.",
        proposition="La consulta requiere contraste juridico posterior.",
        confidence=0.75,
        provider_name="test-provider",
        model_name="test-model",
    )

    return FiscalHypothesisH1Result(
        generation_performed=True,
        hypothesis=hypothesis,
        requires_human_review=False,
        trace=["f3:h1:test"],
    )


def test_f3_h1_generation_is_reported_as_completed() -> None:
    trace = build_hybrid_h1_generation_trace(
        service_configured=True,
        result=_valid_h1_result(),
        generation_failed=False,
    )

    assert trace is not None
    assert trace.stage is OrchestrationStage.LEGAL_HYPOTHESIS
    assert trace.status is StageStatus.COMPLETED
    assert "H1 fiscal F.3" in trace.detail


def test_f3_h1_generation_failure_is_degraded() -> None:
    trace = build_hybrid_h1_generation_trace(
        service_configured=True,
        result=None,
        generation_failed=True,
    )

    assert trace is not None
    assert trace.status is StageStatus.DEGRADED


def test_f3_h1_verification_reports_rbs_and_cbr_contrast() -> None:
    trace = build_hybrid_h1_verification_trace(
        result=_valid_h1_result(),
        rbs_contrast_present=True,
        cbr_contrast_present=True,
        requires_human_review=False,
    )

    assert trace is not None
    assert (
        trace.stage
        is OrchestrationStage.LEGAL_HYPOTHESIS_VERIFICATION
    )
    assert trace.status is StageStatus.COMPLETED
    assert "RBS=true" in trace.detail
    assert "CBR=true" in trace.detail


def test_f3_h1_verification_degrades_when_contrast_requires_review() -> None:
    trace = build_hybrid_h1_verification_trace(
        result=_valid_h1_result(),
        rbs_contrast_present=True,
        cbr_contrast_present=True,
        requires_human_review=True,
    )

    assert trace is not None
    assert trace.status is StageStatus.DEGRADED


def test_orchestrator_uses_f3_trace_when_legacy_service_is_absent() -> None:
    source = Path(
        "app/services/hybrid_orchestrator.py"
    ).read_text(encoding="utf-8")

    assert "build_hybrid_h1_generation_trace(" in source
    assert "build_hybrid_h1_verification_trace(" in source
    assert "hybrid_h1_failed = True" in source
