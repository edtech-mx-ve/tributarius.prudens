import app.services.hybrid_orchestrator as hybrid_orchestrator_module
from app.domain.cbr import CBRReuseDecision
from tests.test_cbr_hybrid_integration import (
    cbr_case,
    request,
    service,
)


def test_cbr_reuse_consumes_stable_rule_normative_identity(
    monkeypatch,
) -> None:
    original = hybrid_orchestrator_module.build_rule_normative_refs

    def stable_refs(retrieval, applicable_chunk_refs):
        refs = original(retrieval, applicable_chunk_refs)
        refs.add("lisr:articulo_100")
        return refs

    monkeypatch.setattr(
        hybrid_orchestrator_module,
        "build_rule_normative_refs",
        stable_refs,
    )

    result = service(
        [
            cbr_case(
                normative_refs=["lisr:articulo_100"],
            )
        ]
    ).run(request())

    assert len(result.cbr_reuse_assessments) == 1

    assessment = result.cbr_reuse_assessments[0]

    assert assessment.decision is CBRReuseDecision.ELIGIBLE
    assert assessment.shared_normative_refs == [
        "lisr:articulo_100"
    ]
    assert assessment.requires_human_review is False
