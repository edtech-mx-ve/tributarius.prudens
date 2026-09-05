from app.services.hybrid_orchestrator import build_fact_map
from llm.providers.runtime_query import RuntimeQueryAnalyzerProvider
from llm.query_analyzer import QueryAnalyzer


def test_explicit_multidimensional_context_reaches_rbs_fact_map() -> None:
    query = (
        "Soy una persona fisica que presta servicios profesionales "
        "independientes en Mexico durante 2026. "
        "Cuales son mis principales obligaciones de cumplimiento "
        "fiscal en materia de ISR?"
    )

    analysis = QueryAnalyzer(
        RuntimeQueryAnalyzerProvider()
    ).analyze(query)

    facts = build_fact_map(analysis)

    assert facts["matter"] == "ISR"
    assert facts["taxpayer_type"] == "individual"
    assert (
        facts["income_type"]
        == "independent_professional_service"
    )
    assert facts["fiscal_year"] == 2026


def test_bridge_does_not_invent_income_type_without_activity() -> None:
    analysis = QueryAnalyzer(
        RuntimeQueryAnalyzerProvider()
    ).analyze(
        "Soy una persona fisica y necesito conocer mis "
        "obligaciones de ISR durante 2026."
    )

    facts = build_fact_map(analysis)

    assert facts["taxpayer_type"] == "individual"
    assert facts["matter"] == "ISR"
    assert facts["fiscal_year"] == 2026
    assert "income_type" not in facts
