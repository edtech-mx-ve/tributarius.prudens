from evaluation.hybrid_llama_diagnostics import (
    F12DiagnosticStructuredProvider,
    diagnose_scenario,
)
from evaluation.hybrid_llama_fixtures import (
    F12ReferenceStructuredProvider,
    build_f12_request,
    build_f12_runtime,
)


def test_f12_6_1_diagnostic_reports_orchestration_review_sources() -> None:
    provider = F12DiagnosticStructuredProvider(F12ReferenceStructuredProvider())
    runtime = build_f12_runtime(provider, provider_is_test_double=True)

    mark = provider.mark()
    result = runtime.run(build_f12_request(with_jurisprudence=False))
    diagnostic = diagnose_scenario(
        scenario_id="F12_WITHOUT_JURISPRUDENCE",
        result=result,
        calls=provider.calls_since(mark),
    )

    assert diagnostic.orchestration_requires_human_review is False
    assert diagnostic.orchestration_review_sources == []
