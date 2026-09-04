from evaluation.hybrid_llama_diagnostics import (
    F12DiagnosticStructuredProvider,
    diagnose_scenario,
)
from evaluation.hybrid_llama_fixtures import (
    F12ReferenceStructuredProvider,
    build_f12_request,
    build_f12_runtime,
)


def test_f12_6_diagnostic_surfaces_review_and_conclusion_chain() -> None:
    provider = F12DiagnosticStructuredProvider(F12ReferenceStructuredProvider())
    runtime = build_f12_runtime(provider, provider_is_test_double=True)

    mark = provider.mark()
    result = runtime.run(build_f12_request(with_jurisprudence=False))
    diagnostic = diagnose_scenario(
        scenario_id="F12_WITHOUT_JURISPRUDENCE",
        result=result,
        calls=provider.calls_since(mark),
    )

    assert diagnostic.runtime_status == "completed"
    assert diagnostic.verification_state == "verified"
    assert diagnostic.verification_review_codes == []
    assert diagnostic.verification_correction_codes == []
    assert diagnostic.semantic_requires_human_review is False
    assert diagnostic.analysis_requires_human_review is False
    assert diagnostic.readiness_requires_human_review is False
    assert diagnostic.decision_requires_human_review is False
    assert diagnostic.analysis_canonical_conclusion == "Perfil sujeto a revisión ISR."
    assert diagnostic.conclusion == "Perfil sujeto a revisión ISR."
