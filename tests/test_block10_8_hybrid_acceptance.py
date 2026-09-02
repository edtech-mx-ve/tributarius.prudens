from app.domain.hybrid_coordination import (
    HybridCoordinationContext,
    HybridReasoningRelation,
)
from app.services.hybrid_reasoning_coordinator import coordinate_rbs_cbr
from app.services.traceability import verify_canonical_integrity
from app.web.presenter import present_canonical_result
from app.web.schemas import WebConsultationRequest
from tests.test_block10_4_hybrid_coordination_scenarios import _cbr, _rbs
from tests.test_block10_6_hybrid_traceability import _canonical


def test_block10_accepts_all_six_coordination_relations() -> None:
    relations = {
        coordinate_rbs_cbr(_rbs(), _cbr()).relation,
        coordinate_rbs_cbr(
            _rbs(basis=["CFF:ART-1"]),
            _cbr(basis=["LIVA:ART-1"]),
        ).relation,
        coordinate_rbs_cbr(
            _rbs("Procede la obligación fiscal."),
            _cbr("No procede la obligación fiscal."),
        ).relation,
        coordinate_rbs_cbr(_rbs(None), _cbr()).relation,
        coordinate_rbs_cbr(_rbs(), _cbr(review=True)).relation,
    }
    relations.add(
        coordinate_rbs_cbr(
            _rbs("Aplica la regla general."),
            _cbr("El caso presenta una excepción."),
            context=HybridCoordinationContext(
                exception_supported=True,
                exception_basis=["CFF:ART-5"],
            ),
        ).relation
    )

    assert relations == set(HybridReasoningRelation)


def test_block10_never_promotes_cbr_over_rbs() -> None:
    scenarios = [
        coordinate_rbs_cbr(_rbs(), _cbr()),
        coordinate_rbs_cbr(
            _rbs("Procede la obligación fiscal."),
            _cbr("No procede la obligación fiscal."),
        ),
        coordinate_rbs_cbr(
            _rbs(basis=["CFF:ART-1"]),
            _cbr(basis=["LIVA:ART-1"]),
        ),
        coordinate_rbs_cbr(_rbs(), _cbr(review=True)),
    ]

    assert all(item.controlling_source == "rbs" for item in scenarios)
    assert all(item.factors.normative_priority_preserved for item in scenarios)


def test_block10_requires_review_for_material_legal_conflict() -> None:
    result = coordinate_rbs_cbr(
        _rbs("Procede la obligación fiscal."),
        _cbr("No procede la obligación fiscal."),
    )

    assert result.relation == HybridReasoningRelation.CONTRADICTION
    assert result.requires_review is True
    assert result.conclusion == "Procede la obligación fiscal."


def test_block10_canonical_decision_is_integrity_protected() -> None:
    canonical = _canonical()

    assert canonical.traceability.hybrid_decision is not None
    assert verify_canonical_integrity(canonical) is True

    assert canonical.hybrid_coordination is not None
    canonical.hybrid_coordination["relation"] = "contradiction"
    assert verify_canonical_integrity(canonical) is False


def test_block10_three_explanation_modes_are_legally_invariant() -> None:
    canonical = _canonical()
    results = []
    for mode in ("taxpayer", "student", "professional"):
        results.append(
            present_canonical_result(
                canonical,
                WebConsultationRequest(
                    query="¿Resulta aplicable la obligación fiscal?",
                    mode=mode,
                    fiscal_year=2026,
                ),
            )
        )

    baseline = results[0]
    invariant_fields = (
        "applicable_normative_refs",
        "calculations",
        "cbr",
        "evidence",
        "uncertainties",
        "requires_human_review",
        "hybrid_decision",
    )
    for result in results[1:]:
        for field in invariant_fields:
            assert result[field] == baseline[field]


def test_block10_backward_compatibility_without_hybrid_coordination() -> None:
    canonical = _canonical()
    canonical.hybrid_coordination = None
    canonical.traceability.hybrid_decision = None

    presented = present_canonical_result(
        canonical,
        WebConsultationRequest(query="Consulta fiscal", mode="professional"),
    )

    assert presented["hybrid_decision"] is None
