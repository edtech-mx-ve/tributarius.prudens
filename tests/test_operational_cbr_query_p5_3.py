from app.domain.cbr import CBRQuery
from app.domain.query import QueryAnalysis, QueryIntent
from app.services.multidimensional_query_analysis import (
    analyze_query_multidimensional,
)
from app.services.operational_cbr_query import (
    build_operational_cbr_query,
    resolve_operational_cbr_query,
)


def _analysis(
    query: str,
    intent: QueryIntent,
) -> QueryAnalysis:
    multidimensional = analyze_query_multidimensional(
        normalized_query=query,
        primary_intent=intent,
        secondary_intents=[],
        facts=[],
    )

    return QueryAnalysis(
        original_query=query,
        normalized_query=query,
        primary_intent=intent,
        multidimensional=multidimensional,
    )


def test_builds_cbr_query_from_sufficient_query_analysis() -> None:
    analysis = _analysis(
        (
            "Obligaciones de ISR de una persona fisica por "
            "servicios profesionales en 2026"
        ),
        QueryIntent.IDENTIFY_OBLIGATIONS,
    )

    result = build_operational_cbr_query(
        analysis,
        fiscal_year=2026,
        top_k=5,
    )

    assert result is not None
    assert result.taxpayer_type == "individual"
    assert result.activity == "servicios profesionales independientes"
    assert result.tax == "ISR"
    assert result.problem_type == "cumplimiento_fiscal"
    assert result.fiscal_year == 2026
    assert result.top_k == 5


def test_missing_activity_does_not_invent_cbr_query() -> None:
    analysis = _analysis(
        "Obligaciones de ISR de una persona fisica en 2026",
        QueryIntent.IDENTIFY_OBLIGATIONS,
    )

    result = build_operational_cbr_query(
        analysis,
        fiscal_year=2026,
    )

    assert result is None


def test_ambiguous_query_years_fail_closed() -> None:
    analysis = _analysis(
        (
            "Obligaciones de ISR de una persona fisica por "
            "servicios profesionales en 2025 y 2026"
        ),
        QueryIntent.IDENTIFY_OBLIGATIONS,
    )

    result = build_operational_cbr_query(
        analysis,
        fiscal_year=2026,
    )

    assert result is None


def test_clarification_required_disables_automatic_cbr_query() -> None:
    analysis = _analysis(
        (
            "Obligaciones de ISR de una persona fisica por "
            "servicios profesionales en 2026"
        ),
        QueryIntent.IDENTIFY_OBLIGATIONS,
    ).model_copy(
        update={"requires_clarification": True}
    )

    result = build_operational_cbr_query(
        analysis,
        fiscal_year=2026,
    )

    assert result is None


def test_authority_act_and_stage_are_preserved_when_unambiguous() -> None:
    analysis = _analysis(
        (
            "Persona fisica con servicios profesionales, ISR 2026, "
            "en una visita domiciliaria durante facultades de comprobacion"
        ),
        QueryIntent.ANALYZE_AUTHORITY_ACT,
    )

    result = build_operational_cbr_query(
        analysis,
        fiscal_year=2026,
    )

    assert result is not None
    assert result.authority_act == "visita domiciliaria"
    assert result.procedural_stage == "comprobacion"


def test_explicit_cbr_query_has_priority() -> None:
    analysis = _analysis(
        "Consulta fiscal general",
        QueryIntent.UNDERSTAND_TAX_SYSTEM,
    )

    explicit = CBRQuery(
        taxpayer_type="individual",
        activity="actividad empresarial",
        tax="ISR",
        problem_type="cumplimiento_fiscal",
        fiscal_year=2026,
        top_k=3,
    )

    result = resolve_operational_cbr_query(
        analysis,
        explicit_query=explicit,
        fiscal_year=2026,
        top_k=5,
    )

    assert result is explicit


def test_resolver_derives_cbr_query_when_explicit_is_absent() -> None:
    analysis = _analysis(
        (
            "Obligaciones de ISR de una persona fisica por "
            "servicios profesionales en 2026"
        ),
        QueryIntent.IDENTIFY_OBLIGATIONS,
    )

    result = resolve_operational_cbr_query(
        analysis,
        explicit_query=None,
        fiscal_year=2026,
        top_k=5,
    )

    assert result is not None
    assert result.problem_type == "cumplimiento_fiscal"
