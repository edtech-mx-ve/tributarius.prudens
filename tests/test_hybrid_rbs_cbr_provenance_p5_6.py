from app.domain.hybrid_coordination import HybridReasoningRelation
from app.domain.hybrid_reasoning import (
    NormalizedReasoningResult,
    ReasoningSource,
)
from app.services.hybrid_reasoning_coordinator import coordinate_rbs_cbr


def test_canonical_cbr_provenance_confirms_active_rbs_without_text_identity() -> None:
    rbs = NormalizedReasoningResult(
        reasoning_source=ReasoningSource.RBS,
        conclusion="Conclusion determinista RBS.",
        legal_basis=[
            "lisr:articulo_100",
            "lisr:articulo_110",
        ],
        applicability=True,
        requires_review=False,
        trace=[
            "1:ISR_PROFESSIONAL_CLASSIFY_001@1.0.0:professional_service_income",
            "2:OBL_PROFESSIONAL_RFC_001@1.0.0:rfc_registration_obligation",
        ],
    )

    cbr = NormalizedReasoningResult(
        reasoning_source=ReasoningSource.CBR,
        conclusion="Resumen experiencial redactado de forma diferente.",
        legal_basis=[
            "lisr:articulo_100",
            "lisr:articulo_110",
        ],
        references=[
            "lisr:articulo_100",
            "lisr:articulo_110",
            "RBS:ISR_PROFESSIONAL_CLASSIFY_001@1.0.0",
            "RBS:OBL_PROFESSIONAL_RFC_001@1.0.0",
        ],
        applicability=True,
        conflicting_facts=[],
        requires_review=False,
    )

    result = coordinate_rbs_cbr(rbs, cbr)

    assert result.relation is HybridReasoningRelation.CONFIRMATION
    assert result.controlling_source == "rbs"
    assert result.requires_review is False


def test_shared_basis_without_rbs_provenance_remains_contradiction() -> None:
    rbs = NormalizedReasoningResult(
        reasoning_source=ReasoningSource.RBS,
        conclusion="Conclusion RBS.",
        legal_basis=["lisr:articulo_100"],
        applicability=True,
        requires_review=False,
        trace=[
            "1:ISR_PROFESSIONAL_CLASSIFY_001@1.0.0:professional_service_income",
        ],
    )

    cbr = NormalizedReasoningResult(
        reasoning_source=ReasoningSource.CBR,
        conclusion="Conclusion distinta.",
        legal_basis=["lisr:articulo_100"],
        references=["lisr:articulo_100"],
        applicability=True,
        conflicting_facts=[],
        requires_review=False,
    )

    result = coordinate_rbs_cbr(rbs, cbr)

    assert result.relation is HybridReasoningRelation.CONTRADICTION
    assert result.requires_review is True
