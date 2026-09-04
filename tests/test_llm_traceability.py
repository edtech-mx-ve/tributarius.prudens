from app.services.llm_traceability import build_llm_trace
from llm.models import ExplanationMode, LlamaStructuredAnswer, RAGExplanation


def explanation() -> RAGExplanation:
    return RAGExplanation(
        question="Consulta fiscal",
        provider_name="test-provider",
        model_name="test-model",
        generation_performed=True,
        retrieved_count=2,
        answer=LlamaStructuredAnswer(
            summary="Conclusión.",
            analysis="Análisis.",
            evidence_ids=["chunk-0001", "juris-chunk-0001"],
            normative_refs=["NORM-001"],
            rule_refs=["RULE-001"],
            calculation_refs=["ISR=2300.00"],
            cbr_refs=["CASE-001"],
            jurisprudence_refs=["juris-chunk-0001"],
            uncertainties=["Verificar hecho X."],
            requires_human_review=True,
            changes_deterministic_result=False,
            asserts_external_legal_authority=False,
        ),
    )


def test_llm_trace_preserves_all_authorized_reasoning_channels() -> None:
    trace = build_llm_trace(
        explanation(),
        explanation_mode=ExplanationMode.PROFESSIONAL,
    )

    assert trace.evidence_ids == ["chunk-0001", "juris-chunk-0001"]
    assert trace.normative_refs == ["NORM-001"]
    assert trace.rule_refs == ["RULE-001"]
    assert trace.calculation_refs == ["ISR=2300.00"]
    assert trace.cbr_refs == ["CASE-001"]
    assert trace.jurisprudence_refs == ["juris-chunk-0001"]
    assert trace.requires_human_review is True
    assert trace.uncertainties == ["Verificar hecho X."]


def test_llm_trace_records_explanation_mode_and_provider() -> None:
    trace = build_llm_trace(
        explanation(),
        explanation_mode=ExplanationMode.STUDENT,
    )

    assert trace.explanation_mode == ExplanationMode.STUDENT
    assert trace.provider_name == "test-provider"
    assert trace.model_name == "test-model"
    assert trace.generated is True


def test_hybrid_result_contract_exposes_optional_llm_trace() -> None:
    from pathlib import Path

    source = Path("app/domain/orchestration.py").read_text(encoding="utf-8")
    assert "llm_trace: LLMTrace | None = None" in source


def test_hybrid_orchestrator_builds_trace_after_explanation() -> None:
    from pathlib import Path

    source = Path("app/services/hybrid_orchestrator.py").read_text(encoding="utf-8")
    explain_pos = source.index("explanation = self._llm_service.explain(")
    trace_pos = source.index("llm_trace = build_llm_trace(")
    result_pos = source.index("result = HybridOrchestrationResult(")
    review_context_pos = source.index("return result.model_copy(")

    assert explain_pos < trace_pos < result_pos < review_context_pos
    assert "explanation_mode=request.explanation_mode" in source
    assert "llm_trace=llm_trace" in source
