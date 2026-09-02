from app.web.presenter import present_canonical_result
from app.web.schemas import WebConsultationRequest
from tests.test_block10_6_hybrid_traceability import _canonical


def _present(mode: str) -> dict[str, object]:
    return present_canonical_result(
        _canonical(),
        WebConsultationRequest(
            query="¿Resulta aplicable la obligación fiscal?",
            mode=mode,
            fiscal_year=2026,
        ),
    )


def test_three_modes_preserve_same_hybrid_legal_decision_e2e() -> None:
    results = [_present(mode) for mode in ("taxpayer", "student", "professional")]

    assert [item["mode"] for item in results] == [
        "taxpayer",
        "student",
        "professional",
    ]
    baseline = results[0]
    for result in results[1:]:
        assert result["applicable_normative_refs"] == baseline["applicable_normative_refs"]
        assert result["calculations"] == baseline["calculations"]
        assert result["cbr"] == baseline["cbr"]
        assert result["evidence"] == baseline["evidence"]
        assert result["uncertainties"] == baseline["uncertainties"]
        assert result["requires_human_review"] == baseline["requires_human_review"]
        assert result["hybrid_decision"] == baseline["hybrid_decision"]


def test_web_projection_exposes_complete_hybrid_decision() -> None:
    decision = _present("professional")["hybrid_decision"]

    assert isinstance(decision, dict)
    assert decision["relation"] == "confirmation"
    assert decision["conclusion"] == "La obligación fiscal resulta aplicable."
    assert decision["controlling_source"] == "rbs"
    assert decision["shared_legal_basis"] == ["CFF:ART-1"]
    assert decision["rbs_trace"] == ["rule:RBS-001"]
    assert decision["cbr_trace"] == ["case:CBR-001"]
    assert decision["requires_human_review"] is False


def test_web_projection_does_not_recalculate_hybrid_decision() -> None:
    canonical = _canonical()
    expected = canonical.traceability.hybrid_decision
    assert expected is not None

    presented = present_canonical_result(
        canonical,
        WebConsultationRequest(query="Consulta fiscal", mode="taxpayer", fiscal_year=2026),
    )
    decision = presented["hybrid_decision"]

    assert isinstance(decision, dict)
    assert decision["relation"] == expected.relation
    assert decision["controlling_source"] == expected.controlling_source
    assert decision["reasons"] == expected.reasons
    assert decision["factors"] == expected.factors


def test_hybrid_review_is_preserved_through_web_boundary() -> None:
    canonical = _canonical(review=True)
    presented = present_canonical_result(
        canonical,
        WebConsultationRequest(query="Consulta fiscal", mode="student", fiscal_year=2026),
    )
    decision = presented["hybrid_decision"]

    assert isinstance(decision, dict)
    assert decision["relation"] == "contradiction"
    assert decision["requires_human_review"] is True
    assert presented["requires_human_review"] is canonical.traceability.requires_human_review


def test_absent_hybrid_decision_remains_backward_compatible() -> None:
    canonical = _canonical()
    canonical.traceability.hybrid_decision = None
    canonical.hybrid_coordination = None

    presented = present_canonical_result(
        canonical,
        WebConsultationRequest(query="Consulta fiscal", mode="professional"),
    )

    assert presented["hybrid_decision"] is None
