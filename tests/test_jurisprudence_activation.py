from app.domain.query import QueryAnalysis, QueryIntent
from jurisprudence.activation import decide_jurisprudence_activation


def analysis(
    intent: QueryIntent,
    *,
    requested: bool = False,
    ambiguities: list[str] | None = None,
) -> QueryAnalysis:
    return QueryAnalysis(
        original_query="Consulta de prueba",
        normalized_query="Consulta de prueba",
        primary_intent=intent,
        jurisprudence_requested=requested,
        ambiguities=ambiguities or [],
    )


def test_jurisprudence_is_off_for_normal_obligation_query() -> None:
    decision = decide_jurisprudence_activation(
        analysis(QueryIntent.IDENTIFY_OBLIGATIONS),
        has_applicable_norms=True,
    )
    assert decision.activated is False
    assert decision.requires_human_review is False


def test_explicit_request_activates_jurisprudence() -> None:
    decision = decide_jurisprudence_activation(
        analysis(QueryIntent.RELATED_JURISPRUDENCE, requested=True),
        has_applicable_norms=False,
    )
    assert decision.activated is True
    assert decision.reason.value == "explicit_request"


def test_interpretation_activates_only_with_identified_norm() -> None:
    without_norm = decide_jurisprudence_activation(
        analysis(QueryIntent.INTERPRET_PROVISION),
        has_applicable_norms=False,
    )
    with_norm = decide_jurisprudence_activation(
        analysis(QueryIntent.INTERPRET_PROVISION),
        has_applicable_norms=True,
    )
    assert without_norm.activated is False
    assert with_norm.activated is True
    assert with_norm.requires_human_review is True


def test_ambiguity_with_norm_activates_review() -> None:
    decision = decide_jurisprudence_activation(
        analysis(
            QueryIntent.IDENTIFY_OBLIGATIONS,
            ambiguities=["Alcance temporal dudoso."],
        ),
        has_applicable_norms=True,
    )
    assert decision.activated is True
    assert decision.reason.value == "ambiguity"


def test_defense_analysis_activates_jurisprudence() -> None:
    decision = decide_jurisprudence_activation(
        analysis(QueryIntent.DEFENSE_OPTIONS),
        has_applicable_norms=False,
    )
    assert decision.activated is True
    assert decision.requires_human_review is True
